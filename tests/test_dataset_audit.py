import hashlib
import io
import tarfile

import pytest

from iatonoesis.dataset_audit import verify_bytes, trial_components, archive_index, split_documents


def test_hash_and_length_gate(tmp_path):
    p = tmp_path/'file'
    p.write_bytes(b'abc')
    assert verify_bytes(p, 3, hashlib.sha256(b'abc').hexdigest())['bytes'] == 3
    with pytest.raises(ValueError, match='integrity'):
        verify_bytes(p, 3, 'a'*64)
    with pytest.raises(ValueError, match='integrity'):
        verify_bytes(p, 4, hashlib.sha256(b'abc').hexdigest())


def test_bipartite_components_count_transitive_overlap():
    r = trial_components([('p1','t1'),('p2','t1'),('p2','t2'),('p3','t3')])
    assert r['patients'] == r['trials'] == 3
    assert r['component_row_counts'] == [3,1]
    assert not r['three_way_group_split_possible']


def test_missing_id_rejected():
    with pytest.raises(ValueError, match='identifier'):
        trial_components([('', 't1')])


def _archive(path, entries):
    with tarfile.open(path,'w:gz') as t:
        for name, payload in entries:
            item=tarfile.TarInfo(name)
            item.size=len(payload)
            t.addfile(item,io.BytesIO(payload))


def test_archive_audit_and_path_traversal(tmp_path):
    p=tmp_path/'a.tar.gz'
    _archive(p,[('test/PMC1_table_0.xml',b'<annotation><object><name>table</name></object></annotation>')])
    r=archive_index(p,kind='annotations')
    assert r['xml_files']==1 and r['object_labels']=={'table':1}
    _archive(p,[('../unsafe.xml',b'<annotation/>')])
    with pytest.raises(ValueError,match='unsafe'):
        archive_index(p,kind='annotations')


def test_filelist_document_leakage():
    r=split_documents({'train':['PMC11_table_0','PMC22_table_1'],'val':['PMC33_table_0'],
                       'test':['PMC11_table_2','unknown']})
    assert r['train_test_document_overlap']==1
    assert r['unmapped_file_ids']=={'train':0,'val':0,'test':1}
    assert not r['document_disjoint_verified']


def test_filelist_archive_identifies_splits(tmp_path):
    p=tmp_path/'lists.tar.gz'
    _archive(p,[('train_filelist.txt',b'PMC1_table_0\n'),('val_filelist.txt',b'PMC2_table_0\n'),('test_filelist.txt',b'PMC3_table_0\n')])
    assert archive_index(p,kind='filelists')['document_disjoint_verified']
