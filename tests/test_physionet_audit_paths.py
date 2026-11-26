"""Exercise fail-closed source audit behavior without external requests."""
import io
import json
import sys
from urllib.parse import parse_qs, urlsplit

import pytest
from iatonoesis import physionet_audit as audit
from test_physionet_audit import record


def test_record_rejects_empty_width_and_invalid_label():
    with pytest.raises(ValueError, match='empty'):
        audit.inspect_record(('|'.join(audit.HEADER)+'\n').encode())
    with pytest.raises(ValueError, match='width'):
        audit.inspect_record(record().replace(b'|8|0\n', b'|8\n'))
    with pytest.raises(ValueError, match='label'):
        audit.inspect_record(record().replace(b'|8|0\n', b'|8|2\n'))
    assert audit.inspect_record(record().replace(b'|8|0\n', b'|9|0\n'))['time_gaps'] == 1


def test_sample_validation_and_audit_errors():
    with pytest.raises(ValueError, match='count'):
        audit.sample_keys(['p000001.psv'], 0)
    with pytest.raises(ValueError, match='key'):
        audit.sample_keys(['unexpected'], 1)
    with pytest.raises(ValueError, match='cohort'):
        audit.audit({'A':[]}, lambda *_: record(), count=1)
    inventories = {'A':['p000001.psv'], 'B':['p100001.psv']}
    with pytest.raises(ValueError, match='inventory count'):
        audit.audit(inventories, lambda *_: record(), count=1)
    with pytest.raises(ValueError, match='source fetch or schema') as exc:
        audit.audit(inventories, lambda *_: b'bad', count=1, expected={'A':1,'B':1})
    assert 'p000001' not in str(exc.value)
    result = audit.audit(inventories, lambda *_:record(), count=1, expected={'A':1,'B':1})
    assert result['duplicate_content'] == result['cross_partition_duplicate_content'] == 1


def test_bounded_get_and_paginated_inventory(monkeypatch):
    monkeypatch.setattr(audit, 'urlopen', lambda *a, **k: io.BytesIO(b'abc'))
    assert audit.get('https://example.invalid', 3) == b'abc'
    with pytest.raises(ValueError, match='limit'):
        audit.get('https://example.invalid', 2)
    prefix = audit.PREFIX+'A/'
    def page(url, limit):
        query = parse_qs(urlsplit(url).query)
        assert query['prefix'] == [prefix]
        if 'continuation-token' not in query:
            return f'<ListBucketResult><Contents><Key>{prefix}p000001.psv</Key></Contents><Contents><Key>{prefix}README</Key></Contents><IsTruncated>true</IsTruncated><NextContinuationToken>next</NextContinuationToken></ListBucketResult>'.encode()
        assert query['continuation-token'] == ['next']
        return f'<ListBucketResult><Contents><Key>{prefix}p000002.psv</Key></Contents><IsTruncated>false</IsTruncated></ListBucketResult>'.encode()
    monkeypatch.setattr(audit, 'get', page)
    assert audit.inventory('A') == ['p000001.psv','p000002.psv']
    monkeypatch.setattr(audit, 'get', lambda *_:b'<ListBucketResult><IsTruncated>true</IsTruncated></ListBucketResult>')
    with pytest.raises(ValueError, match='token'):
        audit.inventory('A')
    monkeypatch.setattr(audit, 'get', lambda *_:b'<ListBucketResult><IsTruncated>true</IsTruncated><NextContinuationToken>same</NextContinuationToken></ListBucketResult>')
    with pytest.raises(ValueError, match='page limit'):
        audit.inventory('A')


def test_cli_writes_only_aggregate_and_failure_receipts(monkeypatch, tmp_path):
    output = tmp_path/'aggregate.json'
    monkeypatch.setattr(sys,'argv',['audit','--output',str(output),'--count','32'])
    monkeypatch.setattr(audit,'inventory',lambda cohort:[cohort])
    monkeypatch.setattr(audit,'get',lambda *_:b'fixture')
    def run(inventories, fetch, *, count):
        assert count == 32 and fetch('A','p000001.psv') == b'fixture'
        return {'status':'bounded_source_sample_audited_not_qualified','sampled':1}
    monkeypatch.setattr(audit,'audit',run)
    audit.main()
    assert json.loads(output.read_text())['sampled'] == 1
    def fail(*a,**k):
        raise ValueError('private identifier p000001')
    monkeypatch.setattr(audit,'audit',fail)
    with pytest.raises(SystemExit) as exc:
        audit.main()
    assert exc.value.code == 1
    receipt = json.loads(output.read_text())
    assert receipt['status']=='failed' and receipt['reason']=='ValueError'
    assert 'p000001' not in output.read_text()
