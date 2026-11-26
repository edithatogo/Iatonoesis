import pytest

pytest.importorskip('torch', reason='optional CPU neural experiment runtime')
from iatonoesis import core_suite as core
from iatonoesis.neural_suite import calibrate, guard, run, train
from iatonoesis.run_contracts import validate_result


def test_calibration_threshold_uses_only_supported_examples():
    assert calibrate([(0.99, True)] * 3) is None
    assert calibrate([(0.9, True)] * 4 + [(0.7, False)]) == 0.8
    assert calibrate([(0.9, False)] * 10) is None


def test_hard_guards_do_not_authorize_unsupported_actions():
    assert guard('E04', {}, [], None) is None
    assert guard('E04', {}, [['action']], []) is None
    assert guard('E11', {}, ['supported'], ['unsupported']) is None
    assert guard('E17', {'allowed': ['quality']}, ['finance'], ['escalate']) is None
    assert guard('E22', {}, ['completed'], ['unverifiable']) is None
    assert guard('E20', {}, ['supports'], ['insufficient']) is None


def test_training_ignores_test_and_calibration_labels():
    data, exp, inputs, refs = core.freeze(17, 'a' * 40)['E04']
    _, m1 = train('E04', data, inputs, refs, seed=17, epochs=2)
    altered = dict(refs)
    for row in data['rows']:
        if row['split'] != 'development':
            altered[row['id']] = [['unrelated', 'reference']]
    _, m2 = train('E04', data, inputs, altered, seed=17, epochs=2)
    assert m1['weights_sha256'] == m2['weights_sha256']
    assert m1['training_ids_sha256'] == m2['training_ids_sha256']


def test_full_eight_family_contracts_and_ablation():
    frozen = core.freeze(17, 'a' * 40)
    results = run(frozen, 'b' * 40, epochs=2, draws=10)
    assert set(results) == set(core.TASKS)
    for key, result in results.items():
        data, _, _, _ = frozen[key]
        validate_result(result['manifest'], result['experiment'], data)
        assert {a['id'] for a in result['manifest']['arms']} >= {'rules', 'classical', 'neural', 'guarded', 'fallback', 'agreement'}
        assert all(a['status'] == 'executed' for a in result['manifest']['arms'])
        assert result['manifest']['arms'][2]['model']['training_split'] == 'development'
        assert result['predictions']['neural'][0]['id'] == result['predictions']['rules'][0]['id']
    assert 'no_messages' in results['E07']['predictions']


def test_freeze_tampering_rejected_before_training():
    f = core.freeze(17, 'a' * 40)
    data, exp, inputs, refs = f['E02']
    refs[exp['case_ids'][0]] = []
    with pytest.raises(ValueError, match='frozen'):
        run(f, 'b' * 40, epochs=1, draws=10)
