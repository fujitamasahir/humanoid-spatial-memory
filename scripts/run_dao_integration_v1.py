"""Frozen hand-scene actual-sensor integration; no FIT or population runner."""
from __future__ import annotations
import json,sys,gzip,time,subprocess,hashlib,traceback
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from c_v21_common import sha,write,manifest,verify_manifest,commit
from spatial_memory.dao_navigation_v1 import DAONavigationV1
from spatial_memory.discovery_observation import predicted_footprints,assess,request_rule
from spatial_memory.navigation import plan
from spatial_memory.simulation import Scenario,World
from spatial_memory.mujoco_navigation import MujocoNavigationScene
from spatial_memory.mujoco_perception import MujocoRayPerception
from spatial_memory.memory import Memory
from dao_engineering_scenes_v1 import scenes
import evaluate_phase2_61ray_emergency_safety_full_288 as legacy
OUT=ROOT/'results/phase2_mujoco/dao_integration_v1'
MODES=('dao_veto','dao_trigger','dao_route','dao_combined')
SOURCES=('scripts/check_dao_infrastructure_v1.py','tests/test_dao_navigation_infrastructure_v1.py','docs/dao_generator_admission_v1.md','docs/dao_pilot_v1_protocol.md','src/spatial_memory/dao_navigation_v1.py','src/spatial_memory/discovery_observation.py',
'src/spatial_memory/dao_generator_v1.py','src/spatial_memory/dao_admission_v1.py','src/spatial_memory/dao_statistics_v1.py',
'scripts/dao_engineering_scenes_v1.py','scripts/run_dao_integration_v1.py','docs/dao_integration_v1_protocol.md',
'src/spatial_memory/evaluation.py','src/spatial_memory/navigation.py','src/spatial_memory/mujoco_perception.py',
'src/spatial_memory/mujoco_navigation.py','src/spatial_memory/emergency_safety.py',
'scripts/evaluate_phase2_61ray_emergency_safety_full_288.py')


def native(value):
    if isinstance(value,np.ndarray):return value.tolist()
    if isinstance(value,np.generic):return value.item()
    if isinstance(value,dict):return {k:native(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [native(v) for v in value]
    return value


def prediction(grid,last,step,position,yaw,goal,route=None):
    started=time.perf_counter_ns();route=plan(grid,tuple(position),tuple(goal),'optimistic') if route is None else route
    route_ns=time.perf_counter_ns()-started
    f=predicted_footprints(grid,position,yaw);detail=assess(grid,last,step,position,yaw,route=route)
    return {'step':step,'position':list(position),'yaw':yaw,'route':route[:6],
            'footprints':{name:sorted(f[name]) for name in ('optimistic','frontier')},
            'predicted_new':{name:sorted(c for c in f[name] if grid[c[1],c[0]]==-1) for name in ('optimistic','frontier')},
            'detail':detail,'diagnostic_point_plan_ns':route_ns,'computed_before_actual_reading':True}


def realized(pred,observation,grid,last,step,position):
    visible=observation>=0;known=last>=0;new=visible&~known;changed=visible&known&(observation!=grid)
    stale=visible&known&((step-last)>=5)
    cells=lambda mask:[[int(x),int(y)] for y,x in np.argwhere(mask)]
    actual_new={tuple(c) for c in cells(new)}-{tuple(position)};route=pred['route'][1:6]
    pred.update(actual_observed_cells=cells(visible),actual_observation_values=[int(observation[y,x]) for x,y in cells(visible)],
        actual_new_cells=cells(new),actual_changed_known_cells=cells(changed),actual_stale_verified_cells=cells(stale),
        actual_route_new=sum(any(abs(x-a)+abs(y-b)<=1 for a,b in route) for x,y in actual_new),metrics={})
    for name in ('frontier','optimistic'):
        p=set(map(tuple,pred['predicted_new'][name]));common=len(p&actual_new)
        pred['metrics'][name]={'predicted':len(p),'actual_comparable':len(actual_new),
          'precision':common/len(p) if p else None,'recall':common/len(actual_new) if actual_new else None,
          'signed_error':len(p)-len(actual_new),'absolute_error':abs(len(p)-len(actual_new)),
          'route_predicted':pred['detail'][name]['route_new']}
    return native(pred)


def run_navigation(definition,mode):
    scenario=Scenario.from_dict(definition);context={};scans=[];calls={'memory':0,'emergency':0,'shield':0};frames=[]
    original_case=legacy.scenario_from_bprime;original_run=legacy.run_episode;original_observe=MujocoRayPerception.observe
    def counted(self,*args):
        calls['memory' if self.range_m==6. else 'emergency']+=1
        return original_observe(self,*args)
    def injected(s,config,method,**kwargs):
        def factory(initial,method,**options):
            c=DAONavigationV1(initial,method,mode=mode,**options);context['agent']=c;return c
        provider=kwargs['_observation_provider'];checker=kwargs['_action_checker'];callback=kwargs['_frame_callback']
        def measured(world,position,yaw):
            c=context.get('agent');g=c.memory.grid if c else np.full((s.height,s.width),-1,dtype=np.int8)
            last=c.last_observed if c else np.full(g.shape,-1,dtype=np.int64)
            pred=prediction(g,last,int(world.step),position,yaw,s.goal,c.last_route if c and c.mode=='dao_route' else None)
            assert c is None or c._pending==world.step
            observation=provider(world,position,yaw)
            scans.append(realized(pred,observation,g,last,int(world.step),position));return observation
        def selected(*args):calls['shield']+=1;return checker(*args)
        def capture(world,frame):
            result=callback(world,frame);frames.append({'step':frame['step'],'position':frame['position'],
                'yaw':frame['heading_yaw'],'memory':frame['memory'].tolist()});return result
        kwargs.update(_controller_factory=factory,_observation_provider=measured,_action_checker=selected,_frame_callback=capture)
        return original_run(s,config,method,**kwargs)
    legacy.scenario_from_bprime=lambda *_:scenario;legacy.run_episode=injected;MujocoRayPerception.observe=counted
    config={'sensor':{'radius':3,'occlusion':True,'noise':0.},'update_interval':4,'unknown':'optimistic',
        'max_steps':definition['horizon'],'observation_cost':1,'max_observations':20,'common_horizon_metrics':True,
        'mujoco_cell_size_m':.75,'mujoco_timestep_seconds':.02,
        'mujoco_ray_sensor':{'range_m':6.,'horizontal_fov_deg':120.,'ray_count':61,'sample_spacing_m':.075},'g1_navigation':{}}
    try:row,trace=legacy.run_case({'mechanism':'ENGINEERING_HAND_SCENE','identity':definition['name']},0,'age',config,with_safety=True)
    finally:legacy.scenario_from_bprime=original_case;legacy.run_episode=original_run;MujocoRayPerception.observe=original_observe
    c=context['agent'];assert calls['memory']==len(scans)==row['observation_count']==c.used<=20
    assert calls['emergency']==row['emergency_safety_scans']
    assert calls['shield']==row['g1_actual_collision_shield_queries'] and row['g1_shield_query_count_valid'] and row['g1_unselected_action_shield_queries']==0
    remembered=np.full((scenario.height,scenario.width),-1,dtype=np.int8)
    scan_by={s['step']:s for s in scans}
    for frame in frames:
        if frame['step'] in scan_by:
            scan=scan_by[frame['step']]
            for (x,y),v in zip(scan['actual_observed_cells'],scan['actual_observation_values']):remembered[y,x]=v
        assert np.array_equal(remembered,np.asarray(frame['memory']))
    return native({'scene':definition['family'],'mode':mode,'metrics':row,'trace':trace,'scans':scans,
        'decisions':c.decisions,'actual_calls':calls,'memory_rays':61*calls['memory'],'emergency_rays':61*calls['emergency'],
        'route_plan_calls':c.route_plan_calls,'route_plan_ms':c.route_plan_ns/1e6,'scheduler_ms':c.scheduler_ns/1e6})


def run_probe(definition):
    s=Scenario.from_dict(definition);world=World(s);scene=MujocoNavigationScene(s)
    sensor=MujocoRayPerception(scene,range_m=6.,horizontal_fov_deg=120.,ray_count=61,sample_spacing_m=.075)
    memory=Memory((s.height,s.width));last=np.full(memory.grid.shape,-1,dtype=np.int64);scans=[];last_scan=0
    for step,yaw in definition['probe_schedule']:
        while world.step<step:world.advance()
        pred=prediction(memory.grid,last,step,s.start,yaw,s.goal)
        pred['hypothetical_rules']={m:request_rule(pred['detail'],step,step-last_scan,m) for m in MODES}
        # These are explicitly authorized fixture scans, NEVER policy-grant counts.
        observation=sensor.observe(world,s.start,yaw)
        scans.append(realized(pred,observation,memory.grid,last,step,s.start))
        memory.update(observation);last[observation>=0]=step;last_scan=step
    return {'scene':definition['family'],'role':'AUTHORIZED_FIXTURE_DIAGNOSTIC_NOT_NAVIGATION_POLICY',
            'fixture_scan_calls':len(scans),'fixture_rays':61*len(scans),'shield_calls':0,'scans':scans}


def prepare():
    target=OUT/'prepared';target.mkdir(parents=True,exist_ok=False);write(target/'scenes.json',scenes())
    command=[sys.executable,'-m','pytest','-q','tests/test_dao_navigation_infrastructure_v1.py',
       'tests/test_discovery_observation.py','tests/test_dao_artifacts.py','tests/test_change_aware_age.py',
       'tests/test_caa_integration.py','tests/test_cadence_age.py','tests/test_phase2_mujoco.py',
       'tests/test_phase2_emergency_safety.py','tests/test_persistence_evi_evaluation.py',f'--junitxml={target/"tests.xml"}']
    r=subprocess.run(command,cwd=ROOT,text=True,capture_output=True);(target/'tests.log').write_text(r.stdout+r.stderr)
    write(target/'gate.json',{'returncode':r.returncode,'command':command});manifest(target)
    if r.returncode:raise RuntimeError(r.stdout+r.stderr)
    write(OUT/'binding.json',{'sources':{p:sha(ROOT/p) for p in SOURCES},'scenes_sha256':sha(target/'scenes.json'),
      'prepared_manifest_sha256':sha(target/'artifact_manifest.json'),'navigation_episodes':48,'fixture_scans':120})
    print(r.stdout)


def gate():
    b=json.loads((OUT/'binding.json').read_text());assert b['sources']=={p:sha(ROOT/p) for p in SOURCES}
    verify_manifest(OUT/'prepared');assert sha(OUT/'prepared/scenes.json')==b['scenes_sha256']
    assert json.loads((OUT/'prepared/gate.json').read_text())['returncode']==0
    for p,h in {**b['sources'],'results/phase2_mujoco/dao_integration_v1/prepared/scenes.json':b['scenes_sha256'],
                'results/phase2_mujoco/dao_integration_v1/binding.json':sha(OUT/'binding.json')}.items():
        assert hashlib.sha256(subprocess.check_output(['git','show',f'HEAD:{p}'],cwd=ROOT)).hexdigest()==h,p


def formal():
    gate();target=OUT/'engineering';target.mkdir(parents=True,exist_ok=False);summaries=[]
    definitions=json.loads((OUT/'prepared/scenes.json').read_text())
    try:
        for d in definitions:
            for mode in MODES:
                result=run_navigation(d,mode);p=target/f'{d["family"]}_{mode}.json.gz'
                with p.open('xb') as f:f.write(gzip.compress(json.dumps(result,sort_keys=True,allow_nan=False).encode(),mtime=0))
                summaries.append({'scene':d['family'],'mode':mode,'paid':result['metrics']['observation_count'],
                    'goals':int(result['metrics']['success']),'contacts':result['metrics']['g1_unwanted_contact_pairs']})
            write(target/f'{d["family"]}_fixture.json',native(run_probe(d)))
            print('Completed hand-defined engineering scene:',d['family'],flush=True)
        write(target/'summary.json',{'status':'PASS_ENGINEERING_ACCOUNTING','source_freeze_commit':commit(),
            'navigation_episodes':len(summaries),'fixture_scans':120,'episodes':summaries,
            'production_population_payloads':0,'full_FIT72_screens':0});manifest(target)
    except Exception:
        (target/'failure.txt').write_text(traceback.format_exc());manifest(target);raise
if __name__=='__main__':{'prepare':prepare,'formal':formal}[sys.argv[1]]()
