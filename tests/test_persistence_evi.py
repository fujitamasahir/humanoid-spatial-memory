import math
import numpy as np
import pytest
from spatial_memory.persistence import PersistenceMemory, calibration_summary
from spatial_memory.evi import (PersistenceEVIController, visible_cells,
                                information_value)

SENSOR = dict(range_m=6., cell_size=1., horizontal_fov_deg=120., ray_count=61)


def test_transient_and_persistent_observed_history():
    m = PersistenceMemory(np.array([[0, 1, -1]]))
    m.update(np.array([[1, 1, -1]]), 2)
    m.update(np.array([[0, 1, -1]]), 4)
    assert m.transitions[:, 0, 0].tolist() == [1, 1]
    assert m.transitions[:, 0, 1].tolist() == [0, 0]
    assert m.rates()[1, 0, 0] > m.rates()[1, 0, 1]
    assert m.persistence_confidence()[0, 1] > m.persistence_confidence()[0, 0]
    assert m.grid[0, 0] == 0  # disappearance adapts on authorized free reading
    assert m.grid[0, 1] == 1
    assert m.grid[0, 2] == -1


def test_inference_never_updates_evidence_or_paid_counts():
    m = PersistenceMemory(np.array([[0, 1, -1]]))
    timestamps, transitions, exposure = m.last_observed.copy(), m.transitions.copy(), m.exposure.copy()
    m.infer(100)
    np.testing.assert_array_equal(m.last_observed, timestamps)
    np.testing.assert_array_equal(m.transitions, transitions)
    np.testing.assert_array_equal(m.exposure, exposure)
    assert m.observed_updates == 1
    assert m.grid.tolist() == [[0, 0, -1]]
    assert m.inference_log[-1]['changed_cells'] == 1
    assert m.probabilities(100)[0, 2] == .5


def test_asymmetric_rates_exposure_uses_previous_state():
    m = PersistenceMemory(np.array([[0]]))
    m.update(np.array([[1]]), 10)
    assert m.exposure[:, 0, 0].tolist() == [10., 0.]
    assert m.transitions[:, 0, 0].tolist() == [1, 0]
    m.update(np.array([[1]]), 20)
    assert m.exposure[:, 0, 0].tolist() == [10., 10.]
    assert m.probabilities(20)[0, 0] == pytest.approx(.95)
    assert calibration_summary(m.calibration)['samples'] == 2


def test_invalid_update_atomic_and_time_monotonic():
    m = PersistenceMemory(np.array([[0]]))
    with pytest.raises(ValueError):
        m.update(np.array([[2]]), 1)
    assert m.observed_updates == 1
    m.infer(2)
    with pytest.raises(ValueError):
        m.infer(1)


def test_fov_range_and_remembered_occlusion():
    grid = np.zeros((11, 11), dtype=np.int8)
    grid[5, 6] = 1
    cells = visible_cells(grid, (5, 5), 0., **SENSOR)
    assert (6, 5) in cells and (7, 5) not in cells
    assert (4, 5) not in cells
    assert (5, 10) not in cells
    grid[5, 6] = -1
    assert (7, 5) in visible_cells(grid, (5, 5), 0., **SENSOR)
    assert (4, 5) in visible_cells(grid, (5, 5), math.pi, **SENSOR)


def test_information_requires_navigation_consequence_and_bounded_plans():
    grid = np.zeros((5, 7), dtype=np.int8)
    grid[1:4, 2] = 1
    grid[2, 2] = 0
    prob = np.zeros(grid.shape)
    prob[2, 2] = .5
    result = information_value(grid, prob, (1, 2), (5, 2), 0., 'optimistic', SENSOR, 19)
    assert result['value'] > 0 and result['net_value'] > 0
    assert result['plan_calls'] <= 7
    prob[:] = 0
    prob[0, 0] = .5  # behind, outside FOV, no route relevance
    result = information_value(grid, prob, (1, 2), (5, 2), 0., 'optimistic', SENSOR, 19)
    assert result['net_value'] < 0


@pytest.mark.parametrize('b,c', [(True, False), (False, True), (True, True)])
def test_components_budget_and_authorized_refresh(b, c):
    initial = np.zeros((5, 7), dtype=np.int8)
    agent = PersistenceEVIController(initial, 'age', persistence=b, evi=c,
        max_observations=1, sensor=SENSOR)
    agent.set_navigation_context(goal=(5, 2), yaw=0., unknown='optimistic')
    for step in (1, 4, 8):
        assert not agent.decide(step, (1, 2))['observation_granted']
    assert agent.used == 1
    with pytest.raises(RuntimeError):
        agent.refresh(initial, 8)


def test_b_only_exact_age_schedule():
    from spatial_memory.scheduling import ObservationController
    initial = np.zeros((5, 7), dtype=np.int8)
    old = ObservationController(initial, 'age', max_observations=20)
    new = PersistenceEVIController(initial, 'age', evi=False, max_observations=20)
    for step in range(1, 20):
        a, b = old.decide(step, (2, 2)), new.decide(step, (2, 2))
        assert a['observation_granted'] == b['observation_granted']
        if a['observation_granted']:
            old.refresh(initial, step)
            new.refresh(initial, step)
    assert old.used == new.used


def test_controller_has_no_hidden_truth_dependency():
    import ast
    from pathlib import Path
    path = Path(__file__).parents[1]/'src/spatial_memory/evi.py'
    tree = ast.parse(path.read_text())
    imports = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    assert set(imports) <= {'dataclasses', 'time', 'navigation', 'scheduling', 'persistence'}
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            assert node.attr not in {'occupancy', 'geometry', 'people', 'observe', 'scan', 'check_move', 'check_turn'}


def test_unknown_cells_can_change_a_route_and_request_a_scan():
    grid = np.zeros((5, 7), dtype=np.int8)
    grid[1:4, 2] = 1
    grid[2, 2] = -1
    probability = np.zeros(grid.shape)
    probability[2, 2] = .5
    score = information_value(grid, probability, (1, 2), (5, 2), 0.,
                              'optimistic', SENSOR, 19)
    assert score['cell'] == (2, 2)
    assert score['net_value'] > 0
    stable = information_value(grid, np.zeros(grid.shape), (1, 2), (5, 2), 0.,
                               'optimistic', SENSOR, 19)
    assert stable['value'] == 0


def test_no_route_unknown_blocked_is_finite():
    grid = np.full((5, 7), -1, dtype=np.int8)
    result = information_value(grid, np.full(grid.shape, .5), (1, 2), (5, 2), 0.,
                               'blocked', SENSOR, 19)
    assert np.isfinite(result['net_value'])
    assert result['plan_calls'] <= 7


def test_uncertainty_without_action_change_postpones():
    grid = np.ones((3, 8), dtype=np.int8)
    grid[1, :] = 0
    probability = np.zeros(grid.shape)
    probability[1, 5] = .5
    result = information_value(grid, probability, (1, 1), (7, 1), 0.,
                              'optimistic', SENSOR, 19)
    assert result['value'] > 0
    # The occupied outcome has no route; it changes the immediate action to wait.
    assert result['delay_regret'] > 0
    grid = np.zeros((5, 8), dtype=np.int8)
    probability = np.zeros(grid.shape)
    probability[2, 5] = .5
    result = information_value(grid, probability, (1, 2), (7, 2), 0.,
                              'optimistic', SENSOR, 19)
    # Both route hypotheses initially move east: sensing can wait.
    assert result['value'] > 0
    assert result['delay_regret'] == 0
    assert result['net_value'] < 0


def test_c_controller_authorizes_one_real_refresh_then_consumes_grant():
    initial = np.zeros((5, 7), dtype=np.int8)
    initial[1:4, 2] = 1
    initial[2, 2] = -1
    agent = PersistenceEVIController(initial, 'age', persistence=False,
                                     max_observations=20, sensor=SENSOR)
    agent.set_navigation_context(goal=(5, 2), yaw=0., unknown='optimistic')
    decision = agent.decide(1, (1, 2))
    assert decision['observation_granted']
    assert agent.used == 1  # a grant is not yet a sensor reading
    with pytest.raises(RuntimeError, match='consumed'):
        agent.decide(2, (1, 2))
    observed = initial.copy()
    observed[2, 2] = 0
    agent.refresh(observed, 1)
    assert agent.used == 2
    assert agent.observation_log[0]['predicted_value'] > 0
    assert agent.observation_log[0]['observed_candidate_outcome'] == 0
    with pytest.raises(RuntimeError, match='Unauthorized'):
        agent.refresh(observed, 1)


def test_scarce_budget_can_defer_same_navigation_information():
    grid = np.zeros((5, 7), dtype=np.int8)
    grid[1:4, 2] = 1
    grid[2, 2] = -1
    probability = np.zeros(grid.shape)
    probability[2, 2] = .5
    enough = information_value(grid, probability, (1, 2), (5, 2), 0.,
                               'optimistic', SENSOR, 19)
    scarce = information_value(grid, probability, (1, 2), (5, 2), 0.,
                               'optimistic', SENSOR, 1)
    assert enough['net_value'] > 0 > scarce['net_value']
    assert enough['value'] == scarce['value']
