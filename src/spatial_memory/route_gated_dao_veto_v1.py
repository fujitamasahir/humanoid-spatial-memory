"""Route-conditioned discovery and bounded fallback ablations of DAO-Veto.

Public nominal route only; no actual sensor, hidden geometry or shield access.
Keep the frozen original policy intact.
"""
from time import perf_counter_ns
from .dao_navigation_compat_v1_1 import DAONavigationCompatV1_1,safe_public_route
from .discovery_observation import assess,request_rule

ARMS={'dao_veto_route_gate':'route','dao_veto_deadline':'deadline','dao_veto_joint':'joint'}

def gated_rule(detail,step,gap,mode,parameters):
    if mode not in ('route','deadline','joint'):raise ValueError('Unknown frozen mode')
    base=request_rule(detail,step,gap,'dao_veto',parameters)
    f=detail['frontier'];has_route=detail['route_available']
    discovery=base['discovery_high']
    if mode in ('route','joint') and has_route:
        discovery=discovery and f['route_new']>0
    fallback=base['fallback']
    # Bound the time since a paid scan, not the age of every invisible cell.
    # Preserve original fallback if no usable nominal route is available.
    if mode in ('deadline','joint') and has_route:
        fallback=fallback and (f['stale']>0 or gap>=parameters.fallback_age)
    requested=bool(fallback or (base['age5_anchor'] and (discovery or base['verification_high'])))
    if requested and not base['requested']:raise RuntimeError('Non-subset same-state policy')
    return {**base,'requested':requested,'effective_discovery':bool(discovery),
        'effective_fallback':bool(fallback),'original_requested':base['requested'],
        'suppressed_same_state':bool(base['requested'] and not requested),
        'route_discovery_veto':bool(base['discovery_high'] and not discovery),
        'invisible_fallback_deferred':bool(base['fallback'] and not fallback)}

class RouteGatedDAOVeto(DAONavigationCompatV1_1):
    def __init__(self,initial,method='age',*,gate_mode,**options):
        if gate_mode not in ARMS.values():raise ValueError('Unknown frozen mode')
        super().__init__(initial,method,mode='dao_veto',**options)
        self.gate_mode=gate_mode

    def decide(self,step,position):
        if self.public_context is None or type(step) is not int or step<=self._latest or self._pending is not None:
            raise RuntimeError('Fresh context, monotonic clock and no pending scan required')
        goal,yaw,unknown=self.public_context;started=perf_counter_ns()
        before=perf_counter_ns()
        route=safe_public_route(self.memory.grid,position,goal,unknown)
        self.route_plan_ns+=perf_counter_ns()-before;self.route_plan_calls+=1
        self.last_route=route
        detail=assess(self.memory.grid,self.last_observed,step,position,yaw,
            route=route,parameters=self.parameters,sensor=self.sensor)
        result=gated_rule(detail,step,step-self.last_scan_step,self.gate_mode,self.parameters)
        granted=result['requested'] and self.used<self.cap
        self.requests+=int(result['requested']);self.denied+=int(result['requested'] and not granted)
        self.decisions.append({'step':step,'goal':goal,**detail,**result,'granted':bool(granted),
            'used_before':self.used,'gate_mode':self.gate_mode,'integration_route_plan_calls':1,
            'suppressed_grant_same_state':bool(result['suppressed_same_state'] and self.used<self.cap)})
        self._pending=step if granted else None;self._latest=step;self.public_context=None
        self.scheduler_ns+=perf_counter_ns()-started
        return {'observation_requested':result['requested'],'observation_granted':bool(granted),
            'observation_score':detail['frontier']['new'],'observation_position':tuple(position)}
