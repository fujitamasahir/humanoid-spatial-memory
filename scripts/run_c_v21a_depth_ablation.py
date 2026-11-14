"""C v2.1a depth control: matched new objective, H=1 versus H=3.

Existing synthetic fixtures are regression material, not a fresh efficacy test.
Only the original admitted FIT72 cases are used after the local correctness gate.
No previous evidence is overwritten.
"""
from __future__ import annotations
import argparse
import gzip
import json
import math
import subprocess
import sys
from pathlib import Path
from statistics import mean

from c_v21_common import ROOT, OUT as OLD, write, manifest, verify_manifest, sha, commit
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'scripts')]

OUT = ROOT/'results/phase2_mujoco/c_v21a_depth_control_v1'
BASE = '63e2debae7376b88ef0d391a0ab3bf93438aec16'
ARMS = ('h1_k', 'h3_k', 'h1_topology', 'h3_topology')
OLD_NAMES = {'h3_k':'ms_k', 'h3_topology':'ms_topology'}
SOURCES = (
    'src/spatial_memory/multistep_depth_ablation.py',
    'src/spatial_memory/multistep_evi.py',
    'src/spatial_memory/multistep_reference.py',
    'scripts/run_c_v21a_depth_ablation.py',
    'tests/test_multistep_depth_ablation.py',
    'docs/c_v21a_depth_control_protocol.md',
)

def fingerprints():
    return {p:sha(ROOT/p) for p in SOURCES}

def load(path):
    return json.loads(Path(path).read_text())

def episode(directory,n,arm):
    with gzip.open(directory/f'episode_{n:03}_{arm}.json.gz','rt') as fh:
        return json.load(fh)

def check():
    target=OUT/'correctness'
    target.mkdir(parents=True,exist_ok=False)
    cmd=[sys.executable,'-m','pytest','-q','tests/test_multistep_depth_ablation.py',
         'tests/test_c_v21_multistep.py','tests/test_c_v21_review.py','tests/test_c_v21_navigation.py']
    proc=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True)
    (target/'pytest.log').write_text(proc.stdout+proc.stderr)
    print(proc.stdout+proc.stderr,flush=True)
    write(target/'gate.json',{'status':'PASS' if proc.returncode==0 else 'REJECTED',
        'source_sha256':fingerprints(),'commit':commit(),'command':cmd,
        'previous_fixtures_are_regression_only':True,'returncode':proc.returncode})
    manifest(target)
    if proc.returncode:raise SystemExit(proc.returncode)

def require_gate():
    verify_manifest(OUT/'correctness')
    gate=load(OUT/'correctness/gate.json')
    if gate['status']!='PASS' or gate['source_sha256']!=fingerprints():
        raise RuntimeError('Local correctness gate missing/failing or source drift')
    # Verify the old prospective gate and frozen source binding using its own runner.
    import evaluate_c_v21_fit72 as previous
    previous.require_gate()
    verify_manifest(OLD/'fit72')

def run_case(payload,schedule,arm,config):
    from spatial_memory.multistep_depth_ablation import ARMS as functions, MultiStepParameters
    import evaluate_persistence_evi_fit72 as runner
    import evaluate_c_v2_candidate_coverage_fit72 as fit
    original=runner.PersistenceEVIController
    topology=arm.endswith('topology')
    class Controller(original):
        def __init__(self,*a,**kw):
            if kw.get('persistence'):raise RuntimeError('Persistence change prohibited')
            kw['evi_function']=functions[arm]
            kw['evi_parameters']=MultiStepParameters(3 if topology else 5)
            super().__init__(*a,**kw)
    runner.PersistenceEVIController=Controller
    try:
        row,trace,diag=fit.run_measured(payload,schedule,'c_topology3d' if topology else 'c_k',config)
    finally:
        runner.PersistenceEVIController=original
    row['depth_ablation_arm']=arm
    diag['depth_ablation_arm']=arm
    return row,trace,diag

def flatten(n,arm,row,diag):
    import evaluate_c_v2_candidate_coverage_fit72 as fit
    flat=fit.flat(arm,row,diag)
    # The old one-step reason interpretation is not applicable to the new objective.
    for k in list(flat):
        if k.startswith('evi_') or k in ('mean_D','mean_V','total_counterfactual_grid_copy_cell_reads'):
            flat.pop(k)
    decisions=diag.get('decisions',[])
    scored=[d for d in decisions if 'candidate_evaluations' in d or 'lookahead_horizon' in d]
    flat.update(episode=n,identity=row['world_identity'],schedule=row['schedule'],
        scored_decisions=len(scored),
        prefix_step_visits=sum(d.get('prefix_step_visits',0) for d in decisions),
        recovery_checks=sum(d.get('recovery_checks',0) for d in decisions),
        grid_copy_reads=sum(d.get('counterfactual_grid_cells_copied',0) for d in decisions),
        future_visibility_computations=sum(d.get('future_visibility_computations',0) for d in decisions))
    return flat

def parity(old,row,trace):
    import evaluate_event_observation_fit72 as ref
    if ref.rdao_evaluator._signature(row)!=ref.rdao_evaluator._signature(old['row']):
        raise RuntimeError('Frozen reference metric signature mismatch')
    ref._compare_trace(old['trace'],ref.base._jsonable_row(trace))

def run(smoke):
    require_gate()
    import evaluate_c_v2_candidate_coverage_fit72 as fit
    import evaluate_event_observation_fit72 as ref
    fit.verify_original_data_integrity()
    if not smoke:
        verify_manifest(OUT/'smoke')
        if load(OUT/'smoke/summary.json')['status']!='PASS_SMOKE':
            raise RuntimeError('Smoke gate failed')
    target=OUT/('smoke' if smoke else 'fit72')
    target.mkdir(parents=True,exist_ok=False)
    _,_,prov,_=ref.base.load_baseline()
    config=ref.base.frozen_config(prov)
    worlds={p['identity']:p for p in ref.navigation.admitted_worlds()}
    write(target/'provenance.json',{'commit':commit(),'base':BASE,'source_sha256':fingerprints(),
         'config':config,'reference_manifest_sha256':sha(OLD/'reference_replays/artifact_manifest.json'),
         'h3_manifest_sha256':sha(OLD/'fit72/artifact_manifest.json'),
         'FIT_is_descriptive_not_independent':True})
    rows=[]
    for n in range(1,3 if smoke else 73):
        old=episode(OLD/'reference_replays',n,'age')
        identity,schedule,_,seed=old['trace']['key']
        for arm in ARMS:
            row,trace,diag=run_case(worlds[identity],schedule,arm,config)
            if arm in OLD_NAMES:
                parity(episode(OLD/'fit72',n,OLD_NAMES[arm]),row,trace)
            if not smoke and n<=2:
                parity(episode(OUT/'smoke',n,arm),row,trace)
            if smoke and row['g1_unwanted_contact_pairs']:
                raise RuntimeError('Smoke unwanted contact')
            if row['g1_unselected_action_shield_queries'] or row['observation_count']>20:
                raise RuntimeError('Safety or observation-cap invariant failed')
            # Frozen model has no future visibility queries in either arm.
            for d in diag['decisions']:
                if d.get('future_visibility_computations',0):
                    raise RuntimeError('Unexpected future visibility computation')
                if d.get('plan_calls',0)>(7 if arm.endswith('topology') else 11):
                    raise RuntimeError('Counterfactual planning ceiling exceeded')
            fit.save_episode(target,n,arm,row,trace,diag)
            rows.append(flatten(n,arm,row,diag))
        if smoke or n%6==0:
            print(f'{"Smoke" if smoke else "FIT"} {n}/{2 if smoke else 72} keys',flush=True)
    fit.verify_original_data_integrity()
    fit.csv_write(target/'episodes.csv',rows)
    write(target/'summary.json',{'status':'PASS_SMOKE' if smoke else 'COMPLETED_DESCRIPTIVE_FIT_NOT_VALIDATION',
        'episodes':len(rows),'arms':{a:aggregate([r for r in rows if r['arm']==a]) for a in ARMS},
        'h3_replay_parity':True})
    manifest(target)

METRICS=('paid_memory_scans','combined_rays','elapsed_steps','travel_distance_m',
         'blocked_attempts','emergency_safety_interventions','unwanted_contacts',
         'scheduler_ms','episode_wall_time_seconds')
def aggregate(rows):
    return {'episodes':len(rows),'goals':sum(bool(r['success']) for r in rows),
        **{f'mean_{k}':mean(r[k] for r in rows) for k in METRICS}}

def report():
    import csv
    verify_manifest(OUT/'fit72')
    if load(OUT/'fit72/summary.json')['status']!='COMPLETED_DESCRIPTIVE_FIT_NOT_VALIDATION':
        raise RuntimeError('Full experiment incomplete')
    verify_manifest(OLD/'reference_replays')
    import evaluate_c_v2_candidate_coverage_fit72 as fit
    target=OUT/'analysis'
    target.mkdir(parents=True,exist_ok=False)
    # Read the actual saved per-episode JSON and avoid legacy EVI columns.
    allrows={}
    for n in range(1,73):
        for arm in ARMS:
            p=episode(OUT/'fit72',n,arm)
            allrows[(n,arm)]=flatten(n,arm,p['row'],p['diagnostics'])
        for arm in ('periodic','age','c0','c_k','c_topology3d'):
            # C v2.1 uses these names; discover aliases by exact local filenames.
            aliases={'c0':('C0',),'c_k':('C-K',),'c_topology3d':('C-Topology3-d',)}
            candidates=aliases.get(arm,(arm,))
            found=[a for a in candidates if (OLD/'reference_replays'/f'episode_{n:03}_{a}.json.gz').exists()]
            if len(found)!=1:raise RuntimeError(f'Missing/ambiguous archived reference: {arm}, {n}')
            p=episode(OLD/'reference_replays',n,found[0])
            allrows[(n,arm)]=flatten(n,arm,p['row'],p['diagnostics'])
    arms=('periodic','age','c0','c_k','c_topology3d',*ARMS)
    summaries={a:aggregate([allrows[n,a] for n in range(1,73)]) for a in arms}
    comparisons=[]
    pair_rows=[]
    for candidate,reference in [('h1_k','c_k'),('h3_k','h1_k'),
        ('h1_topology','c_topology3d'),('h3_topology','h1_topology')]+[(a,b) for a in ARMS for b in ('age','periodic')]:
        pairs=[(allrows[n,reference],allrows[n,candidate]) for n in range(1,73)]
        common=[(a,b) for a,b in pairs if a['success'] and b['success']]
        for a,b in pairs:
            if (a['identity'],a['schedule'])!=(b['identity'],b['schedule']):
                raise RuntimeError('Unpaired identity')
            pair_rows.append({'reference':reference,'candidate':candidate,'identity':a['identity'],
                'schedule':a['schedule'],'reference_success':a['success'],'candidate_success':b['success'],
                **{f'delta_{k}':b[k]-a[k] for k in METRICS}})
        comparisons.append({'reference':reference,'candidate':candidate,
            'rescues':sum(not a['success'] and b['success'] for a,b in pairs),
            'harms':sum(a['success'] and not b['success'] for a,b in pairs),
            'common_successes':len(common),
            'all_episode_delta':{k:mean(b[k]-a[k] for a,b in pairs) for k in METRICS},
            'common_success_delta':{k:mean(b[k]-a[k] for a,b in common) if common else None for k in METRICS}})
    fit.csv_write(target/'paired_episode_deltas.csv',pair_rows)
    write(target/'summary.json',{'status':'DESCRIPTIVE_DEPTH_ABLATION','arms':summaries,'paired':comparisons,
        'caveat':'36 previously reused maze lineages; two schedules are correlated. No independent validation.'})
    lines=['# C v2.1a new-objective depth control','',
        'Descriptive FIT72 only. Positive deltas mean higher candidate costs.','',
        '|Arm|Goals/72|Paid scans|H80 steps|Combined rays|Scheduler ms|',
        '|---|---:|---:|---:|---:|---:|']
    for a,r in summaries.items():
        lines.append(f"|{a}|{r['goals']}|{r['mean_paid_memory_scans']:.3f}|{r['mean_elapsed_steps']:.3f}|{r['mean_combined_rays']:.2f}|{r['mean_scheduler_ms']:.3f}|")
    lines.extend(['','|Candidate vs reference|Rescues/harms|Common successes|All-scan delta|Common-step delta|Common-distance delta (m)|',
        '|---|---:|---:|---:|---:|---:|'])
    for r in comparisons:
        c=r['common_success_delta'];d=r['all_episode_delta']
        fmt=lambda x:'NA' if x is None else f'{x:.3f}'
        lines.append(f"|{r['candidate']} vs {r['reference']}|{r['rescues']}/{r['harms']}|{r['common_successes']}|{fmt(d['paid_memory_scans'])}|{fmt(c['elapsed_steps'])}|{fmt(c['travel_distance_m'])}|")
    (target/'research_report.md').write_text('\n'.join(lines)+'\n')
    manifest(target)
    print('\n'.join(lines))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('stage',choices=['check','smoke','full','report'])
    stage=p.parse_args().stage
    if stage=='check':check()
    elif stage=='report':report()
    else:run(stage=='smoke')
