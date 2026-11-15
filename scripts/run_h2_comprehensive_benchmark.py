"""Checkpointed H2 comprehensive evaluation; see the committed protocol."""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src')]
import h2_high_frequency_dynamics as h2
import h2_final_common as frozen
from h2_comprehensive_adapters import ADDITIONAL,run_case
from verify_dao_integrity import verify as verify_preservation

OUT=ROOT/'results/phase2_mujoco/h2_comprehensive_benchmark_v1'
PROTOCOL=ROOT/'docs/h2_comprehensive_benchmark_protocol_v1.md'
SCHEMA=ROOT/'docs/h2_comprehensive_benchmark_replay_schema.md'
REGISTRY=OUT/'protocol/model_registry.json'
HISTORICAL=(ROOT/'results/phase2_mujoco/h2_final_generalization_v1',
            ROOT/'results/phase2_mujoco/h2_high_frequency_dynamics_v1')

def sha_bytes(b):return hashlib.sha256(b).hexdigest()
def sha(p):return sha_bytes(Path(p).read_bytes())
def write_exclusive(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as f:
        f.write(json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n')
        f.flush();os.fsync(f.fileno())
def atomic_episode(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    raw=json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    packed=gzip.compress(raw,mtime=0)
    tmp=path.with_name(path.name+f'.{os.getpid()}.tmp')
    with tmp.open('xb') as f:f.write(packed);f.flush();os.fsync(f.fileno())
    if path.exists():tmp.unlink();raise FileExistsError(path)
    os.replace(tmp,path)
    return sha_bytes(packed)
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)
def load_registry():return json.loads(REGISTRY.read_text())
def load_maps():
    maps=h2.source_maps()
    if len(maps)!=36:raise RuntimeError('Expected 36 saved H2 maps')
    return maps

def verify_manifests():
    checked=0
    for root in HISTORICAL:
        for m in sorted(root.rglob('artifact_manifest.json')):
            doc=json.loads(m.read_text());entries=doc if isinstance(doc,list) else doc.get('files',[])
            for item in entries:
                target=m.parent/item['path'];raw=target.read_bytes()
                if sha_bytes(raw)!=item['sha256'] or ('bytes' in item and len(raw)!=item['bytes']):
                    raise RuntimeError(f'Historical manifest mismatch: {target}')
                checked+=1
    return checked

def bind():
    if (OUT/'binding.json').exists():raise FileExistsError('Comprehensive binding already exists')
    if subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()!='phase2/mujoco-proxy-pilot':
        raise RuntimeError('Wrong branch')
    if subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip() not in ('?? demos/','?? demos'):
        raise RuntimeError('Unexpected dirty worktree; bind only a clean research branch')
    maps=load_maps();registry=load_registry()
    if len(registry)!=57 or len(ADDITIONAL)!=41:raise RuntimeError('Registry/adapter arm mismatch')
    protected=verify_preservation()
    if protected['status']!='PASS':raise RuntimeError('Phase 1.5 preservation gate failed')
    manifests=verify_manifests()
    _,_,provenance,_=frozen.ref.base.load_baseline()
    config=frozen.ref.base.frozen_config(provenance)
    source_paths={
        PROTOCOL,SCHEMA,Path(__file__),Path(__file__).with_name('h2_comprehensive_adapters.py'),
        Path(__file__).with_name('build_h2_comprehensive_registry.py'),
        ROOT/'scripts/h2_final_common.py',ROOT/'scripts/h2_high_frequency_dynamics.py',
        ROOT/'scripts/evaluate_phase2_61ray_emergency_safety_full_288.py',
        ROOT/'src/spatial_memory/evaluation.py',ROOT/'src/spatial_memory/simulation.py',
        ROOT/'src/spatial_memory/mujoco_navigation.py',ROOT/'src/spatial_memory/mujoco_perception.py',
        ROOT/'src/spatial_memory/emergency_safety.py',ROOT/'src/spatial_memory/navigation.py',
        ROOT/'src/spatial_memory/pedestrian_tracking.py',ROOT/'scripts/verify_dao_integrity.py'}
    for row in registry:
        source_paths.add(ROOT/row['source_file'])
        source_paths.add(ROOT/row['historical_evaluation_script'])
    source_paths.update((ROOT/'src/spatial_memory').glob('*.py'))
    gitsha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    binding={
        'protocol':'h2_comprehensive_benchmark_protocol_v1',
        'status':'PREREGISTERED_READY_FOR_VALIDATION',
        'commit':gitsha,'branch':'phase2/mujoco-proxy-pilot',
        'prior_required_commits':{'h2_final':'12dc945c7da496e6cfc5dd79d6977b4c48d705c1',
          'high_frequency':'015ae8d3f17d9bd9839254eabe4dafa145d09491'},
        'prior_bindings':{
          'h2_final_sha256':sha(HISTORICAL[0]/'binding.json'),
          'high_frequency_binding_amendment3_sha256':sha(HISTORICAL[1]/'binding_amendment_3.json')},
        'frozen_config':config,
        'conditions':['original','high_frequency'],
        'matrix':{'previously_evaluated_models':13,'requested_additional_models':44,
          'eligible_additional_models':41,'blocked_additional_models':3,
          'episodes_per_condition_if_all_eligible':41*72,'seed':42,'schedules':[1,2],
          'max_steps':80,'max_observations':20},
        'blocked_models':[x for x in registry if x['authorization_status'].startswith('blocked')],
        'registry_sha256':sha(REGISTRY),'protocol_sha256':sha(PROTOCOL),'replay_schema_sha256':sha(SCHEMA),
        'maps':[{'identity':p['identity'],'sha256':digest} for p,digest in maps],
        'source_sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in sorted(source_paths)},
        'historical_artifact_manifest_entries_verified':manifests,
        'preservation_gate':protected,
        'runtime':{'python':sys.version,'python_version':platform.python_version(),
          'platform':platform.platform(),'mujoco':importlib.metadata.version('mujoco'),
          'numpy':importlib.metadata.version('numpy'),'hostname':platform.node()},
        'started_utc':datetime.now(timezone.utc).isoformat(),
        'independent_validation':False,'descriptive_development_evaluation':True,
    }
    write_exclusive(OUT/'binding.json',binding)
    print('Binding created; no episode run. Eligible additional arms:',len(ADDITIONAL),flush=True)

def validate_binding():
    b=json.loads((OUT/'binding.json').read_text())
    if b['status'] not in ('PREREGISTERED_READY_FOR_VALIDATION','VALIDATION_PASSED','PRIMARY_IN_PROGRESS','PARTIAL'):
        raise RuntimeError('Binding not eligible to run')
    if b['commit']!=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip():
        raise RuntimeError('Source commit differs from bound protocol commit')
    if b['registry_sha256']!=sha(REGISTRY) or b['protocol_sha256']!=sha(PROTOCOL) or b['replay_schema_sha256']!=sha(SCHEMA):
        raise RuntimeError('Committed protocol or registry drift')
    for p,digest in b['source_sha256'].items():
        if sha(ROOT/p)!=digest:raise RuntimeError(f'Source commitment changed: {p}')
    maps=load_maps()
    if b['maps']!=[{'identity':p['identity'],'sha256':h} for p,h in maps]:
        raise RuntimeError('Saved map identity/hash mismatch')
    return b

def _episode_path(stage,condition,arm,payload,schedule):
    safe=payload['identity'].replace(':','_')
    return OUT/stage/'episodes'/condition/arm/f'{safe}_s{schedule}_seed42.json.gz'

def _run_cases(stage,condition,case_list,resume=False):
    binding=validate_binding()
    root=OUT/stage;root.mkdir(parents=True,exist_ok=True)
    journal=root/'journal.jsonl'
    existing=list((root/'episodes').rglob('*.json.gz')) if (root/'episodes').exists() else []
    if existing and not resume:raise RuntimeError(f'{stage} already has checkpoints; pass --resume')
    maps=load_maps();arms=ADDITIONAL
    done=0;started=time.monotonic();last_progress=started
    conditions=('original','high_frequency') if condition=='both' else (condition,)
    expected=len(case_list)*len(arms)*len(conditions)
    with journal.open('a') as log:
        log.write(canonical({'event':'stage_started','stage':stage,'condition':condition,
            'cases':len(case_list),'arms':len(arms),'expected':expected,'time_utc':datetime.now(timezone.utc).isoformat()})+'\n');log.flush()
        for map_index,schedule,payload in case_list:
            for cond in conditions:
                for arm in arms:
                    target=_episode_path(stage,cond,arm,payload,schedule)
                    if target.exists():
                        if not resume:raise FileExistsError(target)
                        done+=1;continue
                    # Verify the source binding before every model family checkpoint.
                    if done%41==0:validate_binding()
                    row,replay,diag=run_case(payload,schedule,arm,cond)
                    if row['world_identity']!=payload['identity'] or int(row['schedule'])!=schedule or int(row['seed'])!=42:
                        raise RuntimeError('Episode identity drift')
                    if len(replay.get('steps',[]))!=int(row['elapsed_steps'])+1:
                        raise RuntimeError('Replay/frame count mismatch')
                    item={'schema':'h2_comprehensive_replay_v1','condition':cond,
                        'arm':arm,'map_index':map_index,'map_identity':payload['identity'],
                        'schedule':schedule,'seed':42,'row':row,'replay':replay,'diagnostics':diag}
                    digest=atomic_episode(target,item)
                    entry={'event':'episode_committed','path':target.relative_to(OUT).as_posix(),
                        'sha256':digest,'condition':cond,'arm':arm,
                        'map_identity':payload['identity'],'schedule':schedule,
                        'success':bool(row['success']),'elapsed_steps':int(row['elapsed_steps'])}
                    log.write(canonical(entry)+'\n');log.flush();os.fsync(log.fileno())
                    done+=1
            now=time.monotonic()
            if now-last_progress>=60 or done==expected:
                elapsed=now-started;rate=done/max(elapsed,1e-9);eta=(expected-done)/max(rate,1e-9)
                print(f'{stage}: {done}/{expected} episode-model pairs; elapsed {elapsed/60:.1f} min; ETA {eta/60:.1f} min',flush=True)
                last_progress=now
    actual=len(list((root/'episodes').rglob('*.json.gz')))
    if actual!=expected:raise RuntimeError(f'Expected {expected} saved episodes, found {actual}')
    write_exclusive(root/'summary.json',{'status':'COMPLETE','condition':condition,
        'episodes':actual,'requested_models':44,'eligible_models':len(arms),
        'blocked_models':binding['blocked_models'],'case_count':len(case_list),
        'protocol_binding_sha256':sha(OUT/'binding.json'),'elapsed_seconds':time.monotonic()-started})

def _make_smoke_cases():
    maps=load_maps()
    # Prespecified deterministic fixture: lexically first existing R and M map.
    chosen=[]
    for family in ('R','M'):
        candidates=[(i,p) for i,(p,_h) in enumerate(maps,1) if p['mechanism']==family]
        if not candidates:raise RuntimeError(f'Missing saved family {family}')
        chosen.append(candidates[0])
    return [(i,s,p) for i,p in chosen for s in (1,2)]

def _make_primary_cases():
    return [(i,s,p) for i,(p,_h) in enumerate(load_maps(),1) for s in (1,2)]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=('bind','smoke','primary-original','primary-high-frequency','verify'))
    parser.add_argument('--resume',action='store_true')
    args=parser.parse_args()
    if args.stage=='bind':bind();return
    if args.stage=='verify':verify_outputs();return
    if args.stage=='smoke':
        cases=_make_smoke_cases()
        _run_cases('smoke','both',cases,args.resume)
        smoke_gate();return
    if not (OUT/'validation/smoke_gate.json').is_file():raise RuntimeError('Passing smoke gate required before primary')
    if args.stage=='primary-original':_run_cases('original_environment','original',_make_primary_cases(),args.resume)
    else:_run_cases('high_frequency_environment','high_frequency',_make_primary_cases(),args.resume)

def smoke_gate():
    root=OUT/'smoke';files=sorted((root/'episodes').rglob('*.json.gz'))
    if len(files)!=8*len(ADDITIONAL):raise RuntimeError('Smoke episode count mismatch')
    conditions={'original','high_frequency'};families={'R','M'}
    identities=set()
    seen=set()
    for p in files:
        with gzip.open(p,'rt') as f:item=json.load(f)
        row=item['row'];assert row['observation_count']<=20
        assert row['g1_unselected_action_shield_queries']==0 and row['g1_shield_query_count_valid']
        assert len(item['replay']['steps'])==row['elapsed_steps']+1
        identities.add(item['map_identity'])
        seen.add((item['condition'],item['arm'],item['map_identity'],int(item['schedule'])))
        if item['condition'] not in conditions:raise RuntimeError('Invalid smoke condition')
    expected={(c,a,i,s) for c in conditions for a in ADDITIONAL
              for i in identities for s in (1,2)}
    if seen!=expected:raise RuntimeError('Smoke matrix has missing or duplicate cells')
    gate={'status':'PASS_SMOKE','models':len(ADDITIONAL),'episodes':len(files),
        'maps':sorted(identities),'schedules':[1,2],'conditions':['original','high_frequency'],
        'observation_cap_and_selected_shield':'PASS','replay_frame_count':'PASS',
        'source_binding_sha256':sha(OUT/'binding.json')}
    target=OUT/'validation';target.mkdir(exist_ok=True)
    write_exclusive(target/'smoke_gate.json',gate)
    print('Smoke gate PASS',json.dumps(gate,sort_keys=True),flush=True)

def verify_outputs():
    binding=validate_binding();results={}
    for stage,expected in [('smoke',8*len(ADDITIONAL)),
        ('original_environment',72*len(ADDITIONAL)),
        ('high_frequency_environment',72*len(ADDITIONAL))]:
        folder=OUT/stage
        if not folder.exists():results[stage]={'status':'NOT_RUN','episodes':0,'expected':expected};continue
        files=sorted((folder/'episodes').rglob('*.json.gz')) if (folder/'episodes').exists() else []
        errors=[]
        for p in files:
            raw=p.read_bytes()
            try:
                item=json.loads(gzip.decompress(raw))
                row=item['row'];replay=item['replay']
                if len(replay['steps'])!=int(row['elapsed_steps'])+1:errors.append(str(p)+':frame_count')
                if int(row['observation_count'])>20:errors.append(str(p)+':cap')
                if int(row['g1_unselected_action_shield_queries'])!=0 or not row['g1_shield_query_count_valid']:errors.append(str(p)+':shield')
            except Exception as e:errors.append(str(p)+':'+repr(e))
        results[stage]={'status':'PASS' if len(files)==expected and not errors else 'INCOMPLETE_OR_FAIL',
            'episodes':len(files),'expected':expected,'errors':errors[:30]}
    print(json.dumps({'binding':binding['commit'],'stages':results},indent=2))

if __name__=='__main__':main()
