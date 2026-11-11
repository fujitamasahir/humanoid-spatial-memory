import numpy as np
import inspect

from spatial_memory.rdao import (RDAOController, RDAOParameters, action_cost,
    predicted_cell_visibility, route_positions)


def _agent(grid, **kwargs):
    return RDAOController(grid, goal=(7, 4), max_observations=20,
        local_extents=(0.0, 0.0), cell_size_m=.75, **kwargs)


def test_visibility_respects_orientation_range_and_fov():
    grid = np.zeros((9, 9), dtype=np.int8)
    east = predicted_cell_visibility(grid, (4, 4), 0.0, (7, 4),
        cell_size_m=.75, range_m=6, horizontal_fov_deg=120, ray_count=61)
    west = predicted_cell_visibility(grid, (4, 4), 0.0, (1, 4),
        cell_size_m=.75, range_m=6, horizontal_fov_deg=120, ray_count=61)
    too_far = predicted_cell_visibility(grid, (4, 4), 0.0, (8, 4),
        cell_size_m=.75, range_m=2, horizontal_fov_deg=120, ray_count=61)
    assert east == 1.0
    assert west == 0.0
    assert too_far == 0.0


def test_unknown_and_occupied_remembered_cells_reduce_or_block_visibility():
    grid = np.zeros((9, 9), dtype=np.int8)
    open_visibility = predicted_cell_visibility(grid, (1, 4), 0.0, (6, 4),
        cell_size_m=.75, range_m=6, horizontal_fov_deg=120, ray_count=61)
    grid[4, 3] = -1
    unknown_visibility = predicted_cell_visibility(grid, (1, 4), 0.0, (6, 4),
        cell_size_m=.75, range_m=6, horizontal_fov_deg=120, ray_count=61)
    grid[4, 3] = 1
    occupied_visibility = predicted_cell_visibility(grid, (1, 4), 0.0, (6, 4),
        cell_size_m=.75, range_m=6, horizontal_fov_deg=120, ray_count=61)
    assert open_visibility == 1.0
    assert 0 < unknown_visibility < open_visibility
    assert occupied_visibility == 0.0


def test_counterfactual_route_relevance_triggers_before_critical_unknown_corridor():
    grid = np.zeros((9, 9), dtype=np.int8)
    grid[4, 3] = -1
    agent = _agent(grid)
    agent.episode_id = 'synthetic'
    agent.set_context(1, (1, 4), 0.0, frozenset())
    original = agent.memory.grid.copy()
    result = agent.decide(1, (1, 4))
    assert result['observation_requested'] is True
    assert result['observation_granted'] is True
    diag = result['rdao']
    assert diag['uncertainty'] > 0
    assert diag['predicted_visibility'] > 0
    assert diag['route_relevance'] > 0
    assert diag['score'] >= diag['threshold']
    assert np.array_equal(agent.memory.grid, original)
    assert not agent.blocked_actions


def test_observation_refresh_logs_visible_mask_memory_diff_and_replanned_route():
    grid = np.zeros((9, 9), dtype=np.int8)
    grid[4, 3] = -1
    agent = _agent(grid)
    agent.set_context(1, (1, 4), 0.0, frozenset())
    decision = agent.decide(1, (1, 4))
    received = np.full(grid.shape, -1, dtype=np.int8)
    received[4, 3] = 0
    agent.note_observation_duration(1, 12345)
    agent.refresh(received, 1)
    effect = decision['rdao']['observation_effect']
    assert decision['rdao']['observation_time_ns'] == 12345
    assert effect['visible_cell_count'] == 1
    assert effect['memory_changed_cells'] == [{'cell': [3, 4], 'before': -1, 'after': 0}]
    assert effect['route_before'] is not None and effect['route_after'] is not None
    assert agent.last_observed[4, 3] == 1
    assert agent.used == 2


def test_budget_exhaustion_fails_closed_and_records_denial():
    grid = np.zeros((9, 9), dtype=np.int8)
    grid[4, 3] = -1
    agent = RDAOController(grid, goal=(7, 4), max_observations=1,
        local_extents=(0.0, 0.0), cell_size_m=.75)
    agent.set_context(1, (1, 4), 0.0, frozenset())
    result = agent.decide(1, (1, 4))
    assert result['observation_requested'] is True
    assert result['observation_granted'] is False
    assert result['rdao']['reason'] == 'observation_budget_exhausted'
    assert agent.denied == 1


def test_deterministic_scores_and_side_effect_free_g1_planning():
    grid = np.zeros((9, 9), dtype=np.int8)
    grid[4, 3] = -1
    first, second = _agent(grid), _agent(grid)
    for agent in (first, second):
        agent.set_context(1, (1, 4), 0.0, frozenset())
    before = grid.copy()
    a, b = first.decide(1, (1, 4))['rdao'], second.decide(1, (1, 4))['rdao']
    for key in ('nominal_route', 'candidate_regions', 'route_relevance', 'uncertainty',
                'predicted_visibility', 'decision_impact', 'timing', 'score', 'threshold',
                'requested', 'granted', 'reason'):
        assert a[key] == b[key]
    assert np.array_equal(grid, before)
    assert np.array_equal(first.memory.grid, before)


def test_ablation_switches_are_separate_and_timing_component_is_logged():
    grid = np.zeros((12, 9), dtype=np.int8)
    grid[4, 3] = -1
    full = _agent(grid)
    no_timing = _agent(grid, use_timing=False)
    no_visibility = _agent(grid, use_visibility=False)
    for item in (full, no_timing, no_visibility):
        item.set_context(1, (1, 4), 0.0, frozenset())
    full_diag = full.decide(1, (1, 4))['rdao']
    timing_diag = no_timing.decide(1, (1, 4))['rdao']
    visibility_diag = no_visibility.decide(1, (1, 4))['rdao']
    assert full_diag['timing'] <= 1.0
    assert timing_diag['timing'] == 1.0
    assert visibility_diag['predicted_visibility'] == 1.0


def test_g1_action_cost_and_route_position_accounting_include_turns():
    route = [('turn', 1), ('move', (1, 2)), ('turn', 2)]
    assert action_cost(route) == 1.5
    assert route_positions((1, 1), route) == [(1, 1), (1, 1), (1, 2), (1, 2)]


def test_controller_interface_has_no_simulator_or_future_state_input():
    parameters = set(inspect.signature(RDAOController.__init__).parameters)
    assert not parameters.intersection({'world', 'scenario', 'true_occupancy',
        'future_pedestrians', 'change_schedule', 'evaluator_labels'})


def test_new_observation_feedback_releases_only_changed_local_blocked_action():
    grid = np.zeros((9, 9), dtype=np.int8)
    grid[4, 2] = 1
    agent = _agent(grid)
    agent.record_blocked_action((1, 4), 0, ('move', (2, 4)))
    assert agent.blocked_actions
    received = np.full(grid.shape, -1, dtype=np.int8)
    received[4, 2] = 0
    agent.refresh(received, 1)
    assert not agent.blocked_actions
    assert agent.memory.grid[4, 2] == 0

