"""Typed paired result envelope for trusted local continuous/rank/calibration/mutation adapters."""
import copy
import math
import platform
import re
import time

from .metric_extensions import calibration, continuous, mutation_coverage, ranking
from .run_contracts import canonical_sha256 as digest, validate_experiment

METRICS = {'continuous': {'mae','mse','rmse','interval_coverage'},
           'ranking': {'ndcg','precision','recall'}, 'calibration': {'brier','ece'},
           'mutation': {'mean_defect_coverage'}}


def finite(x):
    return type(x) in (int,float) and math.isfinite(x)


def provenance(model):
    return isinstance(model,dict) and all(isinstance(model.get(k),str) and model[k].strip()
                                         for k in ('id','revision','licence'))


def prepare(exp,data,inputs,refs):
    validate_experiment(exp,data)
    kind, options = exp.get('metric_kind'), exp.get('metric_options',{})
    if kind not in METRICS or exp['primary_metric'] not in METRICS[kind] or not isinstance(options,dict):
        raise ValueError('unknown typed metric')
    allowed = {'intervals'} if kind=='continuous' else {'bins'} if kind=='calibration' else set()
    if set(options)-allowed or ('intervals' in options and type(options['intervals']) is not bool):
        raise ValueError('invalid metric options')
    if exp['primary_metric']=='interval_coverage' and not options.get('intervals'):
        raise ValueError('intervals required for primary metric')
    if kind=='calibration' and (type(options.get('bins',10)) is not int or not 1<=options.get('bins',10)<=100):
        raise ValueError('invalid calibration bins')
    if digest(inputs)!=data['sha256'] or digest(refs)!=data['reference']['sha256']:
        raise ValueError('input or reference hash mismatch')
    ids={r['id'] for r in data['rows']}
    if set(inputs)!=ids or set(refs)!=ids:
        raise ValueError('input/reference ID mismatch')
    for ref in refs.values():
        try:
            if kind=='continuous' and not finite(ref): raise ValueError('not finite')
            if kind=='calibration' and (type(ref) is not int or ref not in (0,1)): raise ValueError('not binary')
            if kind=='ranking': ranking(sorted(ref['qrels']),ref['qrels'],ref['k'])
            if kind=='mutation': mutation_coverage(ref['signatures'],[],pool_size=ref['pool_size'],budget=ref['budget'])
        except (ValueError,TypeError,KeyError,OverflowError) as exc:
            raise ValueError('invalid reference for typed metric') from exc
    return kind,options


def summarize(kind, options, rows, refs):
    pairs=[(refs[r['id']],r['prediction']) for r in rows if r['prediction'] is not None]
    total, scored=len(rows),len(pairs)
    out=dict(total=total,scored=scored,abstained=total-scored,decision_coverage=scored/total)
    if kind=='continuous':
        intervals=options.get('intervals',False)
        pred=[]; widths=[]; hits=[]
        for ref,p in pairs:
            if intervals:
                if not isinstance(p,dict) or set(p)!={'value','lower','upper'} or not all(finite(p[k]) for k in p) or not p['lower']<=p['value']<=p['upper']:
                    raise ValueError('invalid interval prediction')
                widths.append(p['upper']-p['lower']);hits.append(p['lower']<=ref<=p['upper']);p=p['value']
            if not finite(p): raise ValueError('invalid continuous prediction')
            pred.append(p)
        metrics=continuous([ref for ref,_ in pairs],pred) if pairs else dict(n=0,mae=None,mse=None,rmse=None)
        out.update(metrics)
        if intervals: out.update(interval_n=scored,interval_coverage=sum(hits)/scored if scored else None,
                                 mean_interval_width=sum(widths)/scored if scored else None)
    elif kind=='calibration':
        out.update(calibration([r for r,_ in pairs],[p for _,p in pairs],bins=options.get('bins',10)) if pairs else dict(n=0,brier=None,ece=None,bins=[]))
    else:
        case=[]
        for ref,p in pairs:
            if not isinstance(p,list): raise ValueError('rank or selected cases must be a list')
            if kind=='ranking': case.append(ranking(p,ref['qrels'],ref['k']))
            else: case.append(mutation_coverage(ref['signatures'],p,pool_size=ref['pool_size'],budget=ref['budget']))
        keys=('ndcg','precision','recall') if kind=='ranking' else ('coverage',)
        defined={}
        for key in keys:
            vals=[m[key] for m in case if m[key] is not None]
            name='mean_defect_coverage' if key=='coverage' else key
            out[name]=sum(vals)/len(vals) if vals else None;defined[name]=len(vals)
        out['defined_counts']=defined
        if kind=='mutation': out.update(distinct_defects=sum(m['distinct_defects'] for m in case),detected=sum(m['detected'] for m in case))
    return out


def manifest_base(exp,data,source_commit):
    if not isinstance(source_commit,str) or not re.fullmatch(r'[0-9a-f]{40}',source_commit):
        raise ValueError('invalid source commit')
    return dict(schema_version='0.2.0',source_commit=source_commit,experiment_id=exp['experiment_id'],
                config_sha256=digest(exp),dataset_sha256=data['sha256'],reference_sha256=data['reference']['sha256'],
                dataset_manifest_sha256=digest(data),seed=exp['seed'],claim_boundary=exp['claim_boundary'],
                metric_kind=exp['metric_kind'],primary_metric=exp['primary_metric'])


def validate_typed(result,exp,data,inputs,refs):
    kind,options=prepare(exp,data,inputs,refs)
    manifest=result['manifest']; base=manifest_base(exp,data,manifest['source_commit'])
    if any(manifest.get(k)!=v for k,v in base.items()) or not isinstance(manifest.get('environment'),str) or not manifest['environment']:
        raise ValueError('manifest binding mismatch')
    declared={a['id']:a for a in exp['arms']}
    arms=manifest['arms'];outputs=result['predictions'];failures=result['failure_artifacts']
    if len(arms)!=len(declared) or {a['id'] for a in arms}!=set(declared): raise ValueError('arm coverage mismatch')
    if set(outputs)!={a['id'] for a in arms if a.get('status')=='executed'} or set(failures)!={a['id'] for a in arms if a.get('status')=='failed'}:
        raise ValueError('artifact coverage mismatch')
    for a in arms:
        key=a['id'];status=a.get('status')
        if status!='executed':
            if status not in ('failed','unavailable','skipped') or not a.get('reason') or a.get('metrics') is not None or a.get('predictions_sha256') is not None:
                raise ValueError('non-executed arm has invalid receipt')
            continue
        rows=outputs[key]
        if [r['id'] for r in rows]!=exp['case_ids'] or a.get('predictions_sha256')!=digest(rows):
            raise ValueError('prediction hash or ordered case mismatch')
        if declared[key]['role']!='deterministic' and not provenance(a.get('model')):
            raise ValueError('missing model provenance')
        if not finite(a.get('elapsed_seconds')) or not 0<=a['elapsed_seconds']<=exp['budget']['max_seconds']:
            raise ValueError('invalid elapsed time')
        if a.get('metrics')!=summarize(kind,options,rows,refs): raise ValueError('metric recomputation mismatch')


def run_typed(exp,data,inputs,refs,*,predictors,source_commit,models=None,clock=time.perf_counter):
    kind,options=prepare(exp,data,inputs,refs)
    manifest=manifest_base(exp,data,source_commit)
    models=models or {};declared={a['id'] for a in exp['arms']}
    if set(predictors)-declared or set(models)-declared: raise ValueError('undeclared arm')
    manifest.update(environment=platform.python_version(),arms=[])
    result=dict(manifest=manifest,predictions={},failure_artifacts={})
    for arm in exp['arms']:
        key=arm['id'];predict=predictors.get(key);model=models.get(key)
        if not callable(predict) or (arm['role']!='deterministic' and not provenance(model)):
            manifest['arms'].append(dict(id=key,status='unavailable',reason='adapter or model provenance unavailable'));continue
        raw=[];start=clock()
        try:
            for case_id in exp['case_ids']:
                if clock()-start>exp['budget']['max_seconds']: raise TimeoutError('arm budget exceeded')
                prediction=predict(copy.deepcopy(inputs[case_id]))
                if clock()-start>exp['budget']['max_seconds']: raise TimeoutError('arm budget exceeded')
                row=dict(id=case_id,prediction=copy.deepcopy(prediction));digest(row)
                # Reject invalid predictions before retaining a completed case.
                summarize(kind,options,[row],refs)
                raw.append(row)
            metrics=summarize(kind,options,raw,refs);elapsed=clock()-start
            if not finite(elapsed) or not 0<=elapsed<=exp['budget']['max_seconds']: raise TimeoutError('arm budget exceeded')
            a=dict(id=key,status='executed',predictions_sha256=digest(raw),metrics=metrics,elapsed_seconds=elapsed)
            if arm['role']!='deterministic': a['model']=copy.deepcopy(model)
            result['predictions'][key]=raw;manifest['arms'].append(a)
        except Exception as exc:
            result['failure_artifacts'][key]=raw;manifest['arms'].append(dict(id=key,status='failed',reason=type(exc).__name__))
    validate_typed(result,exp,data,inputs,refs)
    return result
