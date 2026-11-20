"""Deterministic controls for direction-aware Age; no FIT access."""
import numpy as np
import pytest
from spatial_memory.scheduling import AdaptiveParameters
from spatial_memory.view_age import view_age_decision, ViewAgeController, ARMS

SENSOR=dict(range_m=6.,cell_size=1.,horizontal_fov_deg=120.,ray_count=61)
P=AdaptiveParameters(age_steps=4,stale_fraction=.5)

def score(grid,last,t,mode):
    return view_age_decision(grid,last,t,(4,4),0.,SENSOR,3,P,mode)

def test_stale_behind_robot_does_not_prompt_visible_refresh():
    grid=np.zeros((9,9),dtype=np.int8)
    yy,xx=np.indices(grid.shape)
    last=np.where(xx<=4,0,3)
    last[4,4]=3
    for mode in ARMS:
        d=score(grid,last,4,mode)
        assert d['age_request']
        assert not d['view_request']
        assert d['net_value']<0

def test_stale_ahead_can_be_more_useful_than_stale_behind():
    grid=np.zeros((9,9),dtype=np.int8)
    yy,xx=np.indices(grid.shape)
    last=np.where(xx>4,0,3)
    veto=score(grid,last,4,'age_view_veto')
    clock=score(grid,last,4,'age_view_clock')
    assert not veto['age_request']
    assert clock['view_request']
    assert veto['net_value']<0<clock['net_value']

def test_deadline_is_original_age_conditional():
    grid=np.zeros((9,9),dtype=np.int8)
    last=np.zeros(grid.shape,dtype=int)
    for mode in ARMS:
        d=score(grid,last,8,mode)
        assert d['deadline'] and d['net_value']>0
        d=score(grid,np.full(grid.shape,5),8,mode)
        assert not d['deadline'] and d['net_value']<0

def test_unknown_is_not_counted_as_stale():
    grid=np.full((9,9),-1,dtype=np.int8);last=np.full(grid.shape,-1,dtype=int)
    for mode in ARMS:
        d=score(grid,last,4,mode)
        assert d['known_visible_local_cells']==0
        assert d['net_value']<0

def test_randomized_veto_subset_and_visible_score():
    rng=np.random.default_rng(2026111418)
    for _ in range(80):
        last=rng.integers(-1,8,size=(9,9));grid=rng.integers(0,2,size=(9,9),dtype=np.int8)
        grid[last<0]=-1;grid[4,4]=0
        d=score(grid,last,8,'age_view_veto')
        v=score(grid,last,8,'age_view_clock')
        assert d['age_score']==v['age_score']
        assert d['view_score']==v['view_score']
        assert 0<=d['view_score']<=1
        assert d['net_value']<=0 or d['age_request']
        assert d['net_value']<=v['net_value']

@pytest.mark.parametrize('mode',ARMS)
def test_controller_cap_and_refresh(mode):
    arr=np.zeros((9,9),dtype=np.int8)
    c=ViewAgeController(arr,'age',view_mode=mode,radius=3,parameters=P,
        max_observations=2,persistence=False,sensor=SENSOR)
    c.set_navigation_context(goal=(7,4),yaw=0.,unknown='optimistic')
    assert c.decide(4,(4,4))['observation_granted']
    c.refresh(arr,4)
    assert c.used==2
    assert not c.decide(8,(4,4))['observation_granted']
    with pytest.raises(RuntimeError):c.refresh(arr,8)
