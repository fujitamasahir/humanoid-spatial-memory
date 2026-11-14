"""Cycle-escape mechanism fixtures and certificate parity."""
from types import SimpleNamespace
import numpy as np
import pytest
from spatial_memory.res_cycle_escape_v1 import RESH1CycleEscape,certified_translation
from spatial_memory.risk_ranked_emergency_v1 import RESH1
from spatial_memory.navigation import blocked_action_key,CARDINALS

def scene():return SimpleNamespace(scenario=SimpleNamespace(width=17,height=17),cell_size=.75,footprint_half_extents_local=(.219,.328))
def m(t,cells=((8,8),),grid=None):
    return {'grid':np.zeros((17,17),np.int8) if grid is None else grid,'visible_pedestrian_cells':cells,
            'motion_estimate':{'state':'measured_motion','velocity_cells_per_step':[0.,-1.]},'record':{'step':t}}
def step(c,t,yaw,action,*,pos=(7,7),cells=((8,8),),grid=None,blocked=frozenset()):
    r=c.choose(None,pos,(13,7),yaw,action,m(t,cells,grid),t,blocked)
    return r['action'] if r else action

def test_cycle_escape_preserves_certificate():
    c=RESH1CycleEscape(scene())
    assert step(c,1,0.,('turn',1))==('turn',1)
    assert step(c,2,np.pi/2,('turn',0))==('turn',0)
    out=step(c,3,0.,('turn',1))
    d=c.diagnostics[-1]
    assert d['rotation_cycle'] and d['cycle_escape_applied']
    assert out[0] in ('move','sidestep','retreat')
    assert next(x for x in d['cycle_escape_candidates'] if x['action']==out)['certified']
    step(c,4,0.,('turn',1),pos=out[1])
    assert not c.diagnostics[-1]['rotation_cycle']

def test_legitimate_half_turn_is_not_cycle():
    c=RESH1CycleEscape(scene())
    for t,yaw,turn in [(1,0.,1),(2,np.pi/2,2),(3,np.pi,3)]:
        step(c,t,yaw,('turn',turn))
        assert not c.diagnostics[-1]['rotation_cycle']

def test_cycle_without_observed_tracks_keeps_original():
    c=RESH1CycleEscape(scene())
    for t,yaw,turn in [(1,0.,1),(2,np.pi/2,0),(3,0.,1)]:
        assert step(c,t,yaw,('turn',turn),cells=())==('turn',turn)
    assert not c.diagnostics[-1]['cycle_escape_applied']

def test_all_translations_blocked_keeps_h1():
    a=RESH1CycleEscape(scene());b=RESH1(scene())
    for t,yaw,turn in [(1,0.,1),(2,np.pi/2,0),(3,0.,1)]:
        blocked=frozenset(blocked_action_key((7,7),0,(kind,(7+dx,7+dy)))
            for kind in ('move','sidestep','retreat') for dx,dy in CARDINALS)
        assert step(a,t,yaw,('turn',turn),blocked=blocked)==step(b,t,yaw,('turn',turn),blocked=blocked)
    assert not a.diagnostics[-1]['cycle_escape_applied']

def test_translation_certificates_match_frozen_h1_selected_assessment():
    rng=np.random.default_rng(2026111417)
    for _ in range(160):
        pos=(7,7);yaw=int(rng.integers(0,4))*np.pi/2
        dx,dy=CARDINALS[int(round(yaw/(np.pi/2)))%4]
        action=('move',(7+dx,7+dy))
        c=RESH1(scene());grid=rng.choice([-1,0,1],size=(17,17),p=[.08,.84,.08]).astype(np.int8)
        cells=(tuple(int(v) for v in rng.integers(4,11,size=2)),)
        step(c,1,yaw,action,pos=pos,cells=cells,grid=grid)
        d=c.diagnostics[-1]
        observed=certified_translation(pos,yaw,action,grid,d['current_possible_cells'],
            d['one_transition_reachable'],c.extents,c.cell_size,c.width,c.height,c.p.proxy_radius_m,frozenset())
        assert observed==d['selected_assessment']['certified']
