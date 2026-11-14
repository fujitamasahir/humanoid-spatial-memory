"""Evaluator-only staged contact audit; online interfaces remain unchanged."""
from __future__ import annotations
import sys,json,gzip,time,math
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from c_v21_common import write,sha,manifest,verify_manifest,commit
from spatial_memory.simulation import Scenario,World
from spatial_memory.mujoco_navigation import MujocoNavigationScene
from spatial_memory.mujoco_perception import MujocoRayPerception
from spatial_memory.dao_navigation_compat_v1_1 import DAONavigationCompatV1_1
from spatial_memory.scheduling import ObservationController
from spatial_memory.cadence_age import CadenceController
from spatial_memory.change_aware_age import ChangeAwareAgeController
from spatial_memory.emergency_safety import _reachable_proxy_cells
from dao_engineering_scenes_v1 import scenes
from run_dao_integration_v1_1 import native
import evaluate_phase2_61ray_emergency_safety_full_288 as legacy
OUT=ROOT/'results/phase2_mujoco/predictive_safety_v1'
ARMS=('periodic4','age4','age5','caa_full','dao_veto','dao_trigger','dao_route','dao_combined')


def config(horizon):
    return {'sensor':{'radius':3,'occlusion':True,'noise':0.},'update_interval':4,'unknown':'optimistic',
      'max_steps':horizon,'observation_cost':1,'max_observations':20,'common_horizon_metrics':True,
      'mujoco_cell_size_m':.75,'mujoco_timestep_seconds':.02,
      'mujoco_ray_sensor':{'range_m':6.,'horizontal_fov_deg':120.,'ray_count':61,'sample_spacing_m':.075},'g1_navigation':{}}


def factory(initial,arm,options):
    if arm.startswith('dao_'):return DAONavigationCompatV1_1(initial,mode=arm,**options)
    if arm=='caa_full':return ChangeAwareAgeController(initial,mode='caa_full',**options)
    if arm=='age5':return CadenceController(initial,'age',cadence_mode='age5',persistence=False,evi=True,
        sensor={'range_m':6.,'cell_size':.75,'horizontal_fov_deg':120.,'ray_count':61},**options)
    return ObservationController(initial,'periodic' if arm=='periodic4' else 'age',**options)


def counts_for(scene,data):
    counts={'pedestrian':0,'wall':0,'persistent_obstacle':0,'unwanted_floor':0,'robot_self':0};pairs=[]
    for i in range(data.ncon):
        c=data.contact[i];a,b=int(c.geom1),int(c.geom2);ra=a in scene._robot_geom_ids;rb=b in scene._robot_geom_ids
        if not(ra or rb):continue
        if ra and rb:key='robot_self'
        else:
            robot,other=(a,b) if ra else (b,a)
            if other in scene._ped_geom_ids:key='pedestrian'
            elif other in scene._wall_geom_ids:key='wall'
            elif other in scene._object_geom_ids.values():key='persistent_obstacle'
            elif other==scene._floor_geom_id and robot not in scene._foot_geom_ids:key='unwanted_floor'
            else:continue
        counts[key]+=1;pairs.append({'geoms':[a,b],'distance':float(c.dist),'position_m':c.pos.tolist(),'type':key})
    return counts,pairs


def run_case(definition,arm,*,candidate_class=None,detailed=True):
    scenario=Scenario.from_dict(definition);events=[];decisions=[];raw_frames=[];context={};paid=[]
    calls={'memory':0,'emergency':0,'shield':0};mode={'sweep':False,'action':None};last={'position':scenario.start,'yaw':0.}
    original={'scenario':legacy.scenario_from_bprime,'run':legacy.run_episode,'init':MujocoNavigationScene.__init__,
       'observe':MujocoRayPerception.observe,'advance':World.advance,'contacts':MujocoNavigationScene._contacts,
       'safety':legacy.EmergencySafetyController}
    def init(self,*args,**kwargs):original['init'](self,*args,**kwargs);context['scene']=self;context['shadow']=self.mj.MjData(self.model)
    def snapshot(stage,world,data=None,**extra):
        scene=context['scene'];data=data if data is not None else scene.data;counts,pairs=counts_for(scene,data)
        separation=None
        if scene._ped_geom_ids:
            separation=min(float(scene.mj.mj_geomDistance(scene.model,data,a,b,100.,np.zeros(6)))
                for a in scene._robot_geom_ids for b in scene._ped_geom_ids)
        row={'step':int(world.step),'stage':stage,'counts':counts,'minimum_geom_separation_m':separation,
             'robot_qpos':data.qpos[:7].tolist(),'pedestrian_geom_positions_m':{str(i):data.geom_xpos[i].tolist() for i in sorted(scene._ped_geom_ids)},**extra}
        if detailed:
            row['robot_collision_geometries']=[{'id':i,'type':int(scene.model.geom_type[i]),'size':scene.model.geom_size[i].tolist(),
                'position':data.geom_xpos[i].tolist(),'rotation':data.geom_xmat[i].tolist()} for i in sorted(scene._robot_geom_ids)]
            row['pedestrian_geometry']=[{'id':i,'type':int(scene.model.geom_type[i]),'size':scene.model.geom_size[i].tolist()} for i in sorted(scene._ped_geom_ids)]
            row['contact_pairs']=pairs
        events.append(row);return row
    def advance(world):
        context['world']=world;snapshot('before_environment_advance',world)
        result=original['advance'](world);snapshot('after_advance_raw_unsynchronized',world)
        scene=context['scene'];shadow=context['shadow'];scene.mj.mj_copyData(shadow,scene.model,scene.data)
        for index,mocap in enumerate(scene.pedestrian_mocaps):
            cell=scenario.pedestrians[index][world.step%len(scenario.pedestrians[index])]
            shadow.mocap_pos[mocap]=(*scene.grid_to_world(cell),0)
        for cell,mocap in scene._object_mocaps.items():shadow.mocap_pos[mocap]=(*scene.grid_to_world(cell),0 if cell in world.objects else -1000)
        scene.mj.mj_forward(scene.model,shadow)
        snapshot('after_advance_synchronized_reference',world,shadow,evaluator_only_shadow=True)
        return result
    def observe(self,world,position,yaw):
        context['world']=world;last.update(position=tuple(position),yaw=float(yaw))
        kind='memory' if self.range_m==6. else 'emergency';calls[kind]+=1
        if kind=='emergency':snapshot('before_emergency_sensor_sync',world)
        reading=original['observe'](self,world,position,yaw)
        if kind=='emergency':snapshot('after_emergency_sensor_sync',world)
        else:paid.append({'step':int(world.step),'reading':reading.tolist()})
        return reading
    def contacts(self):
        result=original['contacts'](self)
        if mode['sweep']:
            snapshot('selected_action_sweep_hypothesis',context['world'],action=mode['action'],sweep_actuality='pending_selected_shield_verdict')
        return result
    def injected(s,cfg,method,**kwargs):
        agent={}
        def make(initial,_method,**options):
            agent['core']=factory(initial,arm,options);return agent['core']
        callback=kwargs['_frame_callback'];safety=kwargs['_emergency_safety_controller'];checker=kwargs['_action_checker']
        def frame(world,f):
            result=callback(world,f);last.update(position=tuple(f['position']),yaw=float(f['heading_yaw']))
            snapshot('after_executed_action',world)
            raw_frames.append({'step':f['step'],'position':list(f['position']),'yaw':f['heading_yaw'],
                'memory':f['memory'].tolist(),'planned':f['planned']})
            return result
        def choose(memory,position,goal,yaw,selected,measurement,step,blocked):
            started=time.perf_counter_ns();answer=safety(memory,position,goal,yaw,selected,measurement,step,blocked);ns=time.perf_counter_ns()-started
            after=answer['action'] if answer else selected
            decisions.append(native({'step':step,'position':position,'yaw':yaw,'selected_before':selected,'selected_after':after,
                'measurement':measurement,'original_directional_reachable':sorted(_reachable_proxy_cells(measurement)),
                'safety_result':answer,'safety_ns':ns}))
            snapshot('after_sensing_before_action',context['world'],selected_before=selected,selected_after=after)
            return answer
        def selected_check(world,position,action,yaw):
            calls['shield']+=1;start=len(events);mode.update(sweep=True,action=action)
            try:answer=checker(world,position,action,yaw)
            finally:mode['sweep']=False
            for event in events[start:]:event['sweep_actuality']='rejected_hypothesis' if answer[0] else 'accepted_selected_sweep'
            return answer
        kwargs.update(_controller_factory=make,_frame_callback=frame,_emergency_safety_controller=choose,_action_checker=selected_check)
        row,frames=original['run'](s,cfg,method,**kwargs);context['core']=agent['core'];return row,frames
    legacy.scenario_from_bprime=lambda *_:scenario;legacy.run_episode=injected
    MujocoNavigationScene.__init__=init;MujocoRayPerception.observe=observe;World.advance=advance;MujocoNavigationScene._contacts=contacts
    if candidate_class is not None:
        def create_candidate(scene):
            obj=candidate_class(scene);context['candidate']=obj;return obj
        legacy.EmergencySafetyController=create_candidate
    try:row,trace=legacy.run_case({'mechanism':'ENGINEERING_HAND_SCENE','identity':definition['name']},0,'age',config(definition['horizon']),with_safety=True)
    finally:
        legacy.scenario_from_bprime=original['scenario'];legacy.run_episode=original['run'];legacy.EmergencySafetyController=original['safety']
        MujocoNavigationScene.__init__=original['init'];MujocoRayPerception.observe=original['observe'];World.advance=original['advance'];MujocoNavigationScene._contacts=original['contacts']
    core=context['core'];assert calls['memory']==len(paid)==row['observation_count']==core.used<=20
    assert calls['emergency']==row['emergency_safety_scans'] and calls['shield']==row['g1_actual_collision_shield_queries']
    assert row['g1_shield_query_count_valid'] and row['g1_unselected_action_shield_queries']==0
    grid=np.full((scenario.height,scenario.width),-1,np.int8);by_step={r['step']:np.asarray(r['reading']) for r in paid}
    for f in raw_frames:
        if f['step'] in by_step:
            reading=by_step[f['step']];grid[reading>=0]=reading[reading>=0]
        assert np.array_equal(grid,np.asarray(f['memory']))
    return native({'scene':definition['family'],'arm':arm,'safety':'original' if candidate_class is None else 'predictive_v1',
        'metrics':row,'trace':trace,'events':events,'decisions':decisions,'actual_calls':calls,'paid':paid,
        'raw_frames':raw_frames if detailed else [],'candidate_diagnostics':getattr(context.get('candidate'),'diagnostics',[]),'scheduler_source_unchanged':True})


def save(path,value):
    with path.open('xb') as f:f.write(gzip.compress(json.dumps(value,sort_keys=True,allow_nan=False).encode(),mtime=0))


def parity(saved,current):
    assert saved['trace']==current['trace'],'Untreated semantic trace mismatch'
    from evaluate_event_observation_fit72 import rdao_evaluator
    assert rdao_evaluator._signature(saved['metrics'])==rdao_evaluator._signature(current['metrics']),'Untreated metric mismatch'


def audit():
    target=OUT/'forensics';target.mkdir(parents=True,exist_ok=False);definition=next(s for s in scenes() if s['family']=='pedestrian');summary=[]
    try:
        for arm in ('dao_veto','dao_trigger','dao_route','dao_combined','periodic4','age4','age5'):
            e=run_case(definition,arm);matched=False
            if arm.startswith('dao_'):
                p=ROOT/f'results/phase2_mujoco/dao_integration_v1/engineering_recovery_v1_1/pedestrian_{arm}.json.gz'
                archived=json.loads(gzip.decompress(p.read_bytes()));parity(archived,e);matched=True
            save(target/f'{arm}.json.gz',e)
            actual=[x for x in e['events'] if x['stage']=='after_executed_action' and x['counts']['pedestrian']]
            environment=[x['step'] for x in e['events'] if x['stage']=='after_advance_synchronized_reference' and x['counts']['pedestrian']]
            summary.append({'arm':arm,'exact_archived_parity':matched,'post_action_contact_steps':[x['step'] for x in actual],
                'environment_reference_contact_steps':environment,'contact_pairs':e['metrics']['g1_pedestrian_contact_pairs']})
            print('Forensic replay:',arm,summary[-1],flush=True)
        write(target/'summary.json',{'status':'PARITY_VERIFIED','source_commit':commit(),'episodes':7,'replays':summary});manifest(target)
    except Exception:
        import traceback
        (target/'failure.txt').write_text(traceback.format_exc());manifest(target);raise
if __name__=='__main__':audit()
