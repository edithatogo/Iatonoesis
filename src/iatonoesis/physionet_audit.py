"""Bounded aggregate-only audit of the public PhysioNet 2019 source; no training."""
import argparse
import hashlib
import json
import math
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlencode, quote
from urllib.request import urlopen
from xml.etree import ElementTree

HEADER = tuple('HR O2Sat Temp SBP MAP DBP Resp EtCO2 BaseExcess HCO3 FiO2 pH PaCO2 SaO2 AST BUN Alkalinephos Calcium Chloride Creatinine Bilirubin_direct Glucose Lactate Magnesium Phosphate Potassium Bilirubin_total TroponinI Hct Hgb PTT WBC Fibrinogen Platelets Age Gender Unit1 Unit2 HospAdmTime ICULOS SepsisLabel'.split())
SOURCE = 'https://physionet-open.s3.amazonaws.com/'
PREFIX = 'challenge-2019/1.0.0/training/training_set'
EXPECTED = {'A':20336, 'B':20000}
SEED = 'iatonoesis-physionet-audit-v0.1.0'
AUX = ('MAP','Resp','O2Sat')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return sha(json.dumps(value, sort_keys=True, separators=(',',':'), allow_nan=False).encode())


def inspect_record(raw):
    lines = raw.decode('ascii').splitlines()
    if not lines or tuple(lines[0].split('|')) != HEADER:
        raise ValueError('unexpected header')
    if len(lines) < 2:
        raise ValueError('empty record')
    missing = dict.fromkeys(HEADER,0)
    last_time = None
    past = []
    state = acquire = False
    gaps = 0
    for line in lines[1:]:
        parts = line.split('|')
        if len(parts) != len(HEADER):
            raise ValueError('wrong row width')
        vals = {}
        for column, part in zip(HEADER,parts):
            if part == 'NaN':
                vals[column] = None
                missing[column] += 1
            else:
                value = float(part)
                if not math.isfinite(value):
                    raise ValueError('nonfinite nonmissing value')
                vals[column] = value
        t = vals['ICULOS']
        if t is None or t < 1 or t != int(t) or (last_time is not None and t <= last_time):
            raise ValueError('invalid observation time')
        if last_time is not None and t != last_time+1:
            gaps += 1
        last_time = t
        if vals['SepsisLabel'] not in (0,1):
            raise ValueError('invalid source label')
        # Strictly earlier hours; only actually measured HR is a reconstruction target.
        past = [(h,observed) for h,observed in past if h >= t-6]
        if t >= 7 and vals['HR'] is not None and any(observed for _,observed in past):
            state = True
            if all(vals[k] is not None for k in AUX):
                acquire = True
        past.append((t, vals['HR'] is not None))
    return dict(rows=len(lines)-1, missing=missing, eligible_state=state,
                eligible_acquisition=acquire, time_gaps=gaps)


def sample_keys(keys, count):
    if len(set(keys)) != len(keys):
        raise ValueError('duplicate inventory key')
    if type(count) is not int or not 1 <= count <= len(keys):
        raise ValueError('invalid sample count')
    if not all(re.fullmatch(r'p[0-9]+\.psv', key) for key in keys):
        raise ValueError('invalid inventory key')
    return sorted(keys, key=lambda k:(sha((SEED+'|'+k).encode()),k))[:count]


def partition(cohort,key):
    if cohort == 'B':
        return 'test'
    return 'calibration' if int(sha((SEED+'|split|'+key).encode())[:8],16)%5 == 0 else 'development'


def audit(inventories, fetch, *, count=128, expected=EXPECTED):
    if set(inventories) != {'A','B'} or set(expected) != {'A','B'}:
        raise ValueError('missing source cohort')
    if set(inventories['A']) & set(inventories['B']):
        raise ValueError('cohort key overlap')
    manifest, cohorts = [], {}
    seen = {}
    duplicates = cross_partition_duplicates = 0
    for cohort in ('A','B'):
        keys = inventories[cohort]
        if len(keys) != expected[cohort]:
            raise ValueError('unexpected source inventory count')
        selected = sample_keys(keys,count)
        totals = Counter()
        missing, parts, eligible = Counter(), Counter(), Counter()
        def examine(key):
            try:
                raw = fetch(cohort,key)
                return key, sha(raw), len(raw), inspect_record(raw)
            except Exception:
                # Never emit a patient identifier or row in the error trace.
                raise ValueError('source fetch or schema validation failed') from None
        with ThreadPoolExecutor(max_workers=8) as pool:
            for key, digest, size, stats in pool.map(examine, selected):
                part = partition(cohort,key)
                parts[part] += 1
                if digest in seen:
                    duplicates += 1
                    cross_partition_duplicates += int(seen[digest] != part)
                else:
                    seen[digest] = part
                manifest.append((cohort,key,digest,size,part))
                totals.update(rows=stats['rows'],bytes=size,time_gaps=stats['time_gaps'])
                missing.update(stats['missing'])
                eligible.update({part+'_state':int(stats['eligible_state']),
                                 part+'_acquisition':int(stats['eligible_acquisition'])})
        cohorts[cohort] = dict(inventory_count=len(keys), inventory_sha256=canonical(sorted(keys)),
                               sampled=len(selected), partition_counts=dict(parts),
                               eligible_counts=dict(eligible), missing_counts=dict(missing), **dict(totals))
    return dict(version='0.1.0', status='bounded_source_sample_audited_not_qualified',
                source='PhysioNet challenge-2019/1.0.0', licence='CC-BY-4.0', sample_seed=SEED,
                sample_manifest_sha256=canonical(manifest), cohorts=cohorts,
                duplicate_content=duplicates, cross_partition_duplicate_content=cross_partition_duplicates,
                reference='withheld observed HR at cutoff; prior six-hour observations only; optional same-time MAP/Resp/O2Sat',
                limits=['observed digests not publisher checksums','bounded sample not full byte audit',
                        'cohort A/B not verified site identity','no model training or institutional determination'])


def get(url, limit):
    with urlopen(url,timeout=30) as response:
        raw = response.read(limit+1)
    if len(raw)>limit:
        raise ValueError('source response exceeds limit')
    return raw


def inventory(cohort):
    prefix = PREFIX+cohort+'/'
    token = None
    keys = []
    for _ in range(100):
        params = {'list-type':'2','prefix':prefix,'max-keys':'1000'}
        if token:
            params['continuation-token'] = token
        root = ElementTree.fromstring(get(SOURCE+'?'+urlencode(params),2_000_000))
        for item in root.findall('{*}Contents/{*}Key'):
            value = item.text or ''
            if value.startswith(prefix) and value.endswith('.psv'):
                keys.append(value[len(prefix):])
        if root.findtext('{*}IsTruncated') != 'true':
            return keys
        token = root.findtext('{*}NextContinuationToken')
        if not token:
            raise ValueError('missing continuation token')
    raise ValueError('inventory page limit exceeded')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--count',type=int,default=128,choices=(32,128,256))
    args = parser.parse_args()
    try:
        result = audit({c:inventory(c) for c in ('A','B')},
                       lambda c,k:get(SOURCE+quote(PREFIX+c+'/'+k,safe='/'),2_000_000),count=args.count)
    except Exception as exc:
        args.output.write_text(json.dumps(dict(status='failed',reason=type(exc).__name__,
            scope='bounded aggregate audit; no source records retained'))+'\n')
        raise SystemExit(1) from None
    args.output.write_text(json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+'\n')


if __name__ == '__main__':
    main()
