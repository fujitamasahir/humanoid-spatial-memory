"""Age-anchored view-aware scheduling; public memory only."""
from __future__ import annotations
import numpy as np
from .evi import PersistenceEVIController, visible_cells

ARMS=('age_view_veto','age_view_clock')

def view_age_decision(grid,last_observed,step,position,yaw,sensor,radius,parameters,mode):
    """Directional stale fraction in the original Age radius.

    Never-observed cells are excluded, as in Age. No hidden observation.
    The veto arm cannot request outside the original Age schedule at a fixed
    state. The clock arm replaces the omnidirectional denominator.
    Both retain the original Age request after two age intervals without a scan.
    """
    if mode not in ARMS:raise ValueError('unknown mode')
    yy,xx=np.indices(grid.shape)
    local=(xx-position[0])**2+(yy-position[1])**2<=radius**2
    known=local & (last_observed>=0)
    stale=known & (step-last_observed>=parameters.age_steps)
    age_score=float(stale.sum()/known.sum()) if known.any() else 0.
    age_request=step>0 and age_score>=parameters.stale_fraction
    visible=visible_cells(grid,position,yaw,**sensor)
    relevant=[(x,y) for x,y in visible if known[y,x]]
    view_score=sum(bool(stale[y,x]) for x,y in relevant)/len(relevant) if relevant else 0.
    view_request=step>0 and bool(relevant) and view_score>=parameters.stale_fraction
    latest=int(last_observed.max())
    deadline=age_request and step-latest>=2*parameters.age_steps
    grant=bool(deadline or (view_request and (age_request if mode=='age_view_veto' else True)))
    return {'net_value':1. if grant else -1.,'age_score':age_score,'view_score':view_score,
        'age_request':bool(age_request),'view_request':bool(view_request),'deadline':bool(deadline),
        'known_local_cells':int(known.sum()),'known_visible_local_cells':len(relevant),
        'reason':'age_deadline' if deadline else 'visible_stale' if grant else 'defer'}

class ViewAgeController(PersistenceEVIController):
    def __init__(self,*args,view_mode,**kwargs):
        self.view_mode=view_mode
        kwargs['evi_function']=self._score
        super().__init__(*args,**kwargs)

    def _score(self,grid,probability,position,goal,yaw,unknown,sensor,remaining,parameters):
        history=self.base.agent
        return view_age_decision(grid,history.last_observed,self._step,position,yaw,sensor,
                                 history.radius,history.parameters,self.view_mode)

    def decide(self,step,position):
        self._step=step
        return super().decide(step,position)
