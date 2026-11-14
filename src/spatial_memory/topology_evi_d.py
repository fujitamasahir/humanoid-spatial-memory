"""C v2.0d: v2.0c topology ranking with deterministic bounded top-K selection.

All structural features and the EVI equations remain those of v2.0c. The only
online selection change is replacing a complete candidate sort with a fixed-
size min heap whose root is the worst retained lexicographic rank.
"""
from __future__ import annotations

import heapq
import math
from time import perf_counter_ns

from .evi import EVIParameters
from .navigation import plan
from .topology_evi_c import (
    analyze_public_topology_c,
    eligible_topology_candidates_c,
)


def topology_rank_key_d(feature, probability, cell):
    """The exact C v2.0c lexicographic key; lower tuples rank first."""
    structural, _label = feature
    q = float(probability[cell[1], cell[0]])
    return (
        structural[0], -structural[1], -structural[2],
        -q * (1.0 - q), cell[1], cell[0],
    )


def _feature_d(grid, cell, graph, start, goal, route_set, counters):
    """v2.0c feature labels with counters for each bounded lookup loop."""
    x, y = cell
    counters['candidate_node_membership_checks'] += 1
    if cell in graph['node_set']:
        counters['candidate_terminal_checks'] += 1
        if cell in (tuple(start), tuple(goal)):
            return (0, 1, 0), 'traversable_terminal'
        counters['candidate_separator_checks'] += 1
        if cell in graph['separating']:
            return (0, 1, 0), 'start_goal_separating_articulation'
        counters['candidate_bridge_endpoint_checks'] += 1
        if cell in graph['relevant_bridge_endpoints']:
            return (2, graph['bridge_degree'].get(cell, 0), 0), 'terminal_relevant_bridge_endpoint'
        counters['candidate_articulation_checks'] += 1
        if cell in graph['articulation']:
            counters['candidate_route_membership_checks'] += 1
            if cell in route_set:
                return (3, 1, 0), 'other_route_articulation'
        counters['candidate_cycle_checks'] += 1
        if cell in graph['cyclic_block_vertices']:
            counters['candidate_route_membership_checks'] += 1
            if cell in route_set:
                return (4, 1, 0), 'route_cell_with_alternative_cycle'
        counters['candidate_articulation_checks'] += 1
        if cell in graph['articulation']:
            return (5, 0, 0), 'irrelevant_articulation'
        return (6, 0, 0), 'other_traversable'

    counters['candidate_nonterminal_checks'] += 1
    if cell == tuple(goal):
        return (0, 1, 0), 'nontraversable_goal_terminal'
    neighbors = []
    for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1)):
        counters['candidate_neighbor_slots'] += 1
        neighbor = (x + dx, y + dy)
        counters['candidate_neighbor_membership_checks'] += 1
        if neighbor in graph['node_set']:
            neighbors.append(neighbor)
    counters['candidate_terminal_component_lookups'] += 2
    start_component = graph['component'].get(tuple(start))
    goal_component = graph['component'].get(tuple(goal))
    distinct = (start_component is not None and goal_component is not None
                and start_component != goal_component)
    connected = False
    if distinct:
        for a in neighbors:
            for b in neighbors:
                counters['candidate_connectivity_pairs'] += 1
                if (graph['component'].get(a) == start_component
                        and graph['component'].get(b) == goal_component):
                    connected = True
                    break
            if connected:
                break
    if connected:
        return (1, 1, 0), 'nontraversable_connectivity_restoration'
    gain = 0
    if math.isfinite(graph['baseline_distance']):
        best = math.inf
        for a in neighbors:
            for b in neighbors:
                counters['candidate_distance_pairs'] += 1
                distance = (graph['dist_start'].get(a, math.inf) + 2
                            + graph['dist_goal'].get(b, math.inf))
                best = min(best, distance)
        if math.isfinite(best):
            gain = max(0, int(graph['baseline_distance'] - best))
    if gain > 0:
        return (1, 0, gain), 'nontraversable_distance_shortcut'
    return (6, 0, 0), 'nontraversable_no_route_benefit'


class _WorstFirst:
    __slots__ = ('key', 'cell', 'feature', 'counter')

    def __init__(self, key, cell, feature, counter):
        self.key = key
        self.cell = cell
        self.feature = feature
        self.counter = counter

    def __lt__(self, other):
        self.counter['heap_comparisons'] += 1
        # heapq is a min heap: reverse the C v2.0c order so the worst retained
        # element (largest ordinary key) is at the root.
        return self.key > other.key


def rank_topology_candidates_d(grid, probability, candidates, graph,
                               start, goal, route, k=3):
    """Return the exact full-sort prefix using O(M log K) selection work."""
    if type(k) is not int or k < 0:
        raise ValueError('K must be a nonnegative integer')
    route_set = set(route)
    stats = {
        'candidate_visits': 0,
        'feature_evaluations': 0,
        'rank_key_builds': 0,
        'heap_pushes': 0,
        'heap_replacements': 0,
        'heap_comparisons': 0,
        'final_prefix_comparisons': 0,
        'M': len(candidates),
        'K': k,
        'L': len(route),
        'route_set_insertions': len(route_set),
        'candidate_node_membership_checks': 0,
        'candidate_terminal_checks': 0,
        'candidate_separator_checks': 0,
        'candidate_bridge_endpoint_checks': 0,
        'candidate_articulation_checks': 0,
        'candidate_cycle_checks': 0,
        'candidate_route_membership_checks': 0,
        'candidate_nonterminal_checks': 0,
        'candidate_neighbor_slots': 0,
        'candidate_neighbor_membership_checks': 0,
        'candidate_terminal_component_lookups': 0,
        'candidate_connectivity_pairs': 0,
        'candidate_distance_pairs': 0,
    }
    heap = []
    for raw_cell in candidates:
        cell = tuple(raw_cell)
        stats['candidate_visits'] += 1
        feature = _feature_d(grid, cell, graph, start, goal, route_set, stats)
        stats['feature_evaluations'] += 1
        key = topology_rank_key_d(feature, probability, cell)
        stats['rank_key_builds'] += 1
        if k == 0:
            continue
        item = _WorstFirst(key, cell, feature, stats)
        if len(heap) < k:
            heapq.heappush(heap, item)
            stats['heap_pushes'] += 1
        else:
            stats['heap_comparisons'] += 1
            if key < heap[0].key:
                heapq.heapreplace(heap, item)
                stats['heap_replacements'] += 1

    def compare(a, b):
        stats['final_prefix_comparisons'] += 1
        return (a.key > b.key) - (a.key < b.key)

    ordered = []
    for item in heap:
        index = 0
        while index < len(ordered) and compare(ordered[index], item) <= 0:
            index += 1
        ordered.insert(index, item)
    cells = [item.cell for item in ordered]
    features = {item.cell: item.feature for item in ordered}
    keys = {item.cell: item.key for item in ordered}
    stats['top_k'] = len(cells)
    stats['total_key_comparisons'] = (
        stats['heap_comparisons'] + stats['final_prefix_comparisons']
    )
    stats['theoretical_heap_comparison_bound'] = _heap_comparison_bound(len(candidates), k)
    return cells, features, keys, stats


def _heap_comparison_bound(m, k):
    """Comparison bound for this push/replace heap plus final K-item ordering."""
    if not m or not k:
        return 0
    retained = min(m, k)
    # Each insertion/replacement sifts through at most floor(log2 K) levels;
    # a binary sift-down uses at most two comparisons per level. Each of the
    # remaining candidates first performs one root comparison.
    levels = math.ceil(math.log2(max(2, k)))
    heap_bound = retained * levels + max(0, m - retained) * (1 + 2 * levels)
    prefix_bound = max(0, retained * (retained - 1) // 2)
    return heap_bound + prefix_bound


def accounting_bounds_d(*, n, vertices, edges, bridges, components,
                        articulation_points, m, route_length, k):
    """Loop-derived, stage-separated bounds; units are not summed together."""
    v, e = vertices, edges
    b = min(bridges, e)
    c = min(components, v)
    a = min(articulation_points, v)
    return {
        'grid_construction': {
            'grid_cell_reads_bound': n,
            'open_vertex_materializations_bound': v,
        },
        'adjacency_construction': {
            'directional_neighbor_slots_bound': 4 * v,
            'undirected_edge_records_bound': 2 * e,
        },
        'tarjan_and_biconnected': {
            'vertex_entry_exit_bound': 2 * v,
            'directed_edge_inspections_bound': 2 * e,
            'edge_stack_pushes_bound': e,
            'edge_stack_pops_bound': e,
            'block_edge_visits_bound': e,
            'cycle_endpoint_visits_bound': 2 * e,
        },
        'bridge_components_and_terminals': {
            'component_vertex_visits_bound': v,
            'component_edge_inspections_bound': 2 * e,
            'bridge_forest_edge_visits_bound': b,
            'bridge_tree_edge_inspections_bound': 2 * b,
            'relevant_bridge_path_reconstruction_bound': b,
            'terminal_articulation_tests_bound': a,
            'terminal_child_checks_bound': max(0, v - c),
            'relevant_bridge_endpoint_visits_bound': 2 * b,
        },
        'terminal_bfs': {
            'vertex_visits_bound': 2 * v,
            'directed_edge_inspections_bound': 4 * e,
        },
        'candidate_features': {
            'candidate_feature_evaluations_bound': m,
            'candidate_node_membership_checks_bound': m,
            'candidate_classification_checks_bound': 7 * m,
            'directional_neighbor_slots_bound': 4 * m,
            'neighbor_node_membership_checks_bound': 4 * m,
            'terminal_component_lookups_bound': 2 * m,
            'neighbor_component_pair_checks_bound': 16 * m,
            'distance_pair_checks_bound': 16 * m,
            'route_membership_checks_bound': 2 * m,
            'rank_key_builds_bound': m,
        },
        'top_k': {
            'eligible_candidates': m,
            'retained_limit': min(k, m),
            'rank_key_comparisons_bound': _heap_comparison_bound(m, k),
            'heap_comparisons_bound': (min(m,k)*math.ceil(math.log2(max(2,k)))
                +max(0,m-min(m,k))*(1+2*math.ceil(math.log2(max(2,k)))) if m and k else 0),
            'prefix_order_comparisons_bound': min(m,k)*max(0,min(m,k)-1)//2,
            'asymptotic_bound': 'O(M log(K+1) + K^2)',
        },
        'route_and_astar': {
            'route_set_insertions_bound': route_length,
            'nominal_astar_calls': 1,
            'counterfactual_astar_calls_bound': 2 * min(k, m),
            'maximum_total_astar_calls': 1 + 2 * min(k, m),
            'single_astar_worst_case': 'O(V^2 log(V+1)); separate from topology preprocessing',
            'counterfactual_grid_copy_cell_reads_bound': 2 * min(k, m) * n,
        },
    }


def observed_accounting_d(graph, selection, *, n, route_length, plan_calls,
                          counterfactual_calls):
    """Observed loop counters and independent stage-wise upper-bound checks."""
    counts = graph['operation_counts']
    v, e = graph['vertices'], graph['edges']
    b, c, a = len(graph['bridges']), graph['component_count'], len(graph['articulation'])
    observed = {
        'grid_construction': {'grid_cell_reads': counts['grid_cell_scans'],
                              'open_vertex_materializations': v},
        'adjacency_construction': {'directional_neighbor_slots': counts['adjacency_neighbor_probes'],
                                   'edge_records': 2 * e},
        'tarjan_and_biconnected': {
            'vertex_entry_exit_events': 2 * counts['vertex_visits'],
            'directed_edge_inspections': counts['edge_inspections'],
            'edge_stack_pushes': e,
            'edge_stack_pops': counts['biconnected_edge_pops'],
            'block_edge_visits': counts['biconnected_block_edge_visits'],
            'cycle_endpoint_visits': counts['cycle_block_vertex_visits'],
        },
        'bridge_components_and_terminals': {
            'component_vertex_visits': counts['component_vertex_visits'],
            'component_edge_inspections': counts['component_edge_inspections'],
            'bridge_forest_edge_visits': counts['bridge_forest_edge_visits'],
            'bridge_tree_edge_inspections': counts['bridge_tree_edge_inspections'],
            'relevant_bridge_path_reconstruction': len(graph['relevant_bridges']),
            'terminal_articulation_tests': counts['terminal_articulation_tests'],
            'terminal_child_checks': counts['terminal_child_edge_checks'],
            'relevant_bridge_endpoint_visits': counts['bridge_endpoint_set_visits'],
        },
        'terminal_bfs': {'vertex_visits': counts['bfs_vertex_visits'],
                         'directed_edge_inspections': counts['bfs_edge_inspections']},
        'candidate_features': {
            'feature_evaluations': selection['feature_evaluations'],
            'node_membership_checks': selection['candidate_node_membership_checks'],
            'classification_checks': sum(selection[k] for k in (
                'candidate_terminal_checks','candidate_separator_checks',
                'candidate_bridge_endpoint_checks','candidate_articulation_checks',
                'candidate_cycle_checks','candidate_nonterminal_checks')),
            'neighbor_slots': selection['candidate_neighbor_slots'],
            'neighbor_membership_checks': selection['candidate_neighbor_membership_checks'],
            'terminal_component_lookups': selection['candidate_terminal_component_lookups'],
            'connectivity_pair_checks': selection['candidate_connectivity_pairs'],
            'distance_pair_checks': selection['candidate_distance_pairs'],
            'route_membership_checks': selection['candidate_route_membership_checks'],
            'rank_key_builds': selection['rank_key_builds'],
        },
        'top_k': {'key_comparisons': selection['total_key_comparisons'],
                  'heap_comparisons': selection['heap_comparisons'],
                  'prefix_order_comparisons': selection['final_prefix_comparisons']},
        'route_and_astar': {'route_set_insertions': selection['route_set_insertions'],
                            'plan_calls': plan_calls,
                            'counterfactual_plan_calls': counterfactual_calls,
                            'counterfactual_grid_copy_cell_reads': counterfactual_calls * n},
    }
    bounds = accounting_bounds_d(
        n=n, vertices=v, edges=e, bridges=b, components=c,
        articulation_points=a, m=selection['M'], route_length=route_length,
        k=selection['K'],
    )
    limits = {
        'grid_construction': {'grid_cell_reads': bounds['grid_construction']['grid_cell_reads_bound'],
                              'open_vertex_materializations': bounds['grid_construction']['open_vertex_materializations_bound']},
        'adjacency_construction': {'directional_neighbor_slots': bounds['adjacency_construction']['directional_neighbor_slots_bound'],
                                   'edge_records': bounds['adjacency_construction']['undirected_edge_records_bound']},
        'tarjan_and_biconnected': {'vertex_entry_exit_events': bounds['tarjan_and_biconnected']['vertex_entry_exit_bound'],
                                   'directed_edge_inspections': bounds['tarjan_and_biconnected']['directed_edge_inspections_bound'],
                                   'edge_stack_pushes': bounds['tarjan_and_biconnected']['edge_stack_pushes_bound'],
                                   'edge_stack_pops': bounds['tarjan_and_biconnected']['edge_stack_pops_bound'],
                                   'block_edge_visits': bounds['tarjan_and_biconnected']['block_edge_visits_bound'],
                                   'cycle_endpoint_visits': bounds['tarjan_and_biconnected']['cycle_endpoint_visits_bound']},
        'bridge_components_and_terminals': {'component_vertex_visits': bounds['bridge_components_and_terminals']['component_vertex_visits_bound'],
                                            'component_edge_inspections': bounds['bridge_components_and_terminals']['component_edge_inspections_bound'],
                                            'bridge_forest_edge_visits': bounds['bridge_components_and_terminals']['bridge_forest_edge_visits_bound'],
                                            'bridge_tree_edge_inspections': bounds['bridge_components_and_terminals']['bridge_tree_edge_inspections_bound'],
                                            'relevant_bridge_path_reconstruction': bounds['bridge_components_and_terminals']['relevant_bridge_path_reconstruction_bound'],
                                            'terminal_articulation_tests': bounds['bridge_components_and_terminals']['terminal_articulation_tests_bound'],
                                            'terminal_child_checks': bounds['bridge_components_and_terminals']['terminal_child_checks_bound'],
                                            'relevant_bridge_endpoint_visits': bounds['bridge_components_and_terminals']['relevant_bridge_endpoint_visits_bound']},
        'terminal_bfs': {'vertex_visits': bounds['terminal_bfs']['vertex_visits_bound'],
                         'directed_edge_inspections': bounds['terminal_bfs']['directed_edge_inspections_bound']},
        'candidate_features': {'feature_evaluations': bounds['candidate_features']['candidate_feature_evaluations_bound'],
                               'node_membership_checks': bounds['candidate_features']['candidate_node_membership_checks_bound'],
                               'classification_checks': bounds['candidate_features']['candidate_classification_checks_bound'],
                               'neighbor_slots': bounds['candidate_features']['directional_neighbor_slots_bound'],
                               'neighbor_membership_checks': bounds['candidate_features']['neighbor_node_membership_checks_bound'],
                               'terminal_component_lookups': bounds['candidate_features']['terminal_component_lookups_bound'],
                               'connectivity_pair_checks': bounds['candidate_features']['neighbor_component_pair_checks_bound'],
                               'distance_pair_checks': bounds['candidate_features']['distance_pair_checks_bound'],
                               'route_membership_checks': bounds['candidate_features']['route_membership_checks_bound'],
                               'rank_key_builds': bounds['candidate_features']['rank_key_builds_bound']},
        'top_k': {'key_comparisons': bounds['top_k']['rank_key_comparisons_bound'],
                  'heap_comparisons': bounds['top_k']['heap_comparisons_bound'],
                  'prefix_order_comparisons': bounds['top_k']['prefix_order_comparisons_bound']},
        'route_and_astar': {'route_set_insertions': bounds['route_and_astar']['route_set_insertions_bound'],
                            'plan_calls': bounds['route_and_astar']['maximum_total_astar_calls'],
                            'counterfactual_plan_calls': bounds['route_and_astar']['counterfactual_astar_calls_bound'],
                            'counterfactual_grid_copy_cell_reads': bounds['route_and_astar']['counterfactual_grid_copy_cell_reads_bound']},
    }
    checks = {stage: all(observed[stage][key] <= limits[stage][key]
                         for key in limits[stage]) for stage in limits}
    return {'bounds': bounds, 'observed': observed, 'limits': limits,
            'checks': checks, 'passes': all(checks.values())}


def information_value_topology_d(grid, probability, position, goal, yaw,
                                 unknown, sensor, remaining, parameters=None):
    """C v2.0d: v2.0c decision semantics with bounded top-three extraction."""
    scheduler_started = perf_counter_ns()
    p = parameters or EVIParameters(max_candidates=3)
    if p.max_candidates != 3:
        raise ValueError('C-Topology3-d fixes K=3')

    t0 = perf_counter_ns()
    nominal = plan(grid, position, goal, unknown)
    nominal_astar_ns = perf_counter_ns() - t0
    candidates, footprint = eligible_topology_candidates_c(
        grid, probability, position, yaw, sensor
    )
    graph_started = perf_counter_ns()
    graph = analyze_public_topology_c(grid, position, goal, unknown)
    ordered, features, keys, selection = rank_topology_candidates_d(
        grid, probability, candidates, graph, position, goal,
        nominal or [], p.max_candidates,
    )
    graph_analysis_ns = perf_counter_ns() - graph_started

    best = {'value': 0., 'delay_regret': 0., 'cell': None,
            'occupied_probability': None}
    calls = 1
    counterfactual_astar_ns = []
    for cell in ordered:
        routes = []
        for outcome in (0, 1):
            counterfactual = grid.copy()
            counterfactual[cell[1], cell[0]] = outcome
            t0 = perf_counter_ns()
            routes.append(plan(counterfactual, position, goal, unknown))
            counterfactual_astar_ns.append(perf_counter_ns() - t0)
            calls += 1

        def loss(path, occupied):
            if not path:
                return p.failure_cost
            return len(path) - 1 + (p.failure_cost if occupied and cell in path else 0)

        q = float(probability[cell[1], cell[0]])
        values = [[loss(path, occupied) for occupied in (0, 1)] for path in routes]
        before = min((1 - q) * row[0] + q * row[1] for row in values)
        after = (1 - q) * min(row[0] for row in values) + q * min(row[1] for row in values)
        value = max(0., before - after)
        actions = [tuple(path[1]) if len(path) > 1 else None for path in routes]
        delay = value * min(q, 1 - q) if actions[0] != actions[1] else 0.
        if (delay, value) > (best['delay_regret'], best['value']):
            best = {'value': value, 'delay_regret': delay, 'cell': cell,
                    'occupied_probability': q}

    cost = p.sensing_cost + p.plan_cost * calls + p.scarcity_cost / max(1, remaining)
    # The analysis counters are retained by stage, never collapsed into a
    # heterogeneous scalar work score.
    counts = graph['operation_counts']
    n = int(grid.size); v = graph['vertices']; e = graph['edges']
    accounting = accounting_bounds_d(
        n=n, vertices=v, edges=e, bridges=len(graph['bridges']),
        components=graph['component_count'],
        articulation_points=len(graph['articulation']), m=len(candidates),
        route_length=len(nominal or []), k=p.max_candidates,
    )
    selected_counterfactual_calls = calls - 1
    accounting_observed = observed_accounting_d(
        graph, selection, n=n, route_length=len(nominal or []),
        plan_calls=calls, counterfactual_calls=selected_counterfactual_calls,
    )
    scheduler_ns = perf_counter_ns() - scheduler_started
    route_set = set(nominal or [])
    return {
        **best, 'cost': cost, 'net_value': best['delay_regret'] - cost,
        'plan_calls': calls, 'visible_cells': len(footprint),
        'nominal_route': nominal, 'candidate_count': len(candidates),
        'shortlisted_candidates': [
            {'cell': cell, 'structural': features[cell][0],
             'topology_class': features[cell][1],
             'q_occupied': float(probability[cell[1], cell[0]]),
             'on_nominal_route': cell in route_set}
            for cell in ordered
        ],
        'rank_keys': {str(cell): keys[cell] for cell in ordered},
        'selection_counters': selection,
        'graph_operation_counts': counts,
        'graph_components': graph['component_count'],
        'graph_bridges': len(graph['bridges']),
        'graph_articulations': len(graph['articulation']),
        'stage_accounting_bounds': accounting,
        'stage_accounting': accounting_observed,
        'graph_analysis_ns': graph_analysis_ns,
        'nominal_astar_ns': nominal_astar_ns,
        'counterfactual_astar_ns': counterfactual_astar_ns,
        'counterfactual_astar_ns_total': sum(counterfactual_astar_ns),
        'scheduler_ns': scheduler_ns,
        'graph_vertices': v, 'graph_edges': e,
        'grid_cells_n': n, 'route_length_l': len(nominal or []),
        'candidate_count_m': len(candidates), 'candidate_limit_k': p.max_candidates,
    }
