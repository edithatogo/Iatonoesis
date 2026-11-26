import pytest
from iatonoesis.scifact_pipeline import freeze, paired_budget, fallback_gate, pipeline, features


def claim(i, docs, evidence):
    return dict(id=i, claim=f'Claim {i}', cited_doc_ids=docs, evidence={str(d): [{'label': l, 'sentences': [0]}] for d,l in evidence})


def test_group_freeze_removes_train_overlap_and_keeps_dev():
    train = [claim(1,[1,2],[(1,'SUPPORT')]),claim(2,[2,3],[]),claim(3,[4],[]),claim(4,[5],[]),claim(5,[6],[])]
    dev = [claim(6,[3,7],[(3,'CONTRADICT')])]
    result = freeze(train,dev,{i:['Abstract.'] for i in range(1,8)})
    assert result['excluded_train_claims'] == 2
    assert len(result['partitions']['test']) == 2
    assert {r['label'] for r in result['partitions']['test']} == {'CONTRADICT','NO_EVIDENCE'}
    assert all(r['claim_id'] not in {1,2} for p in ('development','calibration') for r in result['partitions'][p])
    assert result == freeze(train[::-1],dev,{i:['Abstract.'] for i in range(1,8)})


def test_conflicting_labels_rejected():
    bad = claim(1,[1],[(1,'SUPPORT')]); bad['evidence']['1'].append({'label':'CONTRADICT','sentences':[0]})
    with pytest.raises(ValueError,match='conflicting'):
        freeze([bad],[],{1:['a']})


def test_matched_budget_and_fallback():
    rows=[dict(id=str(i),label='SUPPORT' if i%2 else 'CONTRADICT') for i in range(10)]
    pred={r['id']:('SUPPORT',i/10) for i,r in enumerate(rows)}
    p=paired_budget(rows,pred,5)
    assert p['retained']==5 and p['review']==5 and p['correct']==3
    assert fallback_gate([(0.99,True)]*5) is None
    assert fallback_gate([(0.99,True)]*100)==0.5
    assert fallback_gate([(0.99,False)]*100) is None


def test_pipeline_crossed_selection():
    rows=[dict(id='a',claim_id=1,label='SUPPORT'),dict(id='b',claim_id=1,label='NO_EVIDENCE'),dict(id='c',claim_id=2,label='NO_EVIDENCE')]
    pred={'a':('SUPPORT',0.9),'b':('NO_EVIDENCE',0.9),'c':('NO_EVIDENCE',0.9)}
    assert pipeline(rows,{'a':2,'b':1,'c':1},pred)['correct']==2
    wrong=pipeline(rows,{'a':1,'b':2,'c':1},pred)
    assert wrong['correct']==1 and wrong['retrieved_evidence']==0
    assert len(features('A has no effect','A has an effect'))==8


def test_deterministic_is_conservative_and_budget_validation():
    from iatonoesis.scifact_pipeline import deterministic
    rows=[dict(id='a',abstract='The effect is 3.',claim='The effect is 3.'),dict(id='b',abstract='The effect is 3.',claim='The effect is not 3.')]
    p=deterministic(rows)
    assert p['a'][0]=='SUPPORT' and p['b'][0]=='NO_EVIDENCE'
    with pytest.raises(ValueError,match='budget'):
        paired_budget([dict(id='a',label='SUPPORT')],p,1)


def test_archive_integrity_and_safe_members(tmp_path,monkeypatch):
    import hashlib, io, json, tarfile
    from iatonoesis import scifact_pipeline as s
    payloads={'data/corpus.jsonl':json.dumps(dict(doc_id=1,abstract=['text']))+'\n',
              'data/claims_train.jsonl':json.dumps(claim(1,[1],[]))+'\n',
              'data/claims_dev.jsonl':json.dumps(claim(2,[1],[]))+'\n'}
    def archive(files):
        buf=io.BytesIO()
        with tarfile.open(fileobj=buf,mode='w:gz') as stream:
            for name,content in files.items():
                data=content.encode(); item=tarfile.TarInfo(name); item.size=len(data)
                stream.addfile(item,io.BytesIO(data))
        raw=buf.getvalue()
        monkeypatch.setattr(s,'SOURCE_BYTES',len(raw)); monkeypatch.setattr(s,'SOURCE_SHA256',hashlib.sha256(raw).hexdigest())
        return raw
    raw=archive(payloads)
    assert s.read_release(raw)[2]=={1:['text']}
    with pytest.raises(ValueError,match='checksum'):
        s.read_release(raw+b'x')
    with pytest.raises(ValueError,match='unsafe'):
        s.read_release(archive(payloads|{'../bad':'x'}))
    with pytest.raises(ValueError,match='missing'):
        s.read_release(archive({'data/corpus.jsonl':payloads['data/corpus.jsonl']}))
