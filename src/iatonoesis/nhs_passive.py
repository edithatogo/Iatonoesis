"""Passive quarterly paired capacity prediction, no intervention inference."""
import argparse,csv,hashlib,io,json,math,random,re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean
from urllib.request import urlopen

URL='https://www.england.nhs.uk/statistics/wp-content/uploads/sites/2/2024/09/KH03-'
PINS={'Available':(2026852,'de58388b736d555b122a764cbad79524d27476fe50a4071f85e8ce19a7fd1147'),
      'Occupied':(2094637,'d00891eacbee972fd8def2e43dda4a2e01e37af20b957a395e1b386aa84a8bc6')}
HEADER=['Organisation_Code','Sector','Number_Of_Beds','Effective_Snapshot_Date']


def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def quarter(value):
    for fmt in ('%Y-%m-%d','%d/%m/%Y','%Y-%m-%d %H:%M:%S','%d/%m/%Y %H:%M:%S','%Y-%m-%dT%H:%M:%S'):
        try:
            d=datetime.strptime(value.strip(),fmt).date();return d.year*4+(d.month-1)//3,d.isoformat()
        except ValueError:pass
    raise ValueError('unrecognized snapshot date')


def parse(raw):
    reader=csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
    if reader.fieldnames!=HEADER:raise ValueError('unexpected source header')
    out={}
    for row in reader:
        if None in row or any(v is None for v in row.values()):raise ValueError('malformed CSV row')
        code=row['Organisation_Code'].strip();sector=row['Sector'].strip();q,date=quarter(row['Effective_Snapshot_Date']);k=(code,sector,q)
        if not code or not sector:raise ValueError('missing organisation or sector')
        if k in out:raise ValueError('duplicate organisation-sector-quarter')
        value=row['Number_Of_Beds'].strip()
        if value.casefold() in ('','*','-','..','n/a','na','[c]','[x]','[z]'):v=None
        else:
            v=float(value.replace(',',''))
            if not math.isfinite(v) or v<0:raise ValueError('invalid bed quantity')
        out[k]=(date,v)
    return out


def join(a,o):
    a,o=parse(a),parse(o);shared=a.keys()&o.keys();series=defaultdict(dict)
    audit=dict(available_rows=len(a),occupied_rows=len(o),matched_keys=len(shared),available_only=len(a.keys()-o.keys()),occupied_only=len(o.keys()-a.keys()),missing_pairs=0,zero_capacity=0,occupied_exceeds_available=0,snapshot_date_mismatch=0)
    for code,sector,q in sorted(shared):
        date,x=a[code,sector,q];other,y=o[code,sector,q]
        if date!=other:audit['snapshot_date_mismatch']+=1;continue
        if x is None or y is None:audit['missing_pairs']+=1;continue
        if x<=0:audit['zero_capacity']+=1;continue
        if y>x:audit['occupied_exceeds_available']+=1;continue
        series[code,sector][q]=(x,y)
    audit['usable_pairs']=sum(map(len,series.values()));audit['series']=len(series)
    audit['sectors']=sorted({s for _,s in series});return series,audit


def partition(code,q):
    held=int(hashlib.sha256(('kh03-v1|'+code).encode()).hexdigest()[:8],16)%5==0
    if held:return 'heldout_org' if q>=2025*4 else None
    return 'development' if q<2023*4 else 'calibration' if q<2025*4 else 'later_time'


def examples(series):
    rows=[]
    for (code,sector),values in sorted(series.items()):
        for q,(a,o) in sorted(values.items()):
            if any(t not in values for t in range(q-4,q)):continue
            split=partition(code,q)
            if split is None:continue
            past=[values[t] for t in range(q-4,q)];scale=mean(v[0] for v in past)
            if scale<=0:continue
            f=[1.,*[x/scale for pair in past for x in pair],math.sin((q%4)*math.pi/2),math.cos((q%4)*math.pi/2)]
            rows.append(dict(features=f,target=[a/scale,o/scale],scale=scale,split=split,group=digest(code),quarter=q))
    return rows


def forward(model,x):
    h=[math.tanh(sum(a*b for a,b in zip(w,x))) for w in model['w1']] if model['hidden'] else x
    return h,[sum(a*b for a,b in zip(w,h))+b for w,b in zip(model['w2'],model['bias'])]


def fit(rows,hidden):
    if not rows or any(r['split']!='development' for r in rows) or hidden not in (0,8):raise ValueError('development and valid width required')
    rng=random.Random(7139);n=len(rows[0]['features']);width=hidden or n
    model=dict(hidden=hidden,w1=[[rng.uniform(-.1,.1) for _ in range(n)] for _ in range(hidden)],w2=[[rng.uniform(-.1,.1) for _ in range(width)] for _ in range(2)],bias=[1.,.8])
    for _ in range(12):
        order=list(range(len(rows)));rng.shuffle(order)
        for j in order:
            x=rows[j]['features'];y=rows[j]['target'];h,p=forward(model,x);err=[max(-4.,min(4.,a-b)) for a,b in zip(p,y)]
            back=[(1-v*v)*sum(e*w[i] for e,w in zip(err,model['w2'])) for i,v in enumerate(h)] if hidden else []
            for k,e in enumerate(err):
                model['bias'][k]-=.005*e;model['w2'][k]=[w-.005*e*v for w,v in zip(model['w2'][k],h)]
            for k,e in enumerate(back):model['w1'][k]=[w-.005*e*v for w,v in zip(model['w1'][k],x)]
    return model


def evaluate(rows):
    dev=[r for r in rows if r['split']=='development'];models={a:fit(dev,k) for a,k in [('linear',0),('bottleneck',8)]}
    out=dict(development=len(dev),model_sha256=digest(models))
    for split in ('calibration','later_time','heldout_org'):
        rs=[r for r in rows if r['split']==split]
        if not rs:out[split]=None;continue
        arms={}
        for arm in ('last','seasonal',*models):
            pred=[r['features'][7:9] if arm=='last' else r['features'][1:3] if arm=='seasonal' else forward(models[arm],r['features'])[1] for r in rs]
            errors=[abs(a-b) for r,p in zip(rs,pred) for a,b in zip(r['target'],p)]
            arms[arm]=dict(scaled_mae=mean(errors),raw_quantity_mae=mean(abs(a-b)*r['scale'] for r,p in zip(rs,pred) for a,b in zip(r['target'],p)),constraint_violations=sum(a<0 or b<0 or b>a for a,b in pred),prediction_sha256=digest(pred))
        out[split]=dict(n=len(rs),groups=len({r.get('group','fixture') for r in rs}),arms=arms)
    return out


def acquire(name):
    size,sha=PINS[name]
    with urlopen(URL+name+'-Overnight-only.csv',timeout=90) as f:raw=f.read(size+1)
    if len(raw)!=size or hashlib.sha256(raw).hexdigest()!=sha:raise ValueError('source snapshot changed')
    return raw


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--revision',required=True);args=p.parse_args();stage='acquisition'
    try:
        if not re.fullmatch(r'[0-9a-f]{40}',args.revision):raise ValueError('invalid revision')
        a,o=acquire('Available'),acquire('Occupied');stage='join';series,audit=join(a,o);stage='benchmark';rows=examples(series);result=dict(scope='passive_source_trajectory_forecast_only',source_commit=args.revision,pins=PINS,audit=audit,partition_sha256=digest(rows),results=evaluate(rows),limitations=['reported quarterly quantities not causal effect or real-time data','administrative organisation codes, not verified stable sites','revised retrospective source, no vintage validation','scale normalized by preceding four quarters only','missing/anomalous pairs excluded with counts','no clinical or institutional acceptance'])
    except Exception as e:
        args.output.write_text(json.dumps(dict(status='failed',stage=stage,error_type=type(e).__name__))+'\n');raise SystemExit(1) from None
    args.output.write_text(json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+'\n')


if __name__=='__main__':main()
