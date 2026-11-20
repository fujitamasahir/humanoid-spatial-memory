"""Frozen seven-arm CAA screen, fail-closed correctness/smoke/full gates."""
from __future__ import annotations
import argparse,importlib.metadata,json,platform,subprocess,sys
from dataclasses import asdict,replace
from statistics import mean
from collections import Counter
from caa_common import (ROOT,OUT,BASE,HIST,write,manifest,verify_manifest,sha,commit,
                        episode,parity,run_case,ref,fit,frozen_factory)
sys.path.insert(0,str(ROOT/'src'))
from spatial_memory.change_aware_age import CellHistory,ChangeAwareAgeController,HistoryParameters
from spatial_memory.scheduling import ObservationController
ARMS=('periodic','age4','age5','age6','caa_fast','caa_slow','caa_full')
BASELINES={'periodic':'periodic','age4':'age','age5':'age5'}
SOURCES=('src/spatial_memory/change_aware_age.py','scripts/caa_common.py','scripts/run_caa_fit72.py',
 'scripts/report_caa.py','scripts/audit_caa_history.py','tests/test_change_aware_age.py',
 'tests/test_caa_integration.py','docs/caa_protocol.md','docs/age5_frozen_baseline.md',
 'src/spatial_memory/scheduling.py','src/spatial_memory/memory.py','src/spatial_memory/cadence_age.py',
 'src/spatial_memory/evi.py','src/spatial_memory/persistence.py','src/spatial_memory/navigation.py',
 'src/spatial_memory/evaluation.py','src/spatial_memory/mujoco_navigation.py','src/spatial_memory/mujoco_perception.py',
 'src/spatial_memory/emergency_safety.py','src/spatial_memory/pedestrian_tracking.py','src/spatial_memory/simulation.py',
 'scripts/evaluate_phase2_61ray_emergency_safety_full_288.py','scripts/phase2_mujoco_navigation.py',
 'scripts/evaluate_c_v2_candidate_coverage_fit72.py','requirements.txt')
METRICS=('paid_memory_scans','actual_memory_raycasts','emergency_safety_scans','emergency_safety_raycasts',
 'combined_rays','elapsed_steps','travel_distance_m','blocked_attempts','emergency_safety_interventions',
 'unwanted_contacts','false_persistent_occupancy_updates','missed_persistent_changes','scheduler_ms','episode_wall_time_seconds')


def fingerprints():return {p:sha(ROOT/p) for p in SOURCES}
def factory(initial,arm,config,options):
    if arm in BASELINES:return frozen_factory(initial,arm,config,options)
    if arm=='age6':
        adjusted=dict(options);adjusted['parameters']=replace(adjusted['parameters'],age_steps=6)
        return ObservationController(initial,'age',**adjusted)
    return ChangeAwareAgeController(initial,mode=arm,**options)


def safety(row,trace,diag):
    scans=[f['step'] for f in trace['steps'] if f['observation_granted']]
    if scans!=diag['actual_memory_call_steps'] or len(scans)!=row['observation_count'] or len(scans)>20:raise RuntimeError('Paid observation mismatch')
    shields=sum(f['action'] is not None and f['action'][0]!='wait' for f in trace['steps'])
    if row['g1_actual_collision_shield_queries']!=shields or row['g1_unselected_action_shield_queries'] or not row['g1_shield_query_count_valid']:raise RuntimeError('Selected shield mismatch')
    emergency=[f['emergency_scan'] for f in trace['steps'] if 'emergency_scan' in f]
    if len(emergency)!=row['elapsed_steps'] or sum(f['ray_count'] for f in emergency)!=row['emergency_safety_raycasts']:raise RuntimeError('Independent emergency accounting mismatch')
    if diag['actual_memory_raycasts']!=61*row['observation_count']:raise RuntimeError('Memory ray count mismatch')


def flatten(n,arm,row,diag):
    raw=fit.flat(arm,row,diag);dec=diag['decisions'];updates=len(diag['observation_log'])-1
    result={k:raw[k] for k in METRICS}
    result.update(episode=n,arm=arm,identity=row['world_identity'],schedule=row['schedule'],success=bool(row['success']),
        contact_free_success=bool(row['success'] and row['g1_unwanted_contact_pairs']==0),
        history_update_ms=diag['history_update_total_ms'],mean_noninitial_update_ms=diag['history_update_total_ms']/updates if updates else 0.,
        mean_decide_ms=diag['scheduler_total_ms']/len(dec) if dec else 0.,diagnostic_ms=diag['diagnostic_total_ms'],
        advanced_requests=sum(d.get('request_advanced_vs_uniform5',False) for d in dec),
        advanced_paid_scans=sum(d['granted'] and d.get('request_advanced_vs_uniform5',False) for d in dec),
        deferred_requests=sum(d.get('request_deferred_vs_uniform5',False) for d in dec),
        budget_exhausted_decisions=sum(d['used_before']>=20 for d in dec),
        scheduler_astar_calls=sum(d.get('scheduler_plan_calls',0) for d in dec),
        predicted_raycasts=sum(d.get('predicted_raycasts',0) for d in dec))
    for c in ('unknown','changing','intermediate','stable'):
        result['mean_global_'+c]=mean(d['global_history']['classes'][c] for d in dec) if dec else 0.
    for t in ('4','5','6'):
        counts=[d.get('effective_deadlines_known',{}).get(t,0) for d in dec]
        result['mean_deadline_'+t]=mean(counts) if counts else 0.
    return result


def check():
    target=OUT/'correctness';target.mkdir(parents=True,exist_ok=False)
    fit.verify_original_data_integrity();verify_manifest(HIST)
    command=[sys.executable,'-m','pytest','-q','tests/test_change_aware_age.py','tests/test_caa_integration.py',
        'tests/test_cadence_age.py','tests/test_phase2_mujoco.py','tests/test_phase2_emergency_safety.py',
        'tests/test_persistence_evi_evaluation.py','--junitxml='+str(target/'tests.xml')]
    result=subprocess.run(command,cwd=ROOT,text=True,capture_output=True)
    (target/'tests.log').write_text(result.stdout+result.stderr);print(result.stdout+result.stderr,flush=True)
    write(target/'gate.json',{'status':'PASS' if result.returncode==0 else 'REJECTED','command':command,
        'returncode':result.returncode,'source_sha256':fingerprints(),'base_commit':commit()})
    manifest(target)
    if result.returncode:raise SystemExit(result.returncode)
    # Replay all Periodic keys before any CAA rollout. Age/Age-5 already have144
    # exact pre-implementation replays in the original prospective audit.
    replay=OUT/'periodic_replay';replay.mkdir(parents=True,exist_ok=False)
    _,_,prov,_=ref.base.load_baseline();config=ref.base.frozen_config(prov)
    worlds={w['identity']:w for w in ref.navigation.admitted_worlds()}
    for n in range(1,73):
        saved=episode(HIST,n,'periodic');ident,schedule,_,_=saved['trace']['key']
        row,trace,diag=run_case(worlds[ident],schedule,'periodic',config)
        parity(saved,row,trace);safety(row,trace,diag);fit.save_episode(replay,n,'periodic',row,trace,diag)
    write(replay/'summary.json',{'status':'PASS_72_EXACT_PERIODIC_REPLAYS'});manifest(replay)
    pins={l.split('==')[0]:l.split('==')[1] for l in (ROOT/'requirements.txt').read_text().splitlines() if '==' in l}
    versions={p:importlib.metadata.version(p) for p in pins}
    if pins!=versions or sys.version_info[:2]!=(3,12):raise RuntimeError('Pinned runtime mismatch')
    write(OUT/'protocol_binding.json',{'base_commit':BASE,'prepared_from_commit':commit(),'source_sha256':fingerprints(),
        'protocol':'docs/caa_protocol.md','arms':list(ARMS),'history_parameters':asdict(HistoryParameters()),
        'runtime':{'python':sys.version,'prefix':sys.prefix,'platform':platform.platform(),'hostname':platform.node(),'dependencies':versions},
        'correctness_manifest_sha256':sha(target/'artifact_manifest.json'),
        'retrospective_manifest_sha256':sha(ROOT/'results/phase2_mujoco/caa_v1/retrospective/artifact_manifest.json'),
        'frozen_cadence_manifest_sha256':sha(HIST/'artifact_manifest.json'),
        'output_root':OUT.relative_to(ROOT).as_posix(),'independent_cohort_authorized':False})


def gate():
    binding_path=OUT/'protocol_binding.json';binding=json.loads(binding_path.read_text())
    if binding['source_sha256']!=fingerprints():raise RuntimeError('Frozen source drift')
    committed=subprocess.check_output(['git','show','HEAD:'+binding_path.relative_to(ROOT).as_posix()],cwd=ROOT)
    if committed!=binding_path.read_bytes():raise RuntimeError('Source/protocol binding must be committed before outcomes')
    verify_manifest(OUT/'correctness');verify_manifest(OUT/'periodic_replay')
    g=json.loads((OUT/'correctness/gate.json').read_text())
    if g['status']!='PASS' or g['source_sha256']!=fingerprints():raise RuntimeError('Correctness gate failed')
    verify_manifest(ROOT/'results/phase2_mujoco/caa_v1/retrospective')
    if json.loads((ROOT/'results/phase2_mujoco/caa_v1/retrospective/summary.json').read_text())['status']!='PASS_EXACT_144_REPLAYS':raise RuntimeError('Age/Age5 replay missing')


def run(smoke):
    gate();fit.verify_original_data_integrity()
    if not smoke:
        verify_manifest(OUT/'smoke')
        if json.loads((OUT/'smoke/summary.json').read_text())['status']!='PASS_SMOKE':raise RuntimeError('Smoke gate failed')
    target=OUT/('smoke' if smoke else 'fit72');target.mkdir(parents=True,exist_ok=False)
    _,_,prov,_=ref.base.load_baseline();config=ref.base.frozen_config(prov)
    worlds={w['identity']:w for w in ref.navigation.admitted_worlds()}
    write(target/'provenance.json',{'source_commit':commit(),'binding_sha256':sha(OUT/'protocol_binding.json'),
        'source_sha256':fingerprints(),'config':config,'descriptive_fit_not_validation':True,
        'timings':'Same core decide/refresh boundaries in every arm; global shadow logging excluded from scheduler time'})
    rows=[]
    for n in range(1,3 if smoke else 73):
        saved=episode(HIST,n,'age');ident,schedule,_,_=saved['trace']['key']
        for arm in ARMS:
            row,trace,diag=run_case(worlds[ident],schedule,arm,config,factory=factory,history_factory=CellHistory)
            safety(row,trace,diag)
            if arm in BASELINES:parity(episode(HIST,n,BASELINES[arm]),row,trace)
            if not smoke and n<=2:parity(episode(OUT/'smoke',n,arm),row,trace)
            if smoke and row['g1_unwanted_contact_pairs']:raise RuntimeError('Smoke unwanted contact')
            if arm.startswith('caa_') and any(d.get('scheduler_plan_calls',0) or d.get('predicted_raycasts',0) for d in diag['decisions']):raise RuntimeError('CAA planning/sensor boundary violation')
            fit.save_episode(target,n,arm,row,trace,diag);rows.append(flatten(n,arm,row,diag))
        if smoke or n%12==0:print(f'{"Smoke" if smoke else "FIT"} {n}/{2 if smoke else 72}, seven arms',flush=True)
    fit.verify_original_data_integrity();fit.csv_write(target/'episodes.csv',rows)
    write(target/'summary.json',{'status':'PASS_SMOKE' if smoke else 'COMPLETED_DESCRIPTIVE_FIT_NOT_VALIDATION',
        'arms':{a:{'episodes':len(rs:=[r for r in rows if r['arm']==a]),'goals':sum(r['success'] for r in rs),
           'contact_free_goals':sum(r['contact_free_success'] for r in rs),
           **{'mean_'+k:mean(r[k] for r in rs) for k in METRICS}} for a in ARMS},
        'preserved_prefix':ref.navigation.verify_preserved_prefix(),'baseline_semantic_and_metric_parity':True})
    manifest(target)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('stage',choices=['check','smoke','full','report'])
    parser.add_argument('--output-root',type=__import__('pathlib').Path,default=OUT)
    args=parser.parse_args();OUT=args.output_root.resolve()
    if not OUT.is_relative_to(ROOT/'results/phase2_mujoco'):raise ValueError('Output must remain in this repository result tree')
    if args.stage=='check':check()
    elif args.stage=='report':
        from report_caa import report
        report(OUT)
    else:run(args.stage=='smoke')
