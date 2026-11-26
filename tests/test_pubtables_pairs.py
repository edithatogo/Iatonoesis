import hashlib
import io
import json
import tarfile

import pytest

from iatonoesis import pubtables_pairs as p


def archive(path, members):
    with tarfile.open(path, 'w:gz') as f:
        for name, data in members:
            i=tarfile.TarInfo(name);i.size=len(data);f.addfile(i,io.BytesIO(data))
    return path


def xml(w=20,h=10):
    return f'<annotation><size><width>{w}</width><height>{h}</height></size></annotation>'.encode()


def test_pairing_and_sample_checks(tmp_path):
    ids=['PMC1_table_0','PMC1_table_1','PMC2_table_0']
    a=archive(tmp_path/'a.tgz',[(i+'.xml',xml()) for i in ids])
    images=archive(tmp_path/'i.tgz',[(i+'.jpg',b'fake-image') for i in ids])
    words=archive(tmp_path/'w.tgz',[(i+'_words.json',json.dumps([{'bbox':[1,2,5,6],'text':'private test token'}]).encode()) for i in ids+['PMC3_table_0']])
    annotations=p.annotation_index(a)
    selected=p.sample_tables(annotations,2)
    assert len(selected)==2 and len({i.split('_')[0] for i in selected})==2
    ia=p.image_index(images,annotations,selected,decode=lambda raw:(20,10))
    wa=p.word_index(words,annotations,selected)
    result=p.pair_receipt(annotations,selected,ia,wa)
    assert result['annotation_tables']==3 and result['matched_image_word_tables']==3
    assert result['sample_validated']==2 and result['sample_word_count']==2
    assert result['word_archive_extra_tables']==1 and not result['evaluation_admitted']
    assert 'private test token' not in json.dumps(result)


def test_fail_closed_and_missing_pair(tmp_path):
    a=archive(tmp_path/'a.tgz',[('PMC1_table_0.xml',xml())])
    ann=p.annotation_index(a);selected=p.sample_tables(ann,1)
    i=archive(tmp_path/'i.tgz',[('PMC1_table_0.jpg',b'image')])
    with pytest.raises(ValueError,match='dimensions'):
        p.image_index(i,ann,selected,decode=lambda raw:(99,99))
    ia=p.image_index(i,ann,selected,decode=lambda raw:(20,10))
    w=archive(tmp_path/'w.tgz',[('PMC9_table_0_words.json',b'[]')])
    with pytest.raises(ValueError,match='pair'):
        p.pair_receipt(ann,selected,ia,p.word_index(w,ann,selected))
    w=archive(tmp_path/'w.tgz',[('PMC1_table_0_words.json',b'[{"bbox":[1,2,0,3],"text":"x"}]')])
    with pytest.raises(ValueError,match='bbox'):
        p.word_index(w,ann,selected)
    unsafe=archive(tmp_path/'u.tgz',[('../PMC1_table_0.xml',xml())])
    with pytest.raises(ValueError,match='unsafe'):
        p.annotation_index(unsafe)
    duplicate=archive(tmp_path/'d.tgz',[('a/PMC1_table_0.xml',xml()),('b/PMC1_table_0.xml',xml())])
    with pytest.raises(ValueError,match='duplicate'):
        p.annotation_index(duplicate)


def test_metadata_pinning_and_bounds():
    key='PubTables-1M-Structure_Images_Test.tar.gz'
    rows=[{'path':key,'size':100,'lfs':{'oid':'a'*64}}]
    assert p.pin(rows,key,1000)==(100,'a'*64)
    with pytest.raises(ValueError,match='metadata'):
        p.pin(rows,key,50)
    with pytest.raises(ValueError,match='metadata'):
        p.pin([],key,1000)
    with pytest.raises(ValueError,match='metadata'):
        p.pin([dict(rows[0],lfs={})],key,1000)
