import copy
import pytest
from iatonoesis.core_suite import freeze, run_suite, fit_nb, predict_nb
from iatonoesis.run_contracts import canonical_sha256, validate_result

COMMIT = 'a' * 40


def test_frozen_inputs_and_disjoint_groups():
    f = freeze(17, COMMIT)
    assert len(f) == 8
    assert f == freeze(17, COMMIT)
    for _, (data, exp, inputs, refs) in f.items():
        assert data['sha256'] == canonical_sha256(inputs)
        assert data['reference']['sha256'] == canonical_sha256(refs)
        assert len(exp['case_ids']) > 0
        assert set(exp['case_ids']) == {r['id'] for r in data['rows'] if r['split'] == 'test'}
        groups = {}
        for row in data['rows']:
            family = row['groups']['family']
            assert groups.setdefault(family, row['split']) == row['split']


def test_training_learns_signal_and_does_not_depend_on_order():
    rows = [(('word:yes',), 'yes'), (('word:no',), 'no')]
    a = fit_nb(rows)
    assert a == fit_nb(rows[::-1])
    assert predict_nb(a, ('word:yes',)) == 'yes'
    assert predict_nb(a, ('word:no',)) == 'no'


def test_migration_and_all_challengers_execute():
    frozen = freeze(17, COMMIT)
    result = run_suite(frozen, COMMIT)
    assert set(result) == set(frozen)
    for key, item in result.items():
        data, exp, inputs, refs = frozen[key]
        validate_result(item['manifest'], exp, data)
        arms = {a['id']: a for a in item['manifest']['arms']}
        assert all(a['status'] == 'executed' for a in arms.values())
        assert arms['learned']['model']['training_split'] == 'development'
        assert arms['learned']['model']['training_cases'] == sum(r['split'] == 'development' for r in data['rows'])
        assert all(r['id'] in exp['case_ids'] for rows in item['predictions'].values() for r in rows)
        assert arms['learned']['metrics']['total'] == len(exp['case_ids'])
        assert 'paired_f1' in item
    assert result['E02']['manifest']['arms'][0]['metrics']['tp'] == 188
    assert result['E04']['manifest']['arms'][0]['metrics']['abstained'] == 28
    assert result['E22']['manifest']['arms'][0]['metrics']['exact'] == 69


def test_frozen_holdout_mutation_rejected_before_fit():
    f = freeze(17, COMMIT)
    data, exp, inputs, refs = f['E04']
    refs[exp['case_ids'][0]] = ['tamper']
    with pytest.raises(ValueError, match='frozen reference'):
        run_suite(f, COMMIT)
