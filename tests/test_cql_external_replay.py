import hashlib
import json

import pytest

from iatonoesis.cql_external_replay import evaluate, replay, load_suite


def test_three_valued_logic_and_conditional():
    assert evaluate('null and false') is False
    assert evaluate('null or false') is None
    assert evaluate('false implies null') is True
    assert evaluate('not null') is None
    assert evaluate('if 8 > 1 then 4 + 6 else 0') == 10
    assert evaluate('if null = 3 then 1 else 8') == 8


def test_case_semantics_and_unsupported_syntax():
    assert evaluate('case when 1 > 2 then 8 else 3 end') == 3
    assert evaluate('case 2 + 3 when 5 then 17 else 0 end') == 17
    with pytest.raises(ValueError):
        evaluate('unknown(42)')
    with pytest.raises(ValueError):
        evaluate('true false')


def test_fixture_hash_and_identity(tmp_path):
    file = tmp_path / 'suite.json'
    file.write_text(json.dumps([{'id': 'x', 'expression': 'true', 'expected': True}]))
    raw = file.read_bytes()
    entry = {'dataset_sha256': hashlib.sha256(raw).hexdigest(), 'case_count': 1, 'case_ids': ['x'], 'partition': 'external_test_only', 'training_eligible': False}
    assert load_suite(file, entry)[0]['id'] == 'x'
    with pytest.raises(ValueError, match='hash'):
        load_suite(file, dict(entry, dataset_sha256='0' * 64))
    with pytest.raises(ValueError, match='case IDs'):
        load_suite(file, dict(entry, case_ids=['y']))
    with pytest.raises(ValueError, match='test-only'):
        load_suite(file, dict(entry, training_eligible=True))


def test_replay_distinguishes_null_integer_and_boolean():
    rows = [{'id': 'a', 'expression': 'null', 'expected': None}, {'id': 'b', 'expression': '1', 'expected': True}, {'id': 'c', 'expression': 'bad', 'expected': False}]
    result = replay(rows)
    assert result['total'] == 3
    assert result['correct'] == 1
    assert result['incorrect'] == 1
    assert result['unavailable'] == 1
    assert result['cases'][0]['status'] == 'correct'
    assert result['cases'][2]['status'] == 'unavailable'


def test_published_fixture_replay():
    from pathlib import Path
    from iatonoesis.cql_external_replay import run

    directory = Path(__file__).resolve().parents[1] / 'datasets/fixtures/cql-external-holdout-v0.1.0'
    result = run(directory)
    assert sum(s['total'] for s in result['suites'].values()) == 48
    assert sum(s['correct'] for s in result['suites'].values()) == 48
    assert sum(s['unavailable'] for s in result['suites'].values()) == 0
    assert hashlib.sha256((json.dumps(result, sort_keys=True, indent=2) + '\n').encode()).hexdigest() == '807e292ca7079e976a1c5d1137e66e15f3650e6781417d8d58c49b79826e3373'
