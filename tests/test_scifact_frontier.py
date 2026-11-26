import pytest
from iatonoesis.scifact_frontier import frontier, audit


def row(i, label, pred, conf):
    return dict(id=str(i), label=label, predictions={'m':[pred,conf]})


def test_tied_scores_cannot_be_split_and_minimum_is_enforced():
    rows=[row(1,'SUPPORT','SUPPORT',.9),row(2,'NO_EVIDENCE','SUPPORT',.9),row(3,'NO_EVIDENCE','NO_EVIDENCE',.8)]
    assert frontier(rows,'m',max_error=.2,min_retained=1,min_negative=0,max_false_support=1)['status']=='no_feasible_prefix'
    assert frontier(rows,'m',max_error=.4,min_retained=3,min_negative=1,max_false_support=.5)['retained']==3


def test_joint_safety_gate_and_invalid_predictions():
    rows=[row(1,'NO_EVIDENCE','NO_EVIDENCE',.95),row(2,'SUPPORT','SUPPORT',.8),row(3,'CONTRADICT','SUPPORT',.6)]
    got=frontier(rows,'m',max_error=.5,min_retained=1,min_negative=1,max_false_support=0)
    assert got['retained']==2 and got['review']==1 and got['false_support']==0
    with pytest.raises(ValueError,match='prediction'):
        frontier([row(1,'SUPPORT','invalid',.9)],'m',max_error=.2,min_retained=1,min_negative=0,max_false_support=1)


def test_bad_source_is_rejected(tmp_path):
    p=tmp_path/'bad.zip'; p.write_bytes(b'wrong')
    with pytest.raises(ValueError,match='artifact'):
        audit(p)
