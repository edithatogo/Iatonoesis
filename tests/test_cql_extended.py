import pytest
from iatonoesis import cql_extended as c


def xml(inner):
    return ('<tests xmlns="http://hl7.org/fhirpath/tests" name="Fixture"><group name="A">'+inner+'</group></tests>').encode()


def test_literal_reference_and_explicit_unsupported():
    raw=xml('<test name="a"><expression>1 &lt; 2</expression><output>true</output></test>'
            '<test name="b"><expression>null as Boolean</expression><output>null</output></test>'
            '<test name="c"><expression>1</expression><output>1.0</output></test>'
            '<test name="d"><expression invalid="true">invalid</expression></test>'
            '<test name="e"><expression>1L = 1L</expression><output>true</output></test>')
    rows=c.parse_suite(raw,'cmp')
    assert rows[0]['expression']=='1 < 2' and rows[0]['expected'] is True
    assert rows[1]['expected'] is None and rows[1]['status']=='eligible'
    assert [r['status'] for r in rows[2:]]==['unsupported_reference_type','declared_invalid','unsupported_long']
    with pytest.raises(ValueError,match='duplicate'):
        c.parse_suite(xml('<test name="x"/><test name="x"/>'),'cmp')


def test_mutations_and_prompt_freeze_are_balanced():
    rows,groups=c.mutations()
    assert len(rows)==72 and len(groups)==6
    assert all(len(g['cases'])==3 for g in groups)
    cases=[dict(id=f'{label}-{i}',expression='true',expected=value,status='eligible')
           for label,value in [('t',True),('f',False),('n',None)] for i in range(10)]
    sample=c.prompt_sample(cases)
    assert len(sample)==24
    assert c.prompt_sample(list(reversed(cases)))==sample
    assert c.prompt_sample(cases[:10])==[]
    for f in c.FRAMES:
        assert 'ABSTAIN' in c.prompt(f,'1 = 1')
    assert c.parse_answer(' NULL ')=='NULL'
    assert c.parse_answer('true')=='INVALID'
    assert c.parse_answer('TRUE because')=='INVALID'


def test_score_separates_wrong_abstention_and_null():
    refs=[{'id':'a','expected':True},{'id':'b','expected':False},{'id':'c','expected':None},{'id':'d','expected':False}]
    out=c.score(refs,{'a':'TRUE','b':'ABSTAIN','c':'TRUE','d':'INVALID'})
    assert out['correct']==1 and out['decided']==2 and out['false_true']==1
    assert out['abstentions']==1 and out['invalid']==1
    with pytest.raises(ValueError,match='membership'):
        c.score(refs,{'a':'TRUE'})


def test_additional_reference_gate_states_and_integer_oracle():
    raw=xml('<test name="a"><expression>Today() = Today()</expression><output>true</output></test>'
            '<test name="b"><expression>1</expression></test>'
            '<test name="c"><expression>1</expression><output>9007199254740992</output></test>'
            '<test name="d"><expression>1+2</expression><output>3</output></test>')
    rows=c.parse_suite(raw,'additional')
    assert [r['status'] for r in rows]==['clock_dependent','missing_reference','unsupported_reference_type','eligible']
    assert type(rows[-1]['expected']) is int and rows[-1]['expected']==3
    with pytest.raises(ValueError,match='XML declaration'):
        c.parse_suite(b'<!DOCTYPE x><x/>','invalid')
    with pytest.raises(ValueError,match='empty'):
        c.parse_suite(xml(''),'empty')
    with pytest.raises(ValueError,match='non-Boolean'):
        c.label(1)
    assert c.git_blob(b'hello\\n')!=c.git_blob(b'hello')
