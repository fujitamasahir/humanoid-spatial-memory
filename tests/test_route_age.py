"""Public-memory controls for route-aware Age."""
import numpy as np
import pytest
from spatial_memory.scheduling import AdaptiveParameters
from spatial_memory.view_age import view_age_decision
from spatial_memory.route_age import route_age_decision,RouteAgeController,ARMS

P=AdaptiveParameters(age_steps=4,stale_fraction=.5)
SENSOR=dict(range_m=6.,cell_size=1.,horizontal_fov_deg=120.,ray_count=61)
START=(4,4);GOAL=(7,4)

def score(grid,last,mode,step=4,yaw=0.,unknown='optimistic'):
    return route_age_decision(grid,last,step,START,GOAL,yaw,unknown,SENSOR,3,P,mode)

def test_rescue_unknown_route_cell_when_view_veto_defers():
    grid=np.zeros((9,9),dtype=np.int8)
    _,xx=np.indices(grid.shape)
    last=np.where(xx<=4,0,3)
    last[4,4]=3
    grid[4,5]=-1;last[4,5]=-1
    d=score(grid,last,'age_route_rescue')
    assert d['age_request'] and not d['view_veto_grant']
    assert (5,4) in d['route_due_cells']
    assert d['route_rescue'] and d['net_value']>0

def test_proactive_route_clock_is_distinct_and_has_cooldown():
    grid=np.zeros((9,9),dtype=np.int8);last=np.full(grid.shape,2,dtype=int)
    grid[4,5]=-1;last[4,5]=-1
    rescue=score(grid,last,'age_route_rescue')
    clock=score(grid,last,'age_route_clock')
    assert not rescue['age_request'] and rescue['net_value']<0
    assert clock['route_proactive'] and clock['net_value']>0
    assert score(grid,last,'age_route_clock',step=3)['net_value']<0

def test_off_route_stale_cells_do_not_trigger_extra_scan():
    grid=np.zeros((9,9),dtype=np.int8);last=np.full(grid.shape,2,dtype=int)
    last[2,5]=0
    for mode in ARMS:
        d=score(grid,last,mode)
        assert not d['route_due']
        assert d['net_value']<0

def test_stale_occupied_neighbor_and_visibility_boundary():
    grid=np.zeros((9,9),dtype=np.int8);last=np.full(grid.shape,2,dtype=int)
    grid[3,6]=1;last[3,6]=0
    d=score(grid,last,'age_route_clock')
    assert (6,3) in d['route_due_cells']
    assert d['route_proactive']
    d=score(grid,last,'age_route_clock',yaw=np.pi)
    assert (6,3) not in d['route_due_cells']
    assert not d['route_proactive']

def test_no_route_retains_original_age():
    grid=np.zeros((9,9),dtype=np.int8);grid[:,5]=1
    last=np.zeros(grid.shape,dtype=int)
    d=score(grid,last,'age_route_rescue')
    assert d['no_public_point_route'] and d['age_request'] and d['net_value']>0

def test_randomized_frozen_veto_and_age_bounds():
    rng=np.random.default_rng(2026111419)
    for _ in range(64):
        grid=rng.choice([-1,0,1],size=(9,9),p=[.1,.7,.2]).astype(np.int8)
        grid[4,4]=0;grid[4,7]=0
        last=rng.integers(0,8,size=(9,9));last[grid<0]=-1
        prior=view_age_decision(grid,last,8,START,0.,SENSOR,3,P,'age_view_veto')
        rescue=score(grid,last,'age_route_rescue',step=8)
        clock=score(grid,last,'age_route_clock',step=8)
        assert prior['net_value']<=rescue['net_value']<=clock['net_value']
        assert rescue['net_value']<=0 or rescue['age_request']
        assert rescue['plan_calls']==clock['plan_calls']==1
        assert all(c in rescue['route_visible_candidates'] for c in rescue['route_due_cells'])

@pytest.mark.parametrize('mode',ARMS)
def test_controller_cap_and_refresh(mode):
    arr=np.zeros((9,9),dtype=np.int8)
    c=RouteAgeController(arr,'age',route_mode=mode,radius=3,parameters=P,
        max_observations=2,persistence=False,sensor=SENSOR)
    c.set_navigation_context(goal=GOAL,yaw=0.,unknown='optimistic')
    assert c.decide(4,START)['observation_granted']
    c.refresh(arr,4)
    assert c.used==2
    assert not c.decide(8,START)['observation_granted']
    with pytest.raises(RuntimeError):c.refresh(arr,8)
