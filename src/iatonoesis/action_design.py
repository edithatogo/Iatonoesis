"""Finite simulation comparators; no real care or intervention claims."""
import argparse,hashlib,itertools,json,math,random
from functools import lru_cache
from pathlib import Path
from statistics import mean

COST=.03
BUDGET=3


def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def dot(a,b):return sum(x*y for x,y in zip(a,b))


def ridge(rows,penalty=.1):
    n=len(rows[0][0]);m=[[float(i==j)*penalty for j in range(n)]+[0.] for i in range(n)]
    for x,y in rows:
        for i in range(n):
            for j in range(n):m[i][j]+=x[i]*x[j]
            m[i][-1]+=x[i]*y
    for i in range(n):
        j=max(range(i,n),key=lambda j:abs(m[j][i]));m[i],m[j]=m[j],m[i];v=m[i][i];m[i]=[x/v for x in m[i]]
        for j in range(n):
            if j!=i:
                v=m[j][i];m[j]=[a-v*b for a,b in zip(m[j],m[i])]
    return [r[-1] for r in m]


def next_backlog(backlog,demand,capacity,action):return max(0,backlog+demand-capacity-action)
def expected(b,c,a,distribution):return sum(p*next_backlog(b,d,c,a) for d,p in enumerate(distribution))


def distributions(seed,n,shift):
    rng=random.Random(seed);out=[]
    for _ in range(n):
        w=[rng.uniform(.2,2)*(1+i/4 if shift else 1) for i in range(9)];out.append([v/sum(w) for v in w])
    return out


def queue():
    dev=distributions(7139,12,False);test=distributions(7140,6,True)
    def feat(b,c,a,d,conditioned):
        mu=sum(i*p for i,p in enumerate(d));var=sum(p*(i-mu)**2 for i,p in enumerate(d))
        return [1.,b/12,c/5,mu/8,var/16]+([a/4] if conditioned else [])
    cases=list(itertools.product(range(13),(3,5),(0,2,4)))
    weights={name:ridge([(feat(b,c,a,d,cond),expected(b,c,a,d)) for d in dev for b,c,a in cases]) for name,cond in [('passive_linear',False),('action_linear',True)]}
    out={}
    for arm in ('passive_linear','action_linear','mean_demand_plugin','distribution_oracle'):
        err=[];effects=[];bad=0
        for d in test:
            for b,c in itertools.product(range(13),(3,5)):
                def pred(a):
                    if arm in weights:return dot(weights[arm],feat(b,c,a,d,arm=='action_linear'))
                    if arm=='mean_demand_plugin':return next_backlog(b,sum(i*p for i,p in enumerate(d)),c,a)
                    return expected(b,c,a,d)
                zero=pred(0);gold0=expected(b,c,0,d)
                for a in (0,2,4):
                    v=pred(a);gold=expected(b,c,a,d);err.append(abs(v-gold));bad+=int(v<0)
                    if a:effects.append(abs((v-zero)-(gold-gold0)))
        out[arm]=dict(mae=mean(err),action_effect_mae=mean(effects),negative_predictions=bad,n=len(err))
    return dict(test_environments=len(test),development_environments=len(dev),development_cases=len(dev)*len(cases),arms=out,weights_sha256=digest(weights))


def environments(seed,n,shift):
    rng=random.Random(seed);out=[]
    for _ in range(n):
        w=[rng.uniform(.1,1)**(2 if shift else 1) for _ in range(3)];prior=tuple(x/sum(w) for x in w)
        probs=tuple(tuple(rng.uniform(.08,.92) for _ in range(3)) for _ in range(4));costs=tuple(2 if rng.random()<(.65 if shift else .35) else 1 for _ in range(4));out.append((prior,probs,costs))
    return out


def update(prior,probabilities,outcome):
    w=[p*(q if outcome else 1-q) for p,q in zip(prior,probabilities)];z=sum(w);return z,tuple(v/z for v in w)


def design_context(env):
    prior,probs,costs=env
    @lru_cache(None)
    def posterior(history):
        p=prior
        for a,y in history:_,p=update(p,probs[a],y)
        return p
    def remaining(h):return BUDGET-sum(costs[a] for a,_ in h)
    def choices(h):return [a for a in range(4) if costs[a]<=remaining(h) and a not in {i for i,_ in h}]
    def branch(h,a,y):return tuple(sorted((*h,(a,y))))
    def stop(h):return 1-max(posterior(h))
    def expected_next(h,a,fn):return sum(update(posterior(h),probs[a],y)[0]*fn(branch(h,a,y)) for y in (0,1))
    @lru_cache(None)
    def optimal(h):return min([stop(h)]+[COST*costs[a]+expected_next(h,a,optimal) for a in choices(h)])
    def gains(h,a):return stop(h)-COST*costs[a]-expected_next(h,a,optimal)
    def features(h,a):
        p=posterior(h);immediate=stop(h)-expected_next(h,a,stop)
        return [1.,*p,*probs[a],costs[a]/2,remaining(h)/3,immediate,len(choices(h))/4]
    return posterior,choices,branch,stop,expected_next,optimal,gains,features


def policy_value(env,arm,weights):
    p,choices,branch,stop,next_value,optimal,gains,features=design_context(env);costs=env[2]
    @lru_cache(None)
    def evaluate(h):
        eligible=choices(h)
        if not eligible or arm=='stop':return stop(h),0.
        if arm=='fixed':a=eligible[0]
        else:
            def gain(a):
                if arm=='exact':return gains(h,a)
                if arm=='greedy':return (stop(h)-next_value(h,a,stop)-COST*costs[a])/costs[a]
                if arm=='amortized':return dot(weights,features(h,a))
                raise ValueError('unknown policy')
            a=max(eligible,key=lambda a:(gain(a),-a))
            if gain(a)<=1e-12:return stop(h),0.
        total=[0.,float(costs[a])]
        for y in (0,1):
            q,_=update(p(h),env[1][a],y);e,c=evaluate(branch(h,a,y));total[0]+=q*e;total[1]+=q*c
        return tuple(total)
    e,c=evaluate(());return e,c,e+COST*c


def design():
    dev=environments(8011,12,False);test=environments(9917,6,True);train=[]
    for env in dev:
        _,choices,branch,_,_,_,gain,features=design_context(env);stack=[()];seen=set()
        while stack:
            h=stack.pop()
            if h in seen:continue
            seen.add(h)
            for a in choices(h):
                train.append((features(h,a),gain(h,a)))
                stack.extend(branch(h,a,y) for y in (0,1))
    weights=ridge(train);out={};exact=[policy_value(e,'exact',None) for e in test]
    for arm in ('stop','fixed','greedy','amortized','exact'):
        vals=[policy_value(e,arm,weights) for e in test]
        out[arm]=dict(expected_error=mean(x[0] for x in vals),expected_spend=mean(x[1] for x in vals),objective=mean(x[2] for x in vals),regret=mean(x[2]-y[2] for x,y in zip(vals,exact)))
    return dict(development_environments=len(dev),test_environments=len(test),training_states_actions=len(train),weights_sha256=digest(weights),arms=out)


def run():return dict(scope='finite_simulation_only',queue=queue(),design=design(),limitations=['separately authored simulator and enumerated oracle, not independent human adjudication','distribution oracle has richer information','no hospital causal effects or actual economic costs','six held-out authored parameter draws per task, no clinical validity'])


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.write_text(json.dumps(run(),sort_keys=True,indent=2,allow_nan=False)+'\n')


if __name__=='__main__':main()
