"""Risk-ranked safety gate: hand-defined scenes only, no cohort generation."""
from __future__ import annotations
import argparse,gzip,json,subprocess,sys,time,traceback
from pathlib import Path
from copy import deepcopy
from collections import Counter
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src')]
from c_v21_common import write,manifest,verify_manifest,sha,commit
from safety_forensics_v1 import run_case,save,parity,ARMS as ALL_ARMS,OUT as OLD
from predictive_safety_benchmark_v1 import all_cases
from report_predictive_safety_v1 import read,summarize
from spatial_memory.predictive_emergency_v1 import PredictiveEmergencySafetyV1
from spatial_memory.risk_ranked_emergency_v1 import RESH1,RESRisk,RESFull
from verify_dao_integrity import verify
OUT=ROOT/'results/phase2_mujoco/risk_ranked_safety_v1'
BASE='fe087b6e5f1283447c25a439b4a9cee920c3f02b'
ARM3=('periodic4','age5','dao_veto')
VERSIONS={'original':None,'predictive_v1':PredictiveEmergencySafetyV1,
          'res_h1':RESH1,'res_risk':RESRisk,'res_full':RESFull}
CANDIDATES=('res_h1','res_risk','res_full')
SOURCES=('src/spatial_memory/risk_ranked_emergency_v1.py',
 'src/spatial_memory/predictive_emergency_v1.py','src/spatial_memory/emergency_safety.py',
 'src/spatial_memory/evaluation.py','src/spatial_memory/navigation.py',
 'src/spatial_memory/mujoco_navigation.py','src/spatial_memory/mujoco_perception.py',
 'src/spatial_memory/dao_navigation_compat_v1_1.py','src/spatial_memory/discovery_observation.py',
 'src/spatial_memory/scheduling.py','src/spatial_memory/change_aware_age.py',
 'src/spatial_memory/cadence_age.py','scripts/safety_forensics_v1.py',
 'scripts/predictive_safety_benchmark_v1.py','scripts/dao_engineering_scenes_v1.py',
 'scripts/run_risk_ranked_safety_v1.py','tests/test_risk_ranked_emergency_v1.py',
 'docs/risk_ranked_safety_v1_protocol.md')
SUM=('goals','contact_free_goal','contact_pairs','post_action_contact_states',
 'distinct_actual_contact_episodes','proven_unavoidable_first_onsets',
 'other_onsets_not_proven_unavoidable','blocked_actions','rejected_selected_actions','wait_actions',
 'idle_steps','sidesteps','retreats','no_certifiably_safe_action','uncertified_selections',
 'no_admissible_fallback','avoidable_ranked_waits','interventions','paid_scans','emergency_scans',
 'paid_rays','emergency_rays','combined_rays','steps','distance_m','safety_ms','wall_seconds')

def files():return {p:sha(ROOT/p) for p in SOURCES}
def load(p):return json.loads(p.read_text())
def cases():
    old=all_cases()
    keep={'head_on','narrow','crossing','sudden_stop','alternating','unavoidable_first','no_pedestrian','no_pedestrian_turn'}
    selected=[dict(deepcopy(d),archive_index=n) for n,d in enumerate(old,1)
              if (d['role']=='original_regression' and d['family']=='pedestrian') or
              (d['role']=='prospective_benchmark' and d['family'] in keep)]
    # Three explicit new public geometry contracts, not an efficacy cohort.
    for src,name in [('head_on','res_mirror_head_on'),('sudden_stop','res_cross_pause_east'),
                     ('no_pedestrian','res_mirror_empty')]:
        d=deepcopy(next(x for x in old if x['family']==src and x['role']=='prospective_benchmark'))
        if src in ('head_on','no_pedestrian'):
            transform=lambda p:(p[0],16-p[1])
            # Shift by one row as well: the source scenes are symmetric in y.
            transform=lambda p:(p[0], p[1]+1)
            d['start']=transform(d['start']);d['goal']=transform(d['goal'])
            d['pedestrians']=[[transform(p) for p in seq] for seq in d['pedestrians']]
        else:
            d['pedestrians']=[[(9,y) for y in (4,5,6,7,7,7,8,9,10,9,8,7,6,5)]]
        d.update(name=name,family=name,role='new_res_engineering',archive_index=None,
                 declared_contact_class='not_proven_unavoidable')
        selected.append(d)
    return selected

def prior_audit(target):
    # Offline: frozen previous candidate alternatives were actually evaluated
    # with its blocked-action state. Compare one-step certificate geometry
    # using independent cardinal endpoint arithmetic, not new shield queries.
    rows=[]
    for d in cases():
        n=d['archive_index']
        if n is None:continue
        for arm in ARM3:
            p=OLD/'matrix'/f'{n:02}_{arm}_predictive_v1.json.gz'
            e=read(p);decisions={x['step']:x for x in e['decisions']}
            for x in e['candidate_diagnostics']:
                if not x.get('no_certifiably_safe_action'):continue
                m=decisions[x['step']];pos=m['position'];yaw=m['yaw']
                from report_predictive_safety_v1 import risky_proxy
                from spatial_memory.predictive_emergency_v1 import reachable
                current={tuple(c) for c in x['current_possible_cells']}
                p1=reachable(current,1,d['width'],d['height'])
                alternatives=[]
                for a in x.get('alternatives',[]):
                    if 'static_measured_clear' not in a:
                        alternatives.append({'action':a['action'],'invalid_reason':a.get('reason')});continue
                    hit=risky_proxy(pos,yaw,a['action'],p1,future=True)
                    alternatives.append({'action':a['action'],'static_measured_clear':a['static_measured_clear'],
                        'current_sweep_risk':a['current_sweep_risk'],'one_transition_endpoint_risk':hit,
                        'two_transition_endpoint_risk':a['future_endpoint_risk'],
                        'h1_certificate_proxy':bool(a['static_measured_clear'] and not a['current_sweep_risk'] and not hit)})
                rows.append({'scene':d['family'],'arm':arm,'step':x['step'],'position':pos,'yaw':yaw,
                    'original_selected':m['selected_before'],'candidate_selected':m['selected_after'],
                    'alternatives':alternatives})
    write(target/'prior_certificate_audit.json',{'records':rows,'caveat':'Offline endpoint proxy on archived public alternatives, not executed actions or causal proof.'})

def check():
    target=OUT/'prepared';target.mkdir(parents=True,exist_ok=False)
    verify_manifest(OLD/'matrix');verify_manifest(OLD/'forensics')
    write(target/'integrity_before.json',verify())
    write(target/'scenarios.json',cases())
    prior_audit(target)
    tests=['tests/test_risk_ranked_emergency_v1.py','tests/test_predictive_emergency_v1.py',
      'tests/test_phase2_emergency_safety.py','tests/test_dao_navigation_compat_v1_1.py',
      'tests/test_phase2_mujoco.py']
    cmd=[sys.executable,'-m','pytest','-q',*tests,f'--junitxml={target/"tests.xml"}']
    p=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
    (target/'tests.log').write_text(p.stdout+p.stderr);print(p.stdout+p.stderr,flush=True)
    write(target/'gate.json',{'returncode':p.returncode,'command':cmd})
    manifest(target)
    if p.returncode:raise SystemExit(p.returncode)
    write(OUT/'binding.json',{'base':BASE,'implementation_commit':commit(),'sources':files(),
        'prepared_manifest_sha256':sha(target/'artifact_manifest.json'),
        'compact_cases':len(cases()),'compact_arms':list(ARM3),'versions':list(VERSIONS)})

def gate():
    b=load(OUT/'binding.json');verify_manifest(OUT/'prepared')
    assert b['sources']==files() and b['prepared_manifest_sha256']==sha(OUT/'prepared/artifact_manifest.json')
    assert load(OUT/'prepared/gate.json')['returncode']==0
    # Source and scenarios are frozen in Git before actual navigation run.
    for p,h in b['sources'].items():
        import hashlib
        assert hashlib.sha256(subprocess.check_output(['git','show',f'HEAD:{p}'],cwd=ROOT)).hexdigest()==h,p
    verify_manifest(OLD/'matrix')

def run(stage):
    gate()
    if stage=='compact':
        definitions=load(OUT/'prepared/scenarios.json');arms=ARM3;versions=tuple(VERSIONS)
    else:
        verify_manifest(OUT/'analysis');selection=load(OUT/'analysis/summary.json')['selected_for_expansion']
        if selection is None:
            print('Expansion not authorized: no candidate passed compact gate.');return
        definitions=[dict(d,archive_index=n) for n,d in enumerate(all_cases(),1)]
        arms=ALL_ARMS;versions=('original',selection)
    target=OUT/stage;target.mkdir(parents=True,exist_ok=False);done=[];start=time.perf_counter()
    write(target/'matrix_spec.json',{'scenarios':definitions,'arms':list(arms),'versions':list(versions)})
    try:
        for n,d in enumerate(definitions,1):
            for arm in arms:
                for name in versions:
                    e=run_case(d,arm,candidate_class=VERSIONS[name],detailed=False)
                    e['safety']=name;e.update(role=d['role'],declared_contact_class=d['declared_contact_class'])
                    if d['archive_index'] is not None and name in ('original','predictive_v1'):
                        p=OLD/'matrix'/f'{d["archive_index"]:02}_{arm}_{name}.json.gz'
                        parity(read(p),e)
                    save(target/f'{n:02}_{arm}_{name}.json.gz',e);done.append([n,arm,name])
            print(f'{stage}: {n}/{len(definitions)} {d["family"]}',flush=True)
        write(target/'summary.json',{'status':'COMPLETE_ENGINEERING_NOT_SAFETY_ACCEPTANCE','episodes':len(done),
            'source_commit':commit(),'elapsed_seconds':time.perf_counter()-start})
        write(target/'integrity_after.json',verify())
        manifest(target)
    except Exception:
        (target/'failure.txt').write_text(traceback.format_exc());write(target/'partial.json',{'completed':done})
        manifest(target);raise

def enrich(e,d,n):
    r=summarize(e,d);r['scene_index']=n
    ledger=e['candidate_diagnostics']
    r['uncertified_selections']=sum(x.get('uncertified_selection',False) for x in ledger)
    r['no_admissible_fallback']=sum(x.get('no_admissible_fallback',False) for x in ledger)
    # Do not equate any no-certificate wait with a known avoidable collision.
    # Detect a wait despite a recorded lower-risk admissible translation.
    bad=0
    for x in ledger:
        selected=x.get('selected_after') or ('wait','none')
        if not x.get('no_certifiably_safe_action') or selected[0]!='wait':continue
        alternatives=x.get('alternatives',[])
        waits=[tuple(a['risk_key']) for a in alternatives if a['action'][0]=='wait' and a.get('fallback_admissible')]
        moves=[tuple(a['risk_key']) for a in alternatives if a['action'][0] in ('move','sidestep','retreat') and a.get('fallback_admissible')]
        if moves and (not waits or min(moves)<min(waits)):bad+=1
    r['avoidable_ranked_waits']=bad
    return r

def report(stage):
    target0=OUT/stage
    if stage=='expansion' and not target0.exists():
        print('No full expansion result: compact gate did not authorize it.');return
    verify_manifest(target0)
    assert load(target0/'summary.json')['status']=='COMPLETE_ENGINEERING_NOT_SAFETY_ACCEPTANCE'
    spec=load(target0/'matrix_spec.json');definitions=spec['scenarios'];arms=spec['arms'];versions=spec['versions']
    target=OUT/('analysis' if stage=='compact' else 'expansion_analysis')
    target.mkdir(parents=True,exist_ok=False)
    rows={};episodes={}
    for n,d in enumerate(definitions,1):
        for arm in arms:
            for name in versions:
                e=read(target0/f'{n:02}_{arm}_{name}.json.gz')
                k=n,arm,name;rows[k]=enrich(e,d,n);episodes[k]=e
    def totals(group):
        a=list(group);return {'episodes':len(a),**{k:sum(r[k] for r in a) for k in SUM}}
    group={v:totals(r for (n,a,s),r in rows.items() if s==v) for v in versions}
    paired=[];gates={}
    for v in versions:
        if v=='original':continue
        pairs=[(rows[n,a,'original'],rows[n,a,v],d) for n,d in enumerate(definitions,1) for a in arms]
        for a,b,d in pairs:
            paired.append({'candidate':v,'scene':d['family'],'role':d['role'],'arm':a['arm'],
                'original_goal':a['goals'],'candidate_goal':b['goals'],'original_onsets':a['distinct_actual_contact_episodes'],
                'candidate_onsets':b['distinct_actual_contact_episodes'],
                'common_step_delta':b['steps']-a['steps'] if a['goals'] and b['goals'] else None,
                'common_distance_delta_m':b['distance_m']-a['distance_m'] if a['goals'] and b['goals'] else None,
                'paid_delta':b['paid_scans']-a['paid_scans'],'combined_rays_delta':b['combined_rays']-a['combined_rays']})
        a=group['original'];b=group[v]
        flags={'no_new_contact_case':all(x['distinct_actual_contact_episodes']>0 or y['distinct_actual_contact_episodes']==0 for x,y,_ in pairs),
               'no_added_nonfirst_onsets_per_case':all(y['other_onsets_not_proven_unavoidable']<=x['other_onsets_not_proven_unavoidable'] for x,y,_ in pairs),
               'fewer_nonfirst_onsets':b['other_onsets_not_proven_unavoidable']<a['other_onsets_not_proven_unavoidable'],
               'head_on_narrow_contact_free':all(y['distinct_actual_contact_episodes']==0 for x,y,d in pairs if d['family'] in ('head_on','narrow')),
               'negative_control_trace_parity':all(episodes[n,arm,'original']['trace']==episodes[n,arm,v]['trace']
                    for n,d in enumerate(definitions,1) if not d['pedestrians'] for arm in arms),
               'preserve_total_goals':b['goals']>=a['goals'],'preserve_contact_free_goals':b['contact_free_goal']>=a['contact_free_goal'],
               'no_lower_risk_admissible_escape_waits':b['avoidable_ranked_waits']==0}
        gates[v]={'pass':all(flags.values()),'checks':flags}
    eligible=[v for v in CANDIDATES if v in gates and gates[v]['pass']]
    selected=min(eligible,key=lambda v:(group[v]['other_onsets_not_proven_unavoidable'],-group[v]['contact_free_goal'],
                                         group[v]['combined_rays'],CANDIDATES.index(v))) if eligible else None
    write(target/'episode_metrics.json',list(rows.values()));write(target/'paired.json',paired)
    write(target/'summary.json',{'stage':stage,'episodes':len(rows),'totals':group,'gates':gates,
        'selected_for_expansion':selected if stage=='compact' else None,
        'decision':'PASS_ENGINEERING_GATE' if selected else 'REJECT_OR_NO_QUALIFYING_CANDIDATE',
        'independent_efficacy_or_real_world_safety':False})
    lines=['# Risk-ranked safety '+stage,'',
        '|Version|Episodes|Goals|Contact-free goals|Contact states|Onsets except proven first|Paid scans|Combined rays|Gate|',
        '|---|---:|---:|---:|---:|---:|---:|---:|---|']
    for v,r in group.items():
        lines.append(f"|{v}|{r['episodes']}|{r['goals']}|{r['contact_free_goal']}|{r['post_action_contact_states']}|{r['other_onsets_not_proven_unavoidable']}|{r['paid_scans']}|{r['combined_rays']}|{gates.get(v,{}).get('pass','reference')}|")
    lines+=['','Selected after prespecified engineering gate: '+str(selected),'',
            'No independent efficacy or real-world safety claim.']
    (target/'research_report.md').write_text('\n'.join(lines)+'\n');manifest(target);print('\n'.join(lines))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('stage',choices=['check','compact','report','expand','report-expand'])
    a=p.parse_args().stage
    if a=='check':check()
    elif a=='compact':run('compact')
    elif a=='report':report('compact')
    elif a=='expand':run('expansion')
    else:report('expansion')
