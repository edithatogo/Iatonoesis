import pytest
from iatonoesis.scifact_frontier import frontier, audit


def row(i, label, pred, conf):
    return dict(id=str(i), label=label, predictions={'m':[pred,conf]})


def test_tied_scores_cannot_be_split_and_minimum_is_enforced():
    rows=[row(1,'SUPPORT','SUPPORT',.9),row(2,'NO_EVIDENCE','SUPPORT',.9),row(3,'NO_EVIDENCE','NO_EVIDENCE',.8)]
    assert frontier(rows,'m',max_error=.2,min_retained=1,min_negative=0,max_false_support=1)['status']=='no_feasible_prefix'
    assert frontier(rows,'m',max_error=.4,min_retained=3,min_negative=1,max_false_support=.5)['retained']==3


def test_joint_safety_gate_and_invalid_predictions():
    rows=[row(1,'NO_EVIDENCE','NO_EVIDENCE',.95),row(2,'SUPPORT','SUPPORT',.8),row(3,'CONTRADICT','SUPPORT',.6)]
    got=frontier(rows,'m',max_error=.5,min_retained=1,min_negative=1,max_false_support=0)
    assert got['retained']==2 and got['review']==1 and got['false_support']==0
    with pytest.raises(ValueError,match='prediction'):
        frontier([row(1,'SUPPORT','invalid',.9)],'m',max_error=.2,min_retained=1,min_negative=0,max_false_support=1)


def test_bad_source_is_rejected(tmp_path):
    p=tmp_path/'bad.zip'; p.write_bytes(b'wrong')
    with pytest.raises(ValueError,match='artifact'):
        audit(p)


def test_audit_synthetic_envelope_and_cli(monkeypatch, tmp_path):
    import hashlib
    import json
    import sys
    import zipfile
    from iatonoesis import scifact_frontier as f

    rows=[]
    for i in range(339):
        label='SUPPORT' if i%2 else 'NO_EVIDENCE'
        rows.append(dict(id=f'{i}:1',label=label,predictions={m:[label,.8] for m in f.MODELS},ranks={'bm25':1.,'pretrained':1.}))
    expected={r+'_'+m:dict(correct=339,false_support=0,claims=339) for r in ('bm25','pretrained_reranker') for m in f.MODELS}
    payload=dict(predictions=rows,pipeline=expected,timing={})
    p=tmp_path/'fixture.zip'
    raw=json.dumps(payload).encode()
    with zipfile.ZipFile(p,'w') as z:
        z.writestr('result.json',raw)
    monkeypatch.setattr(f,'ZIP_SHA',hashlib.sha256(p.read_bytes()).hexdigest())
    monkeypatch.setattr(f,'RESULT_SHA',hashlib.sha256(raw).hexdigest())
    monkeypatch.setattr(f,'PREDICTIONS_SHA',f.digest(rows))
    got=f.audit(p)
    assert got['frontiers']['0.1']['rules']['retained']==339
    assert got['ranker_substitution']==dict.fromkeys(f.MODELS,0)
    out=tmp_path/'out.json'
    monkeypatch.setattr(sys,'argv',['audit','--artifact',str(p),'--output',str(out)])
    f.main()
    assert json.loads(out.read_text())==got
    monkeypatch.setattr(f,'PREDICTIONS_SHA','0'*64)
    with pytest.raises(ValueError,match='prediction digest'):
        f.audit(p)
    monkeypatch.setattr(f,'RESULT_SHA','0'*64)
    with pytest.raises(ValueError,match='result hash'):
        f.audit(p)
    expected['bm25_rules']['correct']=338
    with pytest.raises(ValueError,match='replay mismatch'):
        f.interactions(rows,expected)


def test_invalid_risk_bounds():
    with pytest.raises(ValueError,match='risk limits'):
        frontier([], 'm',max_error=-1,min_retained=1,min_negative=0,max_false_support=1)
