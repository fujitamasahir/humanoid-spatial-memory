"""One-scan causal interventions on already-used hand scenes only."""
from __future__ import annotations
import argparse,hashlib,json,subprocess,sys,time,traceback
from collections import defaultdict
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src')]
from c_v21_common import write,manifest,verify_manifest,sha,commit
import safety_forensics_v1 as forensic
from report_predictive_safety_v1 import read,summarize
from verify_dao_integrity import verify
from spatial_memory.route_gated_dao_veto_v1 import RouteGatedDAOVeto
from spatial_memory.deadline_single_omission_v1 import DeadlineSingleOmission
from spatial_memory.res_phase_wait_v1 import RESH1PhaseWait
from spatial_memory.discovery_observation import predicted_footprints
OLD=ROOT/'results/phase2_mujoco/route_gated_dao_veto_v1'
OUT=ROOT/'results/phase2_mujoco/deadline_single_omission_v1'
BASE='1a8870c1d42da6e7ec9cfc988c3d36e6346d37f9'
ARM='dao_veto_deadline'
SAFETIES={'original':None,'res_h1_phase_wait':RESH1PhaseWait}
SOURCES=('src/spatial_memory/deadline_single_omission_v1.py',
 'src/spatial_memory/route_gated_dao_veto_v1.py','src/spatial_memory/discovery_observation.py',
 'src/spatial_memory/dao_navigation_compat_v1_1.py','src/spatial_memory/dao_navigation_v1.py',
 'src/spatial_memory/navigation.py','src/spatial_memory/evaluation.py','src/spatial_memory/scheduling.py',
 'src/spatial_memory/memory.py','src/spatial_memory/mujoco_navigation.py','src/spatial_memory/mujoco_perception.py',
 'src/spatial_memory/emergency_safety.py','src/spatial_memory/risk_ranked_emergency_v1.py',
 'src/spatial_memory/res_phase_wait_v1.py','scripts/safety_forensics_v1.py',
 'scripts/report_predictive_safety_v1.py','scripts/run_deadline_single_omission_v1.py',
 'scripts/verify_dao_integrity.py','tests/test_deadline_single_omission_v1.py',
 'docs/deadline_single_omission_v1_protocol.md')

def load(p):return json.loads(p.read_text())
def fingerprints():return {p:sha(ROOT/p) for p in SOURCES}
def archive(n,safety):return read(OLD/'matrix'/f'{n:02}_{ARM}_{safety}.json.gz')

def schedule():
    cases=load(OLD/'prepared/matrix_spec.json')['scenarios'];targets=[]
    for n,d in enumerate(cases,1):
        for s in SAFETIES:
            e=archive(n,s);paid=e['paid']
            assert paid[0]['step']==0 and len(paid)==e['actual_calls']['memory']
            for item in paid[1:]:
                targets.append({'scene_index':n,'scene':d['family'],'safety':s,'step':item['step']})
    assert len(cases)==26 and len(targets)==149
    return cases,targets

def check():
    t=OUT/'prepared';t.mkdir(parents=True,exist_ok=False)
    for d in (OLD/'prepared',OLD/'matrix',OLD/'analysis'):verify_manifest(d)
    write(t/'integrity_before.json',verify())
    cases,targets=schedule();write(t/'schedule.json',{'scenarios':cases,'targets':targets})
    tests=['tests/test_deadline_single_omission_v1.py','tests/test_route_gated_dao_veto_v1.py',
        'tests/test_discovery_observation.py','tests/test_dao_navigation_compat_v1_1.py',
        'tests/test_res_phase_wait_v1.py','tests/test_phase2_emergency_safety.py']
    cmd=[sys.executable,'-m','pytest','-q',*tests,f'--junitxml={t/"tests.xml"}']
    p=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
    (t/'tests.log').write_text(p.stdout+p.stderr);print(p.stdout+p.stderr,flush=True)
    write(t/'gate.json',{'returncode':p.returncode,'command':cmd});manifest(t)
    if p.returncode:raise SystemExit(p.returncode)
    write(OUT/'binding.json',{'base':BASE,'source_commit':commit(),'sources':fingerprints(),
        'prepared_manifest_sha256':sha(t/'artifact_manifest.json'),
        'archive_manifest_sha256':sha(OLD/'matrix/artifact_manifest.json'),
        'untreated_replays':52,'interventions':149})

def gate():
    b=load(OUT/'binding.json');verify_manifest(OUT/'prepared');verify_manifest(OLD/'matrix')
    assert b['sources']==fingerprints() and b['prepared_manifest_sha256']==sha(OUT/'prepared/artifact_manifest.json')
    assert b['archive_manifest_sha256']==sha(OLD/'matrix/artifact_manifest.json')
    assert load(OUT/'prepared/gate.json')['returncode']==0
    for p,h in b['sources'].items():
        assert hashlib.sha256(subprocess.check_output(['git','show',f'HEAD:{p}'],cwd=ROOT)).hexdigest()==h,p

def episode(d,safety,omit=None):
    original=forensic.factory;created={}
    def factory(initial,name,options):
        assert name==ARM
        c=(RouteGatedDAOVeto(initial,gate_mode='deadline',**options) if omit is None
           else DeadlineSingleOmission(initial,omit_step=omit,**options))
        created['controller']=c;return c
    forensic.factory=factory
    try:e=forensic.run_case(d,ARM,candidate_class=SAFETIES[safety],detailed=False)
    finally:forensic.factory=original
    c=created['controller']
    assert omit is None or c.omissions==1
    e.update(safety=safety,role=d['role'],declared_contact_class=d['declared_contact_class'],omitted_step=omit)
    e['scheduler_decisions']=forensic.native(c.decisions)
    e['scheduler_ms']=c.scheduler_ns/1e6
    return e

def assert_prefix(base,treated,step):
    def prefix(rows):return [r for r in rows if r['step']<step]
    for field in ('paid','scheduler_decisions'):
        assert prefix(base[field])==prefix(treated[field]),field
    assert prefix(base['trace']['steps'])==prefix(treated['trace']['steps'])
    b=next(r for r in base['scheduler_decisions'] if r['step']==step)
    a=next(r for r in treated['scheduler_decisions'] if r['step']==step)
    assert b['granted'] and a['intervention_omitted'] and not a['granted']
    assert {k:v for k,v in a.items() if k not in ('intervention_omitted','untreated_requested','untreated_granted','requested','granted')}=={k:v for k,v in b.items() if k not in ('requested','granted')}
    assert step not in {r['step'] for r in treated['paid']}

def run():
    gate();t=OUT/'matrix';t.mkdir(parents=True,exist_ok=False);done=[];start=time.perf_counter()
    spec=load(OUT/'prepared/schedule.json')
    try:
        for n,d in enumerate(spec['scenarios'],1):
            for s in SAFETIES:
                old=archive(n,s);base=episode(d,s)
                forensic.parity(old,base)
                assert old['paid']==base['paid'] and old['scheduler_decisions']==base['scheduler_decisions']
                forensic.save(t/f'{n:02}_{s}_base.json.gz',base);done.append([n,s,None])
                targets=[r['step'] for r in spec['targets'] if r['scene_index']==n and r['safety']==s]
                for step in targets:
                    e=episode(d,s,step);assert_prefix(base,e,step)
                    forensic.save(t/f'{n:02}_{s}_omit_{step:03}.json.gz',e);done.append([n,s,step])
            print(f'Completed {n}/26: {d["family"]}',flush=True)
        assert len(done)==201
        write(t/'summary.json',{'status':'COMPLETE_ENGINEERING_INTERVENTIONS','episodes':len(done),
            'baseline_parities':52,'prefix_parities':149,'elapsed_seconds':time.perf_counter()-start,'source_commit':commit()})
        write(t/'integrity_after.json',verify());manifest(t)
    except Exception:
        (t/'failure.txt').write_text(traceback.format_exc());write(t/'partial.json',{'completed':done});manifest(t);raise

def scan_features(e,d,step):
    memory=np.full((d['height'],d['width']),-1,np.int8)
    for item in e['paid']:
        if item['step']>=step:break
        a=np.asarray(item['reading'],np.int8);memory[a>=0]=a[a>=0]
    reading=np.asarray(next(r['reading'] for r in e['paid'] if r['step']==step),np.int8)
    decision=next(r for r in e['scheduler_decisions'] if r['step']==step)
    pose=next(r for r in e['decisions'] if r['step']==step)
    new=int(np.sum((reading>=0)&(memory<0)))
    changed=int(np.sum((reading>=0)&(memory>=0)&(reading!=memory)))
    predicted=predicted_footprints(memory,tuple(pose['position']),pose['yaw'])
    assert len(predicted['frontier'])==decision['frontier']['visible']
    return {'actual_new':new,'actual_changed_known':changed,
        'predicted_frontier_new':decision['frontier']['new'],
        'predicted_frontier_stale':decision['frontier']['stale'],
        'predicted_route_new':decision['frontier']['route_new'],
        'fallback':decision['effective_fallback'],'age_anchor':decision['age5_anchor'],
        'verification':decision['verification_high'],'discovery':decision['effective_discovery']}

def report():
    gate();verify_manifest(OUT/'matrix');t=OUT/'analysis';t.mkdir(parents=True,exist_ok=False)
    spec=load(OUT/'prepared/schedule.json');rows=[];bases={}
    for n,d in enumerate(spec['scenarios'],1):
        for s in SAFETIES:
            b=read(OUT/'matrix'/f'{n:02}_{s}_base.json.gz')
            bases[n,s]=(b,summarize(b,d))
    for item in spec['targets']:
        n,s,step=item['scene_index'],item['safety'],item['step'];d=spec['scenarios'][n-1]
        base,a=bases[n,s]
        treated=read(OUT/'matrix'/f'{n:02}_{s}_omit_{step:03}.json.gz')
        assert_prefix(base,treated,step);b=summarize(treated,d)
        bt={r['step']:r for r in base['trace']['steps']};tt={r['step']:r for r in treated['trace']['steps']}
        keys=('position','heading_yaw','action','blocked')
        divergence=next((k for k in sorted(bt.keys()|tt.keys()) if k>=step and
            (k not in bt or k not in tt or any(bt[k].get(x)!=tt[k].get(x) for x in keys))),None)
        next_paid=next((r['step'] for r in treated['paid'] if r['step']>step),None)
        goal_delta=b['goals']-a['goals'];safe_delta=b['contact_free_goal']-a['contact_free_goal']
        contacts=b['distinct_actual_contact_episodes']-a['distinct_actual_contact_episodes']
        # Conservative descriptive classification, not proof of combined deletability.
        preserved=(goal_delta>=0 and safe_delta>=0 and contacts<=0 and
            b['other_onsets_not_proven_unavoidable']<=a['other_onsets_not_proven_unavoidable'] and
            b['contact_pairs']<=a['contact_pairs'])
        common=bool(a['goals'] and b['goals'])
        sd=b['steps']-a['steps'];dd=b['distance_m']-a['distance_m']
        pd=b['paid_scans']-a['paid_scans'];rd=b['combined_rays']-a['combined_rays']
        rows.append({**item,'role':d['role'],**scan_features(base,d,step),
            'baseline_goal':a['goals'],'omission_goal':b['goals'],'goal_delta':goal_delta,
            'contact_free_goal_delta':safe_delta,'contact_episode_delta':contacts,
            'contact_pair_delta':b['contact_pairs']-a['contact_pairs'],
            'nonfirst_onset_delta':b['other_onsets_not_proven_unavoidable']-a['other_onsets_not_proven_unavoidable'],
            'paid_delta':pd,'combined_rays_delta':rd,'elapsed_delta':sd,
            'common_steps_delta':sd if common else None,'common_distance_delta_m':dd if common else None,
            'first_action_or_pose_divergence':divergence,'next_paid_step':next_paid,
            'outcomes_preserved':preserved,
            'common_success_observation_saving':bool(common and preserved and pd<0 and rd<=0 and sd<=0 and dd<=0)})
    write(t/'paired.json',rows)
    groups=defaultdict(list)
    for r in rows:groups[r['safety']].append(r)
    totals=[]
    for s,rr in groups.items():
        totals.append({'safety':s,'interventions':len(rr),
            'goal_harms':sum(r['goal_delta']<0 for r in rr),'goal_rescues':sum(r['goal_delta']>0 for r in rr),
            'increased_nonfirst_onsets':sum(r['nonfirst_onset_delta']>0 for r in rr),
            'outcomes_preserved':sum(r['outcomes_preserved'] for r in rr),
            'one_scan_saving_no_worse_common_success':sum(r['common_success_observation_saving'] for r in rr),
            'unchanged_action_pose_sequence':sum(r['first_action_or_pose_divergence'] is None for r in rr),
            'net_paid_decrease_cases':sum(r['paid_delta']<0 for r in rr),
            'net_paid_unchanged_cases':sum(r['paid_delta']==0 for r in rr),
            'net_paid_increase_cases':sum(r['paid_delta']>0 for r in rr)})
    write(t/'summary.json',{'totals':totals,'interventions':149,'baseline_replays':52,
        'policy_selection_authorized':False,'caveat':'One omission from a fresh identical prefix; effects are not additive, and no deployable oracle rule follows.'})
    lines=['# Deadline single-scan omission engineering audit','',
      '|Safety|Interventions|Goal harms|Goal rescues|Increased nonfirst onsets|Net paid decrease|No-worse common-success saving|',
      '|---|---:|---:|---:|---:|---:|---:|']
    for r in totals:
        lines.append(f"|{r['safety']}|{r['interventions']}|{r['goal_harms']}|{r['goal_rescues']}|{r['increased_nonfirst_onsets']}|{r['net_paid_decrease_cases']}|{r['one_scan_saving_no_worse_common_success']}|")
    lines+=['','Each omission has its own untreated prefix. Effects cannot be summed as achievable policy savings.',
        'Realized scan content and outcomes are evaluator-only and cannot be used in online decisions.',
        'No independent efficacy, safety promotion, or production cohort authorization.']
    (t/'research_report.md').write_text('\n'.join(lines)+'\n');manifest(t);print('\n'.join(lines))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('stage',choices=('check','run','report'))
    {'check':check,'run':run,'report':report}[p.parse_args().stage]()
