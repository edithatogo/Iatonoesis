import pytest

from iatonoesis.external_ner import (parse_pubtator, split_sources, dictionary, lexicon,
                                    span_metrics, matched_budget, fallback, bio_spans)


def doc(i, text, spans):
    return dict(id=str(i), text=text, spans=spans)


def test_pubtator_preserves_exact_offsets_and_ignores_relations():
    raw = '1|t|A cold\n1|a|Cold.\n1\t2\t6\tcold\tDisease\tD1\n1\t7\t11\tCold\tDisease\tD1\n1\tCID\tC1\tD1\n'
    assert parse_pubtator(raw, {'Disease'}) == [doc(1, 'A cold Cold.', [[2, 6], [7, 11]])]
    with pytest.raises(ValueError, match='offset'):
        parse_pubtator(raw.replace('2\t6\tcold', '3\t6\tcold'), {'Disease'})


def test_cross_source_groups_and_duplicates_are_not_reused():
    a = doc(1, 'A cold', [[2, 6]])
    b = doc(2, 'Other', [])
    c = doc(3, 'A COLD', [[2, 6]])
    d = doc(4, 'External', [])
    p, counts = split_sources({'development': [a, a], 'calibration': [b], 'test': [c], 'external': [a, d]})
    assert p['development'] == [] and p['test'] == [c] and p['external'] == [d]
    assert counts['development'] == 2 and counts['external'] == 1


def test_lexicon_exact_longest_and_boundaries():
    vocab = dictionary([doc(1, 'cold', [[0, 4]]), doc(2, 'common cold', [[0, 11]])])
    assert lexicon('Common cold, colder, cold.', vocab)[0] == [[0, 11], [21, 25]]


def test_bio_decoding_and_span_metrics():
    assert bio_spans([(0, 3), (4, 7), (8, 9)], [2, 2, 0]) == [[0, 7]]
    rows = [doc(1, 'abc', [[0, 3]]), doc(2, 'none', [])]
    pred = {'1': ([[0, 3]], .8), '2': ([], .4)}
    assert span_metrics(rows, pred)['f1'] == 1
    m = matched_budget(rows, pred, 1)
    assert m['review'] == 1 and m['retained'] == 1 and m['exact'] == 1
    assert m['coverage'] == .5


def test_fallback_insufficient_calibration_and_no_false_clearance():
    r = {'1': ([], 0.), '2': ([[0, 1]], .9)}
    p = {'1': ([[0, 3]], .99), '2': ([], .99)}
    assert fallback(r, p, None) == r
    assert fallback(r, p, .9)['1'][0] == [[0, 3]]
    assert fallback(r, p, .9)['2'] == r['2']
