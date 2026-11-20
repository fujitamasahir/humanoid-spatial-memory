"""DAO-Veto discovery-estimator ablation; no frozen controller edited."""
from time import perf_counter_ns
from .dao_navigation_compat_v1_1 import DAONavigationCompatV1_1
from .discovery_observation import assess,request_rule
from .attenuated_discovery_v1 import attenuated_footprints

ARMS={'dao_veto_q50':.5,'dao_veto_q80':.8,'dao_veto_optimistic':1.}

def estimate_rule(detail,estimated_new,step,gap,parameters):
    """Only replace the new-cell term; verification/fallback remain frontier."""
    changed={**detail,'frontier':{**detail['frontier'],'new':estimated_new}}
    return request_rule(changed,step,gap,'dao_veto',parameters)

class AttenuatedDAOVeto(DAONavigationCompatV1_1):
    def __init__(self,initial,method='age',*,factor,**options):
        if factor not in (0.,.5,.8,1.):raise ValueError('Frozen factor')
        super().__init__(initial,method,mode='dao_veto',**options)
        self.factor=factor

    def decide(self,step,position):
        if self.public_context is None or type(step) is not int or step<=self._latest or self._pending is not None:
            raise RuntimeError('Fresh context, monotonic clock and no pending scan required')
        goal,yaw,unknown=self.public_context
        started=perf_counter_ns()
        detail=assess(self.memory.grid,self.last_observed,step,position,yaw,
            parameters=self.parameters,sensor=self.sensor)
        prediction=attenuated_footprints(self.memory.grid,position,yaw,
            factors=(self.factor,),**self.sensor)
        count=sum(prediction['weights'][self.factor].values())
        gap=step-self.last_scan_step
        original=request_rule(detail,step,gap,'dao_veto',self.parameters)
        result=estimate_rule(detail,count,step,gap,self.parameters)
        if original['requested'] and not result['requested']:
            raise RuntimeError('Nonmonotonic same-state discovery replacement')
        granted=result['requested'] and self.used<self.cap
        self.requests+=int(result['requested']);self.denied+=int(result['requested'] and not granted)
        self.decisions.append({'step':step,'goal':goal,**detail,**result,'granted':bool(granted),
            'used_before':self.used,'discovery_factor':self.factor,'weighted_new':count,
            'frontier_request':original['requested'],
            'extra_request_same_state':bool(result['requested'] and not original['requested']),
            'attenuation_sample_visits':prediction['sample_visits'],
            'integration_route_plan_calls':0,
            'integration_route_unavailable_occupied_start':bool(self.memory.grid[position[1],position[0]]==1)})
        self._pending=step if granted else None;self._latest=step
        self.public_context=None;self.last_route=None
        self.scheduler_ns+=perf_counter_ns()-started
        return {'observation_requested':result['requested'],'observation_granted':bool(granted),
            'observation_score':count,'observation_position':tuple(position)}
