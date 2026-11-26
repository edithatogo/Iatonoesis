"""Post-hoc low-budget fairness audit of v0.2.0; not independent confirmation."""
import argparse
import hashlib
import itertools
import json
from pathlib import Path

DOMAIN = tuple(itertools.product(range(5),range(5),(0,1),(0,1)))
FLAGS = tuple(itertools.product((0,1),repeat=2))
TRUTH = {
    'agreement_guard': {4,7,8,11}, 'exact_two': {3,5,6,9,10,12},
    'priority': {2,3,4,5,6,7,9,11}, 'fallback': {1,5,9,12,13,14},
    'majority_guard': {7,9,10,11,13,14,15}, 'parity_four': {1,2,4,7,8,11,13,14},
}
TEST = ('swap_ab','swap_cd','cross_pair','invert_ab','copy_ab_to_cd',
        'gate_equal','force_cd','invert_equal','xor_bd')
PROXY = ('x_gt','x_lt','x_true','x_false','y_gt','y_lt','y_true','y_false',
         'flip_c','c_true','c_false','flip_d','d_true','d_false')
RAW_SHA = '66fcdda638df1f0955c771561160a53966cca43d4683450d52dc2306e9bfa3fb'


def evaluate(family,t,u,case,operator=None):
    x,y,c,d = case
    a,b = x>=t,y>=u
    original = (a,b,bool(c),bool(d))
    if operator in PROXY:
        values = list(original)
        if operator.startswith('flip_'):
            index = 'xycd'.index(operator[-1]); values[index] = not values[index]
        else:
            field,kind = operator.split('_'); index = 'xycd'.index(field)
            values[index] = {'true':True,'false':False,'gt':(x>t if index==0 else y>u),
                             'lt':(x<t if index==0 else y<u)}[kind]
        a,b,c,d = values
    elif operator=='swap_ab': a,b = b,a
    elif operator=='swap_cd': c,d = d,c
    elif operator=='cross_pair': a,b,c,d = c,d,a,b
    elif operator=='invert_ab': a,b = not a,not b
    elif operator=='copy_ab_to_cd': c,d = a,b
    bits = int(a)+2*int(b)+4*int(c)+8*int(d)
    out = bits in TRUTH[family]
    if operator=='gate_equal': out = out and a==b
    if operator=='force_cd': out = out or (c and d)
    if operator=='invert_equal': out = out != (a==b)
    if operator=='xor_bd': out = out != bool(b and d)
    return bool(out)


def truth_masks(family,t,u,kind):
    operators = {'test':TEST,'proxy':PROXY}[kind]
    base = [evaluate(family,t,u,c) for c in DOMAIN]
    result,seen = {},set()
    for op in operators:
        signature = frozenset(i for i,c in enumerate(DOMAIN) if evaluate(family,t,u,c,op)!=base[i])
        if signature and signature not in seen:
            seen.add(signature);result[op]=signature
    return result


def balanced_boundary(t,u):
    def key(i):
        x,y,_,_ = DOMAIN[i]
        return (min(abs(x-t),abs(y-u))+.01*(abs(x-t)+abs(y-u)),i)
    first = {g:min((i for i,c in enumerate(DOMAIN) if c[2:]==g),key=key) for g in FLAGS}
    return [tuple(first[g] for g in order[:2]) for order in itertools.permutations(FLAGS)]


def symbolic_select(masks,budget):
    if budget not in (1,2) or budget>len(masks):
        raise ValueError('invalid low budget')
    def key(indices):
        merged=0
        for i in indices: merged |= masks[i]
        return merged.bit_count()
    return max(itertools.combinations(range(len(masks)),budget),key=key)


def cover(signatures,indices):
    return {op for op,s in signatures.items() if s.intersection(indices)}


def audit(raw):
    if raw['test_families'] != list(TRUTH) or raw['test_mutations'] != list(TEST) or len(raw['rules'])!=54:
        raise ValueError('unexpected source experiment')
    rows=[]
    checked=0
    for rule in raw['rules']:
        f,t,u=rule['family'],rule['t'],rule['u']
        # Selection may inspect proxy mutations only. Test truth is used afterwards.
        proxy=truth_masks(f,t,u,'proxy')
        masks=[sum(1<<j for j,s in enumerate(proxy.values()) if i in s) for i in range(len(DOMAIN))]
        selections={str(k):symbolic_select(masks,k) for k in (1,2)}
        prefixes=balanced_boundary(t,u)
        truth=truth_masks(f,t,u,'test')
        if len(truth)!=rule['denominator']:
            raise ValueError('oracle denominator mismatch')
        for arm in rule['arms']:
            for k in (1,2,4,8):
                if cover(truth,arm['indices'][:k])!=set(arm['killed'][str(k)]):
                    raise ValueError('original raw kill disagreement')
                checked+=1
        by_budget={}
        for k in (1,2):
            b=str(k); n=len(truth)
            old={arm['arm']:len(arm['killed'][b])/n for arm in rule['arms'] if arm['arm'] in ('boundary','pairwise','learned_feedback','learned_no_feedback')}
            balanced=sum(len(cover(truth,s[:k]))/n for s in prefixes)/len(prefixes)
            symbolic=len(cover(truth,selections[b]))/n
            by_budget[b]=dict(**old,balanced_boundary=balanced,symbolic_proxy=symbolic,
                              symbolic_indices=list(selections[b]),proxy_distinct=len(proxy))
        rows.append(dict(family=f,t=t,u=u,denominator=len(truth),budgets=by_budget))
    metrics={str(k):{arm:sum(r['budgets'][str(k)][arm] for r in rows)/len(rows)
                     for arm in ('boundary','pairwise','learned_feedback','learned_no_feedback','balanced_boundary','symbolic_proxy')}
             for k in (1,2)}
    return dict(version='0.1.0',scope='posthoc_synthetic_audit',source_raw_sha256=RAW_SHA,
                checked_original_arm_budget_records=checked,instances=len(rows),metrics=metrics,rows=rows,
                symbolic_proxy_operators=list(PROXY),heldout_scoring_operators=list(TEST))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();source=args.source.read_bytes()
    if hashlib.sha256(source).hexdigest()!=RAW_SHA: raise ValueError('unqualified source raw hash')
    args.output.write_text(json.dumps(audit(json.loads(source)),sort_keys=True,separators=(',',':'),allow_nan=False)+'\n')


if __name__=='__main__': main()
