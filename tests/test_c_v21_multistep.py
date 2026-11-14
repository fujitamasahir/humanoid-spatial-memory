"""Development correctness cases, disjoint from the frozen formal generator."""
import ast,itertools,math
from pathlib import Path
import numpy as np
import pytest
from spatial_memory.evi import visible_cells,PersistenceEVIController
from spatial_memory.multistep_evi import (ARMS,MultiStepParameters,HORIZON,
                                         information_value_multistep)
from spatial_memory.multistep_reference import reference_cell,footprint
from spatial_memory.candidate_coverage import information_value_uncertainty_k
from spatial_memory.topology_evi_d import information_value_topology_d

SENSOR=dict(range_m=4.,cell_size=1.,horizontal_fov_deg=360.,ray_count=61)

def compare(grid,prob,start,goal,unknown,visibility):
    p=MultiStepParameters(5)
    result=information_value_multistep(grid,prob,start,goal,0.,unknown,SENSOR,19,p,
                                     future_visibility=visibility)
    refs=[]
    for c in result['shortlisted_candidates']:
        cell=tuple(c['cell'])
        ref=reference_cell(grid,cell,float(prob[cell[1],cell[0]]),start,goal,0.,
                           unknown,SENSOR,result['cost'],visibility)
        actual=next(v for v in result['candidate_evaluations'] if v['cell']==cell)
        for key in ('value','delay_regret','net_value','no_information_cost',
                    'informed_movement_cost','observe_now_cost','best_postpone_cost'):
            assert actual[key]==pytest.approx(ref[key],abs=1e-9), (key,grid,cell)
        refs.append(ref)
    if refs:
        expected=max(refs,key=lambda r:(r['net_value'],r['value']))
        assert result['net_value']==pytest.approx(expected['net_value'])
    else:assert result['net_value']<0
    k=result['candidate_limit_k']
    assert result['plan_calls']<=1+2*k
    assert result['visibility_computations']<=1+4*k*HORIZON
    assert result['prefix_step_visits']<=2*k*HORIZON*(HORIZON+1)
    assert result['recovery_checks']<=2*k*HORIZON*(HORIZON+3)
    return result


def test_exhaustive_ternary_small_states_against_independent_enumeration():
    # 81 maps, four uncertain cells, both unknown modes, both visibility arms.
    for values in itertools.product((-1,0,1),repeat=4):
      grid=np.zeros((2,3),dtype=np.int8)
      middle=[(1,0),(2,0),(0,1),(1,1)]
      for c,value in zip(middle,values):grid[c[1],c[0]]=value
      for target in middle:
        q=np.where(grid==1,1.,0.);q[target[1],target[0]]=.5
        for unknown in ('optimistic','blocked'):
          for visibility in (False,True):compare(grid,q,(0,0),(2,1),unknown,visibility)


@pytest.mark.parametrize('selector', ['k','topology'])
def test_frozen_selector_is_exactly_reused(selector):
    rng=np.random.default_rng(2026111450)
    for _ in range(40):
        grid=rng.choice([0,1,-1],size=(5,6),p=[.6,.25,.15]).astype(np.int8)
        grid[2,1]=grid[2,4]=0;q=rng.choice([0.,.3,.5,.7,1.],size=grid.shape)
        fn=information_value_uncertainty_k if selector=='k' else information_value_topology_d
        old=fn(grid,q,(1,2),(4,2),0.,'optimistic',SENSOR,19)
        new=information_value_multistep(grid,q,(1,2),(4,2),0.,'optimistic',SENSOR,19,
             MultiStepParameters(5 if selector=='k' else 3),selector=selector)
        assert [x['cell'] for x in old['shortlisted_candidates']]==[x['cell'] for x in new['shortlisted_candidates']]
        assert old['plan_calls']==new['plan_calls']
        assert old['cost']==new['cost']


def test_independent_footprint_rotations_range_and_occlusion():
    grid=np.zeros((7,8),dtype=np.int8);grid[2:6,4]=1
    for yaw in (0.,.017,math.pi/2,math.pi,-math.pi/2):
      for range_m in (1.,2.7,6.):
        for fov in (60.,120.,360.):
          sensor={**SENSOR,'range_m':range_m,'horizontal_fov_deg':fov}
          assert footprint(grid,(2,3),yaw,sensor)==visible_cells(grid,(2,3),yaw,**sensor)


def test_budget_and_no_persistence_controller_boundary():
    arr=np.zeros((4,5),dtype=np.int8)
    for fn in ARMS.values():
        agent=PersistenceEVIController(arr,'age',max_observations=1,persistence=False,
          evi_function=fn,sensor=SENSOR)
        agent.set_navigation_context(goal=(4,2),yaw=0.,unknown='optimistic')
        assert not agent.decide(1,(1,2))['observation_granted']
        assert agent.used==1 and agent.belief is None
        with pytest.raises(RuntimeError):agent.refresh(arr,1)


def test_max_not_sum_for_competing_marginals():
    grid=np.zeros((6,7),dtype=np.int8);q=np.zeros(grid.shape);q[2,2]=q[2,3]=.5
    result=compare(grid,q,(1,2),(6,2),'optimistic',True)
    assert result['net_value']==max(r['net_value'] for r in result['candidate_evaluations'])


def test_reference_isolated_and_policy_has_no_hidden_access():
    root=Path(__file__).parents[1]/'src/spatial_memory'
    reference=(root/'multistep_reference.py').read_text()
    assert 'from .multistep_evi' not in reference
    tree=ast.parse((root/'multistep_evi.py').read_text())
    for node in ast.walk(tree):
        if isinstance(node,ast.Attribute):
            assert node.attr not in {'observe','scan','geometry','occupancy','people','check_move','check_turn','_sync_environment'}


def test_input_validation_and_fixed_horizon():
    assert HORIZON==3
    with pytest.raises(ValueError):MultiStepParameters(max_candidates=4)
    grid=np.zeros((3,3),dtype=np.int8);q=np.ones((3,3))*2
    with pytest.raises(ValueError):information_value_multistep(grid,q,(0,0),(2,2),0.,'optimistic',SENSOR,19)
