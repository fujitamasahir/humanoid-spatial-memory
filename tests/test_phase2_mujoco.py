import numpy as np

from spatial_memory.evaluation import run_episode
from spatial_memory.mujoco_navigation import MujocoNavigationScene
from spatial_memory.simulation import Scenario, World, scenario_from_bprime


def open_scenario(*, obstacles=(), changes=(), pedestrians=()):
    return Scenario.from_dict(dict(name='phase2-g1-test', split='development', width=5, height=5,
        start=(1, 1), goal=(3, 3),
        walls=tuple((x, y) for x in range(5) for y in range(5)
                    if x in (0, 4) or y in (0, 4)),
        obstacles=obstacles, pedestrians=pedestrians, changes=changes))


def test_actual_g1_stand_keyframe_and_floating_base_are_loaded():
    scene = MujocoNavigationScene(open_scenario())
    assert scene.model.nq == 36
    assert scene.stand_key_id >= 0
    assert np.allclose(scene._stand_root, [0, 0, 0.79, 1, 0, 0, 0])
    assert scene.robot_qpos_adr == 0
    scene.update(World(scene.scenario), dict(step=0, position=(1, 1), planned=[(1, 1)], blocked=False))
    assert scene.world_to_grid(scene.data.qpos[:2]) == (1, 1)


def test_intended_foot_floor_contacts_are_separated_from_unwanted_contacts():
    scenario = open_scenario()
    scene = MujocoNavigationScene(scenario)
    counts = scene.update(World(scenario), dict(step=0, position=scenario.start,
        planned=[scenario.start], blocked=False))
    assert counts['g1_foot_floor_contact_pairs'] == 8
    assert counts['g1_unwanted_floor_contact_pairs'] == 0
    assert counts['g1_wall_contact_pairs'] == 0


def test_actual_g1_collision_geometry_blocks_persistent_obstacle_intersection():
    scenario = open_scenario(obstacles=((2, 1),))
    scene = MujocoNavigationScene(scenario)
    blocked, counts = scene.check_move(World(scenario), scenario.start, (2, 1))
    assert blocked
    assert counts.persistent_obstacle > 0


def test_evaluator_rejects_a_target_when_the_actual_g1_intersects_an_obstacle():
    scenario = open_scenario(obstacles=((2, 1),))
    scene = MujocoNavigationScene(scenario)
    config = dict(sensor=dict(radius=3, occlusion=True, noise=0.0), update_interval=4,
                  unknown='optimistic', max_steps=1, observation_cost=1,
                  max_observations=1)
    forced_plan = lambda grid, start, goal, unknown: [start, (2, 1), goal]
    metrics, frames = run_episode(scenario, config, 'static', seed=42,
        _planner=forced_plan, _frame_callback=scene.update,
        _movement_checker=lambda world, current, target: scene.check_move(world, current, target))
    assert frames[-1]['position'] == scenario.start
    assert frames[-1]['footprint_blocked']
    assert metrics['g1_footprint_blocked_attempts'] == 1
    assert metrics['g1_unwanted_contact_pairs'] == 0


def test_mocap_tracks_persistent_obstacle_change_without_regeneration():
    scenario = open_scenario(changes=(dict(step=1, action='add', cell=(2, 2)),))
    scene = MujocoNavigationScene(scenario)
    world = World(scenario)
    mocap = scene._object_mocaps[(2, 2)]
    scene.update(world, dict(step=0, position=scenario.start, planned=[scenario.start], blocked=False))
    assert scene.data.mocap_pos[mocap, 2] < -999
    world.advance()
    scene.update(world, dict(step=1, position=scenario.start, planned=[scenario.start], blocked=False))
    assert scene.data.mocap_pos[mocap, 2] == 0


def test_prescribed_pedestrian_mocap_tracks_existing_scenario_trace():
    scenario = open_scenario(pedestrians=(((2, 1), (2, 2)),))
    scene = MujocoNavigationScene(scenario)
    world = World(scenario)
    mocap = scene.pedestrian_mocaps[0]
    scene.update(world, dict(step=0, position=scenario.start, planned=[scenario.start], blocked=False))
    first = scene.data.mocap_pos[mocap].copy()
    world.advance()
    scene.update(world, dict(step=1, position=scenario.start, planned=[scenario.start], blocked=False))
    second = scene.data.mocap_pos[mocap].copy()
    assert not np.array_equal(first, second)
    assert scene.snapshot()['pedestrians'] == [(2, 2)]


def test_existing_fit_adapter_keeps_original_pedestrian_samples():
    positions = [(2, 2), (3, 2)]*40 + [(2, 2)]
    payload = dict(mechanism='R', outcome='independent', partition='fit',
        identity='phase1.5-v0.4-BPRIME-1:fit:R:0',
        geometry=dict(width=5, height=5, free=[(x, y) for x in range(1, 4) for y in range(1, 4)]),
        world=dict(start=(1, 1), goal=(3, 3), schedules=[
            dict(initial=[], events=[], positions=positions)]*2))
    scenario = scenario_from_bprime(payload, 0)
    assert scenario.pedestrians[0][:81] == tuple(positions)


def test_grid_coordinate_roundtrip_preserves_documented_scale():
    scene = MujocoNavigationScene(open_scenario())
    for y in range(scene.scenario.height):
        for x in range(scene.scenario.width):
            assert scene.world_to_grid(scene.grid_to_world((x, y))) == (x, y)
    assert scene.grid_to_world((2, 1))[0] - scene.grid_to_world((1, 1))[0] == 0.75


def test_kinematic_run_with_movement_gate_has_no_unwanted_contacts():
    scenario = open_scenario()
    config = dict(sensor=dict(radius=3, occlusion=True, noise=0.0), update_interval=4,
                  unknown='optimistic', max_steps=12, observation_cost=1,
                  max_observations=1)
    scene = MujocoNavigationScene(scenario)
    metrics, frames = run_episode(scenario, config, 'periodic', seed=42,
        _frame_callback=scene.update,
        _movement_checker=lambda world, current, target: scene.check_move(world, current, target))
    assert metrics['travel_distance'] > 0
    assert all(sum(frame.get(key, 0) for key in ('g1_unwanted_floor_contact_pairs',
        'g1_pedestrian_contact_pairs', 'g1_wall_contact_pairs',
        'g1_persistent_obstacle_contact_pairs', 'g1_self_contact_pairs')) == 0
        for frame in frames)
