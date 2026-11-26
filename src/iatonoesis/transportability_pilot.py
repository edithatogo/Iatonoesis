"""Synthetic target-performance estimation; explicit invisible outcome-shift control."""
import argparse
import json
import math
import random
from pathlib import Path
from statistics import mean, pstdev

from .temporal_information import generate, history_features, ridge, dot
from .metric_extensions import conformal_radius
from .run_contracts import canonical_sha256 as digest

SOURCE_SEED = 7139
N = 64
ARMS = ('source_constant', 'meta_mean', 'meta_knn', 'meta_ridge')


def environment(seed, n, missing, noise, drift, hidden_shift=0.):
    rng = random.Random(seed)
    rows = []
    for _ in range(n):
        regime = rng.randrange(2)
        trend = rng.gauss(.18+.25*regime+drift,.35)
        latent = rng.gauss(0,1.5)
        history = []
        for t in range(6):
            latent = .86*latent+trend+rng.gauss(0,noise)
            measured = latent+rng.gauss(0,.3)
            observed = t==0 or rng.random()>min(.9,missing+.17*regime)
            history.append(dict(t=t,value=measured if observed else None))
        latent = .86*latent+trend+rng.gauss(0,noise)
        target = latent+rng.gauss(0,.3)+hidden_shift
        rows.append(dict(visible=dict(history=history,regime=regime),target=target))
    return rows


def features(visible):
    f = [history_features(r['history'],r['regime'],{}) for r in visible]
    return [mean(x[2] for x in f),pstdev(x[2] for x in f),mean(x[5] for x in f),
            mean(abs(x[3]) for x in f),mean(x[4] for x in f),mean(x[1] for x in f)]


def actual(rows, weights, radius):
    residuals = [abs(r['target']-dot(weights,history_features(r['visible']['history'],r['visible']['regime'],{})))
                 for r in rows]
    return dict(mae=mean(residuals),coverage=mean(x<=radius for x in residuals))


def fit_assessors(rows):
    if not rows or any(r['split']!='development' for r in rows):
        raise ValueError('development environments only')
    center = [mean(col) for col in zip(*(r['feature'] for r in rows))]
    scale = [max(pstdev(col),1e-6) for col in zip(*(r['feature'] for r in rows))]
    def standard(f):
        return [(x-c)/s for x,c,s in zip(f,center,scale)]
    data = [(standard(r['feature']),r['mae'],r['coverage']) for r in rows]
    models = {k:ridge([([1.,*f],r[k]) for (f,_,_),r in zip(data,rows)],penalty=1.) for k in ('mae','coverage')}
    return dict(center=center,scale=scale,data=data,models=models)


def estimate(f, fitted, source):
    standardized = [(x-c)/s for x,c,s in zip(f,fitted['center'],fitted['scale'])]
    data = fitted['data']
    nearest = sorted(data,key=lambda r:sum((a-b)**2 for a,b in zip(r[0],standardized)))[:3]
    clip = lambda k,x: min(1.,max(0.,x)) if k=='coverage' else max(0.,x)
    return {'source_constant':dict(source),
            'meta_mean':{k:mean(r[j] for r in data) for j,k in enumerate(('mae','coverage'),1)},
            'meta_knn':{k:mean(r[j] for r in nearest) for j,k in enumerate(('mae','coverage'),1)},
            'meta_ridge':{k:clip(k,dot(fitted['models'][k],[1.,*standardized])) for k in ('mae','coverage')}}


def spec(split,i):
    seed = {'development':18000,'calibration':18100,'test':18200}[split]+i
    if split=='test':
        return seed,.22+.045*(i%5),.5+.11*(i%4),-.35+.19*(i%5)
    level = .05*(i//3+1)+(.02 if split=='calibration' else 0.)
    missing,noise,drift = .18,.45,0.
    if i%3==0: missing += level
    if i%3==1: noise += 1.6*level
    if i%3==2: drift += level*(-1 if i%2 else 1)
    return seed,missing,noise,drift


def run():
    source_rows = generate(SOURCE_SEED)
    dev = [r for r in source_rows if r['split']=='development']
    cal = [r for r in source_rows if r['split']=='calibration']
    weights = ridge([(history_features(r['history'],r['regime'],{}),r['target']) for r in dev])
    err = [abs(r['target']-dot(weights,history_features(r['history'],r['regime'],{}))) for r in cal]
    radius = conformal_radius(err)
    source = dict(mae=mean(err),coverage=mean(x<=radius for x in err))
    meta = {p:[] for p in ('development','calibration','test')}
    for split, group in meta.items():
        for i in range(20):
            seed,m,n,d = spec(split,i)
            rows = environment(seed,N,m,n,d)
            f = features([r['visible'] for r in rows])
            group.append(dict(id=f'{split}-{i:02}',split=split,feature=f,**actual(rows,weights,radius)))
    model = fit_assessors(meta['development'])
    for split in ('calibration','test'):
        for row in meta[split]:
            row['estimates'] = estimate(row['feature'],model,source)
    intervals = {a:{k:conformal_radius([abs(r[k]-r['estimates'][a][k]) for r in meta['calibration']])
                    for k in ('mae','coverage')} for a in ARMS}
    metrics = {}
    for arm in ARMS:
        e = {k:[abs(r[k]-r['estimates'][arm][k]) for r in meta['test']] for k in ('mae','coverage')}
        metrics[arm] = dict(n=len(meta['test']),mae_estimation_mae=mean(e['mae']),
            coverage_estimation_mae=mean(e['coverage']),mae_interval_radius=intervals[arm]['mae'],
            coverage_interval_radius=intervals[arm]['coverage'],
            mae_interval_observed=mean(x<=intervals[arm]['mae'] for x in e['mae']),
            coverage_interval_observed=mean(x<=intervals[arm]['coverage'] for x in e['coverage']))
    base = environment(18300,N,.3,.6,.2)
    hidden = environment(18300,N,.3,.6,.2,3.)
    va,vb = ([r['visible'] for r in x] for x in (base,hidden))
    ae,be = estimate(features(va),model,source),estimate(features(vb),model,source)
    aa,bb = actual(base,weights,radius),actual(hidden,weights,radius)
    return dict(version='0.1.0',scope='synthetic_only',task='T18.004',source_seed=SOURCE_SEED,
                source_calibration=source,source_interval_radius=radius,source_model_sha256=digest(weights),
                meta_model_sha256=digest(model),counts={k:len(v) for k,v in meta.items()},subjects_per_environment=N,
                meta_split={k:[r['id'] for r in v] for k,v in meta.items()},
                meta_dataset_sha256=digest({k:[{z:r[z] for z in ('id','feature','mae','coverage')} for r in v] for k,v in meta.items()}),
                metrics=metrics,test=meta['test'],negative_control=dict(visible_sha256_equal=digest(va)==digest(vb),
                    estimates_equal=ae==be,base_actual=aa,shift_actual=bb,estimates=ae,mae_difference=bb['mae']-aa['mae']))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(run(),sort_keys=True,separators=(',',':'),allow_nan=False)+'\n')


if __name__=='__main__':
    main()
