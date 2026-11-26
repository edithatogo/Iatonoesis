"""Read-only descriptive synthesis of the frozen #57 and #75 aggregate receipts."""
import argparse
import hashlib
import json
import math
from pathlib import Path

PINS = {
    '2019': dict(key='state', run=45815419126, artifact=15116315352,
                 sha256='c5df78bb351ea395eb112fcccddbab16b1cb95094f07863ddcd752bf8f1b2774',
                 manifest='5b6073d8241353b1f56e431b05c68fc544b15b9da2cb9c9ce5ac41686dc7426f'),
    '2012': dict(key='windows', run=45902571448, artifact=15155419391,
                 sha256='0e8c74ed325539858302ba774d1e6b4e8874dca1964ea469c117eddaf03bccaf',
                 manifest='7b145302046c277d4d814e2ad7187d10fc377c2ec2ac844e74cb62c53286c7da'),
}
HORIZONS = (1, 3, 6)
ARMS = ('mean', 'last', 'ar1', 'kalman', 'ridge', 'temporal_mlp')
FAMILIES = ('recency_', 'missing_')
METRICS = ('mae', 'mse', 'rmse', 'interval_coverage', 'interval_width')


def near(a, b):
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-8)


def delta(s):
    p = s['paired']['ridge']
    if p['n'] != s['n'] or not near(p['difference'], s['arms']['ridge']['mae']-s['arms']['last']['mae']):
        raise ValueError('inconsistent paired loss')
    return p['difference']


def standardize(sources, prefix):
    keys = [prefix+s for s in ('0', '1_2', '3_plus')]
    keys = [k for k in keys if all(v[k]['n'] >= 10 and v[k]['arms'] is not None for v in sources.values())]
    if not keys:
        return None
    counts = {d:sum(v[k]['n'] for k in keys) for d,v in sources.items()}
    weights = {k:sum(v[k]['n']/counts[d] for d,v in sources.items())/len(sources) for k in keys}
    adjusted = {d:sum(weights[k]*delta(v[k]) for k in keys) for d,v in sources.items()}
    return dict(counts=counts, weights=weights, standardized=adjusted,
                contrast_2019_minus_2012=adjusted['2019']-adjusted['2012'])


def validate(group):
    strata, receipt = group['strata'], group['receipt']
    overall = strata['all']
    n = group['counts']['test']
    if type(n) is not int or n < 10 or overall['n'] != n or (receipt['metric_kind'],receipt['primary_metric'],receipt['claim_boundary']) != ('continuous','mae','benchmark_only'):
        raise ValueError('overall denominator or contract mismatch')
    arms = receipt['arms']
    if len(arms) != len(ARMS) or {a['id'] for a in arms} != set(ARMS) or set(overall['arms']) != set(ARMS):
        raise ValueError('arm membership mismatch')
    for arm in arms:
        m,s = arm['metrics'],overall['arms'][arm['id']]
        if arm['status'] != 'executed' or (m['total'],m['scored'],m['abstained'],s['n']) != (n,n,0,n):
            raise ValueError('arm denominator mismatch')
        if any(not near(m['mean_interval_width' if k=='interval_width' and 'mean_interval_width' in m else k], s[k]) for k in METRICS):
            raise ValueError('overall metric mismatch')
        if s['interval_n'] != n or not near(s['interval_covered']/n,s['interval_coverage']) or not near(s['rmse']**2,s['mse']):
            raise ValueError('overall metric consistency failure')
    delta(overall)
    for prefix in FAMILIES:
        cells = [strata[prefix+k] for k in ('0','1_2','3_plus')]
        if any(type(c['n']) is not int or c['n']<0 for c in cells) or sum(c['n'] for c in cells)!=n:
            raise ValueError('stratum denominator mismatch')
        observed = [c for c in cells if c['n']]
        for cell in observed:
            if cell['arms'] is None:
                continue
            if any(m['n']!=cell['n'] or m['interval_n']!=cell['n'] for m in cell['arms'].values()):
                raise ValueError('cell denominator mismatch')
            delta(cell)
        if all(c['arms'] is not None for c in observed):
            for arm in ARMS:
                for k in ('mae','mse','interval_coverage'):
                    if not near(sum(c['n']*c['arms'][arm][k] for c in observed)/n,overall['arms'][arm][k]):
                        raise ValueError('stratum metric conservation failure')
    return strata


def analyze(payloads):
    sources={}
    for d,pin in PINS.items():
        raw=payloads[d]
        if hashlib.sha256(raw).hexdigest()!=pin['sha256']:
            raise ValueError('receipt digest mismatch')
        obj=json.loads(raw)
        if obj['source_manifest_sha256']!=pin['manifest']:
            raise ValueError('source manifest mismatch')
        sources[d]=obj[pin['key']]
    windows={}
    for h in HORIZONS:
        grouped={d:validate(v[str(h)]) for d,v in sources.items()}
        row={}
        for d,v in grouped.items():
            s=v['all']; a=s['arms']; p=s['paired']['ridge']
            row[d]=dict(n=s['n'], best_mae=[k for k in ARMS if a[k]['mae']==min(m['mae'] for m in a.values())],
                        best_rmse=[k for k in ARMS if a[k]['rmse']==min(m['rmse'] for m in a.values())],
                        ridge_minus_last_mae=delta(s), paired_descriptive_interval=[p['lower'],p['upper']],
                        last_ridge={k:[a['last'][k],a['ridge'][k]] for k in METRICS})
        row['recency']=standardize(grouped,'recency_')
        row['missingness']=standardize(grouped,'missing_')
        windows[str(h)]=row
    return dict(scope='posthoc_aggregate_only_descriptive_heterogeneity',sources=PINS,windows=windows,
                limitations=['2019 rolling cutoff versus 2012 fixed six-hour cutoff and first recorded HR in target windows',
                             'different development and calibration sample sizes and observation processes',
                             'one-dimensional common-support standardization only; joint strata and cross-window covariance unavailable',
                             'no pooled interval or interaction test, no cross-source patient independence or hospital identity established',
                             'small or suppressed strata excluded, no patient-level input or new acquisition'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--p2019',type=Path,required=True)
    parser.add_argument('--p2012',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    out=analyze({'2019':args.p2019.read_bytes(),'2012':args.p2012.read_bytes()})
    args.output.write_text(json.dumps(out,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n')


if __name__=='__main__':
    main()
