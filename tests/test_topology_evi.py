import numpy as np

from spatial_memory.topology_evi import (
    analyze_public_topology, _candidate_topology_features,
    information_value_topology, exhaustive_public_values,
)


def grid_open(h=9, w=11):
    grid = np.zeros((h, w), dtype=np.int8)
    grid[[0, -1], :] = 1
    grid[:, [0, -1]] = 1
    return grid


def test_tarjan_marks_only_start_goal_separating_articulation():
    grid = np.ones((9, 11), dtype=np.int8)
    grid[4, 1:10] = 0
    grid[4, 5] = -1
    # A side branch T junction is an articulation, but does not separate s/t.
    grid[3, 4] = grid[2, 4] = grid[2, 3] = grid[2, 5] = -1
    result = analyze_public_topology(grid, (2, 4), (8, 4))
    assert (5, 4) in result['separating']
    assert (4, 2) in result['articulation']
    assert (4, 2) not in result['separating']
    assert result['operations'] <= 20*(result['vertices']+result['edges'])


def test_currently_occupied_cell_can_be_ranked_as_shortcut():
    grid = grid_open()
    grid[3, 4:8] = 1
    grid[5, 4:8] = 1
    grid[4, 6] = 1
    graph = analyze_public_topology(grid, (2, 4), (8, 4))
    feature, label = _candidate_topology_features(grid, (6, 4), graph, (2, 4), (8, 4))
    assert feature[0] == 1
    assert label in {'occupied_connectivity_shortcut', 'occupied_distance_shortcut'}


def test_topology_evi_keeps_original_call_cap_and_reports_graph_cost():
    grid = grid_open(15, 15)
    probability = np.full(grid.shape, .01)
    for x in range(3, 12):
        probability[7, x] = .5
        grid[7, x] = -1
    result = information_value_topology(grid, probability, (2, 7), (12, 7),
        0., 'optimistic', {'range_m': 6., 'cell_size': .75,
        'horizontal_fov_deg': 120., 'ray_count': 61}, 10)
    assert result['plan_calls'] <= 7
    assert result['graph_analysis_ns'] >= 0
    assert result['graph_operation_count'] <= result['graph_work_bound']
    assert len(result['shortlisted_candidates']) <= 3


def test_exhaustive_reference_is_public_value_only():
    grid = grid_open()
    probability = np.full(grid.shape, .01)
    grid[4, 4] = -1
    probability[4, 4] = .5
    rows, common_cost, calls = exhaustive_public_values(grid, probability,
        (2, 4), (8, 4), 'optimistic', [(4, 4)])
    assert len(rows) == 1 and rows[0]['cell'] == (4, 4)
    assert common_cost > 0 and calls == 3
