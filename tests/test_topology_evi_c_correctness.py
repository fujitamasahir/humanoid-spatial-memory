"""Independent exhaustive/property checks for C v2.0c topology logic."""
from itertools import product
import math
import numpy as np

from spatial_memory.topology_evi_c import (
    analyze_public_topology_c, candidate_structural_feature_c,
    eligible_topology_candidates_c, rank_topology_candidates_c,
)
from spatial_memory.topology_reference import brute_force_topology_reference
from spatial_memory.evi import visible_cells, EVIParameters, information_value
from spatial_memory.topology_evi_c import information_value_topology_c
from spatial_memory.navigation import plan

SENSOR={'range_m':6.,'cell_size':.75,'horizontal_fov_deg':120.,'ray_count':61}


def _is_open(g,c,mode):
    x,y=c
    return g[y,x]!=1 and not (mode=='blocked' and g[y,x]==-1)


def assert_matches_reference(grid,start,goal,mode):
    nontraversable=[(x,y) for y in range(grid.shape[0]) for x in range(grid.shape[1])
                    if not _is_open(grid,(x,y),mode)]
    prod=analyze_public_topology_c(grid,start,goal,mode)
    ref=brute_force_topology_reference(grid,start,goal,mode,nontraversable)
    assert set(prod['articulation'])==ref['articulation']
    assert set(prod['separating'])==ref['start_goal_separating']
    assert set(prod['bridges'])==ref['bridges']
    assert set(prod['relevant_bridges'])==ref['terminal_relevant_bridges']
    assert set(prod['cyclic_block_vertices'])==ref['cycle_vertices']
    assert prod['component_count']==ref['component_count']
    assert math.isinf(prod['baseline_distance'])==math.isinf(ref['baseline_distance'])
    if math.isfinite(ref['baseline_distance']):
        assert prod['baseline_distance']==ref['baseline_distance']
    nodes=sorted(ref['vertices'])
    for i,a in enumerate(nodes):
        for b in nodes[i+1:]:
            assert (prod['component'][a]==prod['component'][b])==(ref['components'][a]==ref['components'][b])
    route=plan(grid,start,goal,mode)
    for c in nodes:
        got=candidate_structural_feature_c(grid,c,prod,start,goal,route)[1]
        if c in (start,goal):expected='traversable_terminal'
        elif c in ref['start_goal_separating']:expected='start_goal_separating_articulation'
        elif any(c in e for e in ref['terminal_relevant_bridges']):expected='terminal_relevant_bridge_endpoint'
        elif c in ref['articulation'] and c in set(route):expected='other_route_articulation'
        elif c in ref['cycle_vertices'] and c in set(route):expected='route_cell_with_alternative_cycle'
        elif c in ref['articulation']:expected='irrelevant_articulation'
        else:expected='other_traversable'
        assert got==expected,(grid.tolist(),start,goal,mode,c,got,expected)
    for c in nontraversable:
        got=candidate_structural_feature_c(grid,c,prod,start,goal,route)[1]
        expected=ref['nontraversable_shortcuts'][c]['kind']
        assert got==expected,(grid.tolist(),start,goal,mode,c,got,expected)
    assert prod['graph_work_units']<=20*(prod['vertices']+prod['edges'])


def test_exhaustive_all_two_by_three_public_ternary_grids_and_terminal_pairs():
    # 3^6 public ternary maps; both unknown modes; every valid ordered terminal
    # pair, including start==goal. Brute force remains cheap at six vertices.
    shape=(2,3)
    for values in product((-1,0,1),repeat=6):
        grid=np.asarray(values,dtype=np.int8).reshape(shape)
        for mode in ('optimistic','blocked'):
            nodes=[(x,y) for y in range(shape[0]) for x in range(shape[1]) if _is_open(grid,(x,y),mode)]
            for start in nodes:
                for goal in nodes:
                    assert_matches_reference(grid,start,goal,mode)


def test_1000_seeded_random_ternary_maps_match_independent_bfs_reference():
    rng=np.random.default_rng(20261114)
    for case in range(1000):
        grid=rng.choice(np.asarray([-1,0,1],dtype=np.int8),size=(4,5),p=(.28,.54,.18))
        free=list(zip(*np.where(grid==0)))
        if not free:grid[0,0]=0;free=[(0,0)]
        sy,sx=free[int(rng.integers(len(free)))];gy=int(rng.integers(4));gx=int(rng.integers(5))
        start=(sx,sy);goal=(gx,gy)
        for mode in ('optimistic','blocked'):
            try:assert_matches_reference(grid,start,goal,mode)
            except AssertionError as exc:
                raise AssertionError(f'random_seed=20261114 case={case} mode={mode} start={start} goal={goal}: {exc}') from exc


def test_visibility_and_candidate_probability_eligibility_equal_frozen_C():
    grid=np.zeros((12,12),dtype=np.int8);grid[[0,-1],:]=1;grid[:,[0,-1]]=1
    grid[5,6]=1
    probability=np.full(grid.shape,.5)
    pos=(3,5);yaw=0.
    actual,footprint=eligible_topology_candidates_c(grid,probability,pos,yaw,SENSOR)
    expected_fp=visible_cells(grid,pos,yaw,**SENSOR)
    expected=[c for c in expected_fp if c!=pos and .05<probability[c[1],c[0]]<.95]
    assert footprint==expected_fp and set(actual)==set(expected)


def test_candidate_sort_is_deterministic_and_coordinate_ties_are_stable():
    grid=np.zeros((7,7),dtype=np.int8);p=np.full(grid.shape,.5)
    graph=analyze_public_topology_c(grid,(1,3),(5,3),'optimistic')
    cells=[(3,3),(2,3),(4,3)]
    a=rank_topology_candidates_c(grid,p,cells,graph,(1,3),(5,3),[(x,3) for x in range(1,6)])[0]
    b=rank_topology_candidates_c(grid,p,list(reversed(cells)),graph,(1,3),(5,3),[(x,3) for x in range(1,6)])[0]
    assert a==b==[(2,3),(3,3),(4,3)]


def test_topology_selector_preserves_original_V_D_and_cost_for_single_candidate():
    grid=np.zeros((15,15),dtype=np.int8);grid[[0,-1],:]=1;grid[:,[0,-1]]=1
    p=np.full(grid.shape,.01);grid[7,6]=-1;p[7,6]=.5
    args=(grid,p,(2,7),(12,7),0.,'optimistic',SENSOR,10)
    original=information_value(*args,EVIParameters(max_candidates=3))
    topology=information_value_topology_c(*args,EVIParameters(max_candidates=3))
    for field in ('value','delay_regret','cell','occupied_probability','cost','net_value','plan_calls'):
        assert topology[field]==original[field],field
    assert topology['plan_calls']<=7


def test_occupied_cell_connectivity_restoration_requires_distinct_components():
    grid=np.ones((3,5),dtype=np.int8);grid[1,1]=0;grid[1,3]=0;grid[1,2]=1
    assert_matches_reference(grid,(1,1),(3,1),'optimistic')
    graph=analyze_public_topology_c(grid,(1,1),(3,1),'optimistic')
    assert candidate_structural_feature_c(grid,(2,1),graph,(1,1),(3,1))[1]=='nontraversable_connectivity_restoration'


def test_occupied_cell_on_existing_detour_is_distance_only_or_no_benefit():
    grid=np.ones((5,7),dtype=np.int8)
    grid[2,1:6]=0;grid[2,3]=1;grid[1,2:5]=0
    assert_matches_reference(grid,(1,2),(5,2),'optimistic')
    graph=analyze_public_topology_c(grid,(1,2),(5,2),'optimistic')
    kind=candidate_structural_feature_c(grid,(3,2),graph,(1,2),(5,2))[1]
    assert kind=='nontraversable_distance_shortcut'


def test_disconnected_graph_goal_terminal_start_equal_and_unknown_blocking():
    grid=np.ones((5,9),dtype=np.int8)
    grid[2,1:4]=0;grid[2,6:8]=0;grid[2,4]=-1
    for mode in ('optimistic','blocked'):
        assert_matches_reference(grid,(1,2),(7,2),mode)
    assert_matches_reference(grid,(1,2),(1,2),'optimistic')
    graph=analyze_public_topology_c(grid,(1,2),(4,2),'blocked')
    assert candidate_structural_feature_c(grid,(4,2),graph,(1,2),(4,2))[1]=='nontraversable_goal_terminal'


def test_iterative_tarjan_handles_long_corridor_without_recursive_stack():
    grid=np.zeros((1,2500),dtype=np.int8)
    graph=analyze_public_topology_c(grid,(0,0),(2499,0),'optimistic')
    assert graph['baseline_distance']==2499
    assert len(graph['bridges'])==2499
    assert len(graph['separating'])==2498
