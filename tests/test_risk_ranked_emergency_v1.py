"""Public synthetic risk-ranked safety controls, no simulator queries."""
from types import SimpleNamespace
import numpy as np
import pytest
from spatial_memory.risk_ranked_emergency_v1 import RESH1,RESRisk,RESFull,RiskRankedEmergencySafety
from spatial_memory.predictive_emergency_v1 import PredictiveEmergencySafetyV1

def scene():return SimpleNamespace(scenario=SimpleNamespace(width=17,height=17),cell_size=.75,footprint_half_extents_local=(.219,.328))
def measurement(t,cells=(),grid=None):
    return {'grid':np.zeros((17,17),np.int8) if grid is None else grid,
            'visible_pedestrian_cells':cells,'motion_estimate':{'state':'measured_motion','velocity_cells_per_step':[0.,-1.]},'record':{'step':t}}

def choose(c,t=1,pos=(7,8),action=('sidestep',(7,7)),cells=((8,8),),grid=None):
    r=c.choose(None,pos,(13,8),0.,action,measurement(t,cells,grid),t)
    return (r['action'] if r else action),c.diagnostics[-1]

def test_horizon_isolation():
    a,d=choose(RESH1(scene()))
    assert a==('sidestep',(7,7))
    assert d['selected_assessment']['certified']
    assert not d['selected_assessment']['one_transition_risk']
    assert d['selected_assessment']['two_transition_risk']
    _,d=choose(RESRisk(scene()))
    assert not d['selected_assessment']['certified']

def test_reversal_remains_in_h1():
    _,d=choose(RESH1(scene()),pos=(7,8),action=('move',(8,8)),cells=((8,7),))
    assert d['selected_assessment']['one_transition_risk']
    assert (8,8) in d['one_transition_reachable']

def test_risk_rank_escape_from_existing_overlap_is_uncertified():
    a,d=choose(RESFull(scene()),pos=(7,8),action=('wait','base'),cells=((7,8),))
    assert d['no_certifiably_safe_action'] and d['uncertified_selection']
    assert a[0] in ('move','sidestep','retreat')
    selected=next(x for x in d['alternatives'] if x['action']==a)
    assert selected['exits_existing_measured_overlap']
    assert not selected['certified']

def test_unknown_static_clearance_not_overridden():
    grid=np.full((17,17),-1,np.int8)
    a,d=choose(RESRisk(scene()),pos=(7,8),action=('wait','base'),cells=((7,8),),grid=grid)
    assert a[0]=='wait' and d['no_admissible_fallback'] and d['uncertified_selection']

def test_measured_sweep_risk_never_new_fallback():
    a,d=choose(RESRisk(scene()),pos=(7,8),action=('move',(8,8)),cells=((8,8),))
    assert not d['selected_assessment']['fallback_admissible']
    assert a!=('move',(8,8))

@pytest.mark.parametrize('cls',(RESH1,RESRisk,RESFull))
def test_negative_control(cls):
    c=cls(scene())
    a,d=choose(c,cells=())
    assert a==('sidestep',(7,7)) and not d['had_observed_tracks']
    with pytest.raises(ValueError):choose(c,cells=())

def test_default_h2_wait_action_parity():
    old=PredictiveEmergencySafetyV1(scene());new=RiskRankedEmergencySafety(scene())
    for t,cells in enumerate([((8,8),),((8,7),),(),((8,8),),()],1):
        a,_=choose(old,t=t,cells=cells);b,_=choose(new,t=t,cells=cells)
        assert a==b

def test_fallback_order_matches_explicit_lexicographic_reference():
    c=RESRisk(scene())
    # Search deterministic synthetic cases, not navigation outcomes.
    saw=False
    for x in range(5,10):
        for y in range(6,11):
            c=RESRisk(scene())
            a,d=choose(c,cells=((x,y),))
            if d['reason']!='uncertified_risk_ranked_action':continue
            eligible=[(i,v) for i,v in enumerate(d['alternatives']) if v.get('fallback_admissible')]
            expected=min(eligible,key=lambda iv:(tuple(iv[1]['risk_key']),
                abs(iv[1]['end'][0]-13)+abs(iv[1]['end'][1]-8),iv[0]))[1]['action']
            assert a==expected
            saw=True
    assert saw
