"""Public-state phase alignment and inherited-certificate regression tests."""
from types import SimpleNamespace
import numpy as np
from spatial_memory.res_phase_wait_v1 import RESH1PhaseWait
from spatial_memory.risk_ranked_emergency_v1 import RESH1

def scene():return SimpleNamespace(scenario=SimpleNamespace(width=17,height=17),cell_size=.75,footprint_half_extents_local=(.219,.328))
def call(c,t,yaw,a,*,p=(5,8),cells=((7,8),),grid=None):
    m={'grid':np.zeros((17,17),np.int8) if grid is None else grid,
       'visible_pedestrian_cells':cells,'motion_estimate':{'state':'measured_motion','velocity_cells_per_step':[0.,1.]},
       'record':{'step':t}}
    result=c.choose(None,p,(13,8),yaw,a,m,t)
    return result['action'] if result else a

def cycle(c):
    assert call(c,1,0.,('move',(6,8)))==('turn',1)
    assert call(c,2,np.pi/2,('turn',0),cells=((7,7),))==('turn',0)
    return call(c,3,0.,('move',(6,8)))

def test_phase_wait_uses_existing_certified_alternative_and_enables_next_forward():
    c=RESH1PhaseWait(scene())
    assert cycle(c)[0]=='wait'
    d=c.diagnostics[-1]
    assert d['phase_wait_applied'] and d['rotation_cycle']
    assert d['phase_wait_certificate']['certified']
    assert not d['no_certifiably_safe_action']
    assert call(c,4,0.,('move',(6,8)),cells=((7,9),))==('move',(6,8))
    call(c,5,0.,('move',(7,8)),p=(6,8),cells=((7,9),))
    assert not c.diagnostics[-1]['phase_wait_used_before']

def test_at_most_one_wait_per_stationary_dwell():
    c=RESH1PhaseWait(scene())
    assert cycle(c)[0]=='wait'
    assert call(c,4,0.,('move',(6,8)))==('turn',1)
    assert not c.diagnostics[-1]['phase_wait_applied']
    assert c.diagnostics[-1]['phase_wait_used_before']

def test_planned_certified_turn_does_not_trigger():
    c=RESH1PhaseWait(scene())
    call(c,1,0.,('turn',1));call(c,2,np.pi/2,('turn',0),cells=((7,7),))
    assert call(c,3,0.,('turn',1))==('turn',1)
    assert not c.diagnostics[-1]['phase_wait_applied']

def test_no_tracks_and_no_cycle_match_h1():
    a=RESH1PhaseWait(scene());b=RESH1(scene())
    for t,yaw,action in [(1,0.,('turn',1)),(2,np.pi/2,('turn',0)),(3,0.,('move',(6,8)))]:
        assert call(a,t,yaw,action,cells=())==call(b,t,yaw,action,cells=())
        assert not a.diagnostics[-1]['phase_wait_applied']

def test_uncertified_state_retains_h1_behavior():
    c=RESH1PhaseWait(scene());cycle(c)
    out=call(c,4,0.,('move',(6,8)),cells=((5,8),),grid=np.full((17,17),-1,np.int8))
    assert c.diagnostics[-1]['no_certifiably_safe_action']
    assert not c.diagnostics[-1]['phase_wait_applied'] and out[0]=='wait'

def test_initial_attempt_does_not_disrupt_ordinary_h1():
    c=RESH1PhaseWait(scene());h=RESH1(scene())
    assert call(c,1,0.,('move',(6,8)))==call(h,1,0.,('move',(6,8)))
    assert not c.diagnostics[-1]['phase_wait_applied']
