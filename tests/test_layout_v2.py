from iatonoesis.layout_v2_fixture import generate
from iatonoesis.layout_v2 import bidirectional, image_pdf, tsv_words, validate_frozen_fixture


def word(text, x, y, width=20):
    return dict(text=text, x0=x, x1=x+width, y0=y, y1=y+10)


def test_symmetric_left_and_right():
    req = word('REQ-A', 100, 10, 40)
    note = word('*01:EXCEPTION-ABCD', 10, 100)
    for marker in (word('*01', 50, 10), word('*01', 170, 10)):
        assert bidirectional([req, marker, note]) == {('A', 'EXCEPTION-ABCD')}


def test_ambiguous_nearest_abstains():
    words = [word('REQ-A', 10, 10), word('REQ-B', 80, 10), word('*01', 45, 10),
             word('*01:EXCEPTION-ABCD', 10, 100)]
    assert bidirectional(words) == set()


def test_repeated_notes_and_double_assignment_not_inferred():
    req = word('REQ-A', 100, 10, 40)
    marks = [word('*01', 50, 10), word('*02', 170, 10)]
    notes = [word('*01:EXCEPTION-ABCD', 10, 100), word('*02:EXCEPTION-EFGH', 10, 120)]
    assert bidirectional([req] + marks + notes) == set()
    assert bidirectional([req, marks[0], notes[0], word('*01:EXCEPTION-CONFLICT', 10, 140)]) == set()


def test_frozen_reference_and_family_disjointness():
    docs = generate()
    validate_frozen_fixture(docs)
    assert len(docs) == 56
    assert len({d['id'] for d in docs if d['split'] == 'test'}) == 40
    assert {d['family'] for d in docs if d['split'] == 'test'}.isdisjoint(
        {d['family'] for d in docs if d['split'] != 'test'})


def test_changed_reference_rejected():
    import pytest
    docs = generate()
    docs[0]['gold'].pop()
    with pytest.raises(ValueError, match='frozen'):
        validate_frozen_fixture(docs)


def test_ocr_word_box_scaling():
    table = 'level\tleft\ttop\twidth\theight\ttext\n5\t100\t200\t50\t20\tREQ-A\n4\t0\t0\t1\t1\t\n'
    assert tsv_words(table, 2, 2) == [word('REQ-A', 50, 100, 25)]


def test_image_pdf_has_no_font_or_text_operator():
    pdf = image_pdf(2, 2, bytes([0, 255, 255, 0]))
    assert pdf.startswith(b'%PDF-1.4')
    assert b'/Subtype /Image' in pdf
    assert b'/Font' not in pdf
