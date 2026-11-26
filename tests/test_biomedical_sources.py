import io,json,tarfile,zipfile
import pytest
from iatonoesis import biomedical_sources as b


def row(context,label='yes'):
    return {'QUESTION':'A question?', 'CONTEXTS':[context],'LABELS':['RESULTS'],'LONG_ANSWER':'withheld','final_decision':label}


def test_pubmedqa_reference_and_group_checks():
    d={'1':row('test'), '2':row('development','no')}
    a=b.pubmedqa(json.dumps(d).encode(),b'{"1":"yes"}',expected=2,test_expected=1)
    assert a['test']==1 and a['development_pool']==1 and a['test_labels']=={'yes':1}
    with pytest.raises(ValueError,match='reference mismatch'):b.pubmedqa(json.dumps(d).encode(),b'{"1":"no"}',expected=2,test_expected=1)
    d['2']=row('test');a=b.pubmedqa(json.dumps(d).encode(),b'{"1":"yes"}',expected=2,test_expected=1)
    assert a['cross_partition_exact_context_groups']==1 and not a['evaluation_admitted']


def zipbytes(names):
    f=io.BytesIO()
    with zipfile.ZipFile(f,'w') as z:
        for n in names:z.writestr(n,b'fixture')
    return f.getvalue()


def tarbytes(names):
    f=io.BytesIO()
    with tarfile.open(fileobj=f,mode='w:gz') as t:
        for n in names:
            x=tarfile.TarInfo(n);x.size=7;t.addfile(x,io.BytesIO(b'fixture'))
    return f.getvalue()


def test_safe_archive_inventory():
    for mode,make in [('zip',zipbytes),('tar',tarbytes)]:
        result=b.inventory(make(['train/a.txt','test/b.txt']),mode)
        assert result['files']==2 and result['extensions']=={'.txt':2}
        assert result['split_marked_files']=={'test':1,'train':1}
        with pytest.raises(ValueError,match='member'):b.inventory(make(['../x.txt']),mode)


def test_reject_duplicate_json_keys_and_hash_mismatch():
    with pytest.raises(ValueError,match='duplicate'):b.load(b'{"a":1,"a":2}')
    with pytest.raises(ValueError,match='blob'):b.verify_blob(b'x','0'*40)


def test_csv_inventory():
    assert b.csv_inventory(b'year,trust,value\n2020,X,1\n')['rows']==1
    for raw in (b'',b'x,x\n1,2\n',b'x,y\n1\n',b'x,y\n'):
        with pytest.raises(ValueError):b.csv_inventory(raw)
    with pytest.raises(ValueError):b.inventory(b'','invalid')


def test_acquisition_and_independent_failure_receipts(monkeypatch,tmp_path):
    import sys,hashlib
    monkeypatch.setattr(b,'urlopen',lambda *a,**k:io.BytesIO(b'abc'))
    assert b.get('https://example.invalid',3)==b'abc'
    with pytest.raises(ValueError,match='limit'):b.get('https://example.invalid',2)
    b.verify_blob(b'abc',hashlib.sha1(b'blob 3\0abc').hexdigest())
    def fetch(url,limit):
        if url.endswith('ori_pqal.json'):return b'fixture'
        if url.endswith('test_ground_truth.json'):return b'gold'
        if url==b.BIORED:return zipbytes(['train/a.txt','test/b.txt'])
        if url==b.EBM:return tarbytes(['train/a.txt','test/b.txt'])
        if 'Occupied' in url:return b'year,trust,value\n2020,X,1\n'
        raise ValueError('private content')
    monkeypatch.setattr(b,'get',fetch);monkeypatch.setattr(b,'verify_blob',lambda *_:None)
    monkeypatch.setattr(b,'pubmedqa',lambda *_:dict(expert_rows=1000,evaluation_admitted=False))
    monkeypatch.setattr(b,'audit_biored',lambda *_:dict(documents=600))
    r=b.run();assert r['pubmedqa']['expert_rows']==1000 and r['biored']['files']==2 and r['ebm_nlp']['files']==2
    assert r['nhs_occupied']['rows']==1 and r['nhs_available']=={'status':'failed','error_type':'ValueError','reason':'unclassified'}
    path=tmp_path/'audit.json';monkeypatch.setattr(sys,'argv',['audit','--revision','a'*40,'--output',str(path)])
    with pytest.raises(SystemExit):b.main()
    assert json.loads(path.read_text())['sources']==r
    assert 'private content' not in path.read_text()


def test_biored_pubtator_document_and_relation_audit():
    raw=b'1|t|Gene\n1|a|Disease\n1\t0\t4\tGene\tGeneOrGeneProduct\t1\n1\t5\t12\tDisease\tDiseaseOrPhenotypicFeature\tD1\n1\tAssociation\t1\tD1\tNovel\n\n'
    f=io.BytesIO()
    with zipfile.ZipFile(f,'w') as z:
        for split,i in [('train',b'1'),('dev',b'2'),('test',b'3')]:
            z.writestr(split+'.pubtator',raw if i==b'1' else raw.replace(b'1|',i+b'|').replace(b'\n1\t',b'\n'+i+b'\t').replace(b'Gene\n',i+b'Gene\n'))
    out=b.audit_biored(f.getvalue(),expected=3)
    assert out['documents']==3 and out['split_documents']=={'train':1,'dev':1,'test':1}
    assert out['relations']==3 and out['unresolved_relation_endpoints']==0
    assert out['evaluation_admitted'] is False
    with pytest.raises(ValueError):b.audit_biored(zipbytes(['a.txt']),expected=3)


def test_allowlisted_failure_does_not_leak_values():
    assert b.reason(ValueError('invalid archive member'))=='invalid archive member'
    assert b.reason(ValueError('secret member x'))=='unclassified'


def test_archive_inventory_has_source_specific_limits():
    raw=tarbytes(['a.txt','b.txt'])
    with pytest.raises(ValueError,match='expansion limit'):b.inventory(raw,'tar',max_members=1)
    assert b.inventory(raw,'tar',max_members=2)['files']==2
    with pytest.raises(ValueError,match='expansion limit'):b.inventory(raw,'tar',max_expanded=13)
