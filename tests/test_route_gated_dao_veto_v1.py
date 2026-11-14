"""Pure mechanism isolation and public controller invariants."""
from itertools import product
import numpy as np
import pytest
from spatial_memory.discovery_observation import DAOParameters,request_rule
from spatial_memory.route_gated_dao_veto_v1 import gated_rule,RouteGatedDAOVeto
P=DAOParameters()
def detail(*,route=True,new=8,route_new=0,stale=0,age=.6,oldest=6):
    return {'route_available':route,'age_scores':{'5':age},'oldest_local_age':oldest,
        'frontier':{'new':new,'route_new':route_new,'stale':stale,
        'known':10,'stale_fraction':stale/10}}

def test_route_only_filters_discovery_not_verification():
    d=detail()
    assert request_rule(d,6,4,'dao_veto',P)['requested']
    assert not gated_rule(d,6,4,'route',P)['requested']
    assert gated_rule(detail(route_new=1),6,4,'route',P)['requested']
    assert gated_rule(detail(stale=3),6,4,'route',P)['requested']

def test_invisible_old_cell_fallback_can_be_deferred_but_not_indefinitely_by_gap():
    d=detail(new=0,age=.1,oldest=10)
    assert request_rule(d,12,4,'dao_veto',P)['requested']
    assert not gated_rule(d,12,4,'deadline',P)['requested']
    assert gated_rule(d,12,10,'deadline',P)['requested']
    assert gated_rule(detail(new=0,age=.1,oldest=10,stale=1),12,4,'deadline',P)['requested']
    assert not gated_rule(detail(new=0,age=.1,oldest=9),12,10,'deadline',P)['requested']

def test_no_route_preserves_original():
    for mode in ('route','deadline','joint'):
        for new,stale,oldest,gap,age in product((0,5),(0,3),(5,12),(3,10),(.3,.5)):
            d=detail(route=False,new=new,stale=stale,oldest=oldest,age=age)
            assert gated_rule(d,12,gap,mode,P)['requested']==request_rule(d,12,gap,'dao_veto',P)['requested']

def test_same_state_subset_and_joint_intersection():
    for route,new,rnew,stale,age,oldest,gap in product((False,True),(0,5),(0,1),(0,1,3),(.3,.5),(5,12),(3,10)):
        d=detail(route=route,new=new,route_new=rnew,stale=stale,age=age,oldest=oldest)
        original=request_rule(d,12,gap,'dao_veto',P)['requested']
        a,b,c=[gated_rule(d,12,gap,m,P)['requested'] for m in ('route','deadline','joint')]
        assert not a or original
        assert not b or original
        assert not c or (a and b)
        # The joint need not equal a AND b: different terms can protect each separate arm.

@pytest.mark.parametrize('mode',('route','deadline','joint'))
def test_controller_authorized_refresh_and_cap(mode):
    g=np.zeros((15,15),np.int8);g[0,:]=g[-1,:]=g[:,0]=g[:,-1]=1
    c=RouteGatedDAOVeto(g,gate_mode=mode,max_observations=2)
    with pytest.raises(RuntimeError):c.decide(1,(7,7))
    for step in range(1,12):
        c.set_navigation_context(goal=(12,7),yaw=0.)
        if c.decide(step,(7,7))['observation_granted']:
            c.refresh(np.full_like(g,-1),step);break
    assert c.used==2 and np.array_equal(c.memory.grid,g)
    assert not c.last_observed.any()
    c.set_navigation_context(goal=(12,7),yaw=0.)
    assert not c.decide(20,(7,7))['observation_granted']
    with pytest.raises(RuntimeError):c.refresh(g,20)
