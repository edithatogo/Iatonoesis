import pytest
from iatonoesis import physionet2012_grouped as g
from test_physionet2012 import archive, record


def test_transitive_quarantine_and_order_independence():
    # Same identity joins A/B; same content joins another B record transitively.
    entries=[('A','100001','x'),('B','100001','y'),('B','200001','x'),('A','100002','z'),('B','200002','w')]
    a=g.quarantine(entries);b=g.quarantine(list(reversed(entries)))
    assert a==b
    assert a[0]=={('A','100001'),('B','100001'),('B','200001')}
    assert a[1]['identity_duplicate_groups']==1 and a[1]['content_duplicate_groups']==1
    assert a[1]['quarantined_records']==3 and a[1]['cross_cohort_components']==1
    assert a[1]['component_size_histogram']=={'1':2,'3':1}
    with pytest.raises(ValueError):g.quarantine(entries+entries[:1])


def test_grouped_freeze_preserves_cohort_and_redacts_manifest():
    a=archive([('100001.txt',record('100001')),('100002.txt',record('100002',2))])
    b=archive([('200001.txt',record('200001')),('200002.txt',record('200002',3))])
    f=g.freeze_grouped({'A':a,'B':b},expected=2)
    assert f['audit']['quarantined_records']==2 and len(f['rows'])==2
    assert f['counts']['A']['retained']==1 and f['counts']['B']['retained']==1
    assert len(f['manifest_sha256'])==64
    assert f['rows'][1]['split']=='test'
    assert '100001' not in str(f['audit'])


def test_marked_hazard_scores_and_risk():
    rows=[]
    for i in range(40):
        row=dict(id=str(i),split='development' if i<30 else 'test',history=[70.]*6 if i%2 else [None]*6,count=6 if i%2 else 0,aux_counts=[0]*4,mark_minutes=[[350] if i%2 else []]+[[]]*4,first_hr_minute=10 if i%2 else None)
        row['observed']=int(row['first_hr_minute'] is not None);rows.append(row)
    a=g.hazard_benchmark(rows);assert a['n']==10
    assert a['arms']['marked_exponential']['brier_180']<a['arms']['constant_exponential']['brier_180']
    for arm in a['arms'].values():
        assert all(0<=x<=1 for x in arm['mean_event_probability'])
        assert arm['mean_event_probability']==sorted(arm['mean_event_probability'])
    assert a==g.hazard_benchmark(rows)
    with pytest.raises(ValueError):g.hazard_benchmark(rows[:30])


def test_cli_receipt(monkeypatch,tmp_path):
    import sys,json
    target=tmp_path/'result.json'
    monkeypatch.setattr(sys,'argv',['grouped','--revision','a'*40,'--output',str(target)])
    monkeypatch.setattr(g.p,'acquire',lambda _:b'fixture')
    monkeypatch.setattr(g,'freeze_grouped',lambda _:dict(rows=[],counts={},audit={},manifest_sha256='b'*64))
    monkeypatch.setattr(g.p,'observation_benchmark',lambda _:dict(n=1))
    monkeypatch.setattr(g,'hazard_benchmark',lambda _:dict(n=1))
    g.main();assert json.loads(target.read_text())['hazard']['n']==1
    def fail(_):raise ValueError('record 100001')
    monkeypatch.setattr(g,'freeze_grouped',fail)
    with pytest.raises(SystemExit):g.main()
    assert json.loads(target.read_text())['reason']=='unclassified'
    assert '100001' not in target.read_text()
