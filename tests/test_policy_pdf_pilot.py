from iatonoesis.policy_pdf_pilot import (
    families, generate, render, parse_bbox, flat, spatial, score, summarize,
)


def word(text, x, y, width=20):
    return dict(text=text, x0=x, x1=x+width, y0=y, y1=y+10)


def test_detached_marker_binding_uses_spatial_relationship():
    words = [word('REQ-A', 10, 10), word('REQ-B', 100, 10),
             word('*01', 40, 10), word('*01:EXCEPTION-A', 10, 100)]
    assert flat(words) == {('B', 'EXCEPTION-A')}
    assert spatial(words) == {('A', 'EXCEPTION-A')}


def test_missing_and_conflicting_qualifiers_abstain():
    words = [word('REQ-A', 10, 10), word('*01', 40, 10),
             word('*01:EXCEPTION-A', 10, 100), word('*01:EXCEPTION-B', 10, 120)]
    assert spatial(words) == set()
    assert flat(words) == set()
    assert score(set(), {('A', 'EXCEPTION-A')}) == dict(tp=0, fp=0, fn=1)


def test_equal_distance_is_not_silently_resolved():
    words = [word('REQ-A', 10, 10), word('REQ-B', 10, 10),
             word('*01', 40, 10), word('*01:EXCEPTION-A', 10, 100)]
    assert spatial(words) == set()


def test_families_disjoint_and_generation_reproducible():
    docs = generate(17)
    assert docs == generate(17)
    assert len(docs) == 140
    assert len({doc['id'] for doc in docs}) == len(docs)
    by_split = {split: {d['family'] for d in docs if d['split'] == split}
                for split in ('development', 'calibration', 'test')}
    assert len(by_split['test']) == 5
    assert sum(map(len, by_split.values())) == len(families)
    assert not (by_split['test'] & (by_split['development'] | by_split['calibration']))
    assert all(len(d['gold']) == 6 for d in docs)
    assert all(set(token) == {'text', 'x', 'y', 'size'} for d in docs for token in d['tokens'])
    assert render(docs[0]['tokens']) == render(docs[0]['tokens'])
    assert render(docs[0]['tokens']).startswith(b'%PDF-1.4')


def test_parse_poppler_bbox_xml():
    xml = b'''<html xmlns="http://www.w3.org/1999/xhtml"><body><doc><page width="612" height="792"><word xMin="10" yMin="12" xMax="30" yMax="22">REQ-A</word></page></doc></body></html>'''
    assert parse_bbox(xml) == [dict(text='REQ-A', x0=10., y0=12., x1=30., y1=22.)]


def test_summary_preserves_unrecoverable_labels():
    assert summarize([dict(counts=dict(tp=5, fp=0, fn=1))]) == dict(tp=5, fp=0, fn=1,
                    f1=10/11, exact_documents=0, documents=1)
