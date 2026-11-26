"""Fresh bounded public measured-value replication; aggregate-only receipts."""
import argparse
import json
import math
import tempfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from statistics import mean
from urllib.parse import quote

from . import measured_pilot as prior, physionet_audit as source
from .metric_extensions import continuous, conformal_radius, paired_mean_difference
from .run_contracts import canonical_sha256 as digest
from .typed_results import run_typed
from .temporal_information import dot

SEED=7139
HORIZONS=(1,3,6)
ARMS=('mean','last','ar1','kalman','ridge','temporal_mlp')
POLICIES=('fixed','greedy','context','context_stop')
COSTS={'equal':(1,1,1),'resp_costly':(1,3,1),'map_costly':(3,1,1)}
CAPS=(0,1,2,3,5)
EXPECTED={'A':'dfb29db1499c359a8fcdd4fedf9fe6d1942c57f2ef4f93cf5a469940758a3433',
          'B':'c52f3eb06ee68b8859d47aee485803b0ecfce773a8e5b38e64621cc7f3b58c9a'}
STRATA=('all','recency_0','recency_1_2','recency_3_plus','missing_0','missing_1_2','missing_3_plus')


def new_keys(keys,old=128,count=256):
    if type(old) is not int or type(count) is not int or old<0 or count<1:
        raise ValueError('invalid sample range')
    return source.sample_keys(keys,old+count)[old:]


def case_horizon(raw,horizon):
    if type(horizon) is not int or horizon not in HORIZONS:
        raise ValueError('invalid horizon')
    source.inspect_record(raw)
    idx=source.HEADER.index('HR');time=source.HEADER.index('ICULOS');history={}
    for line in raw.decode('ascii').splitlines()[1:]:
        v=line.split('|');t=int(float(v[time]));y=None if v[idx]=='NaN' else float(v[idx])
        h=[history.get(j) for j in range(t-horizon-5,t-horizon+1)]
        if t>=6+horizon and y is not None and any(x is not None for x in h):
            return dict(cutoff=t,target=y,history=h)
        history[t]=y
    return None


def strata(history):
    gap=next(i for i,x in enumerate(reversed(history)) if x is not None)
    missing=sum(x is None for x in history)
    def category(n): return '0' if n==0 else '1_2' if n<=2 else '3_plus'
    return 'recency_'+category(gap),'missing_'+category(missing)


def freeze():
    inv={c:source.inventory(c) for c in ('A','B')}
    if {c:source.canonical(sorted(keys)) for c,keys in inv.items()}!=EXPECTED or set(inv['A'])&set(inv['B']):
        raise ValueError('changed or overlapping source inventory')
    if {c:len(keys) for c,keys in inv.items()}!=source.EXPECTED:
        raise ValueError('source count mismatch')
    rows={str(h):[] for h in HORIZONS};rows['acquisition']=[]
    manifest=[];seen=set()
    for c in ('A','B'):
        keys=new_keys(inv[c])
        def fetch(k): return source.get(source.SOURCE+quote(source.PREFIX+c+'/'+k,safe='/'),2_000_000)
        with ThreadPoolExecutor(max_workers=8) as pool:
            for k,raw in zip(keys,pool.map(fetch,keys)):
                sha=source.sha(raw)
                if sha in seen:
                    raise ValueError('duplicate new sample content')
                seen.add(sha);part=source.partition(c,k)
                manifest.append((c,k,sha,len(raw),part))
                ident=source.sha((source.SEED+'|'+c+'|'+k).encode())
                for h in HORIZONS:
                    row=case_horizon(raw,h)
                    if row is not None: rows[str(h)].append(dict(id=ident,split=part,**row))
                row=prior.case(raw,True)
                if row is not None: rows['acquisition'].append(dict(id=ident,split=part,**row))
    return rows,source.canonical(manifest)


def forecast(model,arm,hist,horizon):
    v=prior.state_value(model,arm,hist)
    if arm in ('ar1','kalman'):
        mu=model['norm'][0]
        return mu+model['phi']**(horizon-1)*(v-mu)
    return v


def cost_acquire(row,model,policy_model,policy,costs,cap):
    if len(costs)!=3 or any(type(c) is not int or c<=0 for c in costs) or type(cap) is not int or cap<0 or policy not in POLICIES:
        raise ValueError('invalid cost or policy')
    h=row['history'];obs={};spent=0
    while True:
        left=[i for i in prior.CANDIDATES if i not in obs and costs[i]<=cap-spent]
        if not left:
            break
        s=tuple(sorted(obs))
        if policy=='fixed':
            i=next(i for i in policy_model['fixed'] if i in left)
        else:
            def gain(i):
                if policy=='greedy': return policy_model['averages'][s,i]
                return dot(policy_model['weights'][s,i],prior.features(h,obs,model[0]))
            i=max(left,key=lambda i:(gain(i)/costs[i],-i))
            if policy=='context_stop' and gain(i)<=0:
                break
        obs[i]=row['aux'][i];spent+=costs[i]
    return dict(prediction=prior.reconstruction(model,h,obs),spent=spent,count=len(obs))


def paired(a,b):
    return paired_mean_difference(a,b,seed=SEED,draws=1000) if len(a)>=2 else None


def stratified(rows,predictions,radii):
    out={}
    for group in STRATA:
        ix=[i for i,row in enumerate(rows) if group=='all' or group in strata(row['history'])]
        y=[rows[i]['target'] for i in ix]
        scores={};deltas={}
        for arm,p in predictions.items():
            z=[p[i] for i in ix]
            scores[arm]=continuous(y,z,radius=radii[arm]) if ix else None
            if arm!='last':
                deltas[arm]=paired([abs(rows[i]['target']-predictions['last'][i]) for i in ix],
                                   [abs(rows[i]['target']-p[i]) for i in ix])
        out[group]=dict(n=len(ix),arms=scores,paired=deltas)
    return out


def execute(rows,revision,name,task,arms,predictors,model_hash,intervals):
    inputs={r['id']:{k:r[k] for k in ('history','cutoff','aux') if k in r} for r in rows};refs={r['id']:r['target'] for r in rows}
    data=dict(schema_version='0.1.0',dataset_id=name,kind='public',source='PhysioNet challenge-2019/1.0.0',revision=revision,sha256=digest(inputs),
              rights=dict(status='approved',licence='CC-BY-4.0',evidence='public technical benchmark only; https://physionet.org/content/challenge-2019/1.0.0/'),
              reference=dict(kind='published_labels',revision=revision,sha256=digest(refs)),grouping_keys=['subject'],
              rows=[dict(id=r['id'],split=r['split'],groups={'subject':r['id']}) for r in rows])
    test=[r['id'] for r in rows if r['split']=='test']
    exp=dict(schema_version='0.1.0',experiment_id=name,track_task=task,dataset_id=name,dataset_sha256=data['sha256'],reference_sha256=data['reference']['sha256'],
             split='test',case_ids=test,primary_metric='mae' if intervals else 'mse',metric_kind='continuous',metric_options={'intervals':intervals},
             unit='subject',seed=SEED,arms=[dict(id=a,role='deterministic' if a in ('last','fixed') else 'classical') for a in arms],
             budget=dict(max_cases=len(test),max_seconds=30),claim_boundary='benchmark_only')
    models={a:dict(id=a,revision=revision,licence='MIT',weights_sha256=model_hash) for a in arms if a not in ('last','fixed')}
    result=run_typed(exp,data,inputs,refs,predictors=predictors,models=models,source_commit=revision)
    if any(a['status']!='executed' for a in result['manifest']['arms']):
        raise ValueError('typed benchmark arm failed')
    return result


def evaluate(rows,manifest,revision):
    output=dict(scope='fresh_bounded_public_measured_value_replication',seed=SEED,source_manifest_sha256=manifest,
                inventory_sha256=EXPECTED,state={},acquisition={},
                limitations=['disjoint source keys, cross-sample byte duplicate checks unavailable','A/B not verified sites',
                             'relative cost scenarios are assumptions, not actual clinical costs','paired intervals descriptive, no multiplicity adjustment',
                             'independent clinical reference and institutional determination outstanding'])
    for horizon in HORIZONS:
        rs=rows[str(horizon)]
        dev,cal,test=([r for r in rs if r['split']==p] for p in ('development','calibration','test'))
        model=prior.fit_state(dev);radii={};predictors={}
        for a in ARMS:
            radius=conformal_radius([abs(r['target']-forecast(model,a,r['history'],horizon)) for r in cal])
            radii[a]=radius
            def pred(x,a=a,radius=radius):
                v=forecast(model,a,x['history'],horizon);return dict(value=v,lower=v-radius,upper=v+radius)
            predictors[a]=pred
        result=execute(rs,revision,'fresh-state-h'+str(horizon),'T15.001',ARMS,predictors,digest(model),True)
        predictions={a:[x['prediction']['value'] for x in result['predictions'][a]] for a in ARMS}
        output['state'][str(horizon)]=dict(counts=dict(Counter(r['split'] for r in rs)),receipt=result['manifest'],
                                         strata=stratified(test,predictions,radii))
    rs=rows['acquisition'];dev=[r for r in rs if r['split']=='development'];test=[r for r in rs if r['split']=='test']
    model,policies,n=prior.fit_acquisition(dev)
    h=digest(dict(norm=model[0],subsets=[(list(s),w) for s,w in model[1].items()],
                  averages=[(list(s),i,v) for (s,i),v in policies['averages'].items()],
                  weights=[(list(s),i,v) for (s,i),v in policies['weights'].items()],fixed=policies['fixed']))
    output['acquisition_counts']=dict(Counter(r['split'] for r in rs));output['acquisition_training_labels']=n
    for name,costs in COSTS.items():
        output['acquisition'][name]={}
        for cap in CAPS:
            adapters={a:lambda x,a=a:cost_acquire(x,model,policies,a,costs,cap)['prediction'] for a in POLICIES}
            result=execute(rs,revision,'fresh-acq-'+name+'-'+str(cap),'T16.001',POLICIES,adapters,h,False)
            details={a:[cost_acquire(r,model,policies,a,costs,cap) for r in test] for a in POLICIES}
            losses={a:[(v['prediction']-r['target'])**2 for v,r in zip(details[a],test)] for a in POLICIES}
            stats={a:dict(mean_spend=mean(v['spent'] for v in details[a]),mean_observations=mean(v['count'] for v in details[a]),
                          paired_delta_vs_fixed=paired(losses['fixed'],losses[a])) for a in POLICIES}
            output['acquisition'][name][str(cap)]=dict(costs=costs,receipt=result['manifest'],spend=stats)
    return output


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--revision',required=True);a=p.parse_args()
    try:
        rows,manifest=freeze();result=evaluate(rows,manifest,a.revision)
    except Exception as exc:
        a.output.write_text(json.dumps(dict(status='failed',error_type=type(exc).__name__,scope='aggregate_only'))+'\n')
        raise SystemExit(1) from None
    a.output.write_text(json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+'\n')


if __name__=='__main__':
    main()
