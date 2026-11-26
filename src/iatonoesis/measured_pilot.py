"""Bounded public measured-value benchmark. Keep all records and predictions in memory."""
import argparse
import itertools
import json
import math
import random
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from statistics import mean, pstdev
from urllib.parse import quote

from . import physionet_audit as source
from .metric_extensions import conformal_radius
from .run_contracts import canonical_sha256 as digest
from .temporal_information import ridge, dot
from .typed_results import run_typed

SOURCE_MANIFEST='bd1255b21e0a7dcf8be66d469c5057fc91d1520d8eb5c2552d6deefd8d68c9ee'
SEED=7139
CANDIDATES=(0,1,2)
SUBSETS=tuple(s for n in range(4) for s in itertools.combinations(CANDIDATES,n))


def case(raw, acquisition):
    source.inspect_record(raw)
    cols={k:source.HEADER.index(k) for k in ('ICULOS','HR',*source.AUX)}
    history={}
    for line in raw.decode('ascii').splitlines()[1:]:
        v=line.split('|');t=int(float(v[cols['ICULOS']]))
        def get(k): return None if v[cols[k]]=='NaN' else float(v[cols[k]])
        h=[history.get(j) for j in range(t-6,t)];y=get('HR');aux=[get(k) for k in source.AUX]
        if t>=7 and y is not None and any(x is not None for x in h) and (not acquisition or all(x is not None for x in aux)):
            row=dict(cutoff=t,target=y,history=h)
            if acquisition: row['aux']=aux
            return row
        history[t]=y
    return None


def freeze(inventories,fetch,*,expected_counts=source.EXPECTED,sample_counts=None,expected_manifest=None):
    if set(inventories)!=set(expected_counts) or set(inventories)!= {'A','B'} or set(inventories['A']) & set(inventories['B']):
        raise ValueError('source cohort overlap or missing cohort')
    counts=sample_counts or {'A':128,'B':128};manifest=[];seen=set();rows={'state':[],'acquisition':[]}
    for c in ('A','B'):
        if len(inventories[c])!=expected_counts[c]: raise ValueError('source inventory count mismatch')
        keys=source.sample_keys(inventories[c],counts[c])
        with ThreadPoolExecutor(max_workers=8) as pool:
            for k,raw in zip(keys,pool.map(lambda k:fetch(c,k),keys)):
                h=source.sha(raw)
                if h in seen: raise ValueError('duplicate source content')
                seen.add(h);part=source.partition(c,k);manifest.append((c,k,h,len(raw),part))
                for name in rows:
                    row=case(raw,name=='acquisition')
                    if row is not None:
                        rows[name].append(dict(id=source.sha((source.SEED+'|'+c+'|'+k).encode()),split=part,**row))
    sha=source.canonical(manifest)
    if expected_manifest is not None and sha!=expected_manifest: raise ValueError('source manifest mismatch')
    return dict(source_manifest_sha256=sha,inventory_sha256={c:source.canonical(sorted(v)) for c,v in inventories.items()},rows=rows)


def standard(rows):
    if not rows or any(r['split']!='development' for r in rows): raise ValueError('development subjects only')
    y=[r['target'] for r in rows];mu=mean(y);sd=max(pstdev(y),1.)
    aux=[(mean([r['aux'][i] for r in rows]),max(pstdev([r['aux'][i] for r in rows]),1.)) for i in CANDIDATES] if 'aux' in rows[0] else []
    return mu,sd,aux


def features(history,obs,norm):
    mu,sd,aux=norm;v=[None if x is None else (x-mu)/sd for x in history]
    seen=[(i,x) for i,x in enumerate(v) if x is not None];i,last=seen[-1]
    return [1.,last,(6-i)/6,len(seen)/6,mean(x for _,x in seen),
            *[0. if x is None else x for x in v],*[float(x is not None) for x in v],
            *[float(i in obs) for i in CANDIDATES],*[((obs[i]-aux[i][0])/aux[i][1]) if i in obs else 0. for i in CANDIDATES]]


def train_mlp(rows,norm):
    rng=random.Random(SEED);mu,sd,_=norm
    train=[(features(r['history'],{},norm),(r['target']-mu)/sd) for r in rows]
    n=len(train[0][0]);w=[[rng.uniform(-.1,.1) for _ in range(n)] for _ in range(8)];v=[rng.uniform(-.1,.1) for _ in w];b=0.
    for _ in range(40):
        order=list(range(len(train)));rng.shuffle(order)
        for i in order:
            x,y=train[i];h=[math.tanh(dot(q,x)) for q in w];err=max(-4.,min(4.,b+dot(v,h)-y));old=v[:]
            b-=.01*err
            for j in range(len(v)):
                v[j]-=.01*err*h[j];d=err*old[j]*(1-h[j]**2)
                w[j]=[a-.01*d*k for a,k in zip(w[j],x)]
    return w,v,b


def ar_params(rows,mu):
    pairs=[(a-mu,b-mu) for r in rows for a,b in zip(r['history'],r['history'][1:]) if a is not None and b is not None]
    if not pairs: raise ValueError('insufficient development transition pairs')
    phi=max(-.98,min(.98,sum(a*b for a,b in pairs)/max(1e-6,sum(a*a for a,_ in pairs))))
    var=max(1.,mean((b-phi*a)**2 for a,b in pairs))
    return phi,var


def kalman(history,mu,phi,q,r):
    x=0.;p=q/max(1e-6,1-phi*phi);loss=0.
    for z in history:
        x*=phi;p=phi*phi*p+q
        if z is not None:
            innovation=z-mu-x;s=p+r;loss+=math.log(s)+innovation*innovation/s
            k=p/s;x+=k*innovation;p*=1-k
    return mu+phi*x,loss


def fit_state(rows):
    norm=standard(rows);mu,sd,_=norm;phi,var=ar_params(rows,mu)
    q,r=min(((var*a,var*b) for a in (.25,.5,1.,2.) for b in (.1,.25,.5,1.)),
            key=lambda pair:sum(kalman(row['history'],mu,phi,*pair)[1] for row in rows))
    w=ridge([(features(row['history'],{},norm),(row['target']-mu)/sd) for row in rows],penalty=1.)
    mlp=train_mlp(rows,norm)
    return dict(norm=norm,phi=phi,q=q,r=r,ridge=w,mlp=mlp)


def state_value(model,arm,history):
    mu,sd,_=model['norm'];i,last=next((i,v) for i,v in reversed(list(enumerate(history))) if v is not None)
    if arm=='mean': return mu
    if arm=='last': return last
    if arm=='ar1': return mu+model['phi']**(6-i)*(last-mu)
    if arm=='kalman': return kalman(history,mu,model['phi'],model['q'],model['r'])[0]
    f=features(history,{},model['norm'])
    if arm=='ridge': return mu+sd*dot(model['ridge'],f)
    w,v,b=model['mlp'];return mu+sd*(b+dot(v,[math.tanh(dot(q,f)) for q in w]))


def subset_fit(rows):
    norm=standard(rows);mu,sd,_=norm
    models={s:ridge([(features(r['history'],{i:r['aux'][i] for i in s},norm),(r['target']-mu)/sd) for r in rows],penalty=1.) for s in SUBSETS}
    return norm,models


def reconstruction(model,h,obs):
    norm,models=model;mu,sd,_=norm
    return mu+sd*dot(models[tuple(sorted(obs))],features(h,obs,norm))


def fit_acquisition(rows):
    final=subset_fit(rows);labels={(s,i):[] for s in SUBSETS for i in CANDIDATES if i not in s}
    for fold in range(4):
        model=subset_fit([r for j,r in enumerate(rows) if j%4!=fold])
        for j,r in enumerate(rows):
            if j%4!=fold: continue
            for s,i in labels:
                obs={k:r['aux'][k] for k in s};y=r['target'];h=r['history']
                before=reconstruction(model,h,obs);after=reconstruction(model,h,dict(obs)|{i:r['aux'][i]})
                labels[s,i].append((features(h,obs,final[0]),(y-before)**2-(y-after)**2))
    averages={key:mean(y for _,y in v) for key,v in labels.items()}
    weights={key:ridge(v,penalty=10.) for key,v in labels.items()}
    fixed=sorted(CANDIDATES,key=lambda i:(-averages[(),i],i))
    return final,dict(averages=averages,weights=weights,fixed=fixed),sum(len(v) for v in labels.values())


def choose(policy,policy_model,h,obs,norm):
    left=[i for i in CANDIDATES if i not in obs];s=tuple(sorted(obs))
    if policy=='fixed': return next(i for i in policy_model['fixed'] if i in left)
    if policy=='greedy': return max(left,key=lambda i:(policy_model['averages'][s,i],-i))
    return max(left,key=lambda i:(dot(policy_model['weights'][s,i],features(h,obs,norm)),-i))


def acquire(row,model,policy_model,policy,budget):
    if type(budget) is not int or not 0<=budget<=3: raise ValueError('invalid observation budget')
    obs={};h=row['history']
    for _ in range(budget):
        i=choose(policy,policy_model,h,dict(obs),model[0]);obs[i]=row['aux'][i]
    return reconstruction(model,h,obs)


def evaluate(frozen,revision,*,synthetic=False):
    if not synthetic and frozen.get('source_manifest_sha256')!=SOURCE_MANIFEST: raise ValueError('unverified source manifest')
    output=dict(scope='synthetic_fixture' if synthetic else 'bounded_public_measured_value_technical_benchmark',
                source_manifest_sha256=frozen['source_manifest_sha256'],inventory_sha256=frozen['inventory_sha256'],seed=SEED,
                limitations=['not clinical outcomes or site validation','A/B cohorts not verified institutions','equal unit synthetic acquisition costs, not clinical costs','one eligible cutoff per subject; selection bias','institutional research determination and independent external validation outstanding'])
    def execute(rows,task,name,arms,predictors,model_hash,*,intervals=False):
        inputs={r['id']:{k:r[k] for k in ('cutoff','history','aux') if k in r} for r in rows};refs={r['id']:r['target'] for r in rows}
        data=dict(schema_version='0.1.0',dataset_id=name,kind='synthetic' if synthetic else 'public',source='PhysioNet challenge-2019/1.0.0' if not synthetic else 'authored PSV fixtures',revision=revision,sha256=digest(inputs),rights=dict(status='approved',licence='MIT' if synthetic else 'CC-BY-4.0',evidence='authored fixture' if synthetic else 'https://physionet.org/content/challenge-2019/1.0.0/; public technical benchmark only'),reference=dict(kind='deterministic_oracle' if synthetic else 'published_labels',revision=revision,sha256=digest(refs)),grouping_keys=['subject'],rows=[dict(id=r['id'],split=r['split'],groups={'subject':r['id']}) for r in rows])
        test=[r['id'] for r in rows if r['split']=='test'];exp=dict(schema_version='0.1.0',experiment_id=name,track_task=task,dataset_id=name,dataset_sha256=data['sha256'],reference_sha256=data['reference']['sha256'],split='test',case_ids=test,primary_metric='mae' if intervals else 'mse',metric_kind='continuous',metric_options={'intervals':intervals},unit='subject',seed=SEED,arms=[dict(id=a,role='deterministic' if a in ('last','fixed') else 'classical') for a in arms],budget=dict(max_cases=len(test),max_seconds=30),claim_boundary='synthetic_only' if synthetic else 'benchmark_only')
        models={a:dict(id=a,revision=revision,licence='MIT',weights_sha256=model_hash) for a in arms if a not in ('last','fixed')}
        result=run_typed(exp,data,inputs,refs,predictors=predictors,models=models,source_commit=revision)
        if any(a['status']!='executed' for a in result['manifest']['arms']): raise ValueError('benchmark arm failed')
        return dict(manifest={k:v for k,v in result['manifest'].items() if k!='arms'},arms={a['id']:a for a in result['manifest']['arms']},counts=dict(Counter(r['split'] for r in rows)))
    rows=frozen['rows']['state'];dev=[r for r in rows if r['split']=='development'];cal=[r for r in rows if r['split']=='calibration'];model=fit_state(dev)
    arms=('mean','last','ar1','kalman','ridge','temporal_mlp');predictors={}
    for arm in arms:
        radius=conformal_radius([abs(r['target']-state_value(model,arm,r['history'])) for r in cal])
        def predictor(inp,arm=arm,radius=radius):
            v=state_value(model,arm,inp['history']);return dict(value=v,lower=v-radius,upper=v+radius)
        predictors[arm]=predictor
    output['state']=execute(rows,'T15.001','measured-hr-state-v0.1.0',arms,predictors,digest(model),intervals=True)
    rows=frozen['rows']['acquisition'];dev=[r for r in rows if r['split']=='development'];model,policies,n=fit_acquisition(dev)
    # Canonical internal model digest: tuple-keyed dictionaries rendered as sorted pairs.
    h=digest(dict(norm=model[0],subsets=[(list(s),w) for s,w in model[1].items()],averages=[(list(s),i,v) for (s,i),v in policies['averages'].items()],weights=[(list(s),i,v) for (s,i),v in policies['weights'].items()],fixed=policies['fixed']))
    output['acquisition_training_labels']=n;output['acquisition']={};output['acquisition_receipts']={}
    arms=('fixed','greedy','context')
    for budget in range(4):
        predictors={a:(lambda inp,a=a,budget=budget:acquire(inp,model,policies,a,budget)) for a in arms}
        result=execute(rows,'T16.001','measured-hr-acquisition-'+str(budget)+'-v0.1.0',arms,predictors,h)
        output['acquisition'][str(budget)]=result['arms'];output['acquisition_receipts'][str(budget)]=dict(manifest=result['manifest'],counts=result['counts'])
    return output


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--revision',required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    try:
        frozen=freeze({c:source.inventory(c) for c in ('A','B')},lambda c,k:source.get(source.SOURCE+quote(source.PREFIX+c+'/'+k,safe='/'),2_000_000),expected_manifest=SOURCE_MANIFEST)
        result=evaluate(frozen,args.revision)
    except Exception as exc:
        args.output.write_text(json.dumps(dict(status='failed',reason=type(exc).__name__,scope='aggregate-only measured-value benchmark'))+'\n');raise SystemExit(1) from None
    args.output.write_text(json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+'\n')


if __name__=='__main__': main()
