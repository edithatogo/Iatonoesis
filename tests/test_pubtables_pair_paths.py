import io
import json
import sys
import tarfile

import pytest
from iatonoesis import pubtables_pairs as p
from test_pubtables_pairs import archive, xml


def test_rejects_unsafe_and_unexpected_archive_members(tmp_path):
    for name,data,reason in [
        ('PMC1_table_0.txt',b'bad','file type'),
        ('wrong.xml',xml(),'identity'),
        ('PMC1_table_0.xml',b'<!DOCTYPE annotation><annotation/>','unsafe'),
        ('PMC1_table_0.xml',b'<other/>','invalid annotation'),
        ('PMC1_table_0.xml',b'<annotation/>','dimensions'),
        ('PMC1_table_0.xml',xml(0,10),'dimensions'),
    ]:
        with pytest.raises(ValueError,match=reason):
            p.annotation_index(archive(tmp_path/'a.tgz',[(name,data)]))
    a=archive(tmp_path/'a.tgz',[('PMC1_table_0.xml',xml())])
    with pytest.raises(ValueError,match='resource cap'):
        list(p.members(a,'.xml',0))
    with tarfile.open(tmp_path/'link.tgz','w:gz') as f:
        m=tarfile.TarInfo('PMC1_table_0.xml');m.type=tarfile.SYMTYPE;m.linkname='outside';f.addfile(m)
    with pytest.raises(ValueError,match='unsafe'):
        p.annotation_index(tmp_path/'link.tgz')


def test_duplicate_image_word_and_outside_box_counts(tmp_path):
    key='PMC1_table_0';ann={key:{'dims':(20,10),'sha256':'a'*64}}
    with pytest.raises(ValueError,match='document'):
        p.sample_tables(ann,2)
    i=archive(tmp_path/'i.tgz',[(f'{d}/{key}.jpg',b'image') for d in ('a','b')])
    with pytest.raises(ValueError,match='duplicate image'):
        p.image_index(i,ann,[key],decode=lambda _: (20,10))
    w=archive(tmp_path/'w.tgz',[(f'{d}/{key}_words.json',b'[]') for d in ('a','b')])
    with pytest.raises(ValueError,match='duplicate word'):
        p.word_index(w,ann,[key])
    for raw,reason in [(b'{}','word list'),(b'[{"bbox":[0,1,2,3]}]','word token')]:
        with pytest.raises(ValueError,match=reason):
            p.word_index(archive(tmp_path/'w.tgz',[(key+'_words.json',raw)]),ann,[key])
    w=archive(tmp_path/'w.tgz',[(key+'_words.json',b'[{"bbox":[-1,0,3,3],"text":"x"}]')])
    assert p.word_index(w,ann,[key])['sample'][key]['outside']==1


def test_actual_jpeg_decoder():
    Image=pytest.importorskip('PIL.Image')
    b=io.BytesIO();Image.new('RGB',(20,10)).save(b,format='JPEG')
    assert p.decode_jpeg(b.getvalue())==(20,10)
    b=io.BytesIO();Image.new('RGB',(20,10)).save(b,format='PNG')
    with pytest.raises(ValueError,match='image'):
        p.decode_jpeg(b.getvalue())


def test_cli_redacts_failure_and_emits_aggregate(tmp_path,monkeypatch):
    out=tmp_path/'result.json'
    monkeypatch.setattr(sys,'argv',['audit','--output',str(out)])
    monkeypatch.setattr(p,'run',lambda _: {'matched_image_word_tables':3,'evaluation_admitted':False})
    p.main()
    assert json.loads(out.read_text())['matched_image_word_tables']==3
    def fail(_): raise ValueError('source text')
    monkeypatch.setattr(p,'run',fail)
    with pytest.raises(SystemExit) as exc:
        p.main()
    assert exc.value.code==1
    assert json.loads(out.read_text())=={'status':'failed','error_type':'ValueError','evaluation_admitted':False}
    assert 'source text' not in out.read_text()
