import pytest
from iatonoesis import measured_replication as r
from iatonoesis import measured_pilot as m
from test_measured_pilot import psv, fixture


def test_horizon_and_strata_are_bound_to_prior_window():
    raw=psv(0,True)
    h=r.case_horizon(raw,3)
    assert h['cutoff']==9 and h['target']==79
    assert h['history']==[71.,72.,73.,74.,None,76.]
    assert r.strata(h['history'])==('recency_0','missing_1_2')
    assert r.strata([1.,None,None,None,None,None])==('recency_3_plus','missing_3_plus')
    assert r.case_horizon(raw,6) is None
    with pytest.raises(ValueError,match='horizon'):
        r.case_horizon(raw,0)


def test_new_sample_excludes_old_ranked_keys():
    keys=[f'p{i:06}.psv' for i in range(20)]
    chosen=r.new_keys(keys,old=4,count=8)
    assert chosen==r.new_keys(list(reversed(keys)),old=4,count=8)
    from iatonoesis import physionet_audit as s
    assert not set(chosen)&set(s.sample_keys(keys,4))
    with pytest.raises(ValueError):
        r.new_keys(keys,old=19,count=2)


def test_cost_caps_and_stop_rule():
    group,records=fixture()
    counts={c:len(v) for c,v in group.items()}
    frozen=m.freeze(group,lambda c,k:records[c,k],expected_counts=counts,sample_counts=counts)
    dev=[x for x in frozen['rows']['acquisition'] if x['split']=='development']
    model,policy,_=m.fit_acquisition(dev)
    row=dev[0]
    zero=r.cost_acquire(row,model,policy,'fixed',(1,3,1),0)
    assert zero['spent']==0 and zero['count']==0
    for cap in (1,2,3,5):
        out=[r.cost_acquire(row,model,policy,a,(1,3,1),cap) for a in ('fixed','greedy','context','context_stop')]
        assert all(0<=x['spent']<=cap for x in out)
        assert all(x['count']<=3 for x in out)
        if cap==5: assert len({round(x['prediction'],10) for x in out[:3]})==1
    with pytest.raises(ValueError,match='cost'):
        r.cost_acquire(row,model,policy,'fixed',(1,0,1),3)


def test_paired_stratified_summary_uses_paired_subjects():
    rows=[{'id':'a','history':[1.,2.,3.,4.,5.,6.],'target':10},
          {'id':'b','history':[1.,None,None,4.,None,6.],'target':20}]
    out=r.stratified(rows,{'last':[11.,22.],'ridge':[10.,20.]},{'last':2.,'ridge':1.})
    assert out['all']['n']==2
    assert out['all']['arms']['ridge']['mae']==0
    assert out['all']['paired']['ridge']['difference']==-1.5
    assert out['missing_1_2']['n']==0
    assert out['missing_3_plus']['n']==1
    assert out['missing_3_plus']['paired']['ridge'] is None
