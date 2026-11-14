"""Run the frozen C v2.0d 80-case synthetic mechanism/resource screen."""
from __future__ import annotations
import hashlib,json,os,platform,subprocess,sys
from pathlib import Path
from time import perf_counter_ns
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from c_v2d_fixtures import FAMILIES,build_formal_fixtures,population_sha256
from validate_c_v2d_fixture_annotations import validate as validate_annotations,SENSOR
from spatial_memory.evi import EVIParameters,information_value,visible_cells
from spatial_memory.navigation import plan
from spatial_memory.candidate_coverage import (
    ExpandedEVIParameters,information_value_original_audit,
    information_value_uncertainty_k,information_value_route)
from spatial_memory.topology_evi_c import (
    analyze_public_topology_c,information_value_topology_c)
from spatial_memory.topology_evi_d import (
    information_value_topology_d,rank_topology_candidates_d)

OUT=ROOT/'results/phase2_mujoco/c_v2d_topology_v1'
REMAINING=20
ARMS=('C0','C-K','C-Route3','C-Topology3-d')
SOURCE_PATHS=['docs/phase2_c_v2d_topology_protocol.md',
      'docs/c_v2d_computational_complexity.md',
      'docs/phase2_c_v2d_fit_intervention_protocol.md','scripts/c_v2d_fixtures.py',
      'scripts/validate_c_v2d_fixture_annotations.py','scripts/run_c_v2d_topology_fixtures.py',
      'scripts/review_c_v2d_mechanism.py','src/spatial_memory/topology_evi_d.py',
      'src/spatial_memory/topology_review_d.py','src/spatial_memory/topology_evi_c.py',
      'src/spatial_memory/topology_reference.py','src/spatial_memory/evi.py',
      'src/spatial_memory/candidate_coverage.py','src/spatial_memory/navigation.py',
      'tests/test_topology_evi_c_correctness.py','tests/test_topology_evi_d_equivalence.py',
      'tests/test_topology_evi_d_v2c_regression.py','tests/test_topology_review_d.py',
      'tests/test_c_v2c_fixture_annotations.py']


def independent_exhaustive_evi(grid,probability,start,goal,yaw,unknown):
    """Independent single-cell value reference; only frozen A* is shared."""
    nominal=plan(grid,start,goal,unknown)
    footprint=visible_cells(grid,start,yaw,**SENSOR)
    candidates=[c for c in footprint if c!=tuple(start)
                and .05<float(probability[c[1],c[0]])<.95]
    rows=[];calls=1
    for cell in sorted(candidates,key=lambda c:(c[1],c[0])):
        routes=[]
        for outcome in (0,1):
            changed=grid.copy();changed[cell[1],cell[0]]=outcome
            routes.append(plan(changed,start,goal,unknown));calls+=1
        q=float(probability[cell[1],cell[0]])
        loss_table=[]
        for route in routes:
            loss_table.append([80. if not route else float(len(route)-1+(80 if occupied and cell in route else 0))
                               for occupied in (0,1)])
        before=min((1-q)*pair[0]+q*pair[1] for pair in loss_table)
        after=(1-q)*min(pair[0] for pair in loss_table)+q*min(pair[1] for pair in loss_table)
        value=max(0.,before-after)
        first=[tuple(r[1]) if len(r)>1 else None for r in routes]
        delay=value*min(q,1-q) if first[0]!=first[1] else 0.
        rows.append({'cell':cell,'V':value,'D':delay,'q':q,
                     'free_first_action':first[0],'occupied_first_action':first[1]})
    cost=.5+.01*7+.5/max(1,REMAINING)
    return rows,cost,calls,nominal,candidates


def run_arms(grid,p,start,goal,yaw,unknown):
    args=(grid,p,start,goal,yaw,unknown,SENSOR,REMAINING)
    params=EVIParameters(max_candidates=3)
    c0=information_value(grid,p,start,goal,yaw,unknown,SENSOR,REMAINING,params)
    c0audit=information_value_original_audit(*args,params)
    if any(c0[k]!=c0audit[k] for k in ('value','delay_regret','cell','cost','net_value','plan_calls')):
        raise RuntimeError('C0 parity check failed')
    return {
      'C0':(c0,c0audit['shortlisted_candidates']),
      'C-K':(information_value_uncertainty_k(*args,ExpandedEVIParameters(max_candidates=5)),None),
      'C-Route3':(information_value_route(*args,ExpandedEVIParameters(max_candidates=3)),None),
      'C-Topology3-d':(information_value_topology_d(*args,params),None),
    }


def _selected(result,audit):
    rows=audit if audit is not None else result.get('shortlisted_candidates',[])
    return [tuple(x['cell']) for x in rows]


def evaluate_one(f,exhaustive,common_cost,arms):
    exact={x['cell']:x for x in exhaustive}
    maxd=max((x['D'] for x in exhaustive),default=0.)
    max_cells=[x['cell'] for x in exhaustive if maxd>0 and x['D']==maxd]
    useful=[x['cell'] for x in exhaustive if x['D']>common_cost]
    reference_scan=maxd>common_cost;out={}
    for name,(result,audit) in arms.items():
        selected=_selected(result,audit);scored=[exact[c] for c in selected if c in exact]
        selected_d=max((x['D'] for x in scored),default=0.)
        actual=bool(result['net_value']>0)
        out[name]={'selected':selected,'selected_D':selected_d,
          'selected_best_D_regret':max(0.,maxd-selected_d),
          'useful_recall':(sum(c in useful for c in selected)/len(useful) if useful else None),
          'max_D_recall':(sum(c in selected for c in max_cells)/len(max_cells) if max_cells else None),
          'common_scan':selected_d>common_cost,
          'common_scan_agreement':(selected_d>common_cost)==reference_scan,
          'actual_authorized':actual,
          'actual_false_positive':actual and not reference_scan,
          'actual_false_negative':not actual and reference_scan,
          'plan_calls':int(result['plan_calls']),'charged_cost':float(result['cost']),
          'V':float(result['value']),'D':float(result['delay_regret']),
          'best_cell':result['cell'],'selected_count':len(selected),
          'scheduler_ns':int(result.get('scheduler_ns',0)),
          'graph_analysis_ns':int(result.get('graph_analysis_ns',0)),
          'graph_vertices':result.get('graph_vertices'),'graph_edges':result.get('graph_edges'),
          'graph_components':result.get('graph_components'),
          'graph_bridges':result.get('graph_bridges'),
          'graph_articulations':result.get('graph_articulations'),
          'candidate_count':result.get('candidate_count'),
          'route_length_l':result.get('route_length_l'),
          'candidate_limit_k':result.get('candidate_limit_k',3),
          'selection_counters':result.get('selection_counters'),
          'graph_operation_counts':result.get('graph_operation_counts'),
          'stage_accounting':result.get('stage_accounting')}
    return {'fixture_id':f['fixture_id'],'family':f['family'],'seed':f['seed'],
      'shape':list(f['grid'].shape),'density_class':f['density_class'],
      'start':f['start'],'goal':f['goal'],'yaw':f['yaw'],'unknown':f['unknown'],
      'target_cell':f['target_cell'],'target_annotation':f['expected_label'],
      'candidate_count':len(exhaustive),'exhaustive_candidates':exhaustive,
      'common_cost':common_cost,'exhaustive_best_D':maxd,
      'exhaustive_best_cells':max_cells,'useful_candidates':useful,
      'reference_common_scan':reference_scan,'arms':out}


def aggregate(rows):
    by_family={}
    for family in sorted({r['family'] for r in rows}):
        group=[r for r in rows if r['family']==family];by_family[family]={}
        for arm in ARMS:by_family[family][arm]=_aggregate_group(group,arm)
    overall={arm:_aggregate_group(rows,arm) for arm in ARMS}
    return {'overall':overall,'by_family':by_family}


def _aggregate_group(rows,arm):
    nonempty=[r for r in rows if r['useful_candidates']]
    bestrows=[r for r in rows if r['exhaustive_best_cells']]
    tp=sum(sum(c in r['arms'][arm]['selected'] for c in r['useful_candidates']) for r in rows)
    den=sum(len(r['useful_candidates']) for r in rows)
    besttp=sum(sum(c in r['arms'][arm]['selected'] for c in r['exhaustive_best_cells']) for r in rows)
    bestden=sum(len(r['exhaustive_best_cells']) for r in rows)
    return {'fixture_count':len(rows),'nonempty_useful_fixture_count':len(nonempty),
      'empty_useful_fixture_count':sum(not r['useful_candidates'] for r in rows),
      'useful_candidate_denominator':den,'max_D_candidate_denominator':bestden,
      'macro_useful_recall':float(np.mean([r['arms'][arm]['useful_recall'] for r in nonempty])) if nonempty else None,
      'micro_useful_recall':tp/den if den else None,
      'macro_max_D_recall':float(np.mean([r['arms'][arm]['max_D_recall'] for r in bestrows])) if bestrows else None,
      'micro_max_D_recall':besttp/bestden if bestden else None,
      'mean_best_D_regret':float(np.mean([r['arms'][arm]['selected_best_D_regret'] for r in rows])),
      'common_scan_correct':sum(bool(r['arms'][arm]['common_scan_agreement']) for r in rows),
      'common_scan_denominator':len(rows),
      'actual_scans':sum(bool(r['arms'][arm]['actual_authorized']) for r in rows),
      'false_positives':sum(bool(r['arms'][arm]['actual_false_positive']) for r in rows),
      'false_negatives':sum(bool(r['arms'][arm]['actual_false_negative']) for r in rows),
      'mean_scheduler_ns':float(np.mean([r['arms'][arm]['scheduler_ns'] for r in rows])),
      'mean_graph_analysis_ns':float(np.mean([r['arms'][arm]['graph_analysis_ns'] or 0 for r in rows]))}


def _stage_benchmark(grid,p,candidates,position,goal,unknown,route):
    graph=analyze_public_topology_c(grid,position,goal,unknown)
    return rank_topology_candidates_d(grid,p,candidates,graph,position,goal,route,3)


def _runtime_benchmarks(fixtures):
    ref=[]
    for f in fixtures:
        if f['grid'].shape!=(17,17):continue
        p=f['probability'];grid=f['grid'];start=f['start'];goal=f['goal'];yaw=f['yaw'];mode=f['unknown']
        route=plan(grid,start,goal,mode) or []
        footprint=visible_cells(grid,start,yaw,**SENSOR)
        candidates=[c for c in footprint if c!=start and .05<float(p[c[1],c[0]])<.95]
        samples=[]
        for i in range(110):
            t0=perf_counter_ns();_stage_benchmark(grid,p,candidates,start,goal,mode,route);elapsed=perf_counter_ns()-t0
            if i>=10:samples.append(elapsed)
        ref.append({'fixture_id':f['fixture_id'],'N':grid.size,'warmup_calls':10,
            'shape':list(grid.shape),'measured_calls':100,'samples_ns':samples,
            'p95_ns':int(np.percentile(samples,95))})
    scaling=[]
    for size in (17,33,65,128):
        for density in ('dense','sparse_disconnected'):
            grid=np.zeros((size,size),dtype=np.int8) if density=='dense' else np.ones((size,size),dtype=np.int8)
            if density=='sparse_disconnected':grid[1:-1:4,1:-1:4]=0
            p=np.full(grid.shape,.5);position=(size//2,size//2);goal=(size-2,size-2)
            route=plan(grid,position,goal,'optimistic') or []
            cells=[(x,y) for y in range(size) for x in range(size)]
            samples=[];warmup=3;measured=7
            for i in range(warmup+measured):
                began=perf_counter_ns();graph=analyze_public_topology_c(grid,position,goal,'optimistic')
                rank_topology_candidates_d(grid,p,cells,graph,position,goal,route,3)
                if i>=warmup:samples.append(perf_counter_ns()-began)
            scaling.append({'size':[size,size],'N':size*size,'density_case':density,
              'V':graph['vertices'],'E':graph['edges'],'M':len(cells),
              'warmup_calls':warmup,'measured_calls':measured,
              'samples_ns':samples,'median_ns':int(np.median(samples)),
              'p95_ns':int(np.percentile(samples,95)),'max_ns':max(samples)})
    ref_samples=[t for row in ref for t in row['samples_ns']]
    p95=int(np.percentile(ref_samples,95)) if ref_samples else None
    return {'reference_scale_17x17':ref,'reference_scale_aggregate_p95_ns':p95,
      'reference_scale_p95_le_5ms':p95 is not None and p95<=5_000_000,
      'large_map_scaling_no_latency_threshold':scaling}


def run():
    binding_path=OUT/'protocol_binding.json'
    if not binding_path.is_file():raise RuntimeError('Frozen protocol binding missing; refusing formal execution')
    binding=json.loads(binding_path.read_text())
    current={x:hashlib.sha256((ROOT/x).read_bytes()).hexdigest() for x in SOURCE_PATHS}
    if current!=binding.get('source_sha256'):
        raise RuntimeError('Frozen source fingerprints changed; refusing formal execution')
    fixtures=build_formal_fixtures()
    population_digest=population_sha256(fixtures)
    if population_digest!=binding.get('fixture_population_sha256'):
        raise RuntimeError('Frozen fixture population changed; refusing formal execution')
    if OUT.exists():
        unexpected=[p.name for p in OUT.iterdir() if p.name!='protocol_binding.json']
        if unexpected:raise FileExistsError(f'Refusing to overwrite non-binding artifacts in {OUT}: {unexpected}')
    else:OUT.mkdir(parents=True,exist_ok=False)
    correctness_cmd=[sys.executable,'-m','pytest','-q',
      'tests/test_topology_evi_c_correctness.py','tests/test_topology_evi_d_equivalence.py',
      'tests/test_topology_evi_d_v2c_regression.py','tests/test_c_v2c_fixture_annotations.py',
      'tests/test_topology_review_d.py']
    tested=subprocess.run(correctness_cmd,cwd=ROOT,text=True,capture_output=True)
    correctness={'command':correctness_cmd,'returncode':tested.returncode,
      'stdout':tested.stdout,'stderr':tested.stderr,
      'status':'PASS' if tested.returncode==0 else 'FAIL'}
    if tested.returncode:
        (OUT/'correctness_failure.json').write_text(json.dumps(correctness,indent=2)+'\n')
        raise RuntimeError('Correctness gate failed before candidate arms')
    annotation=validate_annotations()
    if annotation['status']!='PASS':
        (OUT/'annotation_failure.json').write_text(json.dumps(annotation,indent=2,sort_keys=True)+'\n')
        raise RuntimeError('Independent annotation check failed before candidate arms')

    preflight=[];prepared=[]
    for f in fixtures:
        exhaustive,cost,calls,nominal,candidates=independent_exhaustive_evi(
            f['grid'],f['probability'],f['start'],f['goal'],f['yaw'],f['unknown'])
        useful=[x for x in exhaustive if x['D']>cost]
        row={'fixture_id':f['fixture_id'],'M':len(candidates),
             'exhaustive_plan_calls':calls,'useful_candidate_count':len(useful),
             'empty_useful_set':not useful,'common_cost':cost}
        preflight.append(row);prepared.append((f,exhaustive,cost,calls,nominal,candidates))
    no_benefit=[x for x in preflight if x['fixture_id'].startswith('no_benefit_topology_control_')]
    if len(no_benefit)!=10 or any(not x['empty_useful_set'] for x in no_benefit):
        (OUT/'reference_preflight_failure.json').write_text(json.dumps({'status':'INVALID_STOP_BEFORE_ARMS','preflight':preflight,'candidate_arms_executed':False},indent=2,sort_keys=True)+'\n')
        raise RuntimeError('Designated no-benefit fixture family has useful candidates; candidate arms were not run')

    rows=[];stage_counters=[]
    for f,ex,cost,_calls,_nominal,_candidates in prepared:
        arms=run_arms(f['grid'],f['probability'],f['start'],f['goal'],f['yaw'],f['unknown'])
        row=evaluate_one(f,ex,cost,arms);rows.append(row)
        d=arms['C-Topology3-d'][0]
        stage_counters.append({'fixture_id':f['fixture_id'],
          'N':int(f['grid'].size),'V':d['graph_vertices'],'E':d['graph_edges'],
          'M':d['candidate_count'],'L':d['route_length_l'],'K':3,
          'stage_accounting':d['stage_accounting']})

    aggregates=aggregate(rows);numeric_arms=aggregates['overall'];d=numeric_arms['C-Topology3-d'];c0=numeric_arms['C0']
    graph_bounds_pass=all(x['stage_accounting']['passes'] for x in stage_counters)
    astar_pass=all(r['arms'][a]['plan_calls']<=(11 if a=='C-K' else 7) for r in rows for a in ARMS)
    topk_pass=all(r['arms']['C-Topology3-d']['selection_counters']['total_key_comparisons']<=
                  r['arms']['C-Topology3-d']['selection_counters']['theoretical_heap_comparison_bound'] for r in rows)
    no_benefit_ids={x['fixture_id'] for x in no_benefit}
    no_benefit_scans=[r['fixture_id'] for r in rows if r['fixture_id'] in no_benefit_ids and r['arms']['C-Topology3-d']['actual_authorized']]
    false_positive_nonincrease=(d['false_positives']<=c0['false_positives'])
    runtime=_runtime_benchmarks(fixtures)
    macro_gain=d['macro_useful_recall']-c0['macro_useful_recall']
    scan_gain=(d['common_scan_correct']-c0['common_scan_correct'])/len(rows)
    numeric={'macro_useful_recall_gain':macro_gain,'macro_useful_recall_gain_ge_0_10':macro_gain>=.10,
      'micro_useful_recall_non_decrease':d['micro_useful_recall']>=c0['micro_useful_recall'],
      'macro_max_D_recall_non_decrease':d['macro_max_D_recall']>=c0['macro_max_D_recall'],
      'common_scan_agreement_gain':scan_gain,'scan_agreement_gain_ge_0_05':scan_gain>=.05,
      'false_positive_nonincrease_vs_C0':false_positive_nonincrease,
      'no_benefit_false_authorizations':no_benefit_scans,'no_benefit_cases_pass':not no_benefit_scans,
      'all_A_star_limits_respected':astar_pass,'all_topK_comparison_bounds_respected':topk_pass,
      'all_stage_accounting_bounds_respected':graph_bounds_pass,
      'reference_scale_graph_p95_ns':runtime['reference_scale_aggregate_p95_ns'],
      'reference_scale_graph_p95_le_5ms':runtime['reference_scale_p95_le_5ms']}
    numeric['status']='PASS' if all((numeric['macro_useful_recall_gain_ge_0_10'],
      numeric['micro_useful_recall_non_decrease'],numeric['macro_max_D_recall_non_decrease'],
      numeric['scan_agreement_gain_ge_0_05'],numeric['false_positive_nonincrease_vs_C0'],
      numeric['no_benefit_cases_pass'],astar_pass,
      topk_pass,graph_bounds_pass,runtime['reference_scale_p95_le_5ms'])) else 'REJECTED'
    result={'status':'COMPLETED_C_V2D_FORMAL_SYNTHETIC_SCREEN',
      'numeric_gate':numeric,'correctness_validation':correctness,
      'annotation_validation':annotation,'prepolicy_reference_preflight':preflight,
      'FIT_data_accessed':False,'admitted_worlds_loaded':False,
      'protected_generator_called':False,'reserved_population_accessed':False,
      'protocol':'docs/phase2_c_v2d_topology_protocol.md','source_sha256':current,
      'fixture_population_sha256':population_digest,
      'seed_namespace':2026111600,
      'environment':{'python':sys.version,'platform':platform.platform(),
        'machine':platform.machine(),'processor':platform.processor(),'pid':os.getpid()},
      'fixture_count':len(fixtures),'family_counts':annotation['family_counts'],
      'seed_namespace':2026111600,'policies':list(ARMS),'K_topology':3,
      'A_star_ceiling_topology':7,'aggregates':aggregates,
      'stage_operation_counters':stage_counters,'runtime_benchmarks':runtime,
      'fixtures':rows}
    dest=OUT/'synthetic_mechanism_results.json'
    dest.write_text(json.dumps(result,indent=2,sort_keys=True,
      default=lambda x:list(x) if isinstance(x,tuple) else x)+'\n')
    manifest=[{'path':name,'bytes':(OUT/name).stat().st_size,
      'sha256':hashlib.sha256((OUT/name).read_bytes()).hexdigest()}
      for name in ('protocol_binding.json','synthetic_mechanism_results.json')]
    (OUT/'artifact_manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':numeric['status'],'numeric_gate':numeric,
      'output':str(dest),'fixtures':len(rows),'candidate_arms_executed':True},indent=2))


if __name__=='__main__':run()
