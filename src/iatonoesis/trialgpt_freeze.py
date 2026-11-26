"""Deterministic metadata-only TrialGPT candidate partition; not evaluation admission."""
import argparse
import json
import tempfile
from collections import defaultdict
from pathlib import Path

from .run_contracts import canonical_sha256

PARTITIONS = ('development', 'calibration', 'test')


def candidate_freeze(rows):
    """Group patient/trial connected components, without using outcome labels."""
    parent = {}

    def root(node):
        parent.setdefault(node, node)
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    by_id = {}
    for row in rows:
        i, p, t = (row.get(k) for k in ('annotation_id', 'patient_id', 'trial_id'))
        if type(i) is not int or not isinstance(p, str) or not p or not isinstance(t, str) or not t or type(row.get('training')) is not bool or type(row.get('criterion_missing')) is not bool:
            raise ValueError('invalid metadata')
        if i in by_id:
            raise ValueError('duplicate annotation ID')
        by_id[i] = row
        parent[root(('p', p))] = root(('t', t))
    groups = defaultdict(list)
    for i, row in by_id.items():
        groups[root(('p', row['patient_id']))].append(i)
    if len(groups) < 3:
        raise ValueError('fewer than three independent components')
    ordered = sorted((sorted(ids) for ids in groups.values()), key=lambda ids: (-len(ids), canonical_sha256(ids)))
    n = len(by_id)
    target = dict(development=n*6//10, calibration=n*2//10)
    target['test'] = n-target['development']-target['calibration']
    counts = {p: dict(rows=0, components=0, training_true=0, criterion_missing=0, training_false_only_components=0, training_false_only_rows=0) for p in PARTITIONS}
    assignment, ownership = [], {}
    for ids in ordered:
        p = max(PARTITIONS, key=lambda p: target[p]-counts[p]['rows'])
        group_id = canonical_sha256(ids)
        c = counts[p]
        c['rows'] += len(ids)
        c['components'] += 1
        c['training_true'] += sum(by_id[i]['training'] for i in ids)
        c['criterion_missing'] += sum(by_id[i]['criterion_missing'] for i in ids)
        if not any(by_id[i]['training'] for i in ids):
            c['training_false_only_components'] += 1
            c['training_false_only_rows'] += len(ids)
        for i in ids:
            row = by_id[i]
            for node in (('p', row['patient_id']), ('t', row['trial_id'])):
                if ownership.setdefault(node, p) != p:
                    raise ValueError('group leakage')
            assignment.append([i, group_id, p, row['training'], row['criterion_missing']])
    if not all(c['rows'] for c in counts.values()):
        raise ValueError('three-way grouped partition not feasible with fixed allocator')
    return dict(schema_version='0.1.0', status='candidate_metadata_frozen', qualification='not_qualified',
                evaluation_admitted=False, rows=n, components=len(ordered), group_disjoint_verified=True,
                partitions=counts, assignment_sha256=canonical_sha256(sorted(assignment)),
                algorithm='component-size-descending, digest tie-break, largest remaining absolute target deficit; 60/20/20',
                limitations=['training flag semantics unresolved', 'model-assisted expert labels not blinded',
                             'component grouping only; near-duplicate audit and component-level rights pending',
                             'no row identifiers, labels, notes or model outputs published'])


def main():
    from . import dataset_audit as audit
    import pyarrow.parquet as pq

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory)/'trial.parquet'
        url = f'https://huggingface.co/datasets/ncbi/TrialGPT-Criterion-Annotations/resolve/{audit.TRIAL_REV}/{audit.TRIAL_FILE}'
        audit._download(url, path, 176088)
        integrity = audit.verify_bytes(path, 176088, audit.TRIAL_SHA)
        table = pq.read_table(path, columns=['annotation_id', 'patient_id', 'trial_id', 'training', 'criterion_text'])
        if table.num_rows != 1015:
            raise ValueError('unexpected row count')
        rows = table.to_pylist()
        metadata = [{k: row[k] for k in ('annotation_id', 'patient_id', 'trial_id', 'training')} | {'criterion_missing': row['criterion_text'] is None or row['criterion_text'] == ''} for row in rows]
        result = candidate_freeze(metadata)
        result.update(source_revision=audit.TRIAL_REV, source_integrity=integrity)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True)+'\n')


if __name__ == '__main__':
    main()
