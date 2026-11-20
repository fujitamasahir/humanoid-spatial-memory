import itertools,math,sys
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest
from spatial_memory.predictive_emergency_v1 import (reachable,segment_box,action_geometry,swept_cells,PredictiveEmergencySafetyV1)
from spatial_memory.simulation import Scenario


def scene():return SimpleNamespace(scenario=SimpleNamespace(width=17,height=17),cell_size=.75,footprint_half_extents_local=(.219,.328))
def measurement(step,cells=()):return {'grid':np.zeros((17,17),np.int8),'visible_pedestrian_cells':cells,
     'motion_estimate':{'state':'measured_motion','velocity_cells_per_step':[0.,-1.]},'record':{'step':step}}


@pytest.mark.parametrize('horizon',range(5))
def test_reachable_exhaustive_paths_stopping_and_reversal(horizon):
    # Independent enumerate5^H sequences; no production dilation code.
    reference=set()
    for path in itertools.product(((0,0),(1,0),(-1,0),(0,1),(0,-1)),repeat=horizon):
        x,y=2,2;valid=True
        for dx,dy in path:
            x+=dx;y+=dy
            if not(0<=x<5 and 0<=y<5):valid=False;break
        if valid:reference.add((x,y))
    assert reachable({(2,2)},horizon,5,5)==reference
    assert (2,2) in reference


def test_slab_against_independent_dense_translation_reference():
    rng=np.random.default_rng(2026111420)
    for _ in range(300):
        start=rng.uniform(-2,2,2);end=start+rng.uniform(-1,1,2);point=rng.uniform(-3,3,2);half=rng.uniform(.1,1,2)
        sampled=any(np.all(np.abs(start+t*(end-start)-point)<=half) for t in np.linspace(0,1,1001))
        exact=segment_box(start,end,point,*half)
        assert not sampled or exact
        if not exact:assert not sampled
    assert segment_box((0,0),(2,0),(1,.2),.1,.3)
    assert not segment_box((0,0),(2,0),(1,.4),.1,.3)


def test_rotation_bound_contains_all_oriented_corners_and_rejects_intermediate_hazard():
    extents=(.219,.328);end,half,rotation=action_geometry((8,8),0.,('turn',1),extents,.75)
    assert rotation
    for yaw in np.linspace(0,math.pi/2,1001):
        for sx,sy in itertools.product((-1,1),repeat=2):
            x=(math.cos(yaw)*sx*extents[0]-math.sin(yaw)*sy*extents[1])/.75
            y=(math.sin(yaw)*sx*extents[0]+math.cos(yaw)*sy*extents[1])/.75
            assert abs(x)<=half[0]+1e-12 and abs(y)<=half[1]+1e-12
    assert (9,8) in swept_cells((8,8),end,half,17,17)


def test_reversal_risk_not_removed_by_velocity_estimate_and_swept_escape():
    c=PredictiveEmergencySafetyV1(scene());m=measurement(4,((8,7),))
    answer=c.choose(None,(7,8),(13,8),0.,('move',(8,8)),m,4)
    d=c.diagnostics[-1]
    assert d['selected_assessment']['future_endpoint_risk']
    assert answer is not None and answer['action']!=('move',(8,8))
    assert (8,8) in set(map(tuple,d['two_transition_reachable']))
    assert not d['no_certifiably_safe_action']


def test_wait_not_safe_and_no_safe_action_explicit():
    c=PredictiveEmergencySafetyV1(scene());m=measurement(1,((8,8),));m['grid'][:]=-1
    answer=c.choose(None,(8,8),(13,8),0.,('wait','base_wait'),m,1)
    assert answer['intervention']['no_certifiably_safe_action']
    assert c.diagnostics[-1]['selected_assessment']['current_sweep_risk']


def test_no_pedestrian_preserves_selected_action_and_memory():
    grid=np.zeros((17,17),np.int8);c=PredictiveEmergencySafetyV1(scene())
    assert c.choose(grid,(3,8),(13,8),0.,('move',(4,8)),measurement(1),1) is None
    assert not grid.any() and c.diagnostics[-1]['reason']=='no_observed_tracks_no_global_guarantee'


def test_occluded_track_and_multiple_tracks_explicit_uncertainty():
    c=PredictiveEmergencySafetyV1(scene())
    c.choose(None,(3,8),(13,8),0.,None,measurement(1,((7,7),(8,9))),1)
    c.choose(None,(3,8),(13,8),0.,None,measurement(2),2)
    assert len(c.diagnostics[-1]['current_possible_cells'])>2
    with pytest.raises(ValueError):c.choose(None,(3,8),(13,8),0.,None,measurement(2),2)


def test_benchmark_schema_speed_bounds_and_unavoidable_first_transition():
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
    from predictive_safety_benchmark_v1 import benchmark,all_cases
    assert len(benchmark())==14 and len(all_cases())==26
    for d in all_cases():Scenario.from_dict(d)
    d=next(d for d in benchmark() if d['family']=='unavoidable_first')
    assert tuple(d['pedestrians'][0][1])==tuple(d['start'])


def test_candidate_no_hidden_geometry_sensor_planner_dependency():
    import ast,inspect
    import spatial_memory.predictive_emergency_v1 as module
    tree=ast.parse(inspect.getsource(module))
    assert all((n.module or '') in ('dataclasses','navigation') for n in ast.walk(tree) if isinstance(n,ast.ImportFrom))
    assert not any(isinstance(n,ast.Attribute) and n.attr in ('data','model','_contacts','check_move','check_turn','observe','scan','people','occupancy') for n in ast.walk(tree))
