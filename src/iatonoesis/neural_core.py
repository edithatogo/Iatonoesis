"""CPU neural/linear ablation on the existing synthetic core-suite features."""
import argparse
import copy
import json
import math
import random
from collections import Counter
from pathlib import Path

EPOCHS = 40
RATE = .03
HIDDEN = 16


def vector(vocab, features):
    counts = Counter(features)
    return [float(counts.get(f, 0)) for f in vocab]


def dot(a, b):
    return sum(x*y for x,y in zip(a,b))


def forward(model, x):
    h = [math.tanh(dot(w,x)+b) for w,b in zip(model['w1'],model['b1'])] if model['hidden'] else x
    z = [dot(w,h)+b for w,b in zip(model['w2'],model['b2'])]
    m = max(z)
    exps = [math.exp(t-m) for t in z]
    total = sum(exps)
    return h, [v/total for v in exps]


def fit(rows, *, hidden, seed):
    if not rows or type(hidden) is not int or not 0<=hidden<=64:
        raise ValueError('invalid training rows or hidden width')
    vocab = sorted({f for features,_ in rows for f in features})
    labels = sorted({label for _,label in rows})
    if not vocab or len(labels)<2:
        raise ValueError('insufficient feature or label support')
    rng = random.Random(seed)
    def matrix(n,d):
        scale = 1/math.sqrt(d)
        return [[rng.uniform(-scale,scale) for _ in range(d)] for _ in range(n)]
    width = hidden or len(vocab)
    model = dict(vocab=vocab,labels=labels,hidden=hidden,w1=matrix(hidden,len(vocab)),b1=[0.]*hidden,
                 w2=matrix(len(labels),width),b2=[0.]*len(labels),epochs=EPOCHS,rate=RATE,seed=seed)
    data = [(vector(vocab,f),labels.index(y)) for f,y in rows]
    for _ in range(EPOCHS):
        order = list(range(len(data)))
        rng.shuffle(order)
        for i in order:
            x,y = data[i]
            h,p = forward(model,x)
            delta = [v-float(j==y) for j,v in enumerate(p)]
            back = [(1-v*v)*sum(d*w[j] for d,w in zip(delta,model['w2'])) for j,v in enumerate(h)] if hidden else []
            for j,d in enumerate(delta):
                model['b2'][j] -= RATE*d
                for k,v in enumerate(h):
                    model['w2'][j][k] -= RATE*d*v
            for j,d in enumerate(back):
                model['b1'][j] -= RATE*d
                for k,v in enumerate(x):
                    model['w1'][j][k] -= RATE*d*v
    return model


def probabilities(model, features):
    _,p = forward(model,vector(model['vocab'],features))
    return dict(zip(model['labels'],p))


def fit_task(core, key, data, inputs, refs, hidden, seed):
    train = []
    for row in data['rows']:
        if row['split']!='development':
            continue
        i = row['id']
        inp,gold = inputs[i],refs[i]
        if key=='E02':
            train.extend((f,'yes' if candidate in gold else 'no') for group in core.layout_candidates(inp) for candidate,f in group)
        else:
            train.append((core.features(key,inp),('pending' if gold else 'not_pending') if key=='E04' else gold[0]))
    model = fit(train,hidden=hidden,seed=seed)
    def predict(inp):
        if key=='E02':
            return [max(group,key=lambda c:probabilities(model,c[1])['yes'])[0] for group in core.layout_candidates(inp) if group]
        p = probabilities(model,core.features(key,inp))
        label = max(p,key=p.get)
        if key=='E04':
            match = core.workflow.TUPLE.search(inp)
            return [list(match.groups())] if label=='pending' and match else [] if label=='not_pending' else None
        return [label]
    return model,predict,len(train)


def run_suite(revision, receipt, seed=17):
    from . import core_suite as core
    from .runner import run_experiment, paired_f1_interval
    from .run_contracts import canonical_sha256 as digest
    frozen = core.freeze(seed,revision)
    rules = {'E02':lambda p:sorted(map(list,core.layout.spatial(p))), 'E04':core.workflow.extract_context,
             'E22':core.workflow.verify_steps}
    result = {}
    for key in ('E02','E04','E22'):
        data,exp,inputs,refs = frozen[key]
        old = receipt['tasks'][key]
        if (data['sha256']!=old['dataset_sha256'] or data['reference']['sha256']!=old['reference_sha256']):
            raise ValueError('prior fixture digest mismatch')
        exp = copy.deepcopy(exp)
        exp['experiment_id'] = key+'-neural-feature-ablation-v0.1.0'
        exp['arms'] = [dict(id='rules',role='deterministic'),dict(id='learned',role='classical'),
                       dict(id='linear',role='classical'),dict(id='mlp',role='specialist')]
        nb,old_predict = core.fit_predictor(key,data,inputs,refs)
        predictors = dict(rules=rules[key],learned=old_predict)
        models = dict(learned=dict(id='laplace-nb',revision=revision,licence='MIT',weights_sha256=digest(nb)))
        for arm,width in [('linear',0),('mlp',HIDDEN)]:
            model,predict,n = fit_task(core,key,data,inputs,refs,width,seed)
            predictors[arm] = predict
            models[arm] = dict(id='softmax-linear' if width==0 else 'tanh-mlp',revision=revision,licence='MIT',
                               weights_sha256=digest(model),training_examples=n,hidden=width,epochs=EPOCHS,seed=seed)
        item = run_experiment(exp,data,inputs,refs,predictors=predictors,models=models,source_commit=revision)
        item['paired_f1'] = {a:paired_f1_interval(item['predictions']['rules'],item['predictions'][a],grouping_key='family',seed=seed,draws=200)
                             for a in ('learned','linear','mlp') if {'rules',a}<=set(item['predictions'])}
        if key=='E04':
            item['safety']={a:dict(false_positive_tuples=next(x['metrics']['fp'] for x in item['manifest']['arms'] if x['id']==a),
                                  active_cases_referred=sum(bool(r['gold']) and r['prediction'] is None for r in rows)) for a,rows in item['predictions'].items()}
        if key=='E22':
            item['safety']={a:dict(false_timely=sum(r['prediction']==['completed'] and r['gold']!=['completed'] for r in rows),
                                  non_timely=sum(r['gold']!=['completed'] for r in rows)) for a,rows in item['predictions'].items()}
        result[key]=item
    return dict(scope='synthetic_posthoc_replay_only',source_commit=revision,seed=seed,tasks=result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--revision',required=True)
    parser.add_argument('--receipt',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(run_suite(args.revision,json.loads(args.receipt.read_text())),sort_keys=True,allow_nan=False)+'\n')


if __name__=='__main__':
    main()
