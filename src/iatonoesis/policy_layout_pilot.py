"""Exploratory synthetic policy qualifier binding; not a clinical or OCR benchmark."""

import argparse
import json
import random
import re
from pathlib import Path

from .run_contracts import canonical_sha256

REQ = re.compile(r'REQ-([A-Z]): .+')
MARK = re.compile(r'\*([0-9]+)')
FOOT = re.compile(r'\*([0-9]+): (.+)')
FAMILIES = (
    ('development', 'row-major', 0),
    ('development', 'column-major', 1),
    ('calibration', 'row-major', 2),
    ('calibration', 'marker-block', 3),
    ('test', 'column-major', 4),
    ('test', 'marker-block', 5),
    ('test', 'reverse-columns', 6),
    ('test', 'marker-block', 7),
)


def generate(seed):
    """Create abstract obligations before rendering token positions and reading order."""
    rng = random.Random(seed)
    docs = []
    for split, order, family in FAMILIES:
        for index in range(12):
            # These are fictitious administrative obligations, not clinical recommendations.
            ids = list('ABCD')
            rng.shuffle(ids)
            gold = [(req, f'exception {family}-{index}-{n}') for n, req in enumerate(ids, 1)]
            reqs, markers, footnotes = [], [], []
            for n, (req, qualifier) in enumerate(gold, 1):
                col, row = (n - 1) % 2, (n - 1) // 2
                x, y = 10 + col * (80 + family * 7), 20 + row * (12 + family * 2)
                reqs.append({'text': f'REQ-{req}: routine', 'x': x, 'y': y})
                marker = {'text': f'*{n}', 'x': x + 25, 'y': y + rng.choice([-1, 0, 1])}
                # Deliberately retain intended gold for missing visible markers.
                if family == 7 and n == 4 and index % 3 == 0:
                    marker = None
                markers.append(marker)
                footnotes.append({'text': f'*{n}: {qualifier}', 'x': 10, 'y': 90 + n * 7})
            indices = [0, 1, 2, 3]
            if order == 'column-major':
                indices = [0, 2, 1, 3]
            if order == 'reverse-columns':
                indices = [1, 3, 0, 2]
            if order == 'marker-block':
                body = [reqs[i] for i in indices] + [markers[i] for i in indices]
            else:
                body = [token for i in indices for token in (reqs[i], markers[i])]
            page = [token for token in body if token is not None] + footnotes
            docs.append({'id': f'f{family}-d{index:02d}', 'family': f'f{family}',
                         'split': split, 'page': page, 'gold': sorted(map(list, gold))})
    return docs


def _footnotes(page):
    result = {}
    for token in page:
        match = FOOT.fullmatch(token['text'])
        if match:
            result.setdefault(match[1], []).append(match[2])
    return {key: values[0] for key, values in result.items() if len(values) == 1}


def flat(page):
    """Link visible markers to the preceding requirement in supplied text order."""
    notes, current, out = _footnotes(page), None, set()
    for token in page:
        req, mark = REQ.fullmatch(token['text']), MARK.fullmatch(token['text'])
        if req:
            current = req[1]
        elif mark and current and mark[1] in notes:
            out.add((current, notes[mark[1]]))
    return out


def spatial(page):
    """Link visible markers to nearest uniquely eligible left-hand requirement."""
    notes, out, reqs = _footnotes(page), set(), []
    for token in page:
        req = REQ.fullmatch(token['text'])
        if req:
            reqs.append((req[1], token['x'], token['y']))
    for token in page:
        mark = MARK.fullmatch(token['text'])
        if not mark or mark[1] not in notes:
            continue
        candidates = []
        for req, x, y in reqs:
            dx, dy = token['x'] - x, token['y'] - y
            if 0 < dx <= 40 and abs(dy) <= 5:
                candidates.append((dx * dx + dy * dy, req))
        candidates.sort()
        if candidates and (len(candidates) == 1 or candidates[0][0] < candidates[1][0]):
            out.add((candidates[0][1], notes[mark[1]]))
    return out


def score(predicted, gold):
    return {'tp': len(predicted & gold), 'fp': len(predicted - gold), 'fn': len(gold - predicted)}


def _summarize(cases):
    counts = {key: sum(case['counts'][key] for case in cases) for key in ('tp', 'fp', 'fn')}
    tp, fp, fn = counts['tp'], counts['fp'], counts['fn']
    denominator = 2 * tp + fp + fn
    return dict(counts, f1=2 * tp / denominator if denominator else None,
                exact_documents=sum(case['counts']['fp'] == case['counts']['fn'] == 0 for case in cases),
                documents=len(cases))


def run(seed):
    docs = generate(seed)
    test = [doc for doc in docs if doc['split'] == 'test']
    arms = {}
    for method in (flat, spatial):
        cases = []
        for doc in test:
            gold = set(map(tuple, doc['gold']))
            predicted = method(doc['page'])
            cases.append({'id': doc['id'], 'family': doc['family'], 'predicted': sorted(map(list, predicted)),
                          'gold': doc['gold'], 'counts': score(predicted, gold)})
        arms[method.__name__] = dict(_summarize(cases), predictions_sha256=canonical_sha256(cases),
                                      by_family={f: _summarize([c for c in cases if c['family'] == f])
                                                 for f in sorted({c['family'] for c in cases})}, cases=cases)
    return {'status': 'exploratory_simulation', 'claim_boundary': 'synthetic_only', 'seed': seed,
            'dataset_sha256': canonical_sha256(docs), 'test_documents': len(test), 'arms': arms}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=17)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(run(args.seed), indent=2, sort_keys=True) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
