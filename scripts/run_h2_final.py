"""Checkpointed H2 final execution. No model selection or optimization."""
import json,sys,subprocess,time,gzip,traceback,os
import numpy as np
from h2_final_common import *
from evaluate_rdao_one_shot_interventions import _compare_trace
from run_caa_fit72 import safety
POLICY_SOURCES=sorted({str(p.relative_to(ROOT)) for folder in ('src/spatial_memory','scripts') for p in (ROOT/folder).glob('*.py') if folder.startswith('src') or p.name in ('h2_final_common.py','h2_generate_maps.py','run_h2_final.py','caa_common.py','evaluate_phase2_61ray_emergency_safety_full_288.py','phase2_mujoco_navigation.py','evaluate_event_observation_fit72.py','evaluate_c_v2_candidate_coverage_fit72.py')})
SOURCES=POLICY_SOURCES+['docs/h2_final_evaluation_protocol_v1.md','tests/test_h2_final_benchmark.py','requirements.txt']
def freeze():
    import platform,importlib.metadata
    write(OUT/'binding.json',{'base_commit':commit(),'sources':{p:sha(ROOT/p) for p in SOURCES},'arms':list(ARMS),'config':config(),'hard_deadline_UTC':'2026-11-15T02:30:00Z','runtime':{'python':sys.version,'platform':platform.platform(),'hostname':platform.node(),'mujoco':importlib.metadata.version('mujoco'),'numpy':np.__version__}})
def gate():
    b=json.loads((OUT/'binding.json').read_text())
    assert all(sha(ROOT/p)==h for p,h in b['sources'].items())
    assert subprocess.check_output(['git','show','HEAD:'+str((OUT/'binding.json').relative_to(ROOT))],cwd=ROOT)==(OUT/'binding.json').read_bytes()
def compare_saved(saved,row,trace):
    if 'row' in saved:parity(saved,row,trace)
    else:
        _compare_trace(saved['trace'],trace)
        for k,j in [('success','success'),('observations','observation_count'),('elapsed_steps','elapsed_steps'),('travel_distance_m','travel_distance_m'),('unwanted_contacts','g1_unwanted_contact_pairs'),('blocked_attempts','g1_footprint_blocked_attempts'),('emergency_interventions','emergency_safety_interventions'),('turns','g1_heading_changes')]:assert saved['metrics'][k]==row[j],(k,saved['metrics'][k],row[j])
def save(target,n,arm,r,t,d):
    # Exclusive durable publication; partial temporary files never count complete.
    path=target/f'episode_{n:03}_{arm}.json.gz';tmp=path.with_suffix('.tmp')
    raw=ref.base._jsonable_row({'row':r,'trace':t,'diagnostics':d})
    with tmp.open('xb') as f:
        f.write(gzip.compress(json.dumps(raw,sort_keys=True,allow_nan=False).encode(),mtime=0));f.flush();os.fsync(f.fileno())
    if path.exists():raise FileExistsError(path)
    tmp.rename(path)
    with (target/'journal.jsonl').open('a') as f:f.write(json.dumps({'episode':n,'arm':arm,'path':path.name,'sha256':sha(path)})+'\n');f.flush();os.fsync(f.fileno())
def verify_episode(e):
    r,t,d=e['row'],e['trace'],e['diagnostics'];safety(r,t,d)
    assert len(d['timing_ns']['decision'])==r['elapsed_steps']
    assert len(d['timing_ns']['memory_sensor'])==r['observation_count']
    assert len(d['timing_ns']['update'])==r['observation_count']-1
    assert d['actual_memory_call_steps']==r['spatial_memory_observation_steps']
    assert all(d['timing_ns'][k] for k in ('initialization','memory_sensor','navigation_planning'))
def run(stage):
    deadline_guard(300);gate()
    if stage=='fit_replay':
        cases=[];worlds={p['identity']:p for p in ref.navigation.admitted_worlds()}
        for n in range(1,73):
            ident,s,*_=saved_episode(n,'age5')['trace']['key'];cases.append((worlds[ident],s))
    else:
        verify_manifest(OUT/'maps');verify_manifest(OUT/'fit_replay')
        assert json.loads((OUT/'fit_replay/summary.json').read_text())['completed']==864
        maps=json.loads((OUT/'maps/summary.json').read_text())['maps']
        cases=[(json.loads((OUT/'maps'/m['path']).read_text()),s) for m in maps for s in (0,1)]
        if stage=='smoke':cases=cases[:4]
        elif stage=='primary':verify_manifest(OUT/'smoke')
        elif stage=='timing_repeat':verify_manifest(OUT/'primary')
        else:raise ValueError(stage)
    target=OUT/stage;target.mkdir(exist_ok=True)
    if (target/'artifact_manifest.json').exists():raise FileExistsError('Stage already sealed')
    started=time.perf_counter();count=0;contacts=0
    try:
        # Fixed public FIT warmup, not unseen optimization or measured dataset.
        worlds={p['identity']:p for p in ref.navigation.admitted_worlds()};warm=sorted(worlds)[0]
        for arm in ARMS:run_case(worlds[warm],0,arm)
        for n,(p,s) in enumerate(cases,1):
            order=list(ARMS[(n-1)%12:]+ARMS[:(n-1)%12])
            if stage=='timing_repeat':order=order[::-1]
            for arm in order:
                deadline_guard(300);path=target/f'episode_{n:03}_{arm}.json.gz'
                if path.exists():e=episode(target,n,arm);verify_episode(e);r,t,d=e['row'],e['trace'],e['diagnostics']
                else:
                    r,t,d=run_case(p,s,arm);verify_episode({'row':r,'trace':t,'diagnostics':d})
                    if stage=='fit_replay':compare_saved(saved_episode(n,arm),r,t)
                    if stage=='primary' and n<=4:parity(episode(OUT/'smoke',n,arm),r,t)
                    if stage=='timing_repeat':parity(episode(OUT/'primary',n,arm),r,t)
                    save(target,n,arm,r,t,d)
                count+=1;contacts+=r['g1_unwanted_contact_pairs']
            if n%6==0 or stage=='smoke':print(f'{stage}: {count}/{len(cases)*12} completed; contacts={contacts}; elapsed={time.perf_counter()-started:.1f}s',flush=True)
        write(target/'summary.json',{'status':'COMPLETE','stage':stage,'completed':count,'unwanted_contacts':contacts,'wall_seconds':time.perf_counter()-started,'source_freeze_commit':commit(),'timing_repeat_not_independent':stage=='timing_repeat','warmup_public_fit_episodes':12})
        manifest(target)
    except BaseException:
        # Keep failed attempts and completed ledger for explicit validated resume.
        stamp=time.time_ns();(target/f'interruption_{stamp}.txt').write_text(traceback.format_exc());raise
if __name__=='__main__':
    if sys.argv[1]=='freeze':freeze()
    else:run(sys.argv[1])
