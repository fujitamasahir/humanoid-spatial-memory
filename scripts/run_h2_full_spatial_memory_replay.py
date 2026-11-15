#!/usr/bin/env python3
"""Versioned H2 full-memory replay recovery; does not alter controllers."""
from __future__ import annotations

import argparse, base64, csv, gzip, hashlib, json, os, platform, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'src')]
OUT = ROOT / 'results/phase2_mujoco/h2_full_spatial_memory_replay_v1'
PARENT = 'e2d244583c8c832d6af137c2d93c848e6bf3136a'
BLOCKED = {'c_route3', 'c_routek', 'c_topology3c'}
OLD12 = ('periodic4','periodic5','age4','age5','age6','age_route_rescue',
         'age_route_clock','rdao_v2','rdao_v21','caa_fast','caa_full','raa_defer')
FORBIDDEN_STATE_KEYS = {'world','scenario','truth','ground_truth','geometry','rng',
                        'sensor','renderer','scene','qpos','qvel','callback','provider'}

def sha_bytes(raw: bytes) -> str: return hashlib.sha256(raw).hexdigest()
def sha(path: Path) -> str: return sha_bytes(path.read_bytes())
def jwrite(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as f:
        json.dump(value, f, sort_keys=True, indent=2, allow_nan=False); f.write('\n')
        f.flush(); os.fsync(f.fileno())
def pack_grid(grid):
    import numpy as np
    a = np.asarray(grid, dtype=np.int8)
    if a.shape != (25, 25) or not np.isin(a, (-1,0,1)).all():
        raise ValueError('Expected 25x25 ternary memory')
    flat = a.ravel(order='C').astype(np.int16) + 1
    packed = np.zeros((flat.size + 3)//4, dtype=np.uint8)
    for i in range(4): packed[:len(flat[i::4])] |= (flat[i::4].astype('uint8') & 3) << (2*i)
    return base64.b64encode(packed.tobytes()).decode('ascii')

def _safe_state(value, depth=0, seen=None):
    """Serialize model-owned state only; never serialize simulator/world objects."""
    import numpy as np
    if seen is None: seen = set()
    if value is None or isinstance(value, (str, bool, int)): return value
    if isinstance(value, float): return value if value == value and abs(value) != float('inf') else None
    if depth > 6: return {'unavailable':'depth_limit'}
    ident = id(value)
    if ident in seen: return {'unavailable':'cycle'}
    if isinstance(value, np.ndarray):
        arr = np.asarray(value)
        if arr.shape == (25,25) and np.isin(arr, (-1,0,1)).all():
            return {'encoding':'ternary_2bit_base64_y_major','shape':[25,25],
                    'data':pack_grid(arr)}
        if arr.size > 4096: return {'shape':list(arr.shape),'dtype':str(arr.dtype),'unavailable':'large_array'}
        return {'shape':list(arr.shape),'dtype':str(arr.dtype),'values':arr.tolist()}
    if isinstance(value, (list,tuple)):
        seen.add(ident); out=[_safe_state(x,depth+1,seen) for x in value[:4096]]; seen.remove(ident); return out
    if isinstance(value, (set,frozenset)):
        return [_safe_state(x,depth+1,seen) for x in sorted(value,key=repr)[:4096]]
    if isinstance(value, dict):
        seen.add(ident); out={str(k):_safe_state(v,depth+1,seen) for k,v in value.items()
                              if str(k).lower() not in FORBIDDEN_STATE_KEYS}; seen.remove(ident); return out
    module=value.__class__.__module__
    if module.startswith('spatial_memory') or value.__class__.__name__ in ('Memory','AdaptiveParameters','EVIParameters','PersistenceParameters'):
        attrs=getattr(value,'__dict__',{})
        seen.add(ident); out={'type':value.__class__.__name__,
            'state':{str(k):_safe_state(v,depth+1,seen) for k,v in attrs.items()
                     if str(k).lower().strip('_') not in FORBIDDEN_STATE_KEYS
                     and not any(bad in str(k).lower() for bad in ('sensor','renderer','scene','rng','callback','provider'))}}
        seen.remove(ident); return out
    return {'type':value.__class__.__name__,'unavailable':'non_model_object'}

def _controller_state(agent):
    core = getattr(agent, 'core', agent)
    return _safe_state(core)

def audit():
    """Read-only audit of source replay completeness and known FIT72 files."""
    import h2_high_frequency_dynamics as engine
    import h2_comprehensive_adapters as adapters
    registry=json.loads((ROOT/'results/phase2_mujoco/h2_comprehensive_benchmark_v1/protocol/model_registry.json').read_text())
    expected={x['model_id'] for x in registry if x['model_id'] not in BLOCKED}
    maps_a=engine.source_maps()
    import phase2_mujoco_navigation as nav
    maps_b=nav.admitted_worlds()
    fit_identities={p['identity'] for p in maps_b}
    audit_rows=[]; roots=[]
    for stage,root in [('task_a_history',ROOT/'results/phase2_mujoco/h2_final_generalization_v1/primary'),
                       ('task_b_history',ROOT/'results/phase2_mujoco')]:
        files=sorted(root.rglob('*.json.gz')) if root.is_dir() else []
        if root.name=='primary':
            seen={}
            for p in files:
                try:
                    with gzip.open(p,'rt',encoding='utf-8') as f:d=json.load(f)
                    row=d.get('row',{}); trace=d.get('trace',{}); steps=trace.get('steps',[])
                    arm=p.name.removeprefix('episode_').split('_',1)[-1].removesuffix('.json.gz')
                    has_memory=bool(steps) and all(any(k in s for k in ('spatial_memory','memory','spatial_memory_ternary_packed_2bit_base64')) for s in steps)
                    seen[arm]=seen.get(arm,0)+1
                except Exception: continue
            for model in OLD12:
                count=seen.get(model,0)
                audit_rows.append({'scope':stage,'model_id':model,'expected_episodes':72,
                    'historical_files_found':count,'complete_step_memory':False if count else None,
                    'classification':'historical_result_without_full_spatial_memory' if count else 'no_historical_result_found'})
        else:
            # A conservative key-level scan. Files are not treated as FIT72
            # matches unless their embedded map/schedule/condition identify it.
            keyed={m:set() for m in expected}; mem_ok={m:set() for m in expected}
            aliases={'periodic':'periodic4','age':'age4','age-route-rescue':'age_route_rescue',
                     'age-route-clock':'age_route_clock','caa-fast':'caa_fast','caa-full':'caa_full',
                     'raa-defer':'raa_defer','rdao-v21':'rdao_v21','rdao-v2':'rdao_v2',
                     'c-ternary':'c_ternary','b+age':'b_age','b_age':'b_age','c-k':'c_k',
                     'c0':'c0_audit','c-topology3-d':'c_topology3d','ms-k':'ms_k',
                     'ms-k-visibility':'ms_k_visibility','ms-topology':'ms_topology',
                     'ms-topology-visibility':'ms_topology_visibility'}
            for p in files:
                try:
                    with gzip.open(p,'rt',encoding='utf-8') as f:d=json.load(f)
                    replay=d.get('replay',{}); row=d.get('row',{})
                    trace=d.get('trace',{}); trace_key=trace.get('key') or replay.get('episode_key') or []
                    ident=d.get('map_identity') or replay.get('map') or (trace_key[0] if trace_key else None)
                    if ident not in fit_identities: continue
                    schedule=d.get('schedule',replay.get('schedule',trace_key[1] if len(trace_key)>1 else None))
                    if schedule not in (0,1): continue
                    raw_arm=(d.get('arm') or replay.get('arm') or row.get('comprehensive_arm') or
                             (trace_key[2] if len(trace_key)>2 else None) or row.get('method'))
                    raw=str(raw_arm).lower().replace(' ','-') if raw_arm is not None else ''
                    candidates=[raw,raw.replace('-','_'),p.name.removeprefix('episode_').split('_',1)[-1].removesuffix('.json.gz').lower()]
                    candidates += [aliases.get(x) for x in candidates if aliases.get(x)]
                    arm=next((x for x in candidates if x in expected),None)
                    path_text=str(p).lower()
                    if raw in ('age','periodic'):
                        if 'age_cadence_v1' in path_text: arm={'age':'age4','periodic':'periodic4'}[raw]
                        elif 'age_route_v1' in path_text and raw=='age': arm='age4'
                    if arm not in expected: continue
                    if d.get('condition') not in (None,'original'): continue
                    key=(ident,int(schedule));keyed[arm].add(key)
                    steps=replay.get('steps',trace.get('steps',[]))
                    if steps and all(('spatial_memory_end_of_step_packed_2bit_base64' in s or
                                      'spatial_memory_ternary_packed_2bit_base64' in s) and
                                     'spatial_memory_before_observation_update_packed_2bit_base64' in s and
                                     'spatial_memory_after_observation_update_packed_2bit_base64' in s
                                     for s in steps): mem_ok[arm].add(key)
                except Exception: continue
            for model in sorted(expected):
                audit_rows.append({'scope':stage,'model_id':model,'expected_episodes':72,
                    'historical_keyed_episodes_found':len(keyed[model]),
                    'complete_step_memory_episodes_found':len(mem_ok[model]),
                    'classification':('historical_replay_available_memory_missing_or_incomplete'
                        if keyed[model] and len(mem_ok[model])<len(keyed[model]) else
                        'complete_replay_candidate_requires_protocol_parity' if keyed[model] else
                        'no_keyed_known_fit72_result_found')})
    OUT.mkdir(parents=True,exist_ok=True)
    csvpath=OUT/'historical_replay_audit.csv'
    if csvpath.exists(): raise FileExistsError(csvpath)
    with csvpath.open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=sorted({k for r in audit_rows for k in r}));writer.writeheader();writer.writerows(audit_rows)
    report={'status':'AUDIT_ONLY','parent_commit':PARENT,'branch':subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip(),
        'task_a_saved_maps':len(maps_a),'task_a_expected_episodes':len(maps_a)*2*len(OLD12),
        'task_b_admitted_fit_maps':len(maps_b),'task_b_expected_models':len(expected),
        'task_b_expected_episodes':len(maps_b)*2*len(expected),'excluded_blocked_models':sorted(BLOCKED),
        'known_h2_comprehensive_original_replays':len(list((ROOT/'results/phase2_mujoco/h2_comprehensive_benchmark_v1/original_environment').rglob('*.json.gz'))),
        'known_h2_comprehensive_maps':'unseen H2 maps; not a FIT72 identity match',
        'note':'Audit is conservative; a model-name match alone is not treated as a replay match.',
        'csv':csvpath.relative_to(ROOT).as_posix(),'generated_utc':datetime.now(timezone.utc).isoformat()}
    jwrite(OUT/'historical_replay_audit.json',report)
    print(json.dumps(report,indent=2));return report

def load_binding():
    p=active_binding_path()
    if not p.is_file(): raise FileNotFoundError('Prepare a binding after source/map audit first')
    b=json.loads(p.read_text())
    if b['status'] not in ('READY','RUNNING','PARTIAL'): raise RuntimeError('Binding not runnable')
    for rel,digest in b['source_sha256'].items():
        if sha(ROOT/rel)!=digest: raise RuntimeError(f'Source commitment changed: {rel}')
    return b

def active_binding_path():
    pointer=OUT/'active_binding.json'
    if not pointer.is_file():return OUT/'binding.json'
    active=json.loads(pointer.read_text());p=OUT/active['path']
    if sha(p)!=active['sha256']:raise RuntimeError('Active binding pointer hash mismatch')
    return p

def amend_binding():
    pointer=OUT/'active_binding.json';parent=active_binding_path()
    if not (OUT/'binding.json').is_file():raise FileNotFoundError('Initial binding missing')
    amendments=sorted(OUT.glob('binding_amendment_*.json'),key=lambda p:int(p.stem.rsplit('_',1)[1]))
    version=int(amendments[-1].stem.rsplit('_',1)[1])+1 if amendments else 1
    target=OUT/f'binding_amendment_{version}.json'
    if target.exists():raise FileExistsError(target)
    old=json.loads(parent.read_text())
    src=set(old['source_sha256'])
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    if subprocess.run(['git','merge-base','--is-ancestor',old['bound_at_commit'],head],cwd=ROOT).returncode:
        raise RuntimeError('Current source commit does not descend from binding commit')
    updated=dict(old);updated['parent_binding_sha256']=sha(parent);updated['bound_at_commit']=head
    updated['status']='PARTIAL';updated['amendment_reason']='Append-only source/hash amendment for corrected full replay capture semantics.'
    updated['source_sha256']={name:sha(ROOT/name) for name in sorted(src)}
    updated['amended_utc']=datetime.now(timezone.utc).isoformat()
    jwrite(target,updated);jwrite(pointer,{'path':target.name,'sha256':sha(target),'parent_binding_sha256':sha(parent)})
    print('Created append-only binding amendment; parent binding preserved.')

def bind():
    if (OUT/'binding.json').exists(): raise FileExistsError('Binding already exists')
    import h2_high_frequency_dynamics as engine
    import h2_comprehensive_adapters as adapters
    import h2_final_common as frozen
    from verify_dao_integrity import verify
    from run_h2_comprehensive_benchmark import verify_manifests
    import phase2_mujoco_navigation as nav
    maps_a=engine.source_maps(); maps_b=nav.admitted_worlds()
    if len(maps_a)!=36 or len(maps_b)!=36 or len(adapters.ADDITIONAL)!=41: raise RuntimeError('Map/model inventory mismatch')
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    if subprocess.run(['git','merge-base','--is-ancestor',PARENT,head],cwd=ROOT).returncode:
        raise RuntimeError('Current commit does not descend from the declared parent')
    integrity=verify()
    if integrity.get('status')!='PASS': raise RuntimeError(f'Preservation check failed: {integrity}')
    oldb=ROOT/'results/phase2_mujoco/h2_final_generalization_v1/binding.json'
    compb=ROOT/'results/phase2_mujoco/h2_comprehensive_benchmark_v1/active_binding.json'
    src={
      'scripts/run_h2_full_spatial_memory_replay.py','scripts/h2_high_frequency_dynamics.py','scripts/h2_final_common.py',
      'scripts/h2_comprehensive_adapters.py','scripts/evaluate_phase2_61ray_emergency_safety_full_288.py',
      'scripts/phase2_mujoco_navigation.py','src/spatial_memory/evaluation.py','src/spatial_memory/simulation.py',
      'src/spatial_memory/mujoco_navigation.py','src/spatial_memory/mujoco_perception.py','src/spatial_memory/emergency_safety.py',
      'src/spatial_memory/navigation.py','docs/h2_full_spatial_memory_replay_protocol_v1.md',
      'docs/h2_full_spatial_memory_replay_schema.md','results/phase2_mujoco/h2_comprehensive_benchmark_v1/protocol/model_registry.json',
      'results/phase2_mujoco/h2_final_generalization_v1/maps/summary.json',
      'tests/test_h2_full_spatial_memory_replay.py'}
    src.update(str(p.relative_to(ROOT)) for p in (ROOT/'src/spatial_memory').glob('*.py'))
    maps=[]
    for ds,records in [('task_a',maps_a),('task_b',[(p,sha_bytes(json.dumps(p,sort_keys=True,separators=(',',':')).encode())) for p in maps_b])]:
        for p,d in records: maps.append({'dataset':ds,'identity':p['identity'],'sha256':d})
    OUT.mkdir(parents=True,exist_ok=True)
    b={'protocol':'h2_full_spatial_memory_replay_protocol_v1','status':'READY','parent_commit':PARENT,
       'bound_at_commit':head,'branch':'phase2/mujoco-proxy-pilot','python':sys.version,
       'platform':platform.platform(),'source_sha256':{p:sha(ROOT/p) for p in sorted(src)},
       'parent_binding_sha256':sha(oldb),'comprehensive_binding_pointer_sha256':sha(compb) if compb.exists() else None,
       'task_a':{'models':list(OLD12),'maps':36,'schedules':[0,1],'episodes':864},
       'task_b':{'models':54,'maps':36,'schedules':[0,1],'condition':'original','episodes':3888,
                 'blocked_models':sorted(BLOCKED)},'seed':42,'max_steps':80,'max_observations':20,
       'maps':maps,'preservation_gate':integrity,'historical_manifests_verified':verify_manifests(),
       'created_utc':datetime.now(timezone.utc).isoformat(),'new_evaluation_classification':'descriptive replay recovery'}
    jwrite(OUT/'binding.json',b)
    print('Bound recovery protocol. No episode was executed.')

def recover_case(payload,schedule,arm,dataset,condition='original'):
    import numpy as np
    import h2_high_frequency_dynamics as engine
    import h2_comprehensive_adapters as adapters
    import h2_final_common as frozen
    from spatial_memory import evaluation as ev
    ctx={'steps':{},'observations':{},'initial':None,'agent':None}
    old_eval=ev.run_episode;old_run_original=engine.run_original_case;old_frozen_run=frozen.run_case
    def monitored_eval(scenario,config,method,**kwargs):
        original_factory=kwargs.get('_controller_factory')
        if original_factory is None: raise RuntimeError('Missing frozen controller factory')
        class Monitor:
            def __init__(self,*args,**kw):
                self.target=original_factory(*args,**kw);ctx['agent']=self
                ctx['steps'][0]={'before_decision':None,'after_decision':None,
                    'before_update':None,'after_update':_grid(self.target),
                    'state_after_update':_controller_state(self.target)}
            def __getattr__(self,name):return getattr(self.target,name)
            def decide(self,step,position):
                item=ctx['steps'].setdefault(int(step),{})
                item['before_decision']=_grid(self.target);item['state_before_decision']=_controller_state(self.target)
                result=self.target.decide(step,position)
                item['after_decision']=_grid(self.target);item['state_after_decision']=_controller_state(self.target)
                item['observation_requested']=bool(result.get('observation_requested'))
                item['observation_granted']=bool(result.get('observation_granted'))
                return result
            def refresh(self,observation,step):
                item=ctx['steps'].setdefault(int(step),{})
                item['before_update']=_grid(self.target)
                result=self.target.refresh(observation,step)
                item['after_update']=_grid(self.target);item['state_after_update']=_controller_state(self.target)
                return result
        kwargs['_controller_factory']=Monitor
        provider=kwargs.get('_observation_provider')
        if provider:
            def seen(world,pos,yaw):
                result=provider(world,pos,yaw);ctx['observations'][int(world.step)]=np.asarray(result,dtype=np.int8).copy();return result
            kwargs['_observation_provider']=seen
        initial_cb=kwargs.get('_initial_observation_callback')
        if initial_cb:
            def initial(observation,step,pos):
                ctx['observations'][int(step)]=np.asarray(observation,dtype=np.int8).copy();return initial_cb(observation,step,pos)
            kwargs['_initial_observation_callback']=initial
        return old_eval(scenario,config,method,**kwargs)
    def _grid(target):
        import numpy as np
        arr=getattr(getattr(target,'memory',None),'grid',None)
        if arr is None: raise RuntimeError('Controller does not expose its current memory grid')
        return np.asarray(arr,dtype=np.int8).copy()
    def enrich(payload0,schedule0,arm0,row,trace):
        source_trace=ctx.get('source_trace') or {}
        original_by_step={int(x['step']):x for x in source_trace.get('steps',[])}
        for frame in trace.get('steps',[]):
            t=int(frame['step']);state=ctx['steps'].get(t,{})
            old_frame=original_by_step.get(t,{})
            prior_frame=original_by_step.get(t-1,old_frame)
            observed=ctx['observations'].get(t)
            if t==0:
                frame['spatial_memory_before_observation_decision_packed_2bit_base64']=None
                frame['spatial_memory_before_observation_update_packed_2bit_base64']=None
                frame['spatial_memory_after_observation_update_packed_2bit_base64']=pack_grid(state['after_update'])
                frame['controller_state_before_decision']=None
                frame['controller_state_after_decision']=None
                frame['controller_state_after_observation_update']=state.get('state_after_update')
                frame['pre_observation_memory_status']='controller_not_initialized_before_initial_observation'
            else:
                before=state.get('before_decision')
                before_update=state.get('before_update',state.get('after_decision'))
                after_update=state.get('after_update',before_update)
                frame['spatial_memory_before_observation_decision_packed_2bit_base64']=pack_grid(before)
                frame['spatial_memory_before_observation_update_packed_2bit_base64']=pack_grid(before_update)
                frame['spatial_memory_after_observation_update_packed_2bit_base64']=pack_grid(after_update)
                frame['controller_state_before_decision']=state.get('state_before_decision')
                frame['controller_state_after_decision']=state.get('state_after_decision')
                frame['controller_state_after_observation_update']=state.get('state_after_update',state.get('state_after_decision'))
                frame['pre_observation_memory_status']='captured'
            frame['observed_grid_ternary_packed_2bit_base64']=None if observed is None else pack_grid(observed)
            frame['selected_action']=old_frame.get('action',frame.get('executed_action'))
            frame['selected_action_reason']=old_frame.get('action_reason')
            frame['robot_position_after_action_xy']=old_frame.get('position',frame.get('robot_position_after_action_xy'))
            frame['robot_position_before_action_xy']=prior_frame.get('position',frame.get('robot_position_before_action_xy'))
            frame['robot_heading_after_action_rad']=old_frame.get('heading_yaw',frame.get('robot_heading_after_action_rad'))
            frame['robot_heading_before_action_rad']=prior_frame.get('heading_yaw',frame.get('robot_heading_before_action_rad'))
            yaw_changed=(frame['robot_heading_after_action_rad'] != frame['robot_heading_before_action_rad'])
            frame['executed_action_applied']=bool(old_frame.get('moved') or yaw_changed or
                                                   (frame['selected_action'] and frame['selected_action'][0]=='wait'))
            frame['execution_status']=('rejected_by_safety_or_collision_check' if old_frame.get('blocked') else
                                       'applied' if frame['executed_action_applied'] else 'no_transition')
            frame['executed_action']=frame['selected_action'] if frame['executed_action_applied'] else None
            frame['spatial_memory_end_of_step_packed_2bit_base64']=frame.get('spatial_memory_ternary_packed_2bit_base64')
        return trace
    def monitored_original(p,s,a):
        row,replay,diagnostics=old_run_original(p,s,a)
        return row,enrich(p,s,a,row,replay),diagnostics
    def capture_trace(*args,**kwargs):
        row,trace,diagnostics=old_frozen_run(*args,**kwargs)
        ctx['source_trace']=trace
        return row,trace,diagnostics
    engine.run_original_case=monitored_original
    frozen.run_case=capture_trace
    ev.run_episode=monitored_eval
    engine._extend_frozen_arms()
    try:
        if arm in adapters.ADDITIONAL:
            result=adapters.run_case(payload,schedule,arm,'original')
        else:
            result=engine.run_original_case(payload,schedule,arm)
    finally:
        ev.run_episode=old_eval;engine.run_original_case=old_run_original;frozen.run_case=old_frozen_run
    row,replay,diagnostics=result
    if len(replay['steps'])!=int(row['elapsed_steps'])+1:raise RuntimeError('Replay step count mismatch')
    if any(not s.get('spatial_memory_end_of_step_packed_2bit_base64') for s in replay['steps']):raise RuntimeError('Missing end-of-step memory')
    replay['dataset']=dataset;replay['condition']=condition;replay['map_identity']=payload['identity']
    replay['replay_recovery']={'source_binding_sha256':sha(active_binding_path()),
        'memory_capture':'live controller snapshots, evaluator-side and not passed to policy',
        'classification':'replay_recovery'}
    return row,replay,diagnostics,ctx.get('source_trace')

def _atomic_episode(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    raw=json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    packed=gzip.compress(raw,mtime=0);tmp=path.with_suffix(path.suffix+'.tmp')
    with tmp.open('xb') as f:f.write(packed);f.flush();os.fsync(f.fileno())
    if path.exists():tmp.unlink();raise FileExistsError(path)
    os.replace(tmp,path);return len(packed),sha_bytes(packed)

def run(task,resume=False,limit=None):
    binding=load_binding();import h2_high_frequency_dynamics as engine
    import h2_comprehensive_adapters as adapters
    import h2_final_common as frozen
    from run_h2_final import parity
    import phase2_mujoco_navigation as nav
    if task=='a':
        maps=[x[0] for x in engine.source_maps()];arms=list(OLD12);dataset='h2_unseen'
        target=OUT/'task_a'
    else:
        maps=nav.admitted_worlds(); arms=[x['model_id'] for x in json.loads((ROOT/'results/phase2_mujoco/h2_comprehensive_benchmark_v1/protocol/model_registry.json').read_text()) if x['authorization_status'] in ('historical','eligible') and x['model_id'] not in BLOCKED]
        if len(arms)!=54:raise RuntimeError('Expected exactly 54 non-blocked registry arms')
        dataset='fit72_known';target=OUT/'task_b'
    expected=len(maps)*2*len(arms);journal=target/'journal.jsonl'
    target.mkdir(parents=True,exist_ok=True)
    committed={}
    if journal.exists():
        for line in journal.read_text().splitlines():
            e=json.loads(line)
            if e['event']=='episode_committed': committed[e['path']]=e['sha256']
    existing=list((target/'episodes').rglob('*.json.gz')) if (target/'episodes').exists() else []
    if existing and not resume:raise RuntimeError('Existing output requires --resume')
    for p in existing:
        rel=p.relative_to(OUT).as_posix()
        if rel not in committed or sha(p)!=committed[rel]:raise RuntimeError(f'Unjournaled or modified checkpoint: {rel}')
    source_files=sorted(binding['source_sha256'])
    byid={m['identity']:m for m in maps};cases=[]
    for mi,payload in enumerate(maps,1):
        for schedule in (0,1):
            for arm in arms:
                cases.append((mi,payload,schedule,arm))
    if limit is not None:cases=cases[:limit]
    done=0;started=time.monotonic();last=started
    for mi,payload,schedule,arm in cases:
        safe=payload['identity'].replace(':','_').replace('/','_')
        rel=f'{target.name}/episodes/{arm}/{safe}_s{schedule}_seed42.json.gz'
        path=OUT/rel
        if path.exists():
            if rel not in committed or sha(path)!=committed[rel]:raise RuntimeError(f'Existing record failed journal: {rel}')
            done+=1;continue
        row,replay,diag,source_trace=recover_case(payload,schedule,arm,dataset)
        parity_status='NO_COMPATIBLE_HISTORICAL_RESULT'
        parity_detail=None
        case_number=(mi-1)*2+schedule+1
        try:
            from run_h2_final import compare_saved
            saved=None
            if task=='a':
                old=ROOT/f'results/phase2_mujoco/h2_final_generalization_v1/primary/episode_{case_number:03d}_{arm}.json.gz'
                if old.is_file():
                    with gzip.open(old,'rt',encoding='utf-8') as f:saved=json.load(f)
            elif arm in frozen.SAVED or arm in ('rdao_v2','rdao_v21'):
                saved=frozen.saved_episode(case_number,arm)
            if saved is not None and source_trace is not None:
                compare_saved(saved,row,source_trace);parity_status='PASS_EXACT_TRACE_AND_METRIC_SIGNATURE'
        except Exception as exc:
            parity_status='MISMATCH';parity_detail=f'{type(exc).__name__}: {exc}'
        replay['replay_recovery']['parity_status']=parity_status
        record={'dataset':dataset,'condition':'original','arm':arm,'map_identity':payload['identity'],
            'map_index':mi,'schedule':schedule,'seed':42,'schema':'h2_full_spatial_memory_replay_v1',
            'row':row,'replay':replay,'diagnostics':diag,'source_trace_for_exact_parity':source_trace,
            'parity':{'status':parity_status,'detail':parity_detail}}
        size,digest=_atomic_episode(path,record)
        event={'event':'episode_committed','path':rel,'bytes':size,'sha256':digest,
            'dataset':dataset,'model_id':arm,'map_identity':payload['identity'],'schedule':schedule,
            'frames':len(replay['steps']),'observations':int(row.get('observation_count',-1)),
            'success':bool(row.get('success')),'parity_status':parity_status,'parity_detail':parity_detail}
        with journal.open('a',encoding='utf-8') as f:f.write(json.dumps(event,sort_keys=True)+'\n');f.flush();os.fsync(f.fileno())
        done+=1
        now=time.monotonic()
        if done==1 or done%12==0 or now-last>=900:
            elapsed=now-started;rate=done/max(elapsed,1e-9);eta=(len(cases)-done)/max(rate,1e-9)
            print(f'task_{task}: {done}/{len(cases)} ({100*done/max(len(cases),1):.1f}%), '
                  f'elapsed={elapsed/60:.1f}m eta={eta/60:.1f}m success={row.get("success")}',flush=True);last=now
    print(f'task_{task}: processed {done} cases; output={target.relative_to(ROOT)}',flush=True)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('command',choices=('audit','bind','amend','run-a','run-b'))
    ap.add_argument('--resume',action='store_true');ap.add_argument('--limit',type=int)
    a=ap.parse_args()
    if a.command=='audit':audit()
    elif a.command=='bind':bind()
    elif a.command=='amend':amend_binding()
    else:run('a' if a.command=='run-a' else 'b',a.resume,a.limit)
if __name__=='__main__':main()
