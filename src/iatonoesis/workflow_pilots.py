"""Exploratory synthetic E04 and E22 rule comparisons; never clinical use."""

import argparse
import json
import random
import re
from pathlib import Path

from .run_contracts import canonical_sha256

PARTITIONS = ('development', 'development', 'development', 'calibration',
              'calibration', 'test', 'test', 'test', 'test', 'test')
TUPLE = re.compile(r'Task: ([^;]+); Owner: ([^;]+); Due: ([^;]+); Condition: ([^.]+)\.')
COMPLETION = re.compile(r'Completion recorded at minute ([0-9]+)\.')
STATES = ('completed', 'late', 'missing', 'inapplicable', 'unverifiable')


def _key(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def paired_run(cases, predictors):
    """Score the same frozen test cases; predictors see only input, not the oracle."""
    if not cases or any(case['split'] != 'test' for case in cases):
        raise ValueError('nonempty test cases required')
    if len({case['id'] for case in cases}) != len(cases):
        raise ValueError('duplicate case ID')
    arms = {}
    for name, predictor in predictors.items():
        rows = []
        for case in cases:
            prediction = predictor(case['input'])
            gold = {_key(x) for x in case['gold']}
            pred = set() if prediction is None else {_key(x) for x in prediction}
            rows.append({'id': case['id'], 'family': case['family'], 'gold': case['gold'],
                         'prediction': prediction, 'tp': len(pred & gold),
                         'fp': len(pred - gold), 'fn': len(gold - pred),
                         'exact': prediction is not None and pred == gold})
        totals = {key: sum(row[key] for row in rows) for key in ('tp', 'fp', 'fn')}
        abstained = sum(row['prediction'] is None for row in rows)
        scored = len(rows) - abstained
        errors = sum(row['prediction'] is not None and not row['exact'] for row in rows)
        tp, fp, fn = (totals[key] for key in ('tp', 'fp', 'fn'))
        metrics = dict(totals, total=len(rows), scored=scored, abstained=abstained,
                       errors=errors, exact=sum(row['exact'] for row in rows),
                       coverage=_ratio(scored, len(rows)),
                       selective_accuracy=_ratio(scored - errors, scored),
                       f1=_ratio(2 * tp, 2 * tp + fp + fn))
        arms[name] = {'metrics': metrics, 'predictions_sha256': canonical_sha256(rows), 'cases': rows}
    return arms


def make_discharge(seed):
    """Render fictitious task tuples with pending and nonpending contextual cues."""
    rng = random.Random(seed)
    rows = []
    cues = ('Still pending.', 'Already completed.', 'Cancelled.', 'Hypothetical only.', 'Unclear status.')
    for family, split in enumerate(PARTITIONS):
        for i in range(20):
            state = (i + family) % len(cues)
            values = [f'review form {rng.choice("ABCD")}', f'team {rng.choice("XYZ")}',
                      f'day {rng.randint(1, 9)}', rng.choice(['if available', 'if requested', 'unconditional'])]
            gold = [values] if state == 0 else []
            cue = cues[state]
            if family == 9 and state == 0:
                cue = 'Action remains outstanding.'  # deliberately unseen phrasing
            if family == 8 and state == 1:
                cue = 'No longer pending; previously completed.'
            note = 'Task: {}; Owner: {}; Due: {}; Condition: {}. '.format(*values) + cue
            rows.append({'id': f'd{family}-{i:02d}', 'family': f'd{family}', 'split': split,
                         'input': note, 'gold': gold, 'reference_status': state})
    return rows


def extract_naive(note):
    match = TUPLE.search(note)
    return [list(match.groups())] if match else None


def extract_context(note):
    match = TUPLE.search(note)
    if not match:
        return None
    cue = note[match.end():].strip()
    if cue == 'Still pending.':
        return [list(match.groups())]
    if cue in {'Already completed.', 'Cancelled.', 'Hypothetical only.'}:
        return []
    return None


def make_steps(seed):
    """Simulated verification episodes with abstract deadlines, not stroke guidance."""
    rng = random.Random(seed)
    rows = []
    for family, split in enumerate(PARTITIONS):
        for i in range(15):
            state = STATES[(i + family) % len(STATES)]
            deadline = rng.randint(15, 25)
            events = [{'kind': 'ordered', 'minute': 1}]
            note = ''
            if state in ('completed', 'late'):
                minute = deadline - 2 if state == 'completed' else deadline + 2
                if family == 9:
                    note = f'Performance attested at minute {minute}.'
                elif family % 3 == 1:
                    note = f'Completion recorded at minute {minute}.'
                else:
                    events.append({'kind': 'performed', 'minute': minute})
            episode = {'deadline': deadline, 'events': events, 'note': note,
                       'complete_log': state != 'unverifiable' and family != 9,
                       'exception': state == 'inapplicable'}
            if family == 9 and state == 'missing':
                episode['complete_log'] = True
            rows.append({'id': f's{family}-{i:02d}', 'family': f's{family}', 'split': split,
                         'input': episode, 'gold': [state]})
    return rows


def verify_naive(episode):
    return ['completed' if any(e['kind'] in {'ordered', 'performed'} for e in episode['events']) else 'missing']


def verify_steps(episode):
    if episode['exception']:
        return ['inapplicable']
    times = [e['minute'] for e in episode['events'] if e['kind'] == 'performed']
    match = COMPLETION.fullmatch(episode['note'])
    if match:
        times.append(int(match[1]))
    if times:
        return ['completed' if min(times) <= episode['deadline'] else 'late']
    return ['missing' if episode['complete_log'] and not episode['note'] else 'unverifiable']


def _step_metrics(arm):
    rows = arm['cases']
    non_timely = [r for r in rows if r['gold'] != ['completed']]
    missing = [r for r in rows if r['gold'] == ['missing']]
    false_timely = sum(r['prediction'] == ['completed'] for r in non_timely)
    found_missing = sum(r['prediction'] == ['missing'] for r in missing)
    arm['false_timely_completion'] = {'count': false_timely, 'denominator': len(non_timely),
                                      'rate': _ratio(false_timely, len(non_timely))}
    arm['missed_step_recall'] = {'count': found_missing, 'denominator': len(missing),
                                 'rate': _ratio(found_missing, len(missing))}
    arm['confusion'] = {s: {p: sum(r['gold'] == [s] and r['prediction'] == [p] for r in rows)
                            for p in STATES} for s in STATES}


def run(seed):
    discharge, steps = make_discharge(seed), make_steps(seed)
    dtest, stest = ([c for c in rows if c['split'] == 'test'] for rows in (discharge, steps))
    e04 = paired_run(dtest, {'naive': extract_naive, 'context': extract_context})
    e22 = paired_run(stest, {'naive': verify_naive, 'explicit': verify_steps})
    for arm in e22.values():
        _step_metrics(arm)
    return {'status': 'exploratory_simulation', 'claim_boundary': 'synthetic_only', 'seed': seed,
            'E04': {'dataset_sha256': canonical_sha256(discharge), 'generated': len(discharge), 'test': len(dtest), 'arms': e04},
            'E22': {'dataset_sha256': canonical_sha256(steps), 'generated': len(steps), 'test': len(stest), 'arms': e22}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=17)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(run(args.seed), indent=2, sort_keys=True) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
