import pytest
from iatonoesis import action_design as a


def test_action_mechanism_and_oracle():
    assert a.next_backlog(2,5,3,2)==2
    assert a.next_backlog(0,1,3,4)==0
    d=[0.]*9;d[5]=1
    assert a.expected(2,3,2,d)==2
    assert a.expected(2,3,4,d)==0


def test_posterior_and_exact_policy():
    prior=(.5,.3,.2);probs=((.9,.1,.1),(.1,.8,.2),(.4,.4,.4),(.2,.2,.9));cost=(1,1,2,2)
    env=(prior,probs,cost)
    q,p=a.update(prior,probs[0],1)
    assert q==pytest.approx(.5*.9+.3*.1+.2*.1) and sum(p)==pytest.approx(1)
    best=a.policy_value(env,'exact',None);greedy=a.policy_value(env,'greedy',None)
    assert best[2]<=greedy[2]+1e-12 and best[1]<=3
    assert a.policy_value(env,'stop',None)[0]==pytest.approx(.5)


def test_frozen_design_and_simulation_determinism():
    r=a.run();assert r==a.run()
    assert r['queue']['test_environments']==6 and r['design']['test_environments']==6
    assert r['design']['arms']['exact']['regret']==pytest.approx(0)
    assert all(v['regret']>=-1e-10 for v in r['design']['arms'].values())
