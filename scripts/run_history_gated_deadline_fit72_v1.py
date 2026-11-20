"""Direct descriptive comparison on the existing admitted FIT72 development set.

No generation, reserve access, safety changes, fitting or policy selection.
"""
from __future__ import annotations
import argparse,hashlib,json,subprocess,sys,time,traceback
from pathlib import Path
from statistics import mean
from c_v21_common import ROOT,write,manifest,verify_manifest,sha,commit
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src')]
from run_c_v21a_depth_ablation import episode,parity
import run_age_cadence_fit72 as cadence
import evaluate_event_observation_fit72 as ref
import evaluate_c_v2_candidate_coverage_fit72 as fit
from verify_dao_integrity import verify
from run_dao_integration_v1_1 import native
from spatial_memory.route_gated_dao_veto_v1 import RouteGatedDAOVeto
from spatial_memory.history_gated_deadline_v1 import HistoryGatedDeadline,MODES
OUT=ROOT/'results/phase2_mujoco/history_gated_deadline_fit72_v1'
OLD=ROOT/'results/phase2_mujoco/age_cadence_v1/fit72'
AUDIT=ROOT/'results/phase2_mujoco/omission_public_features_v1'
BASE='03ce4d643a0ed69f07e9d500da1cae0dcbbf99df'
REFERENCES=('periodic','age','age5')
CANDIDATES=('deadline',*MODES)
ARMS=(*REFERENCES,*CANDIDATES)
SOURCES=('src/spatial_memory/history_gated_deadline_v1.py','src/spatial_memory/route_gated_dao_veto_v1.py',
 'src/spatial_memory/omission_public_features_v1.py','src/spatial_memory/dao_navigation_compat_v1_1.py',
 'src/spatial_memory/dao_navigation_v1.py','src/spatial_memory/discovery_observation.py',
 'src/spatial_memory/navigation.py','src/spatial_memory/evaluation.py','src/spatial_memory/memory.py',
 'src/spatial_memory/scheduling.py','src/spatial_memory/cadence_age.py','src/spatial_memory/evi.py',
 'src/spatial_memory/mujoco_navigation.py','src/spatial_memory/mujoco_perception.py',
 'src/spatial_memory/emergency_safety.py','scripts/evaluate_phase2_61ray_emergency_safety_full_288.py',
 'scripts/evaluate_c_v2_candidate_coverage_fit72.py','scripts/evaluate_persistence_evi_fit72.py',
 'scripts/run_age_cadence_fit72.py','scripts/run_history_gated_deadline_fit72_v1.py',
 'tests/test_history_gated_deadline_v1.py','docs/history_gated_deadline_fit72_v1_protocol.md')
METRICS=('paid_memory_scans','actual_memory_raycasts','emergency_safety_scans','emergency_safety_raycasts',
 'combined_rays','elapsed_steps','travel_distance_m','unwanted_contacts','blocked_attempts',
 'emergency_safety_interventions','false_persistent_occupancy_updates','missed_persistent_changes',
 'episode_wall_time_seconds')
def load(p):return json.loads(p.read_text())
def fingerprints():return {p:sha(ROOT/p) for p in SOURCES}
def check():
    t=OUT/'prepared';t.mkdir(parents=True,exist_ok=False)
    for p in (OLD,AUDIT/'prepared',AUDIT/'audit',AUDIT/'analysis'):verify_manifest(p)
    write(t/'integrity_before.json',verify())
    tests=['tests/test_history_gated_deadline_v1.py','tests/test_omission_public_features_v1.py',
           'tests/test_route_gated_dao_veto_v1.py','tests/test_discovery_observation.py',
           'tests/test_dao_navigation_compat_v1_1.py','tests/test_cadence_age.py']
    cmd=[sys.executable,'-m','pytest','-q',*tests]
    p=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
    (t/'tests.log').write_text(p.stdout+p.stderr);print(p.stdout+p.stderr,flush=True)
    write(t/'gate.json',{'returncode':p.returncode,'command':cmd});manifest(t)
    if p.returncode:raise SystemExit(p.returncode)
    write(OUT/'binding.json',{'base':BASE,'source_commit':commit(),'sources':fingerprints(),
        'prepared_sha256':sha(t/'artifact_manifest.json'),'reference_sha256':sha(OLD/'artifact_manifest.json'),
        'arms':list(ARMS),'descriptive_only':True})
def gate():
    b=load(OUT/'binding.json');verify_manifest(OUT/'prepared');verify_manifest(OLD)
    assert b['sources']==fingerprints() and load(OUT/'prepared/gate.json')['returncode']==0
    assert b['prepared_sha256']==sha(OUT/'prepared/artifact_manifest.json')
    assert b['reference_sha256']==sha(OLD/'artifact_manifest.json')
    for p,h in b['sources'].items():
        assert hashlib.sha256(subprocess.check_output(['git','show',f'HEAD:{p}'],cwd=ROOT)).hexdigest()==h,p
def new_arm(payload,schedule,arm,config):
    # Scope a factory replacement around the exact frozen FIT runner.
    original=ref.base.run_episode
    created={}
    def injected(s,cfg,method,**kwargs):
        def factory(initial,mode,**options):
            sensor={k:config['mujoco_ray_sensor'][k] for k in ('range_m','horizontal_fov_deg','ray_count')}
            sensor['cell_size']=config['mujoco_cell_size_m']
            c=(RouteGatedDAOVeto(initial,mode,gate_mode='deadline',sensor=sensor,**options) if arm=='deadline'
                else HistoryGatedDeadline(initial,mode,history_mode=arm,sensor=sensor,**options))
            created['controller']=c
            return c
        kwargs['_controller_factory']=factory
        return original(s,cfg,method,**kwargs)
    ref.base.run_episode=injected
    try:row,trace=ref.base.run_case(payload,schedule,'age',json.loads(json.dumps(config)),with_safety=True)
    finally:ref.base.run_episode=original
    c=created['controller']
    assert c.used==row['observation_count'] and c.used<=20
    assert row['g1_shield_query_count_valid'] and not row['g1_unselected_action_shield_queries']
    assert [d['step'] for d in c.decisions if d['granted']]==[x['step'] for x in trace['steps'] if x['step'] and x['observation_granted']]
    return row,trace,{'decisions':native(c.decisions),'scheduler_total_ms':c.scheduler_ns/1e6}
def run_case(payload,schedule,arm,config):
    if arm=='age5':return cadence.run_case(payload,schedule,arm,config)
    if arm in ('periodic','age'):return fit.run_measured(payload,schedule,arm,config)
    # Reuse measured wrapper for actual paid sensor count and exact grant-step ledger.
    original=fit.runner.run_arm
    fit.runner.run_arm=new_arm
    try:return fit.run_measured(payload,schedule,arm,config)
    finally:fit.runner.run_arm=original
def flat(n,arm,row,diag):
    x=fit.flat(arm,row,diag)
    return {'episode':n,'arm':arm,'identity':row['world_identity'],'schedule':row['schedule'],
        'success':bool(row['success']),**{k:x[k] for k in METRICS},
        'scheduler_ms':x['scheduler_ms'] if arm in CANDIDATES or arm=='age5' else None,
        'history_vetoes':sum(d.get('history_veto',False) for d in diag.get('decisions',[]))}
def run(smoke):
    gate()
    if not smoke:
        verify_manifest(OUT/'smoke')
        assert load(OUT/'smoke/summary.json')['status']=='PASS_SMOKE'
    name='smoke' if smoke else 'fit72';t=OUT/name;t.mkdir(parents=True,exist_ok=False)
    _,_,prov,_=ref.base.load_baseline();config=ref.base.frozen_config(prov)
    worlds={p['identity']:p for p in ref.navigation.admitted_worlds()}
    assert len(worlds)==36
    rows=[];done=[];start=time.perf_counter()
    write(t/'provenance.json',{'commit':commit(),'config':config,'source_sha256':fingerprints(),
        'reference_manifest_sha256':sha(OLD/'artifact_manifest.json'),'descriptive_only':True})
    try:
        for n in range(1,3 if smoke else 73):
            baseline=episode(OLD,n,'age');identity,schedule,_,seed=baseline['trace']['key']
            for arm in ARMS:
                row,trace,diag=run_case(worlds[identity],schedule,arm,config)
                assert tuple(trace['key'][:2])==(identity,schedule) and trace['key'][3]==seed
                if arm in REFERENCES:parity(episode(OLD,n,arm),row,trace)
                if not smoke and n<=2:parity(episode(OUT/'smoke',n,arm),row,trace)
                fit.save_episode(t,n,arm,row,trace,native(diag))
                rows.append(flat(n,arm,row,diag));done.append([n,arm])
            if smoke or n%6==0:print(f'{name} {n}/{2 if smoke else 72}',flush=True)
        write(t/'integrity_after.json',verify())
        fit.csv_write(t/'episodes.csv',rows)
        write(t/'summary.json',{'status':'PASS_SMOKE' if smoke else 'COMPLETED_DESCRIPTIVE_FIT',
            'episodes':len(rows),'reference_parities':(2 if smoke else 72)*3,
            'elapsed_seconds':time.perf_counter()-start})
        manifest(t)
    except Exception:
        (t/'failure.txt').write_text(traceback.format_exc());write(t/'partial.json',{'completed':done});manifest(t);raise
def report():
    gate();verify_manifest(OUT/'fit72');t=OUT/'analysis';t.mkdir(parents=True,exist_ok=False)
    rows={}
    for n in range(1,73):
        for a in ARMS:
            p=episode(OUT/'fit72',n,a);rows[n,a]=flat(n,a,p['row'],p['diagnostics'])
    totals={}
    for a in ARMS:
        rr=[rows[n,a] for n in range(1,73)]
        totals[a]={'episodes':72,'goals':sum(r['success'] for r in rr),
            **{k:sum(r[k] for r in rr) for k in METRICS},
            'history_vetoes':sum(r['history_vetoes'] for r in rr),
            'scheduler_ms_mean':mean(r['scheduler_ms'] for r in rr) if rr[0]['scheduler_ms'] is not None else None}
    pairs=[];comparisons=[]
    for a in CANDIDATES:
        for b in (*REFERENCES,'deadline'):
            if a==b:continue
            rr=[(rows[n,b],rows[n,a]) for n in range(1,73)]
            common=[(x,y) for x,y in rr if x['success'] and y['success']]
            for x,y in rr:
                assert (x['identity'],x['schedule'])==(y['identity'],y['schedule'])
                pairs.append({'candidate':a,'reference':b,'identity':x['identity'],'schedule':x['schedule'],
                    'reference_success':x['success'],'candidate_success':y['success'],
                    **{f'delta_{k}':y[k]-x[k] for k in METRICS}})
            x,y=totals[b],totals[a]
            passed=y['unwanted_contacts']<=x['unwanted_contacts'] and (y['goals']>x['goals'] or
                    (y['goals']==x['goals'] and y['paid_memory_scans']<x['paid_memory_scans']))
            comparisons.append({'candidate':a,'reference':b,'primary_target_met':passed,
                'rescues':sum(not x['success'] and y['success'] for x,y in rr),
                'harms':sum(x['success'] and not y['success'] for x,y in rr),
                'common_successes':len(common),'common_step_delta':mean(y['elapsed_steps']-x['elapsed_steps'] for x,y in common) if common else None,
                'common_distance_delta_m':mean(y['travel_distance_m']-x['travel_distance_m'] for x,y in common) if common else None,
                'paid_delta':y['paid_memory_scans']-x['paid_memory_scans'],
                'combined_ray_delta':y['combined_rays']-x['combined_rays']})
    targets={a:{'beats_original_periodic_and_age':all(r['primary_target_met'] for r in comparisons if r['candidate']==a and r['reference'] in ('periodic','age')),
        'also_beats_age5':all(r['primary_target_met'] for r in comparisons if r['candidate']==a and r['reference'] in REFERENCES)} for a in CANDIDATES}
    fit.csv_write(t/'episodes.csv',list(rows.values()));fit.csv_write(t/'paired.csv',pairs)
    write(t/'summary.json',{'totals':totals,'comparisons':comparisons,'targets':targets,
        'independent_validation':False,'selection_authorized':False})
    lines=['# Direct FIT72 development comparison','',
        '|Arm|Goals/72|Paid scans total|Paid scans mean|H80 steps mean|Combined rays total|Contact pairs|',
        '|---|---:|---:|---:|---:|---:|---:|']
    for a,r in totals.items():
        lines.append(f"|{a}|{r['goals']}|{r['paid_memory_scans']}|{r['paid_memory_scans']/72:.3f}|{r['elapsed_steps']/72:.3f}|{r['combined_rays']}|{r['unwanted_contacts']}|")
    lines+=['','|Candidate vs reference|Rescues/harms|Common successes|Common steps delta|Common distance delta m|Target met?|',
        '|---|---:|---:|---:|---:|---|']
    for r in comparisons:
        lines.append(f"|{r['candidate']} vs {r['reference']}|{r['rescues']}/{r['harms']}|{r['common_successes']}|{r['common_step_delta']}|{r['common_distance_delta_m']}|{r['primary_target_met']}|")
    lines+=['','Original target and stronger Age5 comparison: '+str(targets),
            'Reused FIT development evidence only; no independent efficacy or safety claim.']
    (t/'research_report.md').write_text('\n'.join(lines)+'\n');manifest(t);print('\n'.join(lines))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('stage',choices=('check','smoke','full','report'))
    a=p.parse_args().stage
    if a=='check':check()
    elif a=='report':report()
    else:run(a=='smoke')
