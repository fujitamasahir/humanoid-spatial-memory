"""Frozen C v2.0 candidate-coverage ablation helpers.

The original C function remains in :mod:`spatial_memory.evi`. These helpers
alter only the shortlist selector; V, D, costs, and sensor footprint are kept.
"""
from dataclasses import dataclass
import math
import numpy as np
from .navigation import plan
from .evi import visible_cells, EVIParameters


@dataclass(frozen=True)
class ExpandedEVIParameters:
    """C-K/RouteK use original prices with a pre-frozen max shortlist of five."""
    max_candidates: int = 5
    sensing_cost: float = .5
    plan_cost: float = .01
    scarcity_cost: float = .5
    failure_cost: float = 80.

    def __post_init__(self):
        if type(self.max_candidates) is not int or not 1 <= self.max_candidates <= 5:
            raise ValueError('Expanded candidate count must be in [1,5]')
        vals=(self.sensing_cost,self.plan_cost,self.scarcity_cost,self.failure_cost)
        if not all(math.isfinite(x) and x >= 0 for x in vals) or self.failure_cost <= 0:
            raise ValueError('Invalid candidate-coverage prices')


def _traversable(grid, cell, unknown):
    x,y=cell
    return (0 <= y < grid.shape[0] and 0 <= x < grid.shape[1]
            and grid[y,x] != 1 and not (unknown == 'blocked' and grid[y,x] == -1))


def route_criticality_score(grid, probability, cell, route, unknown='optimistic'):
    """Uncertainty-weighted, public route/bottleneck/branch relevance score."""
    x,y=cell; q=float(probability[y,x])
    uncertainty=4*q*(1-q)
    route_set=set(route)
    distance=min((abs(x-rx)+abs(y-ry) for rx,ry in route),default=math.inf)
    on_route=1. if cell in route_set else 0.
    route_proximity=0. if math.isinf(distance) else 1./(1.+distance)
    neighbors=((x+1,y),(x-1,y),(x,y+1),(x,y-1))
    degree=sum(_traversable(grid,c,unknown) for c in neighbors)
    narrowness=1./(degree-1) if degree>=2 else 0.
    branches=[]
    for rx,ry in route:
        d=sum(_traversable(grid,(rx+dx,ry+dy),unknown)
              for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)))
        if d>=3:branches.append((rx,ry))
    branch_distance=min((abs(x-rx)+abs(y-ry) for rx,ry in branches),default=math.inf)
    branch_proximity=0. if math.isinf(branch_distance) else 1./(1.+branch_distance)
    relevance=(2.*on_route+route_proximity+.5*branch_proximity+.25*narrowness)
    return uncertainty*relevance


def eligible_candidates(grid, probability, position, yaw, sensor):
    footprint=visible_cells(grid,position,yaw,**sensor)
    return [c for c in footprint if c!=position and
            .05<float(probability[c[1],c[0]])<.95], footprint


def rank_route_candidates(grid, probability, candidates, route, unknown='optimistic'):
    scores={c:route_criticality_score(grid,probability,c,route,unknown) for c in candidates}
    return sorted(candidates,key=lambda c:(-scores[c],c[1],c[0])),scores


def rank_uncertainty_candidates(probability, candidates, route):
    def score(c):
        distance=min(abs(c[0]-r[0])+abs(c[1]-r[1]) for r in route)
        q=float(probability[c[1],c[0]])
        return q*(1-q)/(1+distance)
    ordered=sorted(candidates,key=lambda c:(-score(c),c[1],c[0]))
    return ordered,score


def _information_value_ranked(grid, probability, position, goal, yaw, unknown,
                              sensor, remaining, parameters, selector):
    p=parameters
    nominal=plan(grid,position,goal,unknown);calls=1
    cells,footprint=eligible_candidates(grid,probability,position,yaw,sensor)
    route=nominal or [position]
    cells,scores=selector(grid,probability,cells,route,unknown)
    best={'value':0.,'delay_regret':0.,'cell':None,'occupied_probability':None}
    for cell in cells[:p.max_candidates]:
        routes=[]
        for outcome in (0,1):
            cf=grid.copy();cf[cell[1],cell[0]]=outcome
            routes.append(plan(cf,position,goal,unknown));calls+=1
        def loss(path,occupied):
            if not path:return p.failure_cost
            return len(path)-1+(p.failure_cost if occupied and cell in path else 0)
        q=float(probability[cell[1],cell[0]])
        vals=[[loss(path,o) for o in (0,1)] for path in routes]
        before=min((1-q)*v[0]+q*v[1] for v in vals)
        after=(1-q)*min(v[0] for v in vals)+q*min(v[1] for v in vals)
        value=max(0.,before-after)
        actions=[tuple(path[1]) if path and len(path)>1 else None for path in routes]
        delay=value*min(q,1-q) if actions[0]!=actions[1] else 0.
        if (delay,value)>(best['delay_regret'],best['value']):
            best={'value':value,'delay_regret':delay,'cell':cell,'occupied_probability':q}
    cost=p.sensing_cost+p.plan_cost*calls+p.scarcity_cost/max(1,remaining)
    return {**best,'cost':cost,'net_value':best['delay_regret']-cost,
        'plan_calls':calls,'visible_cells':len(footprint),'nominal_route':nominal,
        'candidate_count':len(cells),'shortlisted_candidates':[
            {'cell':c,'score':scores[c] if isinstance(scores,dict) else scores(c),
             'q_occupied':float(probability[c[1],c[0]]),
             'on_nominal_route':c in set(route)} for c in cells[:p.max_candidates]]}


def information_value_route(grid, probability, position, goal, yaw, unknown, sensor,
                            remaining, parameters=None):
    """Original single-cell V/D with route-critical ranking and a fixed call cap."""
    p=parameters or ExpandedEVIParameters(max_candidates=3)
    selector=lambda g,q,c,r,u:rank_route_candidates(g,q,c,r,u)
    return _information_value_ranked(grid,probability,position,goal,yaw,unknown,
                                     sensor,remaining,p,selector)


def information_value_uncertainty_k(grid, probability, position, goal, yaw, unknown,
                                    sensor, remaining, parameters=None):
    """Original ranking/value exactly, with shortlist audit metadata for C-K."""
    p=parameters or ExpandedEVIParameters(max_candidates=5)
    selector=lambda g,q,c,r,u:rank_uncertainty_candidates(q,c,r)
    return _information_value_ranked(grid,probability,position,goal,yaw,unknown,
                                     sensor,remaining,p,selector)


def information_value_original_audit(grid, probability, position, goal, yaw, unknown,
                                     sensor, remaining, parameters=None):
    """C0 audit wrapper; value/cost/action fields are exactly the original C."""
    p=parameters or EVIParameters()
    selector=lambda g,q,c,r,u:rank_uncertainty_candidates(q,c,r)
    return _information_value_ranked(grid,probability,position,goal,yaw,unknown,
                                     sensor,remaining,p,selector)
