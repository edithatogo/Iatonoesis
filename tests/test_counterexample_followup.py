import itertools

import pytest

from iatonoesis import counterexample_pilot as prior
from iatonoesis.counterexample_followup import (
    TEST_FAMILIES, TEST_MUTATIONS, evaluate, oracle, signatures, exact_ceiling,
    run, training_rows, select,
)


def test_new_families_and_mutation_operators_disjoint():
    assert set(TEST_FAMILIES).isdisjoint(prior.FAMILIES)
    assert set(TEST_MUTATIONS).isdisjoint(prior.MUTATIONS)
    rows, provenance = training_rows()
    assert rows
    assert set(provenance['families']) == set(prior.SPLIT['development'])
    assert set(provenance['mutations']) == set(prior.MUTATIONS)


def test_new_boolean_and_truth_table_agree_exhaustively():
    for family, t, u, case, mut in itertools.product(
        TEST_FAMILIES, (1, 2, 3), (1, 2, 3), prior.DOMAIN,
        (None,) + TEST_MUTATIONS,
    ):
        assert evaluate(family, t, u, case, mut) == oracle(family, t, u, case, mut)


def test_semantic_deduplication_and_exact_ceiling():
    s = signatures('exact_two', 2, 2)
    assert s and all(s.values()) and len(set(s.values())) == len(s)
    # A repeated mask or dominated mask cannot inflate coverage.
    assert exact_ceiling((0b0011, 0b0011, 0b0100, 0b1000), (1, 2, 3, 4)) == {1: 2, 2: 3, 3: 4, 4: 4}
    assert exact_ceiling((0, 0), (1, 2)) == {1: 0, 2: 0}


def test_feedback_not_required_for_static_selector():
    def forbidden(_):
        raise AssertionError('static selector must not query hidden feedback')
    result = select('pairwise', 'priority', 2, 2, 8, (), forbidden)
    assert len(set(result)) == 8


def test_feedback_exposes_only_chosen_cases_and_budget():
    called = []
    def observed(i):
        assert i not in called
        called.append(i)
        return 0, 0
    result = select('adaptive_coverage', 'priority', 2, 2, 8, (), observed)
    assert result == called
    assert len(set(result)) == 8
    with pytest.raises(ValueError, match='budget'):
        select('pairwise', 'priority', 2, 2, 101, (), observed)


def test_result_budget_and_oracle_ceiling():
    out = run()
    assert len(out['rules']) == 54
    for rule in out['rules']:
        s = signatures(rule['family'], rule['t'], rule['u'])
        assert rule['denominator'] == len(s)
        for arm in rule['arms']:
            ix = arm['indices']
            assert len(ix) == len(set(ix)) == 8
            assert all(i in range(100) for i in ix)
            for budget in (1, 2, 4, 8):
                expected = {m for m, sig in s.items() if set(ix[:budget]) & set(sig)}
                assert set(arm['killed'][str(budget)]) == expected
                assert len(expected) <= rule['oracle_ceiling'][str(budget)] <= len(s)
    assert out == run()
