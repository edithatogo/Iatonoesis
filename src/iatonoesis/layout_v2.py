"""Exploratory frozen synthetic PDF and image-only OCR comparison using the paired runner."""
import argparse
import csv
import hashlib
import io
import json
import math
import os
import subprocess
import tempfile
import time
import zlib
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .layout_v2_fixture import generate, SEED
from .policy_pdf_pilot import REQ, MARK, NOTE, render, parse_bbox, flat, spatial, unique_notes
from .run_contracts import canonical_sha256
from .runner import run_experiment, paired_f1_interval, summarize

FIXTURE_SHA = 'c5b6a7249268b1525f813be9f36ec5058eb270dd0c917f1a320963677565beb5'
REFERENCE_SHA = '733bc491db63b482622582d0a38a0dd2f7da76ecfde722d11d7c5ce9a97a21d6'
FREEZE_REVISION = 'cb69c6b443eb8f02fa6a3dafc52a33eddb242a3b'


def validate_frozen_fixture(pages):
    if canonical_sha256(pages) != FIXTURE_SHA:
        raise ValueError('frozen fixture changed')
    if canonical_sha256({p['id']: p['gold'] for p in pages}) != REFERENCE_SHA:
        raise ValueError('frozen reference changed')


def bidirectional(words):
    notes, reqs, proposed = unique_notes(words), [], []
    req_counts = Counter()
    marker_counts = Counter()
    for word in words:
        req, marker = REQ.fullmatch(word['text']), MARK.fullmatch(word['text'])
        if req:
            reqs.append((req[1], word))
            req_counts[req[1]] += 1
        if marker:
            marker_counts[marker[1]] += 1
    for word in words:
        marker = MARK.fullmatch(word['text'])
        if not marker or marker[1] not in notes or marker_counts[marker[1]] != 1:
            continue
        candidates = []
        for req, box in reqs:
            if req_counts[req] != 1:
                continue
            if word['x0'] >= box['x1']:
                dx = word['x0'] - box['x1']
            elif box['x0'] >= word['x1']:
                dx = box['x0'] - word['x1']
            else:
                continue
            dy = abs((word['y0'] + word['y1'] - box['y0'] - box['y1']) / 2)
            if dx <= 60 and dy <= 12:
                candidates.append((math.hypot(dx, dy), req))
        candidates.sort()
        if candidates and (len(candidates) == 1 or candidates[1][0] - candidates[0][0] > 4):
            proposed.append((candidates[0][1], notes[marker[1]]))
    counts = Counter(req for req, _ in proposed)
    return {(req, note) for req, note in proposed if counts[req] == 1}


def tsv_words(tsv, scale_x, scale_y):
    words = []
    for row in csv.DictReader(io.StringIO(tsv), delimiter='\t'):
        if row['level'] != '5' or not row['text'].strip():
            continue
        x, y, w, h = (int(row[k]) for k in ('left', 'top', 'width', 'height'))
        words.append(dict(text=row['text'], x0=x/scale_x, x1=(x+w)/scale_x,
                          y0=y/scale_y, y1=(y+h)/scale_y))
    return words


def image_pdf(width, height, gray):
    """Deterministic image-only PDF: a single losslessly compressed grayscale raster."""
    if width <= 0 or height <= 0 or len(gray) != width * height:
        raise ValueError('invalid grayscale raster')
    raster = zlib.compress(gray, 9)
    stream = b'q 612 0 0 792 0 0 cm /Im0 Do Q\n'
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>',
               b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
               b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /XObject << /Im0 4 0 R >> >> /Contents 5 0 R >>',
               f'<< /Type /XObject /Subtype /Image /Width {width} /Height {height} /ColorSpace /DeviceGray /BitsPerComponent 8 /Filter /FlateDecode /Length {len(raster)} >>\nstream\n'.encode() + raster + b'\nendstream',
               f'<< /Length {len(stream)} >>\nstream\n'.encode() + stream + b'endstream']
    pdf, offsets = bytearray(b'%PDF-1.4\n'), [0]
    for i, obj in enumerate(objects, 1):
        offsets.append(len(pdf))
        pdf.extend(f'{i} 0 obj\n'.encode() + obj + b'\nendobj\n')
    xref = len(pdf)
    pdf.extend(f'xref\n0 {len(offsets)}\n0000000000 65535 f \n'.encode())
    for offset in offsets[1:]:
        pdf.extend(f'{offset:010} 00000 n \n'.encode())
    pdf.extend(f'trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode())
    return bytes(pdf)


def command(args):
    return subprocess.run(args, capture_output=True, check=True, timeout=30,
                          env={**os.environ, 'OMP_THREAD_LIMIT': '1'}).stdout


def extract(page):
    from PIL import Image
    start = time.perf_counter()
    pdf = render(page['tokens'])
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        original, raster_pdf = root/'text.pdf', root/'image.pdf'
        original.write_bytes(pdf)
        words = parse_bbox(command(['pdftotext', '-bbox', '-enc', 'UTF-8', str(original), '-']))
        text_seconds = time.perf_counter() - start
        start = time.perf_counter()
        command(['pdftoppm', '-gray', '-r', '200', '-singlefile', '-png', str(original), str(root/'render')])
        with Image.open(root/'render.png') as image:
            gray = image.convert('L')
            raster_pdf.write_bytes(image_pdf(gray.width, gray.height, gray.tobytes()))
        if command(['pdftotext', '-enc', 'UTF-8', str(raster_pdf), '-']).strip():
            raise ValueError('image-only PDF unexpectedly contains extractable text')
        command(['pdftoppm', '-gray', '-r', '200', '-singlefile', '-png', str(raster_pdf), str(root/'ocr')])
        with Image.open(root/'ocr.png') as image:
            sx, sy = image.width/612, image.height/792
        tsv = command(['tesseract', str(root/'ocr.png'), 'stdout', '-l', 'eng', '--psm', '6', 'tsv']).decode('utf-8')
        ocr = tsv_words(tsv, sx, sy)
        return dict(id=page['id'], text=words, ocr=ocr,
                    text_pdf_sha256=hashlib.sha256(pdf).hexdigest(),
                    image_pdf_sha256=hashlib.sha256(raster_pdf.read_bytes()).hexdigest(),
                    text_seconds=text_seconds, ocr_seconds=time.perf_counter()-start)


def evidence_counts(page, words):
    """Count availability of exact reference components; no guessing from missing text."""
    reqs = Counter(m[1] for w in words if (m := REQ.fullmatch(w['text'])))
    marks = Counter(m[1] for w in words if (m := MARK.fullmatch(w['text'])))
    notes = unique_notes(words)
    intended = {m[2]: m[1] for t in page['tokens'] if (m := NOTE.fullmatch(t['text'])) and m[2] != 'EXCEPTION-CONFLICT'}
    counts = Counter(total=len(page['gold']))
    for req, note in page['gold']:
        marker = intended[note]
        r, m, n = reqs[req] == 1, marks[marker] == 1, notes.get(marker) == note
        counts['requirement_missing_or_duplicate'] += not r
        counts['marker_missing_or_duplicate'] += not m
        counts['note_missing_or_conflicting'] += not n
        counts['all_components_available'] += r and m and n
    return dict(counts)


def _prediction(method):
    return lambda words: sorted(map(list, method(words)))


def run(source_commit, *, workers=4):
    pages = generate()
    validate_frozen_fixture(pages)
    references = {p['id']: p['gold'] for p in pages}
    rows = [dict(id=p['id'], split=p['split'], groups={'family': p['family']}) for p in pages]
    test_ids = [p['id'] for p in pages if p['split'] == 'test']
    with ThreadPoolExecutor(max_workers=workers) as pool:
        extracted = list(pool.map(extract, pages))
    outputs = {}
    for modality in ('text', 'ocr'):
        inputs = {e['id']: e[modality] for e in extracted}
        data = dict(schema_version='0.1.0', dataset_id=f'E02-layout-v2-{modality}', kind='synthetic',
                    source='repository-authored fictional administrative tokens', revision=FREEZE_REVISION,
                    sha256=canonical_sha256(inputs), rights=dict(status='approved', licence='MIT',
                    evidence='repository-authored synthetic fixtures; no external or patient records'),
                    reference=dict(kind='deterministic_oracle', revision=FREEZE_REVISION, sha256=REFERENCE_SHA),
                    grouping_keys=['family'], rows=rows)
        exp = dict(schema_version='0.1.0', experiment_id=f'E02-layout-v2-{modality}', track_task='T01.007',
                   dataset_id=data['dataset_id'], dataset_sha256=data['sha256'], reference_sha256=REFERENCE_SHA,
                   split='test', case_ids=test_ids, primary_metric='f1', unit='page', seed=SEED,
                   arms=[dict(id=x, role='deterministic') for x in ('flat','right_only','bidirectional')]+[
                         dict(id='learned', role='specialist')], budget=dict(max_cases=40, max_seconds=60),
                   claim_boundary='synthetic_only')
        result = run_experiment(exp, data, inputs, references, predictors={
            'flat': _prediction(flat), 'right_only': _prediction(spatial),
            'bidirectional': _prediction(bidirectional)}, source_commit=source_commit)
        if set(result['predictions']) != {'flat','right_only','bidirectional'}:
            raise RuntimeError('conventional baseline failed; inspect before publishing results')
        result['paired_f1'] = {arm: paired_f1_interval(result['predictions'][arm], result['predictions']['bidirectional'],
                                  grouping_key='family', seed=SEED, draws=500) for arm in ('flat','right_only')}
        result['by_family'] = {arm: {family: summarize([row for row in raw if row['groups']['family']==family])
                                 for family in sorted({r['groups']['family'] for r in raw})}
                               for arm, raw in result['predictions'].items()}
        result['evidence_counts'] = {p['id']: evidence_counts(p, inputs[p['id']]) for p in pages if p['split']=='test'}
        result['dataset'] = data
        result['experiment'] = exp
        outputs[modality] = result
    return dict(schema_version='0.1.0', status='exploratory_simulation', claim_boundary='synthetic_only',
                canonical_acceptance=False, freeze_revision=FREEZE_REVISION, fixture_sha256=FIXTURE_SHA,
                reference_sha256=REFERENCE_SHA, seed=SEED, workers=workers,
                extractions=[{k: v for k,v in e.items() if k not in {'text','ocr'}} | {
                    'text_words_sha256':canonical_sha256(e['text']), 'ocr_words_sha256':canonical_sha256(e['ocr'])} for e in extracted],
                modalities=outputs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-commit', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(run(args.source_commit), indent=2, sort_keys=True)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()
