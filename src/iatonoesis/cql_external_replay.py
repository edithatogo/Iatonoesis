"""Restricted CQL scalar-expression replay against external published fixtures.

Not a general CQL parser, clinical engine, or certification. No learned model.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

UPSTREAM = 'e87e3fa8a3802c69a760b2583d2306d7c66d9899'
SUITES = {
    'CqlLogicalOperatorsTest.json': '48fd944a1c006e96655796499edc60c5f822573ad659ee1a255ec4b4aa7e1310',
    'CqlConditionalOperatorsTest.json': '280d3ddef3e79afd17f10fadcd52ea09b319c05548b153b5862c7ec91e64405c',
}
ATOM = r'(?:true|false|null|[0-9]+)'
VALUES = {'true': True, 'false': False, 'null': None}


def _atom(token):
    if token in VALUES:
        return VALUES[token]
    if re.fullmatch(r'[0-9]+', token):
        return int(token)
    raise ValueError('unsupported scalar')


def _boolean(value):
    if value is not None and type(value) is not bool:
        raise ValueError('Boolean operand required')
    return value


def _not(value):
    return None if value is None else not _boolean(value)


def _binary(a, op, b):
    if op in {'and', 'or', 'xor', 'implies'}:
        _boolean(a)
        _boolean(b)
        if op == 'and':
            return False if False in (a, b) else None if None in (a, b) else True
        if op == 'or':
            return True if True in (a, b) else None if None in (a, b) else False
        if op == 'xor':
            return None if None in (a, b) else a != b
        return _binary(_not(a), 'or', b)
    if op == '~':
        return type(a) is type(b) and a == b
    if a is None or b is None:
        return None
    if op == '=':
        return type(a) is type(b) and a == b
    if type(a) is not int or type(b) is not int:
        raise ValueError('integer operands required')
    if op == '>':
        return a > b
    if op == '+':
        return a + b
    if op == '-':
        return a - b
    raise ValueError('unsupported operator')


def evaluate(expression):
    """Evaluate only the explicitly supported flat scalar grammar."""
    expr = ' '.join(expression.split())
    match = re.fullmatch(r'if (.+?) then (.+?) else (.+)', expr)
    if match:
        condition, yes, no = match.groups()
        return evaluate(yes if _boolean(evaluate(condition)) is True else no)
    match = re.fullmatch(r'case (.*?)when (.+) else (.+) end', expr)
    if match:
        selector, branches, fallback = match.groups()
        selected = evaluate(selector.strip()) if selector.strip() else None
        for branch in re.split(r' when ', branches):
            parts = branch.split(' then ')
            if len(parts) != 2:
                raise ValueError('unsupported case branch')
            condition, value = parts
            passed = (_binary(selected, '=', evaluate(condition)) if selector.strip()
                      else _boolean(evaluate(condition)))
            if passed is True:
                return evaluate(value)
        return evaluate(fallback)
    match = re.fullmatch(rf'not ({ATOM})', expr)
    if match:
        return _not(_atom(match[1]))
    match = re.fullmatch(rf'({ATOM}) (and|or|xor|implies|=|~|>|\+|-) ({ATOM})', expr)
    if match:
        return _binary(_atom(match[1]), match[2], _atom(match[3]))
    return _atom(expr)


def load_suite(path, entry):
    if entry.get('partition') != 'external_test_only' or entry.get('training_eligible') is not False:
        raise ValueError('external test-only fixture required')
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != entry['dataset_sha256']:
        raise ValueError('dataset hash mismatch')
    rows = json.loads(raw)
    ids = [row['id'] for row in rows]
    if ids != entry['case_ids'] or len(ids) != entry['case_count'] or len(set(ids)) != len(ids):
        raise ValueError('case IDs mismatch')
    if any(set(row) != {'id', 'expression', 'expected'} or not isinstance(row['expression'], str)
           or type(row['expected']) not in (bool, int, type(None)) for row in rows):
        raise ValueError('unsupported fixture schema')
    return rows


def replay(rows):
    cases = []
    for row in rows:
        try:
            value = evaluate(row['expression'])
            status = 'correct' if type(value) is type(row['expected']) and value == row['expected'] else 'incorrect'
            cases.append(dict(id=row['id'], expected=row['expected'], prediction=value, status=status))
        except ValueError:
            cases.append(dict(id=row['id'], expected=row['expected'], status='unavailable'))
    return dict(total=len(cases), cases=cases, **{state: sum(row['status'] == state for row in cases)
                                                for state in ('correct', 'incorrect', 'unavailable')})


def run(directory):
    directory = Path(directory)
    manifest = json.loads((directory / 'manifest.json').read_bytes())
    if manifest['upstream_revision'] != UPSTREAM or manifest['licence'] != 'Apache-2.0':
        raise ValueError('unexpected source or rights')
    if {entry['dataset_file']: entry['dataset_sha256'] for entry in manifest['suites']} != SUITES:
        raise ValueError('frozen suite identities mismatch')
    result = {entry['suite']: replay(load_suite(directory / entry['dataset_file'], entry)) for entry in manifest['suites']}
    return dict(status='exploratory_external_test_only', claim_boundary='scalar_fixture_replay_only',
                upstream_revision=UPSTREAM, dataset_sha256=SUITES, suites=result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixtures', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(run(args.fixtures), sort_keys=True, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
