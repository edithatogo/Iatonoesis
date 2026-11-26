import copy
import pytest
from iatonoesis.census_audit import census


def fixture():
    cat = {'source_revision': 'a'*40, 'published_count': 3, 'guidelines': [
        {'id': 'a', 'source_blob_sha':'b'*40, 'study_types':['A','A','B'], 'metadata_status':'extracted_unverified'},
        {'id': 'b', 'source_blob_sha':'c'*40, 'study_types':['A'], 'metadata_status':'extracted_unverified'},
        {'id': 'c', 'source_blob_sha':'d'*40, 'study_types':[], 'metadata_status':'needs_review'}]}
    survey={'source_revision':'a'*40, 'summary':{'published_count':3,'canonical_packs_promoted':0}, 'records':[
        {'id':'a','source_blob_sha':'b'*40,'status':'oa_xml_candidate'},
        {'id':'b','source_blob_sha':'c'*40,'status':'metadata_only'},
        {'id':'c','source_blob_sha':'d'*40,'status':'missing_identifier'}],
        'priority_articles':[{'edition':'e','status':'held','canonical_packs_promoted':0}], 'bulk_articles':[]}
    return cat,survey


def test_complete_multi_membership_denominators():
    out = census(*fixture())
    assert out['population']==3
    assert out['status_counts']=={'metadata_only':1,'missing_identifier':1,'oa_xml_candidate':1}
    assert out['strata']['study_types']['A']['population']==2
    assert out['strata']['study_types']['A']['oa_candidate_fraction']==.5
    assert out['strata']['study_types']['B']['population']==1
    assert out['strata']['study_types']['(unspecified)']['population']==1
    assert out['metadata_review_count']==1
    assert out['claim_boundary']=='acquisition_coverage_not_model_performance'


@pytest.mark.parametrize('fault',['missing','duplicate','blob','revision','promotion','unknown_status'])
def test_fail_closed(fault):
    a,b=fixture()
    if fault=='missing': b['records'].pop()
    elif fault=='duplicate': b['records'].append(copy.deepcopy(b['records'][0]))
    elif fault=='blob': b['records'][0]['source_blob_sha']='e'*40
    elif fault=='revision': b['source_revision']='z'*40
    elif fault=='promotion': b['priority_articles'][0]['canonical_packs_promoted']=1
    elif fault=='unknown_status': b['records'][0]['status']='qualified'
    with pytest.raises(ValueError): census(a,b)
