"""Paired set recovery and regression counts; no causal or calibration claim."""
import argparse
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


def items(xs):
    if not isinstance(xs, list):
        raise ValueError('expected list of items')
    keys = [json.dumps(x, sort_keys=True, separators=(',', ':'), allow_nan=False) for x in xs]
    if len(keys) != len(set(keys)):
        raise ValueError('duplicate item')
    return set(keys)


def index(rows):
    out = {}
    for row in rows:
        key = row['id']
        if key in out:
            raise ValueError('duplicate case')
        out[key] = row
    return out


def compare(baseline, challenger):
    """Compare identical case/reference/family sets, preserving omitted targets."""
    a,b=index(baseline),index(challenger)
    if not a or a.keys()!=b.keys():
        raise ValueError('case set mismatch')
    counts=Counter(); families=defaultdict(Counter)
    for key in sorted(a):
        x,y=a[key],b[key]
        g=items(x['gold'])
        if g!=items(y['gold']) or x['groups']!=y['groups'] or not x['groups'].get('family'):
            raise ValueError('reference or group mismatch')
        p=items(x['prediction']) if x['prediction'] is not None else set()
        q=items(y['prediction']) if y['prediction'] is not None else set()
        d=dict(shared_correct=len(g&p&q),new_correct=len((g&q)-p),lost_correct=len((g&p)-q),
               shared_missed=len(g-(p|q)),new_false=len(q-g-p),removed_false=len(p-g-q),
               shared_false=len(p&q-g),baseline_abstentions=int(x['prediction'] is None),
               challenger_abstentions=int(y['prediction'] is None),cases=1)
        counts.update(d); families[x['groups']['family']].update(d)
    return dict(total=dict(counts),by_family={k:dict(v) for k,v in sorted(families.items())})


def audit(path, expected_sha):
    if hashlib.sha256(path.read_bytes()).hexdigest()!=expected_sha:
        raise ValueError('receipt digest mismatch')
    with gzip.open(path,'rt',encoding='utf-8') as stream:
        receipt=json.load(stream)
    if receipt['claim_boundary']!='synthetic_only' or receipt['canonical_acceptance'] is not False:
        raise ValueError('unexpected claim boundary')
    raw=receipt['modalities']
    pairs={}
    for modality in ('text','ocr'):
        for baseline in ('flat','right_only'):
            pairs[f'{modality}_{baseline}_vs_bidirectional']=compare(raw[modality]['predictions'][baseline],raw[modality]['predictions']['bidirectional'])
    pairs['text_vs_ocr_bidirectional']=compare(raw['text']['predictions']['bidirectional'],raw['ocr']['predictions']['bidirectional'])
    return dict(schema_version='0.1.0',claim_boundary='synthetic_only_posthoc_replay',receipt_sha256=expected_sha,
                freeze_revision=receipt['freeze_revision'],fixture_sha256=receipt['fixture_sha256'],pairs=pairs)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,required=True)
    p.add_argument('--sha256',required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    a.output.write_text(json.dumps(audit(a.input,a.sha256),indent=2,sort_keys=True)+'\n',encoding='utf-8')


if __name__=='__main__':
    main()
