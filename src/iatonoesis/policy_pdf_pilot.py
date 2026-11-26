"""Exploratory PDF qualifier binding with Poppler; synthetic only, not OCR or clinical validation."""
import argparse
import hashlib
import json
import random
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

families = (
    ('inline_single', 'development', 1),
    ('inline_double', 'calibration', 2),
    ('detached_stream', 'test', 3),
    ('reverse_stream', 'test', 2),
    ('superscript', 'test', 2),
    ('left_marker', 'test', 2),
    ('damaged', 'test', 3),
)
REQ = re.compile(r'REQ-([A-F])')
MARK = re.compile(r'\*([0-9]{2})')
NOTE = re.compile(r'\*([0-9]{2}):(EXCEPTION-[A-Z0-9]+)')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def generate(seed):
    """Specify intended links before generating actual page text and coordinates."""
    rng = random.Random(seed)
    documents = []
    for family, split, columns in families:
        for index in range(20):
            identifiers = list('ABCDEF')
            rng.shuffle(identifiers)
            numbers = rng.sample(range(1, 100), 6)
            abstract = [(req, f'{num:02}', f'EXCEPTION-{rng.getrandbits(32):08X}')
                        for req, num in zip(identifiers, numbers)]
            gold = sorted([req, note] for req, _, note in abstract)
            reqs, marks, notes = [], [], []
            for i, (req, num, note) in enumerate(abstract):
                x, y = 62 + (i % columns) * (480 // columns), 100 + (i // columns) * 38
                reqs.append(dict(text=f'REQ-{req}', x=x, y=y, size=12))
                mx = x - 25 if family == 'left_marker' else x + 66
                my = y - 6 if family == 'superscript' else y
                marks.append(dict(text=f'*{num}', x=mx, y=my, size=8 if family == 'superscript' else 12))
                notes.append(dict(text=f'*{num}:{note}', x=62, y=475, size=10))
            if family == 'damaged':
                marks[0] = None
                if index % 2 == 0:
                    notes.append(dict(text=f'*{abstract[1][1]}:EXCEPTION-CONFLICT', x=62, y=475, size=10))
            rng.shuffle(notes)
            for j, note in enumerate(notes):
                note['y'] += 21 * j
            if family == 'detached_stream':
                body = reqs + marks
            elif family == 'reverse_stream':
                body = list(reversed([t for pair in zip(reqs, marks) for t in pair]))
            else:
                body = [t for pair in zip(reqs, marks) for t in pair]
            tokens = [dict(text='SYNTHETIC-POLICY', x=62, y=50, size=14)]
            tokens += [t for t in body if t is not None] + notes
            documents.append(dict(id=f'{family}-{index:02}', family=family, split=split,
                                  gold=gold, tokens=tokens))
    return documents


def render(tokens):
    """Minimal deterministic single-page PDF using a standard base font and ASCII text."""
    commands = []
    for token in tokens:
        text = token['text'].replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
        commands.append(f"BT /F1 {token['size']} Tf 1 0 0 1 {token['x']} {792-token['y']} Tm ({text}) Tj ET\n")
    stream = ''.join(commands).encode('ascii')
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>',
               b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
               b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
               b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
               f'<< /Length {len(stream)} >>\nstream\n'.encode() + stream + b'endstream']
    pdf = bytearray(b'%PDF-1.4\n')
    offsets = [0]
    for i, obj in enumerate(objects, 1):
        offsets.append(len(pdf))
        pdf.extend(f'{i} 0 obj\n'.encode() + obj + b'\nendobj\n')
    xref = len(pdf)
    pdf.extend(f'xref\n0 {len(offsets)}\n0000000000 65535 f \n'.encode())
    for offset in offsets[1:]:
        pdf.extend(f'{offset:010} 00000 n \n'.encode())
    pdf.extend(f'trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode())
    return bytes(pdf)


def parse_bbox(xml):
    root = ET.fromstring(xml)
    pages = root.findall('.//{*}page')
    if len(pages) != 1:
        raise ValueError('expected exactly one page')
    return [dict(text=word.text or '', x0=float(word.attrib['xMin']), y0=float(word.attrib['yMin']),
                 x1=float(word.attrib['xMax']), y1=float(word.attrib['yMax']))
            for word in pages[0].findall('.//{*}word')]


def unique_notes(words):
    notes = {}
    for word in words:
        match = NOTE.fullmatch(word['text'])
        if match:
            notes.setdefault(match[1], []).append(match[2])
    return {num: values[0] for num, values in notes.items() if len(values) == 1}


def flat(words):
    notes, current, out = unique_notes(words), None, set()
    for word in words:
        req, mark = REQ.fullmatch(word['text']), MARK.fullmatch(word['text'])
        if req:
            current = req[1]
        elif mark and current and mark[1] in notes:
            out.add((current, notes[mark[1]]))
    return out


def spatial(words):
    notes, reqs, out = unique_notes(words), [], set()
    for word in words:
        req = REQ.fullmatch(word['text'])
        if req:
            reqs.append((req[1], word))
    for word in words:
        mark = MARK.fullmatch(word['text'])
        if not mark or mark[1] not in notes:
            continue
        candidates = []
        for req, box in reqs:
            dx = word['x0'] - box['x1']
            dy = ((word['y0'] + word['y1']) - (box['y0'] + box['y1'])) / 2
            if 0 <= dx <= 60 and abs(dy) <= 8:
                candidates.append((dx * dx + dy * dy, req))
        candidates.sort()
        if candidates and (len(candidates) == 1 or candidates[0][0] < candidates[1][0]):
            out.add((candidates[0][1], notes[mark[1]]))
    return out


def score(predicted, gold):
    return dict(tp=len(predicted & gold), fp=len(predicted - gold), fn=len(gold - predicted))


def summarize(cases):
    counts = {key: sum(case['counts'][key] for case in cases) for key in ('tp', 'fp', 'fn')}
    tp, fp, fn = counts['tp'], counts['fp'], counts['fn']
    denom = 2 * tp + fp + fn
    return dict(counts, f1=2 * tp / denom if denom else None,
                exact_documents=sum(c['counts']['fp'] == c['counts']['fn'] == 0 for c in cases),
                documents=len(cases))


def run(seed, executable='pdftotext'):
    version = subprocess.run([executable, '-v'], capture_output=True, check=True, timeout=10)
    runtime = (version.stderr or version.stdout).decode().splitlines()[0]
    docs, pdf_hashes, extraction_hashes = generate(seed), {}, {}
    cases = {method.__name__: [] for method in (flat, spatial)}
    with tempfile.TemporaryDirectory() as directory:
        for doc in docs:
            pdf = render(doc['tokens'])
            pdf_hashes[doc['id']] = hashlib.sha256(pdf).hexdigest()
            if doc['split'] != 'test':
                continue
            path = Path(directory) / 'page.pdf'
            path.write_bytes(pdf)
            proc = subprocess.run([executable, '-bbox', '-enc', 'UTF-8', str(path), '-'],
                                  capture_output=True, check=True, timeout=10)
            words = parse_bbox(proc.stdout)
            extraction_hashes[doc['id']] = digest(words)
            gold = set(map(tuple, doc['gold']))
            for method in (flat, spatial):
                pred = method(words)
                cases[method.__name__].append(dict(id=doc['id'], family=doc['family'],
                    gold=doc['gold'], predicted=sorted(map(list, pred)), counts=score(pred, gold)))
    arms = {name: dict(summarize(rows), predictions_sha256=digest(rows), cases=rows,
                       by_family={family: summarize([c for c in rows if c['family'] == family])
                                  for family in sorted({c['family'] for c in rows})})
            for name, rows in cases.items()}
    return dict(schema_version='0.1.0', status='exploratory_simulation', claim_boundary='synthetic_only',
                seed=seed, poppler=runtime, dataset_sha256=digest(docs), pdf_manifest_sha256=digest(pdf_hashes),
                extraction_manifest_sha256=digest(extraction_hashes),
                pdf_hashes=pdf_hashes, extraction_hashes=extraction_hashes,
                splits={split: sum(d['split'] == split for d in docs) for split in ('development', 'calibration', 'test')},
                arms=arms)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=17)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(run(args.seed), indent=2, sort_keys=True) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
