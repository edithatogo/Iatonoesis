"""Exercise archive integrity, complete CLI replay and negative paths."""
import copy
import gzip
import hashlib
import json
import sys
import zipfile

import pytest

from iatonoesis import census_audit, paired_audit
from test_census_audit import fixture
from test_paired_audit import row


def test_census_archive_and_cli(tmp_path, monkeypatch):
    a,b=fixture()
    a['guidelines'][0]['clinical_areas']=['regional']
    b['summary']['status_counts']={'oa_xml_candidate':1,'metadata_only':1,'missing_identifier':1}
    z=tmp_path/'source.zip'
    with zipfile.ZipFile(z,'w') as f:
        f.writestr('equator-catalogue.json',json.dumps(a))
        f.writestr('equator-article-survey.json',json.dumps(b))
    h=hashlib.sha256(z.read_bytes()).hexdigest()
    with pytest.raises(ValueError,match='digest'):
        census_audit.from_zip(z,'0'*64)
    out=tmp_path/'out.json'
    monkeypatch.setattr(sys,'argv',['audit','--archive',str(z),'--sha256',h,'--output',str(out)])
    census_audit.main()
    result=json.loads(out.read_text())
    assert result['archive_sha256']==h
    assert result['population']==3 and result['canonical_packs_promoted']==0
    assert set(result['input_sha256'])=={'equator-catalogue.json','equator-article-survey.json'}
    assert result['strata']['clinical_areas']['regional']['population']==1


def test_census_rejects_invalid_strata_and_summary():
    a,b=fixture()
    a['guidelines'][0]['study_types']=[' ']
    with pytest.raises(ValueError,match='stratum'):
        census_audit.census(a,b)
    a,b=fixture()
    b['summary']['status_counts']={'metadata_only':3}
    with pytest.raises(ValueError,match='summary'):
        census_audit.census(a,b)
    a,b=fixture()
    b['summary']['canonical_packs_promoted']=1
    with pytest.raises(ValueError,match='promotion'):
        census_audit.census(a,b)
    with pytest.raises(ValueError,match='identity'):
        census_audit.indexed([{'id':''}])


def test_paired_archive_cli_and_boundary(tmp_path,monkeypatch):
    a,b,c=[row('AX')],[row('AB')],[row('BC')]
    receipt=dict(claim_boundary='synthetic_only',canonical_acceptance=False,
                 freeze_revision='a'*40,fixture_sha256='b'*64,modalities={
                     'text':{'predictions':{'flat':a,'right_only':b,'bidirectional':c}},
                     'ocr':{'predictions':{'flat':b,'right_only':a,'bidirectional':b}}})
    def write(value):
        path=tmp_path/'paired.json.gz'
        path.write_bytes(gzip.compress(json.dumps(value).encode(),mtime=0))
        return path,hashlib.sha256(path.read_bytes()).hexdigest()
    path,h=write(receipt)
    with pytest.raises(ValueError,match='digest'):
        paired_audit.audit(path,'0'*64)
    output=tmp_path/'result.json'
    monkeypatch.setattr(sys,'argv',['audit','--input',str(path),'--sha256',h,'--output',str(output)])
    paired_audit.main()
    result=json.loads(output.read_text())
    assert len(result['pairs'])==5
    assert result['receipt_sha256']==h
    assert result['pairs']['text_flat_vs_bidirectional']['total']['new_correct']==2
    assert result['pairs']['text_vs_ocr_bidirectional']['total']['lost_correct']==1
    bad=copy.deepcopy(receipt);bad['canonical_acceptance']=True
    path,h=write(bad)
    with pytest.raises(ValueError,match='boundary'):
        paired_audit.audit(path,h)


def test_reject_invalid_list_and_missing_groups():
    with pytest.raises(ValueError,match='list'):
        paired_audit.items('AB')
    a,b=row('A'),row('B')
    a['groups']=b['groups']={}
    with pytest.raises(ValueError,match='group'):
        paired_audit.compare([a],[b])
