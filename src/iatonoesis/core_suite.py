"""Exploratory classical challengers, not qualified clinical models or independent clinical labels."""
import argparse
import json
import math
import random
import re
from collections import Counter, defaultdict, deque
from pathlib import Path

from . import policy_layout_pilot as layout, workflow_pilots as workflow
from .run_contracts import canonical_sha256, validate_experiment
from .runner import paired_f1_interval, run_experiment

TASKS = {'E02': 'T01.008', 'E04': 'T02.004', 'E07': 'T03.004', 'E11': 'T04.008',
         'E13': 'T05.004', 'E17': 'T06.008', 'E20': 'T07.008', 'E22': 'T08.004'}


def fit_nb(rows):
    """Fit a Laplace-smoothed multinomial naive Bayes model from labelled features."""
    labels, counts, vocab = Counter(), defaultdict(Counter), set()
    for features, label in rows:
        labels[label] += 1
        counts[label].update(features)
        vocab.update(features)
    if not labels or not vocab:
        raise ValueError('empty training set')
    return {'labels': dict(labels), 'counts': {k: dict(v) for k, v in counts.items()}, 'vocab': sorted(vocab)}


def scores(model, features):
    vocab = set(model['vocab'])
    features = [f for f in features if f in vocab]
    n = sum(model['labels'].values())
    return {label: math.log(count / n) + sum(math.log((model['counts'][label].get(f, 0) + 1) /
                (sum(model['counts'][label].values()) + len(vocab))) for f in features)
            for label, count in sorted(model['labels'].items())}


def predict_nb(model, features):
    values = scores(model, features)
    return max(values, key=values.get)


def words(text):
    return tuple('w:' + w for w in re.findall(r'[a-z]+', text.lower()))


def feats(**values):
    return tuple(f'{k}:{v}' for k, v in sorted(values.items()))


def reach(inp):
    queue, seen = deque([inp['start']]), {inp['start']}
    while queue:
        node = queue.popleft()
        if node == inp['end']:
            return ['reachable']
        for a, b in inp['edges']:
            if a == node and b not in seen:
                seen.add(b)
                queue.append(b)
    return ['unreachable']


def graph_features(inp):
    a, b = inp['start'], inp['end']
    outgoing = {y for x, y in inp['edges'] if x == a}
    incoming = {x for x, y in inp['edges'] if y == b}
    return feats(direct=b in outgoing, two_hop=bool(outgoing & incoming), out_degree=min(3, len(outgoing)),
                 in_degree=min(3, len(incoming)), direction=a < b, distance=min(4, abs(a-b)))


def credential(inp):
    if not inp['documented']:
        return ['unresolved']
    if not inp['scope'] or inp['months'] > 24:
        return ['unsupported']
    return ['supported' if inp['supervision'] else 'conditional']


def rank_features(inp, candidate):
    overlap = len(set(words(inp['query'])) & set(words(candidate['text'])))
    return feats(overlap=min(4, overlap), site=inp['site'] == candidate['site'],
                 population=inp['population'] == candidate['population'], approved=candidate['approved'])


def rank_rule(inp):
    candidates = [c for c in inp['candidates'] if c['approved'] and c['site'] == inp['site'] and c['population'] == inp['population']]
    if not candidates:
        return None
    candidate = max(candidates, key=lambda c: (len(set(words(inp['query'])) & set(words(c['text']))), c['id']))
    return [candidate['id']]


ROUTES = {'finance': 'budget', 'workforce': 'roster', 'quality': 'audit'}


def route_rule(inp):
    tokens = set(words(inp['text']))
    eligible = [k for k, v in ROUTES.items() if 'w:' + v in tokens and k in inp['allowed']]
    return eligible if len(eligible) == 1 else None


def evidence(inp):
    if not (inp['direct'] and inp['valid'] and inp['precise']):
        return ['insufficient']
    return ['supports' if inp['direction'] == inp['claim'] else 'contradicts']


def additional(key, seed):
    rng = random.Random(seed)
    rows = []
    for family, split in enumerate(workflow.PARTITIONS):
        for index in range(20):
            if key == 'E07':
                n = 6 + family % 4
                edges = [[a, b] for a in range(n) for b in range(a+1, n) if rng.random() < (0.18 + family*.035)]
                a, b = rng.sample(range(n), 2)
                # Independent transitive-closure expression vs BFS comparator.
                closure = {(x, y) for x, y in edges}
                for k in range(n):
                    closure |= {(x, y) for x in range(n) for y in range(n) if (x,k) in closure and (k,y) in closure}
                inp = dict(edges=edges, start=a, end=b)
                gold = ['reachable' if (a,b) in closure else 'unreachable']
            elif key == 'E11':
                inp = dict(scope=rng.choice([True, False]), months=rng.randint(1, 36), documented=rng.random()>.2,
                           supervision=rng.choice([True, False]))
                # Fictional portfolio states, not clinical credentialing policy.
                gold = [['unresolved', 'unsupported', 'conditional', 'supported'][0 if not inp['documented'] else
                        1 if not inp['scope'] or inp['months']>24 else 3 if inp['supervision'] else 2]]
            elif key == 'E13':
                topic = rng.choice(['review', 'monitor', 'record', 'check'])
                site, population = rng.choice(['rural', 'urban']), rng.choice(['adult', 'child'])
                alternatives = [(topic, site, population, True), (topic, site, population, False),
                                (topic, 'urban' if site=='rural' else 'rural', population, True),
                                ('other', site, population, True), (topic, site, 'adult' if population=='child' else 'child', True)]
                candidates = [dict(id=str(i), text=t+' form', site=s, population=p, approved=ok) for i,(t,s,p,ok) in enumerate(alternatives)]
                rng.shuffle(candidates)
                # IDs shuffled independently of true rank; no label-derived feature.
                for i,c in enumerate(candidates):
                    c['id'] = f'p{i}'
                gold = [c['id'] for c in candidates if c['text']==topic+' form' and c['site']==site and c['population']==population and c['approved']]
                inp = dict(query=topic+' form', site=site, population=population, candidates=candidates)
            elif key == 'E17':
                kind = rng.choice(list(ROUTES))
                allowed = [k for k in ROUTES if rng.random()>.2]
                token = ROUTES[kind] if family < 9 else {'finance':'funding', 'workforce':'staffing', 'quality':'review'}[kind]
                inp = dict(text='request '+token+' consultation', allowed=allowed)
                gold = [kind] if kind in allowed else ['escalate']
            elif key == 'E20':
                inp = dict(direct=rng.random()>.2, valid=rng.random()>.2, precise=rng.random()>.2,
                           direction=rng.choice(['up','down']), claim=rng.choice(['up','down']))
                gold = ['insufficient' if sum([inp['direct'],inp['valid'],inp['precise']])<3 else
                        'supports' if inp['direction']==inp['claim'] else 'contradicts']
            else:
                raise ValueError('unsupported fixture')
            rows.append(dict(id=f'{key}-{family}-{index}', family=f'f{family}', split=split, input=inp, gold=gold))
    return rows


def freeze(seed, revision):
    """Freeze canonical input/reference and split hashes before model fitting."""
    cases = {'E02': [dict(d, input=d['page']) for d in layout.generate(seed)],
             'E04': workflow.make_discharge(seed), 'E22': workflow.make_steps(seed)}
    for key in ('E07','E11','E13','E17','E20'):
        cases[key] = additional(key, seed)
    output = {}
    for key in TASKS:
        rows = cases[key]
        inputs = {r['id']: r['input'] for r in rows}
        refs = {r['id']: r['gold'] for r in rows}
        data = dict(schema_version='0.1.0', dataset_id=key+'-exploratory-v1', kind='synthetic',
                    source='repository-authored fictional scenarios; prior pilots reused', revision=revision,
                    sha256=canonical_sha256(inputs), rights=dict(status='approved', licence='MIT', evidence='repository-authored synthetic scenarios only'),
                    reference=dict(kind='deterministic_oracle', revision=revision, sha256=canonical_sha256(refs)),
                    grouping_keys=['family'], rows=[dict(id=r['id'], split=r['split'], groups={'family':r['family']}) for r in rows])
        exp = dict(schema_version='0.1.0', experiment_id=data['dataset_id'], track_task=TASKS[key], dataset_id=data['dataset_id'],
                   dataset_sha256=data['sha256'], reference_sha256=data['reference']['sha256'], seed=seed, split='test',
                   case_ids=[r['id'] for r in rows if r['split']=='test'], primary_metric='f1', unit='case',
                   arms=[dict(id='rules',role='deterministic'),dict(id='learned',role='classical')]+
                        ([dict(id='naive',role='deterministic')] if key in {'E02','E04','E22'} else []),
                   budget=dict(max_cases=len(rows),max_seconds=60), claim_boundary='synthetic_only')
        validate_experiment(exp,data)
        output[key] = (data,exp,inputs,refs)
    return output


def layout_candidates(page):
    notes = layout._footnotes(page)
    reqs = [(layout.REQ.fullmatch(t['text'])[1],t['x'],t['y']) for t in page if layout.REQ.fullmatch(t['text'])]
    for t in page:
        mark=layout.MARK.fullmatch(t['text'])
        if mark and mark[1] in notes:
            yield [(list((req,notes[mark[1]])), feats(dx='left' if t['x']-x<0 else 'near' if 0<t['x']-x<=40 else 'far',
                      dy='near' if abs(t['y']-y)<=5 else 'far')) for req,x,y in reqs]


def features(key, inp):
    if key=='E04':
        match=workflow.TUPLE.search(inp)
        return words(inp[match.end():] if match else inp)
    if key=='E07':
        return graph_features(inp)
    if key=='E11':
        return feats(scope=inp['scope'],documented=inp['documented'],supervision=inp['supervision'],recent=inp['months']<=24)
    if key=='E17':
        return words(inp['text'])+tuple('allowed:'+x for x in sorted(inp['allowed']))
    if key=='E20':
        return feats(**inp, same=inp['direction']==inp['claim'])
    if key=='E22':
        times=[e['minute'] for e in inp['events'] if e['kind']=='performed']
        m=workflow.COMPLETION.fullmatch(inp['note'])
        if m:
            times.append(int(m[1]))
        return feats(exception=inp['exception'], complete_log=inp['complete_log'], timing='none' if not times else 'timely' if min(times)<=inp['deadline'] else 'late')+words(inp['note'])
    raise ValueError('unknown feature task')


def fit_predictor(key, data, inputs, refs):
    train=[]
    for row in data['rows']:
        if row['split']!='development':
            continue
        i=row['id']; inp,gold=inputs[i],refs[i]
        if key=='E02':
            train.extend((f,'yes' if candidate in gold else 'no') for group in layout_candidates(inp) for candidate,f in group)
        elif key=='E13':
            train.extend((rank_features(inp,c),'yes' if c['id'] in gold else 'no') for c in inp['candidates'])
        else:
            train.append((features(key,inp), ('pending' if gold else 'not_pending') if key=='E04' else gold[0]))
    model=fit_nb(train)

    def margin(f):
        s=scores(model,f)
        return s['yes']-s['no']

    def predict(inp):
        if key=='E02':
            return [max(group,key=lambda c: margin(c[1]))[0] for group in layout_candidates(inp) if group]
        if key=='E13':
            return [max(inp['candidates'],key=lambda c: margin(rank_features(inp,c)))['id']]
        label=predict_nb(model,features(key,inp))
        if key=='E04':
            match=workflow.TUPLE.search(inp)
            return [list(match.groups())] if label=='pending' and match else [] if label=='not_pending' else None
        if key=='E17' and label!='escalate' and label not in inp['allowed']:
            return None
        return [label]
    return model,predict


def run_suite(frozen, revision):
    rules={'E02':lambda p:sorted(map(list,layout.spatial(p))), 'E04':workflow.extract_context, 'E07':reach,
           'E11':credential, 'E13':rank_rule, 'E17':lambda inp:route_rule(inp) or ['escalate'], 'E20':evidence,'E22':workflow.verify_steps}
    naive={'E02':lambda p:sorted(map(list,layout.flat(p))), 'E04':workflow.extract_naive, 'E22':workflow.verify_naive}
    result={}
    # Validate every frozen input before fitting any model.
    for data,exp,inputs,refs in frozen.values():
        validate_experiment(exp,data)
        if canonical_sha256(inputs)!=data['sha256'] or canonical_sha256(refs)!=data['reference']['sha256']:
            raise ValueError('frozen reference or input hash mismatch')
    for key,(data,exp,inputs,refs) in frozen.items():
        model,predict=fit_predictor(key,data,inputs,refs)
        metadata=dict(id='task-specific-laplace-nb', revision=revision, licence='MIT', training_split='development',
                      training_cases=sum(r['split']=='development' for r in data['rows']), weights_sha256=canonical_sha256(model))
        predictors={'rules':rules[key],'learned':predict}
        if key in naive:
            predictors['naive']=naive[key]
        item=run_experiment(exp,data,inputs,refs,predictors=predictors,models={'learned':metadata},source_commit=revision)
        if {'rules','learned'} <= set(item['predictions']):
            item['paired_f1']=paired_f1_interval(item['predictions']['rules'],item['predictions']['learned'],grouping_key='family',seed=exp['seed'],draws=200)
        safety={}
        for arm,rows in item['predictions'].items():
            if key=='E04':
                safety[arm]={'false_positive_tuples': next(a['metrics']['fp'] for a in item['manifest']['arms'] if a['id']==arm),
                             'active_cases_referred':sum(bool(r['gold']) and r['prediction'] is None for r in rows)}
            if key=='E22':
                safety[arm]={'false_timely':sum(r['prediction']==['completed'] and r['gold']!=['completed'] for r in rows),
                             'non_timely':sum(r['gold']!=['completed'] for r in rows),
                             'found_missing':sum(r['gold']==r['prediction']==['missing'] for r in rows),
                             'missing':sum(r['gold']==['missing'] for r in rows)}
        item['safety']=safety
        result[key]=item
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed',type=int,default=17)
    parser.add_argument('--revision',required=True)
    parser.add_argument('--freeze',type=Path,required=True)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.output:
        frozen=json.loads(args.freeze.read_text())
        args.output.write_text(json.dumps(run_suite(frozen,args.revision),indent=2,sort_keys=True)+'\n')
    else:
        args.freeze.write_text(json.dumps(freeze(args.seed,args.revision),indent=2,sort_keys=True)+'\n')


if __name__=='__main__':
    main()
