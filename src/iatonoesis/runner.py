"""Contract-bound, local paired set evaluation for trusted research adapters."""

import copy
import json
import math
import platform
import random
import time
from collections import defaultdict

from .run_contracts import canonical_sha256, validate_experiment, validate_result


def _set(values):
    if not isinstance(values, list):
        raise ValueError('reference or prediction must be a list')
    keys = {json.dumps(v, sort_keys=True, separators=(',', ':'), allow_nan=False) for v in values}
    if len(keys) != len(values):
        raise ValueError('duplicate set item')
    return keys


def _ratio(n, d):
    return n / d if d else None


def summarize(rows):
    """Abstentions count missed targets, but not as scored classification errors."""
    tp = fp = fn = abstained = errors = exact = 0
    for row in rows:
        gold = _set(row['gold'])
        prediction = row['prediction']
        pred = set() if prediction is None else _set(prediction)
        tp += len(gold & pred)
        fp += len(pred - gold)
        fn += len(gold - pred)
        if prediction is None:
            abstained += 1
        elif gold == pred:
            exact += 1
        else:
            errors += 1
    total = len(rows)
    scored = total - abstained
    return dict(total=total, scored=scored, abstained=abstained, errors=errors,
                exact=exact, tp=tp, fp=fp, fn=fn, coverage=_ratio(scored, total),
                accuracy=_ratio(exact, total), selective_accuracy=_ratio(exact, scored),
                precision=_ratio(tp, tp + fp), recall=_ratio(tp, tp + fn),
                f1=_ratio(2 * tp, 2 * tp + fp + fn))


def run_experiment(exp, data, inputs, references, *, predictors, source_commit,
                   models=None, clock=time.perf_counter):
    """Evaluate fixed test IDs only; retain raw and failed partial outputs separately.

    Inputs/references are ID-keyed JSON objects, hashed separately. Adapters are
    trusted local callables; this is not a process sandbox or preemptive timeout.
    """
    validate_experiment(exp, data)
    if exp['primary_metric'] not in {'f1', 'accuracy', 'selective_accuracy', 'coverage', 'precision', 'recall'}:
        raise ValueError('unsupported primary metric')
    if canonical_sha256(inputs) != data['sha256']:
        raise ValueError('input hash mismatch')
    if canonical_sha256(references) != data['reference']['sha256']:
        raise ValueError('reference hash mismatch')
    rows = {row['id']: row for row in data['rows']}
    if set(inputs) != set(rows) or set(references) != set(rows):
        raise ValueError('input/reference IDs mismatch')
    for gold in references.values():
        _set(gold)
    models = models or {}
    arm_ids = {arm['id'] for arm in exp['arms']}
    if set(predictors) - arm_ids or set(models) - arm_ids:
        raise ValueError('undeclared arm')
    outputs, failures, arms = {}, {}, []
    for arm in exp['arms']:
        key = arm['id']
        predictor = predictors.get(key)
        model = models.get(key, {})
        if not callable(predictor):
            arms.append(dict(id=key, status='unavailable', reason='adapter unavailable'))
            continue
        if arm['role'] != 'deterministic' and not all(isinstance(model.get(k), str) and model[k].strip()
                                                       for k in ('id', 'revision', 'licence')):
            arms.append(dict(id=key, status='unavailable', reason='model provenance unavailable'))
            continue
        raw = []
        start = clock()
        try:
            for case_id in exp['case_ids']:
                if clock() - start > exp['budget']['max_seconds']:
                    raise TimeoutError('arm budget exceeded')
                prediction = predictor(copy.deepcopy(inputs[case_id]))
                if clock() - start > exp['budget']['max_seconds']:
                    raise TimeoutError('arm budget exceeded')
                if prediction is not None:
                    _set(prediction)
                raw.append(dict(id=case_id, groups=copy.deepcopy(rows[case_id]['groups']),
                                gold=copy.deepcopy(references[case_id]), prediction=copy.deepcopy(prediction)))
            metrics = summarize(raw)
            elapsed = clock() - start
            if not math.isfinite(elapsed) or elapsed < 0 or elapsed > exp['budget']['max_seconds']:
                raise TimeoutError('invalid elapsed time or arm budget exceeded')
            result = dict(id=key, status='executed', predictions_sha256=canonical_sha256(raw),
                          metrics=metrics, elapsed_seconds=elapsed)
            if arm['role'] != 'deterministic':
                result['model'] = copy.deepcopy(model)
            outputs[key] = raw
            arms.append(result)
        except Exception as exc:
            # Do not embed exception messages, which may contain input material.
            failures[key] = raw
            arms.append(dict(id=key, status='failed', reason=type(exc).__name__))
    manifest = {k: exp[k] for k in ('schema_version', 'experiment_id', 'dataset_sha256',
                                   'reference_sha256', 'seed', 'claim_boundary')}
    manifest.update(source_commit=source_commit, config_sha256=canonical_sha256(exp),
                    dataset_manifest_sha256=canonical_sha256(data), environment=platform.python_version(), arms=arms)
    validate_result(manifest, exp, data)
    return dict(manifest=manifest, predictions=outputs, failure_artifacts=failures)


def paired_f1_interval(baseline, challenger, *, grouping_key, seed, draws=1000):
    """Paired cluster bootstrap of micro-F1 delta; report undefined resamples."""
    if type(draws) is not int or not 1 <= draws <= 100000:
        raise ValueError('invalid bootstrap draws')
    a, b = ({r['id']: r for r in rows} for rows in (baseline, challenger))
    if len(a) != len(baseline) or len(b) != len(challenger) or set(a) != set(b) or not a:
        raise ValueError('paired case IDs required')
    grouped = defaultdict(list)
    for case_id in sorted(a):
        x, y = a[case_id], b[case_id]
        if x['gold'] != y['gold'] or x['groups'] != y['groups'] or grouping_key not in x['groups']:
            raise ValueError('paired reference/group mismatch')
        grouped[x['groups'][grouping_key]].append(case_id)
    keys = sorted(grouped)
    if len(keys) < 2:
        raise ValueError('at least two clusters required')

    def delta(ids):
        x, y = (summarize([arm[i] for i in ids])['f1'] for arm in (a, b))
        return None if x is None or y is None else y - x

    rng = random.Random(seed)
    values = []
    for _ in range(draws):
        value = delta([i for _ in keys for i in grouped[rng.choice(keys)]])
        if value is not None:
            values.append(value)
    values.sort()
    return dict(difference=delta(sorted(a)), clusters=len(keys), draws=draws, valid_draws=len(values), seed=seed,
                lower=values[int(0.025 * (len(values) - 1))] if values else None,
                upper=values[math.ceil(0.975 * (len(values) - 1))] if values else None)
