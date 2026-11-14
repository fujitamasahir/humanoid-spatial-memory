"""Run the frozen C v2.0c synthetic mechanism suite; never loads FIT worlds."""
from __future__ import annotations
import hashlib,json,os,platform,sys,subprocess
from pathlib import Path
from time import perf_counter_ns
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from c_v2c_fixtures import build_formal_fixtures
from validate_c_v2c_fixture_annotations import validate_annotations,SENSOR
from spatial_memory.evi import EVIParameters,information_value,visible_cells
from spatial_memory.navigation import plan
from spatial_memory.candidate_coverage import (
    ExpandedEVIParameters,information_value_original_audit,
    information_value_uncertainty_k,information_value_route)
from spatial_memory.topology_evi_c import (
    information_value_topology_c,
    analyze_public_topology_c,eligible_topology_candidates_c,
    rank_topology_candidates_c)

OUT=ROOT/'results/phase2_mujoco/c_v2c_topology_v2'
REMAINING=10


def independent_exhaustive_evi(grid,probability,start,goal,yaw,unknown):
    """Offline reference reimplements V/D; only frozen point A* is shared."""
    nominal=plan(grid,start,goal,unknown);footprint=visible_cells(grid,start,yaw,**SENSOR)
    candidates=[c for c in footprint if c!=tuple(start) and .05<float(probability[c[1],c[0]])<.95]
    rows=[];calls=1
    for cell in sorted(candidates,key=lambda c:(c[1],c[0])):
        route_outcomes=[]
        for outcome in (0,1):
            changed=grid.copy();changed[cell[1],cell[0]]=outcome
            route_outcomes.append(plan(changed,start,goal,unknown));calls+=1
        q=float(probability[cell[1],cell[0]])
        losses=[]
        for outcome,route in enumerate(route_outcomes):
            row=[]
            for assumed in (0,1):
                if not route: row.append(80.)
                else: row.append(float((len(route)-1)+(80 if assumed==1 and cell in route else 0)))
            losses.append(row)
        expected_before=min((1-q)*l[0]+q*l[1] for l in losses)
        expected_after=(1-q)*min(l[0] for l in losses)+q*min(l[1] for l in losses)
        value=max(0.,expected_before-expected_after)
        first=[]
        for route in route_outcomes:first.append(tuple(route[1]) if len(route)>1 else None)
        delay=value*min(q,1-q) if first[0]!=first[1] else 0.
        rows.append({'cell':cell,'V':value,'D':delay,'q':q,
            'free_first_action':first[0],'occupied_first_action':first[1]})
    common_cost=.5+.01*7+.5/max(1,REMAINING)
    return rows,common_cost,calls,nominal,candidates


def _arms(grid,p,start,goal,yaw,unknown):
    args=(grid,p,start,goal,yaw,unknown,SENSOR,REMAINING)
    reference=information_value(grid,p,start,goal,yaw,unknown,SENSOR,REMAINING,EVIParameters(max_candidates=3))
    audit=information_value_original_audit(*args,EVIParameters(max_candidates=3))
    assert all(reference[k]==audit[k] for k in ('value','delay_regret','cell','cost','net_value','plan_calls'))
    return {
      'C0':(reference,audit['shortlisted_candidates']),
      'C-K':(information_value_uncertainty_k(*args,ExpandedEVIParameters(max_candidates=5)),None),
      'C-Route3':(information_value_route(*args,ExpandedEVIParameters(max_candidates=3)),None),
      'C-Topology3-corrected':(information_value_topology_c(*args,unknown_parameters(EVIParameters(max_candidates=3))),None),
    }


def unknown_parameters(parameters):
    # Positional compatibility for the common selector function signature.
    return parameters


def _selected(result,audit_shortlist):
    records=audit_shortlist if audit_shortlist is not None else result.get('shortlisted_candidates',[])
    return [tuple(x['cell']) for x in records]


def _evaluate_one(f,exhaustive,common_cost,arms):
    e_by={x['cell']:x for x in exhaustive}
    maxd=max((x['D'] for x in exhaustive),default=0.)
    best=[x['cell'] for x in exhaustive if maxd>0 and x['D']==maxd]
    useful=[x['cell'] for x in exhaustive if x['D']>common_cost]
    reference_scan=maxd>common_cost;out={}
    for name,(result,audit) in arms.items():
        selected=_selected(result,audit)
        chosen=[e_by[c] for c in selected if c in e_by]
        selected_d=max((x['D'] for x in chosen),default=0.)
        actual=result['net_value']>0
        out[name]={'selected':selected,'selected_D':selected_d,
            'selected_best_D_regret':max(0.,maxd-selected_d),
            'selected_useful_count':sum(x['D']>common_cost for x in chosen),
            'useful_recall':(sum(c in useful for c in selected)/len(useful) if useful else None),
            'max_D_recall':(sum(c in selected for c in best)/len(best) if best else None),
            'common_scan':selected_d>common_cost,
            'common_scan_agreement':(selected_d>common_cost)==reference_scan,
            'actual_authorized':actual,
            'actual_false_positive':actual and not reference_scan,
            'actual_false_negative':(not actual) and reference_scan,
            'plan_calls':int(result['plan_calls']),'charged_cost':float(result['cost']),
            'V':float(result['value']),'D':float(result['delay_regret']),
            'best_cell':result['cell'],'selected_count':len(selected),
            'scheduler_ns':int(result.get('scheduler_ns',0)),
            'graph_analysis_ns':int(result.get('graph_analysis_ns',0)),
            'graph_work_units':int(result.get('graph_work_units',0)),
            'graph_work_bound':int(result.get('graph_work_bound',0)),
            'graph_operation_counts':result.get('graph_operation_counts',{})}
    return {'fixture_id':f['fixture_id'],'family':f['family'],'seed':f['seed'],
        'source':f['source'],'start':f['start'],'goal':f['goal'],'yaw':f['yaw'],
        'unknown':f['unknown'],'target_cell':f['target_cell'],
        'target_annotation':f['expected_label'],'candidate_count':len(exhaustive),
        'exhaustive_candidates':exhaustive,'common_cost':common_cost,
        'exhaustive_best_D':maxd,'exhaustive_best_cells':best,
        'useful_candidates':useful,'reference_common_scan':reference_scan,
        'arms':out}


def _aggregate(rows):
    names=('C0','C-K','C-Route3','C-Topology3-corrected');by_family={}
    for family in sorted({r['family'] for r in rows}):
        family_rows=[r for r in rows if r['family']==family]
        by_family[family]={}
        for name in names:
            nonempty=[r for r in family_rows if r['useful_candidates']]
            best_nonempty=[r for r in family_rows if r['exhaustive_best_cells']]
            tp=sum(sum(c in r['arms'][name]['selected'] for c in r['useful_candidates']) for r in family_rows)
            den=sum(len(r['useful_candidates']) for r in family_rows)
            besttp=sum(sum(c in r['arms'][name]['selected'] for c in r['exhaustive_best_cells']) for r in family_rows)
            bestden=sum(len(r['exhaustive_best_cells']) for r in family_rows)
            by_family[family][name]={
                'fixture_count':len(family_rows),'nonempty_useful_fixture_count':len(nonempty),
                'empty_useful_fixture_count':sum(not r['useful_candidates'] for r in family_rows),
                'macro_useful_recall':float(np.mean([r['arms'][name]['useful_recall'] for r in nonempty])) if nonempty else None,
                'micro_useful_recall':tp/den if den else None,
                'macro_max_D_recall':float(np.mean([r['arms'][name]['max_D_recall'] for r in best_nonempty])) if best_nonempty else None,
                'micro_max_D_recall':besttp/bestden if bestden else None,
                'common_scan_agreement':sum(r['arms'][name]['common_scan_agreement'] for r in family_rows)/len(family_rows),
                'actual_scans':sum(r['arms'][name]['actual_authorized'] for r in family_rows),
                'false_positives':sum(r['arms'][name]['actual_false_positive'] for r in family_rows),
                'false_negatives':sum(r['arms'][name]['actual_false_negative'] for r in family_rows),
                'mean_scheduler_ns':float(np.mean([r['arms'][name]['scheduler_ns'] for r in family_rows]))}
    overall={}
    for name in names:
        nonempty=[r for r in rows if r['useful_candidates']]
        best_nonempty=[r for r in rows if r['exhaustive_best_cells']]
        tp=sum(sum(c in r['arms'][name]['selected'] for c in r['useful_candidates']) for r in rows)
        den=sum(len(r['useful_candidates']) for r in rows)
        besttp=sum(sum(c in r['arms'][name]['selected'] for c in r['exhaustive_best_cells']) for r in rows)
        bestden=sum(len(r['exhaustive_best_cells']) for r in rows)
        overall[name]={'fixture_count':len(rows),'nonempty_useful_fixture_count':len(nonempty),
            'empty_useful_fixture_count':sum(not r['useful_candidates'] for r in rows),
            'macro_useful_recall':float(np.mean([r['arms'][name]['useful_recall'] for r in nonempty])) if nonempty else None,
            'micro_useful_recall':tp/den if den else None,
            'macro_max_D_recall':float(np.mean([r['arms'][name]['max_D_recall'] for r in best_nonempty])) if best_nonempty else None,
            'micro_max_D_recall':besttp/bestden if bestden else None,
            'common_scan_agreement':sum(r['arms'][name]['common_scan_agreement'] for r in rows)/len(rows),
            'common_scan_correct':sum(r['arms'][name]['common_scan_agreement'] for r in rows),
            'actual_scans':sum(r['arms'][name]['actual_authorized'] for r in rows),
            'false_positives':sum(r['arms'][name]['actual_false_positive'] for r in rows),
            'false_negatives':sum(r['arms'][name]['actual_false_negative'] for r in rows),
            'mean_scheduler_ns':float(np.mean([r['arms'][name]['scheduler_ns'] for r in rows]))}
    return {'overall':overall,'by_family':by_family}


def run():
    if OUT.exists():raise FileExistsError(f'Refusing to overwrite {OUT}')
    test_command=[sys.executable,'-m','pytest','-q',
        'tests/test_topology_evi_c_correctness.py','tests/test_c_v2c_fixture_annotations.py']
    test_run=subprocess.run(test_command,cwd=ROOT,text=True,capture_output=True)
    correctness={'command':test_command,'returncode':test_run.returncode,
        'stdout':test_run.stdout,'stderr':test_run.stderr,
        'status':'PASS' if test_run.returncode==0 else 'FAIL'}
    if test_run.returncode:
        OUT.mkdir(parents=True,exist_ok=False)
        (OUT/'correctness_failure.json').write_text(json.dumps(correctness,indent=2,sort_keys=True)+'\n')
        raise RuntimeError('Correctness test gate failed; candidate arms were not executed')
    fixtures=build_formal_fixtures()
    annotations=validate_annotations()
    if annotations['status']!='PASS':raise RuntimeError('Fixture annotations invalid; refusing candidate screen')
    preflight=[];prepared=[]
    # Exhaustive independent reference completes before any candidate arm runs.
    for f in fixtures:
        ex,cost,calls,route,candidates=independent_exhaustive_evi(
            f['grid'],f['probability'],f['start'],f['goal'],f['yaw'],f['unknown'])
        record={'fixture_id':f['fixture_id'],'candidate_count':len(candidates),
            'exhaustive_plan_calls':calls,'target_cell':f['target_cell'],
            'target_in_visible_candidates':tuple(f['target_cell']) in candidates}
        if f['annotation'].get('target_expected_high_EVI'):
            best=max((x['D'] for x in ex),default=0.)
            record['target_is_max_D']=any(x['cell']==tuple(f['target_cell']) and x['D']==best for x in ex)
        preflight.append(record);prepared.append((f,ex,cost,calls,route,candidates))
    failed=[x for x in preflight if not x['target_in_visible_candidates'] or x.get('target_is_max_D') is False]
    if failed:
        OUT.mkdir(parents=True,exist_ok=False)
        (OUT/'prepolicy_reference_preflight.json').write_text(json.dumps({'status':'INVALID_PREFLIGHT_STOP','failed':failed,'candidate_arms_executed':False,'annotation_validation':annotations},indent=2,sort_keys=True)+'\n')
        raise RuntimeError('Independent EVI fixture preflight failed before candidate arms; archived and stopped')

    rows=[];graph_benchmarks=[]
    for f,ex,cost,calls,route,candidates in prepared:
        g=f['grid'];p=f['probability'];start=f['start'];goal=f['goal'];yaw=f['yaw'];unknown=f['unknown']
        funcs={
            'C0':lambda:information_value(g,p,start,goal,yaw,unknown,SENSOR,REMAINING,EVIParameters(max_candidates=3)),
            'C-K':lambda:information_value_uncertainty_k(g,p,start,goal,yaw,unknown,SENSOR,REMAINING,ExpandedEVIParameters(max_candidates=5)),
            'C-Route3':lambda:information_value_route(g,p,start,goal,yaw,unknown,SENSOR,REMAINING,ExpandedEVIParameters(max_candidates=3)),
            'C-Topology3-corrected':lambda:information_value_topology_c(g,p,start,goal,yaw,unknown,SENSOR,REMAINING,EVIParameters(max_candidates=3))}
        arms={};
        for name,fn in funcs.items():
            began=perf_counter_ns();result=fn();elapsed=perf_counter_ns()-began
            if name=='C0':
                audit=information_value_original_audit(g,p,start,goal,yaw,unknown,SENSOR,REMAINING,EVIParameters(max_candidates=3))
                if any(result[k]!=audit[k] for k in ('value','delay_regret','cell','cost','net_value','plan_calls')):
                    raise RuntimeError(f'C0 parity failed at {f["fixture_id"]}')
                audit_list=audit['shortlisted_candidates']
            else:audit_list=None
            if name=='C0':result={'result':result,'shortlisted_candidates':audit_list,**result}
            result['scheduler_ns']=elapsed
            arms[name]=(result,audit_list)
        rows.append(_evaluate_one(f,ex,cost,arms))
        # Runtime protocol: 10 warm-ups, followed by 100 measured graph+rank calls.
        if f['fixture_id']==fixtures[0]['fixture_id']:
            pass
        footprint=visible_cells(g,start,yaw,**SENSOR)
        eligible=[c for c in footprint if c!=start and .05<float(p[c[1],c[0]])<.95]
        samples=[]
        for j in range(110):
            t0=perf_counter_ns();analysis=analyze_public_topology_c(g,start,goal,unknown)
            rank_topology_candidates_c(g,p,eligible,analysis,start,goal,route)
            dt=perf_counter_ns()-t0
            if j>=10:samples.append(dt)
        graph_benchmarks.append({'fixture_id':f['fixture_id'],'warmup_calls':10,
            'measured_calls':100,'p95_ns':int(np.percentile(samples,95)),
            'samples_ns':samples})

    aggregates=_aggregate(rows)
    topo=aggregates['overall']['C-Topology3-corrected'];c0=aggregates['overall']['C0']
    topo_macro_max=topo['macro_max_D_recall'];c0_macro_max=c0['macro_max_D_recall']
    useful_gain=topo['macro_useful_recall']-c0['macro_useful_recall']
    scan_gain=topo['common_scan_agreement']-c0['common_scan_agreement']
    no_benefit_ids=[f['fixture_id'] for f in fixtures if f['annotation'].get('expected_no_scan') or f['expected_label']=='nontraversable_no_route_benefit']
    no_benefit_scans=[{'fixture_id':r['fixture_id'],'arms':{k:v['actual_authorized'] for k,v in r['arms'].items()}} for r in rows if r['fixture_id'] in no_benefit_ids and r['arms']['C-Topology3-corrected']['actual_authorized']]
    plan_caps=all(r['arms'][a]['plan_calls']<=(11 if a=='C-K' else 7) for r in rows for a in r['arms'])
    work_bounds=all(r['arms']['C-Topology3-corrected']['graph_work_units']<=r['arms']['C-Topology3-corrected']['graph_work_bound'] for r in rows)
    graph_p95=int(np.percentile([t for b in graph_benchmarks for t in b['samples_ns']],95))
    numeric={'macro_useful_recall_gain':useful_gain,'macro_useful_recall_gain_ge_0_10':useful_gain>=.10,
        'micro_useful_recall_non_decrease':topo['micro_useful_recall']>=c0['micro_useful_recall'],
        'macro_max_D_recall_non_decrease':topo_macro_max>=c0_macro_max,
        'normalized_common_scan_agreement_gain':scan_gain,
        'scan_agreement_gain_ge_0_05':scan_gain>=.05,
        'no_benefit_false_authorizations':no_benefit_scans,
        'no_benefit_cases_pass':not no_benefit_scans,
        'all_A_star_limits_respected':plan_caps,
        'graph_work_bound_respected':work_bounds,
        'graph_analysis_p95_ms':graph_p95/1e6,
        'graph_analysis_p95_le_5ms':graph_p95<=5_000_000}
    numeric['status']='PASS' if all((numeric['macro_useful_recall_gain_ge_0_10'],numeric['micro_useful_recall_non_decrease'],numeric['macro_max_D_recall_non_decrease'],numeric['scan_agreement_gain_ge_0_05'],numeric['no_benefit_cases_pass'],plan_caps,work_bounds,graph_p95<=5_000_000)) else 'REJECTED'
    # Numeric status is intentionally separate from the post-run review file.
    source_paths=['docs/phase2_c_v2c_topology_protocol.md','docs/phase2_c_v2c_topology_protocol_v2.md','docs/phase2_c_v2c_fit_intervention_protocol.md','scripts/c_v2c_fixtures.py','scripts/validate_c_v2c_fixture_annotations.py','scripts/run_c_v2c_topology_fixtures.py','scripts/review_c_v2c_mechanism.py','src/spatial_memory/topology_evi_c.py','src/spatial_memory/topology_reference.py','src/spatial_memory/evi.py','src/spatial_memory/candidate_coverage.py']
    data={'status':'COMPLETED_C_V2C_SYNTHETIC_SCREEN','protocol':'docs/phase2_c_v2c_topology_protocol.md','mechanism_gate':numeric,
        'correctness_validation':correctness,
        'annotation_validation':annotations,'policy_preflight':preflight,
        'FIT_data_accessed':False,'admitted_worlds_loaded':False,'protected_generator_called':False,
        'source_sha256':{x:hashlib.sha256((ROOT/x).read_bytes()).hexdigest() for x in source_paths},
        'environment':{'python':sys.version,'platform':platform.platform(),'machine':platform.machine(),'processor':platform.processor(),'pid':os.getpid()},
        'fixture_count':len(fixtures),'family_counts':{n:sum(f['family']==n for f in fixtures) for n in sorted({f['family'] for f in fixtures})},
        'policies':['C0','C-K','C-Route3','C-Topology3-corrected'],
        'remaining_budget':REMAINING,'sensor':SENSOR,'aggregates':aggregates,
        'graph_benchmarks':graph_benchmarks,'fixtures':rows}
    OUT.mkdir(parents=True,exist_ok=False)
    out=OUT/'synthetic_mechanism_results.json'
    out.write_text(json.dumps(data,indent=2,sort_keys=True,default=lambda x:list(x) if isinstance(x,tuple) else x)+'\n')
    print(json.dumps({'status':numeric['status'],'gate':numeric,'output':str(out),'fixtures':len(rows)},indent=2))


if __name__=='__main__':run()
