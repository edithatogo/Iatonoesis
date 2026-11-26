import copy

import pytest

from iatonoesis.run_contracts import canonical_sha256, validate_result
from iatonoesis.runner import paired_f1_interval, run_experiment, summarize

COMMIT = 'a' * 40


def fixture():
    inputs = {'d': ['a'], 'c': ['b'], 't1': ['x'], 't2': ['y']}
    refs = copy.deepcopy(inputs)
    groups = [('d', 'development', 'd'), ('c', 'calibration', 'c'),
              ('t1', 'test', 'one'), ('t2', 'test', 'two')]
    data = dict(schema_version='0.1.0', dataset_id='fixture', kind='synthetic',
                source='local synthetic fixture', revision=COMMIT, sha256=canonical_sha256(inputs),
                rights=dict(status='approved', licence='MIT', evidence='repository-authored test fixture'),
                reference=dict(kind='deterministic_oracle', revision=COMMIT, sha256=canonical_sha256(refs)),
                grouping_keys=['family'], rows=[dict(id=i, split=p, groups={'family': g}) for i, p, g in groups])
    exp = dict(schema_version='0.1.0', experiment_id='fixture', track_task='T00.003',
               dataset_id=data['dataset_id'], dataset_sha256=data['sha256'],
               reference_sha256=data['reference']['sha256'], split='test', case_ids=['t1', 't2'],
               primary_metric='f1', unit='case', seed=17,
               arms=[dict(id='rules', role='deterministic'), dict(id='context', role='deterministic'),
                     dict(id='learned', role='specialist')],
               budget=dict(max_cases=2, max_seconds=10), claim_boundary='synthetic_only')
    return exp, data, inputs, refs


def execute(*args, predictors=None, models=None, **kwargs):
    if not args:
        args = fixture()
    return run_experiment(*args, predictors=predictors or {'rules': lambda x: x, 'context': lambda _: None},
                          models=models, source_commit=COMMIT, **kwargs)


def test_execution_is_contract_valid_and_reproducible():
    args = fixture()
    a, b = execute(*args), execute(*args)
    validate_result(a['manifest'], args[0], args[1])
    assert a['predictions'] == b['predictions']
    assert a['manifest']['arms'][0]['predictions_sha256'] == b['manifest']['arms'][0]['predictions_sha256']
    assert a['manifest']['arms'][0]['metrics']['f1'] == 1
    assert a['manifest']['arms'][1]['metrics']['fn'] == 2
    assert a['manifest']['arms'][1]['metrics']['selective_accuracy'] is None
    assert a['manifest']['arms'][2]['status'] == 'unavailable'
    assert a['manifest']['dataset_manifest_sha256'] == canonical_sha256(args[1])


def test_frozen_inputs_and_reference_hashes_are_verified():
    exp, data, inputs, refs = fixture()
    inputs['t1'] = ['tampered']
    with pytest.raises(ValueError, match='input hash'):
        execute(exp, data, inputs, refs)
    exp, data, inputs, refs = fixture()
    refs['t1'] = ['tampered']
    with pytest.raises(ValueError, match='reference hash'):
        execute(exp, data, inputs, refs)


def test_mutation_of_adapter_input_does_not_change_other_arms():
    def mutate(value):
        value.append('extra')
        return value
    r = execute(predictors={'rules': mutate, 'context': lambda x: x})
    assert r['manifest']['arms'][0]['metrics']['fp'] == 2
    assert r['manifest']['arms'][1]['metrics']['f1'] == 1


def test_failed_arm_never_receives_metrics_and_retains_partial_rows():
    def fail_on_second(value):
        if value == ['y']:
            raise RuntimeError('do not publish this input or error message')
        return value
    r = execute(predictors={'rules': fail_on_second, 'context': lambda x: x})
    arm = r['manifest']['arms'][0]
    assert arm['status'] == 'failed'
    assert arm['reason'] == 'RuntimeError'
    assert 'metrics' not in arm and 'predictions_sha256' not in arm
    assert len(r['failure_artifacts']['rules']) == 1
    assert 'rules' not in r['predictions']


def test_runtime_budget_exceeded_records_failure():
    ticks = iter([0, 0, 11, 20, 20, 20, 20, 20])
    r = execute(predictors={'rules': lambda x: x}, clock=lambda: next(ticks))
    assert r['manifest']['arms'][0]['status'] == 'failed'
    assert r['manifest']['arms'][0]['reason'] == 'TimeoutError'


def test_learned_arm_requires_provenance():
    r = execute(predictors={'rules': lambda x: x, 'learned': lambda x: x})
    assert r['manifest']['arms'][2]['status'] == 'unavailable'
    model = dict(id='toy-trained', revision=COMMIT, licence='MIT')
    r = execute(predictors={'rules': lambda x: x, 'learned': lambda x: x}, models={'learned': model})
    assert r['manifest']['arms'][2]['model'] == model
    assert r['manifest']['arms'][2]['status'] == 'executed'


def test_set_counts_abstentions_and_zero_denominators():
    rows = [dict(gold=['x'], prediction=None), dict(gold=[], prediction=[])]
    m = summarize(rows)
    assert m['fn'] == 1 and m['fp'] == 0 and m['abstained'] == 1
    assert m['coverage'] == 0.5 and m['accuracy'] == 0.5 and m['selective_accuracy'] == 1
    assert m['precision'] is None and m['recall'] == 0 and m['f1'] == 0
    assert summarize([dict(gold=[], prediction=[])])['f1'] is None


def test_paired_cluster_bootstrap_known_difference():
    r = execute(predictors={'rules': lambda _: [], 'context': lambda x: x})
    raw = r['predictions']
    a = paired_f1_interval(raw['rules'], raw['context'], grouping_key='family', seed=17, draws=100)
    assert a == paired_f1_interval(raw['rules'], raw['context'], grouping_key='family', seed=17, draws=100)
    assert a['difference'] == a['lower'] == a['upper'] == 1
    assert a['clusters'] == 2 and a['valid_draws'] == 100
    with pytest.raises(ValueError, match='paired'):
        paired_f1_interval(raw['rules'][:-1], raw['context'], grouping_key='family', seed=17, draws=100)
