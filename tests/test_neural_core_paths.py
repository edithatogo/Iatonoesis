"""Exercise the digest-bound core replay, all predictor paths and CLI."""
import copy
import json
import sys
from pathlib import Path

import pytest

from iatonoesis import neural_core as neural
from iatonoesis.run_contracts import canonical_sha256


ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / 'results/exploratory/core-family-suite-seed17.json'
REVISION = 'a2b494b027b01e46f84143817187f63f2baae1f9'


def test_fit_rejects_empty_vocabulary_and_single_label():
    with pytest.raises(ValueError, match='support'):
        neural.fit([((), 'a'), ((), 'b')], hidden=0, seed=17)
    with pytest.raises(ValueError, match='support'):
        neural.fit([(('a',), 'only')], hidden=16, seed=17)


def test_frozen_replay_rejects_modified_reference_digest():
    receipt = json.loads(RECEIPT.read_text())
    bad = copy.deepcopy(receipt)
    bad['tasks']['E02']['reference_sha256'] = '0' * 64
    with pytest.raises(ValueError, match='fixture digest mismatch'):
        neural.run_suite(REVISION, bad)


def test_full_cli_replay_uses_frozen_cases_and_validates_predictions(tmp_path, monkeypatch):
    output = tmp_path / 'result.json'
    monkeypatch.setattr(sys, 'argv', ['neural_core', '--revision', REVISION,
                                     '--receipt', str(RECEIPT), '--output', str(output)])
    neural.main()
    result = json.loads(output.read_text())
    assert result['scope'] == 'synthetic_posthoc_replay_only'
    assert result['source_commit'] == REVISION
    expected = {'E02': 48, 'E04': 100, 'E22': 75}
    assert set(result['tasks']) == set(expected)
    for key, n in expected.items():
        task = result['tasks'][key]
        arms = {a['id']: a for a in task['manifest']['arms']}
        assert set(arms) == {'rules', 'learned', 'linear', 'mlp'}
        assert set(task['predictions']) == set(arms)
        for arm, record in arms.items():
            assert record['status'] == 'executed'
            rows = task['predictions'][arm]
            assert len(rows) == n
            assert len({r['id'] for r in rows}) == n
            assert record['predictions_sha256'] == canonical_sha256(rows)
            assert record['metrics']['total'] == n
            assert [(r['id'], r['gold']) for r in rows] == [
                (r['id'], r['gold']) for r in task['predictions']['rules']]
        assert arms['linear']['model']['hidden'] == 0
        assert arms['mlp']['model']['hidden'] == neural.HIDDEN
        assert arms['linear']['model']['weights_sha256'] != arms['mlp']['model']['weights_sha256']
        assert set(task['paired_f1']) == {'learned', 'linear', 'mlp'}
    assert result['tasks']['E04']['safety']['rules']['active_cases_referred'] == 4
    assert result['tasks']['E22']['safety']['rules']['false_timely'] == 0
