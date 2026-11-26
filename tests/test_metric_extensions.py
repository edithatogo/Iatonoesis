import math
import pytest
from iatonoesis.metric_extensions import continuous, calibration, ranking, mutation_coverage, conformal_radius


def test_continuous_and_intervals():
    m = continuous([1, 3], [2, 1], radius=1)
    assert m['n'] == 2 and m['mae'] == 1.5
    assert m['rmse'] == pytest.approx(math.sqrt(2.5))
    assert m['interval_coverage'] == 0.5 and m['interval_width'] == 2
    with pytest.raises(ValueError):
        continuous([1], [float('nan')])
    with pytest.raises(ValueError):
        continuous([1], [])


def test_conformal_order_statistic_and_small_sample():
    assert conformal_radius([1, 2, 3, 4], coverage=.6) == 3
    with pytest.raises(ValueError, match='insufficient'):
        conformal_radius([1, 2], coverage=.9)


def test_calibration_includes_endpoints():
    m = calibration([0, 1, 1, 0], [0, 1, .5, .5], bins=2)
    assert m['brier'] == .125
    assert m['ece'] == pytest.approx(0)
    assert sum(b['n'] for b in m['bins']) == 4
    with pytest.raises(ValueError):
        calibration([0], [1.1])


def test_fixed_pool_ranking_and_unjudged_rejection():
    m = ranking(['b', 'a', 'c'], {'a': 1, 'b': 0, 'c': 1}, 2)
    assert m['recall'] == .5 and m['precision'] == .5
    assert m['ndcg'] == pytest.approx((1/math.log2(3))/(1+1/math.log2(3)))
    assert ranking(['a', 'b'], {'a': 0, 'b': 0}, 1)['ndcg'] is None
    with pytest.raises(ValueError, match='judged'):
        ranking(['a', 'b'], {'a': 1}, 1)


def test_mutation_deduplicates_equivalent_signatures():
    m = mutation_coverage({'a': [0, 1], 'equivalent_a': [0, 1], 'b': [2], 'unchanged': []}, [0], pool_size=3, budget=1)
    assert m['distinct_defects'] == 2 and m['detected'] == 1 and m['coverage'] == .5
    with pytest.raises(ValueError):
        mutation_coverage({'a': [0]}, [0, 0], pool_size=2, budget=2)


def test_paired_difference_bootstrap_known_delta():
    from iatonoesis.metric_extensions import paired_mean_difference
    r = paired_mean_difference([1, 3], [2, 4], seed=1, draws=100)
    assert r['difference'] == r['lower'] == r['upper'] == 1
    assert r['n'] == 2 and r['draws'] == 100
    with pytest.raises(ValueError):
        paired_mean_difference([1], [2], seed=1)
