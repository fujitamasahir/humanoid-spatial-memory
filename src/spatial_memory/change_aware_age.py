"""CAA: authorized endpoint history changes deadlines, never occupancy belief."""
from __future__ import annotations
from dataclasses import dataclass
import math
import numpy as np
from .memory import Memory
from .scheduling import AdaptiveParameters

UNKNOWN,CHANGING,INTERMEDIATE,STABLE=-1,0,1,2
MODES=('caa_fast','caa_slow','caa_full','age5')

@dataclass(frozen=True)
class HistoryParameters:
    recent_steps: int = 10
    unchanged_reobservations: int = 3
    stable_span_steps: int = 12
    maximum_observation_gap: int = 6
    stable_freshness_steps: int = 6

    def __post_init__(self):
        if any(type(v) is not int or v<1 for v in vars(self).values()):
            raise ValueError('History constants must be positive integers')


class CellHistory:
    """No hidden classifications; unknown readings never update cell evidence."""
    def __init__(self,initial,parameters=None):
        initial=np.asarray(initial)
        if initial.ndim!=2:raise ValueError('Two-dimensional ternary grid required')
        self.parameters=parameters or HistoryParameters()
        self.memory=Memory(initial.shape)
        shape=initial.shape
        self.last_observed=np.full(shape,-1,dtype=np.int64)
        self.repeated=np.zeros(shape,dtype=np.int64)
        self.transitions=np.zeros(shape,dtype=np.int64)
        self.last_transition=np.full(shape,-1,dtype=np.int64)
        self.unchanged=np.zeros(shape,dtype=np.int64)
        self.run_start=np.full(shape,-1,dtype=np.int64)
        self.latest_scan=-1
        self.observe(initial,0)

    def observe(self,observation,step):
        observation=np.asarray(observation)
        if type(step) is not int or step<=self.latest_scan:
            raise ValueError('Paid observation times must strictly increase')
        if observation.shape!=self.memory.grid.shape or not np.isin(observation,[-1,0,1]).all():
            raise ValueError('Invalid ternary observation')
        visible=observation>=0;known=self.last_observed>=0
        new=visible&~known;repeat=visible&known
        changed=repeat&(observation!=self.memory.grid)
        continuous=repeat&~changed&((step-self.last_observed)<=self.parameters.maximum_observation_gap)
        restart=new|changed|(repeat&~changed&~continuous)
        self.repeated[repeat]+=1
        self.transitions[changed]+=1
        self.last_transition[changed]=step
        self.unchanged[restart]=0;self.unchanged[continuous]+=1
        self.run_start[restart]=step
        self.last_observed[visible]=step
        self.memory.update(observation)
        self.latest_scan=step

    def classify(self,step,region=None):
        if type(step) is not int or step<self.latest_scan:raise ValueError('Monotonic integer time required')
        region=region if region is not None else (slice(None),slice(None))
        last=self.last_observed[region];detected=self.last_transition[region]
        known=last>=0;p=self.parameters
        changing=known&(detected>=0)&((step-detected)<=p.recent_steps)
        stable=(known&~changing&(self.unchanged[region]>=p.unchanged_reobservations)
                &((last-self.run_start[region])>=p.stable_span_steps)
                &((step-last)<=p.stable_freshness_steps))
        classes=np.full(last.shape,UNKNOWN,dtype=np.int8)
        classes[known]=INTERMEDIATE;classes[stable]=STABLE;classes[changing]=CHANGING
        return classes

    def deadlines(self,step,mode,region=None):
        if mode not in MODES:raise ValueError('Unknown deadline mode')
        classes=self.classify(step,region)
        tau=np.full(classes.shape,5,dtype=np.int8)
        if mode in ('caa_fast','caa_full'):tau[classes==CHANGING]=4
        if mode in ('caa_slow','caa_full'):tau[classes==STABLE]=6
        return tau,classes

    def score(self,step,position,radius,mode):
        if not math.isfinite(radius) or radius<0:raise ValueError('Invalid radius')
        x,y=position;h,w=self.memory.grid.shape;r=math.ceil(radius)
        x0=max(0,int(x)-r);x1=min(w,int(x)+r+1)
        y0=max(0,int(y)-r);y1=min(h,int(y)+r+1)
        region=(slice(y0,y1),slice(x0,x1))
        tau,classes=self.deadlines(step,mode,region)
        yy,xx=np.ogrid[y0:y1,x0:x1]
        local=((xx-x)**2+(yy-y)**2<=radius**2)&(self.last_observed[region]>=0)
        due=local&((step-self.last_observed[region])>=tau)
        count=int(local.sum());value=float(due.sum()/count) if count else 0.
        return value,{'known_local_cells':count,'due_local_cells':int(due.sum()),
            'local_class_counts':{name:int(np.count_nonzero(local&(classes==v))) for name,v in [('changing',CHANGING),('intermediate',INTERMEDIATE),('stable',STABLE)]},
            'local_deadline_counts':{str(d):int(np.count_nonzero(local&(tau==d))) for d in (4,5,6)}}

    def summary(self,step):
        tau,classes=self.deadlines(step,'caa_full');known=classes!=UNKNOWN
        return {'classes':{name:int(np.count_nonzero(classes==v)) for name,v in [('unknown',UNKNOWN),('changing',CHANGING),('intermediate',INTERMEDIATE),('stable',STABLE)]},
                'full_deadlines_known':{str(d):int(np.count_nonzero(known&(tau==d))) for d in (4,5,6)}}


class ChangeAwareAgeController:
    """Drop-in paid-observation API, without EVI/planner/sensor dependencies."""
    def __init__(self,initial,method='age',*,mode='caa_full',interval=4,radius=3,
                 parameters=None,max_observations=20,history_parameters=None):
        if method!='age' or mode not in MODES:raise ValueError('Age scheduling only')
        if type(max_observations) is not int or not 1<=max_observations<=20:raise ValueError('Finite cap<=20 including initial scan required')
        self.history=CellHistory(initial,history_parameters);self.memory=self.history.memory
        self.parameters=parameters or AdaptiveParameters();self.radius=radius;self.mode=mode
        self.cap=max_observations;self.used=1;self.requests=self.denied=0
        self._pending=None;self._latest_decision=0;self.decisions=[]

    def decide(self,step,position):
        if type(step) is not int or step<max(self._latest_decision,self.history.latest_scan):raise ValueError('Monotonic integer decision time required')
        if self._pending is not None:raise RuntimeError('Granted paid observation must be consumed')
        score,detail=self.history.score(step,position,self.radius,self.mode)
        uniform5,_=self.history.score(step,position,self.radius,'age5')
        request=step>0 and score>=self.parameters.stale_fraction
        uniform_request=step>0 and uniform5>=self.parameters.stale_fraction
        grant=request and self.used<self.cap
        self.requests+=int(request);self.denied+=int(request and not grant)
        self._pending=step if grant else None;self._latest_decision=step
        self.decisions.append({'step':step,'mode':self.mode,'score':score,
            'uniform5_score':uniform5,'uniform5_request':bool(uniform_request),
            'request_advanced_vs_uniform5':bool(request and not uniform_request),
            'request_deferred_vs_uniform5':bool(uniform_request and not request),
            'requested':bool(request),'granted':bool(grant),'used_before':self.used,
            'scheduler_plan_calls':0,'predicted_raycasts':0,**detail})
        return {'observation_requested':bool(request),'observation_granted':bool(grant),
                'observation_score':score,'observation_position':tuple(position)}

    def refresh(self,observation,step):
        if self._pending!=step or self.used>=self.cap:raise RuntimeError('Unauthorized observation update')
        self.history.observe(observation,step)
        self.used+=1;self._pending=None
