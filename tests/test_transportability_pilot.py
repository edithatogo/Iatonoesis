import pytest
from iatonoesis.transportability_pilot import run, environment, features, fit_assessors, SOURCE_SEED


def test_identical_observations_do_not_identify_hidden_outcomes():
    a = environment(33, 16, .3, .5, .2, 0.)
    b = environment(33, 16, .3, .5, .2, 3.)
    assert [r['visible'] for r in a] == [r['visible'] for r in b]
    assert [r['target'] for r in a] != [r['target'] for r in b]
    assert features([r['visible'] for r in a]) == features([r['visible'] for r in b])


def test_fit_rejects_non_development_environments():
    with pytest.raises(ValueError, match='development'):
        fit_assessors([dict(split='test', feature=[1.], mae=1., coverage=.8)])


def test_replay_and_control():
    r = run()
    assert r == run()
    assert r['counts'] == {'development': 20, 'calibration': 20, 'test': 20}
    assert set(r['meta_split']['development']).isdisjoint(r['meta_split']['test'])
    assert len(r['test']) == 20
    control = r['negative_control']
    assert control['visible_sha256_equal'] and control['estimates_equal']
    assert abs(control['mae_difference']) > 1
    for m in r['metrics'].values():
        assert m['n'] == 20 and 0 <= m['coverage_interval_observed'] <= 1
        assert m['mae_estimation_mae'] >= 0
