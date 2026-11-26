import pytest
from iatonoesis.ontology_factorial import queries, pool, gate, factorial, parse


def nodes(edges):
    return {str(i): {'name': f'term {i}', 'parents': {str(p) for c,p in edges if c==i}} for i in range(1,9)}


def test_queries_keep_new_edges_and_no_change_without_leaking_new_names():
    a=nodes([(2,1),(3,1),(4,2)])
    b=nodes([(2,1),(3,1),(4,2),(2,3)])
    b['2']['name']='future'
    q,s=queries(a,b,'fresh')
    assert s['eligible_edges']==1 and s['changed']==1 and s['unchanged']==1
    assert next(x for x in q if x['child']=='2')['gold']==['3']
    assert all(x['child'] in a for x in q)


def test_equal_budget_factorial_and_cycle_exclusion():
    a=nodes([(2,1),(3,1),(4,2),(5,4)])
    channels={'L':['1','2','4','5','3','6'],'S':['4','6','7'],'G':['5','8','6']}
    for arm in factorial():
        p=pool(a,'2',channels,arm,3,'x')
        assert len(p)==3 and not set(p)&{'1','2','4','5'} and len(set(p))==3
    assert pool(a,'2',channels,'L',3,'x')==['3','6','7'] or set(pool(a,'2',channels,'L',3,'x')) >= {'3','6'}
    assert len(factorial())==8
    with pytest.raises(ValueError): pool(a,'2',channels,'bad',3,'x')


def test_gate_never_uses_test_or_insufficient_confirmation():
    good=[(.9,True)]*100
    assert gate(good,good)['threshold']==.0
    assert gate(good,[(.9,False)]*100)['threshold'] is None
    assert gate(good,good[:4])['threshold'] is None
    assert gate([],good)['threshold'] is None


def test_parse_hpo_identity(tmp_path):
    p=tmp_path/'hp.obo'
    p.write_text('format-version: 1.2\ndata-version: releases/2026-09-01\n\n[Term]\nid: HP:0000001\nname: root\n\n[Term]\nid: HP:0000002\nname: child\nis_a: HP:0000001 ! root\n')
    assert parse(p,'2026-09-01','HP')['HP:0000002']['parents']=={'HP:0000001'}
    with pytest.raises(ValueError): parse(p,'wrong','HP')


def test_preparation_and_factorial_effects():
    pytest.importorskip('numpy')
    from iatonoesis.ontology_factorial import prepare, report_pool, factorial_effects
    a=nodes([(2,1),(3,1),(4,2)])
    q=[{'child':'2','gold':['3']},{'child':'6','gold':[]}]
    vectors={v['name']:[int(k),1.] for k,v in a.items()}
    prepared=prepare(a,q,vectors,'held')
    m=report_pool(prepared)
    assert len(m)==24 and all(x['gold']==1 for x in m.values())
    assert set(factorial_effects(m))=={'16','32','64'}
    assert all('features' not in rows[0] for key,rows in prepared.items() if key!='LSG:32')
    with pytest.raises(ValueError): prepare(a,[],vectors,'held')


def test_message_passing_and_transfer_are_real_and_deterministic():
    pytest.importorskip('torch')
    from iatonoesis.ontology_factorial import graph_ranker, prepare, compare, fallback_receipt
    a=nodes([(2,1),(3,1),(4,2)])
    q=[{'child':'2','gold':['3']},{'child':'6','gold':[]}]
    vectors={v['name']:[int(k),1.] for k,v in a.items()}
    prepared=prepare(a,q,vectors,'held'); rows=prepared['LSG:32']
    models,scores=compare(prepared,a)
    assert set(scores)=={'hybrid_rule','linear','neural','no_graph','semantic','gnn','gnn_zero'}
    assert scores['gnn']!=scores['gnn_zero']
    transfer,s2=compare(prepared,a,models)
    assert s2==scores and transfer==models
    assert fallback_receipt(rows,scores,rows,s2,'gnn')['threshold'] is None
    with pytest.raises(ValueError): graph_ranker(a,[dict(rows[0],gold=[])])


def test_bad_parse_and_source(tmp_path):
    from iatonoesis.ontology_factorial import parse, acquire, SOURCES
    p=tmp_path/'x'; header='data-version: releases/2026-09-01\n'
    for stanza in ('','\n[Term]\nid: HP:0000001\n','\n[Term]\nid: HP:0000001\nname: root\nis_a: HP:0000001\n','\n[Term]\nid: HP:0000001\nname: root\n\n[Term]\nid: HP:0000001\nname: duplicate\n'):
        p.write_text(header+stanza)
        with pytest.raises(ValueError): parse(p,'2026-09-01','HP')


def test_pinned_acquisition_and_cli(tmp_path, monkeypatch):
    import hashlib, io, json, sys
    from iatonoesis import ontology_factorial as m
    raw=b'data-version: releases/2026-01-01\n\n[Term]\nid: HP:0000001\nname: root\n'
    monkeypatch.setattr(m,'SOURCES',{'HP':('publisher/source','hp.obo',{'2026-01-01':(len(raw),hashlib.sha256(raw).hexdigest())})})
    monkeypatch.setattr(m.urllib.request,'urlopen',lambda url,timeout:io.BytesIO(raw))
    s,r=m.acquire('HP',tmp_path)
    assert len(s)==1 and r['2026-01-01']['bytes']==len(raw)
    monkeypatch.setattr(m.urllib.request,'urlopen',lambda url,timeout:io.BytesIO(raw+b'x'))
    with pytest.raises(ValueError,match='oversized'): m.acquire('HP',tmp_path)
    dest=tmp_path/'out.json'; monkeypatch.setattr(sys,'argv',['run','--output',str(dest)])
    monkeypatch.setattr(m,'run',lambda root: {'scope':'fixture'})
    m.main(); assert json.loads(dest.read_text())=={'scope':'fixture'}
    def fail(root): raise ValueError('fixture')
    monkeypatch.setattr(m,'run',fail)
    with pytest.raises(ValueError): m.main()
    assert json.loads(dest.read_text())['status']=='failed'


def test_cross_ontology_run_preserves_transfer(monkeypatch,tmp_path):
    pytest.importorskip('numpy'); pytest.importorskip('torch')
    from iatonoesis import ontology_factorial as m
    snapshots=[nodes([(2,1),(3,1),(4,2)]+extra) for extra in [[],[(2,3)],[(2,3),(5,3)],[(2,3),(5,3),(6,7)]]]
    monkeypatch.setattr(m,'load_encoder',lambda root: (lambda names:{k:[1.,float(k.split()[-1])] for k in names},{'fixture':True}))
    monkeypatch.setattr(m,'acquire',lambda prefix,root:(snapshots if prefix=='MONDO' else snapshots[1:],{'fixture':True}))
    out=m.run(tmp_path)
    assert set(out['results'])=={'MONDO','HP'} and 'development' not in out['results']['HP']['partitions']
    assert len(out['model_hashes'])==5
    assert all(a['fallback']['threshold'] is None for r in out['results'].values() for a in r['arms'].values())


def test_source_timeout_retries_are_bounded(tmp_path,monkeypatch):
    import hashlib,io,urllib.error
    from iatonoesis import ontology_factorial as m
    raw=b'data-version: releases/2026-01-01\n\n[Term]\nid: HP:0000001\nname: root\n'
    monkeypatch.setattr(m,'SOURCES',{'HP':('publisher/source','hp.obo',{'2026-01-01':(len(raw),hashlib.sha256(raw).hexdigest())})})
    monkeypatch.setattr(m.time,'sleep',lambda _:None)
    calls=[]
    def flaky(url,timeout):
        calls.append(url)
        if len(calls)<3: raise urllib.error.URLError(TimeoutError('temporary'))
        return io.BytesIO(raw)
    monkeypatch.setattr(m.urllib.request,'urlopen',flaky)
    assert m.acquire('HP',tmp_path)[1]['2026-01-01']['bytes']==len(raw)
    assert len(calls)==3
    calls.clear()
    def offline(url,timeout):
        calls.append(url);raise TimeoutError('unavailable')
    monkeypatch.setattr(m.urllib.request,'urlopen',offline)
    with pytest.raises(TimeoutError): m.acquire('HP',tmp_path)
    assert len(calls)==3
    calls.clear()
    def corrupt(url,timeout):
        calls.append(url);return io.BytesIO(b'x'*len(raw))
    monkeypatch.setattr(m.urllib.request,'urlopen',corrupt)
    with pytest.raises(ValueError): m.acquire('HP',tmp_path)
    assert len(calls)==1
