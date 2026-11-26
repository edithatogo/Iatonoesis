import copy
import pytest
from iatonoesis.run_contracts import canonical_sha256
from iatonoesis.typed_results import run_typed, validate_typed

COMMIT = 'a'*40


def fixture(kind, metric, refs, outputs, options=None):
    inputs = {k: {'value': k} for k in refs}
    inputs.update(d={'value':'d'}, c={'value':'c'})
    refs = dict(refs, d=next(iter(refs.values())), c=next(iter(refs.values())))
    data = dict(schema_version='0.1.0', dataset_id='toy', kind='synthetic', source='authored fixture',
                revision=COMMIT, sha256=canonical_sha256(inputs),
                rights=dict(status='approved',licence='MIT',evidence='synthetic test'),
                reference=dict(kind='deterministic_oracle',revision=COMMIT,sha256=canonical_sha256(refs)),
                grouping_keys=['case'], rows=[dict(id=k,split={'d':'development','c':'calibration'}.get(k,'test'),groups={'case':k}) for k in inputs])
    exp = dict(schema_version='0.1.0',experiment_id='toy-'+kind,track_task='T00.005',dataset_id='toy',
               dataset_sha256=data['sha256'],reference_sha256=data['reference']['sha256'],split='test',
               case_ids=list(outputs),primary_metric=metric,metric_kind=kind,metric_options=options or {},unit='case',
               seed=17,arms=[dict(id='rules',role='deterministic'),dict(id='model',role='classical')],
               budget=dict(max_cases=len(outputs),max_seconds=10),claim_boundary='synthetic_only')
    return exp,data,inputs,refs,{'rules':lambda x: outputs[x['value']]}


def execute(f):
    exp,data,inputs,refs,predictors = f
    return run_typed(exp,data,inputs,refs,predictors=predictors,source_commit=COMMIT)


def metric(f):
    result = execute(f)
    validate_typed(result,*f[:4])
    return result['manifest']['arms'][0]['metrics']


def test_continuous_with_abstention_and_intervals():
    f=fixture('continuous','mae',{'a':1,'b':3,'e':9},
              {'a':{'value':2,'lower':0,'upper':3},'b':{'value':1,'lower':0,'upper':2},'e':None}, {'intervals':True})
    m=metric(f)
    assert m['total']==3 and m['scored']==2 and m['abstained']==1
    assert m['decision_coverage']==pytest.approx(2/3)
    assert m['mae']==1.5 and m['interval_coverage']==.5
    assert m['mean_interval_width']==2.5
    assert 'errors' not in m


def test_ranked_complete_pool_and_unjudged_failure():
    ref={'qrels':{'x':1,'y':0,'z':1},'k':2}
    f=fixture('ranking','ndcg',{'a':ref},{'a':['y','x','z']})
    m=metric(f)
    assert m['precision']==m['recall']==.5 and m['ndcg']<1
    assert m['defined_counts']['ndcg']==1
    bad=fixture('ranking','ndcg',{'a':ref},{'a':['y','x']})
    r=execute(bad)
    assert r['manifest']['arms'][0]['status']=='failed'
    assert 'metrics' not in r['manifest']['arms'][0]


def test_calibration_and_mutation_metrics():
    m=metric(fixture('calibration','brier',{'a':0,'b':1},{'a':0.25,'b':.75},{'bins':2}))
    assert m['brier']==.0625 and m['ece']==.25
    ref={'signatures':{'a':[0,1],'duplicate':[0,1],'b':[2],'equivalent':[]},'pool_size':3,'budget':1}
    m=metric(fixture('mutation','mean_defect_coverage',{'a':ref},{'a':[0]}))
    assert m['mean_defect_coverage']==.5 and m['distinct_defects']==2 and m['detected']==1


def test_invalid_reference_is_rejected_even_when_adapter_abstains():
    f=fixture('calibration','brier',{'a':3},{'a':None})
    with pytest.raises(ValueError,match='reference'):
        execute(f)


def test_result_recomputation_rejects_tampered_hash_metrics_and_denominator():
    f=fixture('continuous','mae',{'a':1},{'a':2})
    result=execute(f)
    assert result['manifest']['arms'][1]['status']=='unavailable'
    for field in ('predictions_sha256','metrics'):
        bad=copy.deepcopy(result)
        if field=='metrics': bad['manifest']['arms'][0][field]['mae']=0
        else: bad['manifest']['arms'][0][field]='0'*64
        with pytest.raises(ValueError): validate_typed(bad,*f[:4])
    bad=copy.deepcopy(result); bad['predictions']['rules'][0]['id']='wrong'
    with pytest.raises(ValueError): validate_typed(bad,*f[:4])
    bad=copy.deepcopy(result); bad['manifest']['arms'][1]['metrics']={}
    with pytest.raises(ValueError): validate_typed(bad,*f[:4])


def test_missing_refs_bad_provenance_and_failed_arm():
    f=fixture('continuous','mae',{'a':1},{'a':2})
    f[3]['a']=2
    with pytest.raises(ValueError,match='hash'): execute(f)
    f=fixture('continuous','mae',{'a':1},{'a':float('nan')})
    r=execute(f)
    assert r['manifest']['arms'][0]['status']=='failed' and 'rules' not in r['predictions']
    with pytest.raises(ValueError,match='commit'):
        run_typed(*f[:4],predictors=f[4],source_commit='bad')


def test_invalid_options_and_undeclared_adapters():
    for kind,metric,ref,opts in [('continuous','bogus',1,{}),('continuous','interval_coverage',1,{}),
                                 ('continuous','mae',1,{'bins':2}),('calibration','brier',0,{'bins':0})]:
        f=fixture(kind,metric,{'a':ref},{'a':None},opts)
        with pytest.raises(ValueError): execute(f)
    f=fixture('continuous','mae',{'a':1},{'a':2})
    with pytest.raises(ValueError,match='undeclared'):
        run_typed(*f[:4],predictors={'unexpected':lambda _:2},source_commit=COMMIT)


def test_timing_partial_output_and_learning_provenance():
    f=fixture('continuous','mae',{'a':1,'b':2},{'a':2,'b':3})
    ticks=iter([0,0,1,11])
    r=run_typed(*f[:4],predictors=f[4],source_commit=COMMIT,clock=lambda:next(ticks))
    assert r['manifest']['arms'][0]['reason']=='TimeoutError'
    assert [x['id'] for x in r['failure_artifacts']['rules']]==['a']
    assert 'rules' not in r['predictions']
    models={'model':{'id':'regressor','revision':COMMIT,'licence':'MIT'}}
    r=run_typed(*f[:4],predictors=dict(f[4],model=lambda _:2),source_commit=COMMIT,models=models)
    assert r['manifest']['arms'][1]['model']==models['model']
    bad=copy.deepcopy(r);del bad['manifest']['arms'][1]['model']
    with pytest.raises(ValueError,match='provenance'): validate_typed(bad,*f[:4])
    bad=copy.deepcopy(r);bad['manifest']['arms'][1]['elapsed_seconds']=-1
    with pytest.raises(ValueError,match='elapsed'): validate_typed(bad,*f[:4])
    bad=copy.deepcopy(r);bad['manifest']['arms'][1]['metrics']['scored']=99
    with pytest.raises(ValueError,match='metric'): validate_typed(bad,*f[:4])


def test_all_abstentions_undefined_and_interval_ordering():
    for kind,metric,ref,options in [('continuous','mae',1,{}),('calibration','brier',0,{}),
            ('ranking','ndcg',{'qrels':{'a':0},'k':1},{}),
            ('mutation','mean_defect_coverage',{'signatures':{'equivalent':[]},'pool_size':1,'budget':1},{})]:
        m=metric_fn(fixture(kind,metric,{'a':ref},{'a':None},options))
        assert m[metric] is None and m['scored']==0 and m['decision_coverage']==0
    f=fixture('continuous','mae',{'a':1},{'a':{'value':2,'lower':3,'upper':4}},{'intervals':True})
    assert execute(f)['manifest']['arms'][0]['status']=='failed'


metric_fn=metric
