import hashlib
import math

import pytest

from iatonoesis.mondo_temporal import (
    parse_obo, transition, candidates, features, ranking_metrics, fit,
    rank, review_frontier, calibrated, verify_source, run,
)


def ontology(edges, labels=None):
    labels = labels or {i: f'disease {i}' for i in range(1, 8)}
    return {f'MONDO:{i:07d}': {'name': name, 'parents': {f'MONDO:{p:07d}' for c, p in edges if c == i}} for i, name in labels.items()}


def key(i):
    return f'MONDO:{i:07d}'


def test_parse_and_verify_published_bytes(tmp_path):
    raw = b'format-version: 1.2\ndata-version: releases/2026-02-03\n\n[Term]\nid: MONDO:0000001\nname: root\n\n[Term]\nid: MONDO:0000002\nname: child\nis_a: MONDO:0000001 ! root\nis_a: HP:0000001\n\n[Term]\nid: MONDO:0000003\nname: obsolete\nis_obsolete: true\n'
    p = tmp_path / 'source.obo'; p.write_bytes(raw)
    verify_source(p, len(raw), hashlib.sha256(raw).hexdigest())
    nodes = parse_obo(p, '2026-02-03')
    assert set(nodes) == {key(1), key(2)} and nodes[key(2)]['parents'] == {key(1)}
    with pytest.raises(ValueError, match='version'):
        parse_obo(p, 'wrong')
    with pytest.raises(ValueError, match='integrity'):
        verify_source(p, len(raw), '0' * 64)
    p.write_bytes(raw + b'\n[Term]\nid: MONDO:0000001\nname: duplicate\n')
    with pytest.raises(ValueError, match='duplicate'):
        parse_obo(p, '2026-02-03')


def test_transition_and_history_only_candidate_pool():
    old = ontology([(2, 1), (3, 1), (4, 2), (5, 4)])
    new = ontology([(2, 1), (3, 1), (4, 2), (5, 4), (2, 3), (2, 6)])
    rows, stats = transition(old, new, 'test', 8)
    assert stats['eligible_edges'] == 2 and rows[0]['gold'] == [key(3), key(6)]
    pool = candidates(old, key(2), 'test', 8)
    assert pool == rows[0]['pool'] and key(1) not in pool and key(4) not in pool and key(5) not in pool and key(2) not in pool
    assert all(len(f) == 8 for f in rows[0]['features'])
    assert all(math.isfinite(x) for f in rows[0]['features'] for x in f)
    assert candidates(old, key(2), 'test', 8) == pool


def test_metrics_keep_pool_misses_and_review_cost():
    rows = [{'child':'a','gold':['x','y'],'pool':['x','z']}, {'child':'b','gold':['q'],'pool':['z']}]
    scores = [[.9,.1],[.8]]
    m = ranking_metrics(rows, scores)
    assert m['gold_edges'] == 3 and m['pool_hits'] == 1 and m['recall_at_1'] == pytest.approx(1/3)
    assert m['top1_confirmed'] == 1 and m['mrr'] == .5
    assert review_frontier(rows, scores, .5)['reviewed_queries'] == 1
    assert calibrated(rows, scores, rows, scores, min_count=20)['threshold'] is None


def test_trained_pair_scorers_reproduce_and_rank():
    rows = [{'child':'a','gold':['p'],'pool':['p','n'], 'features':[[1.]*8,[0.]*8]}]
    for arm in ('linear','neural','no_graph'):
        model = fit(rows, arm, epochs=8)
        assert model == fit(rows, arm, epochs=8)
        s = rank(rows, arm, model)[0]
        assert s[0] > s[1]
    with pytest.raises(ValueError, match='no retrieved'):
        fit([dict(rows[0],gold=['missing'])], 'linear')


def test_four_snapshot_replay_and_input_validation():
    labels = {i: f'condition group {i}' for i in range(1, 9)}
    old = ontology([(i, 1) for i in range(2,9)], labels)
    dev = ontology([(i, 1) for i in range(2,9)] + [(2,3)], labels)
    cal = ontology([(i, 1) for i in range(2,9)] + [(2,3),(4,5)], labels)
    test = ontology([(i, 1) for i in range(2,9)] + [(2,3),(4,5),(6,7)], labels)
    out = run([old,dev,cal,test], epochs=2, pool_size=8)
    assert out['scope'] == 'published_assertion_prediction_not_clinical_truth'
    assert out['partitions']['test']['queries'] == 1 and out['partitions']['test']['eligible_edges'] == 1
    assert set(out['arms']) == {'lexical','topology','hybrid_rule','linear','neural','no_graph'}
    assert out['test_seen_development_children'] == 0
    with pytest.raises(ValueError, match='four'):
        run([old,dev,cal])


def test_acquire_and_cli(monkeypatch,tmp_path):
    import io
    import json
    import sys
    from iatonoesis import mondo_temporal as m

    raw=b'fixture'
    pins={str(i):(len(raw),hashlib.sha256(raw).hexdigest()) for i in range(4)}
    monkeypatch.setattr(m,'PINS',pins)
    monkeypatch.setattr(m.urllib.request,'urlopen',lambda url,timeout: io.BytesIO(raw))
    assert m.acquire('0',tmp_path/'source')['bytes']==len(raw)
    monkeypatch.setattr(m.urllib.request,'urlopen',lambda url,timeout: io.BytesIO(raw+b'x'))
    with pytest.raises(ValueError,match='exceeds'):
        m.acquire('0',tmp_path/'source')
    monkeypatch.setattr(m.urllib.request,'urlopen',lambda url,timeout: io.BytesIO(raw))
    monkeypatch.setattr(m,'parse_obo',lambda p,v: {'version':v})
    monkeypatch.setattr(m,'run',lambda s: {'versions':[x['version'] for x in s]})
    dest=tmp_path/'result.json'
    monkeypatch.setattr(sys,'argv',['mondo_temporal','--output',str(dest)])
    m.main()
    result=json.loads(dest.read_text())
    assert result['versions']==list(pins) and result['licence']=='CC-BY-4.0'
    monkeypatch.setattr(m.urllib.request,'urlopen',lambda url,timeout: io.BytesIO(raw+b'x'))
    with pytest.raises(SystemExit):
        m.main()
    assert json.loads(dest.read_text())=={'status':'failed','error_type':'ValueError'}


def test_calibration_uses_calibration_only_and_empty_candidates():
    rows=[{'child':str(i),'gold':['p'],'pool':['p','q']} for i in range(30)]
    scores=[[1.,0.]]*30
    m=calibrated(rows,scores,rows,[[0.,1.]]*30)
    assert m['threshold']==1. and m['calibration_retained']==30 and m['unconfirmed']==30
    empty=[{'child':'a','gold':['p'],'pool':[]}]
    assert ranking_metrics(empty,[[]])['pool_recall']==0
    with pytest.raises(ValueError,match='scores'):
        ranking_metrics(empty,[[1.]])
    with pytest.raises(ValueError,match='review fraction'):
        review_frontier(empty,[[]],2)
    with pytest.raises(ValueError,match='empty evaluation'):
        ranking_metrics([],[])
    with pytest.raises(ValueError,match='candidate cap'):
        candidates(ontology([]),key(1),'test',0)
    with pytest.raises(ValueError,match='unknown arm'):
        rank([], 'missing')
    with pytest.raises(ValueError,match='invalid model'):
        fit([], 'missing')
