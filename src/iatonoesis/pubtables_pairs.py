"""Bounded, aggregate-only pairing audit for pinned PubTables structure-test data."""
import argparse
import hashlib
import io
import json
import math
import re
import tarfile
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path, PurePosixPath

from .dataset_audit import TABLE_REV, _download, verify_bytes

PREFIX='PubTables-1M-Structure_'
SOURCES={
    'annotations':(PREFIX+'Annotations_Test.tar.gz',40_000_000),
    'images':(PREFIX+'Images_Test.tar.gz',3_000_000_000),
    'words':(PREFIX+'Table_Words.tar.gz',4_500_000_000),
}
SEED='iatonoesis-pubtables-pairing-v0.1.0'


def digest(data):
    return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def pin(rows, filename, cap):
    matches=[r for r in rows if r.get('path')==filename]
    if len(matches)!=1:
        raise ValueError('pinned archive metadata absent or duplicated')
    row=matches[0];size=row.get('size');lfs=row.get('lfs') or {};sha=lfs.get('oid') or lfs.get('sha256')
    if type(size) is not int or not 0<size<=cap or not isinstance(sha,str) or not re.fullmatch(r'[0-9a-f]{64}',sha):
        raise ValueError('invalid or oversized pinned archive metadata')
    return size,sha


def members(path, suffix, limit):
    names=set();expanded=0
    with tarfile.open(path,'r|gz') as ar:
        for member in ar:
            p=PurePosixPath(member.name)
            if p.is_absolute() or '..' in p.parts or '\\' in member.name:
                raise ValueError('unsafe archive path')
            if member.isdir():
                continue
            if not member.isfile() or member.size>64_000_000 or member.size<0:
                raise ValueError('unsafe archive member')
            expanded+=member.size
            if len(names)>=limit or expanded>60_000_000_000:
                raise ValueError('expanded archive resource cap')
            if member.name in names:
                raise ValueError('duplicate archive member')
            names.add(member.name)
            if not p.name.endswith(suffix):
                raise ValueError('unexpected archive file type')
            key=p.name[:-len(suffix)]
            if not re.fullmatch(r'PMC\d+_table_\d+',key,re.I):
                raise ValueError('unexpected table identity')
            source=ar.extractfile(member)
            if source is None:
                raise ValueError('unreadable member')
            yield key,source


def annotation_index(path):
    result={}
    for key,stream in members(path,'.xml',120000):
        if key in result:
            raise ValueError('duplicate annotation identity')
        raw=stream.read(1_000_001)
        if len(raw)>1_000_000 or b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
            raise ValueError('unsafe annotation XML')
        root=ET.fromstring(raw)
        if root.tag!='annotation':
            raise ValueError('invalid annotation XML')
        try:
            dims=int(root.findtext('size/width')),int(root.findtext('size/height'))
        except (TypeError,ValueError) as exc:
            raise ValueError('missing annotation dimensions') from exc
        if not all(0<v<=50000 for v in dims):
            raise ValueError('invalid annotation dimensions')
        result[key]={'dims':dims,'sha256':hashlib.sha256(raw).hexdigest()}
    return result


def sample_tables(annotations,count):
    docs={}
    for key in annotations:
        doc=key.split('_',1)[0].upper()
        docs.setdefault(doc,[]).append(key)
    order=lambda v: (hashlib.sha256((SEED+'|'+v).encode()).hexdigest(),v)
    if type(count) is not int or not 1<=count<=len(docs):
        raise ValueError('insufficient document groups')
    return [min(docs[d],key=order) for d in sorted(docs,key=order)[:count]]


def decode_jpeg(raw):
    from PIL import Image
    with Image.open(io.BytesIO(raw)) as im:
        if im.format!='JPEG' or im.width*im.height>100_000_000:
            raise ValueError('invalid or oversized image')
        im.load()
        return im.size


def image_index(path,annotations,selected,*,decode=decode_jpeg):
    keys=set();sample={};wanted=set(selected)
    for key,stream in members(path,'.jpg',120000):
        if key in keys:
            raise ValueError('duplicate image identity')
        keys.add(key)
        if key in wanted:
            raw=stream.read()
            dims=decode(raw)
            if tuple(dims)!=annotations[key]['dims']:
                raise ValueError('image dimensions mismatch')
            sample[key]=hashlib.sha256(raw).hexdigest()
    return {'keys':keys,'sample':sample}


def word_index(path,annotations,selected):
    keys=set();sample={};wanted=set(selected)
    for key,stream in members(path,'_words.json',1_200_000):
        if key in keys:
            raise ValueError('duplicate word identity')
        keys.add(key)
        if key not in wanted:
            continue
        raw=stream.read(16_000_001)
        if len(raw)>16_000_000:
            raise ValueError('word JSON exceeds cap')
        tokens=json.loads(raw)
        if not isinstance(tokens,list):
            raise ValueError('invalid word list')
        width,height=annotations[key]['dims'];outside=0
        for token in tokens:
            if not isinstance(token,dict) or not isinstance(token.get('text'),str):
                raise ValueError('invalid word token')
            b=token.get('bbox')
            if not isinstance(b,list) or len(b)!=4 or not all(type(x) in (int,float) and math.isfinite(x) for x in b) or b[0]>b[2] or b[1]>b[3]:
                raise ValueError('invalid word bbox')
            outside+=int(b[0]<0 or b[1]<0 or b[2]>width or b[3]>height)
        sample[key]={'sha256':hashlib.sha256(raw).hexdigest(),'count':len(tokens),'outside':outside}
    return {'keys':keys,'sample':sample}


def pair_receipt(annotations,selected,images,words):
    ids=set(annotations);wanted=set(selected)
    if ids!=images['keys'] or not ids<=words['keys'] or set(images['sample'])!=wanted or set(words['sample'])!=wanted:
        raise ValueError('incomplete or mismatched image/word pair membership')
    manifest=[(k,annotations[k]['sha256'],images['sample'][k],words['sample'][k]['sha256']) for k in selected]
    return dict(annotation_tables=len(ids),image_tables=len(images['keys']),matched_image_word_tables=len(ids&images['keys']&words['keys']),
                word_archive_tables=len(words['keys']),word_archive_extra_tables=len(words['keys']-ids),
                sample_validated=len(selected),sample_document_count=len({k.split('_')[0].upper() for k in selected}),
                sample_manifest_sha256=digest(manifest),sample_word_count=sum(v['count'] for v in words['sample'].values()),
                sample_empty_word_tables=sum(v['count']==0 for v in words['sample'].values()),
                sample_outside_frame_words=sum(v['outside'] for v in words['sample'].values()),
                evaluation_admitted=False,scope='source pairing and bounded sample validation only')


def run(root):
    root.mkdir(parents=True,exist_ok=True)
    api=f'https://huggingface.co/api/datasets/bsmock/pubtables-1m/tree/{TABLE_REV}?recursive=false&expand=true'
    meta=root/'metadata.json';_download(api,meta,2_000_000)
    metadata=json.loads(meta.read_text())
    pins={key:pin(metadata,name,cap) for key,(name,cap) in SOURCES.items()}
    receipts={}
    def acquire(key):
        name,cap=SOURCES[key];size,sha=pins[key];p=root/name
        _download(f'https://huggingface.co/datasets/bsmock/pubtables-1m/resolve/{TABLE_REV}/{name}',p,size)
        receipts[key]=dict(filename=name,**verify_bytes(p,size,sha))
        return p
    p=acquire('annotations');annotations=annotation_index(p);p.unlink()
    if len(annotations)!=93834:
        raise ValueError('unexpected annotation population')
    selected=sample_tables(annotations,128)
    p=acquire('images');images=image_index(p,annotations,selected);p.unlink()
    p=acquire('words');words=word_index(p,annotations,selected);p.unlink()
    return dict(schema_version='0.1.0',revision=TABLE_REV,archives=receipts,**pair_receipt(annotations,selected,images,words))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    try:
        with tempfile.TemporaryDirectory() as directory:
            result=run(Path(directory))
    except Exception as exc:
        args.output.write_text(json.dumps(dict(status='failed',error_type=type(exc).__name__,evaluation_admitted=False))+'\n')
        raise SystemExit(1) from None
    args.output.write_text(json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+'\n')


if __name__=='__main__':
    main()
