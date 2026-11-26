"""Open-corpus published-evidence retrieval and component interaction benchmark."""
import argparse
import math
import json
import re
import tempfile
import time
import urllib.request
from collections import Counter,defaultdict
from pathlib import Path
from .mondo_temporal import digest,_upper

PINS=[('cross-encoder/nli-distilroberta-base','b14d131f9d32668a5e6a982729b57ff6ed5dfcbd','9df3eb5d37118f952f4ba4fb46fde6889e3a9ccedeee0bad09b0110fc64c5c29'),('cross-encoder/ms-marco-MiniLM-L6-v2','233902d25c440f23af6f7d6e94d2946bac0bee0a','821d1aa69520101d6e0737f78a042ae25b19e5cb9160701909d10434f4aeb0ae')]


def words(s): return re.findall(r'[a-z0-9]+',s.lower())


def grams(s):
    s=' '.join(words(s)); return {s[i:i+3] for i in range(max(0,len(s)-2))}


def retrieve(corpus,claims,cap=8):
    if not 1<=cap<=len(corpus): raise ValueError('invalid cap')
    ids=sorted(corpus); lengths={}; postings=defaultdict(list); chars=defaultdict(list); sizes={}
    for d in ids:
        text=' '.join(corpus[d]); w=words(text); lengths[d]=len(w)
        for term,f in Counter(w).items(): postings[term].append((d,f))
        g=grams(text); sizes[d]=len(g)
        for term in g: chars[term].append(d)
    avg=sum(lengths.values())/len(ids); result={}
    for claim in claims:
        q=claim['claim']; lexical=defaultdict(float); overlap=Counter(); g=grams(q)
        for term in set(words(q)):
            docs=postings[term]; idf=math.log(1+(len(ids)-len(docs)+.5)/(len(docs)+.5))
            for d,f in docs: lexical[d]+=idf*2.2*f/(f+1.2*(.25+.75*lengths[d]/max(1,avg)))
        for term in g: overlap.update(chars[term])
        a=sorted(ids,key=lambda d:(-lexical[d],d)); b=sorted(ids,key=lambda d:(-overlap[d]/max(1,sizes[d]+len(g)-overlap[d]),d))
        ranks={d:1/(60+i) for i,d in enumerate(a,1)}
        for i,d in enumerate(b,1): ranks[d]+=1/(60+i)
        result[claim['id']]={'bm25':a[:cap],'lexical_fusion':sorted(ids,key=lambda d:(-ranks[d],d))[:cap]}
    return result


def proposal(doc,label,confidence,sentences,verification,verify_conf,enabled):
    if label not in ('SUPPORT','CONTRADICT') or not sentences: return None
    if enabled and verification!=label: return None
    return dict(doc=doc,label=label,confidence=min(confidence,verify_conf) if enabled else confidence,sentences=sentences)


def confirmed(ref,p):
    return p is not None and any(r['label']==p['label'] and set(r['sentences'])<=set(p['sentences']) for r in ref['evidence'].get(str(p['doc']),[]))


def evaluate(refs,pred,budget):
    if set(pred)!={r['id'] for r in refs} or not 0<=budget<=len(refs): raise ValueError('unmatched claim population or budget')
    selected=sorted((r for r in refs if pred[r['id']] is not None),key=lambda r:(-pred[r['id']]['confidence'],r['id']))[:budget]
    hits=sum(confirmed(r,pred[r['id']]) for r in selected); relevant=sum(bool(r['evidence']) for r in refs)
    return dict(claims=len(refs),reference_claims=relevant,proposals=len(selected),review=len(refs)-len(selected),confirmed=hits,unconfirmed=len(selected)-hits,unjudged_doc=sum(str(pred[r['id']]['doc']) not in r['evidence'] and pred[r['id']]['doc'] not in r.get('cited_doc_ids',[]) for r in selected),confirmed_recall=hits/relevant if relevant else None,unconfirmed_rate=(len(selected)-hits)/len(selected) if selected else None)


def fit_gate(fit,check,min_count=60,target=.20):
    for t in (.5,.6,.7,.8,.9,.95):
        a=[ok for s,ok in fit if s>=t]
        if len(a)>=min_count and _upper(a.count(False),len(a))<=target:
            b=[ok for s,ok in check if s>=t]; upper=_upper(b.count(False),len(b))
            return dict(threshold=t if len(b)>=min_count and upper<=target else None,chosen=t,fit=len(a),confirmation=len(b),confirmation_errors=b.count(False),upper=upper)
    return dict(threshold=None,fit_eligible=len(fit),confirmation_eligible=len(check))


def fallback(base,alt,threshold):
    if set(base)!=set(alt): raise ValueError('unmatched fallback')
    return {i:(alt[i] if p is None and threshold is not None and alt[i] is not None and alt[i]['confidence']>=threshold else p) for i,p in base.items()}


def sentence_ids(sentences,claim):
    q=set(words(claim))
    return sorted(sorted(range(len(sentences)),key=lambda i:(-len(q&set(words(sentences[i])))/max(1,len(q)),i))[:3])


def pin_models():
    from huggingface_hub import HfApi
    pins=[]
    for repo,rev,sha in PINS:
        info=HfApi().model_info(repo,revision=rev,files_metadata=True,token=False)
        ws=[f for f in info.siblings if f.rfilename=='model.safetensors']
        if info.sha!=rev or getattr(info.card_data,'license',None)!='apache-2.0' or len(ws)!=1 or getattr(ws[0].lfs,'sha256',None)!=sha or not 0<ws[0].size<=400000000: raise ValueError('model source mismatch')
        pins.append(dict(repo=repo,revision=rev,weights_sha256=sha,weights_bytes=ws[0].size,licence='Apache-2.0'))
    return pins


def stage(corpus,claims,ranker,nli,mlp,rules,cap=8):
    """Cross two retrieval, two ranking, three evaluation, two verification arms."""
    from .scifact_pipeline import pretrained
    start=time.perf_counter(); pools=retrieve(corpus,claims,cap); timing={'retrieval':time.perf_counter()-start}
    by_id={r['id']:r for r in claims}; candidates={}; selections={}
    for c in claims:
        for d in sorted(set().union(*map(set,pools[c['id']].values()))):
            i=f"{c['id']}:{d}"; candidates[i]=dict(id=i,claim=c['claim'],abstract=' '.join(corpus[d]))
    start=time.perf_counter(); scores,truncated=pretrained(list(candidates.values()),*ranker,ranking=True); timing['ranking']=time.perf_counter()-start
    for i,arms in pools.items():
        for retr,ds in arms.items():
            selections[(i,retr,'retrieval')]=ds[0]
            selections[(i,retr,'neural')]=min(ds,key=lambda d:(-scores[f'{i}:{d}'],d))
    ids=sorted({f'{i}:{d}' for (i,_,_),d in selections.items()}); rows=[candidates[i] for i in ids]; sentences={}
    for i in ids:
        c,d=map(int,i.split(':')); indices=sentence_ids(corpus[d],by_id[c]['claim']); sentences[i]=indices
    support=[dict(r,abstract=' '.join(corpus[int(r['id'].split(':')[1])][i] for i in sentences[r['id']])) for r in rows]
    start=time.perf_counter(); doc_pred,dt=pretrained(rows,*nli,ranking=False); sent_pred,st=pretrained(support,*nli,ranking=False); timing['evaluation_and_verification']=time.perf_counter()-start
    predictions={'rules':rules(rows),'mlp':mlp(rows),'nli':doc_pred}; output={}; retrieval={}
    for retr in ('bm25','lexical_fusion'):
        evidence=[c for c in claims if c['evidence']]
        retrieval[retr]=dict(queries=len(claims),reference_claims=len(evidence),pool_hits=sum(any(str(d) in c['evidence'] for d in pools[c['id']][retr]) for c in evidence),pool_sha256=digest([(c['id'],pools[c['id']][retr]) for c in claims]))
        for rk in ('retrieval','neural'):
            for ev,values in predictions.items():
                for verify in (False,True):
                    key=f'{retr}:{rk}:{ev}:{int(verify)}'; output[key]={}
                    for c in claims:
                        i=c['id']; d=selections[(i,retr,rk)]; row=f'{i}:{d}'; label,conf=values[row]; vl,vc=sent_pred[row]
                        output[key][i]=proposal(d,label,conf,sentences[row],vl,vc,verify)
    return output,retrieval,dict(timing,candidate_pairs=len(candidates),evaluated_pairs=len(rows),reranker_truncations=truncated,document_truncations=dt,sentence_truncations=st)


def run(root):
    from . import scifact_pipeline as s
    with urllib.request.urlopen(s.SOURCE,timeout=60) as response: raw=response.read(s.SOURCE_BYTES+1)
    train,dev,corpus=s.read_release(raw); frozen=s.freeze(train,dev,corpus); parts=frozen['partitions']; cal_groups={r['claim_id']:r['group'] for r in parts['calibration']}
    cal=[r for r in train if r['id'] in cal_groups]; test=sorted(dev,key=lambda r:r['id']); cal.sort(key=lambda r:r['id'])
    if len(corpus)>6000 or len(cal)>1500 or len(test)>500: raise ValueError('budget exceeded')
    mlp,w=s.fit_small(parts['development'],neural=True); pins=pin_models(); nli=s.load_model(pins[0],str(root/'nli')); ranker=s.load_model(pins[1],str(root/'ranker'))
    c,cr,ct=stage(corpus,cal,ranker,nli,mlp,s.deterministic); t,tr,tt=stage(corpus,test,ranker,nli,mlp,s.deterministic)
    report={k:dict(calibration=evaluate(cal,c[k],len(cal)),test=[evaluate(test,v,int(len(test)*f)) for f in (.25,.5,.75,1)],prediction_sha256=digest(v)) for k,v in t.items()}
    base='bm25:retrieval:rules:1'; alt='lexical_fusion:neural:nli:1'; examples=[(r,c[alt][r['id']]) for r in cal if c[base][r['id']] is None and c[alt][r['id']] is not None]
    fit=[(p['confidence'],confirmed(r,p)) for r,p in examples if int(digest(cal_groups[r['id']])[0],16)<8]; check=[(p['confidence'],confirmed(r,p)) for r,p in examples if int(digest(cal_groups[r['id']])[0],16)>=8]
    gate=fit_gate(fit,check); hybrid=fallback(t[base],t[alt],gate['threshold'])
    return dict(scope='published_open_retrieval_evidence_confirmation_not_clinical_truth',source_sha256=s.SOURCE_SHA256,corpus_documents=len(corpus),calibration_claims=len(cal),test_claims=len(test),calibration_sha256=digest([r['id'] for r in cal]),test_sha256=digest([r['id'] for r in test]),models=pins,small_weights_sha256=w,retrieval=dict(calibration=cr,test=tr),timing=dict(calibration=ct,test=tt),arms=report,fallback=dict(gate,eligible=len(examples),test=evaluate(test,hybrid,len(test)),activated=sum(t[base][i] is None and hybrid[i] is not None for i in hybrid)))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);a=parser.parse_args()
    try:
        with tempfile.TemporaryDirectory() as d: result=run(Path(d))
    except Exception as exc:
        a.output.write_text(json.dumps(dict(status='failed',error_type=type(exc).__name__))+'\n');raise
    a.output.write_text(json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+'\n')


if __name__=='__main__': main()
