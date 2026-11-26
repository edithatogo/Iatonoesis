import json
import math
import pytest
from iatonoesis import physionet_audit as source
from iatonoesis import measured_pilot as m


def psv(offset, missing_aux=False):
    lines=['|'.join(source.HEADER)]
    for t in range(1,11):
        row=['1']*len(source.HEADER)
        vals={'ICULOS':t,'HR':70+offset+t,'MAP':65+offset,'Resp':16+offset%4,'O2Sat':97-offset%3,'SepsisLabel':0}
        if t==7 and missing_aux: vals['MAP']='NaN'
        if t==5: vals['HR']='NaN'
        for k,v in vals.items(): row[source.HEADER.index(k)]=str(v)
        lines.append('|'.join(row))
    return ('\n'.join(lines)+'\n').encode()


def test_reference_cutoff_no_future_or_label_and_distinct_eligibility():
    raw=psv(0,True)
    state=m.case(raw,False); acq=m.case(raw,True)
    assert state['cutoff']==7 and state['target']==77 and state['history']==[71.,72.,73.,74.,None,76.]
    assert 'aux' not in state and acq['cutoff']==8 and acq['target']==78
    assert acq['aux']==[65.,16.,97.]
    # Alter only future HR/label and prove earlier state extraction remains identical.
    lines=raw.decode().splitlines();v=lines[-1].split('|');v[0]='999';v[-1]='1';lines[-1]='|'.join(v)
    assert m.case(('\n'.join(lines)+'\n').encode(),False)==state


def fixture():
    # Find deterministic keys in both A splits; all generated rows distinct.
    groups={'A':[],'B':[]};records={}
    seen={'development':0,'calibration':0,'test':0}
    for i in range(200):
        c='A' if i<100 else 'B';k=f'p{i:06}.psv';part=source.partition(c,k)
        if seen[part]>=12: continue
        seen[part]+=1;groups[c].append(k);records[c,k]=psv(i%37+i/100,i%4==0)
    return groups,records


def test_freeze_is_deterministic_and_fails_on_source_change_or_duplicate():
    groups,records=fixture()
    a=m.freeze(groups,lambda c,k:records[c,k],expected_counts={c:len(v) for c,v in groups.items()},sample_counts={c:len(v) for c,v in groups.items()})
    b=m.freeze({c:list(reversed(v)) for c,v in groups.items()},lambda c,k:records[c,k],expected_counts={c:len(v) for c,v in groups.items()},sample_counts={c:len(v) for c,v in groups.items()},expected_manifest=a['source_manifest_sha256'])
    assert a==b
    with pytest.raises(ValueError,match='manifest'):
        m.freeze(groups,lambda c,k:records[c,k],expected_counts={c:len(v) for c,v in groups.items()},sample_counts={c:len(v) for c,v in groups.items()},expected_manifest='0'*64)
    with pytest.raises(ValueError,match='duplicate'):
        m.freeze(groups,lambda c,k:psv(0),expected_counts={c:len(v) for c,v in groups.items()},sample_counts={c:len(v) for c,v in groups.items()})


def test_state_and_acquisition_benchmark_receipt():
    groups,records=fixture();counts={c:len(v) for c,v in groups.items()}
    data=m.freeze(groups,lambda c,k:records[c,k],expected_counts=counts,sample_counts=counts)
    result=m.evaluate(data,'a'*40,synthetic=True)
    assert result['scope']=='synthetic_fixture' and result['source_manifest_sha256']==data['source_manifest_sha256']
    assert set(result['state']['arms'])=={'mean','last','ar1','kalman','ridge','temporal_mlp'}
    assert all(a['status']=='executed' for a in result['state']['arms'].values())
    for budget,arms in result['acquisition'].items():
        assert set(arms)=={'fixed','greedy','context'}
        assert all(a['status']=='executed' for a in arms.values())
    full=result['acquisition']['3'];assert len({a['metrics']['mse'] for a in full.values()})==1
    assert all(a['metrics']['scored']==12 for a in result['state']['arms'].values())
    text=json.dumps(result);assert 'p000' not in text and 'predictions"' not in text and 'history' not in text


def test_fit_gates_and_invalid_parameters():
    with pytest.raises(ValueError,match='development'):
        m.fit_state([{'split':'test'}])
    with pytest.raises(ValueError,match='budget'):
        m.acquire({'history':[70]*6,'aux':[1,2,3]},None,None,None,4)
    with pytest.raises(ValueError,match='source'):
        m.evaluate({'source_manifest_sha256':'0'*64},'a'*40)


def test_cli_failure_receipt_is_aggregate_only(tmp_path,monkeypatch):
    import sys
    path=tmp_path/'result.json'
    monkeypatch.setattr(sys,'argv',['measured','--revision','a'*40,'--output',str(path)])
    def fail(_): raise RuntimeError('private source identifier')
    monkeypatch.setattr(source,'inventory',fail)
    with pytest.raises(SystemExit) as exc: m.main()
    assert exc.value.code==1
    record=json.loads(path.read_text())
    assert record['status']=='failed' and record['reason']=='RuntimeError'
    assert 'private source identifier' not in path.read_text()


def test_bad_inventory_counts_and_cohort_overlap():
    with pytest.raises(ValueError,match='overlap'):
        m.freeze({'A':['p000001.psv'],'B':['p000001.psv']},lambda *_:psv(0),expected_counts={'A':1,'B':1},sample_counts={'A':1,'B':1})
    with pytest.raises(ValueError,match='count mismatch'):
        m.freeze({'A':['p000001.psv'],'B':['p100001.psv']},lambda *_:psv(0),expected_counts={'A':2,'B':1},sample_counts={'A':1,'B':1})
