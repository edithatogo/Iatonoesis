import copy
import hashlib
import json
import sys

import pytest
from iatonoesis import state_heterogeneity as m


def stratum(n, delta):
    return {'n': n, 'arms': {'last': {'mae': 5}, 'ridge': {'mae': 5+delta}},
            'paired': {'ridge': {'n': n, 'difference': delta}}}


def test_common_support_equal_source_weights_not_pooled_counts():
    a={'all':stratum(100,1), 'recency_0':stratum(90,1), 'recency_1_2':stratum(10,3), 'recency_3_plus':stratum(0,0)}
    b={'all':stratum(1000,0), 'recency_0':stratum(500,-1), 'recency_1_2':stratum(400,1), 'recency_3_plus':stratum(100,2)}
    r=m.standardize({'2019':a,'2012':b}, 'recency_')
    assert r['counts']=={'2019':100,'2012':900}
    assert r['weights']['recency_0']==pytest.approx((.9+5/9)/2)
    assert r['standardized']['2019']==pytest.approx(r['weights']['recency_0']+3*r['weights']['recency_1_2'])
    assert r['contrast_2019_minus_2012']==pytest.approx(r['standardized']['2019']-r['standardized']['2012'])
    assert 'recency_3_plus' not in r['weights']


def test_sparse_and_suppressed_support_is_not_recovered():
    a={'all':stratum(25,1), 'missing_0':stratum(5,1), 'missing_1_2':stratum(20,2), 'missing_3_plus':stratum(0,0)}
    b=copy.deepcopy(a)
    b['missing_1_2']['arms']=None
    assert m.standardize({'2019':a,'2012':b},'missing_') is None
    b['missing_1_2']=stratum(20,-1)
    assert m.standardize({'2019':a,'2012':b},'missing_')['counts']=={'2019':20,'2012':20}


def test_inconsistent_paired_delta_rejected():
    s=stratum(10,1);s['paired']['ridge']['difference']=2
    with pytest.raises(ValueError,match='paired'):m.delta(s)
    s=stratum(10,1);s['paired']['ridge']['n']=9
    with pytest.raises(ValueError,match='paired'):m.delta(s)


def fixture():
    v={}
    for name in m.ARMS:
        err=5 if name=='last' else 6
        v[name]=dict(n=30,mae=err,mse=err**2,rmse=err,interval_n=30,interval_covered=27,interval_coverage=.9,interval_width=20)
    s=dict(n=30,arms=v,paired={a:dict(n=30,difference=v[a]['mae']-5,lower=-1,upper=2) for a in m.ARMS if a!='last'})
    group=dict(counts={'test':30},receipt={'metric_kind':'continuous','primary_metric':'mae','claim_boundary':'benchmark_only','arms':[dict(id=a,status='executed',metrics=dict(total=30,scored=30,abstained=0,**v[a])) for a in m.ARMS]},strata={'all':s})
    for prefix in ('missing_','recency_'):
        for suffix in ('0','1_2','3_plus'):
            small=copy.deepcopy(s);small['n']=10
            for metrics in small['arms'].values():metrics.update(n=10,interval_n=10,interval_covered=9)
            for metrics in small['paired'].values():metrics['n']=10
            group['strata'][prefix+suffix]=small
    return group


def test_validate_and_reject_denominator_and_conservation():
    group=fixture();assert m.validate(group)['all']['n']==30
    for edit in (lambda v:v['receipt']['arms'][0]['metrics'].update(scored=29),lambda v:v['strata']['missing_0'].update(n=11),lambda v:v['strata']['missing_0']['arms']['last'].update(mae=7),lambda v:v['receipt']['arms'][0]['metrics'].update(mse=100)):
        bad=copy.deepcopy(group);edit(bad)
        with pytest.raises(ValueError):m.validate(bad)
    group['strata']['missing_0']['arms']=None
    assert m.validate(group)['all']['n']==30


def test_exact_digest_binding_and_cli(tmp_path, monkeypatch):
    payloads={d:json.dumps(dict(source_manifest_sha256=p['manifest'],**{p['key']:{str(h):fixture() for h in m.HORIZONS}})).encode() for d,p in m.PINS.items()}
    monkeypatch.setattr(m,'PINS',{d:dict(p,sha256=hashlib.sha256(payloads[d]).hexdigest()) for d,p in m.PINS.items()})
    out=m.analyze(payloads)
    assert out['windows']['3']['2012']['best_mae']==['last']
    assert out['windows']['3']['recency']['contrast_2019_minus_2012']==0
    with pytest.raises(ValueError,match='digest'):m.analyze(dict(payloads,**{'2019':b'changed'}))
    p=tmp_path/'a.json';q=tmp_path/'b.json';z=tmp_path/'result.json';p.write_bytes(payloads['2019']);q.write_bytes(payloads['2012'])
    monkeypatch.setattr(sys,'argv',['state','--p2019',str(p),'--p2012',str(q),'--output',str(z)])
    m.main();assert json.loads(z.read_text())==out


def test_validate_rejects_nonexecuted_and_invalid_metrics():
    for edit in (lambda v:v['counts'].update(test=9), lambda v:v['receipt']['arms'].pop(),
                 lambda v:v['strata']['all']['arms']['last'].update(interval_n=29),
                 lambda v:v['strata']['missing_0']['arms']['last'].update(n=9)):
        bad=fixture();edit(bad)
        with pytest.raises(ValueError):m.validate(bad)


def test_reject_source_manifest_even_with_matching_digest(monkeypatch):
    raw=b'{"source_manifest_sha256":"wrong"}'
    monkeypatch.setattr(m,'PINS',{'2019':dict(m.PINS['2019'],sha256=hashlib.sha256(raw).hexdigest())})
    with pytest.raises(ValueError,match='manifest'):m.analyze({'2019':raw})
