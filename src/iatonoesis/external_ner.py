"""Bounded external disease span benchmark; research only, no source text export."""
import argparse
import hashlib
import io
import json
import re
import time
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

from .run_contracts import canonical_sha256 as digest
from .runner import summarize, paired_f1_interval
from .scifact_pipeline import fallback_gate

NCBI_REV = '413ebc68601670d9a36b041535c77112c5e629da'
NCBI_FILES = {
    'development': ('original-data/train/NCBItrainset_corpus.txt', 1045965, 'f22d210fd4d59a1d11944d6317db2a60f725953e'),
    'calibration': ('original-data/devel/NCBIdevelopset_corpus.txt', 178373, '11397ce039ef99dbbbbadde81a2ce7c849c47618'),
    'test': ('original-data/test/NCBItestset_corpus.txt', 189219, 'c098c9115a9b858dbc3795c730d86bf85556ecf2'),
}
NCBI_TYPES = {'DiseaseClass', 'SpecificDisease', 'CompositeMention', 'Modifier'}
MODEL = 'd4data/biomedical-ner-all'
CDR = 'bigbio/bc5cdr'
TOKEN = re.compile(r'\w+|[^\w\s]', re.UNICODE)


def parse_pubtator(raw, types, quarantine=None):
    rows = []
    for block in re.split(r'\n[ \t]*\n', raw.replace('\r\n', '\n').strip()):
        lines = block.splitlines()
        title = [x.split('|', 2) for x in lines if re.match(r'^\d+\|t\|', x)]
        abstract = [x.split('|', 2) for x in lines if re.match(r'^\d+\|a\|', x)]
        if len(title) != 1 or len(abstract) != 1 or title[0][0] != abstract[0][0]:
            raise ValueError('invalid document header')
        key, text = title[0][0], title[0][2] + ' ' + abstract[0][2]
        spans, bad = set(), False
        for line in lines:
            if re.match(r'^\d+\|[ta]\|', line):
                continue
            v = line.split('\t')
            if len(v) == 4 and v[1] == 'CID':
                continue
            if len(v) != 6 or v[0] != key:
                raise ValueError('invalid annotation row')
            if v[4] not in types:
                continue
            a, b = int(v[1]), int(v[2])
            if not 0 <= a < b <= len(text) or text[a:b] != v[3]:
                bad = True
            spans.add((a, b))
        if bad:
            if quarantine is None:
                raise ValueError('annotation offset mismatch')
            quarantine.append(digest(key))
        else:
            rows.append(dict(id=key, text=text, spans=[list(s) for s in sorted(spans)]))
    return rows


def split_sources(parts):
    """Priority: NCBI test, calibration, development; external excludes any prior overlap."""
    out, counts, seen_id, seen_text = {}, {}, {}, set()
    for p in ('test', 'calibration', 'development', 'external'):
        out[p], counts[p] = [], 0
        for row in sorted(parts[p], key=lambda r: (r['id'], digest(r))):
            h = digest(' '.join(row['text'].casefold().split()))
            if row['id'] in seen_id and seen_id[row['id']] != digest(row):
                # Cross-corpus annotation differences are explicit overlap exclusions.
                if p != 'external':
                    raise ValueError('conflicting duplicate NCBI document')
            if row['id'] in seen_id or h in seen_text:
                counts[p] += 1
                continue
            seen_id[row['id']] = digest(row)
            seen_text.add(h)
            out[p].append(row)
    return out, counts


def dictionary(rows):
    return {row['text'][a:b].casefold() for row in rows for a, b in row['spans']}


def lexicon(text, vocab):
    if not vocab:
        return [], 0.
    pattern = r'(?<!\w)(?:' + '|'.join(re.escape(x) for x in sorted(vocab, key=lambda x: (-len(x), x))) + r')(?!\w)'
    spans = [[m.start(), m.end()] for m in re.finditer(pattern, text, re.I)]
    return spans, min(.99, .5 + .05 * len(spans)) if spans else 0.


def bio_spans(offsets, labels):
    out, current = [], None
    for (a, b), label in zip(offsets, labels, strict=True):
        if label == 0 or label == 1:
            if current:
                out.append(current)
            current = None
        if label and current is None:
            current = [a, b]
        elif label:
            current[1] = b
    if current:
        out.append(current)
    return out


def span_metrics(rows, pred):
    if set(pred) != {r['id'] for r in rows}:
        raise ValueError('unmatched predictions')
    scored = []
    for r in rows:
        spans, conf = pred[r['id']]
        if not 0 <= conf <= 1 or (spans is not None and any(not 0 <= a < b <= len(r['text']) for a, b in spans)):
            raise ValueError('invalid span prediction')
        scored.append(dict(id=digest(r['id']), groups={'document': digest(r['id'])}, gold=r['spans'], prediction=spans))
    return summarize(scored)


def matched_budget(rows, pred, retain):
    if not 0 <= retain <= len(rows):
        raise ValueError('invalid review budget')
    available = [r for r in rows if pred[r['id']][0] is not None]
    if len(available) < retain:
        return dict(status='unavailable_at_budget', requested_retained=retain, available=len(available))
    selected = {r['id'] for r in sorted(available, key=lambda r: (-pred[r['id']][1], digest(r['id'])))[:retain]}
    reduced = {i: v if i in selected else (None, 0.) for i, v in pred.items()}
    return dict(span_metrics(rows, reduced), retained=retain, review=len(rows)-retain)


def fallback(rule, model, threshold):
    return {i: model[i] if threshold is not None and v[0] == [] and model[i][0] and model[i][1] >= threshold else v for i, v in rule.items()}


def tiny_model(train, seed=17):
    import torch
    from torch import nn
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    torch.manual_seed(seed)

    def encode(text):
        tokens = list(TOKEN.finditer(text))
        words = [m.group().lower() for m in tokens]
        x = torch.zeros((len(tokens), 256))
        for i, w in enumerate(words):
            feats = ('word:'+w, 'prefix:'+w[:3], 'suffix:'+w[-3:], 'prev:'+words[i-1] if i else 'START', 'next:'+words[i+1] if i+1<len(words) else 'END')
            for f in feats:
                x[i, int(hashlib.sha256(f.encode()).hexdigest()[:8], 16) % 256] += 1
        return tokens, x

    xs, ys, missed = [], [], 0
    for row in train:
        tokens, x = encode(row['text'])
        by_start = {m.start(): i for i, m in enumerate(tokens)}
        by_end = {m.end(): i for i, m in enumerate(tokens)}
        y = torch.zeros(len(tokens), dtype=torch.long)
        for a, b in row['spans']:
            if a not in by_start or b not in by_end or by_start[a] > by_end[b] or y[by_start[a]:by_end[b]+1].any():
                missed += 1
                continue
            y[by_start[a]] = 1
            y[by_start[a]+1:by_end[b]+1] = 2
        xs.append(x)
        ys.append(y)
    x, y = torch.cat(xs), torch.cat(ys)
    model = nn.Sequential(nn.Linear(256, 32), nn.ReLU(), nn.Linear(32, 3))
    opt = torch.optim.Adam(model.parameters(), lr=.01)
    weights = torch.bincount(y, minlength=3).clamp(min=1).float().reciprocal()
    weights /= weights.mean()
    for _ in range(25):
        for ids in torch.randperm(len(y)).split(1024):
            opt.zero_grad()
            loss = nn.functional.cross_entropy(model(x[ids]), y[ids], weight=weights)
            loss.backward()
            opt.step()
    model.eval()

    @torch.inference_mode()
    def predict(text):
        tokens, x = encode(text)
        probs = model(x).softmax(1)
        conf, labs = probs.max(1)
        spans = bio_spans([(m.start(),m.end()) for m in tokens], labs.tolist())
        return spans, float(conf.min()) if len(conf) else 0.

    return predict, dict(unrepresentable_training_spans=missed, weights_sha256=digest({k:v.tolist() for k,v in model.state_dict().items()}), parameters=sum(p.numel() for p in model.parameters()), seed=seed)


def read_url(url, cap):
    if not url.startswith(('https://raw.githubusercontent.com/openbiocorpora/ncbi-disease/', 'https://huggingface.co/datasets/bigbio/bc5cdr/')):
        raise ValueError('unapproved source URL')
    with urllib.request.urlopen(url, timeout=60) as stream:
        if not stream.geturl().startswith('https://'):
            raise ValueError('insecure redirect')
        raw = stream.read(cap+1)
    if len(raw) > cap:
        raise ValueError('source cap exceeded')
    return raw


def git_blob(raw):
    return hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest()


def acquire():
    parts, source, quarantine = {}, {}, []
    root = f'https://raw.githubusercontent.com/openbiocorpora/ncbi-disease/{NCBI_REV}/'
    notice = read_url(root+'LICENSE', 1260)
    if git_blob(notice) != '498b69f93dd27d7cf1547004fe7ea0e5601dbd6f' or b'PUBLIC DOMAIN NOTICE' not in notice:
        raise ValueError('NCBI rights notice mismatch')
    for name, (path, size, blob) in NCBI_FILES.items():
        raw = read_url(root+path, size)
        if len(raw) != size or git_blob(raw) != blob:
            raise ValueError('NCBI source mismatch')
        parts[name] = parse_pubtator(raw.decode('utf-8'), NCBI_TYPES, quarantine if name=='development' else None)
        source[name] = dict(bytes=size, git_blob=blob, sha256=hashlib.sha256(raw).hexdigest())
    try:
        parts['external'], source['external'] = acquire_cdr()
    except Exception as exc:
        # Source unavailable is not a successful external test or a zero score.
        parts['external'] = []
        source['external'] = dict(status='unavailable', reason=type(exc).__name__)
    parts, exclusions = split_sources(parts)
    # Hash-defined bounded sample, selected independently of labels.
    parts['development'] = sorted(parts['development'],key=lambda r:digest(r['id']))[:256]
    parts['external'] = sorted(parts['external'],key=lambda r:digest(r['id']))[:100]
    if not all(parts[p] for p in ('development','calibration','test')):
        raise ValueError('empty NCBI partition')
    return parts, dict(source=source, quarantined_development=len(quarantine), quarantine_sha256=digest(sorted(quarantine)), overlap_exclusions=exclusions)


def acquire_cdr():
    # Cross-source holdout uses the original, pinned archive, never a loader script.
    from huggingface_hub import HfApi, hf_hub_download
    api = HfApi()
    parts = {}
    info = api.dataset_info(CDR, files_metadata=True, token=False)
    files = [x for x in info.siblings if x.rfilename=='CDR_Data.zip']
    if len(files)!=1 or not re.fullmatch(r'[0-9a-f]{40}',info.sha or '') or files[0].size!=20403150:
        raise ValueError('CDR source pin absent')
    sha = getattr(files[0].lfs,'sha256',None)
    if not re.fullmatch(r'[0-9a-f]{64}',sha or ''):
        raise ValueError('CDR source digest absent')
    path = Path(hf_hub_download(CDR,'CDR_Data.zip',repo_type='dataset',revision=info.sha,token=False))
    raw = path.read_bytes()
    if len(raw)!=files[0].size or hashlib.sha256(raw).hexdigest()!=sha:
        raise ValueError('CDR source integrity mismatch')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        members = z.infolist()
        if len(members)>1000 or any(PurePosixPath(m.filename).is_absolute() or '..' in PurePosixPath(m.filename).parts for m in members):
            raise ValueError('unsafe CDR archive')
        notices = [m for m in members if re.search(r'(license|readme|notice)',m.filename,re.I) and m.file_size<=100000 and not m.is_dir()]
        if not any(b'government work' in z.read(m).lower() or b'public domain' in z.read(m).lower() for m in notices):
            raise ValueError('CDR public-domain notice not verified')
        matches = [m for m in members if m.filename.endswith('CDR_TestSet.PubTator.txt') and m.file_size<10000000]
        if len(matches)!=1:
            raise ValueError('CDR test member missing')
        parts['external'] = parse_pubtator(z.read(matches[0]).decode('utf-8'), {'Disease'})
    if len(parts['external']) != 500:
        raise ValueError('unexpected CDR test count')
    return parts['external'], dict(revision=info.sha, bytes=len(raw), sha256=sha, status='verified')


def pretrained_model():
    from huggingface_hub import HfApi, snapshot_download
    from transformers import AutoTokenizer, AutoModelForTokenClassification, pipeline
    info=HfApi().model_info(MODEL,files_metadata=True,token=False)
    weights=[x for x in info.siblings if x.rfilename=='model.safetensors']
    if getattr(info.card_data,'license',None)!='apache-2.0' or not re.fullmatch(r'[0-9a-f]{40}',info.sha or '') or len(weights)!=1 or weights[0].size!=265722260:
        raise ValueError('model pin or rights mismatch')
    sha=getattr(weights[0].lfs,'sha256',None)
    if not re.fullmatch(r'[0-9a-f]{64}',sha or ''):
        raise ValueError('model digest unavailable')
    path=Path(snapshot_download(MODEL,revision=info.sha,token=False,allow_patterns=['model.safetensors','config.json','tokenizer.json','tokenizer_config.json','special_tokens_map.json','vocab.txt']))
    with (path/'model.safetensors').open('rb') as f:
        if hashlib.file_digest(f,'sha256').hexdigest()!=sha:
            raise ValueError('model weight integrity mismatch')
    tok=AutoTokenizer.from_pretrained(path,local_files_only=True,trust_remote_code=False)
    model=AutoModelForTokenClassification.from_pretrained(path,local_files_only=True,trust_remote_code=False,use_safetensors=True).eval()
    if not {'B-Disease_disorder','I-Disease_disorder'} <= set(model.config.id2label.values()):
        raise ValueError('model label mapping mismatch')
    tagger=pipeline('token-classification',model=model,tokenizer=tok,aggregation_strategy='simple',device=-1)

    def predict(text):
        if len(tok(text,add_special_tokens=True,truncation=False)['input_ids'])>512:
            return None,0.
        hits=[h for h in tagger(text) if h['entity_group']=='Disease_disorder']
        spans=sorted({(int(h['start']),int(h['end'])) for h in hits})
        return [list(s) for s in spans], min((float(h['score']) for h in hits),default=0.)
    return predict,dict(id=MODEL, revision=info.sha, licence='Apache-2.0 (model card)', weights_sha256=sha, weights_bytes=weights[0].size,
                        config_sha256=digest({f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in path.iterdir() if f.is_file() and f.name!='model.safetensors'}))


def run(output):
    output.mkdir(parents=True,exist_ok=True)
    parts, sources=acquire()
    freeze=dict(sources,partitions={k:dict(n=len(v),ids_sha256=digest([r['id'] for r in v]),inputs_sha256=digest([r['text'] for r in v]),references_sha256=digest([r['spans'] for r in v])) for k,v in parts.items()})
    t=time.perf_counter(); pretrained,model=pretrained_model(); load=time.perf_counter()-t
    freeze['pretrained_model'] = model
    (output/'freeze.json').write_text(json.dumps(freeze,indent=2,sort_keys=True)+'\n')
    vocab=dictionary(parts['development'])
    t=time.perf_counter(); small, small_meta=tiny_model(parts['development']); training=time.perf_counter()-t
    methods={'dictionary':lambda x:lexicon(x,vocab),'small_mlp':small,'pretrained':pretrained}
    pred,elapsed={},{}
    for split in ('calibration','test','external'):
        rows=parts[split]; pred[split],elapsed[split]={},{}
        for name,fn in methods.items():
            t=time.perf_counter(); pred[split][name]={r['id']:fn(r['text']) for r in rows}; elapsed[split][name]=time.perf_counter()-t
    cal=pred['calibration']; eligible=[(cal['pretrained'][r['id']][1],cal['pretrained'][r['id']][0]==r['spans']) for r in parts['calibration'] if cal['dictionary'][r['id']][0]==[] and cal['pretrained'][r['id']][0]]
    threshold=fallback_gate(eligible)
    result=dict(scope='external authored biomedical abstract span benchmark; public and potentially pretraining-exposed; not clinical',freeze_sha256=digest(freeze),models={'small_mlp':small_meta,'pretrained':model},training_seconds=training,load_seconds=load,calibration=dict(eligible=len(eligible),threshold=threshold),elapsed_seconds=elapsed,results={})
    for split in ('test','external'):
        rows=parts[split]
        if not rows:
            result['results'][split] = dict(status='unavailable', reason='source integrity, rights or overlap gate')
            continue
        arms=pred[split]; arms['fallback']=fallback(arms['dictionary'],arms['pretrained'],threshold)
        arms['agreement']={i:(r[0],min(r[1],arms['pretrained'][i][1])) if r[0]==arms['pretrained'][i][0] else (None,0.) for i,r in arms['dictionary'].items()}
        record={}
        for name,p in arms.items():
            metrics=span_metrics(rows,p)
            record[name]=dict(metrics=metrics,matched={str(k):matched_budget(rows,p,int(len(rows)*k/100)) for k in (50,75,100)},prediction_sha256=digest(p),novel_gold=sum(r['text'][a:b].casefold() not in vocab for r in rows for a,b in r['spans']),novel_correct=sum(r['text'][a:b].casefold() not in vocab and [a,b] in (p[r['id']][0] or []) for r in rows for a,b in r['spans']))
        def paired_rows(p):
            return [dict(id=digest(r['id']), groups={'document':digest(r['id'])}, gold=r['spans'], prediction=p[r['id']][0]) for r in rows]
        result['results'][split]=dict(arms=record, fallback_activations=sum(arms['fallback'][i]!=arms['dictionary'][i] for i in arms['dictionary']),
            contrasts={name:paired_f1_interval(paired_rows(arms['dictionary']),paired_rows(arms[name]),grouping_key='document',seed=17,draws=200) for name in ('small_mlp','pretrained','fallback','agreement')} if len(rows)>1 else {},
            predictions={name:paired_rows(p) for name,p in arms.items()})
    (output/'result.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',required=True,type=Path)
    args=parser.parse_args();run(args.output_dir)


if __name__=='__main__':
    main()
