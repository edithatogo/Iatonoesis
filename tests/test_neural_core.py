import pytest
from iatonoesis.neural_core import fit, probabilities


def test_deterministic_fit_and_probability_contract():
    rows = [(('a',),'yes'), (('b',),'no')]*20
    a = fit(rows, hidden=8, seed=17)
    assert a == fit(rows, hidden=8, seed=17)
    p = probabilities(a, ('a',))
    assert set(p) == {'no','yes'}
    assert sum(p.values()) == pytest.approx(1.)
    assert p['yes'] > p['no']
    assert probabilities(a, ('unseen',)) == probabilities(a, ())


def test_linear_and_neural_are_distinct_and_validate_input():
    rows = [(('a',),'yes'), (('b',),'no')]*4
    assert fit(rows, hidden=0, seed=17)['hidden'] == 0
    assert fit(rows, hidden=8, seed=17)['hidden'] == 8
    with pytest.raises(ValueError):
        fit([], hidden=8, seed=17)
    with pytest.raises(ValueError):
        fit(rows, hidden=-1, seed=17)
