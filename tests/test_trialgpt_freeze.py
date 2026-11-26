import json
import pytest
from iatonoesis.trialgpt_freeze import candidate_freeze


def fixture():
    return [dict(annotation_id=i, patient_id=f'patient-{i//2}', trial_id=f'trial-{i//2}',
                 training=i % 3 == 0, criterion_missing=i == 1) for i in range(12)]


def test_candidate_is_stable_group_disjoint_and_not_admitted():
    rows = fixture()
    a = candidate_freeze(rows)
    assert a == candidate_freeze(list(reversed(rows)))
    assert a['qualification'] == 'not_qualified'
    assert a['rows'] == 12 and a['components'] == 6
    assert sum(x['rows'] for x in a['partitions'].values()) == 12
    assert sum(x['training_true'] for x in a['partitions'].values()) == 4
    assert sum(x['criterion_missing'] for x in a['partitions'].values()) == 1
    assert a['group_disjoint_verified']
    assert 'patient-' not in json.dumps(a) and 'trial-' not in json.dumps(a)
    assert all(x['rows'] > 0 for x in a['partitions'].values())


def test_transitive_links_are_one_group():
    rows = fixture()
    rows[2]['trial_id'] = rows[0]['trial_id']
    assert candidate_freeze(rows)['components'] == 5


def test_invalid_and_duplicate_metadata_fail_closed():
    rows = fixture()
    with pytest.raises(ValueError, match='duplicate'):
        candidate_freeze(rows + [rows[0]])
    with pytest.raises(ValueError, match='metadata'):
        candidate_freeze([dict(rows[0], training=None)] + rows[1:])
    with pytest.raises(ValueError, match='three'):
        candidate_freeze(rows[:2])


def test_label_or_model_output_does_not_affect_partition():
    rows = fixture()
    altered = [dict(r, expert_eligibility='changed', gpt4_eligibility='changed') for r in rows]
    assert candidate_freeze(rows) == candidate_freeze(altered)
