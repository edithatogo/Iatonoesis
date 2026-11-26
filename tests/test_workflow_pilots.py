import copy

import pytest

from iatonoesis.workflow_pilots import (
    extract_context, extract_naive, make_discharge, make_steps, paired_run,
    run, verify_naive, verify_steps,
)


def test_paired_runner_counts_abstention_and_errors():
    cases = [{'id': 'a', 'family': 'f', 'split': 'test', 'input': 'a', 'gold': ['x']},
             {'id': 'b', 'family': 'f', 'split': 'test', 'input': 'b', 'gold': []}]
    result = paired_run(cases, {'abstain': lambda _: None, 'wrong': lambda _: ['y']})
    assert result['abstain']['metrics']['abstained'] == 2
    assert result['abstain']['metrics']['fn'] == 1
    assert result['wrong']['metrics']['fp'] == 2
    assert result['wrong']['metrics']['errors'] == 2


def test_runner_rejects_duplicate_ids_and_non_test_rows():
    case = {'id': 'a', 'family': 'f', 'split': 'test', 'input': '', 'gold': []}
    with pytest.raises(ValueError, match='duplicate'):
        paired_run([case, copy.deepcopy(case)], {'a': lambda _: []})
    with pytest.raises(ValueError, match='test'):
        paired_run([dict(case, split='development')], {'a': lambda _: []})


def test_completed_obligation_is_not_pending():
    note = 'Task: review form A; Owner: team A; Due: day 7; Condition: if available. Already completed.'
    assert extract_naive(note) == [['review form A', 'team A', 'day 7', 'if available']]
    assert extract_context(note) == []


def test_unrecognised_status_abstains():
    note = 'Task: review form A; Owner: team A; Due: day 7; Condition: if available. Unclear status.'
    assert extract_context(note) is None


def test_order_is_not_completion():
    episode = {'deadline': 20, 'events': [{'kind': 'ordered', 'minute': 1}],
               'note': '', 'complete_log': True, 'exception': False}
    assert verify_naive(episode) == ['completed']
    assert verify_steps(episode) == ['missing']


def test_incomplete_record_is_not_missing_or_completed():
    episode = {'deadline': 20, 'events': [{'kind': 'ordered', 'minute': 1}],
               'note': '', 'complete_log': False, 'exception': False}
    assert verify_steps(episode) == ['unverifiable']


def test_late_step_and_documented_exception():
    episode = {'deadline': 20, 'events': [{'kind': 'performed', 'minute': 25}],
               'note': '', 'complete_log': True, 'exception': False}
    assert verify_steps(episode) == ['late']
    assert verify_steps(dict(episode, exception=True, events=[])) == ['inapplicable']


def test_synthetic_families_are_disjoint():
    for generator, count in [(make_discharge, 200), (make_steps, 150)]:
        rows = generator(17)
        assert len(rows) == count
        assert len({c['id'] for c in rows}) == count
        groups = {p: {c['family'] for c in rows if c['split'] == p}
                  for p in ('development', 'calibration', 'test')}
        assert all(groups[p].isdisjoint(groups[q]) for p in groups for q in groups if p != q)


def test_reproducible_run_and_safety_counters():
    a = run(17)
    assert a == run(17)
    assert a['claim_boundary'] == 'synthetic_only'
    assert a['E04']['arms']['context']['metrics']['fp'] < a['E04']['arms']['naive']['metrics']['fp']
    assert a['E22']['arms']['explicit']['false_timely_completion']['count'] < a['E22']['arms']['naive']['false_timely_completion']['count']
    assert a['E22']['arms']['explicit']['missed_step_recall']['denominator'] > 0
