import pytest

from iatonoesis.run_contracts import canonical_sha256, validate_dataset, validate_experiment, validate_result

H = 'a' * 64
C = 'b' * 40


def dataset():
    return dict(schema_version='0.1.0', dataset_id='synthetic-example', kind='synthetic',
                source='repository-generator', revision=C, sha256=H,
                rights=dict(status='approved', licence='MIT', evidence='generator licence and review'),
                reference=dict(kind='deterministic_oracle', revision=C, sha256=H),
                rows=[dict(id='a', split='development', groups={'family': 'x'}),
                      dict(id='b', split='calibration', groups={'family': 'y'}),
                      dict(id='c', split='test', groups={'family': 'z'})],
                grouping_keys=['family'])


def experiment():
    return dict(schema_version='0.1.0', experiment_id='E02-pilot', track_task='T01.007',
                dataset_id='synthetic-example', dataset_sha256=H, reference_sha256=H,
                split='test', case_ids=['c'], primary_metric='accuracy', unit='case', seed=17,
                arms=[dict(id='rules', role='deterministic'), dict(id='learned', role='specialist')],
                budget=dict(max_cases=1, max_seconds=60), claim_boundary='synthetic_only')


def result():
    return dict(schema_version='0.1.0', experiment_id='E02-pilot', source_commit=C,
                config_sha256=canonical_sha256(experiment()), dataset_sha256=H, reference_sha256=H,
                environment='python local', seed=17, claim_boundary='synthetic_only',
                arms=[dict(id='rules', status='executed', predictions_sha256=H,
                           metrics=dict(total=1, scored=1, abstained=0, errors=0), elapsed_seconds=0.2),
                      dict(id='learned', status='unavailable', reason='not yet qualified')])


def test_valid_contract_chain():
    d, e, r = dataset(), experiment(), result()
    validate_dataset(d)
    validate_experiment(e, d)
    validate_result(r, e, d)


@pytest.mark.parametrize('field,value,match', [('sha256', None, 'hash'), ('revision', '', 'revision')])
def test_missing_provenance(field, value, match):
    d = dataset()
    d[field] = value
    with pytest.raises(ValueError, match=match):
        validate_dataset(d)


def test_unqualified_rights_rejected():
    d = dataset()
    d['rights']['status'] = 'candidate'
    with pytest.raises(ValueError, match='rights'):
        validate_dataset(d)


def test_group_leakage_rejected():
    d = dataset()
    d['rows'][2]['groups']['family'] = 'x'
    with pytest.raises(ValueError, match='leakage'):
        validate_dataset(d)


def test_missing_group_rejected():
    d = dataset()
    d['rows'][2]['groups'] = {}
    with pytest.raises(ValueError, match='group'):
        validate_dataset(d)


def test_reference_mismatch_rejected():
    e = experiment()
    e['reference_sha256'] = 'c' * 64
    with pytest.raises(ValueError, match='reference'):
        validate_experiment(e, dataset())


def test_result_denominator_rejected():
    r = result()
    r['arms'][0]['metrics']['scored'] = 2
    with pytest.raises(ValueError, match='denominator'):
        validate_result(r, experiment(), dataset())


def test_unavailable_arm_requires_reason_and_no_metrics():
    r = result()
    r['arms'][1]['metrics'] = {'total': 1}
    with pytest.raises(ValueError, match='unavailable'):
        validate_result(r, experiment(), dataset())


def test_result_cannot_omit_prespecified_arm():
    r = result()
    r['arms'].pop()
    with pytest.raises(ValueError, match='arm'):
        validate_result(r, experiment(), dataset())


def test_unknown_state_rejected():
    r = result()
    r['arms'][1]['status'] = 'probably fine'
    with pytest.raises(ValueError, match='status'):
        validate_result(r, experiment(), dataset())


def test_synthetic_claim_cannot_be_promoted():
    e = experiment()
    e['claim_boundary'] = 'clinical_effectiveness'
    with pytest.raises(ValueError, match='claim'):
        validate_experiment(e, dataset())
