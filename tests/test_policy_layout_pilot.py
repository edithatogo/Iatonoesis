from iatonoesis.policy_layout_pilot import generate, flat, spatial, score, run


def test_layout_recovers_shuffled_marker():
    page = [{'text': 'REQ-A: routine', 'x': 0, 'y': 10},
            {'text': 'REQ-B: routine', 'x': 100, 'y': 10},
            {'text': '*1', 'x': 25, 'y': 10},
            {'text': '*1: exception alpha', 'x': 0, 'y': 90}]
    assert spatial(page) == {('A', 'exception alpha')}
    assert flat(page) == {('B', 'exception alpha')}


def test_oracle_and_inputs_are_separate_and_groups_disjoint():
    docs = generate(17)
    assert len(docs) == 96
    assert len({doc['id'] for doc in docs}) == 96
    by_family = {}
    for doc in docs:
        assert all(set(token) == {'text', 'x', 'y'} for token in doc['page'])
        by_family.setdefault(doc['family'], set()).add(doc['split'])
    assert all(len(splits) == 1 for splits in by_family.values())


def test_score_penalizes_false_binding_and_missing_link():
    assert score({('B', 'x')}, {('A', 'x')}) == {'tp': 0, 'fp': 1, 'fn': 1}


def test_same_seed_reproduces_dataset_and_predictions():
    assert run(17) == run(17)
    assert run(17)['test_documents'] == 48
