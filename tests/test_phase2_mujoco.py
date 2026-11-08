import numpy as np

from spatial_memory.evaluation import run_episode
from spatial_memory.mujoco_navigation import MujocoNavigationScene
from spatial_memory.scheduling import ObservationController
from spatial_memory.simulation import Scenario, World, scenario_from_bprime


def open_scenario(*, changes=(), pedestrians=()):
    return Scenario.from_dict(dict(name='phase2-test', split='development', width=5, height=5,
        start=(1, 1), goal=(3, 3),
        walls=tuple((x, y) for x in range(5) for y in range(5)
                    if x in (0, 4) or y in (0, 4)),
        obstacles=(), pedestrians=pedestrians, changes=changes))


def test_grid_world_coordinate_roundtrip_and_spacing():
    scenario = open_scenario()
    scene = MujocoNavigationScene(scenario)
    for y in range(scenario.height):
        for x in range(scenario.width):
            assert scene.world_to_grid(scene.grid_to_world((x, y))) == (x, y)
    x0, _ = scene.grid_to_world((1, 1))
    x1, _ = scene.grid_to_world((2, 1))
    assert x1 - x0 == scene.cell_size


def test_persistent_event_updates_mujoco_geometry():
    scenario = open_scenario(changes=(dict(step=1, action='add', cell=(2, 2)),))
    scene = MujocoNavigationScene(scenario)
    world = World(scenario)
    mocap = scene._object_mocaps[(2, 2)]
    initial = dict(step=0, position=scenario.start, planned=[scenario.start], blocked=False)
    scene.update(world, initial)
    assert scene.data.mocap_pos[mocap, 2] < -999
    world.advance()
    after = dict(step=1, position=scenario.start, planned=[scenario.start], blocked=False)
    scene.update(world, after)
    assert scene.data.mocap_pos[mocap, 2] == 0
    assert scene.snapshot()['active_objects'] == [(2, 2)]
    overlap = dict(step=2, position=(2, 2), planned=[(2, 2)], blocked=False)
    contacts = scene.update(world, overlap)
    assert contacts['mujoco_pose_persistent_obstacle_contact_pairs'] > 0


def test_first_81_saved_pedestrian_positions_are_unchanged():
    positions = [(2, 2), (3, 2)] * 40 + [(2, 2)]
    payload = dict(mechanism='R', outcome='independent', partition='fit',
        identity='phase1.5-v0.4-BPRIME-1:fit:R:0',
        geometry=dict(width=5, height=5, free=[(x, y) for x in range(1, 4) for y in range(1, 4)]),
        world=dict(start=(1, 1), goal=(3, 3), schedules=[dict(initial=[], events=[], positions=positions)]*2))
    scenario = scenario_from_bprime(payload, 0)
    assert scenario.pedestrians[0][:81] == tuple(positions)
    assert all(abs(a[0]-b[0])+abs(a[1]-b[1]) <= 1
               for a, b in zip(scenario.pedestrians[0],
                               scenario.pedestrians[0][1:] + scenario.pedestrians[0][:1]))


def test_mujoco_episode_is_seed_reproducible_and_initial_observation_is_budgeted():
    scenario = open_scenario()
    config = dict(sensor=dict(radius=3, occlusion=True, noise=0.0), update_interval=4,
                  unknown='optimistic', max_steps=12, observation_cost=1,
                  max_observations=1)
    def execute():
        scene = MujocoNavigationScene(scenario)
        return run_episode(scenario, config, 'periodic', seed=42, _frame_callback=scene.update)
    first, first_frames = execute()
    second, second_frames = execute()
    assert first == second
    assert first['observation_count'] == 1
    assert first['max_observations'] == 1
    assert [frame['position'] for frame in first_frames] == [frame['position'] for frame in second_frames]
    assert first['travel_distance'] > 0


def test_evaluator_truth_callback_is_not_passed_to_policy():
    scenario = open_scenario(pedestrians=(((2, 1), (2, 2)),))
    received = []
    truth_frames = []
    config = dict(sensor=dict(radius=3, occlusion=True, noise=0.0), update_interval=4,
                  unknown='optimistic', max_steps=3, observation_cost=1,
                  max_observations=1)
    def factory(initial, method, **kwargs):
        assert isinstance(initial, np.ndarray)
        assert not hasattr(initial, 'scenario')
        received.append((initial.copy(), method))
        return ObservationController(initial, method, **kwargs)
    def evaluator_only_callback(world, frame):
        truth_frames.append((world.step, tuple(sorted(world.people())), frame['position']))
        return {'evaluator_truth_marker': len(truth_frames)}
    metrics, frames = run_episode(scenario, config, 'static', seed=42,
        _controller_factory=factory, _frame_callback=evaluator_only_callback)
    assert received and len(truth_frames) == len(frames)
    assert 'evaluator_truth_marker' in frames[-1]
    assert not hasattr(ObservationController(np.zeros((2, 2), dtype=np.int8), 'static'), 'scenario')
