"""Versioned phase-wait engineering gate; reuses frozen RES infrastructure."""
from __future__ import annotations
import argparse,json,math,subprocess,sys
from collections import Counter
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src')]
import run_risk_ranked_safety_v1 as prior
from c_v21_common import write,manifest,verify_manifest,sha,commit
from spatial_memory.risk_ranked_emergency_v1 import RESH1
from spatial_memory.res_phase_wait_v1 import RESH1PhaseWait
from verify_dao_integrity import verify
from report_predictive_safety_v1 import read
from safety_forensics_v1 import parity
from spatial_memory.navigation import heading_index
OLD=ROOT/'results/phase2_mujoco/res_cycle_escape_v1'
OUT=ROOT/'results/phase2_mujoco/res_phase_wait_v1'
BASE='f8314410cae300d18c189e5700bbb31d9a45681e'
CANDIDATE='res_h1_phase_wait'
old_run=prior.run_case
prior.OUT=OUT
prior.BASE=BASE
prior.VERSIONS={'original':None,'res_h1':RESH1,CANDIDATE:RESH1PhaseWait}
prior.CANDIDATES=(CANDIDATE,)
prior.SOURCES=(*prior.SOURCES,'src/spatial_memory/res_phase_wait_v1.py',
    'tests/test_res_phase_wait_v1.py','scripts/run_res_phase_wait_v1.py',
    'docs/res_phase_wait_v1_protocol.md','scripts/report_predictive_safety_v1.py',
    'scripts/verify_dao_integrity.py')

def load(p):return json.loads(p.read_text())

def cases():
    result=load(OLD/'compact/matrix_spec.json')['scenarios']
    d=next(x for x in result if x['family']=='alternating')
    # New engineering controls vary the crossing period and pause, not a
    # random population or independent efficacy evaluation.
    a=deepcopy(d);a.update(name='phase_long_crossing',family='phase_long_crossing',
        role='new_phase_engineering',archive_index=None,
        pedestrians=[[(7,y) for y in (6,7,8,9,10,9,8,7)]])
    b=deepcopy(d);b.update(name='phase_paused_crossing',family='phase_paused_crossing',
        role='new_phase_engineering',archive_index=None,
        pedestrians=[[(7,y) for y in (7,8,8,9,8,8)]])
    return result+[a,b]
prior.cases=cases

def run_case(d,arm,*,candidate_class=None,detailed=False):
    e=old_run(d,arm,candidate_class=candidate_class,detailed=detailed)
    if arm in prior.ARM3 and candidate_class in (None,RESH1):
        prev=load(OLD/'compact/matrix_spec.json')['scenarios']
        n=next((i for i,x in enumerate(prev,1) if (x['family'],x['role'])==(d['family'],d['role'])),None)
        if n is not None:
            label='original' if candidate_class is None else 'res_h1'
            parity(read(OLD/'compact'/f'{n:02}_{arm}_{label}.json.gz'),e)
    return e
prior.run_case=run_case

def audit(target):
    old=load(OLD/'prepared/prior_failed_case_audit.json')
    rows=[]
    for x in old['records']:
        ordinary=x['ordinary_selected'] or ['none',None]
        if (not x['rotation_cycle'] or x['h1_selected'][0]!='turn'
                or ordinary[0] not in ('move','sidestep','retreat')
                or x['h1_selected_assessment'].get('certified',False)):continue
        waits=[a for a in x['archived_alternatives'] if a['action'][0]=='wait' and a.get('certified',False)]
        rows.append({'step':x['step'],'position':x['position'],'heading':x['heading_index'],
                     'base_action':ordinary,'h1_action':x['h1_selected'],'certified_wait':waits})
    write(target/'phase_deadlock_audit.json',{'eligible_steps':rows,
        'prior_action_counts':old['action_counts'],
        'caveat':'Archived same-state alternatives; no causal outcome or next-step safety guarantee.'})
    if not any(x['certified_wait'] for x in rows):
        raise RuntimeError('No archived certified wait supporting mechanism')
def check():
    target=OUT/'prepared';target.mkdir(parents=True,exist_ok=False)
    for p in (OLD/'prepared',OLD/'compact',OLD/'analysis',OLD/'cycle_analysis',prior.OLD/'matrix',prior.OLD/'forensics'):
        verify_manifest(p)
    write(target/'integrity_before.json',verify())
    write(target/'scenarios.json',cases())
    audit(target)
    tests=['tests/test_res_phase_wait_v1.py','tests/test_res_cycle_escape_v1.py','tests/test_risk_ranked_emergency_v1.py',
        'tests/test_predictive_emergency_v1.py','tests/test_phase2_emergency_safety.py',
        'tests/test_dao_navigation_compat_v1_1.py','tests/test_phase2_mujoco.py']
    cmd=[sys.executable,'-m','pytest','-q',*tests,f'--junitxml={target/"tests.xml"}']
    p=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
    (target/'tests.log').write_text(p.stdout+p.stderr);print(p.stdout+p.stderr,flush=True)
    write(target/'gate.json',{'returncode':p.returncode,'command':cmd});manifest(target)
    if p.returncode:raise SystemExit(p.returncode)
    write(OUT/'binding.json',{'base':BASE,'implementation_commit':commit(),'sources':prior.files(),
       'prepared_manifest_sha256':sha(target/'artifact_manifest.json'),
       'compact_cases':len(cases()),'compact_arms':list(prior.ARM3),'versions':list(prior.VERSIONS)})

def report():
    prior.report('compact')
    target=OUT/'phase_analysis';target.mkdir(parents=True,exist_ok=False)
    spec=load(OUT/'compact/matrix_spec.json')
    summary=load(OUT/'analysis/summary.json')
    rows=load(OUT/'analysis/episode_metrics.json')
    idx={(r['scene_index'],r['arm'],r['safety']):r for r in rows}
    comparisons=[];activations=[]
    for n,d in enumerate(spec['scenarios'],1):
        for arm in spec['arms']:
            a=idx[n,arm,'res_h1'];b=idx[n,arm,CANDIDATE]
            e=read(OUT/'compact'/f'{n:02}_{arm}_{CANDIDATE}.json.gz')
            changes=[{'step':x['step'],'before':x['pre_phase_selected'],'after':x['selected_after'],
                      'candidates':x['phase_wait_certificate']}
                     for x in e['candidate_diagnostics'] if x.get('phase_wait_applied')]
            if changes:activations.append({'scene':d['family'],'arm':arm,'changes':changes})
            comparisons.append({'scene':d['family'],'role':d['role'],'arm':arm,
                'old_compact_scene':n<=14,'h1_goal':a['goals'],'phase_goal':b['goals'],
                'h1_contact_free_goal':a['contact_free_goal'],'phase_contact_free_goal':b['contact_free_goal'],
                'h1_nonfirst_onsets':a['other_onsets_not_proven_unavoidable'],
                'phase_nonfirst_onsets':b['other_onsets_not_proven_unavoidable'],
                'common_steps_delta':b['steps']-a['steps'] if a['goals'] and b['goals'] else None,
                'common_distance_delta_m':b['distance_m']-a['distance_m'] if a['goals'] and b['goals'] else None,
                'paid_delta':b['paid_scans']-a['paid_scans'],'phase_waits':len(changes)})
    flags={'original_gate':summary['gates'][CANDIDATE]['pass'],
        'no_new_nonfirst_onsets_vs_h1':all(r['phase_nonfirst_onsets']<=r['h1_nonfirst_onsets'] for r in comparisons),
        'no_goal_harm_vs_h1':all(r['phase_goal']>=r['h1_goal'] for r in comparisons),
        'no_contact_free_goal_harm_vs_h1':all(r['phase_contact_free_goal']>=r['h1_contact_free_goal'] for r in comparisons),
        'improve_old_compact_goals_vs_h1':sum(r['phase_goal']-r['h1_goal'] for r in comparisons if r['old_compact_scene'])>0,
        'phase_mechanism_activated':bool(activations)}
    write(target/'paired_h1.json',comparisons);write(target/'activations.json',activations)
    write(target/'authorization.json',{'expand':all(flags.values()),'checks':flags,
        'candidate':CANDIDATE,'descriptive_engineering_only':True})
    manifest(target);print('Additional H1-preservation gate:',flags,flush=True)

def expand():
    verify_manifest(OUT/'phase_analysis')
    if not load(OUT/'phase_analysis/authorization.json')['expand']:
        print('Expansion not authorized: H1-preservation gate failed.');return
    prior.run('expansion')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('stage',choices=['check','compact','report','expand','report-expand'])
    a=p.parse_args().stage
    if a=='check':check()
    elif a=='compact':prior.run('compact')
    elif a=='report':report()
    elif a=='expand':expand()
    else:prior.report('expansion')
