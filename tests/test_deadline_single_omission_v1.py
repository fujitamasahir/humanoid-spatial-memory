"""Single omission preserves the real authorization boundary."""
import numpy as np
import pytest
from spatial_memory.deadline_single_omission_v1 import DeadlineSingleOmission
from spatial_memory.route_gated_dao_veto_v1 import RouteGatedDAOVeto
def test_one_omission_then_normal_decisions():
    g=np.zeros((15,15),np.int8);g[0,:]=g[-1,:]=g[:,0]=g[:,-1]=1
    a=RouteGatedDAOVeto(g,gate_mode='deadline',max_observations=3)
    for t in range(1,16):
        a.set_navigation_context(goal=(12,7),yaw=0.)
        if a.decide(t,(7,7))['observation_granted']:break
    else:pytest.fail('No baseline grant')
    b=DeadlineSingleOmission(g,omit_step=t,max_observations=3)
    for k in range(1,t+1):
        b.set_navigation_context(goal=(12,7),yaw=0.)
        answer=b.decide(k,(7,7))
        assert not answer['observation_granted']
    assert b.omissions==1 and b.used==1 and b.last_scan_step==0
    assert b.requests==0 and b.denied==0 and np.array_equal(b.memory.grid,g)
    assert not b.last_observed.any()
    with pytest.raises(RuntimeError):b.refresh(g,t)
    b.set_navigation_context(goal=(12,7),yaw=0.)
    assert b.decide(t+1,(7,7))['observation_granted']
    b.refresh(g,t+1)
    assert b.used==2 and b.omissions==1 and b.last_scan_step==t+1

def test_wrong_target_is_not_silently_accepted():
    g=np.zeros((15,15),np.int8)
    c=DeadlineSingleOmission(g,omit_step=1)
    c.set_navigation_context(goal=(12,7),yaw=0.)
    with pytest.raises(RuntimeError,match='matching granted'):c.decide(1,(7,7))

def test_initial_scan_cannot_be_omitted():
    with pytest.raises(ValueError):DeadlineSingleOmission(np.zeros((15,15),np.int8),omit_step=0)
