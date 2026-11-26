"""Bounded public-source integrity and aggregate metadata audit; no qualification or raw release."""
import argparse
import hashlib
import json
import re
import tarfile
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath

TRIAL_REV = '7fca07b80914df31e0ab69f9f8fd4d3c6a06d020'
TRIAL_FILE = 'data/train-00000-of-00001.parquet'
TRIAL_SHA = '14c547184fac9b013cd17441fd028845b40150c76b022e58334f5494077e5234'
TABLE_REV = '35b1c097807e0b07ec5313879b85956b7b3890db'
TABLES = {'PubTables-1M-Structure_Annotations_Test.tar.gz': (29925736, 'annotations'),
          'PubTables-1M-Structure_Filelists.tar.gz': (9665473, 'filelists')}
TRIAL_COLUMNS = {'annotation_id','patient_id','note','trial_id','trial_title','criterion_type',
                 'criterion_text','gpt4_explanation','explanation_correctness','gpt4_sentences',
                 'expert_sentences','gpt4_eligibility','expert_eligibility','training'}


def verify_bytes(path, expected_size, expected_sha):
    h = hashlib.sha256()
    size = 0
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024*1024), b''):
            size += len(block)
            h.update(block)
    actual = h.hexdigest()
    if size != expected_size or actual != expected_sha:
        raise ValueError('source integrity mismatch')
    return {'bytes': size, 'sha256': actual}


def _download(url, path, cap):
    if not url.startswith('https://huggingface.co/'):
        raise ValueError('unapproved source')
    with urllib.request.urlopen(url, timeout=30) as response, path.open('wb') as target:
        if not response.geturl().startswith('https://'):
            raise ValueError('insecure redirect')
        size = 0
        while chunk := response.read(1024*1024):
            size += len(chunk)
            if size > cap:
                raise ValueError('download size cap exceeded')
            target.write(chunk)


def trial_components(pairs):
    parent = {}
    def root(x):
        parent.setdefault(x,x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for p,t in pairs:
        if not isinstance(p,str) or not p or not isinstance(t,str) or not t:
            raise ValueError('missing patient/trial identifier')
        parent[root(('p',p))] = root(('t',t))
    counts=Counter(root(('p',p)) for p,_ in pairs)
    sizes=sorted(counts.values(),reverse=True)
    return dict(patients=len({p for p,_ in pairs}),trials=len({t for _,t in pairs}),
                components=len(sizes),component_row_counts=sizes,
                largest_component_fraction=sizes[0]/len(pairs) if pairs else None,
                three_way_group_split_possible=len(sizes)>=3,
                largest_component_exceeds_60pct=bool(sizes and sizes[0]>.6*len(pairs)))


def split_documents(filelists):
    sets, unmapped, counts, duplicates = {}, {}, {}, {}
    for name in ('train','val','test'):
        files=filelists.get(name,[])
        counts[name]=len(files)
        duplicates[name]=len(files)-len(set(files))
        docs=[re.search(r'PMC\d+', item, flags=re.I) for item in files]
        sets[name]={x.group(0).upper() for x in docs if x}
        unmapped[name]=sum(x is None for x in docs)
    overlaps={f'{a}_{b}_document_overlap':len(sets[a]&sets[b]) for a,b in [('train','val'),('train','test'),('val','test')]}
    return dict(file_counts=counts,duplicate_file_ids=duplicates,unmapped_file_ids=unmapped,
                document_counts={k:len(v) for k,v in sets.items()},**overlaps,
                document_disjoint_verified=all(counts.values()) and not any(unmapped.values()) and not any(duplicates.values()) and not any(overlaps.values()))


def archive_index(path, *, kind):
    if kind not in {'annotations','filelists'}:
        raise ValueError('unknown archive kind')
    names=set(); xml_files=0; labels=Counter(); lists=defaultdict(list); unknown=0; expanded=0
    with tarfile.open(path, 'r|gz') as archive:
        for member in archive:
            p=PurePosixPath(member.name)
            if p.is_absolute() or '..' in p.parts or '\\' in member.name:
                raise ValueError('unsafe archive member')
            if member.isdir():
                continue
            if not member.isfile():
                raise ValueError('unsafe nonregular member')
            if member.name in names:
                raise ValueError('duplicate archive member')
            names.add(member.name)
            expanded+=member.size
            if len(names)>120000 or expanded>1500000000 or member.size>50000000:
                raise ValueError('archive resource cap exceeded')
            source=archive.extractfile(member)
            if source is None:
                raise ValueError('unreadable archive member')
            if kind=='annotations' and p.suffix.lower()=='.xml':
                if member.size>1000000:
                    raise ValueError('XML size cap exceeded')
                root=ET.fromstring(source.read())
                if root.tag!='annotation':
                    raise ValueError('unexpected annotation XML root')
                xml_files+=1
                for node in root.findall('object/name'):
                    label=node.text or ''
                    if not re.fullmatch(r'[A-Za-z0-9 _-]{1,80}',label):
                        raise ValueError('unexpected object label')
                    labels[label]+=1
            elif kind=='filelists' and p.suffix.lower()=='.txt':
                match=re.search(r'(?:^|[_.\-/])(train|val|test)(?:[_.\-/]|$)',member.name,re.I)
                if match:
                    lists[match[1].lower()].extend(line.strip() for line in source.read().decode('utf-8').splitlines() if line.strip())
                else:
                    unknown+=1
            else:
                unknown+=1
    out=dict(regular_members=len(names),expanded_bytes=expanded,unclassified_members=unknown)
    if kind=='annotations':
        out.update(xml_files=xml_files,object_labels=dict(labels))
    else:
        out.update(split_documents(lists))
    return out


def audit_trial(root):
    import pyarrow.parquet as pq
    path=root/'trial.parquet'
    url=f'https://huggingface.co/datasets/ncbi/TrialGPT-Criterion-Annotations/resolve/{TRIAL_REV}/{TRIAL_FILE}'
    _download(url,path,176088)
    integrity=verify_bytes(path,176088,TRIAL_SHA)
    table=pq.read_table(path)
    if table.num_rows!=1015 or set(table.column_names)!=TRIAL_COLUMNS:
        raise ValueError('unexpected TrialGPT row count or schema')
    rows=table.to_pylist()
    missing={col:sum(row[col] is None or row[col]=='' for row in rows) for col in table.column_names}
    ids=[row['annotation_id'] for row in rows]
    if None in ids or len(set(ids))!=len(ids):
        raise ValueError('duplicate or missing annotation identifier')
    # Count duplicate narrative content without publishing the source text or identifiers.
    by_note=defaultdict(set)
    for row in rows:
        if isinstance(row['note'],str) and row['note']:
            by_note[hashlib.sha256(row['note'].encode()).hexdigest()].add(row['patient_id'])
    labels=Counter()
    for row in rows:
        value=row['expert_eligibility']
        if isinstance(value,str) and re.fullmatch(r'[A-Za-z _-]{1,40}',value):
            labels[value]+=1
        else:
            labels['other_or_missing']+=1
    return dict(revision=TRIAL_REV,integrity=integrity,rows=table.num_rows,columns=table.num_columns,
                missing=missing,expert_label_counts=dict(labels),training_true=sum(r['training'] is True for r in rows),
                expert_model_agreement=sum(r['expert_eligibility']==r['gpt4_eligibility'] for r in rows),
                duplicate_note_across_patient_groups=sum(len(v)>1 for v in by_note.values()),
                **trial_components([(r['patient_id'],r['trial_id']) for r in rows]),
                status='structural_audit_only',qualification='not_qualified')


def audit_tables(root):
    api=f'https://huggingface.co/api/datasets/bsmock/pubtables-1m/tree/{TABLE_REV}?recursive=false&expand=true'
    meta=root/'metadata.json'
    _download(api,meta,2000000)
    data=json.loads(meta.read_text())
    out={}
    for filename,(size,kind) in TABLES.items():
        matches=[row for row in data if row.get('path')==filename]
        if len(matches)!=1:
            raise ValueError('pinned archive metadata absent')
        row=matches[0]; lfs=row.get('lfs') or {}
        sha=lfs.get('oid') or lfs.get('sha256')
        if row.get('size')!=size or not isinstance(sha,str) or not re.fullmatch(r'[0-9a-f]{64}',sha):
            raise ValueError('pinned archive metadata mismatch')
        path=root/filename
        _download(f'https://huggingface.co/datasets/bsmock/pubtables-1m/resolve/{TABLE_REV}/{filename}',path,size)
        integrity=verify_bytes(path,size,sha)
        result=archive_index(path,kind=kind)
        if kind=='annotations' and result['xml_files']!=93834:
            raise ValueError('unexpected test annotation count')
        out[kind]=dict(filename=filename,integrity=integrity,**result)
        path.unlink()
    return dict(revision=TABLE_REV,archives=out,status='annotation_metadata_only',qualification='not_qualified',
                images_or_words_acquired=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    results={'schema_version':'0.1.0','scope':'public source integrity and aggregate metadata only',
             'qualification':'not_qualified','sources':{}}
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory)
        for key,fn in [('trialgpt_criterion',audit_trial),('pubtables_structure',audit_tables)]:
            try:
                results['sources'][key]=fn(root)
            except Exception as exc:
                # No exception string or raw source content in logs or public artifacts.
                results['sources'][key]={'status':'failed','error_type':type(exc).__name__,'qualification':'not_qualified'}
    args.output.write_text(json.dumps(results,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    if any(x['status']=='failed' for x in results['sources'].values()):
        raise SystemExit(1)


if __name__=='__main__':
    main()
