import hashlib
import json

import pytest

from iatonoesis import bundle_cost as b


def source_fixture():
    def row(mse, count, name):
        return dict(id=name, status='executed', metrics=dict(total=6, scored=6, abstained=0, mse=mse)), dict(mean_observations=count, mean_spend=count)
    groups = {}
    for cap in (0, 3):
        rows, spend = [], {}
        for name in ('fixed', 'greedy', 'context', 'context_stop'):
            loss, count = (10, 0) if not cap else (9.9, 1.5) if name == 'context_stop' else (11, 3)
            arm, cost = row(loss, count, name)
            rows.append(arm)
            spend[name] = cost
        groups[str(cap)] = dict(costs=[1, 1, 1], receipt=dict(arms=rows), spend=spend)
    return dict(source_manifest_sha256=b.MANIFEST, acquisition_counts={'test': 6}, acquisition={'equal': groups})


def test_integer_incidence_bounds():
    assert b.incidence(6, 9) == (3, 6)
    assert b.incidence(6, 10) == (4, 6)
    assert b.incidence(6, 0) == (0, 0)
    assert b.incidence(6, 18) == (6, 6)
    for n, count in ((0, 1), (6, -1), (6, 19), (6, 1.1), (True, 1)):
        with pytest.raises(ValueError): b.incidence(n, count)


def test_counterfactual_time_is_bounded_not_divided_per_measurement(monkeypatch):
    source = source_fixture()
    raw = json.dumps(source).encode()
    monkeypatch.setattr(b, 'RAW_SHA', hashlib.sha256(raw).hexdigest())
    r = b.analyze(raw)
    assert r['population'] == 6
    assert r['full']['delta_mse'] == 1
    assert r['full']['dominated_on_point_estimates'] is True
    assert r['stop']['mse_reduction'] == pytest.approx(.1)
    assert r['stop']['bundle_count_bounds'] == [3, 6]
    s = next(x for x in r['scenarios'] if x['id']=='round')
    assert s['stop_mean_seconds_bounds'] == [150.5, 301]
    assert s['stop_break_even_loss_per_staff_minute_bounds'] == pytest.approx([.1*60/301, .1*60/150.5])
    assert len(r['context_only_geometric_means']) == 2
    assert r['paired_stop_vs_none'] is None


def test_reject_digest_denominator_and_bad_count(monkeypatch):
    with pytest.raises(ValueError, match='digest'): b.analyze(b'{}')
    source = source_fixture()
    def invoke():
        raw=json.dumps(source).encode()
        monkeypatch.setattr(b, 'RAW_SHA', hashlib.sha256(raw).hexdigest())
        return b.analyze(raw)
    source['acquisition']['equal']['3']['receipt']['arms'][0]['metrics']['total']=5
    with pytest.raises(ValueError, match='denominator'): invoke()
    source['acquisition']['equal']['3']['receipt']['arms'][0]['metrics']['total']=6
    source['acquisition']['equal']['3']['spend']['context_stop']['mean_observations']=1.51
    with pytest.raises(ValueError, match='count'): invoke()


def test_nonpositive_gain_has_no_positive_break_even(monkeypatch):
    s = source_fixture()
    s['acquisition']['equal']['3']['receipt']['arms'][-1]['metrics']['mse']=10.1
    raw=json.dumps(s).encode()
    monkeypatch.setattr(b, 'RAW_SHA', hashlib.sha256(raw).hexdigest())
    r=b.analyze(raw)
    assert all(x['stop_break_even_loss_per_staff_minute_bounds'] is None for x in r['scenarios'])


def test_binding_and_endpoint_failures(monkeypatch):
    def check(edit, reason):
        source = source_fixture()
        edit(source)
        raw = json.dumps(source).encode()
        monkeypatch.setattr(b, 'RAW_SHA', hashlib.sha256(raw).hexdigest())
        with pytest.raises(ValueError, match=reason): b.analyze(raw)
    check(lambda s:s.update(source_manifest_sha256='wrong'), 'manifest')
    check(lambda s:s['acquisition']['equal']['3'].update(costs=[1,2,1]), 'arms or budget')
    check(lambda s:s['acquisition']['equal']['3']['spend']['fixed'].update(mean_observations=2, mean_spend=2), 'forced')
    check(lambda s:s['acquisition']['equal']['3']['receipt']['arms'][0]['metrics'].update(mse=-1), 'loss or count')
    check(lambda s:s['acquisition']['equal']['3']['receipt']['arms'][0]['metrics'].update(mse=8), 'convergence')


def test_cli_keeps_exact_derived_receipt(monkeypatch, tmp_path):
    import sys
    raw=json.dumps(source_fixture()).encode()
    src, out=tmp_path/'source.json', tmp_path/'result.json'
    src.write_bytes(raw)
    monkeypatch.setattr(b, 'RAW_SHA', hashlib.sha256(raw).hexdigest())
    monkeypatch.setattr(sys, 'argv', ['bundle_cost','--source',str(src),'--output',str(out)])
    b.main()
    assert json.loads(out.read_text())==b.analyze(raw)
