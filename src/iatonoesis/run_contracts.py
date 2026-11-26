"""Version 0.1.0 structural run contracts; no data download or clinical authorization."""

import hashlib
import json
import math
import re

VERSION = '0.1.0'
PARTITIONS = {'development', 'calibration', 'test'}
ROLES = {'deterministic', 'classical', 'specialist', 'generalist', 'hybrid'}
STATES = {'executed', 'failed', 'skipped', 'unavailable'}


def _require(ok, message):
    if not ok:
        raise ValueError(message)


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _hash(value, label, length=64):
    _require(isinstance(value, str) and re.fullmatch(rf'[0-9a-f]{{{length}}}', value),
             f'invalid {label} hash')


def _count(value):
    return type(value) is int and value >= 0


def _number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _version(record):
    _require(record.get('schema_version') == VERSION, 'unknown contract schema version')


def canonical_sha256(record):
    """Hash canonical UTF-8 JSON, rejecting nonfinite numeric values."""
    return hashlib.sha256(json.dumps(record, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def _unique(values, label):
    _require(all(_text(v) for v in values) and len(values) == len(set(values)),
             f'invalid or duplicate {label}')


def validate_dataset(data):
    """Require provenance, rights assertion and non-overlapping declared group splits."""
    _version(data)
    _require(data.get('kind') in {'synthetic', 'public'}, 'unsupported dataset kind')
    for key in ('dataset_id', 'source', 'revision'):
        _require(_text(data.get(key)), f'missing dataset {key}')
    _hash(data.get('sha256'), 'dataset')
    rights = data.get('rights', {})
    _require(rights.get('status') == 'approved' and _text(rights.get('licence'))
             and _text(rights.get('evidence')), 'dataset rights not approved or recorded')
    ref = data.get('reference', {})
    _require(ref.get('kind') in {'deterministic_oracle', 'expert_adjudicated', 'published_labels'}
             and _text(ref.get('revision')), 'missing reference provenance')
    _hash(ref.get('sha256'), 'reference')
    keys = data.get('grouping_keys', [])
    _require(isinstance(keys, list) and bool(keys), 'missing grouping keys')
    _unique(keys, 'grouping key')
    rows = data.get('rows', [])
    _require(isinstance(rows, list) and bool(rows), 'missing split rows')
    _unique([row.get('id') for row in rows], 'row ID')
    seen = {}
    splits = set()
    for row in rows:
        split = row.get('split')
        _require(split in PARTITIONS, 'unknown split')
        splits.add(split)
        groups = row.get('groups', {})
        for key in keys:
            group = groups.get(key)
            _require(_text(group), f'missing group {key}')
            pair = (key, group)
            _require(pair not in seen or seen[pair] == split, f'group leakage: {key}')
            seen[pair] = split
    _require(splits == PARTITIONS, 'missing required split')


def validate_experiment(exp, data):
    """Bind a prespecified test and comparators to dataset and reference identity."""
    validate_dataset(data)
    _version(exp)
    for key in ('experiment_id', 'track_task', 'primary_metric', 'unit'):
        _require(_text(exp.get(key)), f'missing experiment {key}')
    _require(re.fullmatch(r'T[0-9]{2}\.[0-9]{3}', exp['track_task']), 'invalid task ID')
    _require(exp.get('dataset_id') == data['dataset_id'] and exp.get('dataset_sha256') == data['sha256'],
             'experiment dataset mismatch')
    _require(exp.get('reference_sha256') == data['reference']['sha256'], 'experiment reference mismatch')
    _require(exp.get('split') == 'test' and _count(exp.get('seed')), 'invalid split or seed')
    boundary = 'synthetic_only' if data['kind'] == 'synthetic' else 'benchmark_only'
    _require(exp.get('claim_boundary') == boundary, 'invalid claim boundary')
    arms = exp.get('arms', [])
    _unique([a.get('id') for a in arms], 'arm ID')
    _require(len(arms) >= 2 and all(a.get('role') in ROLES for a in arms)
             and any(a['role'] == 'deterministic' for a in arms), 'invalid comparison arms')
    budget = exp.get('budget', {})
    _require(_count(budget.get('max_cases')) and budget['max_cases'] > 0
             and _number(budget.get('max_seconds')) and budget['max_seconds'] > 0, 'invalid budget')
    ids = exp.get('case_ids', [])
    _require(isinstance(ids, list) and bool(ids), 'missing frozen case IDs')
    _unique(ids, 'case ID')
    test_ids = {row['id'] for row in data['rows'] if row['split'] == 'test'}
    _require(set(ids) <= test_ids and len(ids) <= budget['max_cases'], 'case IDs outside frozen test/budget')


def validate_result(result, exp, data):
    """Require every configured arm, consistent denominators and no invented metrics."""
    validate_experiment(exp, data)
    _version(result)
    _hash(result.get('source_commit'), 'commit', 40)
    _require(result.get('config_sha256') == canonical_sha256(exp), 'result config hash mismatch')
    for key in ('experiment_id', 'dataset_sha256', 'reference_sha256', 'seed', 'claim_boundary'):
        _require(result.get(key) == exp[key], f'result {key} mismatch')
    _require(_text(result.get('environment')), 'missing environment')
    arms = result.get('arms', [])
    ids = [a.get('id') for a in arms]
    _unique(ids, 'result arm')
    planned = {a['id']: a for a in exp['arms']}
    _require(set(ids) == set(planned), 'result arm coverage mismatch')
    for arm in arms:
        status = arm.get('status')
        _require(status in STATES, 'unknown arm status')
        if status != 'executed':
            _require(_text(arm.get('reason')) and arm.get('metrics') is None
                     and arm.get('predictions_sha256') is None, f'{status} arm must have reason, no results')
            continue
        _hash(arm.get('predictions_sha256'), 'predictions')
        _require(_number(arm.get('elapsed_seconds')) and arm['elapsed_seconds'] <= exp['budget']['max_seconds'],
                 'invalid elapsed time or budget exceeded')
        if planned[arm['id']]['role'] in {'specialist', 'generalist', 'hybrid', 'classical'}:
            model = arm.get('model', {})
            _require(all(_text(model.get(k)) for k in ('id', 'revision', 'licence')),
                     'missing learned arm model provenance')
        metrics = arm.get('metrics', {})
        counts = [metrics.get(k) for k in ('total', 'scored', 'abstained', 'errors')]
        _require(all(_count(c) for c in counts), 'invalid metric denominator')
        total, scored, abstained, errors = counts
        _require(total == len(exp['case_ids']) and total == scored + abstained and errors <= scored,
                 'inconsistent metric denominator')
