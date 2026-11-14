"""Pure, fail-closed conformance evaluator for C v2.0d result documents."""
from __future__ import annotations
import math
import numpy as np

ARMS=('C0','C-K','C-Route3','C-Topology3-d')
REFERENCE_ARM='C0';D_ARM='C-Topology3-d'


def _close(a,b):
    if a is None or b is None:return a is b
    return math.isclose(float(a),float(b),rel_tol=1e-12,abs_tol=1e-12)


def _recompute_group(rows,arm):
    nonempty=[r for r in rows if r['useful_candidates']]
    max_rows=[r for r in rows if r['exhaustive_best_cells']]
    useful_hits=sum(sum(c in r['arms'][arm]['selected'] for c in r['useful_candidates']) for r in rows)
    useful_n=sum(len(r['useful_candidates']) for r in rows)
    max_hits=sum(sum(c in r['arms'][arm]['selected'] for c in r['exhaustive_best_cells']) for r in rows)
    max_n=sum(len(r['exhaustive_best_cells']) for r in rows)
    return {
      'fixture_count':len(rows),'nonempty_useful_fixture_count':len(nonempty),
      'empty_useful_fixture_count':sum(not r['useful_candidates'] for r in rows),
      'useful_candidate_denominator':useful_n,'max_D_candidate_denominator':max_n,
      'macro_useful_recall':float(np.mean([r['arms'][arm]['useful_recall'] for r in nonempty])) if nonempty else None,
      'micro_useful_recall':useful_hits/useful_n if useful_n else None,
      'macro_max_D_recall':float(np.mean([r['arms'][arm]['max_D_recall'] for r in max_rows])) if max_rows else None,
      'micro_max_D_recall':max_hits/max_n if max_n else None,
      'mean_best_D_regret':float(np.mean([r['arms'][arm]['selected_best_D_regret'] for r in rows])),
      'common_scan_correct':sum(bool(r['arms'][arm]['common_scan_agreement']) for r in rows),
      'common_scan_denominator':len(rows),
      'actual_scans':sum(bool(r['arms'][arm]['actual_authorized']) for r in rows),
      'false_positives':sum(bool(r['arms'][arm]['actual_false_positive']) for r in rows),
      'false_negatives':sum(bool(r['arms'][arm]['actual_false_negative']) for r in rows),
      'mean_scheduler_ns':float(np.mean([r['arms'][arm]['scheduler_ns'] for r in rows])),
      'mean_graph_analysis_ns':float(np.mean([r['arms'][arm]['graph_analysis_ns'] or 0 for r in rows]))}


def _row_metric_errors(row):
    errors=[]
    common=float(row.get('common_cost',math.inf))
    maxd=float(row.get('exhaustive_best_D',0.))
    reference=maxd>common
    for arm in ARMS:
        data=row.get('arms',{}).get(arm)
        if not isinstance(data,dict):errors.append(f'missing arm {arm}');continue
        selected={tuple(x) for x in data.get('selected',[])}
        allowed={tuple(x['cell']) for x in row.get('exhaustive_candidates',[])}
        if not selected.issubset(allowed):errors.append(f'{arm} selected outside exhaustive candidate population')
        if int(data.get('selected_count',-1))!=len(data.get('selected',[])):
            errors.append(f'{arm} selected-count mismatch')
        # Denominator semantics are reviewed in their own isolated category.
        selected_d=max((float(x['D']) for x in row.get('exhaustive_candidates',[]) if tuple(x['cell']) in selected),default=0.)
        if not _close(data.get('selected_D'),selected_d):errors.append(f'{arm} selected D')
        selected_cell=data.get('best_cell')
        if selected_cell is None:
            expected_v=expected_d=0.
        else:
            candidate=next((x for x in row.get('exhaustive_candidates',[])
                            if tuple(x['cell'])==tuple(selected_cell)),None)
            expected_v=float(candidate['V']) if candidate else None
            expected_d=float(candidate['D']) if candidate else None
        if expected_v is None or not _close(data.get('V'),expected_v):errors.append(f'{arm} selected V/reference parity')
        if expected_d is None or not _close(data.get('D'),expected_d):errors.append(f'{arm} selected D/reference parity')
        if selected_cell is not None and tuple(selected_cell) not in selected:errors.append(f'{arm} best cell outside selected prefix')
        if not _close(data.get('D'),selected_d):errors.append(f'{arm} decision D differs from selected maximum')
        if bool(data.get('common_scan')) != (selected_d>common):errors.append(f'{arm} common scan')
        if bool(data.get('common_scan_agreement')) != ((selected_d>common)==reference):errors.append(f'{arm} scan agreement')
        authorized=bool(data.get('actual_authorized'))
        if authorized != (float(data.get('D',0.))>float(data.get('charged_cost',math.inf))):errors.append(f'{arm} actual authorization/cost')
        expected_cost=.5+.01*int(data.get('plan_calls',-1))+.5/20
        if not _close(data.get('charged_cost'),expected_cost):errors.append(f'{arm} frozen cost equation')
        cap=5 if arm=='C-K' else 3
        if len(data.get('selected',[]))>cap:errors.append(f'{arm} candidate cap')
        if int(data.get('plan_calls',-1))!=1+2*len(data.get('selected',[])):errors.append(f'{arm} plan call accounting')
        if bool(data.get('actual_false_positive')) != (authorized and not reference):errors.append(f'{arm} false positive')
        if bool(data.get('actual_false_negative')) != ((not authorized) and reference):errors.append(f'{arm} false negative')
    return errors


def _expected_stage_limits(row,arm):
    """Independent loop-derived limits; does not trust stored limit values."""
    item=row['arms'][arm];n=int(row['shape'][0])*int(row['shape'][1])
    v=int(item['graph_vertices']);e=int(item['graph_edges']);m=int(item['candidate_count'])
    b=int(item['graph_bridges']);c=int(item['graph_components']);a=int(item['graph_articulations'])
    l=int(item['route_length_l']);k=int(item.get('candidate_limit_k',3))
    retained=min(k,m);levels=math.ceil(math.log2(max(2,k))) if retained else 0
    heap_bound=retained*levels+max(0,m-retained)*(1+2*levels)
    prefix_bound=retained*(retained-1)//2
    top=heap_bound+prefix_bound
    selected=int(item['selected_count']);counterfactual=2*selected
    return {
      'grid_construction':{'grid_cell_reads':n,'open_vertex_materializations':v},
      'adjacency_construction':{'directional_neighbor_slots':4*v,'edge_records':2*e},
      'tarjan_and_biconnected':{'vertex_entry_exit_events':2*v,
        'directed_edge_inspections':2*e,'edge_stack_pushes':e,'edge_stack_pops':e,
        'block_edge_visits':e,'cycle_endpoint_visits':2*e},
      'bridge_components_and_terminals':{'component_vertex_visits':v,
        'component_edge_inspections':2*e,'bridge_forest_edge_visits':b,
        'bridge_tree_edge_inspections':2*b,'relevant_bridge_path_reconstruction':b,
        'terminal_articulation_tests':a,'terminal_child_checks':max(0,v-c),
        'relevant_bridge_endpoint_visits':2*b},
      'terminal_bfs':{'vertex_visits':2*v,'directed_edge_inspections':4*e},
      'candidate_features':{'feature_evaluations':m,'node_membership_checks':m,
        'classification_checks':7*m,'neighbor_slots':4*m,'neighbor_membership_checks':4*m,
        'terminal_component_lookups':2*m,'connectivity_pair_checks':16*m,
        'distance_pair_checks':16*m,'route_membership_checks':2*m,'rank_key_builds':m},
      'top_k':{'key_comparisons':top,'heap_comparisons':heap_bound,
        'prefix_order_comparisons':prefix_bound},
      'route_and_astar':{'route_set_insertions':l,'plan_calls':1+2*selected,
        'counterfactual_plan_calls':counterfactual,
        'counterfactual_grid_copy_cell_reads':counterfactual*n}}


def _recompute_numeric(data,aggregates):
    c0=aggregates.get(REFERENCE_ARM,{});d=aggregates.get(D_ARM,{})
    try:
        gain=float(d['macro_useful_recall'])-float(c0['macro_useful_recall'])
        scan_gain=(int(d['common_scan_correct'])-int(c0['common_scan_correct']))/int(d['common_scan_denominator'])
        useful=gain>=.10 and d['micro_useful_recall']>=c0['micro_useful_recall']
        max_d=d['macro_max_D_recall']>=c0['macro_max_D_recall']
        scan=scan_gain>=.05
    except (KeyError,TypeError,ZeroDivisionError):
        return {'efficacy':False,'gain':None,'scan_gain':None}
    no_benefit_ids={r['fixture_id'] for r in data.get('fixtures',[])
        if r.get('family')=='no_benefit_topology_control' and not r.get('useful_candidates')}
    no_benefit_scans=[r['fixture_id'] for r in data.get('fixtures',[])
        if r['fixture_id'] in no_benefit_ids and r['arms'][D_ARM]['actual_authorized']]
    false_positive_nonincrease=(int(d.get('false_positives',10**9))
        <=int(c0.get('false_positives',-1)))
    return {'efficacy':bool(useful and max_d and scan),'useful_gain':gain,
      'scan_gain':scan_gain,'useful_gate':bool(useful),'max_D_gate':bool(max_d),
      'scan_agreement_gate':bool(scan),'no_benefit_gate':not no_benefit_scans,
      'false_positive_nonincrease':false_positive_nonincrease,
      'C0_false_positives':c0.get('false_positives'),
      'topology_false_positives':d.get('false_positives'),
      'no_benefit_cases':len(no_benefit_ids),'no_benefit_authorizations':no_benefit_scans}


def review_document(data, *, expected_source_hashes=None, artifact_integrity_ok=False,
                    correctness_status=None, annotation_status=None,
                    expected_fixture_population_sha256=None):
    """Check validity and numeric acceptance with isolated error collections."""
    expected_source_hashes=expected_source_hashes or {}
    validity_errors={};numeric_errors={};checks={}
    fixtures=data.get('fixtures') if isinstance(data,dict) else None
    if not isinstance(fixtures,list) or not fixtures:
        return {'status':'INVALID_STOP_BEFORE_FIT','checks':{'row_invariants':False},
          'validity_errors':{'row_invariants':['missing fixture rows']},
          'numeric_errors':{'all_numeric_gates':['cannot review without rows']},
          'recomputed_aggregates':{},'recomputed_numeric_gate':{},
          'reference_runtime_p95_ns_independent':None,'FIT_authorized':False}
    checks['structural_correctness']=((correctness_status or data.get('correctness_validation',{}).get('status'))=='PASS'
      and int(data.get('correctness_validation',{}).get('mismatches',0))==0)
    if not checks['structural_correctness']:validity_errors['structural_correctness']=['structural correctness evidence missing or failing']
    checks['fixture_annotations']=((annotation_status or data.get('annotation_validation',{}).get('status'))=='PASS'
      and data.get('annotation_validation',{}).get('candidate_arms_executed') is False)
    if not checks['fixture_annotations']:validity_errors['fixture_annotations']=['independent annotations missing/failing or evaluated with policy arms']
    family_counts=data.get('family_counts',{})
    annotation_data=data.get('annotation_validation',{})
    population_ok=(len(fixtures)==80 and len(family_counts)==8 and all(v==10 for v in family_counts.values())
      and annotation_data.get('fixtures_with_M_gt_5',0)>=60
      and annotation_data.get('fixtures_with_M_gt_20',0)>=20)
    checks['fixture_population']=population_ok
    if not population_ok:validity_errors['fixture_population']=['formal fixture count, balance, or candidate-count diversity invalid']
    fixture_binding_ok=(data.get('seed_namespace')==2026111600
      and isinstance(expected_fixture_population_sha256,str)
      and data.get('fixture_population_sha256')==expected_fixture_population_sha256)
    checks['fixture_binding']=fixture_binding_ok
    if not fixture_binding_ok:validity_errors['fixture_binding']=['seed namespace or canonical fixture digest mismatch']

    row_errors=[]
    for row in fixtures:
        if set(row.get('arms',{}))!=set(ARMS):row_errors.append(f"{row.get('fixture_id')}: arm keys")
        row_errors.extend(f"{row.get('fixture_id')}: {e}" for e in _row_metric_errors(row))
        if int(row.get('candidate_count',-1))!=len(row.get('exhaustive_candidates',[])):row_errors.append(f"{row.get('fixture_id')}: candidate count")
        if float(row.get('common_cost',-1))<0:row_errors.append(f"{row.get('fixture_id')}: common cost")
    checks['row_invariants']=not row_errors
    if row_errors:validity_errors['row_invariants']=row_errors

    aggregate_errors=[];computed={arm:_recompute_group(fixtures,arm) for arm in ARMS}
    saved=data.get('aggregates',{}).get('overall',{})
    for arm in ARMS:
        for key,val in computed[arm].items():
            got=saved.get(arm,{}).get(key)
            if not _close(got,val):aggregate_errors.append(f'{arm}/{key}: saved {got!r}, recomputed {val!r}')
    checks['metric_aggregation']=not aggregate_errors
    if aggregate_errors:validity_errors['metric_aggregation']=aggregate_errors

    denominator_errors=[]
    for row in fixtures:
        useful=row.get('useful_candidates',[]);best=row.get('exhaustive_best_cells',[])
        for arm in ARMS:
            selected={tuple(x) for x in row.get('arms',{}).get(arm,{}).get('selected',[])}
            useful=[tuple(x) for x in row.get('useful_candidates',[])]
            best=[tuple(x) for x in row.get('exhaustive_best_cells',[])]
            expected_useful=(sum(c in selected for c in useful)/len(useful)) if useful else None
            expected_max=(sum(c in selected for c in best)/len(best)) if best else None
            if not _close(row.get('arms',{}).get(arm,{}).get('useful_recall'),expected_useful):
                denominator_errors.append(f"{row.get('fixture_id')}/{arm}: useful recall denominator/value")
            if not _close(row.get('arms',{}).get(arm,{}).get('max_D_recall'),expected_max):
                denominator_errors.append(f"{row.get('fixture_id')}/{arm}: max-D recall denominator/value")
    checks['recall_denominators']=not denominator_errors
    if denominator_errors:validity_errors['recall_denominators']=denominator_errors

    work_errors=[];bound_excesses=[];astar_fail=[];comparison_fail=[]
    for row in fixtures:
        for arm in ARMS:
            item=row.get('arms',{}).get(arm,{})
            if int(item.get('plan_calls',10**9))>(11 if arm=='C-K' else 7):astar_fail.append(row.get('fixture_id'))
        drow=row.get('arms',{}).get(D_ARM,{})
        stage=drow.get('stage_accounting') or {}
        expected_limits=_expected_stage_limits(row,D_ARM)
        if stage.get('limits')!=expected_limits:
            work_errors.append(f"{row.get('fixture_id')}: independently derived stage limits mismatch")
        if set(stage.get('checks',{}))!=set(stage.get('limits',{})) or set(stage.get('checks',{}))!=set(stage.get('observed',{})):
            work_errors.append(f"{row.get('fixture_id')}: stage categories mismatch")
        for section,counts in stage.get('observed',{}).items():
            limits=stage.get('limits',{}).get(section,{})
            if set(counts)!=set(limits):work_errors.append(f"{row.get('fixture_id')}/{section}: counter keys mismatch");continue
            if any(counts[k]>limits[k] for k in counts):bound_excesses.append(f"{row.get('fixture_id')}/{section}: theoretical bound exceeded")
            if stage.get('checks',{}).get(section)!=(all(counts[k]<=limits[k] for k in counts)):
                work_errors.append(f"{row.get('fixture_id')}/{section}: inconsistent pass bit")
        sel=drow.get('selection_counters') or {}
        expected_top=expected_limits['top_k']['key_comparisons']
        if (sel.get('theoretical_heap_comparison_bound')!=expected_top
            or int(sel.get('M',-1))!=int(drow.get('candidate_count',-2))
            or int(sel.get('K',-1))!=int(drow.get('candidate_limit_k',-2))
            or int(sel.get('total_key_comparisons',10**9))!=int(stage.get('observed',{}).get('top_k',{}).get('key_comparisons',-1))):
            work_errors.append(f"{row.get('fixture_id')}: top-K counter binding mismatch")
        if sel.get('total_key_comparisons',10**9)>expected_top:comparison_fail.append(row.get('fixture_id'))
        raw=drow.get('graph_operation_counts') or {}
        observed=stage.get('observed',{})
        expected_graph_counts={
          ('grid_construction','grid_cell_reads'):raw.get('grid_cell_scans'),
          ('adjacency_construction','directional_neighbor_slots'):raw.get('adjacency_neighbor_probes'),
          ('tarjan_and_biconnected','vertex_entry_exit_events'):2*raw.get('vertex_visits',-1),
          ('tarjan_and_biconnected','directed_edge_inspections'):raw.get('edge_inspections'),
          ('tarjan_and_biconnected','edge_stack_pops'):raw.get('biconnected_edge_pops'),
          ('tarjan_and_biconnected','block_edge_visits'):raw.get('biconnected_block_edge_visits'),
          ('tarjan_and_biconnected','cycle_endpoint_visits'):raw.get('cycle_block_vertex_visits'),
          ('bridge_components_and_terminals','component_vertex_visits'):raw.get('component_vertex_visits'),
          ('bridge_components_and_terminals','component_edge_inspections'):raw.get('component_edge_inspections'),
          ('bridge_components_and_terminals','bridge_forest_edge_visits'):raw.get('bridge_forest_edge_visits'),
          ('bridge_components_and_terminals','bridge_tree_edge_inspections'):raw.get('bridge_tree_edge_inspections'),
          ('bridge_components_and_terminals','terminal_articulation_tests'):raw.get('terminal_articulation_tests'),
          ('bridge_components_and_terminals','terminal_child_checks'):raw.get('terminal_child_edge_checks'),
          ('bridge_components_and_terminals','relevant_bridge_endpoint_visits'):raw.get('bridge_endpoint_set_visits'),
          ('terminal_bfs','vertex_visits'):raw.get('bfs_vertex_visits'),
          ('terminal_bfs','directed_edge_inspections'):raw.get('bfs_edge_inspections'),
        }
        for (section,key),expected in expected_graph_counts.items():
            if expected is None or observed.get(section,{}).get(key)!=expected:
                work_errors.append(f"{row.get('fixture_id')}/{section}/{key}: raw graph counter mismatch")
        candidate_expected={
          'feature_evaluations':sel.get('feature_evaluations'),
          'node_membership_checks':sel.get('candidate_node_membership_checks'),
          'neighbor_slots':sel.get('candidate_neighbor_slots'),
          'neighbor_membership_checks':sel.get('candidate_neighbor_membership_checks'),
          'terminal_component_lookups':sel.get('candidate_terminal_component_lookups'),
          'connectivity_pair_checks':sel.get('candidate_connectivity_pairs'),
          'distance_pair_checks':sel.get('candidate_distance_pairs'),
          'route_membership_checks':sel.get('candidate_route_membership_checks'),
          'rank_key_builds':sel.get('rank_key_builds')}
        for key,expected in candidate_expected.items():
            if expected is None or observed.get('candidate_features',{}).get(key)!=expected:
                work_errors.append(f"{row.get('fixture_id')}/candidate_features/{key}: selection counter mismatch")
        if (observed.get('candidate_features',{}).get('classification_checks')!=sum(
             int(sel.get(k,0)) for k in ('candidate_terminal_checks','candidate_separator_checks',
              'candidate_bridge_endpoint_checks','candidate_articulation_checks','candidate_cycle_checks',
              'candidate_nonterminal_checks'))):
            work_errors.append(f"{row.get('fixture_id')}: classification counter mismatch")
        route_obs=observed.get('route_and_astar',{})
        if (route_obs.get('route_set_insertions')!=sel.get('route_set_insertions')
            or route_obs.get('plan_calls')!=drow.get('plan_calls')
            or route_obs.get('counterfactual_plan_calls')!=2*int(drow.get('selected_count',-1))
            or route_obs.get('counterfactual_grid_copy_cell_reads')!=2*int(drow.get('selected_count',-1))*int(row['shape'][0])*int(row['shape'][1])):
            work_errors.append(f"{row.get('fixture_id')}: route/A* counter mismatch")
        if (observed.get('top_k',{}).get('key_comparisons')!=sel.get('total_key_comparisons')
            or observed.get('top_k',{}).get('heap_comparisons')!=sel.get('heap_comparisons')
            or observed.get('top_k',{}).get('prefix_order_comparisons')!=sel.get('final_prefix_comparisons')):
            work_errors.append(f"{row.get('fixture_id')}: top-K observed counter mismatch")
        if (observed.get('grid_construction',{}).get('open_vertex_materializations')!=int(drow.get('graph_vertices',-1))
            or observed.get('adjacency_construction',{}).get('edge_records')!=2*int(drow.get('graph_edges',-1))
            or observed.get('tarjan_and_biconnected',{}).get('edge_stack_pushes')!=int(drow.get('graph_edges',-1))):
            work_errors.append(f"{row.get('fixture_id')}: graph derived counter mismatch")
    checks['accounting_counter_consistency']=not work_errors
    if work_errors:validity_errors['accounting_counter_consistency']=work_errors
    checks['A_star_numeric_limit']=not astar_fail
    if astar_fail:numeric_errors['A_star_limit']=astar_fail
    checks['topK_numeric_limit']=not comparison_fail
    if comparison_fail:numeric_errors['topK_comparison_limit']=comparison_fail
    checks['stage_bound_numeric_gate']=not bound_excesses
    if bound_excesses:numeric_errors['stage_bound_gate']=bound_excesses

    runtime=data.get('runtime_benchmarks',{});ref=runtime.get('reference_scale_17x17',[])
    runtime_protocol_ok=bool(ref) and all(x.get('warmup_calls')==10 and x.get('measured_calls')==100
        and len(x.get('samples_ns',[]))==100 and tuple(x.get('shape',[]))==(17,17) for x in ref)
    checks['runtime_protocol']=runtime_protocol_ok
    if not runtime_protocol_ok:validity_errors['runtime_protocol']=['missing or malformed reference-scale timing samples']
    sample=[x for row in ref for x in row.get('samples_ns',[])]
    measured=int(np.percentile(sample,95)) if sample else None
    runtime_pass=measured is not None and measured<=5_000_000
    checks['reference_scale_runtime_gate']=runtime_pass
    if not runtime_pass:numeric_errors['reference_scale_runtime']=[measured]
    checks['large_map_scaling_reported']=bool(runtime.get('large_map_scaling_no_latency_threshold'))
    if not checks['large_map_scaling_reported']:validity_errors['large_map_scaling_report']=['missing scaling characterization']

    source_ok=data.get('source_sha256')==expected_source_hashes
    checks['source_fingerprints']=source_ok
    if not source_ok:validity_errors['source_fingerprints']=['source hashes differ or are missing']
    checks['artifact_integrity']=bool(artifact_integrity_ok)
    if not artifact_integrity_ok:validity_errors['artifact_integrity']=['artifact manifest missing or mismatched']
    access=data.get('FIT_data_accessed') is False and data.get('admitted_worlds_loaded') is False and data.get('protected_generator_called') is False and data.get('reserved_population_accessed') is False
    checks['data_access_restrictions']=access
    if not access:validity_errors['data_access_restrictions']=['forbidden data access flag missing or true']

    computed_numeric=_recompute_numeric(data,computed)
    numeric_pass=(computed_numeric.get('efficacy') is True
                  and computed_numeric.get('no_benefit_gate') is True
                  and computed_numeric.get('false_positive_nonincrease') is True
                  and not astar_fail and not comparison_fail
                  and not bound_excesses and not work_errors and runtime_pass)
    checks['efficacy_numeric_gate']=computed_numeric.get('efficacy') is True
    checks['no_benefit_authorization_gate']=computed_numeric.get('no_benefit_gate') is True
    checks['false_positive_nonincrease_gate']=computed_numeric.get('false_positive_nonincrease') is True
    if not computed_numeric.get('efficacy'):numeric_errors['efficacy']=computed_numeric
    if not computed_numeric.get('no_benefit_gate'):numeric_errors['no_benefit_authorization']=computed_numeric.get('no_benefit_authorizations')
    if not computed_numeric.get('false_positive_nonincrease'):numeric_errors['false_positive_nonincrease']={
        'C0':computed_numeric.get('C0_false_positives'),
        D_ARM:computed_numeric.get('topology_false_positives')}
    if bool(data.get('numeric_gate',{}).get('status')=='PASS')!=numeric_pass:
        validity_errors['numeric_gate_reproduction']=['stored numeric status disagrees with independent recomputation']
    valid=not validity_errors
    status=('INVALID_STOP_BEFORE_FIT' if not valid else
      'ACCEPTED_FOR_FIT' if numeric_pass else 'VALID_REJECTED_STOP_BEFORE_FIT')
    return {'status':status,'checks':checks,'validity_errors':validity_errors,
      'numeric_errors':numeric_errors,'recomputed_aggregates':computed,
      'recomputed_numeric_gate':computed_numeric,
      'reference_runtime_p95_ns_independent':measured,
      'FIT_authorized':status=='ACCEPTED_FOR_FIT'}
