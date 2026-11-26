import pytest
from iatonoesis.scifact_open import retrieve, proposal, evaluate, fallback, fit_gate


def test_open_retrieval_does_not_insert_gold_or_use_citations():
    corpus={1:['cold causes cough'],2:['unrelated text'],3:['cold cough result'],4:['fish study']}
    q={'id':7,'claim':'cold cough','evidence':{'4':[{'label':'SUPPORT','sentences':[0]}]},'cited_doc_ids':[4]}
    a=retrieve(corpus,[q],2)
    b=retrieve(corpus,[dict(q,evidence={'2':[]},cited_doc_ids=[2])],2)
    assert a==b and all(4 not in pool for pool in a[7].values())
    assert all(len(p)==2 for p in a[7].values())


def test_verification_uses_predictions_not_reference():
    a=proposal(1,'SUPPORT',.9,[0,2],'SUPPORT',.8,True)
    assert a['doc']==1 and a['label']=='SUPPORT' and a['sentences']==[0,2]
    assert proposal(1,'SUPPORT',.9,[0,2],'CONTRADICT',.8,True) is None
    assert proposal(1,'NO_EVIDENCE',.9,[0], 'SUPPORT',.8,False) is None


def test_complete_reference_set_and_unjudged_are_distinct():
    refs=[{'id':1,'evidence':{'1':[{'label':'SUPPORT','sentences':[0,1]}]}},{'id':2,'evidence':{}},{'id':3,'evidence':{'2':[{'label':'CONTRADICT','sentences':[0]}]}}]
    p={1:proposal(1,'SUPPORT',.9,[0],'SUPPORT',.8,False),2:proposal(4,'SUPPORT',.8,[0],'SUPPORT',.9,False),3:None}
    r=evaluate(refs,p,3)
    assert r['confirmed']==0 and r['unconfirmed']==2 and r['unjudged_doc']==1 and r['reference_claims']==2
    p[1]=proposal(1,'SUPPORT',.9,[0,1],'SUPPORT',.8,False)
    assert evaluate(refs,p,1)['confirmed']==1
    with pytest.raises(ValueError): evaluate(refs,{1:p[1]},3)


def test_calibration_gate_and_fallback_only_on_abstentions():
    fit=[(.9,True)]*100
    assert fit_gate(fit,fit)['threshold']==.5
    assert fit_gate(fit,fit[:4])['threshold'] is None
    assert fit_gate(fit,[(.9,False)]*100)['threshold'] is None
    base={1:None,2:proposal(2,'SUPPORT',.9,[0],'SUPPORT',.9,True)}
    alt={1:proposal(1,'SUPPORT',.9,[0],'SUPPORT',.9,True),2:None}
    assert fallback(base,alt,None)==base and fallback(base,alt,.5)=={1:alt[1],2:base[2]}


def test_full_factorial_cross_on_small_real_retrieval(monkeypatch):
    import sys
    from types import ModuleType
    from iatonoesis.scifact_open import stage,sentence_ids
    module=ModuleType('iatonoesis.scifact_pipeline')
    def predict(rows,*args,ranking):
        return ({r['id']:(1. if ranking else ('SUPPORT',.9)) for r in rows},0)
    module.pretrained=predict; monkeypatch.setitem(sys.modules,'iatonoesis.scifact_pipeline',module)
    corpus={1:['cold causes cough','study'],2:['cold result'],3:['fish study']}
    claims=[{'id':7,'claim':'cold cough','evidence':{'1':[{'label':'SUPPORT','sentences':[0]}]},'cited_doc_ids':[1]}]
    p,r,t=stage(corpus,claims,(None,None),(None,None),lambda rows:{x['id']:('SUPPORT',.9) for x in rows},lambda rows:{x['id']:('NO_EVIDENCE',.9) for x in rows},2)
    assert len(p)==24 and r['bm25']['pool_hits']==1 and t['candidate_pairs']>=2
    assert p['bm25:retrieval:rules:1'][7] is None
    assert p['bm25:retrieval:nli:1'][7]['sentences']==[0,1]
    assert sentence_ids(corpus[1],'cold cough')==[0,1]


def test_source_failure_receipt_and_budget_validation(monkeypatch,tmp_path):
    import json,sys
    from iatonoesis import scifact_open as m
    with pytest.raises(ValueError): retrieve({1:['x']},[],2)
    with pytest.raises(ValueError): fallback({1:None},{2:None},None)
    dest=tmp_path/'result.json';monkeypatch.setattr(sys,'argv',['run','--output',str(dest)])
    monkeypatch.setattr(m,'run',lambda root:{'scope':'fixture'});m.main();assert json.loads(dest.read_text())=={'scope':'fixture'}
    def fail(root): raise ValueError('fixture')
    monkeypatch.setattr(m,'run',fail)
    with pytest.raises(ValueError): m.main()
    assert json.loads(dest.read_text())['status']=='failed'
