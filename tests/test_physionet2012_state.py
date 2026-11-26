import copy
import pytest

from iatonoesis import physionet2012_state as m


def test_projection_retains_only_pre_cutoff_history_and_horizon_target():
    rows=[dict(id='d',split='development',history=[70,None,72,None,74,75],targets={'1':76,'3':81},icu='1',mark_minutes=[[359]],unused=99),
          dict(id='c',split='calibration',history=[71]*6,targets={'3':82}),
          dict(id='t',split='test',history=[72]*6,targets={'3':83})]
    result=m.project(rows,3)
    assert len(result)==3
    assert result[0]==dict(id='d',split='development',history=[70,None,72,None,74,75],target=81)
    assert len(m.project(rows,1))==1
    rows[0]['targets']['6']=99
    assert m.project(rows,3)==result


def test_projection_rejects_duplicate_unknown_split_and_invalid_values():
    row=dict(id='a',split='test',history=[70]*6,targets={'1':75})
    for invalid in [dict(row,split='quarantine'),dict(row,history=[None]*6),dict(row,history=[70]*5),dict(row,targets={'1':float('inf')})]:
        with pytest.raises(ValueError):m.project([invalid],1)
    with pytest.raises(ValueError,match='duplicate'):m.project([row,row],1)
    with pytest.raises(ValueError,match='horizon'):m.project([row],2)


def test_archive_partition_receipt_gate():
    counts={c:dict(archive_sha256=h,records=4000,retained=3999,partitions=m.PARTITIONS[c],eligible_observed_targets=m.ELIGIBLE[c]) for c,h in m.ARCHIVES.items()}
    receipt=dict(manifest_sha256=m.MANIFEST,counts=counts,audit=dict(quarantined_records=2,cross_cohort_components=1))
    m.verify(receipt)
    for change in [lambda x:x.update(manifest_sha256='bad'),lambda x:x['counts']['A'].update(archive_sha256='bad'),lambda x:x['counts']['B'].update(retained=4000),lambda x:x['audit'].update(quarantined_records=0)]:
        bad=copy.deepcopy(receipt);change(bad)
        with pytest.raises(ValueError):m.verify(bad)


def test_sparse_strata_suppression_keeps_denominators():
    original={'all':{'n':12,'arms':{'last':{'mae':1}},'paired':{}},'recency_3_plus':{'n':3,'arms':{'last':{'mae':5}},'paired':{}},'missing_0':{'n':0,'arms':{},'paired':{}}}
    out=m.protect_strata(original)
    assert out['all']==original['all']
    assert out['recency_3_plus']==dict(n=3,status='suppressed_small_stratum',arms=None,paired=None)
    assert out['missing_0']['n']==0 and out['missing_0']['arms'] is None


def test_complementary_suppression():
    out=m.protect_strata({'recency_0':{'n':20,'arms':{},'paired':{}},'recency_1_2':{'n':3,'arms':{},'paired':{}},'missing_0':{'n':23,'arms':{},'paired':{}}})
    assert out['recency_0']['status']=='suppressed_complementary'
    assert out['missing_0']['n']==23 and 'status' not in out['missing_0']


def test_missing_cohort_rejected():
    with pytest.raises(ValueError,match='cohort'):
        m.verify(dict(manifest_sha256=m.MANIFEST,counts={},audit=dict(quarantined_records=2,cross_cohort_components=1)))
