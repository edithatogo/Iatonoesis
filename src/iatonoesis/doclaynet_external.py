"""Human-annotated external page detection; model exposure is explicitly unresolved."""
import argparse
import hashlib
import io
import json
import math
import tempfile
import time
from pathlib import Path
from .mondo_temporal import digest, verify_source

DATA='docling-project/DocLayNet-v1.1'
DATA_REF='5e89392'
MODEL='docling-project/docling-layout-heron'
MODEL_REF='ba3d2ab1d8914adf82cbb435a2f126264673ccea'
WEIGHTS='00333a43451945aaf89db8ca9c0a17e75d1537c17db60fdb91aa95f4c7929e0c'
FILES={'val':{'data/val-00000-of-00003-773d4c8bcd94c1c8.parquet':765073914,'data/val-00001-of-00003-85237747c8a9b131.parquet':895322981,'data/val-00002-of-00003-187c2752863691c7.parquet':761290139},'test':{'data/test-00000-of-00002-635b47e9044a436c.parquet':1053660329,'data/test-00001-of-00002-b2396409212624ed.parquet':885024279}}
LABELS=('caption','footnote','formula','list_item','page_footer','page_header','picture','section_header','table','text','title')


def box(b):
    if len(b)!=4 or not all(math.isfinite(x) for x in b) or b[2]<=0 or b[3]<=0: raise ValueError('invalid xywh box')
    return [float(b[0]),float(b[1]),float(b[0]+b[2]),float(b[1]+b[3])]


def iou(a,b):
    area=lambda p:max(0.,p[2]-p[0])*max(0.,p[3]-p[1])
    inter=area([max(a[0],b[0]),max(a[1],b[1]),min(a[2],b[2]),min(a[3],b[3])]); union=area(a)+area(b)-inter
    return inter/union if union>0 else 0.


def match(gold,pred,overlap=.5,classes=True):
    remaining=set(range(len(gold))); tp=0
    for label,b,score in sorted(pred,key=lambda p:(-p[2],p[0],p[1])):
        choices=[(iou(b,gold[i][1]),-i) for i in remaining if not classes or label==gold[i][0]]
        if choices:
            v,i=max(choices)
            if v>=overlap: remaining.remove(-i); tp+=1
    return tp,len(pred)-tp,len(gold)-tp


def select(val,test,per_category=32):
    def keys(rows,field): return {r[2][field] for r in rows}
    overlaps=keys(val,'original_filename')&keys(test,'original_filename'); pages=keys(val,'page_hash')&keys(test,'page_hash')
    def pick(rows,split):
        chosen={}; docs=set(); hashes=set()
        for row in sorted(rows,key=lambda r:(digest([split,r[2]['page_hash'],r[2]['image_id']]),r[0],r[1])):
            m=row[2]; d=m['original_filename']; h=m['page_hash']; cat=m['doc_category']
            if not d or not h or not cat: raise ValueError('missing metadata')
            if d in overlaps or h in pages or d in docs or h in hashes or len(chosen.get(cat,[]))>=per_category: continue
            chosen.setdefault(cat,[]).append(row); docs.add(d); hashes.add(h)
        return [r for c in sorted(chosen) for r in chosen[c]]
    v,t=pick(val,'val'),pick(test,'test')
    if not v or not t: raise ValueError('empty sample')
    return v,t,dict(val_population=len(val),test_population=len(test),overlap_documents=len(overlaps),overlap_pages=len(pages),val_sample_sha256=digest(v),test_sample_sha256=digest(t))


def metrics(rows,cut,cap,classes=True,overlap=.5):
    tp=fp=fn=0; proposals=0
    for r in rows:
        pred=sorted((p for p in r['pred'] if p[2]>=cut),key=lambda p:(-p[2],p[0],p[1]))[:cap]
        a,b,c=match(r['gold'],pred,overlap,classes); tp+=a;fp+=b;fn+=c;proposals+=len(pred)
    return dict(pages=len(rows),tp=tp,fp=fp,fn=fn,proposals=proposals,f1=2*tp/(2*tp+fp+fn) if tp or fp or fn else None)


def threshold(rows):
    return max((.1,.25,.5,.9),key=lambda t:((metrics(rows,t,60)['f1'] or 0.),t))


def geometry(image):
    import numpy as np
    from scipy.ndimage import binary_closing,label,find_objects
    a=np.asarray(image.convert('L'))<200
    m=binary_closing(a,structure=np.ones((3,11),dtype=bool)); m=binary_closing(m,structure=np.ones((5,1),dtype=bool))
    labels,_=label(m); pred=[]
    for y,x in find_objects(labels):
        if (y.stop-y.start)*(x.stop-x.start)<40: continue
        density=float(a[y,x].mean()); pred.append(('text',[float(x.start),float(y.start),float(x.stop),float(y.stop)],density))
    return sorted(pred,key=lambda p:(-p[2],p[1]))[:300]


def hybrid(a,b):
    out=list(a)
    for p in b:
        if not any(iou(p[1],q[1])>=.5 for q in out): out.append(p)
    return out


def evaluate(val,test):
    result={}
    for arm in ('geometry','heron','hybrid'):
        v=[dict(r,pred=r[arm]) for r in val]; t=[dict(r,pred=r[arm]) for r in test]; cut=threshold(v)
        categories=sorted({r['category'] for r in t})
        result[arm]=dict(validation_threshold=cut,validation=metrics(v,cut,60),test={str(cap):{f'{kind}_{overlap}':metrics(t,cut,cap,kind=='typed',overlap) for kind in ('typed','agnostic') for overlap in (.5,.75)} for cap in (30,60,120)},categories={c:metrics([r for r in t if r['category']==c],cut,60) for c in categories},test_seconds=sum(r['seconds'][arm] for r in t))
        confidence=lambda r:min((p[2] for p in r['pred'] if p[2]>=cut),default=0.)
        ordered=sorted(t,key=lambda r:(-confidence(r),r['identity']))
        result[arm]['review_frontier']=[dict(retained=int(len(t)*f),review=len(t)-int(len(t)*f),metrics=metrics(ordered[:int(len(t)*f)]+[dict(r,pred=[]) for r in ordered[int(len(t)*f):]],cut,60)) for f in (.25,.5,.75,1.)]
    return result


def file_pin(info,name,size):
    matches=[f for f in info.siblings if f.rfilename==name]
    if len(matches)!=1 or matches[0].size!=size or not matches[0].lfs: raise ValueError('source pin mismatch')
    lfs=matches[0].lfs; sha=lfs.sha256 if hasattr(lfs,'sha256') else lfs['sha256']
    if not isinstance(sha,str) or len(sha)!=64: raise ValueError('missing LFS SHA')
    return sha


def acquire(root):
    import pyarrow.parquet as pq
    from huggingface_hub import HfApi,hf_hub_download
    api=HfApi(); info=api.dataset_info(DATA,revision=DATA_REF,files_metadata=True)
    if not info.sha.startswith(DATA_REF): raise ValueError('dataset revision mismatch')
    card=Path(hf_hub_download(DATA,'README.md',repo_type='dataset',revision=info.sha,local_dir=root/'data'))
    if 'CDLA-Permissive-1.0' not in card.read_text(): raise ValueError('dataset licence not verified')
    paths={}; rows={}; receipts={}
    for split,files in FILES.items():
        rows[split]=[]
        for name,size in files.items():
            sha=file_pin(info,name,size); path=Path(hf_hub_download(DATA,name,repo_type='dataset',revision=info.sha,local_dir=root/'data')); paths[name]=path
            receipts[name]=verify_source(path,size,sha); pf=pq.ParquetFile(path); i=0
            for batch in pf.iter_batches(columns=['metadata'],batch_size=256):
                for row in batch.to_pylist(): rows[split].append((name,i,row['metadata'])); i+=1
        if len(rows[split])!=dict(val=6489,test=4999)[split]: raise ValueError('unexpected split population')
    return paths,rows,dict(revision=info.sha,files=receipts,licence='CDLA-Permissive-1.0',card_sha256=hashlib.sha256(card.read_bytes()).hexdigest())


def detector(root):
    import torch
    from huggingface_hub import snapshot_download
    from transformers import RTDetrV2ForObjectDetection,RTDetrImageProcessor
    p=Path(snapshot_download(MODEL,revision=MODEL_REF,allow_patterns=['README.md','config.json','preprocessor_config.json','model.safetensors'],local_dir=root/'model'))
    if 'license: apache-2.0' not in (p/'README.md').read_text(): raise ValueError('model licence not verified')
    receipt=verify_source(p/'model.safetensors',171658996,WEIGHTS)
    receipt.update(revision=MODEL_REF,files={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in p.iterdir() if f.is_file() and f.name!='model.safetensors'})
    processor=RTDetrImageProcessor.from_pretrained(p,local_files_only=True)
    model=RTDetrV2ForObjectDetection.from_pretrained(p,local_files_only=True,use_safetensors=True).eval(); torch.set_num_threads(4)
    def predict(im):
        with torch.inference_mode():
            result=processor.post_process_object_detection(model(**processor(images=[im],return_tensors='pt')),target_sizes=torch.tensor([im.size[::-1]]),threshold=0.)[0]
        return [(model.config.id2label[int(l)],b.tolist(),float(s)) for l,b,s in zip(result['labels'],result['boxes'],result['scores'],strict=True)]
    return predict,receipt


def execute(paths,selected,predict):
    from PIL import Image
    import pyarrow.parquet as pq
    wanted={(name,i):m for name,i,m in selected}; out=[]
    for name in sorted({x[0] for x in selected}):
        i=0
        for batch in pq.ParquetFile(paths[name]).iter_batches(columns=['image','bboxes','category_id','metadata'],batch_size=16):
            targets=[j for j in range(batch.num_rows) if (name,i+j) in wanted]
            for j in targets:
                row=batch.slice(j,1).to_pylist()[0]; m=wanted[(name,i+j)]
                if row['metadata']!=m: raise ValueError('metadata mismatch')
                im=Image.open(io.BytesIO(row['image']['bytes'])).convert('RGB')
                if im.size!=(m['coco_width'],m['coco_height']): raise ValueError('coordinate frame mismatch')
                gold=[(LABELS[int(c)-1],box(b)) for c,b in zip(row['category_id'],row['bboxes'],strict=True) if 1<=int(c)<=len(LABELS)]
                if len(gold)!=len(row['category_id']): raise ValueError('unknown class')
                start=time.perf_counter(); a=geometry(im); ga=time.perf_counter()-start; start=time.perf_counter(); b=predict(im); hb=time.perf_counter()-start; start=time.perf_counter(); c=hybrid(b,a); hc=time.perf_counter()-start
                out.append(dict(identity=digest([name,i+j]),category=m['doc_category'],gold=gold,geometry=a,heron=b,hybrid=c,seconds=dict(geometry=ga,heron=hb,hybrid=ga+hb+hc)))
            i+=batch.num_rows
    if len(out)!=len(wanted): raise ValueError('missing selected rows')
    return out


def run(root):
    paths,rows,source=acquire(root); val,test,selection=select(rows['val'],rows['test']); predict,model=detector(root)
    v=execute(paths,val,predict); t=execute(paths,test,predict)
    return dict(scope='published_human_annotated_layout_replay_not_unseen_source',dataset=source,model=model,selection=selection,validation_pages=len(v),test_pages=len(t),prediction_sha256=digest([{k:v for k,v in r.items() if k!='seconds'} for r in t]),arms=evaluate(v,t))


def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--output',type=Path,required=True); args=parser.parse_args()
    try:
        with tempfile.TemporaryDirectory() as d: result=run(Path(d))
    except Exception as exc:
        args.output.write_text(json.dumps(dict(status='failed',error_type=type(exc).__name__))+'\n'); raise
    args.output.write_text(json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+'\n')


if __name__=='__main__': main()
