"""Same-state replacement and real controller authorization regressions."""
import numpy as np
import pytest
from spatial_memory.attenuated_dao_veto_v1 import AttenuatedDAOVeto,estimate_rule
from spatial_memory.dao_navigation_compat_v1_1 import DAONavigationCompatV1_1
from spatial_memory.discovery_observation import DAOParameters,request_rule

def test_only_discovery_term_changes():
    p=DAOParameters()
    detail={'age_scores':{'5':.5},'oldest_local_age':5,
            'frontier':{'new':1,'stale':0,'known':10,'stale_fraction':0.,'route_new':0}}
    assert not request_rule(detail,5,5,'dao_veto',p)['requested']
    assert estimate_rule(detail,5.,5,5,p)['requested']
    assert detail['frontier']['new']==1
    detail['age_scores']['5']=0.
    assert not estimate_rule(detail,20.,5,5,p)['requested']
    detail['oldest_local_age']=10
    assert estimate_rule(detail,0.,10,10,p)['requested']

def test_q0_exact_authorization_and_memory_parity():
    initial=np.full((15,15),-1,np.int8);initial[6:9,6:9]=0
    a=DAONavigationCompatV1_1(initial,mode='dao_veto',max_observations=3)
    b=AttenuatedDAOVeto(initial,factor=0.,max_observations=3)
    for t in range(1,21):
        for c in (a,b):c.set_navigation_context(goal=(12,7),yaw=0.)
        x=a.decide(t,(7,7));y=b.decide(t,(7,7));assert x==y
        if x['observation_granted']:
            for c in (a,b):c.refresh(initial,t)
        assert a.used==b.used and np.array_equal(a.memory.grid,b.memory.grid)
        assert np.array_equal(a.last_observed,b.last_observed)
    assert a.used==b.used==3

@pytest.mark.parametrize('q',[.5,.8,1.])
def test_cap_authorized_empty_reading_and_fresh_context(q):
    initial=np.zeros((15,15),np.int8)
    c=AttenuatedDAOVeto(initial,factor=q,max_observations=2)
    with pytest.raises(RuntimeError):c.decide(1,(7,7))
    grant=None
    for t in range(1,12):
        c.set_navigation_context(goal=(12,7),yaw=0.)
        d=c.decide(t,(7,7))
        if d['observation_granted']:
            grant=t;break
    assert grant is not None
    c.refresh(np.full_like(initial,-1),grant)
    assert c.used==2 and c.last_scan_step==grant
    assert not c.memory.grid.any() and not c.last_observed.any()
    c.set_navigation_context(goal=(12,7),yaw=0.)
    assert not c.decide(grant+10,(7,7))['observation_granted']
    with pytest.raises(RuntimeError):c.refresh(initial,grant+10)
