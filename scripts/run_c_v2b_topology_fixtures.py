"""Frozen C v2.0b mechanism screen; synthetic public grids only."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
from time import perf_counter_ns

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from spatial_memory.evi import EVIParameters, information_value, visible_cells
from spatial_memory.navigation import plan
from spatial_memory.candidate_coverage import (
    ExpandedEVIParameters, information_value_original_audit,
    information_value_uncertainty_k, information_value_route,
)
from spatial_memory.topology_evi import (
    TopologyEVIParameters, analyze_public_topology, rank_topology_candidates,
    information_value_topology, exhaustive_public_values,
)

OUT = ROOT/'results/phase2_mujoco/c_v2b_topology_v1'
SENSOR = {'range_m': 6., 'cell_size': .75, 'horizontal_fov_deg': 120., 'ray_count': 61}
REMAINING = 10


def _blank():
    g = np.zeros((15, 15), dtype=np.int8)
    g[[0, -1], :] = 1; g[:, [0, -1]] = 1
    p = np.full(g.shape, .01, dtype=float)
    return g, p


def fixtures():
    # 1. A single uncertain passage cell separates the current cell and goal.
    g, p = _blank(); g[1:14, 7] = 1; g[7, 7] = -1; p[7, 7] = .5
    for c in ((3, 7), (4, 7), (5, 7)): g[c[1], c[0]] = -1; p[c[1], c[0]] = .5
    yield {'name':'unique_start_goal_articulation','grid':g,'p':p,'start':(2,7),'goal':(12,7),
           'annotated_cell':(7,7),'expected_label':'start_goal_separator'}

    # 2. An articulation inside a dead-end side spur, irrelevant to s->t.
    g = np.ones((15,15),dtype=np.int8); p=np.full(g.shape,.01)
    g[7,1:14]=0; g[6,4]=g[5,4]=g[5,3]=g[5,5]=-1
    p[5,4]=p[6,4]=p[5,3]=p[5,5]=.5
    yield {'name':'irrelevant_dead_end_articulation','grid':g,'p':p,'start':(2,7),'goal':(12,7),
           'annotated_cell':(4,5),'expected_label':'irrelevant_articulation'}

    # 3. Main corridor plus a loop alternative around the uncertain center.
    g, p = _blank(); g[6,2:13] = 1; g[8,2:13] = 1
    g[6,4] = g[6,10] = 0; g[7,4:11] = -1; g[7,7] = -1
    g[5,4:11] = -1; g[4,4:11] = -1; g[4,4] = g[4,10] = -1
    for x in range(4,11): p[7,x] = .5; p[4,x] = .5
    yield {'name':'narrow_corridor_with_alternative_loop','grid':g,'p':p,'start':(2,7),'goal':(12,7),
           'annotated_cell':(7,7),'expected_label':'route_cell_with_alternative_cycle'}

    # 4. Two serial uncertain doors; each is a start-goal separator.
    g, p = _blank()
    for x in (5,9): g[1:14,x] = 1; g[7,x] = -1; p[7,x] = .5
    yield {'name':'multiple_serial_bottlenecks','grid':g,'p':p,'start':(2,7),'goal':(12,7),
           'annotated_cell':(5,7),'expected_label':'start_goal_separator'}

    # 5. Loop-rich open public map with no articulation points.
    g, p = _blank()
    for c in ((4,7),(5,7),(6,7),(7,7),(8,7),(9,7),(10,7)):
        g[c[1],c[0]] = -1; p[c[1],c[0]] = .5
    yield {'name':'loop_rich_no_articulation','grid':g,'p':p,'start':(2,7),'goal':(12,7),
           'annotated_cell':(7,7),'expected_label':'route_cell_with_alternative_cycle'}

    # 6. Remembered occupied cell blocks the direct corridor; a public detour
    # exists, and clearing it creates a shorter route.
    g, p = _blank(); g[6,2:13] = 1; g[8,2:13] = 1
    g[7,7] = 1; p[7,7] = .5
    g[6,4] = g[6,10] = -1
    yield {'name':'occupied_cell_clearing_shortcut','grid':g,'p':p,'start':(2,7),'goal':(12,7),
           'annotated_cell':(7,7),'expected_label':'occupied_distance_shortcut'}

    # 7. The unique separator is fourth under C0 coordinate tie-breaking.
    g, p = _blank(); g[1:14,7] = 1; g[7,7] = -1; p[7,7] = .5
    for x in (3,4,5): g[7,x] = -1; p[7,x] = .5
    yield {'name':'critical_cell_outside_C0_top3','grid':g,'p':p,'start':(2,7),'goal':(12,7),
           'annotated_cell':(7,7),'expected_label':'start_goal_separator'}

    # 8. Correlated probabilities across two adjacent uncertain bottleneck cells.
    g, p = _blank(); g[1:14,5]=1; g[1:14,10]=1
    for x in (5,6,7,8,9,10): g[7,x]=-1; p[7,x]=.5
    yield {'name':'multiple_correlated_uncertain_cells','grid':g,'p':p,'start':(2,7),'goal':(12,7),
           'annotated_cell':(7,7),'expected_label':'start_goal_separator'}

    # 9. An uncertain off-route cell in an open loop-rich area; no value.
    g, p = _blank(); g[5,4] = -1; p[5,4] = .5
    yield {'name':'no_beneficial_scan','grid':g,'p':p,'start':(2,7),'goal':(12,7),
           'annotated_cell':(4,5),'expected_label':'other_traversable'}

    # 10a/10b. Same map, different terminal pair; topology relevance changes.
    g, p = _blank(); g[1:14,7] = 1
    g[4,7] = g[10,7] = -1; p[4,7] = p[10,7] = .5
    for name, start, goal, cell in (
        ('same_graph_pair_upper','2,4','12,4',(7,4)),
        ('same_graph_pair_lower','2,10','12,10',(7,10))):
        yield {'name':name,'grid':g.copy(),'p':p.copy(),
               'start':tuple(map(int,start.split(','))),
               'goal':tuple(map(int,goal.split(','))),
               'annotated_cell':cell,'expected_label':'route_cell_with_alternative_cycle'}


def _c0_value_reference(grid, p, start, goal):
    return information_value(grid, p, start, goal, 0., 'optimistic', SENSOR,
                             REMAINING, EVIParameters(max_candidates=3))


def _arms():
    return {
        'C0': lambda g,p,s,t: information_value_original_audit(g,p,s,t,0.,'optimistic',SENSOR,REMAINING,EVIParameters(max_candidates=3)),
        'C-K': lambda g,p,s,t: information_value_uncertainty_k(g,p,s,t,0.,'optimistic',SENSOR,REMAINING,ExpandedEVIParameters(max_candidates=5)),
        'C-Route3': lambda g,p,s,t: information_value_route(g,p,s,t,0.,'optimistic',SENSOR,REMAINING,ExpandedEVIParameters(max_candidates=3)),
        'C-Topology3': lambda g,p,s,t: information_value_topology(g,p,s,t,0.,'optimistic',SENSOR,REMAINING,TopologyEVIParameters()),
    }


def run():
    if OUT.exists():
        raise FileExistsError(f'Refusing to overwrite {OUT}')
    all_fixtures = list(fixtures())
    arms = _arms(); rows = []
    for f in all_fixtures:
        g,p,s,t = f['grid'],f['p'],f['start'],f['goal']
        footprint = visible_cells(g,s,0.,**SENSOR)
        eligible = [c for c in footprint if c != s and .05 < p[c[1],c[0]] < .95]
        exhaustive, common_cost, exhaustive_calls = exhaustive_public_values(
            g,p,s,t,'optimistic',eligible,remaining=REMAINING)
        exhaustive_best = max((r['D'] for r in exhaustive),default=0.)
        useful = [r for r in exhaustive if r['D'] > common_cost]
        best_cells = [r['cell'] for r in exhaustive if r['D'] == exhaustive_best and exhaustive_best > 0]
        per_arm = {}
        for name, fn in arms.items():
            started = perf_counter_ns(); result = fn(g,p,s,t)
            elapsed = perf_counter_ns()-started
            if name == 'C0':
                ref = _c0_value_reference(g,p,s,t)
                assert all(result[k] == ref[k] for k in ('value','delay_regret','cell','cost','net_value','plan_calls'))
            selected = [tuple(x['cell']) for x in result.get('shortlisted_candidates',[])]
            selected_rows = [r for r in exhaustive if r['cell'] in selected]
            max_selected_d = max((r['D'] for r in selected_rows),default=0.)
            reference_common_scan = exhaustive_best > common_cost
            per_arm[name] = {'selected':selected,'selected_D':max_selected_d,
                'selected_best_D_regret':exhaustive_best-max_selected_d,
                'selected_useful':sum(r['D'] > common_cost for r in selected_rows),
                'plan_calls':result['plan_calls'],'actual_cost':result['cost'],
                'actual_scan':result['net_value']>0,
                'common_scan':max_selected_d>common_cost,
                'exhaustive_common_scan_agreement':(max_selected_d>common_cost)==reference_common_scan,
                'best_cell':result['cell'],'D':result['delay_regret'],
                'V':result['value'],'scheduler_ns':elapsed,
                'graph_analysis_ns':result.get('graph_analysis_ns',0),
                'graph_operations':result.get('graph_operation_count',0),
                'graph_work_bound':result.get('graph_work_bound',0),
                'topology_classes':[x.get('topology_class') for x in result.get('shortlisted_candidates',[])]}
        graph = analyze_public_topology(g,s,t,'optimistic')
        annotation = _candidate_label(f['annotated_cell'],g,graph,s,t)
        rows.append({'fixture':f['name'],'start':s,'goal':t,'eligible_count':len(eligible),
            'eligible':eligible,'exhaustive_candidates':exhaustive,'exhaustive_calls':exhaustive_calls,
            'common_cost':common_cost,'exhaustive_best_D':exhaustive_best,
            'exhaustive_best_cells':best_cells,'useful_cells':[r['cell'] for r in useful],
            'annotation':{'cell':f['annotated_cell'],'expected':f['expected_label'],'observed':annotation},
            'topology':{'vertices':graph['vertices'],'edges':graph['edges'],
                'articulation_count':len(graph['articulation']),
                'separating_count':len(graph['separating']),
                'bridge_count':len(graph['bridges']),
                'relevant_bridge_count':len(graph['relevant_bridges']),
                'biconnected_block_count':len(graph['blocks'])},'arms':per_arm})

    # Repeat graph analysis to measure p95 independently from EVI/A*.
    graph_samples=[]
    for f in all_fixtures:
        samples=[]
        footprint=visible_cells(f['grid'],f['start'],0.,**SENSOR)
        candidates=[c for c in footprint if c!=f['start'] and .05<f['p'][c[1],c[0]]<.95]
        for _ in range(100):
            started=perf_counter_ns()
            g=analyze_public_topology(f['grid'],f['start'],f['goal'],'optimistic')
            rank_topology_candidates(f['grid'],f['p'],candidates,g,f['start'],f['goal'])
            samples.append(perf_counter_ns()-started)
        graph_samples.append({'fixture':f['name'],'samples_ns':samples,
            'p95_ns':int(np.percentile(samples,95))})

    recall_use=[];recall_best=[];scan_wins=0;false_positive=[]
    for row in rows:
        use=set(row['useful_cells'])
        if use:
            recall_use.append(len(use & set(row['arms']['C-Topology3']['selected']))/len(use))
        if row['exhaustive_best_cells']:
            recall_best.append(len(set(row['exhaustive_best_cells']) & set(row['arms']['C-Topology3']['selected']))/len(row['exhaustive_best_cells']))
        reference_scan = row['exhaustive_best_D'] > row['common_cost']
        topology_correct = row['arms']['C-Topology3']['common_scan'] == reference_scan
        c0_correct = row['arms']['C0']['common_scan'] == reference_scan
        if topology_correct and not c0_correct: scan_wins += 1
        if row['fixture']=='no_beneficial_scan':
            false_positive=[name for name,a in row['arms'].items() if a['actual_scan']]
    c0_use_recall=sum(len(set(r['useful_cells']) & set(r['arms']['C0']['selected']))/len(r['useful_cells']) for r in rows if r['useful_cells'])/max(1,len(recall_use))
    topology_use_recall=float(np.mean(recall_use)) if recall_use else 0.
    c0_best_recall=float(np.mean([
        len(set(r['exhaustive_best_cells']) & set(r['arms']['C0']['selected']))/len(r['exhaustive_best_cells'])
        for r in rows if r['exhaustive_best_cells']])) if any(r['exhaustive_best_cells'] for r in rows) else 0.
    topology_best_recall=float(np.mean(recall_best)) if recall_best else 0.
    p95_ns=max(x['p95_ns'] for x in graph_samples)
    within_calls=all(a['plan_calls'] <= (11 if name=='C-K' else 7)
        for r in rows for name,a in r['arms'].items())
    within_operations=all(a['graph_operations'] <= a['graph_work_bound']
        for r in rows for a in r['arms'].values() if a['graph_work_bound'])
    gate={'useful_candidate_recall_gain':topology_use_recall-c0_use_recall,
        'useful_recall_at_least_10pp':topology_use_recall-c0_use_recall >= .10,
        'max_D_candidate_recall_not_worse':topology_best_recall >= c0_best_recall,
        'common_scan_agreement_wins_vs_C0':scan_wins,
        'common_scan_agreement_improved_on_2':scan_wins>=2,
        'no_benefit_actual_false_positives':false_positive,
        'no_benefit_case_pass':not false_positive,
        'all_A_star_caps_respected':within_calls,
        'graph_work_bound_respected':within_operations,
        'graph_p95_ms':p95_ns/1e6,'graph_p95_under_5ms':p95_ns<=5_000_000,
        'status':'PASS' if (topology_use_recall-c0_use_recall>=.10 and topology_best_recall>=c0_best_recall and scan_wins>=2 and not false_positive and within_calls and within_operations and p95_ns<=5_000_000) else 'REJECTED_STOP_BEFORE_FIT'}
    annotation_correct=sum(r['annotation']['expected']==r['annotation']['observed'] for r in rows)
    data={'status':'COMPLETED_C_V2B_SYNTHETIC_MECHANISM_SCREEN',
        'protocol':'docs/phase2_c_v2b_topology_protocol.md','mechanism_gate':gate,
        'FIT_data_accessed':False,'admitted_worlds_loaded':False,
        'protected_phase15_generator_called':False,'sensor':SENSOR,'remaining_budget':REMAINING,
        'environment':{'python':sys.version,'platform':platform.platform(),
            'machine':platform.machine(),'processor':platform.processor(),'pid':os.getpid()},
        'source_sha256':{'runner':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'topology_module':hashlib.sha256((ROOT/'src/spatial_memory/topology_evi.py').read_bytes()).hexdigest(),
            'protocol':hashlib.sha256((ROOT/'docs/phase2_c_v2b_topology_protocol.md').read_bytes()).hexdigest()},
        'summary':{'fixtures':len(rows),'fixture_arm_runs':len(rows)*4,
            'C0_useful_recall':c0_use_recall,'topology_useful_recall':topology_use_recall,
            'C0_max_D_recall':c0_best_recall,'topology_max_D_recall':topology_best_recall,
            'topology_annotation_correct':annotation_correct,
            'topology_annotation_total':len(rows),
            'graph_runtime_samples_per_fixture':100},'graph_runtime_samples':graph_samples,
        'fixtures':rows}
    OUT.mkdir(parents=True,exist_ok=False)
    path=OUT/'synthetic_mechanism_results.json'
    path.write_text(json.dumps(data,indent=2,sort_keys=True,default=lambda x:list(x) if isinstance(x,tuple) else x)+'\n')
    print(json.dumps({'status':gate['status'],'gate':gate,'output':str(path),'fixtures':len(rows),'arms':len(rows)*4},indent=2))


def _candidate_label(cell,grid,graph,start,goal):
    from spatial_memory.topology_evi import _candidate_topology_features
    route=plan(grid,start,goal,'optimistic')
    return _candidate_topology_features(grid,cell,graph,start,goal,route)[1]


if __name__ == '__main__':
    run()
