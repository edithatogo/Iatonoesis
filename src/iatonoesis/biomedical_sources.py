"""Aggregate-only source audit; no inference or redistribution of abstract text."""
import argparse
import csv
import hashlib
import io
import json
import re
import tarfile
import zipfile
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath
from urllib.request import urlopen

PQA='https://raw.githubusercontent.com/pubmedqa/pubmedqa/1cbae8e92f72f20c8d3747cbb3bf5bc53554d997/data/'
EBM='https://raw.githubusercontent.com/bepnye/EBM-NLP/43a4a1ea3f0a21cfb8820c040b843dfaf66192d0/ebm_nlp_2_00.tar.gz'
BIORED='https://ftp.ncbi.nlm.nih.gov/pub/lu/BioRED/BIORED.zip'
NHS='https://www.england.nhs.uk/statistics/wp-content/uploads/sites/2/2024/09/KH03-'


def sha(raw):return hashlib.sha256(raw).hexdigest()


def verify_blob(raw,expected):
    if hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest()!=expected:raise ValueError('source Git blob mismatch')


def load(raw):
    def pairs(items):
        out={}
        for k,v in items:
            if k in out:raise ValueError('duplicate JSON key')
            out[k]=v
        return out
    return json.loads(raw,object_pairs_hook=pairs)


def pubmedqa(raw,gold,expected=1000,test_expected=500):
    rows=load(raw);ref=load(gold)
    if not isinstance(rows,dict) or not isinstance(ref,dict) or len(rows)!=expected or len(ref)!=test_expected or not set(ref)<=set(rows):raise ValueError('source membership mismatch')
    groups=defaultdict(set);labels=Counter();test_labels=Counter();withheld=0
    for k,r in rows.items():
        if not re.fullmatch(r'\d+',k) or not isinstance(r['QUESTION'],str) or not r['QUESTION'].strip() or not isinstance(r['CONTEXTS'],list) or not r['CONTEXTS'] or not all(isinstance(v,str) for v in r['CONTEXTS']) or r['final_decision'] not in ('yes','no','maybe'):raise ValueError('invalid expert reference row')
        if k in ref and ref[k]!=r['final_decision']:raise ValueError('author test reference mismatch')
        split='test' if k in ref else 'development_pool';labels[r['final_decision']]+=1
        if k in ref:test_labels[r['final_decision']]+=1
        text=' '.join(' '.join(r['CONTEXTS']).casefold().split());groups[sha(text.encode())].add(split)
        withheld+=int('LONG_ANSWER' in r)
    return dict(expert_rows=len(rows),test=len(ref),development_pool=len(rows)-len(ref),labels=dict(labels),test_labels=dict(test_labels),cross_partition_exact_context_groups=sum(len(v)>1 for v in groups.values()),long_answer_fields_to_withhold=withheld,evaluation_admitted=False,limits=['author test labels publicly available; unknown pretraining exposure','MIT repository licence does not settle underlying abstract rights','exact normalized context only, near-duplicate and expert reference review outstanding'])


def inventory(raw,mode):
    seen=set();ext=Counter();splits=Counter();expanded=0
    def add(name,size,is_file):
        nonlocal expanded
        name=name.removeprefix('./');p=PurePosixPath(name)
        if p.is_absolute() or '..' in p.parts or '\\' in name or not is_file or name in seen or not 0<=size<=50_000_000:raise ValueError('invalid archive member')
        seen.add(name);expanded+=size
        if len(seen)>200_000 or expanded>500_000_000:raise ValueError('archive expansion limit')
        ext[p.suffix.lower() or '(none)']+=1
        for s in ('train','training','dev','development','test','testing'):
            if s in {x.lower() for x in p.parts} or re.search(r'(^|[_-])'+s+r'([_.-]|$)',p.name.lower()):splits[s]+=1
    if mode=='zip':
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            for e in z.infolist():
                if e.is_dir():continue
                add(e.filename,e.file_size,((e.external_attr>>16)&0o170000)!=0o120000)
            if z.testzip() is not None:raise ValueError('archive CRC failure')
    elif mode=='tar':
        with tarfile.open(fileobj=io.BytesIO(raw),mode='r:gz') as t:
            for e in t:
                if e.isdir():continue
                add(e.name,e.size,e.isfile())
    else:raise ValueError('unknown archive type')
    if not seen:raise ValueError('empty archive')
    return dict(files=len(seen),extensions=dict(ext),split_marked_files=dict(splits),expanded_bytes=expanded,member_manifest_sha256=sha('\n'.join(sorted(seen)).encode()),evaluation_admitted=False)


def csv_inventory(raw):
    reader=csv.reader(io.StringIO(raw.decode('utf-8-sig')));header=next(reader,None)
    if not header or len(header)!=len(set(header)) or len(header)>100 or any(len(s)>120 for s in header):raise ValueError('invalid CSV header')
    n=0
    for r in reader:
        if not r:continue
        if len(r)!=len(header):raise ValueError('invalid CSV row width')
        n+=1
    if not n:raise ValueError('empty CSV')
    return dict(columns=header,rows=n,evaluation_admitted=False)


def get(url,limit):
    with urlopen(url,timeout=90) as response:raw=response.read(limit+1)
    if len(raw)>limit:raise ValueError('source byte limit')
    return raw


def run():
    def pqa():
        raw=get(PQA+'ori_pqal.json',4_000_000);gold=get(PQA+'test_ground_truth.json',50_000)
        verify_blob(raw,'38db7750761c78950ed32303e7545bdaa513390c');verify_blob(gold,'825bf8f262c3cca0e3bd1c6f38eecf5e581b0659')
        return dict(status='source_audited',bytes=len(raw),sha256=sha(raw),test_reference_sha256=sha(gold),**pubmedqa(raw,gold))
    def archive(url,mode,blob=None):
        raw=get(url,40_000_000)
        if blob:verify_blob(raw,blob)
        return dict(status='archive_inventory_only',bytes=len(raw),sha256=sha(raw),**inventory(raw,mode))
    def nhs(name):
        raw=get(NHS+name+'-Overnight-only.csv',40_000_000)
        return dict(status='csv_inventory_only',bytes=len(raw),sha256=sha(raw),**csv_inventory(raw))
    funcs={'pubmedqa':pqa,'biored':lambda:archive(BIORED,'zip'),'ebm_nlp':lambda:archive(EBM,'tar','152a6348e6a29d19c3727658d269fd3a8a8c6327'),'nhs_occupied':lambda:nhs('Occupied'),'nhs_available':lambda:nhs('Available')}
    result={}
    for k,f in funcs.items():
        try:result[k]=f()
        except Exception as e:result[k]=dict(status='failed',error_type=type(e).__name__)
    return result


def main():
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--output',type=Path,required=True);a.add_argument('--revision',required=True);args=a.parse_args()
    if not re.fullmatch(r'[0-9a-f]{40}',args.revision):raise ValueError('invalid source revision')
    result=run();args.output.write_text(json.dumps(dict(scope='source_audit_not_admission',source_commit=args.revision,sources=result),sort_keys=True,indent=2)+'\n')
    if any(v['status']=='failed' for v in result.values()):raise SystemExit(1)


if __name__=='__main__':main()
