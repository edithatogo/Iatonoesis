"""Source-pinned temporal ontology retrieval, transfer and calibrated proposal audit."""
import argparse
import hashlib
import json
import math
import random
import re
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from . import mondo_temporal as mt

SOURCES={
    'MONDO':('monarch-initiative/mondo','mondo.obo',{
        '2025-06-03':(52369032,'2942bfc8713f93d038c9f2659f1a8200197e32e244f45b071ba8d14c4073b808'),
        '2025-09-02':(52649281,'0f359c53ea36750aef1c7619588b8ee4c3e6daebe9ccdfebb04d7da29d04ef30'),
        '2025-12-02':(50592949,'7d0927e652f0a5af4af94478f7bc9484e183df0c4621ba933833244bb72bd738'),
        '2026-02-03':mt.PINS['2026-02-03']}),
    'HP':('obophenotype/human-phenotype-ontology','hp.obo',{
        '2025-11-24':(10323898,'d1f3e411add1a1bbe68c00b628f7a2c8210433de1e478c6b79924a7c1e4dc737'),
        '2026-06-23':(11222341,'a5092cbdf605f568403cf7380d9173015692433b2cc631bc5c1b053876b1b'),
        '2026-09-01':(10863613,'93dace952fcb3ec4728818857f6ba76bc2d5312f4d83266519b8694b8e798f22')})}
MODEL='cambridgeltl/SapBERT-from-PubMedBERT-fulltext'
MODEL_REF='090663c'
WEIGHTS='a4696930afef9aab296196d3d2142216c44cba24f21b4f285ceca7af21025614'


def parse(path,version,prefix):
    pattern=re.compile(re.escape(prefix)+r':[0-9]{7}')
    raw=path.read_text(encoding='utf-8'); header=raw.split('\n[',1)[0]
    if not any(x.startswith('data-version: ') and version in x for x in header.splitlines()):
        raise ValueError('version mismatch')
    result={}; seen=set()
    for stanza in raw.split('\n[Term]\n')[1:]:
        lines=stanza.split('\n[',1)[0].splitlines()
        idline=next((x[4:] for x in lines if x.startswith('id: ')),'')
        if not pattern.fullmatch(idline): continue
        if idline in seen: raise ValueError('duplicate term')
        seen.add(idline)
        if 'is_obsolete: true' in lines: continue
        name=next((x[6:] for x in lines if x.startswith('name: ')),'')
        if not name: raise ValueError('missing name')
        parents={x[6:].split()[0] for x in lines if x.startswith('is_a: ')}
        result[idline]={'name':name,'parents':parents}
    for k,n in result.items():
        n['parents'].intersection_update(result)
        if k in n['parents']: raise ValueError('self parent')
    if not result: raise ValueError('empty ontology')
    return result


def queries(old,new,salt):
    changed=[]; unchanged=[]; excluded=0
    for child in sorted(new):
        added=new[child]['parents']-old.get(child,{'parents':set()})['parents']
        gold=sorted(p for p in added if child in old and p in old)
        excluded+=len(added)-len(gold)
        if gold: changed.append({'child':child,'gold':gold})
        elif child in old and not added: unchanged.append(child)
    sampled=sorted(unchanged,key=lambda x:mt.digest([salt,x]))[:len(changed)]
    out=sorted(changed+[{'child':c,'gold':[]} for c in sampled],key=lambda x:x['child'])
    return out,dict(changed=len(changed),unchanged=len(sampled),eligible_edges=sum(len(x['gold']) for x in changed),excluded_new_endpoints=excluded,manifest_sha256=mt.digest(out))


def factorial():
    return [''.join(c for i,c in enumerate('LSG') if bits&(1<<i)) for bits in range(8)]


def pool(nodes,child,channels,arm,cap,salt,index=None):
    if arm not in factorial() or cap<1: raise ValueError('invalid arm or cap')
    idx=index or mt._index(nodes); children=idx[0]
    blocked={child}|nodes[child]['parents']; stack=list(children[child]); descendants=set()
    while stack:
        node=stack.pop()
        if node not in descendants:
            descendants.add(node); stack.extend(children[node]-descendants)
    eligible=set(nodes)-blocked-descendants
    chosen=[]; lists=[iter(x for x in channels[c] if x in eligible) for c in arm]
    while lists and len(chosen)<cap:
        remaining=[]
        for seq in lists:
            x=next(seq,None)
            while x is not None and x in chosen: x=next(seq,None)
            if x is not None:
                chosen.append(x); remaining.append(seq)
            if len(chosen)==cap: break
        lists=remaining
    if len(chosen)<cap:
        rem=sorted(eligible-set(chosen)); chosen+=random.Random(mt.digest([salt,child])).sample(rem,min(cap-len(chosen),len(rem)))
    return chosen


def gate(fit,confirm,min_count=60,target=.20):
    """Select a confidence cutoff on fit; test it once on disjoint confirmation rows."""
    for t in (0.,.05,.1,.2,.4,.8):
        a=[ok for s,ok in fit if s>=t]
        if len(a)>=min_count and mt._upper(a.count(False),len(a))<=target:
            b=[ok for s,ok in confirm if s>=t]
            bound=mt._upper(b.count(False),len(b))
            return dict(threshold=t if len(b)>=min_count and bound<=target else None,chosen=t,fit=len(a),confirmation=len(b),confirmation_errors=b.count(False),upper=bound)
    return dict(threshold=None,fit_eligible=len(fit),confirmation_eligible=len(confirm))


def prepare(nodes,refs,embeddings,salt):
    import numpy as np
    if not refs or len(refs)>5000: raise ValueError('empty or oversized query population')
    idx=mt._index(nodes); ids=idx[-1]; pos={k:i for i,k in enumerate(ids)}
    x=np.asarray([embeddings[nodes[k]['name']] for k in ids],dtype=np.float32)
    x/=np.maximum(np.linalg.norm(x,axis=1,keepdims=True),1e-12)
    results={f'{a or "none"}:{k}':[] for a in factorial() for k in (16,32,64)}
    for row in refs:
        c=row['child']; lex=set().union(*(idx[1][w] for w in idx[2][c])); neigh=nodes[c]['parents']|idx[0][c]
        topo=set().union(*(nodes[n]['parents']|idx[0][n] for n in neigh))
        sem=x@x[pos[c]]; order=np.argsort(-sem,kind='stable')
        channels={'L':sorted(lex,key=lambda p:(-mt._lex(mt.features(nodes,c,p,idx)),p)),
                  'G':sorted(topo,key=lambda p:(-mt._top(mt.features(nodes,c,p,idx)),p)),
                  'S':[ids[i] for i in order]}
        for arm in factorial():
            for k in (16,32,64):
                ps=pool(nodes,c,channels,arm,k,salt,idx)
                entry=dict(row,pool=ps)
                if arm=='LSG' and k==32:
                    entry.update(features=[mt.features(nodes,c,p,idx) for p in ps],semantic=[float(sem[pos[p]]) for p in ps])
                results[f'{arm or "none"}:{k}'].append(entry)
    return results


def graph_ranker(nodes,rows,training=None,messages=True,epochs=12):
    """Train/evaluate two-layer mean message-passing pair scorer on historical graph."""
    import torch
    from torch import nn
    torch.set_num_threads(2); torch.manual_seed(17)
    ids=sorted(nodes); pos={k:i for i,k in enumerate(ids)}; n=len(ids)
    x=torch.zeros(n,32); edges=set()
    for k in ids:
        i=pos[k]
        for w in re.findall(r'\w+',nodes[k]['name'].lower()): x[i,int(mt.digest(w)[:8],16)%32]+=1
        for p in nodes[k]['parents']:
            j=pos[p]; edges.update(((i,j),(j,i)))
    x=torch.nn.functional.normalize(x); e=sorted(edges)
    deg=[0]*n
    for i,j in e: deg[i]+=1
    indices=torch.tensor(e,dtype=torch.long).reshape(-1,2).T
    adj=torch.sparse_coo_tensor(indices,torch.tensor([1/deg[i] for i,j in e],dtype=torch.float32),(n,n)).coalesce()
    model=nn.ModuleList([nn.Linear(64,32),nn.Linear(64,16),nn.Linear(48,1)])
    def encode():
        h=x
        for layer in model[:2]:
            msg=torch.sparse.mm(adj,h) if messages else torch.zeros_like(h)
            h=layer(torch.cat((h,msg),1)).tanh()
        return h
    def score(h,r):
        a=h[pos[r['child']]].expand(len(r['pool']),-1); b=h[[pos[p] for p in r['pool']]]
        return model[2](torch.cat((a,b,a*b),1)).flatten()
    if training is None:
        eligible=[r for r in rows if set(r['gold'])&set(r['pool'])]
        if not eligible: raise ValueError('no retrieved training positives')
        opt=torch.optim.Adam(model.parameters(),lr=.02)
        for _ in range(epochs):
            h=encode(); losses=[]
            for r in eligible:
                target=torch.tensor([p in r['gold'] for p in r['pool']],dtype=torch.float32)
                losses.append(-(score(h,r).log_softmax(0)*target/target.sum()).sum())
            opt.zero_grad(); torch.stack(losses).mean().backward(); opt.step()
        training={k:v.detach().tolist() for k,v in model.state_dict().items()}
    else: model.load_state_dict({k:torch.tensor(v) for k,v in training.items()})
    with torch.no_grad():
        h=encode(); scores=[score(h,r).tolist() for r in rows]
    return training,scores


def compare(prepared,old,train=None):
    rows=prepared['LSG:32']; models={} if train is None else train; scores={}
    for arm in ('hybrid_rule','linear','neural','no_graph'):
        if arm!='hybrid_rule' and train is None: models[arm]=mt.fit(rows,arm)
        scores[arm]=mt.rank(rows,arm,models.get(arm))
    scores['semantic']=[r['semantic'] for r in rows]
    for arm,messages in [('gnn',True),('gnn_zero',False)]:
        models[arm],scores[arm]=graph_ranker(old,rows,models.get(arm),messages)
    return models,scores


def report_pool(prepared):
    out={}
    for key,rows in prepared.items():
        gold=sum(len(r['gold']) for r in rows); hits=sum(len(set(r['gold'])&set(r['pool'])) for r in rows)
        out[key]=dict(queries=len(rows),gold=gold,hits=hits,recall=hits/gold if gold else None,candidates=sum(len(r['pool']) for r in rows),pool_sha256=mt.digest([(r['child'],r['pool']) for r in rows]))
    return out


def factorial_effects(results):
    # Difference of differences over the complete fixed-budget factorial.
    effects={}
    for k in (16,32,64):
        values={a:results[f'{a or "none"}:{k}']['recall'] for a in factorial()}
        if any(v is None for v in values.values()): raise ValueError('missing reference edges')
        effects[str(k)]={f:sum(v*(1 if sum(c in a for c in f)%2==len(f)%2 else -1) for a,v in values.items())/4 for f in ('L','S','G','LS','LG','SG','LSG')}
    return effects


def fallback_receipt(cal,cs,test,ts,arm):
    def proposals(rows,scores):
        out=[]
        for r,a,b in zip(rows,scores['hybrid_rule'],scores[arm],strict=True):
            q=mt._ordered(r,a); p=mt._ordered(r,b)
            if len(q)>=2 and q[0][1]-q[1][1]<=.05 and p and p[0][0]!=q[0][0]:
                out.append((r['child'],p[0][1]-p[1][1] if len(p)>1 else 0.,p[0][0] in r['gold'],q[0][0] in r['gold']))
        return out
    c=proposals(cal,cs); t=proposals(test,ts)
    fit=[(s,ok) for k,s,ok,_ in c if int(mt.digest(k)[0],16)<8]; confirm=[(s,ok) for k,s,ok,_ in c if int(mt.digest(k)[0],16)>=8]
    g=gate(fit,confirm); selected=[x for x in t if g['threshold'] is not None and x[1]>=g['threshold']]
    return dict(g,calibration_eligible=len(c),test_eligible=len(t),activated=len(selected),confirmed=sum(x[2] for x in selected),baseline_confirmed=sum(x[3] for x in selected))


def load_encoder(root):
    import torch
    from huggingface_hub import HfApi,snapshot_download
    from transformers import AutoModel,AutoTokenizer
    info=HfApi().model_info(MODEL,revision=MODEL_REF,files_metadata=True)
    if not info.sha.startswith(MODEL_REF): raise ValueError('model revision mismatch')
    path=Path(snapshot_download(MODEL,revision=info.sha,allow_patterns=['README.md','config.json','model.safetensors','vocab.txt','*token*.json'],local_dir=root))
    if 'license: apache-2.0' not in (path/'README.md').read_text(): raise ValueError('model licence')
    receipt=mt.verify_source(path/'model.safetensors',437955508,WEIGHTS)
    receipt.update(revision=info.sha,files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(path.iterdir()) if p.is_file() and p.name!='model.safetensors'})
    tok=AutoTokenizer.from_pretrained(path,local_files_only=True,trust_remote_code=False)
    model=AutoModel.from_pretrained(path,local_files_only=True,trust_remote_code=False,use_safetensors=True).eval()
    torch.set_num_threads(4)
    def encode(names):
        result={}
        with torch.inference_mode():
            for i in range(0,len(names),128):
                batch=names[i:i+128]; inp=tok(batch,padding=True,truncation=True,max_length=25,return_tensors='pt')
                emb=model(**inp).last_hidden_state[:,0,:].numpy()
                result.update(zip(batch,emb,strict=True))
        return result
    return encode,receipt


def acquire(prefix,root):
    repo,name,pins=SOURCES[prefix]; snapshots=[]; receipts={}
    for date,(size,sha) in pins.items():
        p=root/name; url=f'https://github.com/{repo}/releases/download/v{date}/{name}'
        for attempt in range(3):
            try:
                with urllib.request.urlopen(url,timeout=90) as src,p.open('wb') as dest:
                    remaining=size
                    while data:=src.read(min(1048576,remaining+1)):
                        remaining-=len(data)
                        if remaining<0: raise ValueError('oversized source')
                        dest.write(data)
                break
            except (TimeoutError,urllib.error.URLError) as exc:
                p.unlink(missing_ok=True)
                transient=(isinstance(exc,TimeoutError) or isinstance(getattr(exc,'reason',None),TimeoutError) or getattr(exc,'code',None) in (429,500,502,503,504))
                if not transient or attempt==2: raise
                print(f'retry {prefix} {date} after {type(exc).__name__}',flush=True)
                time.sleep(2**attempt)
        receipts[date]=mt.verify_source(p,size,sha); snapshots.append(parse(p,date,prefix)); p.unlink()
    return snapshots,receipts


def run(root):
    encode,model_receipt=load_encoder(root/'model'); cache={}; output={}; trained=None
    for prefix in SOURCES:
        snapshots,receipts=acquire(prefix,root); splits=('development','calibration','test') if prefix=='MONDO' else ('calibration','test')
        results={}; prepared={}; predictions={}; stats={}
        for i,split in enumerate(splits):
            start=time.perf_counter(); old=snapshots[i]; ref,stats[split]=queries(old,snapshots[i+1],prefix+split)
            names=sorted({n['name'] for n in old.values()}-cache.keys()); cache.update(encode(names))
            prepared[split]=prepare(old,ref,cache,prefix+split); results[split]=report_pool(prepared[split])
            trained,predictions[split]=compare(prepared[split],old,trained)
            stats[split]['elapsed_seconds']=time.perf_counter()-start
        cal,test=(prepared[s]['LSG:32'] for s in ('calibration','test')); cs,ts=(predictions[s] for s in ('calibration','test'))
        output[prefix]=dict(sources=receipts,partitions=stats,factorial=results,test_factorial_effects=factorial_effects(results['test']),arms={a:dict(metrics=mt.ranking_metrics(test,v),review=[mt.review_frontier(test,v,f) for f in (.25,.5,.75,1)],fallback=fallback_receipt(cal,cs,test,ts,a)) for a,v in ts.items()})
    return dict(scope='retrospective_temporal_assertion_prediction_not_clinical_truth',model=model_receipt,model_hashes={k:mt.digest(v) for k,v in trained.items()},results=output)


def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--output',type=Path,required=True); args=parser.parse_args()
    try:
        with tempfile.TemporaryDirectory() as folder: result=run(Path(folder))
    except Exception as exc:
        args.output.write_text(json.dumps(dict(status='failed',error_type=type(exc).__name__))+'\n'); raise
    args.output.write_text(json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+'\n')


if __name__=='__main__': main()
