import json
from pathlib import Path

import pytest

from iatonoesis.rule_feedback import refined, run

FIXTURE = Path(__file__).resolve().parents[1] / 'datasets/fixtures/rule-feedback-v0.1.0.json'


def test_frozen_stress_cases():
    data = json.loads(FIXTURE.read_text())
    for row in data['cases']:
        assert refined(data['defaults'] | row['overrides']) == [row['gold']], row['id']


def test_unknown_provenance_and_malformed_metadata_fail_closed():
    data = json.loads(FIXTURE.read_text())['defaults']
    for key in ('deadline', 'observed_until', 'note_verified', 'exception_verified', 'complete_log'):
        incomplete = dict(data)
        del incomplete[key]
        assert refined(incomplete) == ['unverifiable']
    assert refined(data | {'deadline': True}) == ['unverifiable']
    assert refined(data | {'events': [{'kind': 'performed', 'minute': '18'}]}) == ['unverifiable']


def test_comparator_replay_and_review_accounting():
    data = json.loads(FIXTURE.read_text())
    result = run(data)
    assert result == run(data)
    assert result['total'] == 19
    assert result['arms']['refined']['exact'] == 19
    assert result['arms']['refined']['false_timely'] == 0
    assert result['arms']['refined']['missed_required_review'] == 0
    assert result['arms']['alias_only']['false_timely'] > 0
    assert result['arms']['legacy']['exact'] < 19
    with pytest.raises(ValueError, match='duplicate'):
        run(data | {'cases': data['cases'] + data['cases'][:1]})


def test_additional_input_guards_and_cli(tmp_path, monkeypatch):
    import sys
    from iatonoesis.rule_feedback import main

    data = json.loads(FIXTURE.read_text())['defaults']
    for overrides in ({'note': None}, {'events': [{'kind': 'unknown', 'minute': 1}]},
                      {'note': 'Performance attested at minute 31.', 'note_verified': True}):
        assert refined(data | overrides) == ['unverifiable']
    output = tmp_path / 'output.json'
    monkeypatch.setattr(sys, 'argv', ['rule_feedback', '--fixtures', str(FIXTURE), '--output', str(output)])
    main()
    assert json.loads(output.read_text()) == run(json.loads(FIXTURE.read_text()))
