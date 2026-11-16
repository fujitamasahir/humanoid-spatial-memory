"""Cadence and motion-aware Age controls. No simulator or hidden inputs."""
from __future__ import annotations
import math
import numpy as np
from .evi import PersistenceEVIController

ARMS=('periodic5','age5','age_gap4','age_motion')

def cadence_decision(grid,last_observed,step,position,radius,parameters,mode,
                     *,last_scan_step,travel_since_scan,heading_changed):
    if mode not in ARMS:raise ValueError('unknown cadence arm')
    if step<last_scan_step or travel_since_scan<0:raise ValueError('invalid public history')
    age=parameters.age_steps
    gap=step-last_scan_step
    if mode=='periodic5':
        # Fixed-period requests depend only on the step and the frozen period.
        # The age fraction below was logged as a diagnostic but never used to
        # grant or deny Periodic-5 observations. Avoid allocating coordinate
        # grids and the known-cell mask on this fixed-cadence path.
        granted=step>0 and step%(age+1)==0
        return {'net_value':1. if granted else -1.,
            'reason':'fixed_longer_interval' if granted else 'defer',
            'age_request':None,'age_score':None,'effective_age_score':None,
            'last_scan_step':int(last_scan_step),'scan_gap':int(gap),
            'travel_since_scan_cells':float(travel_since_scan),
            'heading_changed_since_scan':bool(heading_changed),'plan_calls':0}
    yy,xx=np.indices(grid.shape)
    known=((xx-position[0])**2+(yy-position[1])**2<=radius**2)&(last_observed>=0)
    def fraction(age):
        return float(np.mean(step-last_observed[known]>=age)) if known.any() else 0.
    if mode=='age5':
        # Only the age+1 fraction controls this arm. The age fraction used to
        # populate age_request was diagnostic-only and duplicated this pass.
        effective_score=fraction(age+1)
        granted=step>0 and effective_score>=parameters.stale_fraction
        reason='longer_memory_age'
        age_request=None
        score=None
    elif mode=='age_gap4':
        score=fraction(age)
        age_request=step>0 and score>=parameters.stale_fraction
        effective_score=score
        granted=age_request and gap>=age
        reason='age_with_minimum_gap'
    else:
        score=fraction(age)
        age_request=step>0 and score>=parameters.stale_fraction
        effective_score=score
        # Preserve the first ordinary Age request. Later requests are
        # deferred until movement/heading has supplied a new viewpoint
        # or the one-step-longer deadline is reached.
        fresh_view=travel_since_scan>=max(1,age-1) or heading_changed
        granted=age_request and (last_scan_step==0 or gap>=age+1 or
                                  (gap>=max(1,age-1) and fresh_view))
        reason='age_with_motion_or_deadline'
    return {'net_value':1. if granted else -1.,'reason':reason if granted else 'defer',
        'age_request':None if age_request is None else bool(age_request),
        'age_score':score,'effective_age_score':effective_score,
        'last_scan_step':int(last_scan_step),'scan_gap':int(gap),
        'travel_since_scan_cells':float(travel_since_scan),
        'heading_changed_since_scan':bool(heading_changed),'plan_calls':0}

class CadenceController(PersistenceEVIController):
    def __init__(self,*args,cadence_mode,**kwargs):
        self.cadence_mode=cadence_mode
        self.last_scan_step=0
        self.travel_since_scan=0.
        self.last_position=None
        self.last_scan_yaw=None
        kwargs['evi_function']=self._score
        super().__init__(*args,**kwargs)
        if self.belief is not None:raise ValueError('Persistence disabled for cadence comparisons')

    def decide(self,step,position):
        self._step=step
        current=tuple(position)
        if self.context is None:raise RuntimeError('public context required')
        yaw=self.context[1]
        if self.last_position is None:
            # Step 1 begins before the first action, at the initial scan pose.
            self.last_scan_yaw=yaw
        else:
            self.travel_since_scan+=abs(current[0]-self.last_position[0])+abs(current[1]-self.last_position[1])
        self.last_position=current
        return super().decide(step,position)

    def _score(self,grid,probability,position,goal,yaw,unknown,sensor,remaining,parameters):
        history=self.base.agent
        changed=abs(math.remainder(yaw-self.last_scan_yaw,2*math.pi))>1e-6
        return cadence_decision(grid,history.last_observed,self._step,position,history.radius,
            history.parameters,self.cadence_mode,last_scan_step=self.last_scan_step,
            travel_since_scan=self.travel_since_scan,heading_changed=changed)

    def refresh(self,observation,step):
        super().refresh(observation,step)
        # Actual authorized observation time, even if no cell was visible.
        self.last_scan_step=step
        self.last_scan_yaw=self.context[1]
        self.travel_since_scan=0.
