"""Route-aware directional Age scheduling: public-memory heuristic."""
from __future__ import annotations
import numpy as np
from .evi import PersistenceEVIController, visible_cells
from .navigation import plan
from .view_age import view_age_decision

ARMS=('age_route_rescue','age_route_clock')

def route_age_decision(grid,last_observed,step,position,goal,yaw,unknown,sensor,
                       radius,parameters,mode):
    if mode not in ARMS:raise ValueError('unknown mode')
    position,goal=tuple(position),tuple(goal)
    detail=view_age_decision(grid,last_observed,step,position,yaw,sensor,radius,
                             parameters,'age_view_veto')
    route=plan(grid,position,goal,unknown)
    footprint=visible_cells(grid,position,yaw,**sensor)
    # At most one Age interval of prospective point-grid moves. Include direct
    # path cells (stale/unknown) and stale occupied immediate neighbors, which
    # may affect clearance or indicate a newly available alternative.
    prefix=[tuple(c) for c in route[1:parameters.age_steps+1]]
    direct=set(prefix)
    neighbors={(x+dx,y+dy) for x,y in prefix
               for dx,dy in ((1,0),(-1,0),(0,1),(0,-1))}
    height,width=grid.shape
    def local(c):
        x,y=c
        return (0<=x<width and 0<=y<height and
                (x-position[0])**2+(y-position[1])**2<=radius**2)
    candidates=sorted(c for c in footprint if local(c) and c!=position and
        (c in direct or (c in neighbors and grid[c[1],c[0]]==1)))
    due=[c for c in candidates if last_observed[c[1],c[0]]<0 or
         step-int(last_observed[c[1],c[0]])>=parameters.age_steps]
    latest=int(last_observed.max())
    gap=step-latest
    route_due=bool(step>0 and due)
    no_route=not route and position!=goal
    # Rescue grants are restricted to original Age requests at the same state.
    rescue=bool(detail['age_request'] and (route_due or no_route))
    # Clock can act ahead of the original Age request, but only at the
    # half of the original age interval since the latest nonempty observation.
    # A full interval would make every known local cell stale, so would
    # generally make the proactive arm redundant with the rescue arm.
    minimum_gap=max(1,(parameters.age_steps+1)//2)
    proactive=bool(mode=='age_route_clock' and route_due and gap>=minimum_gap)
    if step<=0:rescue=proactive=False
    veto_grant=detail['net_value']>0
    granted=bool(veto_grant or rescue or proactive)
    reason=('view_veto_grant' if veto_grant else 'route_rescue' if rescue
            else 'route_clock' if proactive else 'defer')
    return {**detail,'net_value':1. if granted else -1.,'reason':reason,
        'nominal_route':route,'plan_calls':1,'route_prefix':prefix,
        'route_visible_candidates':candidates,'route_due_cells':due,
        'route_due':route_due,'no_public_point_route':no_route,
        'route_rescue':rescue,'route_proactive':proactive,'view_veto_grant':veto_grant,
        'steps_since_latest_observed_cell':gap,'proactive_minimum_gap':minimum_gap,
        'route_visibility_computations':2}

class RouteAgeController(PersistenceEVIController):
    def __init__(self,*args,route_mode,**kwargs):
        self.route_mode=route_mode
        kwargs['evi_function']=self._score
        super().__init__(*args,**kwargs)

    def _score(self,grid,probability,position,goal,yaw,unknown,sensor,remaining,parameters):
        history=self.base.agent
        return route_age_decision(grid,history.last_observed,self._step,position,goal,
            yaw,unknown,sensor,history.radius,history.parameters,self.route_mode)

    def decide(self,step,position):
        self._step=step
        return super().decide(step,position)
