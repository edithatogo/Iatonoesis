"""Temporal ranking of independently published MONDO is_a assertions; not clinical truth."""
import argparse
import hashlib
import json
import math
import random
import re
import tempfile
import time
import urllib.request
from collections import defaultdict
from pathlib import Path

PINS = {
    '2026-02-03': (50723023, '7ee951f9dd83b561179d6e588e8a753e1d7c8e1bba4d67535a39efc294c52d09'),
    '2026-05-05': (51135232, 'fffd4c01bd56a5b105c3b752fcbb735335c6b18a0ae82f8f50cff9f8ab375217'),
    '2026-08-04': (53086111, 'fce4bccd97c4eb66161e88272ca0bd6ecd28c003afa878bbec8eae0ceb78fba8'),
    '2026-11-03': (53442278, 'b5a3d848578694601dffb1c2866798d4f6f4b4a12c315030c4d4c62ffe4e7e22'),
}
ARMS = ('lexical', 'topology', 'hybrid_rule', 'linear', 'neural', 'no_graph')
ID = re.compile(r'MONDO:[0-9]{7}')


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def verify_source(path, size, sha):
    with path.open('rb') as stream:
        actual = hashlib.file_digest(stream, 'sha256').hexdigest()
    if path.stat().st_size != size or actual != sha:
        raise ValueError('source integrity mismatch')
    return {'bytes': size, 'sha256': actual}


def parse_obo(path, version):
    nodes, seen = {}, set()
    stanza, term, found_version = '', {}, False

    def flush():
        if stanza != '[Term]' or not ID.fullmatch(term.get('id', '')):
            return
        i = term['id']
        if i in seen:
            raise ValueError('duplicate MONDO term')
        seen.add(i)
        if term.get('is_obsolete') == 'true':
            return
        if not term.get('name'):
            raise ValueError('missing term name')
        nodes[i] = {'name': term['name'], 'parents': set(term.get('parents', []))}

    with path.open(encoding='utf-8') as stream:
        for line in stream:
            line = line.strip()
            if line.startswith('[') and line.endswith(']'):
                flush()
                stanza, term = line, {}
            elif not stanza and line.startswith('data-version: '):
                found_version = line.split(': ', 1)[1].rstrip('/').split('/')[-1] == version
            elif stanza == '[Term]' and ': ' in line:
                k, v = line.split(': ', 1)
                if k == 'is_a' and ID.fullmatch(v.split()[0]):
                    term.setdefault('parents', []).append(v.split()[0])
                elif k in {'id', 'name', 'is_obsolete'}:
                    term[k] = v
    flush()
    if not found_version or not nodes:
        raise ValueError('missing or mismatched release version')
    for i, n in nodes.items():
        n['parents'].intersection_update(nodes)
        if i in n['parents']:
            raise ValueError('self parent')
    return nodes


def _jac(a, b):
    return len(a & b) / len(a | b) if a or b else 0.0


def _index(nodes):
    children, inv = defaultdict(set), defaultdict(set)
    words, grams = {}, {}
    for i, n in nodes.items():
        for p in n['parents']:
            children[p].add(i)
        words[i] = set(re.findall(r'[a-z0-9]+', n['name'].lower()))
        name = ' '.join(n['name'].lower().split())
        grams[i] = {name[j:j+3] for j in range(max(0, len(name)-2))}
        for w in words[i]:
            inv[w].add(i)
    return children, inv, words, grams, sorted(nodes)


def features(nodes, child, parent, index):
    children, _, words, grams, _ = index
    cp, pp = nodes[child]['parents'], nodes[parent]['parents']
    cc, pc = children[child], children[parent]
    return [_jac(words[child], words[parent]), _jac(grams[child], grams[parent]),
            len(words[child] & words[parent]) / max(1, len(words[parent])),
            _jac(cp, pp), _jac(cc, pc), float(any(parent in nodes[p]['parents'] for p in cp)),
            _jac(cp | cc, pp | pc), max((_jac(words[p], words[parent]) for p in cp), default=0.0)]


def _lex(f):
    return (f[0] + f[1] + f[2]) / 3


def _top(f):
    return (f[3] + f[4] + f[5] + f[6] + f[7]) / 5


def candidates(nodes, child, salt, count=32, index=None):
    if not 2 <= count <= 128:
        raise ValueError('candidate cap out of range')
    idx = index if index is not None else _index(nodes)
    children, inv, words, grams, ids = idx
    blocked = {child} | nodes[child]['parents']
    descendants, stack = set(), list(children[child])
    while stack:
        x = stack.pop()
        if x not in descendants:
            descendants.add(x)
            stack.extend(children[x] - descendants)
    blocked |= descendants
    eligible = set(ids) - blocked
    lexical = set().union(*(inv[w] for w in words[child])) & eligible
    neigh = nodes[child]['parents'] | children[child]
    topo = set().union(*(nodes[n]['parents'] | children[n] for n in neigh)) & eligible
    # Separate retrieval budgets, then interleave without duplicating candidates.
    a = sorted(lexical, key=lambda p: (-_lex(features(nodes, child, p, idx)), p))[:count//2]
    b = sorted(topo, key=lambda p: (-_top(features(nodes, child, p, idx)), p))[:count//2]
    pool = list(dict.fromkeys(a + b))
    if len(pool) < count:
        rem = sorted(eligible - set(pool))
        rng = random.Random(digest([salt, child]))
        pool.extend(rng.sample(rem, min(count-len(pool), len(rem))))
    return sorted(pool)


def transition(old, new, salt, pool_size=32):
    idx = _index(old)
    rows, excluded, total = [], 0, 0
    for child in sorted(new):
        added = new[child]['parents'] - old.get(child, {'parents': set()})['parents']
        total += len(added)
        eligible = sorted(p for p in added if child in old and p in old)
        excluded += len(added) - len(eligible)
        if not eligible:
            continue
        pool = candidates(old, child, salt, pool_size, idx)
        rows.append({'child':child,'gold':eligible,'pool':pool,
                     'features':[features(old, child, p, idx) for p in pool]})
    return rows, {'old_terms':len(old),'new_terms':len(new),'new_assertions':total,
                  'excluded_new_endpoint_edges':excluded,'eligible_edges':total-excluded,
                  'queries':len(rows),'manifest_sha256':digest(rows)}


def _ordered(row, scores):
    if len(row['pool']) != len(scores) or not all(math.isfinite(x) for x in scores):
        raise ValueError('invalid candidate scores')
    return sorted(zip(row['pool'], scores), key=lambda x: (-x[1], x[0]))


def _query(row, scores):
    order = _ordered(row, scores)
    gold = set(row['gold'])
    positions = [i+1 for i, (p, _) in enumerate(order) if p in gold]
    confidence = order[0][1] - order[1][1] if len(order) >= 2 else 0.0
    return {'child':row['child'],'gold':len(gold),'pool_hits':len(positions),
            'hits1':sum(i<=1 for i in positions),'hits5':sum(i<=5 for i in positions),'hits10':sum(i<=10 for i in positions),
            'rr':1/min(positions) if positions else 0.0,'confidence':confidence,
            'top1_confirmed':bool(positions and min(positions)==1),'has_candidate':bool(order)}


def _queries(rows, scores):
    return [_query(r, s) for r, s in zip(rows, scores, strict=True)]


def ranking_metrics(rows, scores):
    q = _queries(rows, scores)
    n, gold = len(q), sum(x['gold'] for x in q)
    if not n or not gold:
        raise ValueError('empty evaluation reference')
    out = {'queries':n,'gold_edges':gold,'pool_hits':sum(x['pool_hits'] for x in q),
           'pool_candidates':sum(len(r['pool']) for r in rows),'mrr':sum(x['rr'] for x in q)/n,
           'top1_confirmed':sum(x['top1_confirmed'] for x in q),'prediction_sha256':digest([_ordered(r,s) for r,s in zip(rows,scores,strict=True)])}
    out['pool_recall'] = out['pool_hits']/gold
    for k in (1,5,10):
        out[f'recall_at_{k}'] = sum(x[f'hits{k}'] for x in q)/gold
        out[f'candidate_reviews_at_{k}'] = sum(min(k,len(r['pool'])) for r in rows)
    return out


def _review(q, selected):
    confirmed = sum(x['top1_confirmed'] for x in selected)
    return {'reviewed_queries':len(selected),'retained':len(selected),'coverage':len(selected)/len(q) if q else None,
            'confirmed':confirmed,'unconfirmed':len(selected)-confirmed,'unconfirmed_rate':(len(selected)-confirmed)/len(selected) if selected else None,
            'confirmed_edge_recall':confirmed/sum(x['gold'] for x in q) if q else None}


def review_frontier(rows, scores, fraction):
    if not 0 <= fraction <= 1:
        raise ValueError('invalid review fraction')
    q = _queries(rows, scores)
    selected = sorted((x for x in q if x['has_candidate']),key=lambda x:(-x['confidence'],x['child']))[:int(len(q)*fraction)]
    return _review(q, selected)


def _upper(errors, n):
    if not n:
        return 1.0
    p, z = errors/n, 1.95996398454
    return (p+z*z/(2*n)+z*math.sqrt(p*(1-p)/n+z*z/(4*n*n)))/(1+z*z/n)


def calibrated(cal_rows, cal_scores, test_rows, test_scores, min_count=20, target=.20):
    cal = _queries(cal_rows, cal_scores)
    test = _queries(test_rows, test_scores)
    choices=[]
    for threshold in sorted({x['confidence'] for x in cal if x['has_candidate']}):
        retained=[x for x in cal if x['has_candidate'] and x['confidence']>=threshold]
        n=len(retained); errors=sum(not x['top1_confirmed'] for x in retained)
        bound=_upper(errors,n)
        if n>=min_count and bound<=target:
            choices.append((n,-threshold,bound))
    if choices:
        n, neg, bound=max(choices); threshold=-neg
    else:
        n, threshold, bound=0,None,None
    selected=[x for x in test if threshold is not None and x['has_candidate'] and x['confidence']>=threshold]
    return {'threshold':threshold,'calibration_retained':n,'calibration_upper_unconfirmed':bound,'target':target,
            'min_calibration_queries':min_count,**_review(test,selected)}


def _forward(model, f):
    if model['kind'] == 'linear':
        return sum(w*x for w,x in zip(model['w'],f,strict=True)), []
    h = [math.tanh(sum(w*x for w,x in zip(row,f,strict=True))+b) for row,b in zip(model['w'],model['b'],strict=True)]
    return sum(w*x for w,x in zip(model['v'],h,strict=True)), h


def _f(arm,f):
    return f[:3]+[0.0]*5 if arm=='no_graph' else f


def fit(rows, arm, epochs=25):
    if arm not in ('linear','neural','no_graph') or not 1<=epochs<=100:
        raise ValueError('invalid model configuration')
    train=[r for r in rows if set(r['pool']) & set(r['gold'])]
    if not train:
        raise ValueError('no retrieved positive for training')
    rng=random.Random(17)
    model={'kind':'linear','w':[0.0]*8} if arm=='linear' else {'kind':'mlp','w':[[rng.uniform(-.15,.15) for _ in range(8)] for _ in range(8)],'b':[0.0]*8,'v':[rng.uniform(-.15,.15) for _ in range(8)]}
    for _ in range(epochs):
        for r in train:
            xs=[_f(arm,f) for f in r['features']]; gold=set(r['gold'])
            targets=[float(p in gold) for p in r['pool']]; n=sum(targets)
            outputs=[_forward(model,f) for f in xs]; hi=max(y for y,_ in outputs)
            probs=[math.exp(y-hi) for y,_ in outputs]; z=sum(probs)
            ds=[p/z-t/n for p,t in zip(probs,targets,strict=True)]
            lr=.05
            if arm=='linear':
                for j in range(8):
                    model['w'][j]-=lr*sum(d*x[j] for d,x in zip(ds,xs,strict=True))
            else:
                for j,v in enumerate(model['v'][:]):
                    g=[d*v*(1-h[j]*h[j]) for d,(_,h) in zip(ds,outputs,strict=True)]
                    model['v'][j]-=lr*sum(d*h[j] for d,(_,h) in zip(ds,outputs,strict=True))
                    model['b'][j]-=lr*sum(g)
                    for k in range(8):
                        model['w'][j][k]-=lr*sum(d*x[k] for d,x in zip(g,xs,strict=True))
    return model


def rank(rows,arm,model=None):
    if arm not in ARMS:
        raise ValueError('unknown arm')
    def score(f):
        if arm=='lexical': return _lex(f)
        if arm=='topology': return _top(f)
        if arm=='hybrid_rule': return (_lex(f)+_top(f))/2
        return _forward(model,_f(arm,f))[0]
    return [[score(f) for f in r['features']] for r in rows]


def _paired(a,b,draws=200):
    if len(a)!=len(b) or not a:
        raise ValueError('paired queries required')
    values=[y['rr']-x['rr'] for x,y in zip(a,b,strict=True)]
    rng=random.Random(17); n=len(values)
    boot=sorted(sum(rng.choices(values,k=n))/n for _ in range(draws))
    return {'mrr_delta':sum(values)/n,'lower':boot[int(.025*(draws-1))],'upper':boot[math.ceil(.975*(draws-1))],'queries':n,'draws':draws}


def run(snapshots,epochs=25,pool_size=32):
    if len(snapshots)!=4:
        raise ValueError('four chronologically ordered snapshots required')
    start=time.perf_counter(); partitions={}; rows={}
    for i,key in enumerate(('development','calibration','test')):
        rows[key],partitions[key]=transition(snapshots[i],snapshots[i+1],key,pool_size)
        if not rows[key] or len(rows[key])>5000:
            raise ValueError('empty or oversized eligible transition')
    generation=time.perf_counter()-start; out={}; test_queries={}
    dev,cal,test=[rows[k] for k in ('development','calibration','test')]
    for arm in ARMS:
        start=time.perf_counter(); model=fit(dev,arm,epochs) if arm in ('linear','neural','no_graph') else None
        train_seconds=time.perf_counter()-start; start=time.perf_counter()
        c=rank(cal,arm,model); s=rank(test,arm,model)
        elapsed=time.perf_counter()-start
        test_queries[arm]=_queries(test,s)
        out[arm]={'metrics':ranking_metrics(test,s),'calibration':calibrated(cal,c,test,s),
                  'matched_review':[review_frontier(test,s,p) for p in (.25,.5,.75,1)],
                  'training_seconds':train_seconds,'scoring_calibration_test_seconds':elapsed,
                  'model_sha256':digest(model) if model else None}
    dev_ids={r['child'] for r in dev}; cal_ids={r['child'] for r in cal}
    return {'scope':'published_assertion_prediction_not_clinical_truth','schema_version':'0.1.0','seed':17,
            'partitions':partitions,'test_seen_development_children':sum(r['child'] in dev_ids for r in test),
            'test_seen_calibration_children':sum(r['child'] in cal_ids for r in test),
            'candidate_generation_seconds':generation,'pool_size_cap':pool_size,'epochs':epochs,'arms':out,
            'paired_mrr':{f'{b}_minus_{a}':_paired(test_queries[a],test_queries[b]) for a,b in [('hybrid_rule','linear'),('hybrid_rule','neural'),('no_graph','neural')]}}


def acquire(date,path):
    size,sha=PINS[date]
    url=f'https://github.com/monarch-initiative/mondo/releases/download/v{date}/mondo.obo'
    with urllib.request.urlopen(url,timeout=90) as source, path.open('wb') as dest:
        remaining=size
        while chunk:=source.read(min(1048576,remaining+1)):
            remaining-=len(chunk)
            if remaining<0:
                raise ValueError('source exceeds pinned size')
            dest.write(chunk)
    return verify_source(path,size,sha)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True); args=parser.parse_args()
    try:
        with tempfile.TemporaryDirectory() as folder:
            snapshots=[]; receipts={}
            for date in PINS:
                path=Path(folder)/'mondo.obo'
                receipts[date]=acquire(date,path); snapshots.append(parse_obo(path,date)); path.unlink()
            result=run(snapshots); result.update(sources=receipts,licence='CC-BY-4.0',source='MONDO Disease Ontology; Monarch Initiative')
    except Exception as exc:
        args.output.write_text(json.dumps({'status':'failed','error_type':type(exc).__name__})+'\n')
        raise SystemExit(1) from None
    args.output.write_text(json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+'\n')


if __name__=='__main__':
    main()
