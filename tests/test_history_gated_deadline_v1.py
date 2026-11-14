"""Correctness checks on bounded history veto and original grant accounting."""
import numpy as np
import pytest
from spatial_memory.history_gated_deadline_v1 import HistoryGatedDeadline,MODES
from spatial_memory.route_gated_dao_veto_v1 import RouteGatedDAOVeto

@pytest.mark.parametrize('mode',tuple(MODES))
def test_first_scan_protection_veto_and_deadline(mode):
    g=np.zeros((15,15),np.int8)
    c=HistoryGatedDeadline(g,history_mode=mode,max_observations=3)
    grants=[]
    for t in range(1,26):
        c.set_navigation_context(goal=(12,7),yaw=0.)
        ans=c.decide(t,(7,7))
        if ans['observation_granted']:
            grants.append(t);c.refresh(g,t)
        assert c.history.readings==c.used
    assert grants==[5,15]
    assert any(x['history_veto'] for x in c.decisions)
    assert c.used==3 and c.history.last_step==15
    assert c.requests>=len(grants) and c.denied==c.requests-len(grants)
    assert np.array_equal(c.memory.grid,c.history.grid)
    assert np.array_equal(c.last_observed,c.history.last)
    with pytest.raises(RuntimeError):c.refresh(g,25)

@pytest.mark.parametrize('mode',tuple(MODES))
def test_first_noninitial_matches_frozen_deadline(mode):
    g=np.full((15,15),-1,np.int8);g[6:9,6:9]=0
    a=RouteGatedDAOVeto(g,gate_mode='deadline');b=HistoryGatedDeadline(g,history_mode=mode)
    for t in range(1,20):
        for c in (a,b):c.set_navigation_context(goal=(12,7),yaw=0.)
        x=a.decide(t,(7,7));y=b.decide(t,(7,7))
        assert x==y
        if x['observation_granted']:
            a.refresh(g,t);b.refresh(g,t);break
    else:pytest.fail('Missing first grant')
    assert a.used==b.used==2
