"""C v2.1a depth ablation: bounded scan-now / delayed scan / no-information route surrogate.

Only public grids, probabilities, pose/heading, goal, sensor geometry and
remaining budget enter. No persistence, sensor calls, G1 planning or shield.
Frozen selectors are reused verbatim; predictions are NOT observations.
"""
from __future__ import annotations
from dataclasses import dataclass
from functools import partial
import math
from time import perf_counter_ns
import numpy as np
from .navigation import plan
from .evi import visible_cells
from .candidate_coverage import eligible_candidates,rank_uncertainty_candidates
from .topology_evi_c import analyze_public_topology_c
from .topology_evi_d import rank_topology_candidates_d

DEFAULT_HORIZON=1

@dataclass(frozen=True)
class MultiStepParameters:
    max_candidates: int = 5
    sensing_cost: float = .5
    plan_cost: float = .01
    scarcity_cost: float = .5
    failure_cost: float = 80.

    def __post_init__(self):
        if type(self.max_candidates) is not int or self.max_candidates not in (3,5):raise ValueError('Only frozen K=3 or K=5')
        if any(not math.isfinite(v) or v<0 for k,v in vars(self).items() if k!='max_candidates') or self.failure_cost<=0:raise ValueError('Invalid costs')


def select_candidates(grid,probability,position,goal,yaw,unknown,sensor,selector,nominal):
    candidates,footprint=eligible_candidates(grid,probability,position,yaw,sensor)
    metadata={}
    if selector=='k':
        ordered,_=rank_uncertainty_candidates(probability,candidates,nominal or [position])
        selected=ordered[:5]
    elif selector=='topology':
        t=perf_counter_ns();graph=analyze_public_topology_c(grid,position,goal,unknown)
        selected,features,keys,stats=rank_topology_candidates_d(grid,probability,candidates,graph,position,goal,nominal or [],3)
        metadata={'graph_analysis_ns':perf_counter_ns()-t,'selection_counters':stats,
                  'graph_vertices':graph['vertices'],'graph_edges':graph['edges'],
                  'graph_operation_counts':graph['operation_counts']}
    else:raise ValueError('Unknown frozen selector')
    return selected,len(candidates),len(footprint),metadata


def _loss(route,occupied,cell,failure):
    if not route:return failure
    return len(route)-1+(failure if occupied and cell in route else 0.)


def candidate_options(grid,cell,q,routes,position,yaw,sensor,price,*,visibility,
                      failure=80.,visibility_cache=None,horizon=DEFAULT_HORIZON):
    """Evaluate a fixed two-route, nonanticipatory prefix catalog, without A*."""
    if type(horizon) is not int or horizon not in (1,3): raise ValueError("Only preregistered H=1 or H=3")
    weights=(1-q,q)
    losses=[[_loss(r,o,cell,failure) for o in (0,1)] for r in routes]
    no_info=min(sum(weights[o]*row[o] for o in (0,1)) for row in losses)
    optimal=[min(range(2),key=lambda r:losses[r][o]) for o in (0,1)]
    after=sum(weights[o]*losses[optimal[o]][o] for o in (0,1))
    common=0
    while all(len(r)>common for r in routes) and routes[0][common]==routes[1][common]:common+=1
    shared_moves=max(0,common-1)
    cache=visibility_cache if visibility_cache is not None else {}
    evaluations=[];visibility_calls=0;prefix_steps=0;recovery_checks=0
    indexes=[{tuple(c):i for i,c in enumerate(r)} for r in routes]
    for blind_index,blind in enumerate(routes):
      for h in range(1,horizon+1):
        # A fixed (route,time) choice is made BEFORE the occupancy outcome.
        # No outcome-specific stopping-time or clairvoyant branch selection.
        outcome_costs=[];predictions=[]
        for occupied in (0,1):
            walked=[tuple(position)];heading=float(yaw);stopped=False
            for step in range(1,h+1):
                prefix_steps+=1
                if stopped or step>=len(blind):continue
                destination=tuple(blind[step]);source=walked[-1]
                heading=math.atan2(destination[1]-source[1],destination[0]-source[0])
                if occupied and destination==cell:
                    stopped=True
                else:walked.append(destination)
            pos=walked[-1]
            if visibility:
                key=(pos,heading)
                if key not in cache:
                    cache[key]=visible_cells(grid,pos,heading,**sensor);visibility_calls+=1
                observable=cell in cache[key]
            else:observable=True
            if observable:
                best_route=routes[optimal[occupied]]
                if not best_route or (occupied and cell in best_route):
                    movement=h+losses[optimal[occupied]][occupied]
                else:
                    # Reverse an executed prefix to ANY common route vertex,
                    # then follow the precomputed outcome-optimal suffix.
                    # Costs include prefix time once and never add V twice.
                    recovery=math.inf
                    for k,c in enumerate(walked):
                        recovery_checks+=1
                        if c in indexes[optimal[occupied]]:
                            i=indexes[optimal[occupied]][c]
                            recovery=min(recovery,len(walked)-1-k+len(best_route)-1-i)
                    movement=h+recovery
            else:
                # A scan that cannot reveal this cell leaves the original
                # full-route loss; prefix time is already in that route loss.
                movement=losses[blind_index][occupied]
            outcome_costs.append(float(movement))
            predictions.append({'outcome':occupied,'position':pos,'yaw':heading,
                                'visible':bool(observable),'blocked_in_hypothesis':stopped})
        expected=sum(weights[o]*outcome_costs[o] for o in (0,1))
        evaluations.append({'route_index':blind_index,'after_moves':h,
            'expected_movement':expected,'cost_with_scan':expected+price,
            'outcome_movement_costs':outcome_costs,'predictions':predictions})
    best_delayed=min(evaluations,key=lambda v:(v['cost_with_scan'],v['after_moves'],v['route_index']))
    now=after+price;alternative=min(no_info,best_delayed['cost_with_scan'])
    net=alternative-now
    if abs(net)<1e-12:net=0.
    return {'cell':cell,'occupied_probability':q,'value':max(0.,no_info-after),
        'delay_regret':max(0.,best_delayed['expected_movement']-after),
        'no_information_cost':no_info,'informed_movement_cost':after,
        'observe_now_cost':now,'best_postpone_cost':best_delayed['cost_with_scan'],
        'net_value':net,'shared_prefix_moves':shared_moves,
        'earliest_route_divergence':shared_moves if routes[0]!=routes[1] else None,
        'best_delayed_option':best_delayed,'delayed_options':evaluations,
        'future_visibility_computations':visibility_calls,
        'prefix_step_visits':prefix_steps,'recovery_checks':recovery_checks,
        'reason':('scan_avoids_lost_opportunity_or_delay' if net>0 else
                  'no_information_is_cheaper' if no_info<=now else 'postpone_without_extra_expected_cost')}


def information_value_multistep(grid,probability,position,goal,yaw,unknown,
                               sensor,remaining,parameters=None,*,selector='k',
                               future_visibility=False,horizon=DEFAULT_HORIZON):
    if type(horizon) is not int or horizon not in (1,3): raise ValueError("Only preregistered H=1 or H=3")
    started=perf_counter_ns();p=parameters or MultiStepParameters(5 if selector=='k' else 3)
    k=5 if selector=='k' else 3
    if p.max_candidates!=k:raise ValueError('Selector and candidate bound differ')
    grid=np.asarray(grid);probability=np.asarray(probability)
    if grid.ndim!=2 or probability.shape!=grid.shape or not np.isin(grid,[-1,0,1]).all() or not np.isfinite(probability).all() or ((probability<0)|(probability>1)).any():raise ValueError('Invalid public belief')
    nominal=plan(grid,tuple(position),tuple(goal),unknown)
    selected,m,visible,metadata=select_candidates(grid,probability,tuple(position),tuple(goal),yaw,unknown,sensor,selector,nominal)
    calls=1+2*len(selected)
    price=p.sensing_cost+p.plan_cost*calls+p.scarcity_cost/max(1,remaining)
    cache={};rows=[]
    for cell in selected:
        routes=[]
        for o in (0,1):
            cf=grid.copy();cf[cell[1],cell[0]]=o
            routes.append(plan(cf,tuple(position),tuple(goal),unknown))
        row=candidate_options(grid,cell,float(probability[cell[1],cell[0]]),routes,
            tuple(position),yaw,sensor,price,visibility=future_visibility,
            failure=p.failure_cost,visibility_cache=cache,horizon=horizon)
        row['routes']=routes
        rows.append(row)
    best=max(rows,key=lambda r:(r['net_value'],r['value']),default=None)
    summary=({key:best[key] for key in ('cell','occupied_probability','value','delay_regret','net_value','reason','shared_prefix_moves','best_delayed_option')} if best else
             {'cell':None,'occupied_probability':None,'value':0.,'delay_regret':0.,'net_value':-price,'reason':'no_eligible_candidates','shared_prefix_moves':None,'best_delayed_option':None})
    return {**summary,'cost':price,'plan_calls':calls,'visible_cells':visible,
        'nominal_route':nominal,'candidate_count':m,'candidate_count_m':m,
        'candidate_limit_k':k,'lookahead_horizon':horizon,
        'future_visibility_enabled':future_visibility,
        'shortlisted_candidates':[{'cell':c,'q_occupied':float(probability[c[1],c[0]]),'on_nominal_route':c in (nominal or [])} for c in selected],
        'candidate_evaluations':rows,
        'future_visibility_computations':sum(r['future_visibility_computations'] for r in rows),
        'visibility_computations':1+sum(r['future_visibility_computations'] for r in rows),
        'prefix_step_visits':sum(r['prefix_step_visits'] for r in rows),
        'recovery_checks':sum(r['recovery_checks'] for r in rows),
        'counterfactual_grid_cells_copied':2*len(selected)*grid.size,
        'future_option_evaluations':2*horizon*len(selected),
        'scheduler_ns':perf_counter_ns()-started,**metadata}

# Only the no-future-visibility arms: matched objective, selector, and costs.
ARMS={
    'h1_k':partial(information_value_multistep,selector='k',future_visibility=False,horizon=1),
    'h1_topology':partial(information_value_multistep,selector='topology',future_visibility=False,horizon=1),
    'h3_k':partial(information_value_multistep,selector='k',future_visibility=False,horizon=3),
    'h3_topology':partial(information_value_multistep,selector='topology',future_visibility=False,horizon=3),
}
