"""Network-free regression coverage of the actual source audit entry points."""
import hashlib
import io
import json
import sys
import tarfile
from types import ModuleType, SimpleNamespace

import pytest

from iatonoesis import dataset_audit as audit


class Response(io.BytesIO):
    def __init__(self, data, url='https://huggingface.co/file'):
        super().__init__(data)
        self.url = url

    def geturl(self):
        return self.url


def test_download_constraints(tmp_path, monkeypatch):
    dest = tmp_path / 'payload'
    with pytest.raises(ValueError, match='unapproved'):
        audit._download('https://example.invalid/file', dest, 5)
    monkeypatch.setattr(audit.urllib.request, 'urlopen', lambda *a, **k: Response(b'abc'))
    audit._download('https://huggingface.co/file', dest, 3)
    assert dest.read_bytes() == b'abc'
    with pytest.raises(ValueError, match='size cap'):
        audit._download('https://huggingface.co/file', dest, 2)
    monkeypatch.setattr(audit.urllib.request, 'urlopen', lambda *a, **k: Response(b'abc', 'http://example.invalid'))
    with pytest.raises(ValueError, match='insecure redirect'):
        audit._download('https://huggingface.co/file', dest, 3)
    with pytest.raises(ValueError, match='integrity'):
        audit.verify_bytes(dest, 3, '0' * 64)


def make_archive(path, entries):
    with tarfile.open(path, 'w:gz') as stream:
        for name, payload, kind in entries:
            member = tarfile.TarInfo(name)
            member.type = kind
            member.size = len(payload)
            stream.addfile(member, io.BytesIO(payload))


def test_archive_rejects_invalid_members(tmp_path):
    path = tmp_path / 'fixture.tar.gz'
    with pytest.raises(ValueError, match='unknown archive kind'):
        audit.archive_index(path, kind='unknown')
    for entries, message in [
        ([('/absolute.xml', b'', tarfile.REGTYPE)], 'unsafe archive'),
        ([('link', b'', tarfile.SYMTYPE)], 'nonregular'),
        ([('a.xml', b'<annotation/>', tarfile.REGTYPE)] * 2, 'duplicate'),
        ([('a.xml', b'<wrong/>', tarfile.REGTYPE)], 'XML root'),
        ([('a.xml', b'<annotation><object><name>bad!</name></object></annotation>', tarfile.REGTYPE)], 'object label'),
        ([('a.xml', b' ' * 1000001, tarfile.REGTYPE)], 'XML size cap'),
    ]:
        make_archive(path, entries)
        with pytest.raises(ValueError, match=message):
            audit.archive_index(path, kind='annotations')
    make_archive(path, [('dir', b'', tarfile.DIRTYPE), ('readme.txt', b'x', tarfile.REGTYPE)])
    assert audit.archive_index(path, kind='annotations')['unclassified_members'] == 1
    assert audit.archive_index(path, kind='filelists')['unclassified_members'] == 1


def test_archive_resource_limit_and_unreadable(monkeypatch, tmp_path):
    class Archive:
        def __init__(self, size):
            self.member = tarfile.TarInfo('safe.xml')
            self.member.size = size

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def __iter__(self):
            return iter([self.member])

        def extractfile(self, member):
            return None

    monkeypatch.setattr(audit.tarfile, 'open', lambda *a, **k: Archive(50000001))
    with pytest.raises(ValueError, match='resource cap'):
        audit.archive_index(tmp_path/'a', kind='annotations')
    monkeypatch.setattr(audit.tarfile, 'open', lambda *a, **k: Archive(1))
    with pytest.raises(ValueError, match='unreadable'):
        audit.archive_index(tmp_path/'a', kind='annotations')


def test_trial_schema_and_aggregate_paths(monkeypatch, tmp_path):
    columns = sorted(audit.TRIAL_COLUMNS)
    rows = [dict.fromkeys(columns, 'fixture') | dict(annotation_id=i, patient_id=f'p{i%3}',
            trial_id=f't{i%3}', note='shared synthetic text', training=i%2==0,
            criterion_text=None if i==0 else 'fixture', expert_eligibility='included' if i else 'bad!')
            for i in range(1015)]
    table = SimpleNamespace(num_rows=1015, num_columns=len(columns), column_names=columns, to_pylist=lambda: rows)
    arrow, parquet = ModuleType('pyarrow'), ModuleType('pyarrow.parquet')
    parquet.read_table = lambda path: table
    arrow.parquet = parquet
    monkeypatch.setitem(sys.modules, 'pyarrow', arrow)
    monkeypatch.setitem(sys.modules, 'pyarrow.parquet', parquet)
    monkeypatch.setattr(audit, '_download', lambda url, path, cap: path.write_bytes(b'fixture'))
    monkeypatch.setattr(audit, 'verify_bytes', lambda *a: {'bytes': 176088, 'sha256': audit.TRIAL_SHA})
    out = audit.audit_trial(tmp_path)
    assert out['rows'] == 1015 and out['missing']['criterion_text'] == 1
    assert out['expert_label_counts'] == {'included': 1014, 'other_or_missing': 1}
    assert out['duplicate_note_across_patient_groups'] == 1
    assert out['qualification'] == 'not_qualified' and 'shared synthetic text' not in json.dumps(out)
    table.num_rows = 1014
    with pytest.raises(ValueError, match='row count'):
        audit.audit_trial(tmp_path)
    table.num_rows = 1015
    rows[1]['annotation_id'] = 0
    with pytest.raises(ValueError, match='duplicate or missing'):
        audit.audit_trial(tmp_path)


def test_table_metadata_and_integrity_paths(monkeypatch, tmp_path):
    entries = [{'path': name, 'size': size, 'lfs': {'oid': 'a'*64}} for name,(size,_) in audit.TABLES.items()]
    monkeypatch.setattr(audit, '_download', lambda url, path, cap: path.write_text(json.dumps(entries)))
    monkeypatch.setattr(audit, 'verify_bytes', lambda path,size,sha: {'bytes':size,'sha256':sha})
    counts = {'annotations': {'xml_files': 93834}, 'filelists': {'document_disjoint_verified': True}}
    monkeypatch.setattr(audit, 'archive_index', lambda path,kind: counts[kind])
    out = audit.audit_tables(tmp_path)
    assert out['qualification'] == 'not_qualified' and not out['images_or_words_acquired']
    assert set(out['archives']) == set(counts)
    counts['annotations']['xml_files'] = 1
    with pytest.raises(ValueError, match='annotation count'):
        audit.audit_tables(tmp_path)
    counts['annotations']['xml_files'] = 93834
    entries[0]['lfs']['oid'] = 'wrong'
    with pytest.raises(ValueError, match='metadata mismatch'):
        audit.audit_tables(tmp_path)
    entries.pop(0)
    with pytest.raises(ValueError, match='metadata absent'):
        audit.audit_tables(tmp_path)


def test_cli_records_failure_without_raw_error(monkeypatch, tmp_path):
    dest = tmp_path/'aggregate.json'
    monkeypatch.setattr(sys, 'argv', ['audit', '--output', str(dest)])
    monkeypatch.setattr(audit, 'audit_trial', lambda root: {'status': 'structural_audit_only'})
    monkeypatch.setattr(audit, 'audit_tables', lambda root: {'status': 'annotation_metadata_only'})
    audit.main()
    assert set(json.loads(dest.read_text())['sources']) == {'trialgpt_criterion', 'pubtables_structure'}
    def fail(root):
        raise RuntimeError('private synthetic input')
    monkeypatch.setattr(audit, 'audit_tables', fail)
    with pytest.raises(SystemExit) as exc:
        audit.main()
    assert exc.value.code == 1
    assert json.loads(dest.read_text())['sources']['pubtables_structure']['error_type'] == 'RuntimeError'
    assert 'private synthetic input' not in dest.read_text()
