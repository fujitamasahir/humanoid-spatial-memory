"""CAA artifact helpers and unchanged G1 replay adapter."""
from __future__ import annotations
import gzip,json,sys
from time import perf_counter_ns
import numpy as np
from c_v21_common import ROOT,write,manifest,verify_manifest,sha,commit
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
import evaluate_event_observation_fit72 as ref
import evaluate_c_v2_candidate_coverage_fit72 as fit
from spatial_memory.scheduling import ObservationController
from spatial_memory.cadence_age import CadenceController
OUT=ROOT/'results/phase2_mujoco/caa_v1'
HIST=ROOT/'results/phase2_mujoco/age_cadence_v1/fit72'
BASE='b4fa534bfbcf6944766af743cbe5bc56cbdaffe5'


def episode(directory,n,arm):return json.load(gzip.open(directory/f'episode_{n:03}_{arm}.json.gz','rt'))
def parity(saved,row,trace):
    if ref.rdao_evaluator._signature(saved['row'])!=ref.rdao_evaluator._signature(row):raise RuntimeError('Frozen metric signature mismatch')
    ref._compare_trace(saved['trace'],ref.base._jsonable_row(trace))

def frozen_factory(initial,arm,config,options):
    if arm in ('periodic','age4'):
        return ObservationController(initial,'periodic' if arm=='periodic' else 'age',**options)
    if arm=='age5':
        sensor={k:config['mujoco_ray_sensor'][k] for k in ('range_m','horizontal_fov_deg','ray_count')}
        sensor['cell_size']=config['mujoco_cell_size_m']
        return CadenceController(initial,'age',cadence_mode='age5',persistence=False,
                                 evi=True,sensor=sensor,**options)
    raise ValueError('Unknown frozen baseline')


def run_case(payload,schedule,arm,config,*,factory=None,capture_frames=False,history_factory=None):
    """Instrument only paid readings/public frames; no extra sensing/planning."""
    original=ref.base.run_episode;context={};frames=[];actual_calls=[]
    original_observe=fit.MujocoRayPerception.observe
    def measured_observe(self,world,position,yaw):
        result=original_observe(self,world,position,yaw)
        if self.ray_count==61 and self.horizontal_fov_deg==120. and self.range_m==6.:
            actual_calls.append(int(world.step))
        return result
    def injected(scenario,run_config,method,**kwargs):
        class Wrapped:
            def __init__(self,initial,mode,**options):
                self.radius=options['radius']
                self.core=(factory(initial,arm,config,options) if factory else frozen_factory(initial,arm,config,options))
                self.memory=self.core.memory;self.decisions=[];self.observation_log=[]
                self.scheduler_decision_total_ns=0;self.history_update_total_ns=0
                self.diagnostic_total_ns=0;self._pending=None
                self.last_state=np.full(initial.shape,-1,dtype=np.int8)
                self.last_observed=np.full(initial.shape,-1,dtype=np.int64)
                self.history=history_factory(initial) if history_factory else None
                self.initialization_complete=False
                self.record(initial,0)
                self.initialization_complete=True
                context['agent']=self
            @property
            def used(self):return self.core.used
            @property
            def cap(self):return self.core.cap
            @property
            def requests(self):return self.core.requests
            @property
            def denied(self):return self.core.denied
            def set_navigation_context(self,**kw):
                if hasattr(self.core,'set_navigation_context'):self.core.set_navigation_context(**kw)
            def record(self,observation,step):
                t=perf_counter_ns();visible=observation>=0;known=self.last_observed>=0
                new=visible&~known;repeated=visible&known;changed=repeated&(observation!=self.last_state)
                self.observation_log.append({'step':int(step),'visible_cells':int(visible.sum()),'new_cells':int(new.sum()),'repeated_cells':int(repeated.sum()),'changed_known_cells':int(changed.sum()),'unchanged_known_cells':int((repeated&~changed).sum()),'only_unchanged_known':bool(visible.any() and not new.any() and not changed.any()),'empty':not bool(visible.any()),'observed_occupied':int(np.count_nonzero(observation==1)),'observed_free':int(np.count_nonzero(observation==0))})
                self.last_state[visible]=observation[visible];self.last_observed[visible]=step
                if self.history is not None and self.initialization_complete:self.history.observe(observation,step)
                if self.history is not None:self.observation_log[-1]['history_after_scan']=self.history.summary(step)
                if not np.array_equal(self.memory.grid,self.last_state):raise RuntimeError('Memory is not authorized last-write observation history')
                self.diagnostic_total_ns+=perf_counter_ns()-t
            def decide(self,step,position):
                if self._pending is not None:raise RuntimeError('Pending paid scan not consumed')
                started=perf_counter_ns();result=self.core.decide(step,position)
                elapsed=perf_counter_ns()-started;self.scheduler_decision_total_ns+=elapsed
                detail=dict(self.core.decisions[-1]) if getattr(self.core,'decisions',None) else {}
                # Legacy cadence net_value is not CAA information value.
                detail.update(step=int(step),granted=bool(result['observation_granted']),requested=bool(result['observation_requested']),used_before=int(self.used),scheduler_ns=elapsed)
                if self.history is not None:
                    t=perf_counter_ns();detail['global_history']=self.history.summary(step)
                    detail['uniform_age5_score']=self.history.score(step,position,self.radius,'age5')[0]
                    if arm.startswith('caa_'):
                        tau,classes=self.history.deadlines(step,arm)
                        detail['effective_deadlines_known']={str(v):int(np.count_nonzero((self.last_observed>=0)&(tau==v))) for v in (4,5,6)}
                    elif arm!='periodic':
                        fixed={'age4':4,'age5':5,'age6':6}[arm]
                        detail['effective_deadlines_known']={str(v):int(np.count_nonzero(self.last_observed>=0)) if v==fixed else 0 for v in (4,5,6)}
                    else:detail['periodic_clock_interval']=config['update_interval']
                    self.diagnostic_total_ns+=perf_counter_ns()-t
                self.decisions.append(detail)
                self._pending=step if result['observation_granted'] else None
                return result
            def refresh(self,observation,step):
                if self._pending!=step or self.used>=self.cap:raise RuntimeError('Unauthorized paid refresh')
                started=perf_counter_ns();self.core.refresh(observation,step)
                self.history_update_total_ns+=perf_counter_ns()-started
                self.record(observation,step);self._pending=None
        kwargs['_controller_factory']=Wrapped
        prior=kwargs.get('_frame_callback')
        def frame_callback(world,frame):
            result=prior(world,frame) if prior else None
            if capture_frames:
                # Evaluator-only retrospective labels, NEVER passed to a core.
                occupied=world.occupancy().astype(bool);memory=frame['memory']
                frames.append({'step':int(frame['step']),'position':list(frame['position']),'yaw':float(frame['heading_yaw']),'memory':memory.copy(),'stale_occupied_cells':int(np.count_nonzero((memory==1)&~occupied)),'stale_free_cells':int(np.count_nonzero((memory==0)&occupied)),'persistent_errors':dict(frame['errors'])})
            return result
        kwargs['_frame_callback']=frame_callback
        return original(scenario,run_config,method,**kwargs)
    ref.base.run_episode=injected
    fit.MujocoRayPerception.observe=measured_observe
    try:
        row,trace=ref.base.run_case(payload,schedule,'periodic' if arm=='periodic' else 'age',json.loads(json.dumps(config)),with_safety=True)
    finally:
        ref.base.run_episode=original
        fit.MujocoRayPerception.observe=original_observe
    agent=context['agent'];scans=[f['step'] for f in trace['steps'] if f['observation_granted']]
    if scans!=actual_calls or scans!=[s['step'] for s in agent.observation_log] or len(scans)!=row['observation_count']:raise RuntimeError('Actual sensor/scan ledger mismatch')
    diag={'decisions':agent.decisions,'observation_log':agent.observation_log,'scheduler_total_ms':agent.scheduler_decision_total_ns/1e6,'history_update_total_ms':agent.history_update_total_ns/1e6,'diagnostic_total_ms':agent.diagnostic_total_ns/1e6,'actual_memory_call_steps':scans,'actual_memory_sensor_calls':len(scans),'actual_memory_raycasts':61*len(scans),'retrospective_frames':frames}
    if row['g1_unselected_action_shield_queries'] or not row['g1_shield_query_count_valid'] or row['observation_count']>20:raise RuntimeError('Safety/cap invariant')
    return row,trace,diag
