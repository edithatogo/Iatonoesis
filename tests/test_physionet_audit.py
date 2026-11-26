import pytest
from iatonoesis.physionet_audit import HEADER, audit, inspect_record, sample_keys


def record(hours=8, missing=False):
    lines = ['|'.join(HEADER)]
    for hour in range(1, hours+1):
        row = ['1']*len(HEADER)
        row[HEADER.index('ICULOS')] = str(hour)
        row[HEADER.index('SepsisLabel')] = '0'
        if missing:
            row[HEADER.index('HR')] = 'NaN'
        lines.append('|'.join(row))
    return ('\n'.join(lines)+'\n').encode()


def test_schema_cutoff_and_missingness():
    result = inspect_record(record())
    assert result['rows'] == 8
    assert result['eligible_state'] and result['eligible_acquisition']
    result = inspect_record(record(missing=True))
    assert result['missing']['HR'] == 8
    assert not result['eligible_state'] and not result['eligible_acquisition']
    with pytest.raises(ValueError, match='header'):
        inspect_record(b'x|y\n1|2\n')


def test_reject_nonfinite_and_invalid_time():
    with pytest.raises(ValueError, match='nonfinite'):
        inspect_record(record().replace(b'1|1|1|', b'inf|1|1|', 1))
    with pytest.raises(ValueError, match='time'):
        inspect_record(record().replace(b'|8|0\n', b'|2|0\n'))


def test_deterministic_sample_independent_of_listing_order():
    keys = [f'p{i:06}.psv' for i in range(20)]
    assert sample_keys(keys, 8) == sample_keys(list(reversed(keys)), 8)
    assert len(set(sample_keys(keys,8))) == 8
    with pytest.raises(ValueError,match='duplicate'):
        sample_keys(keys+keys[:1],8)


def test_receipt_is_aggregate_and_partitioned():
    inventories = {'A':['p000001.psv','p000002.psv','p000003.psv'],
                   'B':['p100001.psv','p100002.psv','p100003.psv']}
    result = audit(inventories, lambda cohort,key:record(hours=8+int(key[1:7])%3), count=3,
                   expected={'A':3,'B':3})
    assert result['cohorts']['A']['sampled'] == 3
    assert result['cohorts']['B']['partition_counts'] == {'test':3}
    assert sum(result['cohorts']['A']['partition_counts'].values()) == 3
    assert len(result['sample_manifest_sha256']) == 64
    assert 'p000001' not in str(result) and 'p100001' not in str(result)
    with pytest.raises(ValueError,match='overlap'):
        audit({'A':['p000001.psv'], 'B':['p000001.psv']},lambda *_:record(),count=1,expected={'A':1,'B':1})
