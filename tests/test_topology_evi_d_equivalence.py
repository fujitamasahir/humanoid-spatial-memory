"""Exact semantic-equivalence checks for C v2.0d bounded top-K selection."""
from itertools import product
import numpy as np

from spatial_memory.evi import EVIParameters
from spatial_memory.navigation import plan
from spatial_memory.topology_evi_c import (
    analyze_public_topology_c,
    information_value_topology_c,
    rank_topology_candidates_c,
)
from spatial_memory.topology_evi_d import (
    information_value_topology_d,
    rank_topology_candidates_d,
    topology_rank_key_d,
)

SENSOR={'range_m':6.,'cell_size':.75,'horizontal_fov_deg':120.,'ray_count':61}


def _compare_rankings(grid, start, goal, mode, probabilities):
    graph=analyze_public_topology_c(grid,start,goal,mode)
    route=plan(grid,start,goal,mode)
    candidates=[(x,y) for y in range(grid.shape[0]) for x in range(grid.shape[1])
                if (x,y)!=start and .05<probabilities[y,x]<.95]
    full, full_features, full_counts=rank_topology_candidates_c(
        grid,probabilities,candidates,graph,start,goal,route)
    selected, features, keys, stats=rank_topology_candidates_d(
        grid,probabilities,candidates,graph,start,goal,route,3)
    assert selected==full[:3]
    assert features=={c:full_features[c] for c in selected}
    assert keys=={c:topology_rank_key_d(full_features[c],probabilities,c) for c in selected}
    assert len(selected)==min(3,len(candidates))
    assert stats['candidate_visits']==stats['feature_evaluations']==len(candidates)
    assert stats['rank_key_builds']==len(candidates)
    assert stats['total_key_comparisons']<=stats['theoretical_heap_comparison_bound']
    assert stats['total_key_comparisons']<=full_counts['sort_comparisons']+10


def test_topk_matches_full_sort_for_all_small_ternary_maps_and_terminal_pairs():
    shape=(2,3)
    for values in product((-1,0,1),repeat=6):
        grid=np.asarray(values,dtype=np.int8).reshape(shape)
        probabilities=np.full(shape,.5)
        for mode in ('optimistic','blocked'):
            nodes=[(x,y) for y in range(shape[0]) for x in range(shape[1])
                   if grid[y,x]!=1 and not(mode=='blocked' and grid[y,x]==-1)]
            for start in nodes:
                for goal in nodes:
                    _compare_rankings(grid,start,goal,mode,probabilities)


def test_topk_matches_full_sort_for_1000_deterministic_random_maps():
    rng=np.random.default_rng(2026111504)
    for i in range(1000):
        grid=rng.choice(np.asarray([-1,0,1],dtype=np.int8),size=(4,5),p=(.25,.55,.2))
        free=list(zip(*np.where(grid==0)))
        if not free:grid[0,0]=0;free=[(0,0)]
        sy,sx=free[int(rng.integers(len(free)))];goal=(int(rng.integers(5)),int(rng.integers(4)))
        p=rng.choice(np.asarray([.01,.25,.5,.75,.99]),size=grid.shape)
        for mode in ('optimistic','blocked'):
            try:_compare_rankings(grid,(sx,sy),goal,mode,p)
            except AssertionError as exc:
                raise AssertionError(f'seed=2026111504 case={i}, mode={mode}: {exc}') from exc


def test_topk_empty_ties_sparse_dense_and_candidate_counts_beyond_k():
    for grid in (np.ones((9,9),dtype=np.int8),np.zeros((9,9),dtype=np.int8)):
        probabilities=np.full(grid.shape,.5)
        start=(4,4);goal=(7,7)
        graph=analyze_public_topology_c(grid,start,goal,'optimistic')
        for candidates in ([],[(5,4)],[(x,y) for y in range(9) for x in range(9) if (x,y)!=start]):
            full=rank_topology_candidates_c(grid,probabilities,candidates,graph,start,goal,plan(grid,start,goal))[0]
            selected,_,_,_=rank_topology_candidates_d(grid,probabilities,candidates,graph,start,goal,plan(grid,start,goal),3)
            assert selected==full[:3]


def test_complete_topology_evi_decision_is_exactly_equivalent_on_seeded_maps():
    rng=np.random.default_rng(2026111505)
    for i in range(100):
        grid=np.zeros((12,12),dtype=np.int8)
        grid[[0,-1],:]=1;grid[:,[0,-1]]=1
        for y in range(1,11):
            for x in range(1,11):
                value=rng.random()
                if value<.14:grid[y,x]=1
                elif value<.37:grid[y,x]=-1
        start=(5,5);goal=(int(rng.integers(1,11)),int(rng.integers(1,11)))
        p=np.full(grid.shape,.01);p[grid==-1]=.5
        # Force many eligible candidates, including equal-score ties.
        for y in range(1,11):
            for x in range(1,11):
                if (x,y)!=start and rng.random()<.45:p[y,x]=.5
        args=(grid,p,start,goal,0.,'optimistic',SENSOR,9,EVIParameters(max_candidates=3))
        old=information_value_topology_c(*args)
        new=information_value_topology_d(*args)
        for field in ('value','delay_regret','cell','occupied_probability','cost','net_value','plan_calls','candidate_count'):
            assert new[field]==old[field],(i,field,new[field],old[field])
        assert new['shortlisted_candidates']==old['shortlisted_candidates'],i
        assert new['plan_calls']<=7
        assert (new['net_value']>0)==(old['net_value']>0)
        assert new['stage_accounting']['passes'],new['stage_accounting']['checks']


def test_heap_comparator_preserves_coordinate_tie_order_and_k_zero():
    grid=np.zeros((5,5),dtype=np.int8);p=np.full(grid.shape,.5)
    graph=analyze_public_topology_c(grid,(0,2),(4,2),'optimistic')
    cells=[(3,2),(1,2),(2,2),(4,1),(4,3)]
    full=rank_topology_candidates_c(grid,p,cells,graph,(0,2),(4,2),[(x,2) for x in range(5)])[0]
    selected,_,_,_=rank_topology_candidates_d(grid,p,cells,graph,(0,2),(4,2),[(x,2) for x in range(5)],3)
    assert selected==full[:3]
    empty,features,keys,stats=rank_topology_candidates_d(grid,p,cells,graph,(0,2),(4,2),[],0)
    assert empty==[] and features==keys=={} and stats['top_k']==0
