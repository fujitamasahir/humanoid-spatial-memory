import numpy as np

from spatial_memory.evaluation import run_episode
from spatial_memory.mujoco_navigation import (ContactCounts, MujocoNavigationScene,
    desired_heading, yaw_quaternion)
from spatial_memory.mujoco_perception import MujocoRayPerception
from spatial_memory.scheduling import ObservationController
from spatial_memory.simulation import Scenario, World, scenario_from_bprime


def open_scenario(*, obstacles=(), changes=(), pedestrians=()):
    return Scenario.from_dict(dict(name='phase2-g1-test', split='development', width=5, height=5,
        start=(1, 1), goal=(3, 3),
        walls=tuple((x, y) for x in range(5) for y in range(5)
                    if x in (0, 4) or y in (0, 4)),
        obstacles=obstacles, pedestrians=pedestrians, changes=changes))


def ray_scenario(*, width=9, height=7, start=(1, 3), goal=(7, 3),
                 obstacles=(), changes=(), pedestrians=(), extra_walls=()):
    walls = {(x, y) for x in range(width) for y in range(height)
             if x in (0, width-1) or y in (0, height-1)}
    walls.update(extra_walls)
    return Scenario.from_dict(dict(name='phase2-g1-ray-test', split='development',
        width=width, height=height, start=start, goal=goal, walls=tuple(walls),
        obstacles=obstacles, changes=changes, pedestrians=pedestrians))


def test_actual_g1_stand_keyframe_and_floating_base_are_loaded():
    scene = MujocoNavigationScene(open_scenario())
    assert scene.model.nq == 36
    assert scene.stand_key_id >= 0
    assert np.allclose(scene._stand_root, [0, 0, 0.79, 1, 0, 0, 0])
    assert scene.robot_qpos_adr == 0
    scene.update(World(scene.scenario), dict(step=0, position=(1, 1), planned=[(1, 1)], blocked=False))
    assert scene.world_to_grid(scene.data.qpos[:2]) == (1, 1)


def test_forward_axis_quaternion_and_heading_for_all_cardinal_directions():
    import math
    scenario = open_scenario()
    scene = MujocoNavigationScene(scenario)
    start = scenario.start
    for delta, expected in (((1, 0), 0.0), ((0, 1), math.pi/2),
                            ((-1, 0), math.pi), ((0, -1), -math.pi/2)):
        target = start[0]+delta[0], start[1]+delta[1]
        yaw = desired_heading(start, target, scene.cell_size)
        assert math.isclose(math.atan2(math.sin(yaw-expected), math.cos(yaw-expected)), 0.0, abs_tol=1e-9)
        scene._set_pose(start, yaw)
        scene.mj.mj_forward(scene.model, scene.data)
        forward = scene.data.site_xmat[scene.sensor_site_id].reshape(3, 3) @ np.array([1., 0., 0.])
        assert np.allclose(forward[:2], delta, atol=1e-9)
        assert np.allclose(scene.data.qpos[3:7], yaw_quaternion(yaw))


def test_stationary_move_keeps_the_previous_heading():
    scene = MujocoNavigationScene(open_scenario())
    old_yaw = 1.1
    blocked, _, result_yaw, reason = scene.check_move(World(scene.scenario),
        scene.scenario.start, scene.scenario.start, old_yaw)
    assert not blocked and result_yaw == old_yaw and reason is None


def test_rotation_sweep_rejects_an_intermediate_collision_and_restores_pose():
    scenario = open_scenario()
    scene = MujocoNavigationScene(scenario)
    scene._set_pose(scenario.start, 0.0)
    original = scene.data.qpos[scene.robot_qpos_adr:scene.robot_qpos_adr+7].copy()
    checks = []
    def synthetic_contact():
        q = scene.data.qpos[scene.robot_qpos_adr+3:scene.robot_qpos_adr+7]
        yaw = 2*np.arctan2(q[3], q[0])
        checks.append(yaw)
        return ContactCounts(wall=1) if 0.25 < yaw < 0.45 else ContactCounts()
    scene._contacts = synthetic_contact
    blocked, counts, next_yaw, reason = scene.check_move(World(scenario),
        scenario.start, (scenario.start[0], scenario.start[1]+1), 0.0)
    assert blocked and counts.wall == 1
    assert reason == 'rotation_collision' and next_yaw == 0.0
    assert len(checks) >= 5
    assert np.allclose(scene.data.qpos[scene.robot_qpos_adr:scene.robot_qpos_adr+7], original)


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
    blocked, counts, next_yaw, reason = scene.check_move(World(scenario), scenario.start, (2, 1), 0.0)
    assert blocked
    assert counts.persistent_obstacle > 0
    assert next_yaw == 0.0
    assert reason == 'translation_collision'


def test_evaluator_rejects_a_target_when_the_actual_g1_intersects_an_obstacle():
    scenario = open_scenario(obstacles=((2, 1),))
    scene = MujocoNavigationScene(scenario)
    config = dict(sensor=dict(radius=3, occlusion=True, noise=0.0), update_interval=4,
                  unknown='optimistic', max_steps=1, observation_cost=1,
                  max_observations=1)
    forced_plan = lambda grid, start, goal, unknown: [start, (2, 1), goal]
    metrics, frames = run_episode(scenario, config, 'static', seed=42,
        _planner=forced_plan, _frame_callback=scene.update,
        _movement_checker=lambda world, current, target, yaw: scene.check_move(world, current, target, yaw))
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
        _movement_checker=lambda world, current, target, yaw: scene.check_move(world, current, target, yaw))
    assert metrics['travel_distance'] > 0
    assert all(sum(frame.get(key, 0) for key in ('g1_unwanted_floor_contact_pairs',
        'g1_pedestrian_contact_pairs', 'g1_wall_contact_pairs',
        'g1_persistent_obstacle_contact_pairs', 'g1_self_contact_pairs')) == 0
        for frame in frames)


def test_mujoco_ray_sensor_detects_a_visible_obstacle_as_occupied():
    scenario = ray_scenario(obstacles=((4, 3),))
    scene = MujocoNavigationScene(scenario)
    sensor = MujocoRayPerception(scene)
    observation = sensor.observe(World(scenario), scenario.start, 0.0)
    assert observation[3, 4] == 1
    assert sensor.last_stats['hits_by_type']['persistent_obstacles'] > 0
    assert sensor.last_stats['sensor_height_m'] < 0.9


def test_mujoco_rays_respect_occlusion_behind_a_wall():
    divider = tuple((3, y) for y in range(1, 6))
    scenario = ray_scenario(obstacles=((5, 3),), extra_walls=divider)
    sensor = MujocoRayPerception(MujocoNavigationScene(scenario))
    observation = sensor.observe(World(scenario), scenario.start, 0.0)
    assert observation[3, 3] == 1
    assert observation[3, 5] == -1
    assert sensor.last_stats['hits_by_type']['persistent_obstacles'] == 0


def test_cells_outside_the_sensor_visibility_remain_unknown():
    scenario = ray_scenario(width=15, height=11, start=(1, 5), goal=(13, 5))
    sensor = MujocoRayPerception(MujocoNavigationScene(scenario))
    observation = sensor.observe(World(scenario), scenario.start, 0.0)
    assert observation[9, 13] == -1
    assert np.any(observation == 0)


def test_ray_measurements_change_with_robot_heading():
    scenario = ray_scenario(obstacles=((4, 3),))
    sensor = MujocoRayPerception(MujocoNavigationScene(scenario))
    world = World(scenario)
    east = sensor.observe(world, scenario.start, 0.0)
    west = sensor.observe(world, scenario.start, np.pi)
    assert east[3, 4] == 1
    assert west[3, 4] == -1
    assert not np.array_equal(east, west)


def test_moving_pedestrian_is_measured_at_its_current_geometry_only():
    scenario = ray_scenario(pedestrians=(((3, 3), (3, 2)),))
    scene, world = MujocoNavigationScene(scenario), World(scenario)
    sensor = MujocoRayPerception(scene)
    first = sensor.observe(world, scenario.start, 0.0)
    assert first[3, 3] == 1
    assert sensor.last_stats['hits_by_type']['pedestrians'] > 0
    world.advance()
    second = sensor.observe(world, scenario.start, 0.0)
    assert second[2, 3] == 1
    assert second[3, 3] == 0


def test_persistent_obstacle_geometry_appears_and_disappears_in_rays():
    scenario = ray_scenario(changes=(
        dict(step=1, action='add', cell=(3, 3)),
        dict(step=2, action='remove', cell=(3, 3))))
    world, sensor = World(scenario), MujocoRayPerception(MujocoNavigationScene(scenario))
    before = sensor.observe(world, scenario.start, 0.0)
    world.advance()
    present = sensor.observe(world, scenario.start, 0.0)
    world.advance()
    removed = sensor.observe(world, scenario.start, 0.0)
    assert before[3, 3] == 0
    assert present[3, 3] == 1
    assert removed[3, 3] == 0


def test_3d_observations_are_deterministic_for_fixed_geometry_and_heading():
    scenario = ray_scenario(obstacles=((4, 3),), pedestrians=(((3, 3), (3, 2)),))
    sensor = MujocoRayPerception(MujocoNavigationScene(scenario))
    first = sensor.observe(World(scenario), scenario.start, 0.0)
    second = sensor.observe(World(scenario), scenario.start, 0.0)
    assert np.array_equal(first, second)
    assert sensor.last_stats['ray_count'] == 61


def test_3d_sensor_updates_memory_without_passing_truth_to_policy_and_respects_budget():
    scenario = ray_scenario(obstacles=((4, 3),))
    scene = MujocoNavigationScene(scenario)
    sensor = MujocoRayPerception(scene)
    seen = []
    config = dict(sensor=dict(radius=3, occlusion=True, noise=0.0), update_interval=1,
                  unknown='optimistic', max_steps=4, observation_cost=1,
                  max_observations=1)
    def controller_factory(initial, method, **kwargs):
        assert isinstance(initial, np.ndarray)
        assert not isinstance(initial, World)
        seen.append(initial.copy())
        return ObservationController(initial, method, **kwargs)
    metrics, frames = run_episode(scenario, config, 'periodic', seed=23,
        _controller_factory=controller_factory, _observation_provider=sensor.observe)
    assert len(seen) == 1
    assert metrics['observation_count'] == 1
    assert metrics['observation_requests_denied'] > 0
    assert frames[0]['memory'][3, 4] == 1
    assert metrics['mujoco_sensor_rays'] == 61
    assert metrics['mujoco_sensor_hit_types']['persistent_obstacles'] > 0


def test_legacy_2d_observation_backend_remains_deterministic():
    scenario = open_scenario()
    config = dict(sensor=dict(radius=3, occlusion=True, noise=0.0), update_interval=4,
                  unknown='optimistic', max_steps=8, observation_cost=1,
                  max_observations=2)
    first, _ = run_episode(scenario, config, 'periodic', seed=42)
    second, _ = run_episode(scenario, config, 'periodic', seed=42)
    assert first == second


def test_saved_g1_scene_has_display_only_rendering_bounds_without_changing_evidence():
    """Parked Z=-1000 obstacle bodies must not make the GUI near clip enormous."""
    from importlib.util import module_from_spec, spec_from_file_location
    from pathlib import Path
    import xml.etree.ElementTree as ET
    import mujoco

    result_dir = Path(__file__).resolve().parents[1] / 'results/phase2_mujoco/g1_smoke'
    source = result_dir / 'scene.xml'
    original = source.read_bytes()
    viewer_path = Path(__file__).resolve().parents[1] / 'scripts/view_phase2_g1_navigation.py'
    spec = spec_from_file_location('phase2_g1_viewer_test_module', viewer_path)
    viewer_module = module_from_spec(spec)
    spec.loader.exec_module(viewer_module)
    xml = viewer_module.display_scene_xml(result_dir)
    statistic = ET.fromstring(xml).find('statistic')
    assert statistic is not None
    model = mujoco.MjModel.from_xml_string(xml)
    assert 1 < model.stat.extent < 100
    assert model.stat.extent * model.vis.map.znear < 1
    assert source.read_bytes() == original
