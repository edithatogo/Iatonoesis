"""T15/T16 exploratory synthetic measurement replay; never clinical inference."""
import argparse
import itertools
import json
import math
import random
from pathlib import Path

from .metric_extensions import continuous, conformal_radius, paired_mean_difference
from .run_contracts import canonical_sha256 as digest, validate_experiment

SEED = 7139
CANDIDATES = (0, 1, 2)
MASKS = tuple(s for n in range(4) for s in itertools.combinations(CANDIDATES, n))
POLICIES = ('fixed', 'regime_greedy', 'context_learned')


def generate(seed=SEED):
    rng = random.Random(seed)
    rows = []
    for split, setting, count in (('development','source',480), ('calibration','calibration',160),
                                  ('test','matched',120), ('test','shifted',120)):
        shift = setting == 'shifted'
        for i in range(count):
            regime = rng.randrange(2)
            drift = rng.gauss(.18 + .25*regime + .25*shift, .35)
            latent = rng.gauss(0, 1.5)
            history = []
            for t in range(6):
                latent = .86*latent + drift + rng.gauss(0,.45+.2*shift)
                measured = latent + rng.gauss(0,.3)
                observed = t == 0 or rng.random() > (.18+.17*regime+.12*shift)
                history.append(dict(t=t, value=measured if observed else None))
            latent = .86*latent + drift + rng.gauss(0,.45+.2*shift)
            target = latent + rng.gauss(0,.3)
            # Three optional current measurements with regime-dependent reliability.
            aux = [latent+rng.gauss(0,.25+1.1*regime+.25*shift),
                   latent+rng.gauss(0,1.25-1.0*regime+.35*shift),
                   latent+.7*drift+rng.gauss(0,.7+.25*shift)]
            rows.append(dict(id=f'{setting}-{i:04}', split=split, setting=setting,
                             regime=regime, history=history, aux=aux, target=target))
    return rows


def observed_history(history):
    values = [(r['t'], r['value']) for r in history if r['value'] is not None]
    if not values or any(t < 0 or t >= 6 for t, _ in values):
        raise ValueError('past observations required')
    return values


def history_features(history, regime, observed):
    values = observed_history(history)
    t, last = values[-1]
    slope = (last-values[0][1])/max(1,t-values[0][0])
    return (1., float(regime), last, slope, (6-t)/6, len(values)/6,
            sum(v for _,v in values)/len(values),
            *(float(i in observed) for i in CANDIDATES),
            *(observed.get(i,0.) for i in CANDIDATES))


def ridge(rows, penalty=1.):
    n = len(rows[0][0])
    a = [[penalty*float(i==j) for j in range(n)]+[0.] for i in range(n)]
    for f,y in rows:
        for i in range(n):
            for j in range(n):
                a[i][j] += f[i]*f[j]
            a[i][-1] += f[i]*y
    for i in range(n):
        pivot = max(range(i,n),key=lambda j:abs(a[j][i]))
        a[i],a[pivot] = a[pivot],a[i]
        v = a[i][i]
        a[i] = [x/v for x in a[i]]
        for j in range(n):
            if j != i:
                v = a[j][i]
                a[j] = [x-v*y for x,y in zip(a[j],a[i])]
    return tuple(r[-1] for r in a)


def dot(w,f):
    return sum(a*b for a,b in zip(w,f))


def subset(row, mask):
    return {i:row['aux'][i] for i in mask}


def fit_models(rows):
    if not rows or any(r['split']!='development' for r in rows):
        raise ValueError('fit requires development subjects only')
    return {m:ridge([(history_features(r['history'],r['regime'],subset(r,m)),r['target'])
                     for r in rows]) for m in MASKS}


def predict(models, history, regime, observed):
    return dot(models[tuple(sorted(observed))], history_features(history,regime,observed))


def train_policies(rows):
    if not rows or any(r['split']!='development' for r in rows):
        raise ValueError('fit requires development subjects only')
    labels = {(m,a):[] for m in MASKS for a in CANDIDATES if a not in m}
    for fold in range(4):
        models = fit_models([r for j,r in enumerate(rows) if j%4!=fold])
        for j,r in enumerate(rows):
            if j%4!=fold:
                continue
            h,g,y = r['history'],r['regime'],r['target']
            for m,a in labels:
                obs = subset(r,m)
                before = predict(models,h,g,obs)
                after = predict(models,h,g,subset(r,(*m,a)))
                gain = (y-before)**2-(y-after)**2
                labels[m,a].append((history_features(h,g,obs),gain,g))
    fixed = sorted(CANDIDATES,key=lambda a:(-sum(y for _,y,_ in labels[(),a])/len(rows),a))
    means = {(m,a,g):sum(y for _,y,r in labels[m,a] if r==g)/sum(r==g for _,_,r in labels[m,a])
             for m,a in labels for g in (0,1)}
    learned = {key:ridge([(f,y) for f,y,_ in values]) for key,values in labels.items()}
    return dict(fixed=fixed, means=means, learned=learned,
                training_labels=sum(len(v) for v in labels.values()))


def select_action(policy, models, history, regime, observed):
    remaining = [a for a in CANDIDATES if a not in observed]
    if not remaining:
        raise ValueError('no remaining action')
    if policy=='fixed':
        return next(a for a in models['fixed'] if a in remaining)
    mask = tuple(sorted(observed))
    if policy=='regime_greedy':
        return max(remaining,key=lambda a:(models['means'][mask,a,regime],-a))
    if policy=='context_learned':
        f = history_features(history,regime,observed)
        return max(remaining,key=lambda a:(dot(models['learned'][mask,a],f),-a))
    raise ValueError('unknown policy')


def reveal_sequence(history, regime, policy, reveal, budget):
    if type(budget) is not int or not 0 <= budget <= len(CANDIDATES):
        raise ValueError('invalid budget')
    obs, trace = {}, [{}]
    for _ in range(budget):
        action = policy(history,regime,dict(obs))
        if type(action) is not int or action not in CANDIDATES or action in obs:
            raise ValueError('invalid or repeated action')
        value = reveal(action)
        if type(value) not in (float,int) or not math.isfinite(value):
            raise ValueError('invalid acquired value')
        obs[action] = value
        trace.append(dict(obs))
    return trace


def state_predictions(row, models, mean):
    h,g = row['history'],row['regime']
    obs = observed_history(h)
    t,last = obs[-1]
    slope = (last-obs[0][1])/max(1,t-obs[0][0])
    return dict(mean=mean, last=last, trend=last+max(-1.,min(1.,slope))*(6-t),
                ridge=predict(models,h,g,{}))


def acquisition_predictions(row, models, policies):
    h,g = row['history'],row['regime']
    arms = {}
    for name in POLICIES:
        states = reveal_sequence(h,g,lambda hist,reg,obs:select_action(name,policies,hist,reg,obs),
                                 lambda a:row['aux'][a],3)
        actions = [next(iter(set(b)-set(a))) for a,b in zip(states,states[1:])]
        arms[name] = dict(actions=actions,predictions=[predict(models,h,g,s) for s in states])
    return arms


def score(rows, cal, arms, *, acquisition=False):
    out = {}
    for arm in arms:
        budgets = range(4) if acquisition else (0,)
        by_budget = {}
        for b in budgets:
            def pred(r):
                v = r['arms'][arm]
                return v['predictions'][b] if acquisition else v
            radius = conformal_radius([abs(r['target']-pred(r)) for r in cal])
            groups = {}
            for name in ('all','matched','shifted'):
                group = [r for r in rows if name=='all' or r['setting']==name]
                groups[name] = continuous([r['target'] for r in group], [pred(r) for r in group],radius=radius)
            by_budget[str(b)] = groups
        out[arm] = by_budget if acquisition else by_budget['0']
    return out


def run(seed=SEED):
    rows = generate(seed)
    partitions = {p:[r for r in rows if r['split']==p] for p in ('development','calibration','test')}
    # Hash distinct raw input, reference and split objects. Hidden candidate values
    # belong to the replay harness, never to the policy's observation interface.
    inputs = {r['id']:{k:r[k] for k in ('history','regime','aux','setting')} for r in rows}
    refs = {r['id']:r['target'] for r in rows}
    split = {r['id']:r['split'] for r in rows}
    # Reuse the canonical structural contracts, but keep continuous results separate
    # from set/classification denominators. Only the synthetic generator's rights are asserted.
    data = dict(schema_version='0.1.0', dataset_id='synthetic-temporal-v0.1.0', kind='synthetic',
                source='repository-authored synthetic generator', revision='0.1.0', sha256=digest(inputs),
                rights=dict(status='approved', licence='MIT', evidence='repository-authored synthetic values only'),
                reference=dict(kind='deterministic_oracle', revision='0.1.0', sha256=digest(refs)),
                grouping_keys=['subject'], rows=[dict(id=r['id'],split=r['split'],groups={'subject':r['id']}) for r in rows])
    experiments = []
    for task, metric, specs in (
        ('T15.001','mae', [('mean','deterministic'),('last','deterministic'),('trend','deterministic'),('ridge','classical')]),
        ('T16.001','mse_at_1', [('fixed','deterministic'),('regime_greedy','classical'),('context_learned','classical')]),
    ):
        exp = dict(schema_version='0.1.0',experiment_id=task+'-synthetic-v0.1.0',track_task=task,
                   dataset_id=data['dataset_id'],dataset_sha256=data['sha256'],reference_sha256=data['reference']['sha256'],
                   split='test',case_ids=[r['id'] for r in partitions['test']],primary_metric=metric,unit='synthetic_subject',seed=seed,
                   arms=[dict(id=a,role=b) for a,b in specs],budget=dict(max_cases=len(partitions['test']),max_seconds=30),
                   claim_boundary='synthetic_only')
        validate_experiment(exp,data)
        experiments.append(exp)
    dev = partitions['development']
    models = fit_models(dev)
    policies = train_policies(dev)
    mean = sum(r['target'] for r in dev)/len(dev)
    def evaluation(part,fn):
        return [dict(id=r['id'],setting=r['setting'],target=r['target'],arms=fn(r)) for r in partitions[part]]
    state_test,state_cal = (evaluation(p,lambda r:state_predictions(r,models,mean)) for p in ('test','calibration'))
    acq_test,acq_cal = (evaluation(p,lambda r:acquisition_predictions(r,models,policies)) for p in ('test','calibration'))
    model_record = dict(state={str(k):list(v) for k,v in models.items()}, fixed=policies['fixed'],
                        means={str(k):v for k,v in policies['means'].items()},
                        gain={str(k):list(v) for k,v in policies['learned'].items()})
    contrasts = {}
    for a,b in [('last','ridge'),('trend','ridge')]:
        contrasts[a+'__'+b] = paired_mean_difference(
            [abs(r['target']-r['arms'][a]) for r in state_test],
            [abs(r['target']-r['arms'][b]) for r in state_test],seed=seed)
    for a in ('fixed','regime_greedy'):
        for budget in (1,2):
            contrasts[a+'__context_learned_at_'+str(budget)] = paired_mean_difference(
                [(r['target']-r['arms'][a]['predictions'][budget])**2 for r in acq_test],
                [(r['target']-r['arms']['context_learned']['predictions'][budget])**2 for r in acq_test],seed=seed)
    return dict(schema_version='0.1.0',tasks=['T15.001','T16.001'],scope='synthetic_only',seed=seed,
                counts={p:len(rs) for p,rs in partitions.items()}, training_labels=policies['training_labels'],
                dataset_manifest=data,experiments=experiments,descriptive_paired_bootstrap=contrasts,
                manifest=dict(inputs_sha256=digest(inputs),reference_sha256=digest(refs),
                              dataset_manifest_sha256=digest(data),experiment_sha256=[digest(e) for e in experiments],
                              split_sha256=digest(split),models_sha256=digest(model_record),
                              state_predictions_sha256=digest(state_test),acquisition_predictions_sha256=digest(acq_test)),
                state=dict(rows=state_test,metrics=score(state_test,state_cal,('mean','last','trend','ridge'))),
                acquisition=dict(rows=acq_test,metrics=score(acq_test,acq_cal,POLICIES,acquisition=True)))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    args.output.write_text(json.dumps(run(),sort_keys=True,separators=(',',':'),allow_nan=False)+'\n')


if __name__=='__main__':
    main()
