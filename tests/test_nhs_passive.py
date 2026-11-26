import pytest
from iatonoesis import nhs_passive as n


def raw(rows):return ('Organisation_Code,Sector,Number_Of_Beds,Effective_Snapshot_Date\n'+'\n'.join(','.join(r) for r in rows)+'\n').encode()


def test_join_keeps_unmatched_suppressed_and_inconsistent_counts():
    a=raw([('R01','Acute','100','2020-03-31'),('R01','Acute','100','2020-06-30'),('R01','Acute','100','2020-09-30'),('R02','Acute','10','2020-03-31')])
    o=raw([('R01','Acute','80','31/03/2020'),('R01','Acute','*','2020-06-30'),('R01','Acute','110','2020-09-30')])
    series,audit=n.join(a,o)
    assert audit['matched_keys']==3 and audit['available_only']==1
    assert audit['missing_pairs']==1 and audit['occupied_exceeds_available']==1
    assert len(series['R01','Acute'])==1
    with pytest.raises(ValueError,match='duplicate'):n.parse(raw([('R01','Acute','1','2020-03-31')]*2))


def test_contiguous_history_and_time_partitions():
    series={('R01','Acute'):{q:(100.,80.) for q in range(2020*4,2026*4)}}
    rows=n.examples(series)
    assert len(rows)==20 and all(len(r['features'])==11 for r in rows)
    assert {r['split'] for r in rows}<={'development','calibration','later_time','heldout_org'}
    assert all(r['target']==[1.,.8] for r in rows)
    del series['R01','Acute'][2023*4];assert len(n.examples(series))==15


def test_model_and_benchmark_are_deterministic():
    rows=[]
    for i in range(100):
        x=[1.,*([1.,.8]*4),0.,1.]
        rows.append(dict(features=x,target=[1.,.8],scale=100.,split='development' if i<80 else 'later_time'))
    a=n.fit(rows[:80],8);assert a==n.fit(rows[:80],8)
    result=n.evaluate(rows);assert result['later_time']['n']==20
    assert result['later_time']['arms']['last']['scaled_mae']==0
    assert result['heldout_org'] is None
    with pytest.raises(ValueError):n.fit(rows[80:],8)


def test_source_pins_and_cli(monkeypatch,tmp_path):
    import hashlib,io,json,sys
    with pytest.raises(ValueError,match='date'):n.quarter('unknown')
    monkeypatch.setattr(n,'PINS',{'Available':(3,hashlib.sha256(b'abc').hexdigest())})
    monkeypatch.setattr(n,'urlopen',lambda *a,**k:io.BytesIO(b'abc'))
    assert n.acquire('Available')==b'abc'
    monkeypatch.setattr(n,'urlopen',lambda *a,**k:io.BytesIO(b'bad'))
    with pytest.raises(ValueError,match='changed'):n.acquire('Available')
    target=tmp_path/'r.json';monkeypatch.setattr(sys,'argv',['nhs','--output',str(target),'--revision','a'*40])
    monkeypatch.setattr(n,'acquire',lambda _:b'fixture')
    monkeypatch.setattr(n,'join',lambda *_:({}, {'usable_pairs':1}))
    monkeypatch.setattr(n,'examples',lambda _:[])
    monkeypatch.setattr(n,'evaluate',lambda _:dict(development=1))
    n.main();assert json.loads(target.read_text())['scope']=='passive_source_trajectory_forecast_only'
    def fail(_):raise ValueError('private row')
    monkeypatch.setattr(n,'acquire',fail)
    with pytest.raises(SystemExit):n.main()
    assert json.loads(target.read_text())=={'status':'failed','stage':'acquisition','error_type':'ValueError'}
