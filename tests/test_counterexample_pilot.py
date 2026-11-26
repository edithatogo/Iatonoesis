import itertools

from iatonoesis.counterexample_pilot import (
    DOMAIN, FAMILIES, MUTATIONS, evaluate, oracle, defects, fit, run,
)


def test_independent_oracle_agrees_on_entire_domain():
    for family, t, u, mutation, case in itertools.product(
        FAMILIES, (1, 2, 3), (1, 2, 3), (None,) + MUTATIONS, DOMAIN
    ):
        assert evaluate(family, t, u, case, mutation) == oracle(family, t, u, case, mutation)


def test_defects_are_nonempty_distinct_semantic_signatures():
    signatures = list(defects('and', 2, 2).values())
    assert signatures and all(signatures)
    assert len(set(signatures)) == len(signatures)
    assert all(set(s) <= set(range(len(DOMAIN))) for s in signatures)


def test_training_rejects_held_out_family():
    import pytest
    with pytest.raises(ValueError, match='development'):
        fit(('nand',))


def test_run_reproducible_and_matched_budget():
    a = run()
    assert a == run()
    assert set(a['split']['development']).isdisjoint(a['split']['test'])
    assert len(a['rules']) == 36
    for rule in a['rules']:
        assert rule['family'] in a['split']['test']
        for arm in rule['arms']:
            assert len(arm['indices']) == len(set(arm['indices'])) == 8
            assert set(arm['indices']) <= set(range(len(DOMAIN)))
            assert 0 <= len(arm['killed']) <= rule['denominator']
            truth = defects(rule['family'], rule['t'], rule['u'])
            assert set(arm['killed']) == {k for k, v in truth.items() if set(v) & set(arm['indices'])}
