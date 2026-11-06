import json
from pathlib import Path
import inspect
import numpy as np
import pytest
from spatial_memory.simulation import Scenario, World
from spatial_memory.observation import Sensor
from spatial_memory.memory import Memory, Baseline
from spatial_memory.navigation import plan
from spatial_memory.evaluation import map_errors, run_episode

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def config():
    return json.loads((ROOT/'configs/development.json').read_text())


@pytest.fixture
def scenario(config):
    return Scenario.from_dict(config['scenarios'][0])


def test_initialization(scenario):
    world = World(scenario)
    assert world.geometry().shape == (7, 11)
    assert world.geometry()[5, 7]
    assert not world.geometry()[3, 3]
    assert world.occupancy()[3, 3]
    assert not world.occupancy()[3, 1]


def test_dynamics(scenario):
    world = World(scenario)
    world.advance()
    assert (3, 3) in world.people()
    world.advance()
    assert (4, 3) in world.people()
    world.advance()
    assert world.geometry()[3, 6]
    for _ in range(3):
        world.advance()
    assert not world.geometry()[5, 7] and world.geometry()[5, 8]
    for _ in range(4):
        world.advance()
    assert not world.geometry()[3, 6]


def test_invalid_scenario(config):
    data = config['scenarios'][0]
    data['start'] = [100, 100]
    with pytest.raises(ValueError):
        Scenario.from_dict(data)


def test_range_occlusion_and_noise():
    occupancy = np.zeros((5, 6), bool)
    occupancy[2, 2] = True
    rng = lambda: np.random.default_rng(2)
    obs = Sensor(3, True).observe(occupancy, (1, 2), rng())
    assert obs[2, 2] == 1
    assert obs[2, 3] == -1
    assert obs[0, 5] == -1
    assert obs[2, 1] == 0
    clear = Sensor(3, False).observe(occupancy, (1, 2), rng())
    assert clear[2, 3] == 0
    noisy = Sensor(3, False, 1).observe(occupancy, (1, 2), rng())
    visible = clear >= 0
    np.testing.assert_array_equal(noisy[visible], 1-clear[visible])
    np.testing.assert_array_equal(noisy[~visible], -1)
    assert not obs.flags.writeable


def test_corner_occlusion():
    occupancy = np.zeros((4, 4), bool)
    occupancy[0, 1] = True
    obs = Sensor(4, True).observe(occupancy, (0, 0), np.random.default_rng(0))
    assert obs[1, 1] == -1


def test_memory_and_frozen_static():
    initial = np.array([[0, -1, 1]], dtype=np.int8)
    memory = Memory(initial.shape)
    memory.update(initial)
    initial[0, 0] = 1
    assert memory.grid[0, 0] == 0  # copy, not an alias
    memory.update(np.array([[-1, 0, 0]]))
    np.testing.assert_array_equal(memory.grid, [[0, 0, 0]])
    static = Baseline(initial.shape, initial, 'static', 2)
    periodic = Baseline(initial.shape, initial, 'periodic', 2)
    np.testing.assert_array_equal(static.memory.grid, periodic.memory.grid)
    assert not static.needs_observation(2)
    assert periodic.needs_observation(2)
    assert not periodic.needs_observation(1)
    with pytest.raises(ValueError):
        static.refresh(initial)


def test_planner():
    grid = np.zeros((3, 4), dtype=np.int8)
    grid[1, 1:3] = 1
    path = plan(grid, (0, 1), (3, 1))
    assert len(path) == 6
    assert all(grid[y, x] == 0 for x, y in path)
    unknown = np.array([[0, -1, 0]])
    assert len(plan(unknown, (0, 0), (2, 0))) == 3
    assert plan(unknown, (0, 0), (2, 0), 'blocked') == []
    assert plan(grid, (0, 0), (0, 0)) == [(0, 0)]


def test_collision_checker(scenario):
    world = World(scenario)
    assert world.move((2, 3), (3, 3)) == ((2, 3), 1)
    assert world.move((1, 3), (2, 3)) == ((2, 3), 0)
    assert world.move((0, 1), (-1, 1)) == ((0, 1), 1)


def test_metrics():
    memory = np.array([[1, -1, 0, 1]])
    truth = np.array([[False, True, True, True]])
    errors = map_errors(memory, truth, np.array([[False, True, True, False]]),
                        np.array([[True, False, False, False]]))
    assert errors == dict(stale_map_errors=2, false_persistent_occupancy_updates=1,
                          missed_persistent_changes=2)


def test_reproducibility_and_initial_fairness(scenario, config):
    a, af = run_episode(scenario, config, 'static', 7)
    b, bf = run_episode(scenario, config, 'static', 7)
    p, pf = run_episode(scenario, config, 'periodic', 7)
    assert a == b
    for x, y in zip(af, bf):
        np.testing.assert_array_equal(x['memory'], y['memory'])
        assert x['position'] == y['position']
    np.testing.assert_array_equal(af[0]['memory'], pf[0]['memory'])
    assert np.any(af[0]['memory'] == -1)
    assert all(np.array_equal(f['memory'], af[0]['memory']) for f in af)
    assert a['observation_count'] == 1
    assert p['observation_count'] == 1 + p['elapsed_steps']//config['update_interval']
    assert p['observation_cost'] == p['observation_count']*1.5
    assert a['travel_distance'] <= a['elapsed_steps']


def test_success_and_exact_steps(config):
    scenario = Scenario.from_dict(dict(name='empty', split='development', width=5,
        height=3, start=[0, 1], goal=[4, 1]))
    cfg = {**config, 'sensor': dict(radius=1, occlusion=False, noise=0)}
    metrics, _ = run_episode(scenario, cfg, 'static', 0)
    assert metrics['success']
    assert metrics['elapsed_steps'] == metrics['travel_distance'] == 4
    assert metrics['collision_count'] == 0
    assert metrics['stale_map_errors'] == 0


def test_ground_truth_boundary():
    # World never crosses the agent/planner boundary. Identical sensor outputs
    # from different hidden worlds must yield identical memory and action.
    from spatial_memory import memory, navigation
    assert 'simulation' not in inspect.getsource(memory)
    assert 'simulation' not in inspect.getsource(navigation)
    a = np.zeros((5, 8), bool)
    b = a.copy()
    b[4, 7] = True
    sensor = Sensor(1)
    observations = [sensor.observe(g, (0, 0), np.random.default_rng(0)) for g in (a, b)]
    np.testing.assert_array_equal(*observations)
    agents = [Baseline(a.shape, o, 'periodic', 2) for o in observations]
    assert plan(agents[0].memory.grid, (0, 0), (7, 4)) == plan(
        agents[1].memory.grid, (0, 0), (7, 4))
    assert set(inspect.signature(plan).parameters) == {'grid', 'start', 'goal', 'unknown'}


def test_noise_seed_reproducibility():
    sensor = Sensor(10, False, 0.3)
    grid = np.zeros((10, 10), bool)
    a = sensor.observe(grid, (5, 5), np.random.default_rng(1))
    b = sensor.observe(grid, (5, 5), np.random.default_rng(1))
    c = sensor.observe(grid, (5, 5), np.random.default_rng(2))
    np.testing.assert_array_equal(a, b)
    assert not np.array_equal(a, c)


def test_transient_write_attribution_and_removal(config):
    scenario = Scenario.from_dict(dict(name='transient', split='development', width=6,
        height=3, start=[0, 1], goal=[5, 1],
        pedestrians=[[[1, 1], [1, 2], [2, 2], [2, 1]]]))
    cfg = {**config, 'max_steps': 1, 'update_interval': 1,
           'sensor': dict(radius=5, occlusion=False, noise=0)}
    a, _ = run_episode(scenario, cfg, 'static', 0)
    b, _ = run_episode(scenario, cfg, 'periodic', 0)
    assert a['false_persistent_occupancy_updates'] == 1
    assert b['false_persistent_occupancy_updates'] == 0
    assert a['final_stale_map_errors'] == 1


def test_missed_change_unknown_and_reversion(config):
    scenario = Scenario.from_dict(dict(name='changes', split='development', width=6,
        height=3, start=[0, 1], goal=[5, 1],
        changes=[dict(step=1, action='add', cell=[4, 2]),
                 dict(step=2, action='remove', cell=[4, 2])]))
    cfg = {**config, 'max_steps': 2, 'sensor': dict(radius=1, occlusion=False, noise=0)}
    metrics, _ = run_episode(scenario, cfg, 'static', 0)
    assert metrics['missed_persistent_changes'] == 2  # unknown at both snapshots
    assert metrics['final_missed_persistent_changes'] == 1
    cfg['sensor']['radius'] = 10
    metrics, _ = run_episode(scenario, cfg, 'static', 0)
    assert metrics['missed_persistent_changes'] == 1
    assert metrics['final_missed_persistent_changes'] == 0


def test_dynamic_contact_counts(config):
    scenario = Scenario.from_dict(dict(name='contact', split='development', width=4,
        height=3, start=[0, 1], goal=[3, 1],
        changes=[dict(step=1, action='add', cell=[0, 1])]))
    cfg = {**config, 'max_steps': 1, 'sensor': dict(radius=5, occlusion=False, noise=0)}
    metrics, _ = run_episode(scenario, cfg, 'static', 0)
    assert metrics['collision_count'] == 1
    assert metrics['travel_distance'] == 1


def test_visualization_saves_png(tmp_path, scenario, config):
    from spatial_memory.visualization import save_figure
    _, frames = run_episode(scenario, config, 'periodic', 7)
    output = tmp_path / 'snapshot.png'
    save_figure(scenario, frames[4], output)
    assert output.read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
