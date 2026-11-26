import pytest
from iatonoesis.temporal_information import generate, history_features, reveal_sequence, run, fit_models, select_action


def test_partitions_and_no_future_or_target_in_features():
    rows = generate()
    assert len(rows) == 880
    assert len({r['id'] for r in rows}) == len(rows)
    assert {r['split'] for r in rows} == {'development', 'calibration', 'test'}
    assert len([r for r in rows if r['split']=='test']) == 240
    r = rows[0]
    assert len(r['history']) == 6 and 'target' not in r['history'][0]
    f = history_features(r['history'], r['regime'], {})
    r['target'] += 10000
    r['aux'] = [10000, 20000, 30000]
    assert history_features(r['history'], r['regime'], {}) == f


def test_replay_does_not_reveal_future_candidates():
    seen = []
    def policy(history, regime, observed):
        assert len(observed) == len(seen)
        action = next(i for i in range(3) if i not in observed)
        seen.append(action)
        return action
    revealed = []
    def reveal(action):
        assert action == seen[-1]
        revealed.append(action)
        return float(action)
    traces = reveal_sequence([], 0, policy, reveal, 3)
    assert seen == revealed == [0, 1, 2]
    assert traces == [{}, {0: 0.}, {0: 0., 1: 1.}, {0: 0., 1: 1., 2: 2.}]
    with pytest.raises(ValueError, match='action'):
        reveal_sequence([], 0, lambda *_: 0, lambda _: 0., 2)


def test_fitting_rejects_non_development():
    rows = generate()
    with pytest.raises(ValueError, match='development'):
        fit_models([r for r in rows if r['split']=='test'])


def test_repeatable_matched_budget_and_metric_receipts():
    a = run()
    assert a == run()
    assert a['scope'] == 'synthetic_only'
    assert a['counts'] == {'development':480, 'calibration':160, 'test':240}
    assert len(a['state']['rows']) == 240
    assert len(a['acquisition']['rows']) == 240
    for row in a['acquisition']['rows']:
        for arm in ('fixed','regime_greedy','context_learned'):
            tr = row['arms'][arm]
            assert len(set(tr['actions'])) == 3 and len(tr['predictions']) == 4
        assert len({round(row['arms'][arm]['predictions'][3],12) for arm in row['arms']}) == 1
    for arm, metrics in a['state']['metrics'].items():
        assert metrics['all']['n'] == 240
        assert 0 <= metrics['all']['interval_coverage'] <= 1
    assert a['manifest']['inputs_sha256'] != a['manifest']['reference_sha256']
