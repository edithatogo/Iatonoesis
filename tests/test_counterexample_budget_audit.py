import itertools
import pytest
from iatonoesis.counterexample_budget_audit import DOMAIN, truth_masks, balanced_boundary, symbolic_select, audit


def test_balanced_prefixes_represent_every_flag_group_equally():
    sequences = balanced_boundary(2, 2)
    assert len(sequences) == 24
    assert len(set(sequences)) == 12
    flags = [DOMAIN[s[0]][2:] for s in sequences]
    assert all(flags.count(g) == 6 for g in itertools.product((0,1), repeat=2))
    assert all(DOMAIN[s[0]][2:] != DOMAIN[s[1]][2:] for s in sequences)


def test_symbolic_selector_uses_only_supplied_proxy_masks():
    assert symbolic_select([3,1,4,0],1) == (0,)
    assert symbolic_select([3,1,4,0],2) == (0,2)
    with pytest.raises(ValueError):
        symbolic_select([1,2],3)


def test_known_original_and_test_signature_counts():
    assert len(truth_masks('agreement_guard',2,2,'test')) == 5
    assert len(truth_masks('exact_two',2,2,'test')) == 6
    assert len(truth_masks('priority',2,2,'test')) == 9
    assert len(truth_masks('parity_four',2,2,'test')) == 5
