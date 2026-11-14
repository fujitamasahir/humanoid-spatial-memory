"""Independent post-screen conformance check for the frozen C v2.0c screen."""
from __future__ import annotations
import hashlib, json, subprocess, sys
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
RESULT=ROOT/'results/phase2_mujoco/c_v2c_topology_v2/synthetic_mechanism_results.json'
OUT=RESULT.parent/'gate_review.json'
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]

SOURCE_PATHS=['docs/phase2_c_v2c_topology_protocol.md','docs/phase2_c_v2c_topology_protocol_v2.md',
 'docs/phase2_c_v2c_fit_intervention_protocol.md',
 'scripts/c_v2c_fixtures.py',
 'scripts/validate_c_v2c_fixture_annotations.py','scripts/run_c_v2c_topology_fixtures.py',
 'scripts/review_c_v2c_mechanism.py',
 'src/spatial_memory/topology_evi_c.py','src/spatial_memory/topology_reference.py',
 'src/spatial_memory/evi.py','src/spatial_memory/candidate_coverage.py']
ARMS=('C0','C-K','C-Route3','C-Topology3-corrected')

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def _recompute_metrics(data):
    rows=data['fixtures'];out={}
    for arm in ARMS:
        nonempty=[r for r in rows if r['useful_candidates']]
        bestrows=[r for r in rows if r['exhaustive_best_cells']]
        tp=sum(sum(c in r['arms'][arm]['selected'] for c in r['useful_candidates']) for r in rows)
        den=sum(len(r['useful_candidates']) for r in rows)
        btp=sum(sum(c in r['arms'][arm]['selected'] for c in r['exhaustive_best_cells']) for r in rows)
        bden=sum(len(r['exhaustive_best_cells']) for r in rows)
        agreement=sum(bool(r['arms'][arm]['common_scan_agreement']) for r in rows)
        out[arm]={
          'macro_useful_recall':sum(r['arms'][arm]['useful_recall'] for r in nonempty)/len(nonempty) if nonempty else None,
          'micro_useful_recall':tp/den if den else None,
          'macro_max_D_recall':sum(r['arms'][arm]['max_D_recall'] for r in bestrows)/len(bestrows) if bestrows else None,
          'micro_max_D_recall':btp/bden if bden else None,
          'common_scan_correct':agreement,'common_scan_denominator':len(rows),
          'actual_scans':sum(bool(r['arms'][arm]['actual_authorized']) for r in rows),
          'false_positives':sum(bool(r['arms'][arm]['actual_false_positive']) for r in rows),
          'false_negatives':sum(bool(r['arms'][arm]['actual_false_negative']) for r in rows)}
    return out

def review():
    if not RESULT.exists(): raise FileNotFoundError(RESULT)
    data=json.loads(RESULT.read_text());checks={};errors=[]
    checks['result_status']=data.get('status')=='COMPLETED_C_V2C_SYNTHETIC_SCREEN'
    checks['no_fit_access']=data.get('FIT_data_accessed') is False and data.get('admitted_worlds_loaded') is False and data.get('protected_generator_called') is False
    checks['fixture_count']=data.get('fixture_count')==48 and len(data.get('fixtures',[]))==48
    checks['family_balance']=all(v==6 for v in data.get('family_counts',{}).values()) and len(data.get('family_counts',{}))==8
    checks['correctness_status']=data.get('correctness_validation',{}).get('status')=='PASS'
    checks['annotations_status']=data.get('annotation_validation',{}).get('status')=='PASS' and data.get('annotation_validation',{}).get('candidate_arms_executed') is False
    checks['policy_preflight']=len(data.get('policy_preflight',[]))==48 and all(x.get('target_in_visible_candidates') and x.get('target_is_max_D') is not False for x in data.get('policy_preflight',[]))
    expected={p:sha(ROOT/p) for p in SOURCE_PATHS}
    checks['source_hashes']=data.get('source_sha256')==expected
    for r in data.get('fixtures',[]):
        if set(r.get('arms',{}))!=set(ARMS): errors.append(f"{r.get('fixture_id')}: arm set mismatch")
        if not r.get('useful_candidates') and any(r['arms'][a]['useful_recall'] is not None for a in ARMS):errors.append(f"{r.get('fixture_id')}: empty useful denominator mishandled")
        for a in ARMS:
            d=r['arms'][a]
            if d['plan_calls']>(11 if a=='C-K' else 7):errors.append(f"{r['fixture_id']}/{a}: A* cap exceeded")
            if a=='C-Topology3-corrected' and d['graph_work_units']>d['graph_work_bound']:errors.append(f"{r['fixture_id']}: work bound exceeded")
    checks['row_invariants']=not errors
    recomputed=_recompute_metrics(data)
    saved=data.get('aggregates',{}).get('overall',{})
    for arm in ARMS:
        for key in ('macro_useful_recall','micro_useful_recall','macro_max_D_recall','micro_max_D_recall','common_scan_correct','actual_scans','false_positives','false_negatives'):
            if saved.get(arm,{}).get(key)!=recomputed[arm][key]:errors.append(f'aggregate mismatch {arm}/{key}')
    checks['aggregate_denominators_and_values']=not errors
    gate=data.get('mechanism_gate',{});c0=recomputed['C0'];topo=recomputed['C-Topology3-corrected']
    if c0['macro_useful_recall'] is None or topo['macro_useful_recall'] is None:
        errors.append('empty macro recall denominator')
    else:
        checks['numeric_useful_gain']=topo['macro_useful_recall']-c0['macro_useful_recall']>=.10
        checks['numeric_micro_non_decrease']=topo['micro_useful_recall']>=c0['micro_useful_recall']
        checks['numeric_max_D_non_decrease']=topo['macro_max_D_recall']>=c0['macro_max_D_recall']
        checks['numeric_scan_agreement_gain']=(topo['common_scan_correct']-c0['common_scan_correct'])/48>=.05
    no_benefit=[r for r in data['fixtures'] if r['family']=='no_benefit_and_C0_controls' and r['fixture_id'].endswith(('v00','v01','v02')) or r['family']=='occupied_shortcut_or_none' and r['fixture_id'].endswith(('v03','v04','v05'))]
    checks['no_benefit_authorization']=len(no_benefit)==6 and not any(r['arms']['C-Topology3-corrected']['actual_authorized'] for r in no_benefit)
    checks['astar_and_work_limits']=all(r['arms']['C-Topology3-corrected']['plan_calls']<=7 and r['arms']['C-Topology3-corrected']['graph_work_units']<=r['arms']['C-Topology3-corrected']['graph_work_bound'] for r in data['fixtures'])
    p95_ns=sorted(t for fixture in data['graph_benchmarks'] for t in fixture['samples_ns'])
    measured_p95=int(np.percentile(p95_ns,95)) if p95_ns else None
    checks['runtime_protocol']=len(data.get('graph_benchmarks',[]))==48 and all(x.get('warmup_calls')==10 and x.get('measured_calls')==100 and len(x.get('samples_ns',[]))==100 for x in data.get('graph_benchmarks',[]))
    checks['runtime_gate']=measured_p95 is not None and measured_p95<=5_000_000
    # Mandatory correctness/conformance checks are rerun by this separate process.
    cmd=[sys.executable,'-m','pytest','-q','tests/test_topology_evi_c_correctness.py','tests/test_c_v2c_fixture_annotations.py']
    test=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True)
    checks['independent_test_rerun']=test.returncode==0
    checks['numeric_gate_consistency']=gate.get('status')=='PASS' and all(gate.get(k) is True for k in ('macro_useful_recall_gain_ge_0_10','micro_useful_recall_non_decrease','macro_max_D_recall_non_decrease','scan_agreement_gain_ge_0_05','no_benefit_cases_pass','all_A_star_limits_respected','graph_work_bound_respected','graph_analysis_p95_le_5ms'))
    errors.extend([x for x,v in checks.items() if not v])
    result={'status':'ACCEPTED_FOR_FIT' if not errors else 'INVALID_STOP_BEFORE_FIT',
      'protocol':'docs/phase2_c_v2c_topology_protocol_v2.md','intervention_protocol':'docs/phase2_c_v2c_fit_intervention_protocol.md',
      'checked_at_utc':subprocess.run(['date','-u','+%Y-%m-%dT%H:%M:%SZ'],capture_output=True,text=True).stdout.strip(),
      'checks':checks,'errors':errors,'recomputed_overall':recomputed,'runtime_p95_ns_independent':measured_p95,
      'test_command':cmd,'test_returncode':test.returncode,'test_stdout':test.stdout,'test_stderr':test.stderr,
      'result_sha256':sha(RESULT),'source_sha256':expected,'FIT_data_accessed_by_reviewer':False}
    OUT.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':result['status'],'checks':checks,'errors':errors,'output':str(OUT)},indent=2))
    return 0 if not errors else 2

if __name__=='__main__':raise SystemExit(review())
