"""Run in the full repository environment, using actual prior model/metric modules."""
import json

from iatonoesis import physionet2012_state as m


def test_all_frozen_arm_adapters_on_authored_values():
    rows=[]
    for split in m.SPLITS:
        for i in range(12):
            history=[70+i,71+i,None,73+i,74+i,75+i]
            rows.append(dict(id=split+str(i),split=split,history=history,target=76+i))
    out=m.evaluate_horizon(rows,'a'*40,3,synthetic=True)
    assert out['counts']==dict(development=12,calibration=12,test=12)
    assert {x['id'] for x in out['receipt']['arms']}=={'mean','last','ar1','kalman','ridge','temporal_mlp'}
    assert all(x['status']=='executed' and x['metrics']['total']==12 for x in out['receipt']['arms'])
    assert out['strata']['all']['n']==12
    assert 'test0' not in json.dumps(out) and 'predictions"' not in json.dumps(out)


def test_cli_freeze_and_actual_model_adapters_on_authored_values(monkeypatch,tmp_path):
    import hashlib
    import sys
    import pytest
    from iatonoesis import physionet2012, physionet2012_grouped
    archives={c:c.encode() for c in ('A','B')}
    monkeypatch.setattr(m,'ARCHIVES',{c:hashlib.sha256(v).hexdigest() for c,v in archives.items()})
    monkeypatch.setattr(m,'PARTITIONS',{'A':{'development':12,'calibration':12,'quarantine':1},'B':{'test':12,'quarantine':1}})
    monkeypatch.setattr(m,'ELIGIBLE',{'A':{str(h):24 for h in m.HORIZONS},'B':{str(h):12 for h in m.HORIZONS}})
    rows=[dict(id=p+str(i),split=p,history=[70+i,71+i,None,73+i,74+i,75+i],targets={str(h):76+i for h in m.HORIZONS}) for p in m.SPLITS for i in range(12)]
    counts={c:dict(archive_sha256=d,records=sum(m.PARTITIONS[c].values()),retained=sum(m.PARTITIONS[c].values())-1,partitions=m.PARTITIONS[c],eligible_observed_targets=m.ELIGIBLE[c]) for c,d in m.ARCHIVES.items()}
    frozen=dict(manifest_sha256=m.MANIFEST,counts=counts,audit=dict(quarantined_records=2,cross_cohort_components=1),rows=rows)
    monkeypatch.setattr(physionet2012,'acquire',archives.__getitem__)
    monkeypatch.setattr(physionet2012_grouped,'freeze_grouped',lambda _:frozen)
    output=tmp_path/'aggregate.json'
    monkeypatch.setattr(sys,'argv',['p12','--revision','a'*40,'--output',str(output)])
    m.main()
    report=json.loads(output.read_text())
    assert set(report['windows'])=={'1','3','6'}
    assert 'test0' not in output.read_text() and '"predictions"' not in output.read_text()
    monkeypatch.setattr(physionet2012,'acquire',lambda _:b'changed')
    with pytest.raises(SystemExit):m.main()
    assert json.loads(output.read_text())['stage']=='archive_acquisition'
