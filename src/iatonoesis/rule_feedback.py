"""Model-informed, deterministic verification experiment; synthetic assumptions only."""
import argparse
import copy
import json
import re
from pathlib import Path

from .run_contracts import canonical_sha256 as digest
from .runner import summarize
from .workflow_pilots import verify_steps

ATTESTED = re.compile(r'Performance attested at minute ([0-9]+)\.')
COMPLETION = re.compile(r'(?:Performance attested|Completion recorded) at minute ([0-9]+)\.')
UNKNOWN = 'unverifiable'


def alias_only(episode):
    """Extend legacy recognition alone, without additional safeguards."""
    note = ATTESTED.fullmatch(episode['note'])
    return verify_steps(episode | {'note': f'Completion recorded at minute {note[1]}.'}) if note else verify_steps(episode)


def decision(episode):
    """Require trusted explicit evidence, valid time and consistent sources."""
    deadline, horizon = episode.get('deadline'), episode.get('observed_until')
    flags = ('note_verified', 'exception', 'exception_verified', 'complete_log')
    if type(deadline) is not int or deadline < 0 or type(horizon) is not int or horizon < 0 or any(type(episode.get(k)) is not bool for k in flags):
        return UNKNOWN, 'invalid_metadata'
    note, events = episode.get('note'), episode.get('events')
    if not isinstance(note, str) or not isinstance(events, list):
        return UNKNOWN, 'invalid_metadata'
    times = []
    for event in events:
        if not isinstance(event, dict) or event.get('kind') not in {'ordered', 'performed'}:
            return UNKNOWN, 'invalid_event'
        minute = event.get('minute')
        if type(minute) is not int or not 0 <= minute <= horizon:
            return UNKNOWN, 'invalid_event_time'
        if event['kind'] == 'performed':
            times.append(minute)
    if note:
        match = COMPLETION.fullmatch(note)
        if not episode['note_verified'] or not match:
            return UNKNOWN, 'unsupported_note'
        minute = int(match[1])
        if minute > horizon:
            return UNKNOWN, 'invalid_note_time'
        times.append(minute)
    if episode['exception']:
        if not episode['exception_verified'] or times:
            return UNKNOWN, 'unverified_or_conflicting_exception'
        return 'inapplicable', 'verified_exception'
    if times:
        if len(set(times)) > 1:
            return UNKNOWN, 'conflicting_timestamps'
        return ('completed' if times[0] <= deadline else 'late'), 'verified_completion_time'
    if episode['complete_log'] and horizon >= deadline:
        return 'missing', 'complete_log_deadline_elapsed'
    return UNKNOWN, 'insufficient_observation'


def refined(episode):
    return [decision(episode)[0]]


def run(fixture):
    cases = fixture['cases']
    ids = [r['id'] for r in cases]
    if len(set(ids)) != len(ids):
        raise ValueError('duplicate case ID')
    outputs = {}
    for name, predictor in [('legacy', verify_steps), ('alias_only', alias_only), ('refined', refined)]:
        rows = []
        for case in cases:
            inp = copy.deepcopy(fixture['defaults'] | case['overrides'])
            prediction = predictor(inp)
            rows.append(dict(id=case['id'], gold=[case['gold']], prediction=prediction))
        metrics = summarize(rows)
        metrics.update(false_timely=sum(r['prediction'] == ['completed'] and r['gold'] != ['completed'] for r in rows),
                       missed_required_review=sum(r['gold'] == [UNKNOWN] and r['prediction'] != [UNKNOWN] for r in rows),
                       unnecessary_review=sum(r['gold'] != [UNKNOWN] and r['prediction'] == [UNKNOWN] for r in rows),
                       review=sum(r['prediction'] == [UNKNOWN] for r in rows), predictions_sha256=digest(rows), cases=rows)
        outputs[name] = metrics
    return dict(scope='co-authored synthetic stress cases, no AI inference, no independent clinical gold',
                fixture_sha256=digest(fixture), total=len(cases), arms=outputs,
                gold_review=sum(r['gold'] == UNKNOWN for r in cases),
                reasons={r['id']:decision(fixture['defaults'] | r['overrides'])[1] for r in cases})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixtures', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(run(json.loads(args.fixtures.read_text())), indent=2, sort_keys=True)+'\n')


if __name__ == '__main__':
    main()
