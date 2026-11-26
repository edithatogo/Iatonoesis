"""Retrospective risk and component interaction audit of the frozen SciFact replay."""
import argparse
import hashlib
import json
import math
import zipfile
from collections import defaultdict
from pathlib import Path

from .scifact_pipeline import LABELS, digest, pipeline

ZIP_SHA = 'b0c15678940e3c43c76922ff9fc2e172b45fb8e61cbdb64297e34bd92c8f8d61'
RESULT_SHA = '40eb749415cb065e26a4d6ea3613d8222b76a79766d469d4a71cef5a73624924'
PREDICTIONS_SHA = '76126dacae5ee20ac1d97346f22baa11e9d19d6986fd36ec6565461d5ba82549'
MODELS = ('rules', 'linear', 'small_mlp', 'nli')


def frontier(rows, model, *, max_error, min_retained, min_negative, max_false_support):
    """Largest complete confidence prefix meeting descriptive observed risk limits."""
    if not 0 <= max_error <= 1 or not 0 <= max_false_support <= 1 or min_retained < 1 or min_negative < 0:
        raise ValueError('invalid risk limits')
    buckets = defaultdict(list)
    ids = set()
    for row in rows:
        pred, conf = row['predictions'][model]
        if row['id'] in ids or row['label'] not in LABELS or pred not in LABELS or not math.isfinite(conf) or not 0 <= conf <= 1:
            raise ValueError('invalid prediction')
        ids.add(row['id'])
        buckets[conf].append((row['label'], pred))
    retained = correct = false_support = negatives = 0
    best = dict(status='no_feasible_prefix', total=len(rows), retained=0, review=len(rows))
    for score in sorted(buckets, reverse=True):
        for ref, pred in buckets[score]:
            retained += 1
            correct += ref == pred
            negatives += ref != 'SUPPORT'
            false_support += pred == 'SUPPORT' and ref != 'SUPPORT'
        error = (retained-correct)/retained
        fs = false_support/negatives if negatives else None
        if retained >= min_retained and negatives >= min_negative and error <= max_error and (fs is None or fs <= max_false_support):
            best = dict(status='feasible_observed_prefix', total=len(rows), retained=retained, review=len(rows)-retained,
                        correct=correct, error_rate=error, false_support=false_support, false_support_denominator=negatives,
                        false_support_rate=fs, coverage=retained/len(rows), diagnostic_threshold=score)
    return best


def interactions(rows, expected):
    cases = [dict(r,claim_id=int(r['id'].split(':')[0])) for r in rows]
    crossed = {}
    for rank in ('bm25','pretrained'):
        ranks = {r['id']:r['ranks'][rank] for r in cases}
        for model in MODELS:
            pred = {r['id']:r['predictions'][model] for r in cases}
            result = pipeline(cases,ranks,pred)
            key = ('bm25' if rank=='bm25' else 'pretrained_reranker')+'_'+model
            if result['correct'] != expected[key]['correct'] or result['false_support'] != expected[key]['false_support'] or result['claims'] != expected[key]['claims']:
                raise ValueError('crossed pipeline replay mismatch')
            crossed[key]=result
    baseline = crossed['pretrained_reranker_rules']['correct']-crossed['bm25_rules']['correct']
    return dict(crossed=crossed, ranker_substitution={m:crossed['pretrained_reranker_'+m]['correct']-crossed['bm25_'+m]['correct'] for m in MODELS},
                interaction_vs_rules={m:crossed['pretrained_reranker_'+m]['correct']-crossed['bm25_'+m]['correct']-baseline for m in MODELS})


def audit(artifact):
    if hashlib.sha256(Path(artifact).read_bytes()).hexdigest()!=ZIP_SHA:
        raise ValueError('artifact hash mismatch')
    with zipfile.ZipFile(artifact) as z:
        raw=z.read('result.json')
    if hashlib.sha256(raw).hexdigest()!=RESULT_SHA:
        raise ValueError('result hash mismatch')
    src=json.loads(raw); rows=src['predictions']
    if len(rows)!=339 or digest(rows)!=PREDICTIONS_SHA:
        raise ValueError('prediction digest mismatch')
    policies={}
    for risk in (.1,.2,.3,.4,.5):
        policies[str(risk)]={m:frontier(rows,m,max_error=risk,min_retained=30,min_negative=20,max_false_support=.05) for m in MODELS}
    return dict(scope='retrospective test-label diagnostic only; not threshold selection or clinical safety evidence',source_zip_sha256=ZIP_SHA,source_result_sha256=RESULT_SHA,
                prediction_sha256=PREDICTIONS_SHA,min_retained=30,min_negative=20,max_false_support=.05,frontiers=policies,
                **interactions(rows,src['pipeline']),observed_timing=src['timing'],compute_limit='same observed input budgets, not an equal-compute experiment; timing includes calibration and test for classifiers')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifact',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    args.output.write_text(json.dumps(audit(args.artifact),indent=2,sort_keys=True)+'\n')


if __name__=='__main__':
    main()
