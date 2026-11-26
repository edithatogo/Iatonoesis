import pytest
from iatonoesis.paired_audit import compare


def row(pred, id='x'):
    return {'id':id,'gold':[['A'],['B'],['C'],['D']], 'prediction':[[x] for x in pred], 'groups':{'family':'f'}}


def test_unique_gain_and_regression():
    r=compare([row('ABX')],[row('BCY')])
    assert r['total']=={'shared_correct':1,'new_correct':1,'lost_correct':1,'shared_missed':1,'new_false':1,'removed_false':1,'shared_false':0,'baseline_abstentions':0,'challenger_abstentions':0,'cases':1}
    assert r['by_family']['f']==r['total']


def test_abstentions_remain_in_denominator():
    a=row('AB'); a['prediction']=None
    r=compare([a],[row('AB')])['total']
    assert r['baseline_abstentions']==1 and r['new_correct']==2 and r['shared_missed']==2


@pytest.mark.parametrize('fault',['id','duplicate','gold','family','duplicate_prediction'])
def test_fail_closed(fault):
    a,b=[row('AB')],[row('BC')]
    if fault=='id': b[0]['id']='y'
    elif fault=='duplicate': b.append(row('BC'))
    elif fault=='gold': b[0]['gold']=[['B']]
    elif fault=='family': b[0]['groups']['family']='g'
    elif fault=='duplicate_prediction': b[0]['prediction'].append(['B'])
    with pytest.raises(ValueError): compare(a,b)
