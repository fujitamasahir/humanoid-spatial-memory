"""Paired hand-scene navigation study of fixed discovery estimates."""
from __future__ import annotations
import argparse,json,subprocess,sys,time,traceback,hashlib
from pathlib import Path
from collections import defaultdict
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src')]
from c_v21_common import write,manifest,verify_manifest,sha,commit
import safety_forensics_v1 as forensic
from report_predictive_safety_v1 import read,summarize
from verify_dao_integrity import verify
from spatial_memory.res_phase_wait_v1 import RESH1PhaseWait
from spatial_memory.attenuated_dao_veto_v1 import AttenuatedDAOVeto,ARMS as NEW
OUT=ROOT/'results/phase2_mujoco/attenuated_dao_veto_v1'
OLD=ROOT/'results/phase2_mujoco/res_phase_wait_v1'
AUDIT=ROOT/'results/phase2_mujoco/attenuated_discovery_v1'
BASE='b59b7f3d98757c5c31b1cde2b09133b2bb853529'
ARMS=('periodic4','age4','age5','caa_full','dao_veto',*NEW)
VERSIONS={'original':None,'res_h1_phase_wait':RESH1PhaseWait}
SOURCES=('src/spatial_memory/attenuated_dao_veto_v1.py','src/spatial_memory/attenuated_discovery_v1.py',
 'src/spatial_memory/discovery_observation.py','src/spatial_memory/dao_navigation_compat_v1_1.py',
 'src/spatial_memory/dao_navigation_v1.py','src/spatial_memory/evaluation.py','src/spatial_memory/navigation.py',
 'src/spatial_memory/emergency_safety.py','src/spatial_memory/res_phase_wait_v1.py',
 'src/spatial_memory/risk_ranked_emergency_v1.py','src/spatial_memory/mujoco_navigation.py',
 'src/spatial_memory/mujoco_perception.py','src/spatial_memory/cadence_age.py','src/spatial_memory/change_aware_age.py',
 'src/spatial_memory/scheduling.py','scripts/safety_forensics_v1.py','scripts/report_predictive_safety_v1.py',
 'scripts/run_attenuated_dao_veto_v1.py','tests/test_attenuated_dao_veto_v1.py',
 'docs/attenuated_dao_veto_v1_protocol.md')
def load(p):return json.loads(p.read_text())
def fingerprints():return {p:sha(ROOT/p) for p in SOURCES}
def check():
    t=OUT/'prepared';t.mkdir(parents=True,exist_ok=False)
    for d in (OLD/'expansion',OLD/'expansion_analysis',AUDIT/'audit',AUDIT/'analysis'):verify_manifest(d)
    write(t/'integrity_before.json',verify())
    definitions=load(OLD/'expansion/matrix_spec.json')['scenarios']
    assert len(definitions)==26
    write(t/'matrix_spec.json',{'scenarios':definitions,'arms':list(ARMS),'versions':list(VERSIONS)})
    tests=['tests/test_attenuated_dao_veto_v1.py','tests/test_attenuated_discovery_v1.py',
           'tests/test_discovery_observation.py','tests/test_res_phase_wait_v1.py',
           'tests/test_dao_navigation_compat_v1_1.py','tests/test_phase2_emergency_safety.py']
    cmd=[sys.executable,'-m','pytest','-q',*tests,f'--junitxml={t/"tests.xml"}']
    p=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
    (t/'tests.log').write_text(p.stdout+p.stderr);print(p.stdout+p.stderr,flush=True)
    write(t/'gate.json',{'returncode':p.returncode,'command':cmd});manifest(t)
    if p.returncode:raise SystemExit(p.returncode)
    write(OUT/'binding.json',{'base':BASE,'source_commit':commit(),'sources':fingerprints(),
          'prepared_manifest_sha256':sha(t/'artifact_manifest.json'),
          'old_manifest_sha256':sha(OLD/'expansion/artifact_manifest.json'),'episodes':416})
def gate():
    b=load(OUT/'binding.json');verify_manifest(OUT/'prepared');verify_manifest(OLD/'expansion')
    assert b['sources']==fingerprints() and b['prepared_manifest_sha256']==sha(OUT/'prepared/artifact_manifest.json')
    assert b['old_manifest_sha256']==sha(OLD/'expansion/artifact_manifest.json')
    assert load(OUT/'prepared/gate.json')['returncode']==0
    for p,h in b['sources'].items():
        assert hashlib.sha256(subprocess.check_output(['git','show',f'HEAD:{p}'],cwd=ROOT)).hexdigest()==h,p
def episode(d,arm,safety):
    original=forensic.factory;created={}
    def factory(initial,name,options):
        c=AttenuatedDAOVeto(initial,factor=NEW[name],**options) if name in NEW else original(initial,name,options)
        created['controller']=c;return c
    forensic.factory=factory
    try:e=forensic.run_case(d,arm,candidate_class=VERSIONS[safety],detailed=False)
    finally:forensic.factory=original
    c=created['controller'];e.update(safety=safety,role=d['role'],declared_contact_class=d['declared_contact_class'])
    e['scheduler_decisions']=forensic.native(getattr(c,'decisions',[]))
    e['scheduler_ms']=getattr(c,'scheduler_ns',0)/1e6 if arm.startswith('dao_') else None
    return e
def run():
    gate();t=OUT/'matrix';t.mkdir(parents=True,exist_ok=False);done=[];start=time.perf_counter()
    spec=load(OUT/'prepared/matrix_spec.json')
    try:
        for n,d in enumerate(spec['scenarios'],1):
            for arm in ARMS:
                for safety in VERSIONS:
                    e=episode(d,arm,safety)
                    if arm not in NEW:forensic.parity(read(OLD/'expansion'/f'{n:02}_{arm}_{safety}.json.gz'),e)
                    forensic.save(t/f'{n:02}_{arm}_{safety}.json.gz',e);done.append([n,arm,safety])
            print(f'Completed {n}/26: {d["family"]}',flush=True)
        assert len(done)==416
        write(t/'summary.json',{'episodes':len(done),'baseline_parities':260,'elapsed_seconds':time.perf_counter()-start,
            'status':'COMPLETE_ENGINEERING_ONLY','source_commit':commit()})
        write(t/'integrity_after.json',verify());manifest(t)
    except Exception:
        (t/'failure.txt').write_text(traceback.format_exc());write(t/'partial.json',{'completed':done});manifest(t);raise
def report():
    gate();verify_manifest(OUT/'matrix');t=OUT/'analysis';t.mkdir(parents=True,exist_ok=False)
    spec=load(OUT/'prepared/matrix_spec.json');rows={};groups=defaultdict(list)
    for n,d in enumerate(spec['scenarios'],1):
        for arm in ARMS:
            for safety in VERSIONS:
                e=read(OUT/'matrix'/f'{n:02}_{arm}_{safety}.json.gz')
                r=summarize(e,d);r.update(scene_index=n,scheduler_ms=e['scheduler_ms'],
                   extra_requests_same_state=sum(x.get('extra_request_same_state',False) for x in e['scheduler_decisions']),
                   extra_grants_same_state=sum(x.get('extra_request_same_state',False) and x.get('granted',False) for x in e['scheduler_decisions']))
                rows[n,arm,safety]=r
                groups[safety,'all',arm].append(r)
                groups[safety,d['role'],arm].append(r)
    fields=('goals','contact_free_goal','distinct_actual_contact_episodes','contact_pairs',
        'proven_unavoidable_first_onsets','other_onsets_not_proven_unavoidable','paid_scans','emergency_scans',
        'combined_rays','steps','distance_m','blocked_actions','extra_requests_same_state','extra_grants_same_state')
    totals=[{'safety':s,'role':role,'arm':a,'episodes':len(rr),**{k:sum(r[k] for r in rr) for k in fields}}
        for (s,role,a),rr in sorted(groups.items())]
    pairs=[]
    for safety in VERSIONS:
        for candidate in NEW:
            for ref in ARMS[:5]:
                for n,d in enumerate(spec['scenarios'],1):
                    a,b=rows[n,ref,safety],rows[n,candidate,safety]
                    pairs.append({'safety':safety,'scene':d['family'],'role':d['role'],'candidate':candidate,'reference':ref,
                      'reference_goal':a['goals'],'candidate_goal':b['goals'],
                      'reference_contact_free_goal':a['contact_free_goal'],'candidate_contact_free_goal':b['contact_free_goal'],
                      'reference_nonfirst_onsets':a['other_onsets_not_proven_unavoidable'],
                      'candidate_nonfirst_onsets':b['other_onsets_not_proven_unavoidable'],
                      'paid_delta':b['paid_scans']-a['paid_scans'],'combined_rays_delta':b['combined_rays']-a['combined_rays'],
                      'common_steps_delta':b['steps']-a['steps'] if a['goals'] and b['goals'] else None,
                      'common_distance_delta':b['distance_m']-a['distance_m'] if a['goals'] and b['goals'] else None})
    write(t/'episode_metrics.json',list(rows.values()));write(t/'paired.json',pairs)
    write(t/'summary.json',{'totals':totals,'episodes':len(rows),'selection_authorized':False,
          'independent_efficacy_or_real_world_safety':False})
    lines=['# Fixed-estimator DAO-Veto: engineering navigation comparison','',
      '|Safety|Role|Policy|Goals|Contact-free goals|Nonfirst onsets|Paid scans|Combined rays|Extra same-state grants|',
      '|---|---|---|---:|---:|---:|---:|---:|---:|']
    for r in totals:
        lines.append(f"|{r['safety']}|{r['role']}|{r['arm']}|{r['goals']}/{r['episodes']}|{r['contact_free_goal']}|{r['other_onsets_not_proven_unavoidable']}|{r['paid_scans']}|{r['combined_rays']}|{r['extra_grants_same_state']}|")
    lines+=['','No safety replacement or winner selection authorized. Paired movement costs are restricted to common successes.',
      'Different safety versions are separate comparisons, not pooled independent samples.']
    (t/'research_report.md').write_text('\n'.join(lines)+'\n');manifest(t);print('\n'.join(lines))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('stage',choices=('check','run','report'))
    {'check':check,'run':run,'report':report}[p.parse_args().stage]()
