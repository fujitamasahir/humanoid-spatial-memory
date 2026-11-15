"""Frozen-model H2 final benchmark adapter and disjoint timing instruments."""
from pathlib import Path
import sys,json,time,signal,datetime,hashlib,subprocess
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src')]
from c_v21_common import write,manifest,verify_manifest,sha,commit
import evaluate_event_observation_fit72 as ref
import evaluate_c_v2_candidate_coverage_fit72 as fit
from run_c_v21a_depth_ablation import episode,parity
from spatial_memory.scheduling import ObservationController
from spatial_memory.cadence_age import CadenceController
from spatial_memory.route_age import RouteAgeController
from spatial_memory.change_aware_age import ChangeAwareAgeController
from spatial_memory.route_adaptive_age_v1 import RouteAdaptiveAgeV1
from spatial_memory.rdao_v2 import RDAOv2ViewpointController
from spatial_memory.rdao_v21_quality import RDAOv21CurrentQualityController
from spatial_memory.navigation import heading_index
OUT=ROOT/'results/phase2_mujoco/h2_final_generalization_v1'
ARMS=('periodic4','periodic5','age4','age5','age6','age_route_rescue','age_route_clock','rdao_v2','rdao_v21','caa_fast','caa_full','raa_defer')
LABELS=('Periodic-4','Periodic-5','Age-4','Age-5','Age-6','Age-Route-Rescue','Age-Route-Clock','RDAO v2','RDAO v2.1','CAA-Fast','CAA-Full','RAA-Defer')
DEADLINE=datetime.datetime(2026,11,15,2,30,tzinfo=datetime.timezone.utc).timestamp()
def deadline_guard(reserve=180):
    remaining=DEADLINE-time.time()-reserve
    if remaining<=0:raise TimeoutError('Owner hard deadline: preserve partial results now')
    def expired(*_):raise TimeoutError('Owner hard deadline reserve reached')
    signal.signal(signal.SIGALRM,expired);signal.setitimer(signal.ITIMER_REAL,remaining)
def config():return ref.base.frozen_config(ref.base.load_baseline()[2])
def factory(initial,arm,cfg,options,goal):
    from dataclasses import replace
    if arm in ('periodic4','age4','age6'):
        kw=dict(options)
        if arm=='age6':kw['parameters']=replace(kw['parameters'],age_steps=6)
        return ObservationController(initial,'periodic' if arm=='periodic4' else 'age',**kw)
    sensor={k:cfg['mujoco_ray_sensor'][k] for k in ('range_m','horizontal_fov_deg','ray_count')};sensor['cell_size']=cfg['mujoco_cell_size_m']
    if arm in ('periodic5','age5'):return CadenceController(initial,'age',cadence_mode=arm,persistence=False,evi=True,sensor=sensor,**options)
    if arm.startswith('age_route_'):return RouteAgeController(initial,'age',route_mode=arm,persistence=False,evi=True,sensor=sensor,**options)
    if arm.startswith('caa_'):return ChangeAwareAgeController(initial,mode=arm,**options)
    if arm=='raa_defer':return RouteAdaptiveAgeV1(initial,mode=arm,sensor=sensor,**options)
    cls={'rdao_v2':RDAOv2ViewpointController,'rdao_v21':RDAOv21CurrentQualityController}[arm]
    return cls(initial,goal=tuple(goal),max_observations=options['max_observations'],unknown=cfg['unknown'],local_extents=cfg['g1_navigation']['local_half_extents_m'],cell_size_m=cfg['mujoco_cell_size_m'],**{k:cfg['mujoco_ray_sensor'][k] for k in ('range_m','horizontal_fov_deg','ray_count')})

def run_case(payload,schedule,arm,cfg=None):
    """Single-threaded scoped wrappers. Cores never receive truth/timings/labels."""
    cfg=json.loads(json.dumps(cfg or config()));context={};times={k:[] for k in ('decision','update','initialization','memory_sensor','emergency_sensor','navigation_planning','point_planning','safety_decision')};calls=[];observations=[]
    original=ref.base.run_episode;scenario_original=ref.base.scenario_from_bprime
    def scenario_adapter(p,s):
        if p.get('partition')=='h2_final_generalization_v1':
            # Format adapter only; disjoint identity/seed/manifest are preserved.
            return scenario_original(dict(p,partition='fit'),s)
        return scenario_original(p,s)
    def injected(scenario,run_config,method,**kwargs):
        class Wrapped:
            def __init__(self,initial,mode,**options):
                t=time.perf_counter_ns();self.core=factory(initial,arm,cfg,options,scenario.goal);times['initialization'].append(time.perf_counter_ns()-t)
                self.memory=self.core.memory;self.yaw=0.;self.pending=None;self.decisions=[]
                self.last=np.full(initial.shape,-1,dtype=np.int8);self.record(initial,0);context['agent']=self
            @property
            def used(self):return self.core.used
            @property
            def cap(self):return self.core.cap
            @property
            def requests(self):return self.core.requests
            @property
            def denied(self):return self.core.denied
            def record(self,o,step):
                v=o>=0;known=self.last>=0
                observations.append({'step':int(step),'new_cells':int((v&~known).sum()),'changed_known_cells':int((v&known&(o!=self.last)).sum()),'unchanged_known_cells':int((v&known&(o==self.last)).sum())})
                self.last[v]=o[v];assert np.array_equal(self.last,self.memory.grid)
            def set_navigation_context(self,**kw):
                self.yaw=kw['yaw']
                if hasattr(self.core,'set_navigation_context'):self.core.set_navigation_context(**kw)
            def decide(self,step,position):
                if hasattr(self.core,'set_context'):self.core.set_context(step,position,self.yaw)
                assert self.pending is None
                t=time.perf_counter_ns();result=self.core.decide(step,position);elapsed=time.perf_counter_ns()-t;times['decision'].append(elapsed)
                self.decisions.append({'step':int(step),'requested':bool(result['observation_requested']),'granted':bool(result['observation_granted']),'used_before':self.used,'duration_ns':elapsed})
                self.pending=step if result['observation_granted'] else None
                return result
            def refresh(self,o,step):
                assert self.pending==step and self.used<self.cap
                t=time.perf_counter_ns();self.core.refresh(o,step);times['update'].append(time.perf_counter_ns()-t)
                self.record(o,step);self.pending=None
        kwargs['_controller_factory']=Wrapped
        for key,metric in (('_observation_provider','memory_sensor'),('_emergency_safety_sensor','emergency_sensor'),('_g1_planner','navigation_planning'),('_emergency_safety_controller','safety_decision')):
            f=kwargs.get(key)
            if f is None:continue
            def timed(*a,_f=f,_metric=metric,**kw):
                t=time.perf_counter_ns()
                try:return _f(*a,**kw)
                finally:
                    times[_metric].append(time.perf_counter_ns()-t)
                    if _metric=='memory_sensor':calls.append(int(a[0].step))
            kwargs[key]=timed
        checker=kwargs['_action_checker']
        def check(world,position,action,yaw):
            result=checker(world,position,action,yaw);core=context['agent'].core
            if result[0] and hasattr(core,'record_blocked_action'):core.record_blocked_action(position,heading_index(yaw),action)
            return result
        kwargs['_action_checker']=check
        # Evaluation's point-plan diagnostics are distinct from G1 navigation.
        from spatial_memory.navigation import plan as old_plan
        def point(*a,**kw):
            t=time.perf_counter_ns()
            try:return old_plan(*a,**kw)
            finally:times['point_planning'].append(time.perf_counter_ns()-t)
        kwargs['_planner']=point
        return original(scenario,run_config,method,**kwargs)
    ref.base.run_episode=injected;ref.base.scenario_from_bprime=scenario_adapter
    try:row,trace=ref.base.run_case(payload,schedule,'periodic' if arm=='periodic4' else 'age',cfg,with_safety=True)
    finally:ref.base.run_episode=original;ref.base.scenario_from_bprime=scenario_original
    agent=context['agent'];scansteps=[f['step'] for f in trace['steps'] if f['observation_granted']]
    assert scansteps==calls==[o['step'] for o in observations]
    assert len(calls)==row['observation_count']<=20
    assert row['g1_unselected_action_shield_queries']==0 and row['g1_shield_query_count_valid']
    assert len(times['emergency_sensor'])==row['elapsed_steps']
    diag={'timing_ns':times,'decisions':agent.decisions,'observation_log':observations,'actual_memory_call_steps':calls,'actual_memory_sensor_calls':len(calls),'actual_memory_raycasts':61*len(calls)}
    return row,ref.base._jsonable_row(trace),diag

SAVED={
 'periodic4':('age_cadence_v1/fit72','periodic'),'periodic5':('age_cadence_v1/fit72','periodic5'),
 'age4':('age_cadence_v1/fit72','age'),'age5':('age_cadence_v1/fit72','age5'),
 'age6':('caa_v1/fit72','age6'),'age_route_rescue':('age_route_v1/fit72','age_route_rescue'),
 'age_route_clock':('age_route_v1/fit72','age_route_clock'),'caa_fast':('caa_v1/fit72','caa_fast'),
 'caa_full':('caa_v1/fit72','caa_full'),'raa_defer':('raa_v1/fit72','raa_defer')}
def saved_episode(n,arm):
    if arm in SAVED:
        directory,label=SAVED[arm];return episode(ROOT/'results/phase2_mujoco'/directory,n,label)
    directory,file={'rdao_v2':('rdao_v2_viewpoint_fit72_v1','v2_traces.jsonl.gz'),'rdao_v21':('rdao_v21_current_view_quality_fit72_v1','v21_traces.jsonl.gz')}[arm]
    import gzip
    rows=[json.loads(l) for l in gzip.open(ROOT/'results/phase2_mujoco'/directory/file,'rt')]
    return rows[n-1]
