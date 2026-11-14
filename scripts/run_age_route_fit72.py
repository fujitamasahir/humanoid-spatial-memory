"""Read-only FIT72 descriptive screen of route-aware directional Age variants."""
from __future__ import annotations
import argparse,gzip,json,subprocess,sys
from statistics import mean
from collections import Counter
from c_v21_common import ROOT,OUT as OLD,write,manifest,verify_manifest,sha,commit
from run_c_v21a_depth_ablation import episode,parity
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from spatial_memory.view_age import ViewAgeController
from spatial_memory.route_age import ARMS,RouteAgeController
VIEW='age_view_veto'
VIEWS=ROOT/'results/phase2_mujoco/age_view_v1'
OUT=ROOT/'results/phase2_mujoco/age_route_v1'
BASE='3e381a8d32a966a02f697020e063e35c1098855d'
SOURCES=('src/spatial_memory/route_age.py','src/spatial_memory/view_age.py',
         'src/spatial_memory/navigation.py','src/spatial_memory/evi.py',
         'src/spatial_memory/scheduling.py','scripts/run_age_route_fit72.py',
         'tests/test_route_age.py','docs/age_route_protocol.md')
METRICS=('paid_memory_scans','actual_memory_raycasts','emergency_safety_scans',
         'emergency_safety_raycasts','combined_rays','elapsed_steps','travel_distance_m',
         'blocked_attempts','emergency_safety_interventions','unwanted_contacts',
         'false_persistent_occupancy_updates','missed_persistent_changes','scheduler_ms',
         'episode_wall_time_seconds')
def fingerprints():return {p:sha(ROOT/p) for p in SOURCES}
def load(path):return json.loads(path.read_text())
def check():
    target=OUT/'correctness';target.mkdir(parents=True,exist_ok=False)
    cmd=[sys.executable,'-m','pytest','-q','tests/test_route_age.py','tests/test_view_age.py','tests/test_c_v21_navigation.py']
    p=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
    (target/'pytest.log').write_text(p.stdout+p.stderr);print(p.stdout+p.stderr,flush=True)
    write(target/'gate.json',{'status':'PASS' if p.returncode==0 else 'REJECTED',
        'source_sha256':fingerprints(),'commit':commit(),'command':cmd})
    manifest(target)
    if p.returncode:raise SystemExit(p.returncode)
def gate():
    verify_manifest(OUT/'correctness')
    g=load(OUT/'correctness/gate.json')
    if g['status']!='PASS' or g['source_sha256']!=fingerprints():raise RuntimeError('Correctness gate or source drift')
    verify_manifest(OLD/'reference_replays')
    verify_manifest(VIEWS/'fit72')
    if load(OLD/'reference_replays/summary.json')['status']!='PASS_EXACT_ALL_360_REFERENCE_REPLAYS':
        raise RuntimeError('Missing verified baseline evidence')
def run_case(payload,schedule,arm,config):
    import evaluate_persistence_evi_fit72 as runner
    import evaluate_c_v2_candidate_coverage_fit72 as fit
    original=runner.PersistenceEVIController
    parent=ViewAgeController if arm==VIEW else RouteAgeController
    class Controller(parent):
        def __init__(self,*a,**kw):
            if kw.get('persistence'):raise RuntimeError('Persistence changes prohibited')
            if arm==VIEW:super().__init__(*a,view_mode=arm,**kw)
            else:super().__init__(*a,route_mode=arm,**kw)
    runner.PersistenceEVIController=Controller
    try:row,trace,diag=fit.run_measured(payload,schedule,'c_k',config)
    finally:runner.PersistenceEVIController=original
    return row,trace,diag
def flatten(n,arm,row,diag):
    import evaluate_c_v2_candidate_coverage_fit72 as fit
    raw=fit.flat(arm,row,diag)
    result={k:raw[k] for k in METRICS}
    result.update(episode=n,arm=arm,identity=row['world_identity'],schedule=row['schedule'],
                  success=bool(row['success']))
    decisions=diag.get('decisions',[])
    result['age_requests']=sum(bool(d.get('age_request')) for d in decisions)
    result['directional_requests']=sum(bool(d.get('view_request')) for d in decisions)
    result['deadline_requests']=sum(bool(d.get('deadline')) for d in decisions)
    result['age_requests_deferred']=sum(bool(d.get('age_request')) and not d['granted'] for d in decisions)
    result['route_rescue_only_grants']=sum(bool(d.get('route_rescue')) and not bool(d.get('view_veto_grant')) and bool(d['granted']) for d in decisions)
    result['route_clock_only_grants']=sum(bool(d.get('route_proactive')) and not bool(d.get('route_rescue')) and not bool(d.get('view_veto_grant')) and bool(d['granted']) for d in decisions)
    result['route_candidate_cells']=sum(len(d.get('route_visible_candidates',[])) for d in decisions)
    return result
def aggregate(rows):
    return {'episodes':len(rows),'goals':sum(r['success'] for r in rows),
        **{f'mean_{k}':mean(r[k] for r in rows) for k in METRICS}}
def run(smoke):
    gate()
    import evaluate_event_observation_fit72 as ref
    import evaluate_c_v2_candidate_coverage_fit72 as fit
    fit.verify_original_data_integrity()
    if not smoke:
        verify_manifest(OUT/'smoke')
        if load(OUT/'smoke/summary.json')['status']!='PASS_SMOKE':raise RuntimeError('Smoke gate failed')
    target=OUT/('smoke' if smoke else 'fit72');target.mkdir(parents=True,exist_ok=False)
    _,_,prov,_=ref.base.load_baseline();config=ref.base.frozen_config(prov)
    worlds={p['identity']:p for p in ref.navigation.admitted_worlds()}
    write(target/'provenance.json',{'base':BASE,'commit':commit(),'source_sha256':fingerprints(),
        'config':config,'reference_manifest_sha256':sha(OLD/'reference_replays/artifact_manifest.json'),
        'descriptive_not_independent':True})
    rows=[]
    for n in range(1,3 if smoke else 73):
        saved=episode(OLD/'reference_replays',n,'age')
        identity,schedule,_,seed=saved['trace']['key']
        for arm in ('periodic','age',VIEW,*ARMS):
            if arm in (*ARMS,VIEW):
                row,trace,diag=run_case(worlds[identity],schedule,arm,config)
                for d in diag['decisions']:
                    if arm in (VIEW,'age_route_rescue') and d['granted'] and not d.get('age_request'):
                        raise RuntimeError('Age-anchored grant outside original Age request')
                    if arm in ARMS and d.get('view_veto_grant') and not d['granted']:
                        raise RuntimeError('Original view veto grant unexpectedly suppressed')
                if arm==VIEW:parity(episode(VIEWS/'fit72',n,arm),row,trace)
            else:
                row,trace,diag=fit.run_measured(worlds[identity],schedule,arm,config)
                parity(episode(OLD/'reference_replays',n,arm),row,trace)
                # Baseline scheduler not instrumented by this runner.
                diag['scheduler_total_ms']=0.
            if not smoke and n<=2:parity(episode(OUT/'smoke',n,arm),row,trace)
            if smoke and row['g1_unwanted_contact_pairs']:raise RuntimeError('Smoke unwanted contact')
            if row['g1_unselected_action_shield_queries'] or row['observation_count']>20:
                raise RuntimeError('Safety/cap violation')
            fit.save_episode(target,n,arm,row,trace,diag);rows.append(flatten(n,arm,row,diag))
        if smoke or n%6==0:print(f'{"Smoke" if smoke else "FIT"} {n}/{2 if smoke else 72}',flush=True)
    fit.verify_original_data_integrity()
    fit.csv_write(target/'episodes.csv',rows)
    write(target/'summary.json',{'status':'PASS_SMOKE' if smoke else 'COMPLETED_DESCRIPTIVE_FIT_NOT_VALIDATION',
        'arms':{a:aggregate([r for r in rows if r['arm']==a]) for a in ('periodic','age',VIEW,*ARMS)},
        'baseline_scheduler_timing':'not measured; zero is a placeholder'})
    manifest(target)
def report():
    gate();verify_manifest(OUT/'fit72')
    if load(OUT/'fit72/summary.json')['status']!='COMPLETED_DESCRIPTIVE_FIT_NOT_VALIDATION':
        raise RuntimeError('Full screen incomplete')
    import evaluate_c_v2_candidate_coverage_fit72 as fit
    target=OUT/'analysis';target.mkdir(parents=True,exist_ok=False)
    arms=('periodic','age',VIEW,*ARMS)
    rows={}
    for n in range(1,73):
        for a in arms:
            p=episode(OUT/'fit72',n,a);rows[n,a]=flatten(n,a,p['row'],p['diagnostics'])
    summary={a:aggregate([rows[n,a] for n in range(1,73)]) for a in arms}
    comparisons=[];pair_rows=[]
    for a in ARMS:
        for b in ('periodic','age',VIEW):
            pairs=[(rows[n,b],rows[n,a]) for n in range(1,73)]
            common=[(x,y) for x,y in pairs if x['success'] and y['success']]
            for x,y in pairs:
                if (x['identity'],x['schedule'])!=(y['identity'],y['schedule']):raise RuntimeError('Pair mismatch')
                pair_rows.append({'candidate':a,'reference':b,'identity':x['identity'],'schedule':x['schedule'],
                    'reference_success':x['success'],'candidate_success':y['success'],
                    **{f'delta_{k}':y[k]-x[k] for k in METRICS if k!='scheduler_ms'}})
            r=summary[a];s=summary[b]
            comparisons.append({'candidate':a,'reference':b,
                'rescues':sum(not x['success'] and y['success'] for x,y in pairs),
                'harms':sum(x['success'] and not y['success'] for x,y in pairs),
                'common_successes':len(common),
                'better_success_or_equal_fewer_scans':r['mean_unwanted_contacts']<=s['mean_unwanted_contacts'] and
                    (r['goals']>s['goals'] or (r['goals']==s['goals'] and r['mean_paid_memory_scans']<s['mean_paid_memory_scans'])),
                'common_success_delta':{k:mean(y[k]-x[k] for x,y in common) if common else None
                                        for k in METRICS if k!='scheduler_ms'}})
    fit.csv_write(target/'paired_episode_deltas.csv',pair_rows)
    write(target/'summary.json',{'status':'DESCRIPTIVE_ONLY','arms':summary,'paired':comparisons,
        'caveat':'36 reused maze lineages; schedules correlated. Baseline scheduler time not measured.'})
    lines=['# Route-aware Age sensing: descriptive FIT72','',
        '|Arm|Goals/72|Paid scans|H80 steps|Combined rays|Contacts total|',
        '|---|---:|---:|---:|---:|---:|']
    for a,r in summary.items():
        lines.append(f"|{a}|{r['goals']}|{r['mean_paid_memory_scans']:.3f}|{r['mean_elapsed_steps']:.3f}|{r['mean_combined_rays']:.2f}|{round(72*r['mean_unwanted_contacts'])}|")
    lines+=['','|Candidate vs reference|Rescues/harms|Common successes|Common steps delta|Common distance delta (m)|User target met?|',
             '|---|---:|---:|---:|---:|---|']
    for r in comparisons:
        c=r['common_success_delta'];fmt=lambda x:'NA' if x is None else f'{x:.3f}'
        lines.append(f"|{r['candidate']} vs {r['reference']}|{r['rescues']}/{r['harms']}|{r['common_successes']}|{fmt(c['elapsed_steps'])}|{fmt(c['travel_distance_m'])}|{r['better_success_or_equal_fewer_scans']}|")
    lines+=['','Primary target (both baselines): '+str({a:all(p['better_success_or_equal_fewer_scans'] for p in comparisons if p['candidate']==a and p['reference'] in ('periodic','age')) for a in ARMS}),'','This is a reused FIT development screen, not independent validation. Positive cost deltas are worse.']
    (target/'research_report.md').write_text('\n'.join(lines)+'\n')
    manifest(target);print('\n'.join(lines))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('stage',choices=['check','smoke','full','report'])
    a=p.parse_args().stage
    if a=='check':check()
    elif a=='report':report()
    else:run(a=='smoke')
