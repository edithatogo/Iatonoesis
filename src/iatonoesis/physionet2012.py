"""PhysioNet 2012 aggregate-only source and observation-process benchmark."""
import argparse
import csv
import hashlib
import io
import json
import math
import re
import tarfile
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from urllib.request import urlopen

BASE='https://physionet.org/files/challenge-2012/1.0.0/'
SIZES={'A':6632372,'B':6652690}
HORIZONS=(1,3,6)
AUX=('MAP','NIMAP','RespRate','SaO2')
SEED='iatonoesis-p12-v0.1.0'


def sha(raw): return hashlib.sha256(raw).hexdigest()


def digest(obj): return sha(json.dumps(obj,sort_keys=True,separators=(',',':'),allow_nan=False).encode())


def parse(raw,identifier):
    lines=csv.reader(io.StringIO(raw.decode('utf-8-sig')))
    if next(lines,None)!=['Time','Parameter','Value']: raise ValueError('invalid header')
    hr=[];other=Counter();icu='unknown';ids=[];content=[];previous=0;out_of_order=0
    for row in lines:
        if len(row)!=3 or not re.fullmatch(r'\d{2}:\d{2}',row[0]): raise ValueError('invalid row/time')
        h,m=map(int,row[0].split(':'));t=h*60+m
        if m>=60 or not 0<=t<=2880: raise ValueError('time outside 48-hour window')
        out_of_order+=int(t<previous);previous=t
        name=row[1]
        if name=='RecordID':
            if t!=0: raise ValueError('non-admission identity')
            ids.append(row[2]);continue
        content.append(row)
        if name=='ICUType':
            if t==0 and row[2] in ('1','2','3','4'): icu=row[2]
        elif name in ('HR',*AUX):
            v=float(row[2])
            if not math.isfinite(v) or (v<0 and v!=-1): raise ValueError('invalid observed value')
            if v==-1: continue
            if name=='HR': hr.append((t,v))
            elif t<360: other[name]+=1
    if ids!=[identifier]: raise ValueError('record identity mismatch')
    # Stable tie-order from the source. Never use post-cutoff values in features.
    hr.sort(key=lambda item:item[0]);history=[None]*6
    for t,v in hr:
        if t<360: history[t//60]=v
    targets={}
    for h in HORIZONS:
        values=[v for t,v in hr if 360+(h-1)*60<=t<360+h*60]
        if values and any(v is not None for v in history): targets[str(h)]=values[0]
    return dict(history=history,count=sum(x is not None for x in history),aux_counts=[other[k] for k in AUX],
                targets=targets,observed=int(any(360<=t<540 for t,_ in hr)),icu=icu,
                content_sha256=digest(content),out_of_order=out_of_order)


def unpack(blob,cohort,expected=4000):
    if cohort not in SIZES or len(blob)>10_000_000: raise ValueError('invalid archive')
    rows={};members=0;expanded=0
    with tarfile.open(fileobj=io.BytesIO(blob),mode='r:gz') as tar:
        for entry in tar:
            members+=1
            if members>expected+20: raise ValueError('too many archive members')
            name=entry.name.removeprefix('./');prefix='set-'+cohort.lower()
            if entry.isdir() and name in ('', '.',prefix): continue
            match=re.fullmatch(r'(?:'+prefix+r'/)?(\d{6})\.txt',name)
            if not entry.isfile() or match is None or not 1<=entry.size<=1_000_000: raise ValueError('invalid archive member')
            expanded+=entry.size
            if expanded>200_000_000: raise ValueError('expanded archive limit')
            key=match.group(1)
            if key in rows: raise ValueError('duplicate archive identity')
            fh=tar.extractfile(entry)
            if fh is None: raise ValueError('unreadable archive member')
            raw=fh.read(entry.size+1)
            if len(raw)!=entry.size: raise ValueError('archive member size mismatch')
            rows[key]=dict(raw_sha256=sha(raw),**parse(raw,key))
    if len(rows)!=expected: raise ValueError('archive record count mismatch')
    return rows


def freeze(archives,expected=4000):
    if set(archives)!=set(SIZES): raise ValueError('missing cohort')
    rows=[];seen_ids=set();seen_content={};manifest=[];counts={}
    for cohort in ('A','B'):
        data=unpack(archives[cohort],cohort,expected);parts=Counter();eligible=Counter();icu=Counter();events=0;disorder=0
        for key,r in sorted(data.items()):
            split='test' if cohort=='B' else 'calibration' if int(sha((SEED+'|'+key).encode())[:8],16)%5==0 else 'development'
            if key in seen_ids or (r['content_sha256'] in seen_content and seen_content[r['content_sha256']]!=split): raise ValueError('cross-partition identity or content overlap')
            seen_ids.add(key);seen_content[r['content_sha256']]=split
            manifest.append([cohort,key,r['raw_sha256'],r['content_sha256'],split]);parts[split]+=1;icu[r['icu']]+=1;events+=r['observed'];disorder+=r['out_of_order']
            eligible.update(r['targets'].keys());rows.append(dict(id=sha((SEED+'|'+key).encode()),split=split,**r))
        counts[cohort]=dict(records=len(data),partitions=dict(parts),eligible_observed_targets=dict(eligible),icu_type=dict(icu),observed_next_3h=events,out_of_order_rows=disorder,archive_sha256=sha(archives[cohort]),archive_bytes=len(archives[cohort]))
    return dict(rows=rows,counts=counts,manifest_sha256=digest(manifest))


def observation_features(r,extra):
    lag=next((i for i,v in enumerate(reversed(r['history'])) if v is not None),6)
    return [1.,r['count']/6,lag/6,*([min(n,12)/12 for n in r['aux_counts']] if extra else [])]


def sigmoid(x): return 1/(1+math.exp(-max(-30.,min(30.,x))))


def fit_logistic(rows,extra):
    if not rows or any(r['split']!='development' for r in rows): raise ValueError('development only')
    data=[(observation_features(r,extra),r['observed']) for r in rows];w=[0.]*len(data[0][0])
    for _ in range(160):
        g=[0.]*len(w)
        for x,y in data:
            err=sigmoid(sum(a*b for a,b in zip(w,x)))-y
            for i,v in enumerate(x): g[i]+=err*v
        w=[v-.5*(d/len(data)+(.01*v if i else 0.)) for i,(v,d) in enumerate(zip(w,g))]
    return w


def observation_benchmark(rows):
    dev=[r for r in rows if r['split']=='development'];test=[r for r in rows if r['split']=='test']
    if not dev or not test: raise ValueError('missing split')
    base=mean(r['observed'] for r in dev);groups=defaultdict(list)
    def bucket(r): return tuple(observation_features(r,False)[1:3])
    for r in dev:groups[bucket(r)].append(r['observed'])
    weights={name:fit_logistic(dev,extra) for name,extra in [('timing_logistic',False),('multivariate_timing',True)]}
    def predict(r,name):
        if name=='prevalence': return base
        if name=='empirical_bucket':
            y=groups.get(bucket(r),[]);return (sum(y)+10*base)/(len(y)+10)
        return sigmoid(sum(a*b for a,b in zip(weights[name],observation_features(r,name=='multivariate_timing'))))
    arms={}
    for name in ('prevalence','empirical_bucket',*weights):
        pred=[predict(r,name) for r in test];errors=[(r['observed']-p)**2 for r,p in zip(test,pred)];bins=[]
        for i in range(10):
            selected=[(r['observed'],p) for r,p in zip(test,pred) if min(9,int(p*10))==i]
            bins.append(dict(n=len(selected),observed=mean(y for y,_ in selected) if selected else None,predicted=mean(p for _,p in selected) if selected else None))
        arms[name]=dict(brier=mean(errors),ece=sum(b['n']*abs(b['observed']-b['predicted']) for b in bins if b['n'])/len(test),bins=bins,prediction_sha256=digest(pred))
    return dict(n=len(test),development=len(dev),prevalence=mean(r['observed'] for r in test),arms=arms,model_sha256=digest(dict(weights=weights,base=base,groups=sorted((k,v) for k,v in groups.items()))))


def acquire(cohort):
    with urlopen(BASE+'set-'+cohort.lower()+'.tar.gz',timeout=60) as response: blob=response.read(SIZES[cohort]+1)
    if len(blob)!=SIZES[cohort]: raise ValueError('published archive length mismatch')
    return blob


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--revision',required=True);args=parser.parse_args()
    try:
        if not re.fullmatch(r'[0-9a-f]{40}',args.revision): raise ValueError('invalid revision')
        frozen=freeze({c:acquire(c) for c in SIZES});result=dict(scope='public_observation_process_technical_benchmark',source=BASE,licence='ODC-By-1.0',source_commit=args.revision,source_manifest_sha256=frozen['manifest_sha256'],counts=frozen['counts'],observation=observation_benchmark(frozen['rows']),limits=['actual recording not clinical need','no mortality labels','source identities not verified cross-dataset patient independence','A/B random split, not hospitals','archive hash observed, no independent publisher checksum verified'])
    except Exception as exc:
        args.output.write_text(json.dumps(dict(status='failed',error_type=type(exc).__name__,scope='aggregate_only'))+'\n');raise SystemExit(1) from None
    args.output.write_text(json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+'\n')


if __name__=='__main__': main()
