import numpy as np
import pytest

from spatial_memory.candidate_coverage import (
    ExpandedEVIParameters, information_value_route, rank_route_candidates,
    rank_uncertainty_candidates, route_criticality_score,
    information_value_original_audit, information_value_uncertainty_k,
)
from spatial_memory.evi import information_value, EVIParameters
from spatial_memory.evi import PersistenceEVIController


def make_corridor():
    grid=np.zeros((15,15),dtype=np.int8);grid[[0,-1],:]=1;grid[:,[0,-1]]=1
    grid[6,5:9]=1;grid[8,5:9]=1
    prob=np.full(grid.shape,.01)
    return grid,prob


def test_route_critical_cell_can_enter_top_three_when_original_ranks_it_fourth():
    grid,prob=make_corridor();route=[(x,7) for x in range(2,13)]
    candidates=[(4,6),(5,6),(7,6),(6,7)]
    for c in candidates:prob[c[1],c[0]]=.5
    prob[7,6]=.1
    old,_=rank_uncertainty_candidates(prob,candidates,route)
    new,_=rank_route_candidates(grid,prob,candidates,route)
    assert old.index((6,7))==3
    assert new.index((6,7))<3


def test_unique_chokepoint_fixture_exposes_route3_ranking_failure():
    grid=np.zeros((15,15),dtype=np.int8);grid[[0,-1],:]=1;grid[:,[0,-1]]=1
    grid[1:14,6]=1;grid[7,6]=-1
    route=[(x,7) for x in range(2,13)];critical=(6,7)
    candidates=[(3,7),(4,7),(5,7),critical];prob=np.full(grid.shape,.01)
    for c in candidates:prob[c[1],c[0]]=.5
    original,_=rank_uncertainty_candidates(prob,candidates,route)
    route_ranked,_=rank_route_candidates(grid,prob,candidates,route)
    # Frozen negative fixture: branch-point proximity keeps the chokepoint
    # outside Route3 just as C0 does; K=5 is needed to include it.
    assert critical not in original[:3]
    assert critical not in route_ranked[:3]
    assert critical in route_ranked[:5]


def test_narrow_route_bottleneck_scores_above_open_route_cell():
    grid,prob=make_corridor();route=[(x,7) for x in range(2,13)]
    narrow=(6,7);open_cell=(10,6)
    prob[7,6]=prob[6,10]=.4
    assert route_criticality_score(grid,prob,narrow,route) > route_criticality_score(grid,prob,open_cell,route)


def test_branch_proximity_is_public_and_deterministic():
    grid=np.ones((13,13),dtype=np.int8);grid[1:12,1:12]=0
    # A T-shaped public junction lies on the nominal path.
    route=[(x,6) for x in range(2,10)]
    near=(6,5);far=(3,3);prob=np.full(grid.shape,.5)
    assert route_criticality_score(grid,prob,near,route) > route_criticality_score(grid,prob,far,route)
    ranked,_=rank_route_candidates(grid,prob,[far,near],route)
    assert ranked[0]==near


def test_multiple_alternative_routes_prioritize_current_route_and_branch_cells():
    grid=np.ones((15,15),dtype=np.int8);grid[1:14,1:14]=0
    route=[(x,7) for x in range(2,13)]
    candidates=[(6,7),(6,6),(6,8),(4,5)]
    prob=np.full(grid.shape,.5)
    # Three public alternatives exist around the route; the route cell is the
    # decision-critical candidate, not every uncertain detour cell.
    ranking,_=rank_route_candidates(grid,prob,candidates,route)
    assert ranking[0]==(6,7)


def test_high_uncertainty_irrelevant_cell_loses_to_route_critical_cell():
    grid,prob=make_corridor();route=[(x,7) for x in range(2,13)]
    critical=(6,7);irrelevant=(8,6)
    prob[7,6]=.1;prob[6,8]=.5
    assert route_criticality_score(grid,prob,critical,route) > route_criticality_score(grid,prob,irrelevant,route)


def test_future_branch_candidate_priority_uses_public_route_distance():
    grid=np.ones((15,15),dtype=np.int8);grid[1:14,1:14]=0
    route=[(x,7) for x in range(2,13)];prob=np.full(grid.shape,.5)
    near=(8,6);far=(3,3)
    assert route_criticality_score(grid,prob,near,route) > route_criticality_score(grid,prob,far,route)


def test_expanded_limit_is_fixed_at_five_and_original_default_remains_three():
    assert EVIParameters().max_candidates==3
    assert ExpandedEVIParameters().max_candidates==5
    with pytest.raises(ValueError):ExpandedEVIParameters(max_candidates=6)


def test_route_value_keeps_original_cost_and_plan_accounting():
    grid,prob=make_corridor();prob[7,6]=.5
    sensor={'range_m':6.,'cell_size':.75,'horizontal_fov_deg':120.,'ray_count':61}
    p3=ExpandedEVIParameters(max_candidates=3)
    p5=ExpandedEVIParameters(max_candidates=5)
    a=information_value_route(grid,prob,(2,7),(12,7),0.,'optimistic',sensor,10,p3)
    b=information_value_route(grid,prob,(2,7),(12,7),0.,'optimistic',sensor,10,p5)
    assert a['plan_calls']<=7 and b['plan_calls']<=11
    assert a['cost']==pytest.approx(.5+.01*a['plan_calls']+.5/10)
    assert b['cost']==pytest.approx(.5+.01*b['plan_calls']+.5/10)


def test_no_benefit_fixture_does_not_authorize_scan():
    grid=np.zeros((15,15),dtype=np.int8);prob=np.full(grid.shape,.01)
    grid[:,0]=grid[:,-1]=1;grid[0,:]=grid[-1,:]=1
    prob[6,4]=.5;grid[6,4]=-1 # off-route unknown; direct route is y=7
    sensor={'range_m':6.,'cell_size':.75,'horizontal_fov_deg':120.,'ray_count':61}
    result=information_value_route(grid,prob,(2,7),(12,7),0.,'optimistic',sensor,10,
                                   ExpandedEVIParameters(max_candidates=3))
    assert result['value']==0 and result['delay_regret']==0
    assert result['net_value']<0


def test_correlated_uncertain_candidates_are_not_summed():
    grid,prob=make_corridor();prob[7,5]=prob[7,6]=.5
    sensor={'range_m':6.,'cell_size':.75,'horizontal_fov_deg':120.,'ray_count':61}
    args=(grid,prob,(2,7),(12,7),0.,'optimistic',sensor,10)
    both=information_value_route(*args,ExpandedEVIParameters(max_candidates=3))
    individual=[]
    for cell in ((5,7),(6,7)):
        q=prob.copy();q[7,5]=q[7,6]=.01;q[cell[1],cell[0]]=.5
        individual.append(information_value_route(grid,q,(2,7),(12,7),0.,'optimistic',sensor,10,
            ExpandedEVIParameters(max_candidates=1))['value'])
    assert both['value']<=max(individual)+1e-12


def test_audit_wrappers_preserve_original_value_and_cost_exactly():
    grid,prob=make_corridor();prob[7,6]=.5
    sensor={'range_m':6.,'cell_size':.75,'horizontal_fov_deg':120.,'ray_count':61}
    for params in (EVIParameters(max_candidates=3),ExpandedEVIParameters(max_candidates=5)):
        original=information_value(grid,prob,(2,7),(12,7),0.,'optimistic',sensor,10,params)
        if params.max_candidates==3:
            wrapped=information_value_original_audit(grid,prob,(2,7),(12,7),0.,'optimistic',sensor,10,params)
        else:
            wrapped=information_value_uncertainty_k(grid,prob,(2,7),(12,7),0.,'optimistic',sensor,10,params)
        for key in ('value','delay_regret','cell','occupied_probability','cost','net_value','plan_calls','nominal_route'):
            assert wrapped[key]==original[key]


def test_original_controller_keeps_frozen_information_function_by_default():
    initial=np.zeros((9,9),dtype=np.int8)
    controller=PersistenceEVIController(initial,'age',persistence=False,evi=True)
    assert controller.evi_function is information_value
