import io
import tarfile
import json
import pytest
from iatonoesis import physionet2012 as p


def record(i, offset=0, observed=True):
    return (f'Time,Parameter,Value\n00:00,RecordID,{i}\n00:00,ICUType,3\n'
            f'00:10,HR,{70+offset}\n01:30,HR,{72+offset}\n01:35,HR,{73+offset}\n'
            '02:00,MAP,65\n03:00,HR,-1\n05:30,RespRate,18\n'
            + (f'06:00,HR,{80+offset}\n08:10,HR,{82+offset}\n11:05,HR,{84+offset}\n' if observed else '')).encode()


def archive(records):
    stream=io.BytesIO()
    with tarfile.open(fileobj=stream,mode='w:gz') as tar:
        for name,raw in records:
            info=tarfile.TarInfo(name);info.size=len(raw);tar.addfile(info,io.BytesIO(raw))
    return stream.getvalue()


def test_timestamp_and_observed_targets_are_strictly_after_history():
    r=p.parse(record('100001'), '100001')
    assert r['history']==[70.,73.,None,None,None,None]
    assert r['targets']=={'1':80.,'3':82.,'6':84.} and r['observed']==1
    assert r['icu']=='3' and r['count']==2
    assert p.parse(record('100001',observed=False),'100001')['observed']==0
    assert p.parse(record('100001').replace(b'06:00,HR,80',b'06:00,HR,999'),'100001')['history']==r['history']
    for bad in [b'bad',record('100002'),record('100001').replace(b'01:30',b'55:00'),record('100001').replace(b'01:30,HR,72',b'01:30,HR,nan')]:
        with pytest.raises(ValueError):p.parse(bad,'100001')


def test_archive_rejects_traversal_duplicate_identity_and_count():
    good=archive([('set-a/100001.txt',record('100001'))])
    assert len(p.unpack(good,'A',1))==1
    for bad in [archive([('../100001.txt',record('100001'))]),archive([('100001.txt',record('100001')),('100001.txt',record('100001'))])]:
        with pytest.raises(ValueError):p.unpack(bad,'A',1)
    with pytest.raises(ValueError):p.unpack(good,'A',2)


def test_freeze_rejects_cross_partition_content_duplicates_and_ids():
    a=archive([('100001.txt',record('100001'))]);b=archive([('200001.txt',record('200001',offset=1))])
    f=p.freeze({'A':a,'B':b},1)
    assert f['counts']['B']['records']==1 and len(f['manifest_sha256'])==64
    assert f['rows'][1]['split']=='test'
    with pytest.raises(ValueError,match='overlap'):p.freeze({'A':a,'B':a},1)
    with pytest.raises(ValueError,match='overlap'):p.freeze({'A':a,'B':archive([('200001.txt',record('200001'))])},1)


def test_observation_model_learns_and_returns_aggregate_only():
    rows=[]
    for i in range(40):
        r=p.parse(record(str(100000+i),i,observed=i%2==0),str(100000+i));r.update(split='development' if i<20 else 'test')
        if i%2: r['history']=[None]*6;r['count']=0
        rows.append(r)
    assert p.observation_features(rows[1],False)[1:3]==[0.,1.]
    out=p.observation_benchmark(rows)
    assert out['n']==20 and out['arms']['timing_logistic']['brier']<out['arms']['prevalence']['brier']
    assert 'history' not in json.dumps(out) and 'targets' not in json.dumps(out)
    with pytest.raises(ValueError):p.observation_benchmark(rows[:20])


def test_acquire_size_and_cli_receipts(monkeypatch,tmp_path):
    import sys
    monkeypatch.setattr(p,'urlopen',lambda *a,**k:io.BytesIO(b'abc'))
    monkeypatch.setattr(p,'SIZES',{'A':3,'B':4})
    assert p.acquire('A')==b'abc'
    with pytest.raises(ValueError,match='length'):p.acquire('B')
    out=tmp_path/'result.json'
    monkeypatch.setattr(sys,'argv',['p12','--output',str(out),'--revision','a'*40])
    monkeypatch.setattr(p,'acquire',lambda c:b'x')
    monkeypatch.setattr(p,'freeze',lambda _:dict(rows=[],counts={'A':{'records':4000}},manifest_sha256='b'*64))
    monkeypatch.setattr(p,'observation_benchmark',lambda _:dict(n=4000))
    p.main();r=json.loads(out.read_text());assert r['observation']['n']==4000
    def fail(_):raise ValueError('sensitive record identity')
    monkeypatch.setattr(p,'freeze',fail)
    with pytest.raises(SystemExit):p.main()
    assert json.loads(out.read_text())=={'status':'failed','error_type':'ValueError','stage':'source_freeze','reason':'unclassified','scope':'aggregate_only'}


def test_diagnostic_reasons_are_allowlisted_not_arbitrary_exception_messages():
    assert p.failure_reason(ValueError('archive record count mismatch'))=='archive record count mismatch'
    assert p.failure_reason(ValueError('record identity 100001'))=='unclassified'
    assert p.failure_reason(RuntimeError('invalid header'))=='unclassified'
