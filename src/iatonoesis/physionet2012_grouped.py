"""Prespecified duplicate quarantine and first-recording hazard comparison."""
import argparse
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from . import physionet2012 as p


def quarantine(entries):
    identities=defaultdict(list);contents=defaultdict(list);parent={}
    for cohort,key,content in entries:
        node=(cohort,key)
        if node in parent: raise ValueError('duplicate archive identity')
        parent[node]=node;identities[key].append(node);contents[content].append(node)
    def root(x):
        while x!=parent[x]:
            parent[x]=parent[parent[x]];x=parent[x]
        return x
    for groups in (identities,contents):
        for nodes in groups.values():
            for node in nodes[1:]:
                a,b=sorted((root(nodes[0]),root(node)));parent[b]=a
    components=defaultdict(list)
    for node in sorted(parent): components[root(node)].append(node)
    blocked={node for group in components.values() if len(group)>1 for node in group}
    audit=dict(identity_duplicate_groups=sum(len(v)>1 for v in identities.values()),
               content_duplicate_groups=sum(len(v)>1 for v in contents.values()),
               cross_cohort_components=sum(len({c for c,_ in v})>1 for v in components.values()),
               component_size_histogram=dict(Counter(str(len(v)) for v in components.values())),
               quarantined_records=len(blocked),quarantined_by_cohort=dict(Counter(c for c,_ in blocked)))
    return blocked,audit


def freeze_grouped(archives,expected=4000):
    if set(archives)!=set(p.SIZES): raise ValueError('missing cohort')
    data={c:p.unpack(archives[c],c,expected) for c in ('A','B')}
    blocked,audit=quarantine([(c,k,r['content_sha256']) for c,rs in data.items() for k,r in rs.items()])
    rows=[];manifest=[];counts={}
    for c,rs in data.items():
        parts=Counter();elig=Counter()
        for k,r in sorted(rs.items()):
            split='quarantine' if (c,k) in blocked else 'test' if c=='B' else 'calibration' if int(p.sha((p.SEED+'|'+k).encode())[:8],16)%5==0 else 'development'
            parts[split]+=1;manifest.append([c,k,r['raw_sha256'],r['content_sha256'],split])
            if split!='quarantine':
                elig.update(r['targets'].keys());rows.append(dict(id=p.sha((p.SEED+'|'+k).encode()),split=split,**r))
        counts[c]=dict(records=len(rs),retained=len(rs)-parts['quarantine'],partitions=dict(parts),eligible_observed_targets=dict(elig),archive_sha256=p.sha(archives[c]))
    if len({r['id'] for r in rows})!=len(rows) or len({r['content_sha256'] for r in rows})!=len(rows): raise ValueError('retained duplicate')
    return dict(rows=rows,audit=audit,counts=counts,manifest_sha256=p.digest(manifest))


def features(r,marked):
    base=p.observation_features(r,False)
    if not marked: return base
    return base+[min(len(ts),12)/12 for ts in r['mark_minutes']]+[(360-max(ts))/360 if ts else 1. for ts in r['mark_minutes']]


def fit_rate(dev,marked):
    # Time to first valid HR, in hours; discrete minute resolution is approximated
    # by event at the midpoint of its minute. Censor at 3h. Penalised exponential likelihood.
    data=[(features(r,marked),int(r['first_hr_minute'] is not None),3. if r['first_hr_minute'] is None else (r['first_hr_minute']+.5)/60) for r in dev]
    w=[0.]*len(data[0][0]);w[0]=math.log((sum(y for _,y,_ in data)+.5)/(sum(t for _,_,t in data)+.5))
    for _ in range(240):
        gradient=[0.]*len(w)
        for x,y,t in data:
            error=t*math.exp(max(-8.,min(5.,sum(a*b for a,b in zip(x,w)))))-y
            for i,v in enumerate(x):gradient[i]+=error*v
        w=[a-.15*(g/len(data)+(.01*a if i else 0.)) for i,(a,g) in enumerate(zip(w,gradient))]
    return w


def hazard_benchmark(rows):
    dev=[r for r in rows if r['split']=='development'];test=[r for r in rows if r['split']=='test']
    if not dev or not test: raise ValueError('missing split')
    n=len(test);base=(sum(r['first_hr_minute'] is not None for r in dev)+.5)/(sum(3. if r['first_hr_minute'] is None else (r['first_hr_minute']+.5)/60 for r in dev)+.5)
    weights={a:fit_rate(dev,m) for a,m in [('timing_exponential',False),('marked_exponential',True)]}
    # Strong empirical discrete first-event baseline conditioned on history count and recency.
    def bucket(r):return tuple(p.observation_features(r,False)[1:3])
    def event_bin(r):return 3 if r['first_hr_minute'] is None else r['first_hr_minute']//60
    pools=defaultdict(list)
    for r in dev:pools[bucket(r)].append(event_bin(r))
    overall=Counter(event_bin(r) for r in dev);arms={}
    for arm in ('constant_exponential','empirical_bucket',*weights):
        probs=[]
        for r in test:
            if arm=='empirical_bucket':
                v=Counter(pools[bucket(r)]);q=[(v[i]+10*(overall[i]+.5)/(len(dev)+2))/(sum(v.values())+10) for i in range(4)]
            else:
                rate=base if arm=='constant_exponential' else math.exp(max(-8.,min(5.,sum(a*b for a,b in zip(weights[arm],features(r,arm=='marked_exponential'))))))
                q=[math.exp(-rate*i)-math.exp(-rate*(i+1)) for i in range(3)]+[math.exp(-rate*3)]
            probs.append(q)
        cum=[[sum(q[:i]) for q in probs] for i in (1,2,3)]
        arms[arm]=dict(brier_180=mean((float(event_bin(r)<3)-v)**2 for r,v in zip(test,cum[-1])),hour_bin_log_loss=mean(-math.log(max(1e-12,q[event_bin(r)])) for r,q in zip(test,probs)),mean_event_probability=[mean(v) for v in cum],prediction_sha256=p.digest(probs))
    return dict(n=n,development=len(dev),arms=arms,model_sha256=p.digest(dict(weights=weights,base=base,overall=overall,pools=sorted((k,v) for k,v in pools.items()))))


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--revision',required=True);args=ap.parse_args();stage='configuration'
    try:
        if not re.fullmatch(r'[0-9a-f]{40}',args.revision):raise ValueError('invalid revision')
        stage='acquisition';archives={c:p.acquire(c) for c in p.SIZES}
        stage='grouped_freeze';f=freeze_grouped(archives)
        stage='benchmark';result=dict(scope='duplicate_quarantined_public_recording_process_benchmark',source_commit=args.revision,source_manifest_sha256=f['manifest_sha256'],audit=f['audit'],counts=f['counts'],observation=p.observation_benchmark(f['rows']),hazard=hazard_benchmark(f['rows']),limits=['quarantine all non-singleton exact-content/identity components; no cross-cohort movement','source order-sensitive exact content, not near-duplicate or patient-linkage proof','A/B not hospitals','hour-bin score for first recording, not clinical need or full multivariate point process','no clinical or institutional acceptance'])
    except Exception as e:
        args.output.write_text(json.dumps(dict(status='failed',stage=stage,error_type=type(e).__name__,reason=p.failure_reason(e),scope='aggregate_only'))+'\n');raise SystemExit(1) from None
    args.output.write_text(json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+'\n')


if __name__=='__main__':main()
