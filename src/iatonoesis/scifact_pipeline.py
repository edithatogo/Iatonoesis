"""Bounded external SciFact evidence-pair and cited-pool pipeline experiment."""
import argparse
import hashlib
import io
import json
import math
import re
import tarfile
import tempfile
import time
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath

SOURCE = 'https://scifact.s3-us-west-2.amazonaws.com/release/latest/data.tar.gz'
SOURCE_BYTES = 3115079
SOURCE_SHA256 = '11c621288d41ac144d29b13b0f8503b3820b7d6e8b1f6ff24dff335c196d76be'
LABELS = ('CONTRADICT', 'SUPPORT', 'NO_EVIDENCE')
MODELS = ('cross-encoder/nli-distilroberta-base', 'cross-encoder/ms-marco-MiniLM-L6-v2')
THRESHOLDS = (.5, .6, .7, .8, .9, .95)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def read_release(raw):
    """Read three exact JSONL members; never extract or execute archive contents."""
    if len(raw) != SOURCE_BYTES or hashlib.sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError('source checksum mismatch')
    expected = {'data/corpus.jsonl', 'data/claims_train.jsonl', 'data/claims_dev.jsonl'}
    files = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as archive:
        for member in archive:
            path = PurePosixPath(member.name)
            if path.is_absolute() or '..' in path.parts:
                raise ValueError('unsafe archive path')
            name = str(path)
            if name not in expected:
                continue
            if not member.isfile() or member.size > 20000000 or name in files:
                raise ValueError('invalid source member')
            data = archive.extractfile(member)
            if data is None:
                raise ValueError('unreadable source member')
            files[name] = [json.loads(line) for line in data if line.strip()]
    if set(files) != expected:
        raise ValueError('source members missing')
    docs = files['data/corpus.jsonl']
    corpus = {int(d['doc_id']): d['abstract'] for d in docs}
    if len(corpus) != len(docs):
        raise ValueError('duplicate source document')
    return files['data/claims_train.jsonl'], files['data/claims_dev.jsonl'], corpus


def freeze(train, dev, corpus):
    """Keep all source dev claims as test; remove train components touching any dev claim."""
    parent, cases, source_split = {}, {}, {}

    def root(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for split, records in [('train', train), ('dev', dev)]:
        for c in records:
            i = c['id']
            if i in cases:
                raise ValueError('duplicate claim')
            source_split[i] = split
            docs = sorted(set(map(int, c['cited_doc_ids'])) | set(map(int, c['evidence'])))
            parent[root(('c', i))] = root(('c', i))
            cases[i] = []
            for d in docs:
                if d not in corpus or not corpus[d]:
                    raise ValueError('missing cited abstract')
                refs = c['evidence'].get(str(d), [])
                labels = {r['label'] for r in refs}
                if len(labels) > 1 or (labels and not labels <= set(LABELS[:2])):
                    raise ValueError('conflicting or unknown reference labels')
                if any(type(j) is not int or not 0 <= j < len(corpus[d]) for r in refs for j in r['sentences']):
                    raise ValueError('invalid reference sentence index')
                parent[root(('c', i))] = root(('d', d))
                cases[i].append(dict(id=f'{i}:{d}', claim_id=i, doc_id=d, claim=c['claim'],
                                     abstract=' '.join(corpus[d]), label=next(iter(labels), 'NO_EVIDENCE')))
    groups = defaultdict(list)
    for i in cases:
        groups[root(('c', i))].append(i)
    parts = {k: [] for k in ('development', 'calibration', 'test')}
    excluded, empty, train_groups = [], [], []
    for ids in groups.values():
        group = digest(sorted(ids))
        if any(source_split[i] == 'dev' for i in ids):
            for i in ids:
                if source_split[i] == 'train':
                    excluded.append(i)
                else:
                    parts['test'].extend(dict(row, group=group) for row in cases[i])
        else:
            train_groups.append((group, sorted(ids)))
    remaining = sum(len(cases[i]) for _, ids in train_groups for i in ids)
    for group, ids in sorted(train_groups):
        partition = 'calibration' if len(parts['calibration']) < remaining * .25 else 'development'
        for i in ids:
            parts[partition].extend(dict(row, group=group) for row in cases[i])
    for i in cases:
        if not cases[i]:
            empty.append(i)
    for p in parts:
        parts[p].sort(key=lambda r: r['id'])
    if not all(parts.values()):
        raise ValueError('empty grouped partition')
    for a, b in [('development','calibration'), ('development','test'), ('calibration','test')]:
        for key in ('doc_id','claim_id','group'):
            if {r[key] for r in parts[a]} & {r[key] for r in parts[b]}:
                raise ValueError('group leakage')
    return dict(partitions=parts, excluded_train_claims=len(excluded), excluded_train_ids_sha256=digest(sorted(excluded)),
                no_candidate_claims=len(empty), no_candidate_ids_sha256=digest(sorted(empty)))


def words(text):
    return re.findall(r'[a-z0-9]+', text.lower())


def features(premise, claim):
    p, c = words(premise), words(claim)
    a, b = set(p), set(c)
    neg = {'no','not','never','without','neither','lack','failed'}
    num_p, num_c = {w for w in a if w.isdigit()}, {w for w in b if w.isdigit()}
    return [len(a&b)/max(1,len(b)), len(a&b)/max(1,len(a|b)), float(bool(a&neg)),
            float(bool(b&neg)), float(bool((a&neg) != (b&neg))), float(bool(num_c-num_p)),
            min(len(p),512)/512, min(len(c),128)/128]


def deterministic(rows):
    # Lexical containment is only a crude candidate for support, not proof.
    out = {}
    for r in rows:
        f = features(r['abstract'], r['claim'])
        support = f[0] >= .95 and not f[4] and not f[5]
        out[r['id']] = ('SUPPORT' if support else 'NO_EVIDENCE', f[0] if support else 1-f[0])
    return out


def paired_budget(rows, pred, retain):
    if not 0 <= retain <= len(rows) or set(pred) != {r['id'] for r in rows}:
        raise ValueError('unmatched coverage budget')
    selected = sorted(rows, key=lambda r: (-pred[r['id']][1], r['id']))[:retain]
    if any(label not in LABELS or not math.isfinite(conf) or not 0<=conf<=1 for label,conf in pred.values()):
        raise ValueError('invalid prediction')
    correct = sum(pred[r['id']][0] == r['label'] for r in selected)
    wrong_support = sum(pred[r['id']][0] == 'SUPPORT' and r['label'] != 'SUPPORT' for r in selected)
    return dict(total=len(rows), retained=retain, review=len(rows)-retain, correct=correct,
                error_rate=(retain-correct)/retain if retain else None,
                false_support=wrong_support, false_support_denominator=sum(r['label']!='SUPPORT' for r in selected),
                correct_fraction=correct/len(rows) if rows else None,
                confusion={label:{p:sum(r['label']==label and pred[r['id']][0]==p for r in selected) for p in LABELS} for label in LABELS})


def fallback_gate(examples):
    """Fixed conservative exploratory Wilson upper bound; calibration labels only."""
    for threshold in THRESHOLDS:
        kept = [correct for conf, correct in examples if conf >= threshold]
        n = len(kept)
        if n < 30:
            continue
        err = 1-sum(kept)/n
        z = 2.4  # conservative descriptive screening across six thresholds
        upper = (err+z*z/(2*n)+z*math.sqrt(err*(1-err)/n+z*z/(4*n*n)))/(1+z*z/n)
        if upper <= .20:
            return threshold
    return None


def pipeline(rows, ranks, pred):
    if set(ranks) != {r['id'] for r in rows} or set(pred) != set(ranks):
        raise ValueError('candidate pool mismatch')
    by_claim = defaultdict(list)
    for row in rows:
        by_claim[row['claim_id']].append(row)
    correct = retrieved = positives = false_support = 0
    rr, ndcg = [], []
    for candidates in by_claim.values():
        ordered = sorted(candidates, key=lambda r: (-ranks[r['id']],r['id']))
        relevant = [i for i,r in enumerate(ordered,1) if r['label'] != 'NO_EVIDENCE']
        top = ordered[0]
        label = pred[top['id']][0]
        if relevant:
            positives += 1
            retrieved += int(relevant[0] == 1)
            rr.append(1/relevant[0])
            ndcg.append(sum(1/math.log2(i+1) for i in relevant if i<=3)/sum(1/math.log2(i+1) for i in range(1,min(3,len(relevant))+1)))
        correct += int(label == top['label'] and (not relevant or top['label'] != 'NO_EVIDENCE'))
        false_support += int(label=='SUPPORT' and top['label']!='SUPPORT')
    return dict(claims=len(by_claim), correct=correct, evidence_claims=positives, retrieved_evidence=retrieved,
                recall_at_one=retrieved/positives if positives else None, mrr=sum(rr)/len(rr) if rr else None,
                ndcg_at_three=sum(ndcg)/len(ndcg) if ndcg else None, false_support=false_support)


def lexical_ranks(rows, corpus):
    """BM25 over the same fixed author-cited pools; corpus IDF is label-free."""
    tokenized = [words(' '.join(a)) for a in corpus.values()]
    df = Counter(w for doc in tokenized for w in set(doc))
    average = sum(map(len,tokenized))/len(tokenized)
    ranks = {}
    for row in rows:
        doc = words(row['abstract']); tf = Counter(doc)
        score = 0.0
        for w in set(words(row['claim'])):
            idf = math.log(1+(len(tokenized)-df[w]+.5)/(df[w]+.5))
            score += idf*tf[w]*2.2/(tf[w]+1.2*(.25+.75*len(doc)/max(1,average)))
        ranks[row['id']] = score
    return ranks


def fit_small(train, *, neural):
    import torch
    from torch import nn
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    torch.manual_seed(17)
    x = torch.tensor([features(r['abstract'],r['claim']) for r in train])
    y = torch.tensor([LABELS.index(r['label']) for r in train])
    if len(set(y.tolist())) != 3:
        raise ValueError('development missing label class')
    model = nn.Sequential(nn.Linear(8,24),nn.Tanh(),nn.Linear(24,3)) if neural else nn.Linear(8,3)
    opt = torch.optim.Adam(model.parameters(),lr=.02)
    for _ in range(100):
        opt.zero_grad(); loss=nn.functional.cross_entropy(model(x),y); loss.backward(); opt.step()
    model.eval()

    def predict(rows):
        with torch.inference_mode():
            prob=model(torch.tensor([features(r['abstract'],r['claim']) for r in rows])).softmax(1)
        return {r['id']:(LABELS[int(p.argmax())],float(p.max())) for r,p in zip(rows,prob,strict=True)}
    return predict, digest({k:v.tolist() for k,v in model.state_dict().items()})


def pin_model(repo):
    """Resolve immutable revision and published safetensors digest before any inference."""
    from huggingface_hub import HfApi
    if repo not in MODELS:
        raise ValueError('unapproved model source')
    info=HfApi().model_info(repo,files_metadata=True,token=False)
    if getattr(info.card_data,'license',None) != 'apache-2.0':
        raise ValueError('model licence differs from reviewed card')
    weights=[x for x in info.siblings if x.rfilename=='model.safetensors']
    if not re.fullmatch(r'[0-9a-f]{40}',info.sha or '') or len(weights)!=1:
        raise ValueError('immutable safetensors source missing')
    w=weights[0]
    sha=getattr(w.lfs,'sha256',None)
    if not sha or not re.fullmatch(r'[0-9a-f]{64}',sha) or not 0<w.size<=400000000:
        raise ValueError('model weights metadata invalid')
    return dict(repo=repo,revision=info.sha,weights_sha256=sha,weights_bytes=w.size,licence='Apache-2.0 (model card)')


def load_model(pin, directory):
    from huggingface_hub import snapshot_download
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    path=Path(snapshot_download(pin['repo'],revision=pin['revision'],local_dir=directory,
                                token=False,allow_patterns=['model.safetensors','config.json','tokenizer.json','tokenizer_config.json','special_tokens_map.json','vocab.json','vocab.txt','merges.txt']))
    raw=path/'model.safetensors'
    with raw.open('rb') as stream:
        h=hashlib.file_digest(stream,'sha256').hexdigest()
    if raw.stat().st_size!=pin['weights_bytes'] or h!=pin['weights_sha256']:
        raise ValueError('model weights integrity mismatch')
    pin['files_sha256']={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in path.iterdir() if f.is_file() and f.name!='model.safetensors'}
    tokenizer=AutoTokenizer.from_pretrained(path,local_files_only=True,trust_remote_code=False)
    model=AutoModelForSequenceClassification.from_pretrained(path,local_files_only=True,trust_remote_code=False,use_safetensors=True).eval()
    return tokenizer,model


def pretrained(rows, tokenizer, model, *, ranking):
    import torch
    out={}; truncated=0
    for i in range(0,len(rows),8):
        batch=rows[i:i+8]
        first=[r['claim'] if ranking else r['abstract'] for r in batch]
        second=[r['abstract'] if ranking else r['claim'] for r in batch]
        lengths=tokenizer(first,second,add_special_tokens=True,truncation=False,return_length=True)['length']
        truncated+=sum(n>512 for n in lengths)
        tokens=tokenizer(first,second,padding=True,truncation=True,max_length=512,return_tensors='pt')
        with torch.inference_mode():
            scores=model(**tokens).logits
        if ranking:
            if scores.shape[1]!=1:
                raise ValueError('unexpected reranker output')
            out.update({r['id']:float(s[0]) for r,s in zip(batch,scores,strict=True)})
        else:
            if [model.config.id2label[k].lower() for k in range(3)]!=['contradiction','entailment','neutral']:
                raise ValueError('unexpected NLI label order')
            out.update({r['id']:(LABELS[int(p.argmax())],float(p.max())) for r,p in zip(batch,scores.softmax(1),strict=True)})
    return out,truncated


def compare(frozen, corpus, pins, directory):
    train,cal,test=(frozen['partitions'][p] for p in ('development','calibration','test'))
    import torch
    results={}; preds={}; cals={}; times={}; weights={}
    start=time.perf_counter(); cals['rules']=deterministic(cal); preds['rules']=deterministic(test); times['rules']={'cal_test_seconds':time.perf_counter()-start}
    # All calibration choices are fit without test labels; fixed 50/75/100% diagnostic coverage.
    for name,neural in [('linear',False),('small_mlp',True)]:
        start=time.perf_counter(); predict,w=fit_small(train,neural=neural); weights[name]=w
        times[name]={'train_seconds':time.perf_counter()-start}; start=time.perf_counter()
        cals[name]=predict(cal); preds[name]=predict(test); times[name]['cal_test_seconds']=time.perf_counter()-start
    torch.set_num_threads(2)
    start=time.perf_counter(); tok,nli=load_model(pins[0],str(directory/'nli')); times['nli']={'load_seconds':time.perf_counter()-start}; start=time.perf_counter()
    cals['nli'],ct=pretrained(cal,tok,nli,ranking=False); preds['nli'],tt=pretrained(test,tok,nli,ranking=False)
    times['nli'].update(cal_test_seconds=time.perf_counter()-start,truncated_cal=ct,truncated_test=tt)
    del nli,tok
    start=time.perf_counter(); bm=lexical_ranks(test,corpus); times['bm25']={'test_seconds':time.perf_counter()-start}
    start=time.perf_counter(); tok,ranker=load_model(pins[1],str(directory/'ranker')); times['reranker']={'load_seconds':time.perf_counter()-start}; start=time.perf_counter()
    neural_rank,rt=pretrained(test,tok,ranker,ranking=True); times['reranker'].update(test_seconds=time.perf_counter()-start,truncated_test=rt)
    for name in preds:
        results[name]={'matched_coverage':{str(c):paired_budget(test,preds[name],int(len(test)*c)) for c in (.5,.75,1)},
                       'calibrated_risk_threshold':fallback_gate([(p[1],p[0]==r['label']) for r in cal for p in [cals[name][r['id']]]])}
        threshold=results[name]['calibrated_risk_threshold']
        retained={r['id'] for r in test if threshold is not None and preds[name][r['id']][1]>=threshold}
        results[name]['matched_calibration_risk']=paired_budget(test,preds[name],len(retained))
    # Classical baseline abstention cut fixed on calibration confidence, not test accuracy.
    cut=sorted((v[1] for v in cals['linear'].values()),reverse=True)[max(0,int(.7*len(cal))-1)]
    eligible=[r for r in cal if cals['linear'][r['id']][1]<cut]
    fallback=fallback_gate([(cals['nli'][r['id']][1],cals['nli'][r['id']][0]==r['label']) for r in eligible])
    base_retained=[r for r in test if preds['linear'][r['id']][1]>=cut]
    fallback_rows=[r for r in test if preds['linear'][r['id']][1]<cut and fallback is not None and preds['nli'][r['id']][1]>=fallback]
    hybrid=[(r,preds['linear'][r['id']][0]) for r in base_retained]+[(r,preds['nli'][r['id']][0]) for r in fallback_rows]
    hybrid_receipt=dict(calibration_eligible=len(eligible),base_cut=cut,fallback_threshold=fallback,base_retained=len(base_retained),fallback_activated=len(fallback_rows),
                        retained=len(hybrid),review=len(test)-len(hybrid),correct=sum(p==r['label'] for r,p in hybrid),false_support=sum(p=='SUPPORT' and r['label']!='SUPPORT' for r,p in hybrid))
    crossed={f'{rank}_{name}':pipeline(test,values,preds[name]) for rank,values in [('bm25',bm),('pretrained_reranker',neural_rank)] for name in preds}
    raw=[dict(id=r['id'],label=r['label'],predictions={n:p[r['id']] for n,p in preds.items()},ranks={'bm25':bm[r['id']],'pretrained':neural_rank[r['id']]}) for r in test]
    subgroups={}
    for name,predicate in [('negation',lambda r: bool(set(words(r['claim']))&{'no','not','never','without','neither','lack','failed'})),('numeric',lambda r:any(w.isdigit() for w in words(r['claim']))),('long_abstract',lambda r:len(words(r['abstract']))>300)]:
        subset=[r for r in test if predicate(r)]
        subgroups[name]={k:paired_budget(subset,{r['id']:p[r['id']] for r in subset},len(subset)) for k,p in preds.items()}
    return dict(metrics=results,hybrid=hybrid_receipt,pipeline=crossed,subgroups=subgroups,timing=times,small_weights_sha256=weights,predictions_sha256=digest(raw),predictions=raw,models=pins)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args(); args.output_dir.mkdir(parents=True,exist_ok=True)
    with urllib.request.urlopen(SOURCE,timeout=60) as response:
        raw=response.read(SOURCE_BYTES+1)
    train,dev,corpus=read_release(raw); frozen=freeze(train,dev,corpus)
    if len(corpus)>6000 or any(len(rows)>2500 for rows in frozen['partitions'].values()):
        raise ValueError('source case budget exceeded')
    pins=[pin_model(repo) for repo in MODELS]
    metadata=dict(status='external_published_development_benchmark_not_blinded',source=SOURCE,source_sha256=SOURCE_SHA256,
                  source_rights='claims/evidence CC BY 4.0; corpus ODC-By 1.0; original author LICENSE.md',
                  official_test_labels_unavailable=True,source_train_claims=len(train),source_dev_claims=len(dev),
                  corpus_documents=len(corpus),excluded_train_claims=frozen['excluded_train_claims'],no_candidate_claims=frozen['no_candidate_claims'],
                  partitions={p:dict(rows=len(rows),claims=len({r['claim_id'] for r in rows}),groups=len({r['group'] for r in rows}),labels=dict(Counter(r['label'] for r in rows)),sha256=digest(rows)) for p,rows in frozen['partitions'].items()},models=pins)
    freeze_path=args.output_dir/'freeze.json'
    freeze_path.write_text(json.dumps(metadata,indent=2,sort_keys=True)+'\n')
    frozen_sha=hashlib.sha256(freeze_path.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory() as temp:
        result=compare(frozen,corpus,pins,Path(temp))
    result['freeze_sha256']=frozen_sha
    result['claim_boundary']='exploratory external evidence-pair and cited-pool benchmark only; not clinical truth or open retrieval'
    (args.output_dir/'result.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')


if __name__=='__main__':
    main()
