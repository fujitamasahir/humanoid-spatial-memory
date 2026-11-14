"""Fault-injection regression tests for isolated fail-closed C v2d review."""
from copy import deepcopy
import numpy as np

from spatial_memory.topology_review_d import ARMS,review_document,_recompute_group,_expected_stage_limits


def valid_evidence():
    rows=[]
    families=('sparse_unique_separator','serial_separators','irrelevant_articulation',
      'loop_rich','occupied_connectivity','occupied_distance_only',
      'no_benefit_topology_control','dense_competing_ties')
    for family in families:
      for index in range(10):
        empty=family=='no_benefit_topology_control';candidate=[1,1]
        useful=[] if empty else [candidate];best=[] if empty else [candidate]
        ex=[] if empty else [{'cell':candidate,'V':1.,'D':.8}]
        arms={}
        for arm in ARMS:
          select=[] if empty or arm=='C0' else [candidate]
          sd=.8 if select else 0.;common=not empty
          auth=bool(select)
          calls=3 if select else 1
          cost=.5+.01*calls+.5/20
          arms[arm]={'selected':select,'selected_D':sd,
            'selected_best_D_regret':.8-sd if not empty else 0.,
            'useful_recall':(1. if select else 0.) if useful else None,
            'max_D_recall':(1. if select else 0.) if best else None,
            'common_scan':common and bool(select),
            'common_scan_agreement':(bool(select)==common),
            'actual_authorized':auth,
            'actual_false_positive':False,
            'actual_false_negative':common and not auth,
            'plan_calls':calls,
            'charged_cost':cost,'V':1. if auth else 0.,'D':sd,
            'best_cell':candidate if select else None,'selected_count':len(select),
            'scheduler_ns':100,'graph_analysis_ns':50,'candidate_count':len(ex),
            'stage_accounting':{'checks':{'toy':True},
              'observed':{'toy':{'count':0}},'limits':{'toy':{'count':1}},'passes':True},
            'selection_counters':{'total_key_comparisons':0,
              'theoretical_heap_comparison_bound':2 if len(ex) else 0,'heap_comparisons':0,
              'final_prefix_comparisons':0,'M':len(ex),'K':3,
              'feature_evaluations':len(ex),'candidate_node_membership_checks':len(ex),
              'candidate_neighbor_slots':0,'candidate_neighbor_membership_checks':0,
              'candidate_terminal_component_lookups':0,'candidate_connectivity_pairs':0,
              'candidate_distance_pairs':0,'candidate_route_membership_checks':0,
              'rank_key_builds':len(ex),'candidate_terminal_checks':0,
              'candidate_separator_checks':0,'candidate_bridge_endpoint_checks':0,
              'candidate_articulation_checks':0,'candidate_cycle_checks':0,
              'candidate_nonterminal_checks':0,'route_set_insertions':5},
            'graph_vertices':10,'graph_edges':9,'graph_components':1,
            'graph_bridges':0,'graph_articulations':0,'route_length_l':5,
            'candidate_limit_k':3,
            'graph_operation_counts':{'grid_cell_scans':289,
              'adjacency_neighbor_probes':40,'vertex_visits':10,'edge_inspections':18,
              'biconnected_edge_pops':9,'biconnected_block_edge_visits':9,
              'cycle_block_vertex_visits':18,'component_vertex_visits':10,
              'component_edge_inspections':18,'bridge_forest_edge_visits':0,
              'bridge_tree_edge_inspections':0,'terminal_articulation_tests':0,
              'terminal_child_edge_checks':9,'bridge_endpoint_set_visits':0,
              'bfs_vertex_visits':20,'bfs_edge_inspections':36}}
        for arm in ARMS:
          item=arms[arm];limits=_expected_stage_limits({'shape':[17,17],'arms':arms},arm)
          m=len(ex);calls=item['plan_calls'];selected_count=item['selected_count']
          observed={
            'grid_construction':{'grid_cell_reads':289,'open_vertex_materializations':10},
            'adjacency_construction':{'directional_neighbor_slots':40,'edge_records':18},
            'tarjan_and_biconnected':{'vertex_entry_exit_events':20,
              'directed_edge_inspections':18,'edge_stack_pushes':9,'edge_stack_pops':9,
              'block_edge_visits':9,'cycle_endpoint_visits':18},
            'bridge_components_and_terminals':{'component_vertex_visits':10,
              'component_edge_inspections':18,'bridge_forest_edge_visits':0,
              'bridge_tree_edge_inspections':0,'relevant_bridge_path_reconstruction':0,
              'terminal_articulation_tests':0,'terminal_child_checks':9,
              'relevant_bridge_endpoint_visits':0},
            'terminal_bfs':{'vertex_visits':20,'directed_edge_inspections':36},
            'candidate_features':{'feature_evaluations':item['selection_counters']['feature_evaluations'],
              'node_membership_checks':m,'classification_checks':0,'neighbor_slots':0,
              'neighbor_membership_checks':0,'terminal_component_lookups':0,
              'connectivity_pair_checks':0,'distance_pair_checks':0,
              'route_membership_checks':0,'rank_key_builds':m},
            'top_k':{'key_comparisons':0,'heap_comparisons':0,'prefix_order_comparisons':0},
            'route_and_astar':{'route_set_insertions':5,'plan_calls':calls,
              'counterfactual_plan_calls':2*selected_count,
              'counterfactual_grid_copy_cell_reads':2*selected_count*289}}
          item['graph_operation_counts']=arms['C0']['graph_operation_counts']
          item['stage_accounting']={'checks':{stage:True for stage in limits},
            'observed':observed,'limits':limits,'passes':True}
        rows.append({'fixture_id':f'{family}_{index:03d}','family':family,
          'shape':[17,17],'density_class':'synthetic','start':[1,1],'goal':[5,5],
          'candidate_count':len(ex),'exhaustive_candidates':ex,
          'common_cost':.595,'exhaustive_best_D':0. if empty else .8,
          'exhaustive_best_cells':best,'useful_candidates':useful,
          'reference_common_scan':common,'arms':arms})
    aggregates={'overall':{arm:_recompute_group(rows,arm) for arm in ARMS}}
    data={'fixtures':rows,'fixture_count':80,
      'family_counts':{family:10 for family in families},
      'correctness_validation':{'status':'PASS','mismatches':0},
      'annotation_validation':{'status':'PASS','candidate_arms_executed':False,
        'fixtures_with_M_gt_5':70,'fixtures_with_M_gt_20':60},
      'aggregates':aggregates,'source_sha256':{'source.py':'abc'},
      'fixture_population_sha256':'fixture-digest','seed_namespace':2026111600,
      'numeric_gate':{'status':'PASS'},
      'runtime_benchmarks':{'reference_scale_17x17':[{'fixture_id':'ref','shape':[17,17],
        'warmup_calls':10,'measured_calls':100,'samples_ns':[100]*100}],
        'large_map_scaling_no_latency_threshold':[{'N':128*128}]},
      'FIT_data_accessed':False,'admitted_worlds_loaded':False,
      'protected_generator_called':False,'reserved_population_accessed':False}
    return data


def run(data=None,*,source_ok=True,artifact_ok=True):
    data=data or valid_evidence()
    expected=data['source_sha256'] if source_ok else {'source.py':'changed'}
    return review_document(data,expected_source_hashes=expected,
      artifact_integrity_ok=artifact_ok,
      expected_fixture_population_sha256='fixture-digest')


def test_all_valid_evidence_is_accepted_and_requires_all_gates():
    result=run()
    assert result['status']=='ACCEPTED_FOR_FIT'
    assert result['FIT_authorized'] is True
    assert all(result['checks'].values())


def test_single_structural_failure_isolated_from_other_checks():
    data=valid_evidence();data['correctness_validation']['status']='FAIL'
    out=run(data)
    assert out['status']=='INVALID_STOP_BEFORE_FIT'
    assert out['checks']['structural_correctness'] is False
    assert out['checks']['fixture_annotations'] is True
    assert out['checks']['metric_aggregation'] is True


def test_single_annotation_failure_isolated():
    data=valid_evidence();data['annotation_validation']['status']='INVALID'
    out=run(data)
    assert out['checks']['fixture_annotations'] is False
    assert out['checks']['structural_correctness'] is True
    assert out['checks']['metric_aggregation'] is True


def test_fixture_binding_mismatch_fails_without_corrupting_metrics():
    data=valid_evidence();data['fixture_population_sha256']='different'
    out=run(data)
    assert out['checks']['fixture_binding'] is False
    assert out['checks']['metric_aggregation'] is True
    assert out['status']=='INVALID_STOP_BEFORE_FIT'


def test_single_row_integrity_failure_isolated():
    data=valid_evidence();data['fixtures'][0]['candidate_count']=99
    out=run(data)
    assert out['checks']['row_invariants'] is False
    assert out['checks']['metric_aggregation'] is True
    assert out['checks']['recall_denominators'] is True


def test_single_aggregate_failure_isolated():
    data=valid_evidence();data['aggregates']['overall']['C0']['actual_scans']+=1
    out=run(data)
    assert out['checks']['metric_aggregation'] is False
    assert out['checks']['row_invariants'] is True
    assert out['checks']['recall_denominators'] is True


def test_empty_recall_denominator_failure_is_isolated():
    data=valid_evidence()
    row=next(r for r in data['fixtures'] if r['family']=='no_benefit_topology_control')
    row['arms']['C-Topology3-d']['useful_recall']=0.
    out=run(data)
    assert out['checks']['recall_denominators'] is False
    assert out['checks']['metric_aggregation'] is True
    assert out['checks']['row_invariants'] is True


def test_valid_numeric_efficacy_rejection_is_not_mislabeled_invalid():
    data=valid_evidence()
    for row in data['fixtures']:
      if row['useful_candidates']:
        for arm in ARMS:
          val=row['arms'][arm];val['selected']=[];val['selected_D']=0.;val['selected_best_D_regret']=.9
          val['useful_recall']=0.;val['max_D_recall']=0.;val['common_scan']=False
          val['common_scan_agreement']=False;val['actual_authorized']=False
          val['actual_false_negative']=True;val['plan_calls']=1;val['selected_count']=0
          val['charged_cost']=.535
          val['best_cell']=None;val['V']=0.;val['D']=0.
          if arm=='C-Topology3-d':
            val['stage_accounting']['limits']=_expected_stage_limits(row,arm)
            route=val['stage_accounting']['observed']['route_and_astar']
            route.update(route_set_insertions=5,plan_calls=1,
              counterfactual_plan_calls=0,counterfactual_grid_copy_cell_reads=0)
    data['aggregates']['overall']={arm:_recompute_group(data['fixtures'],arm) for arm in ARMS}
    data['numeric_gate']['status']='REJECTED'
    out=run(data)
    assert out['status']=='VALID_REJECTED_STOP_BEFORE_FIT'
    assert out['checks']['efficacy_numeric_gate'] is False
    assert out['checks']['metric_aggregation'] is True


def test_false_positive_numeric_gate_does_not_corrupt_row_validity():
    data=valid_evidence();row=data['fixtures'][0];d=row['arms']['C-Topology3-d']
    cell=row['exhaustive_candidates'][0]['cell']
    row['exhaustive_candidates'][0]['D']=.57
    row['exhaustive_best_D']=.57;row['exhaustive_best_cells']=[cell]
    row['useful_candidates']=[]
    d.update(selected=[cell],selected_D=.57,selected_best_D_regret=0.,
      useful_recall=None,max_D_recall=1.,common_scan=False,
      common_scan_agreement=False,actual_authorized=True,
      actual_false_positive=True,actual_false_negative=False,
      plan_calls=3,charged_cost=.555,best_cell=cell,V=1.,D=.57,selected_count=1)
    for arm in ARMS:
        item=row['arms'][arm]
        item['selected_D']=.57 if item['selected'] else 0.
        item['D']=item['selected_D'];item['V']=1. if item['selected'] else 0.
        item['common_scan']=item['selected_D']>.595
        item['selected_best_D_regret']=.57-item['selected_D']
        item['useful_recall']=None
        item['max_D_recall']=1. if item['selected'] else 0.
        item['common_scan_agreement']=(item['selected_D']>.595)==False
        item['actual_false_positive']=bool(item['actual_authorized'])
        item['actual_false_negative']=False
        if arm=='C-Topology3-d':item['stage_accounting']['limits']=_expected_stage_limits(row,arm)
    data['numeric_gate']['status']='REJECTED'
    data['aggregates']['overall']={arm:_recompute_group(data['fixtures'],arm) for arm in ARMS}
    out=run(data)
    assert out['checks']['row_invariants'] is True
    assert out['checks']['metric_aggregation'] is True
    assert out['status']=='VALID_REJECTED_STOP_BEFORE_FIT'


def test_stage_bound_and_astar_failures_are_valid_numeric_rejections():
    data=valid_evidence();row=data['fixtures'][1];d=row['arms']['C-Topology3-d']
    stage=d['stage_accounting'];limit=stage['limits']['grid_construction']['grid_cell_reads']
    stage['observed']['grid_construction']['grid_cell_reads']=limit+1
    d['graph_operation_counts']['grid_cell_scans']=limit+1
    stage['checks']['grid_construction']=False;stage['passes']=False
    data['numeric_gate']['status']='REJECTED'
    out=run(data)
    assert out['checks']['accounting_counter_consistency'] is True
    assert out['checks']['stage_bound_numeric_gate'] is False
    assert out['status']=='VALID_REJECTED_STOP_BEFORE_FIT'
    data=valid_evidence();data['fixtures'][0]['arms']['C-Topology3-d']['plan_calls']=8
    data['numeric_gate']['status']='REJECTED'
    out=run(data)
    assert out['checks']['A_star_numeric_limit'] is False
    assert out['checks']['row_invariants'] is False
    assert out['status']=='INVALID_STOP_BEFORE_FIT'


def test_runtime_limit_failure_is_valid_rejection_but_malformed_runtime_is_invalid():
    data=valid_evidence();data['runtime_benchmarks']['reference_scale_17x17'][0]['samples_ns']=[6_000_000]*100
    data['numeric_gate']['status']='REJECTED'
    out=run(data)
    assert out['checks']['runtime_protocol'] is True
    assert out['checks']['reference_scale_runtime_gate'] is False
    assert out['status']=='VALID_REJECTED_STOP_BEFORE_FIT'
    data=valid_evidence();data['runtime_benchmarks']['reference_scale_17x17'][0]['samples_ns']=[1]
    data['numeric_gate']['status']='REJECTED'
    out=run(data)
    assert out['checks']['runtime_protocol'] is False
    assert out['status']=='INVALID_STOP_BEFORE_FIT'


def test_source_artifact_and_data_access_failures_fail_closed_independently():
    out=run(source_ok=False)
    assert out['checks']['source_fingerprints'] is False
    assert out['checks']['artifact_integrity'] is True
    assert out['status']=='INVALID_STOP_BEFORE_FIT'
    out=run(artifact_ok=False)
    assert out['checks']['artifact_integrity'] is False
    assert out['checks']['source_fingerprints'] is True
    assert out['status']=='INVALID_STOP_BEFORE_FIT'
    data=valid_evidence();data['FIT_data_accessed']=True
    out=run(data)
    assert out['checks']['data_access_restrictions'] is False
    assert out['status']=='INVALID_STOP_BEFORE_FIT'


def test_missing_or_invalid_evidence_never_authorizes_fit():
    for data in ({}, {'fixtures':None}, {'numeric_gate':{'status':'PASS'}}):
        out=review_document(data,expected_source_hashes={},artifact_integrity_ok=False)
        assert out['status']=='INVALID_STOP_BEFORE_FIT'
        assert out['FIT_authorized'] is False
