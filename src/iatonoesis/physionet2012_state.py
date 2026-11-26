"""Measured HR window forecast using the exact quarantined PhysioNet 2012 partition."""
import argparse
import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path

MANIFEST = '7b145302046c277d4d814e2ad7187d10fc377c2ec2ac844e74cb62c53286c7da'
ARCHIVES = {'A':'8cb250f179cd0952b4b9ebcf8954b63d70383131670fac1cfee13deaa13ca920',
            'B':'b1637a2a423a8e76f8f087896cfc5fdf28f88519e1f4e874fbda69b2a64dac30'}
PARTITIONS = {'A':{'development':3212,'calibration':787,'quarantine':1},'B':{'test':3999,'quarantine':1}}
ELIGIBLE = {'A':{'1':3643,'3':3644,'6':3656},'B':{'1':3665,'3':3661,'6':3643}}
HORIZONS = (1,3,6)
SPLITS = ('development','calibration','test')


def verify(frozen):
    if frozen['manifest_sha256'] != MANIFEST or frozen['audit']['quarantined_records'] != 2 or frozen['audit']['cross_cohort_components'] != 1:
        raise ValueError('source manifest or quarantine mismatch')
    if set(frozen['counts']) != set(ARCHIVES):
        raise ValueError('source cohort mismatch')
    for cohort, digest in ARCHIVES.items():
        parts = PARTITIONS[cohort]
        expected = dict(archive_sha256=digest,records=sum(parts.values()),retained=sum(parts.values())-parts['quarantine'],partitions=parts,eligible_observed_targets=ELIGIBLE[cohort])
        if frozen['counts'][cohort] != expected:
            raise ValueError('source count or archive mismatch')


def finite(value):
    return type(value) in (int,float) and math.isfinite(value)


def project(rows,horizon):
    if type(horizon) is not int or horizon not in HORIZONS:
        raise ValueError('invalid forecast horizon')
    out,seen = [],set()
    for row in rows:
        ident,split = row['id'],row['split']
        if not isinstance(ident,str) or not ident or ident in seen:
            raise ValueError('invalid or duplicate record identity')
        seen.add(ident)
        if split not in SPLITS:
            raise ValueError('invalid retained partition')
        if str(horizon) not in row['targets']:
            continue
        hist,target = row['history'],row['targets'][str(horizon)]
        if len(hist)!=6 or not any(v is not None for v in hist) or not all(v is None or finite(v) for v in hist) or not finite(target):
            raise ValueError('invalid eligible measured case')
        out.append(dict(id=ident,split=split,history=list(hist),target=target))
    return out


def protect_strata(strata):
    # Suppress complementary strata in a partition if a nonempty cell is small.
    blocked = {prefix for prefix in ('recency_','missing_') if any(k.startswith(prefix) and 0<v['n']<10 for k,v in strata.items())}
    return {k:dict(n=v['n'],status='suppressed_small_stratum' if v['n']<10 else 'suppressed_complementary',arms=None,paired=None)
            if v['n']<10 or any(k.startswith(prefix) for prefix in blocked) else v for k,v in strata.items()}


def evaluate_horizon(rows,revision,horizon,*,synthetic=False):
    from . import measured_pilot as prior, measured_replication as replication
    from .metric_extensions import conformal_radius
    from .run_contracts import canonical_sha256 as digest
    from .typed_results import run_typed

    dev,cal,test = ([r for r in rows if r['split']==p] for p in SPLITS)
    model = prior.fit_state(dev)
    radii,predictors = {},{}
    for arm in replication.ARMS:
        radius = conformal_radius([abs(r['target']-replication.forecast(model,arm,r['history'],horizon)) for r in cal])
        radii[arm] = radius
        def predict(x,arm=arm,radius=radius):
            v = replication.forecast(model,arm,x['history'],horizon)
            return dict(value=v,lower=v-radius,upper=v+radius)
        predictors[arm] = predict
    name = 'p12-fixed-cutoff-measured-window-h'+str(horizon)+'-v0.1.0'
    inputs = {r['id']:dict(history=r['history'],cutoff_minute=360,target_window_minutes=[360+60*(horizon-1),360+60*horizon]) for r in rows}
    refs = {r['id']:r['target'] for r in rows}
    data = dict(schema_version='0.1.0',dataset_id=name,kind='synthetic' if synthetic else 'public',source='authored fixture' if synthetic else 'https://physionet.org/content/challenge-2012/1.0.0/',revision=revision,sha256=digest(inputs),rights=dict(status='approved',licence='MIT' if synthetic else 'ODC-By-1.0',evidence='authored fixture' if synthetic else 'public technical benchmark only; https://physionet.org/content/challenge-2012/1.0.0/'),reference=dict(kind='deterministic_oracle' if synthetic else 'published_labels',revision=revision,sha256=digest(refs)),grouping_keys=['subject'],rows=[dict(id=r['id'],split=r['split'],groups={'subject':r['id']}) for r in rows])
    exp = dict(schema_version='0.1.0',experiment_id=name,track_task='T15.001',dataset_id=name,dataset_sha256=data['sha256'],reference_sha256=data['reference']['sha256'],split='test',case_ids=[r['id'] for r in test],primary_metric='mae',metric_kind='continuous',metric_options={'intervals':True},unit='subject',seed=replication.SEED,arms=[dict(id=a,role='deterministic' if a=='last' else 'classical') for a in replication.ARMS],budget=dict(max_cases=len(test),max_seconds=60),claim_boundary='synthetic_only' if synthetic else 'benchmark_only')
    model_hash = digest(model)
    models = {a:dict(id=a,revision=revision,licence='MIT',weights_sha256=model_hash) for a in replication.ARMS if a!='last'}
    result = run_typed(exp,data,inputs,refs,predictors=predictors,models=models,source_commit=revision)
    if any(a['status']!='executed' for a in result['manifest']['arms']):
        raise ValueError('typed forecast arm failed')
    predictions = {a:[r['prediction']['value'] for r in result['predictions'][a]] for a in replication.ARMS}
    return dict(counts=dict(Counter(r['split'] for r in rows)),receipt=result['manifest'],strata=protect_strata(replication.stratified(test,predictions,radii)))


def main():
    from . import physionet2012 as source, physionet2012_grouped as grouped
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--revision',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();stage='configuration'
    try:
        if not re.fullmatch(r'[0-9a-f]{40}',args.revision):
            raise ValueError('invalid revision')
        stage='archive_acquisition'
        archives={c:source.acquire(c) for c in ARCHIVES}
        if any(hashlib.sha256(raw).hexdigest()!=ARCHIVES[c] for c,raw in archives.items()):
            raise ValueError('archive hash mismatch')
        stage='grouped_freeze'
        frozen=grouped.freeze_grouped(archives);verify(frozen)
        expected = Counter()
        for parts in PARTITIONS.values():
            expected.update({k:v for k,v in parts.items() if k!='quarantine'})
        if Counter(r['split'] for r in frozen['rows'])!=expected:
            raise ValueError('retained partition mismatch')
        output=dict(scope='public_recorded_hr_window_benchmark_not_clinical_admission',source_manifest_sha256=MANIFEST,archives=ARCHIVES,source_commit=args.revision,cutoff_minute=360,quarantined_records=2,windows={})
        stage='projection'
        rows={h:project(frozen['rows'],h) for h in HORIZONS}
        for h,rs in rows.items():
            n=Counter(r['split'] for r in rs)
            if n['test']!=ELIGIBLE['B'][str(h)] or n['development']+n['calibration']!=ELIGIBLE['A'][str(h)]:
                raise ValueError('eligible target count mismatch')
        stage='benchmark'
        for h,rs in rows.items():
            output['windows'][str(h)]=evaluate_horizon(rs,args.revision,h)
        output['limitations']=['first recorded HR in each prespecified hour window, not exact-horizon or latent state','eligibility depends on future recorded target; no clinical-need or missing-value claim','six prior hourly bins use last available value; no minute-level model','A/B not verified sites; no cross-dataset patient independence established','no individual predictions, patient identifiers or weights exported; small strata suppressed','descriptive paired intervals; no clinical or institutional acceptance']
    except Exception as exc:
        args.output.write_text(json.dumps(dict(status='failed',stage=stage,error_type=type(exc).__name__,scope='aggregate_only'))+'\n')
        raise SystemExit(1) from None
    args.output.write_text(json.dumps(output,sort_keys=True,indent=2,allow_nan=False)+'\n')


if __name__=='__main__':
    main()
