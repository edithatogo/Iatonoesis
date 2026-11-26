import json
import pytest
from iatonoesis.trialgpt_freeze import candidate_freeze


def fixture():
    return [dict(annotation_id=i, patient_id=f'patient-{i//2}', trial_id=f'trial-{i//2}',
                 training=i % 3 == 0, criterion_missing=i == 1) for i in range(12)]


def test_candidate_is_stable_group_disjoint_and_not_admitted():
    rows = fixture()
    a = candidate_freeze(rows)
    assert a == candidate_freeze(list(reversed(rows)))
    assert a['qualification'] == 'not_qualified'
    assert a['rows'] == 12 and a['components'] == 6
    assert sum(x['rows'] for x in a['partitions'].values()) == 12
    assert sum(x['training_true'] for x in a['partitions'].values()) == 4
    assert sum(x['criterion_missing'] for x in a['partitions'].values()) == 1
    assert a['group_disjoint_verified']
    assert 'patient-' not in json.dumps(a) and 'trial-' not in json.dumps(a)
    assert all(x['rows'] > 0 for x in a['partitions'].values())


def test_transitive_links_are_one_group():
    rows = fixture()
    rows[2]['trial_id'] = rows[0]['trial_id']
    assert candidate_freeze(rows)['components'] == 5


def test_invalid_and_duplicate_metadata_fail_closed():
    rows = fixture()
    with pytest.raises(ValueError, match='duplicate'):
        candidate_freeze(rows + [rows[0]])
    with pytest.raises(ValueError, match='metadata'):
        candidate_freeze([dict(rows[0], training=None)] + rows[1:])
    with pytest.raises(ValueError, match='three'):
        candidate_freeze(rows[:2])


def test_label_or_model_output_does_not_affect_partition():
    rows = fixture()
    altered = [dict(r, expert_eligibility='changed', gpt4_eligibility='changed') for r in rows]
    assert candidate_freeze(rows) == candidate_freeze(altered)


def test_cli_retains_aggregate_only_and_rejects_wrong_row_count(monkeypatch, tmp_path):
    import sys
    from types import ModuleType, SimpleNamespace
    import iatonoesis
    from iatonoesis.trialgpt_freeze import main

    rows = [dict(annotation_id=i, patient_id=f'private-p{i//5}', trial_id=f'private-t{i//5}',
                 training=i % 3 == 0, criterion_text='private text' if i else None) for i in range(1015)]
    audit = ModuleType('iatonoesis.dataset_audit')
    audit.TRIAL_REV, audit.TRIAL_FILE, audit.TRIAL_SHA = 'a'*40, 'data/source.parquet', 'b'*64
    def download(url, path, cap):
        assert audit.TRIAL_REV in url and cap == 176088
        path.write_bytes(b'fixture')
    audit._download = download
    audit.verify_bytes = lambda path, size, sha: {'bytes': size, 'sha256': sha}
    monkeypatch.setitem(sys.modules, 'iatonoesis.dataset_audit', audit)
    monkeypatch.setattr(iatonoesis, 'dataset_audit', audit, raising=False)
    arrow, parquet = ModuleType('pyarrow'), ModuleType('pyarrow.parquet')
    table = SimpleNamespace(num_rows=1015, to_pylist=lambda: rows)
    def read_table(path, columns):
        assert columns == ['annotation_id', 'patient_id', 'trial_id', 'training', 'criterion_text']
        return table
    parquet.read_table = read_table
    arrow.parquet = parquet
    monkeypatch.setitem(sys.modules, 'pyarrow', arrow)
    monkeypatch.setitem(sys.modules, 'pyarrow.parquet', parquet)
    dest = tmp_path/'aggregate.json'
    monkeypatch.setattr(sys, 'argv', ['trialgpt_freeze', '--output', str(dest)])
    main()
    result = json.loads(dest.read_text())
    assert result['rows'] == 1015 and result['source_revision'] == audit.TRIAL_REV
    assert 'private-' not in dest.read_text() and 'private text' not in dest.read_text()
    table.num_rows = 1014
    with pytest.raises(ValueError, match='row count'):
        main()


def test_fixed_allocator_rejects_empty_partition():
    rows = [dict(annotation_id=i, patient_id=str(i), trial_id=str(i), training=False,
                 criterion_missing=False) for i in range(3)]
    with pytest.raises(ValueError, match='three-way'):
        candidate_freeze(rows)
