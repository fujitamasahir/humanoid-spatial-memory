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
    assert np.allclose(scene.footprint_half_extents_local, (0.219, 0.328), atol=0.002)


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


def test_hidden_occupancy_and_collision_rejection_do_not_write_agent_memory():
    """Only authorized ternary observations may change the controller's map."""
    from spatial_memory.scheduling import ObservationController

    config = dict(sensor=dict(radius=3, occlusion=True, noise=0.0), update_interval=1,
        unknown='optimistic', max_steps=1, observation_cost=1, max_observations=1)
    memories = []
    original_move = World.move
    for obstacles in ((), ((2, 1),)):
        scenario = open_scenario(obstacles=obstacles)
        before = None
        def factory(initial, method, **kwargs):
            nonlocal before
            controller = ObservationController(initial, method, **kwargs)
            before = controller.memory.grid.copy()
            memories.append(controller)
            return controller
        # The synthetic movement gate reports an ambiguous blocked maneuver;
        # it must not turn that feedback into a free map observation.
        # A G1 episode must not delegate action acceptance to the oracle grid.
        def forbidden_oracle_move(*args, **kwargs):
            raise AssertionError('G1 movement consulted World.move ground truth')
        World.move = forbidden_oracle_move
        try:
            run_episode(scenario, config, 'static', seed=42,
                _controller_factory=factory,
                _planner=lambda grid, start, goal, unknown: [start, (2, 1), goal],
                _observation_provider=lambda world, position, yaw: np.full((5, 5), -1, np.int8),
                _movement_checker=lambda world, current, target, yaw:
                    (True, None, yaw, 'translation_collision'))
        finally:
            World.move = original_move
        assert np.array_equal(memories[-1].memory.grid, before)
    assert np.array_equal(memories[0].memory.grid, memories[1].memory.grid)


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
    # Box-face boundary snapping puts the first-hit cell with the obstacle,
    # leaving the adjacent approach cell free.
    assert observation[3, 4] == 1
    assert observation[3, 3] == 0
    assert sensor.last_stats['free_cells'] > 0
    assert sensor.last_stats['occupied_cells'] > 0
    assert sensor.last_stats['conflicting_cells'] >= 0
    assert sensor.last_stats['hits_by_type']['persistent_obstacles'] > 0
    assert sensor.last_stats['sensor_height_m'] < 0.9


def test_mujoco_rays_respect_occlusion_behind_a_wall():
    divider = tuple((3, y) for y in range(1, 6))
    scenario = ray_scenario(obstacles=((5, 3),), extra_walls=divider)
    sensor = MujocoRayPerception(MujocoNavigationScene(scenario))
    observation = sensor.observe(World(scenario), scenario.start, 0.0)
    assert observation[3, 3] == 1
    assert observation[3, 2] == 0
    assert observation[3, 5] == -1
    assert sensor.last_stats['hits_by_type']['persistent_obstacles'] == 0


def test_occupied_grid_cells_are_rasterized_from_first_hit_surface_points():
    """Occupied cells correspond to measured ray intersections, not geom centers."""
    scenario = ray_scenario(obstacles=((4, 3),))
    scene = MujocoNavigationScene(scenario)
    sensor = MujocoRayPerception(scene)
    world = World(scenario)
    sensor.observe(world, scenario.start, 0.0)
    # Reconstruct observed first-hit cells from ray distances and the explicit
    # 0.005-cell box-edge tolerance, never from hidden geometry centers.
    from spatial_memory.mujoco_navigation import G1_FORWARD_AXIS
    import math
    scene._sync_environment(world)
    scene._set_pose(scenario.start, 0.0)
    scene.mj.mj_forward(scene.model, scene.data)
    origin = scene.data.site_xpos[scene.sensor_site_id].copy()
    matrix = scene.data.site_xmat[scene.sensor_site_id].reshape(3, 3)
    forward = matrix @ np.asarray(G1_FORWARD_AXIS)
    left = matrix @ np.asarray((0., 1., 0.))
    geom = np.full(1, -1, dtype=np.int32)
    surfaces = set()
    for offset in np.linspace(-math.radians(60), math.radians(60), 61):
        direction = forward*math.cos(offset) + left*math.sin(offset)
        direction[2] = 0
        direction /= np.linalg.norm(direction)
        distance = float(scene.mj.mj_ray(scene.model, scene.data, origin, direction,
            sensor.geom_groups, True, scene.robot_body, geom))
        if 0 <= distance <= sensor.range_m:
            point = origin + direction*distance
            surfaces.add(sensor._surface_cell(point[:2], direction[:2]))
    measured = { (int(x), int(y)) for y, x in np.argwhere(sensor.observe(world, scenario.start, 0.0) == 1) }
    assert measured == surfaces
    assert sensor.observe(world, scenario.start, 0.0)[scenario.start[1], scenario.start[0]] == 0


def test_first_observation_preserves_free_approach_and_assigns_wall_to_far_cell():
    # The .37875 m wall face is 0.00375 m beyond the .375 m raster boundary.
    scenario = ray_scenario(start=(5, 3), goal=(7, 3), extra_walls=((6, 2), (6, 3), (6, 4)))
    scene = MujocoNavigationScene(scenario)
    sensor = MujocoRayPerception(scene)
    observation = sensor.observe(World(scenario), scenario.start, 0.0)
    assert observation[3, 5] == 0
    assert observation[3, 6] == 1
    assert sensor.last_stats['free_cells'] >= 1


def test_occupied_surface_wins_only_in_its_measured_cell_not_the_approach_cell():
    scenario = ray_scenario(obstacles=((4, 3),))
    sensor = MujocoRayPerception(MujocoNavigationScene(scenario))
    observation = sensor.observe(World(scenario), scenario.start, 0.0)
    assert observation[3, 3] == 0
    assert observation[3, 4] == 1


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
    assert east[3, 3] == 0
    assert west[3, 4] == -1
    assert not np.array_equal(east, west)


def test_moving_pedestrian_is_measured_at_its_current_geometry_only():
    scenario = ray_scenario(pedestrians=(((3, 3), (3, 2)),))
    scene, world = MujocoNavigationScene(scenario), World(scenario)
    sensor = MujocoRayPerception(scene)
    first = sensor.observe(world, scenario.start, 0.0)
    assert first[3, 3] == 1
    assert sensor.last_stats['hits_by_type']['pedestrians'] > 0
    assert [3, 3] in sensor.last_stats['visible_pedestrian_cells']
    world.advance()
    second = sensor.observe(world, scenario.start, 0.0)
    assert second[2, 3] == 1
    assert second[3, 3] == 0


def test_wait_action_records_why_and_does_not_query_collision_checker():
    scenario = open_scenario()
    config = dict(sensor=dict(radius=3, occlusion=True, noise=0.0), update_interval=1,
        unknown='optimistic', max_steps=2, observation_cost=1, max_observations=3)
    def planner(grid, position, goal, unknown, yaw, blocked):
        return [('wait', 'dynamic_threat_uncertain_no_safe_retreat')]
    def forbidden_unattempted_check(*_args):
        raise AssertionError('Waiting must not query a collision pose')
    metrics, frames = run_episode(scenario, config, 'periodic', seed=42,
        _observation_provider=lambda world, position, yaw: np.zeros((5, 5), np.int8),
        _g1_planner=planner, _action_checker=forbidden_unattempted_check,
        _g1_action_reason=lambda action, position, yaw: action[1])
    assert metrics['g1_waits'] == 2
    assert metrics['g1_forward_actions'] == 0
    assert metrics['g1_nonforward_action_reasons'] == {
        'dynamic_threat_uncertain_no_safe_retreat': 2}
    assert all(frame['navigation_action'][0] == 'wait' for frame in frames[1:])


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


def test_environment_rays_do_not_self_detect_g1_collision_geometry():
    scenario = ray_scenario(obstacles=((4, 3),), pedestrians=(((3, 3),),))
    scene = MujocoNavigationScene(scenario)
    sensor = MujocoRayPerception(scene)
    sensor.observe(World(scenario), scenario.start, 0.0)
    assert sensor.geom_groups[5] == 1
    assert not np.any(sensor.geom_groups[:5])
    assert sum(sensor.last_stats['hits_by_type'].values()) == sensor.last_stats['ray_hits']
    # Every G1 collision geom is outside the environment ray group.
    for geom_id in range(scene.model.ngeom):
        body = int(scene.model.geom_bodyid[geom_id])
        while body > 0:
            if body == scene.robot_body:
                assert int(scene.model.geom_group[geom_id]) != 5
                break
            body = int(scene.model.body_parentid[body])


def test_view_scene_exposes_walls_objects_pedestrians_and_actual_g1(tmp_path):
    import json
    import mujoco
    import xml.etree.ElementTree as ET
    from importlib.util import module_from_spec, spec_from_file_location
    from pathlib import Path

    viewer_path = Path(__file__).resolve().parents[1] / 'scripts/view_phase2_g1_navigation.py'
    spec = spec_from_file_location('phase2_g1_scene_visibility_test', viewer_path)
    viewer = module_from_spec(spec)
    spec.loader.exec_module(viewer)

    scenario = ray_scenario(obstacles=((4, 3),), pedestrians=(((3, 3), (3, 2)),))
    scene = MujocoNavigationScene(scenario)
    (tmp_path/'scene.xml').write_text(scene.xml, encoding='utf-8')
    (tmp_path/'scenario.json').write_text(json.dumps(dict(width=scenario.width,
        height=scenario.height, cell_size_m=scene.cell_size)), encoding='utf-8')
    display_root = ET.fromstring(viewer.display_scene_xml(tmp_path))
    names = {g.get('name') for g in display_root.iter('geom')}
    assert any(name.startswith('wall_') for name in names)
    assert 'object_geom_4_3' in names
    assert 'pedestrian_geom_0' in names
    visible_environment = [g for g in display_root.iter('geom')
        if g.get('name', '').startswith(('wall_', 'object_geom_', 'pedestrian_geom_'))]
    assert visible_environment and all((g.get('group') or '0') == '0' for g in visible_environment)
    model = mujoco.MjModel.from_xml_string(ET.tostring(display_root, encoding='unicode'))
    assert mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, 'pelvis') >= 0


def test_g1_footprint_planner_routes_around_observed_occupancy_and_is_deterministic():
    from spatial_memory.navigation import plan_g1

    grid = np.zeros((7, 7), dtype=np.int8)
    grid[3, 3] = 1
    first = plan_g1(grid, (1, 3), (5, 3), local_extents=(0.22, 0.328))
    second = plan_g1(grid, (1, 3), (5, 3), local_extents=(0.22, 0.328))
    assert first and first == second
    assert all(not (kind == 'move' and value == (3, 3)) for kind, value in first)
    # Movement can be lateral while yaw remains fixed, allowing the robot to
    # leave a tight wall before a planner-permitted safe turn.
    assert any(kind == 'move' and value[1] != 3 for kind, value in first)


def test_footprint_clearance_depends_on_heading():
    from spatial_memory.navigation import _overlaps_known_occupied

    grid = np.full((5, 5), -1, dtype=np.int8)
    grid[3, 2] = 1
    # Deliberately asymmetric public footprint proves the orientation transform.
    assert _overlaps_known_occupied(grid, 2, 2, 0, (0.1, 0.6), 0.75)
    assert not _overlaps_known_occupied(grid, 2, 2, np.pi/2, (0.1, 0.6), 0.75)


def test_g1_planner_uses_attempt_feedback_without_repeating_until_observation_changes():
    from spatial_memory.navigation import blocked_action_key

    scenario = open_scenario()
    config = dict(sensor=dict(radius=3, occlusion=True, noise=0.0), update_interval=1,
        unknown='optimistic', max_steps=3, observation_cost=1, max_observations=4)
    action = ('move', (2, 1))
    key = blocked_action_key(scenario.start, 0, action)
    observations = [np.full((5, 5), -1, np.int8) for _ in range(4)]
    observations[1][1, 2] = 0
    observations[2][1, 2] = 0  # no information change: keep the rejection
    observations[3][1, 2] = 0
    observations[3][2, 2] = 0  # new local information: allow reconsideration
    obs_calls, planner_block_sets, shield_calls = 0, [], 0
    def provider(world, position, yaw):
        nonlocal obs_calls
        result = observations[min(obs_calls, len(observations)-1)].copy()
        obs_calls += 1
        return result
    def planner(grid, position, goal, unknown, yaw, blocked):
        planner_block_sets.append(set(blocked))
        if position == scenario.start:
            return [] if key in blocked else [action]
        return []
    def checker(world, position, attempted, yaw):
        nonlocal shield_calls
        shield_calls += 1
        if shield_calls == 1:
            return True, None, yaw, 'translation_collision'
        return False, None, yaw, None
    metrics, _ = run_episode(scenario, config, 'periodic', seed=42,
        _observation_provider=provider, _g1_planner=planner, _action_checker=checker)
    assert shield_calls == 2  # one rejected attempt, no duplicate on step 2, one reconsideration
    assert metrics['g1_distinct_rejected_actions'] == 1
    assert metrics['g1_rejected_action_attempts'] == 1
    assert metrics['g1_blocked_movement_reasons']['translation_collision'] == 1
    assert metrics['g1_blocked_feedback_resets_after_changed_observation'] == 1
    assert planner_block_sets[1] == {key}
    assert planner_block_sets[2] == set()
    assert metrics['observation_count'] == 4


def test_forward_facing_planner_turns_before_walking_and_never_strafes_or_reverses():
    from spatial_memory.navigation import CARDINALS, plan_g1_forward_facing

    grid = np.zeros((9, 9), dtype=np.int8)
    route = plan_g1_forward_facing(grid, (3, 3), (3, 6), heading=0,
        local_extents=(0.22, 0.328), cell_size=0.75)
    assert route[0] == ('turn', 1)
    face = 0
    position = (3, 3)
    for kind, value in route:
        if kind == 'turn':
            face = value
        else:
            dx, dy = CARDINALS[face]
            assert value == (position[0]+dx, position[1]+dy)
            position = value
    assert position == (3, 6)


def test_forward_facing_planner_routes_around_a_rotation_clearance_rejection():
    from spatial_memory.navigation import blocked_action_key, plan_g1_forward_facing

    grid = np.zeros((9, 9), dtype=np.int8)
    grid[4, 4] = 1
    route = plan_g1_forward_facing(grid, (3, 3), (3, 5), heading=0,
        local_extents=(0.22, 0.328), cell_size=0.75)
    assert route
    # The AABB diagonal overlap no longer pre-rejects the turn. The selected
    # turn is checked once by the actual MuJoCo shield in the evaluator.
    assert route[0] == ('turn', 1)
    assert ('turn', 1) in route

    # If the actual attempted north pivot is rejected by MuJoCo while the
    # observation is still unknown, feedback removes that transition and A*
    # finds a different observed-map route without probing other poses.
    open_memory = np.zeros((9, 9), dtype=np.int8)
    rejected_turn = blocked_action_key((3, 3), 0, ('turn', 1))
    alternative = plan_g1_forward_facing(open_memory, (3, 3), (3, 5), heading=0,
        local_extents=(0.22, 0.328), cell_size=0.75,
        blocked_actions={rejected_turn})
    assert alternative and alternative[0] != ('turn', 1)


def test_forward_facing_turns_are_not_filtered_by_rectangular_clearance():
    from spatial_memory.navigation import _turn_clear, plan_g1_forward_facing

    grid = np.zeros((9, 9), dtype=np.int8)
    grid[4, 4] = 1
    assert not _turn_clear(grid, (3, 3), 0, 1, (0.22, 0.328), 0.75)
    route = plan_g1_forward_facing(grid, (3, 3), (3, 5), heading=0,
        local_extents=(0.22, 0.328), cell_size=0.75)
    assert route[0] == ('turn', 1)


def test_actual_g1_turn_clearance_uses_only_attempted_mujoco_geometry():
    # Empty geometry permits a selected turn. A pedestrian that occupies the
    # robot's pivot at the attempted time rejects it through the actual model.
    safe = ray_scenario(width=9, height=9, start=(3, 3), goal=(6, 6))
    safe_scene = MujocoNavigationScene(safe)
    safe_result = safe_scene.check_turn(World(safe), safe.start, 0, np.pi/2)
    assert not safe_result[0]

    occupied_pivot = ray_scenario(width=9, height=9, start=(3, 3), goal=(6, 6),
        pedestrians=(((4, 3), (3, 3)),))
    world = World(occupied_pivot)
    world.step = 1
    scene = MujocoNavigationScene(occupied_pivot)
    blocked = scene.check_turn(world, occupied_pivot.start, 0, np.pi/2)
    assert blocked[0] and blocked[3] == 'rotation_collision'
    assert blocked[1].pedestrian > 0


def test_actual_g1_side_step_and_retreat_sweeps_are_checked_by_collision_model():
    side_scenario = ray_scenario(width=9, height=9, start=(3, 3), goal=(6, 3),
                                 obstacles=((4, 3),))
    side_world = World(side_scenario)
    side_scene = MujocoNavigationScene(side_scenario)
    sidestep = side_scene.check_move(side_world, (3, 3), (3, 4), 0, target_yaw=0)
    assert not sidestep[0]
    side_scene._set_pose((3, 4), 0)
    resume_forward = side_scene.check_move(side_world, (3, 4), (4, 4), 0,
                                           target_yaw=0)
    assert not resume_forward[0]

    pedestrian_scenario = ray_scenario(width=9, height=9, start=(3, 3), goal=(6, 3),
                                       pedestrians=(((4, 3),),))
    pedestrian_world = World(pedestrian_scenario)
    retreat_scene = MujocoNavigationScene(pedestrian_scenario)
    retreat = retreat_scene.check_move(pedestrian_world, (3, 3), (2, 3), 0,
                                       target_yaw=0)
    assert not retreat[0]


def test_forward_facing_episode_uses_observations_and_only_checks_selected_actions(monkeypatch):
    from spatial_memory.navigation import plan_g1_forward_facing

    scenario = ray_scenario(width=7, height=7, start=(2, 2), goal=(2, 4))
    config = dict(sensor=dict(radius=3, occlusion=True, noise=0.0), update_interval=1,
        unknown='optimistic', max_steps=8, observation_cost=1, max_observations=8)
    selected_checks = []

    def no_oracle_move(*_args, **_kwargs):
        raise AssertionError('Forward-facing planner consulted hidden World.move occupancy')

    monkeypatch.setattr(World, 'move', no_oracle_move)

    def planner(grid, position, goal, unknown, yaw, blocked):
        return plan_g1_forward_facing(grid, position, goal, heading=round(yaw/(np.pi/2)),
            unknown=unknown, local_extents=(0.22, 0.328), blocked_actions=blocked)

    def checker(world, position, action, yaw):
        selected_checks.append(action)
        if action[0] == 'turn':
            return False, None, action[1]*np.pi/2, None
        return False, None, yaw, None

    metrics, frames = run_episode(scenario, config, 'periodic', seed=42,
        _observation_provider=lambda world, position, yaw: np.zeros((7, 7), np.int8),
        _g1_planner=planner, _action_checker=checker)
    assert metrics['success']
    assert metrics['g1_forward_actions'] == 2
    assert metrics['g1_lateral_actions'] == metrics['g1_backward_actions'] == 0
    assert metrics['g1_in_place_turns'] == 1
    assert metrics['g1_executed_forward_translations'] == 2
    assert selected_checks and len(selected_checks) == sum(
        frame.get('navigation_action') is not None for frame in frames)
    assert selected_checks[0][0] == 'turn'
    assert all(kind in {'turn', 'move'} for kind, _ in selected_checks)


def test_default_policy_turns_for_ordinary_routes_and_rejects_unnecessary_lateral_motion():
    from spatial_memory.navigation import plan_g1_default_policy

    grid = np.zeros((9, 9), dtype=np.int8)
    ordinary = plan_g1_default_policy(grid, (3, 3), (3, 6), heading=0,
        local_extents=(0.22, 0.328), cell_size=0.75)
    assert ordinary[0] == ('turn', 1)
    assert all(kind not in {'sidestep', 'retreat'} for kind, _ in ordinary)

    no_static_evidence = grid.copy()
    no_static_evidence[3, 4] = 1
    blocked_forward = plan_g1_default_policy(no_static_evidence, (3, 3), (6, 3),
        heading=0, local_extents=(0.22, 0.328), cell_size=0.75,
        static_obstacle_cells=())
    assert not blocked_forward or blocked_forward[0][0] not in {'sidestep', 'retreat'}


def test_default_policy_allows_one_clear_side_step_only_for_observed_static_object():
    from spatial_memory.navigation import plan_g1_default_policy

    grid = np.zeros((9, 9), dtype=np.int8)
    grid[3, 4] = 1
    action = plan_g1_default_policy(grid, (3, 3), (6, 3), heading=0,
        local_extents=(0.22, 0.328), cell_size=0.75,
        static_obstacle_cells={(4, 3)})
    assert action[0] == ('sidestep', (3, 4))
    resumed = plan_g1_default_policy(grid, (3, 4), (6, 3), heading=0,
        local_extents=(0.22, 0.328), cell_size=0.75,
        static_obstacle_cells={(4, 3)})
    assert resumed[0] == ('move', (4, 4))

    # A side cell that is unknown does not qualify as a safe maneuver.
    uncertain = grid.copy()
    uncertain[4, 3] = -1
    uncertain[2, 3] = -1
    no_step = plan_g1_default_policy(uncertain, (3, 3), (6, 3), heading=0,
        local_extents=(0.22, 0.328), cell_size=0.75,
        static_obstacle_cells={(4, 3)})
    assert not no_step or no_step[0][0] != 'sidestep'


def test_default_policy_retreats_only_for_observed_imminent_pedestrian_and_clear_sweep():
    from spatial_memory.navigation import plan_g1_default_policy

    grid = np.zeros((9, 9), dtype=np.int8)
    grid[3, 4] = 1
    approaching = {'visible_cells': ((4, 3),),
        'history': ((0, 6.0, 3.0), (4, 4.0, 3.0)), 'reliable': True,
        'last_step': 4, 'max_age_steps': 8}
    action = plan_g1_default_policy(grid, (3, 3), (6, 3), heading=0,
        local_extents=(0.22, 0.328), cell_size=0.75,
        pedestrian_context=approaching, step=5)
    assert action == [('retreat', (2, 3))]

    # Unknown cells behind the robot make retreat unsafe, so the policy waits.
    unknown_behind = np.full((9, 9), -1, dtype=np.int8)
    unknown_behind[3, 3] = 0
    unknown_behind[3, 4] = 1
    action = plan_g1_default_policy(unknown_behind, (3, 3), (6, 3), heading=0,
        local_extents=(0.22, 0.328), cell_size=0.75,
        pedestrian_context=approaching, step=5)
    assert action == [('wait', 'imminent_dynamic_threat_retreat_not_observed_clear')]


def test_unreliable_nearby_pedestrian_motion_causes_wait_not_blind_retreat():
    from spatial_memory.navigation import plan_g1_default_policy

    grid = np.zeros((9, 9), dtype=np.int8)
    grid[3, 4] = 1
    grid[2, 3] = grid[4, 3] = -1
    uncertain = {'visible_cells': ((4, 3),), 'history': (), 'reliable': False,
                 'last_step': 5, 'max_age_steps': 8}
    action = plan_g1_default_policy(grid, (3, 3), (6, 3), heading=0,
        pedestrian_context=uncertain, step=5)
    assert action == [('wait', 'dynamic_threat_uncertain_no_safe_retreat')]


def test_uncertain_close_pedestrian_uses_only_observed_clear_lateral_escape():
    from spatial_memory.navigation import plan_g1_default_policy

    # Regression shape for the M:80030007 periodic collision: pedestrian
    # detection is close and forward, but its motion estimate is uncertain.
    grid = np.zeros((9, 9), dtype=np.int8)
    grid[3, 4] = 1  # measured pedestrian first-hit cell
    context = {'visible_cells': ((4.0, 3.0),), 'history': (), 'reliable': False,
               'last_step': 5, 'max_age_steps': 8}
    action = plan_g1_default_policy(grid, (3, 3), (6, 3), heading=0,
        local_extents=(0.22, 0.328), cell_size=0.75,
        pedestrian_context=context, step=5)
    assert action == [('sidestep', (3, 2))]

    # When the observed threat is offset to the robot's left, choose the
    # observed-free right side rather than moving toward it.
    offset_grid = grid.copy()
    offset_grid[4, 4] = 1
    left_threat = {**context, 'visible_cells': ((4.0, 3.5),)}
    action = plan_g1_default_policy(offset_grid, (3, 3), (6, 3), heading=0,
        local_extents=(0.22, 0.328), cell_size=0.75,
        pedestrian_context=left_threat, step=5)
    assert action == [('sidestep', (3, 2))]

    # Unknown side cells are not clearances. With both side corridors unknown,
    # the policy remains stationary instead of probing a maneuver.
    uncertain = grid.copy()
    uncertain[2, 3] = uncertain[4, 3] = -1
    action = plan_g1_default_policy(uncertain, (3, 3), (6, 3), heading=0,
        local_extents=(0.22, 0.328), cell_size=0.75,
        pedestrian_context=context, step=5)
    assert action == [('wait', 'dynamic_threat_uncertain_no_safe_retreat')]


def test_departing_pedestrian_does_not_trigger_dynamic_retreat_or_sidestep():
    from spatial_memory.navigation import plan_g1_default_policy

    grid = np.zeros((9, 9), dtype=np.int8)
    grid[3, 4] = 1
    departing = {'visible_cells': ((4.0, 3.0),),
        'history': ((0, 3.0, 3.0), (4, 4.0, 3.0)), 'reliable': True,
        'last_step': 4, 'max_age_steps': 8}
    action = plan_g1_default_policy(grid, (3, 3), (6, 3), heading=0,
        local_extents=(0.22, 0.328), cell_size=0.75,
        pedestrian_context=departing, step=5)
    assert action[0][0] not in {'retreat', 'sidestep'}


def test_pedestrian_occluded_by_wall_is_not_given_to_tracker_or_policy():
    scenario = ray_scenario(obstacles=((4, 3),), pedestrians=(((5, 3),),))
    sensor = MujocoRayPerception(MujocoNavigationScene(scenario))
    sensor.observe(World(scenario), scenario.start, 0.0)
    assert sensor.last_stats['hits_by_type']['pedestrians'] == 0
    assert sensor.last_stats['visible_pedestrian_cells'] == []


def test_failing_static_contact_case_has_no_permitted_pedestrian_detection():
    """R:80000001 has one static observation and cannot react to hidden motion."""
    scenario = ray_scenario(obstacles=((4, 3),), pedestrians=(((5, 3),),))
    sensor = MujocoRayPerception(MujocoNavigationScene(scenario))
    sensor.observe(World(scenario), scenario.start, 0.0)
    # The policy receives no pedestrian class/cell; evaluator truth is not an
    # input to plan_g1_default_policy. A null context cannot authorize retreat.
    assert sensor.last_stats['visible_pedestrian_cells'] == []
    from spatial_memory.navigation import plan_g1_default_policy
    grid = np.zeros((9, 9), dtype=np.int8)
    action = plan_g1_default_policy(grid, scenario.start, scenario.goal,
        heading=0, local_extents=(0.22, 0.328), cell_size=0.75,
        pedestrian_context=None)
    assert action[0][0] in {'move', 'turn'}


def test_observed_pedestrian_tracker_uses_only_measured_cells_and_needs_two_observations():
    from spatial_memory.pedestrian_tracking import ObservedPedestrianTracker

    tracker = ObservedPedestrianTracker(max_age_steps=8)
    tracker.observe(0, [(6, 3), (6, 3)])
    assert not tracker.context()['reliable']
    tracker.observe(4, [(4, 3), (4, 3)])
    context = tracker.context()
    assert context['visible_cells'] == ((4.0, 3.0),)
    assert context['history'] == [(0, 6.0, 3.0), (4, 4.0, 3.0)]
    assert context['reliable']
    tracker.observe(8, [])
    assert not tracker.context()['reliable']


def test_full_comparison_summary_and_world_clustered_pairing_validate_matched_design():
    from importlib.util import module_from_spec, spec_from_file_location
    from pathlib import Path
    from spatial_memory.phase15_bprime import ACTIVE_MECHANISMS

    script = Path(__file__).resolve().parents[1] / 'scripts/phase2_mujoco_navigation.py'
    spec = spec_from_file_location('phase2_runner_cluster_test', script)
    runner = module_from_spec(spec)
    spec.loader.exec_module(runner)
    methods = ('static', 'periodic', 'age', 'uncertainty')
    rows = []
    for mechanism in ACTIVE_MECHANISMS:
        for world_index in range(12):
            identity = f'{mechanism}:{world_index}'
            for schedule in (0, 1):
                for method_index, method in enumerate(methods):
                    row = dict(mechanism=mechanism, world_identity=identity,
                        schedule=schedule, method=method, success=method == 'periodic',
                        contact_free_success=method == 'periodic',
                        g1_contact_free_success=method == 'periodic',
                        observation_count=method_index+schedule, observation_cost=method_index+schedule,
                        travel_distance_m=10.0+method_index, elapsed_steps=20+method_index,
                        g1_navigation_no_route_steps=0,
                        g1_heading_changes=method_index, stale_map_errors=0,
                        false_persistent_occupancy_updates=0, missed_persistent_changes=0,
                        mujoco_sensor_rays=61, mujoco_sensor_hits=10,
                        mujoco_sensor_visible_cells=5, mujoco_sensor_occupied_cells=2,
                        mujoco_sensor_free_cells=3, mujoco_sensor_hit_types={
                            'walls': 8, 'persistent_obstacles': 2, 'pedestrians': 0},
                        g1_unwanted_contact_pairs=0, g1_footprint_blocked_attempts=method_index,
                        g1_rejected_action_attempts=method_index,
                        g1_distinct_rejected_actions=method_index,
                        g1_blocked_feedback_resets_after_changed_observation=0,
                        g1_blocked_movement_reasons={'rotation_collision': 0,
                            'translation_collision': method_index, 'grid_occupancy': 0},
                        blocked_movement_attempts=method_index, dynamic_contacts=0,
                        g1_pedestrian_contact_pairs=0, g1_wall_contact_pairs=0,
                        g1_persistent_obstacle_contact_pairs=0,
                        g1_attempt_pedestrian_contact_pairs=0, g1_attempt_wall_contact_pairs=0,
                        g1_attempt_persistent_obstacle_contact_pairs=0,
                        travel_distance=10.0, final_stale_map_errors=0,
                        final_false_persistent_occupancy_updates=0,
                        final_missed_persistent_changes=0)
                    rows.append(row)
    indexed = runner.validate_matched_design(rows)
    assert len(indexed) == 288
    summary = runner.summarize(rows)
    assert summary['mechanisms']['R']['periodic']['episodes'] == 24
    paired = runner.paired_world_clustered(rows, bootstrap_replicates=200)
    contrast = paired['contrasts']['overall']['static_minus_periodic']['goal_completion']
    assert contrast['world_clusters'] == 36
    assert contrast['matched_world_schedule_pairs'] == 72
    assert contrast['left_minus_right_mean'] == -1.0
    assert contrast['cluster_bootstrap_95pct_ci'] == [-1.0, -1.0]


def test_action_history_audit_separates_attempts_from_unique_transitions():
    from importlib.util import module_from_spec, spec_from_file_location
    from pathlib import Path

    script = Path(__file__).resolve().parents[1] / 'scripts/audit_phase2_rejected_actions.py'
    spec = spec_from_file_location('phase2_action_history_audit_test', script)
    audit = module_from_spec(spec)
    spec.loader.exec_module(audit)
    move = dict(position=[2, 3], heading_index=0, action_kind='move', action=[3, 3])
    turn = dict(position=[2, 3], heading_index=0, action_kind='turn', action=1)
    result = audit.audit_records([move, dict(move), turn])
    assert result == dict(attempts=3, unique_transitions=2,
                          retries_after_local_observation_change=1)


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
    display_root = ET.fromstring(xml)
    statistic = display_root.find('statistic')
    assert statistic is not None
    # The saved scene is immutable; the derived viewer XML exposes sensing
    # geoms to the stock viewer (default groups 0, 1 and 2).
    saved_walls = [g for g in ET.parse(source).getroot().iter('geom')
                   if g.get('name', '').startswith('wall_')]
    visible_walls = [g for g in display_root.iter('geom')
                     if g.get('name', '').startswith('wall_')]
    assert saved_walls and len(saved_walls) == len(visible_walls)
    assert all((g.get('group') or '0') == '0' for g in visible_walls)
    saved_objects = [g for g in ET.parse(source).getroot().iter('geom')
                     if g.get('name', '').startswith(('object_geom_', 'pedestrian_geom_'))]
    visible_objects = [g for g in display_root.iter('geom')
                       if g.get('name', '').startswith(('object_geom_', 'pedestrian_geom_'))]
    assert len(saved_objects) == len(visible_objects)
    assert all((g.get('group') or '0') == '0' for g in visible_objects)
    model = mujoco.MjModel.from_xml_string(xml)
    assert 1 < model.stat.extent < 100
    assert model.stat.extent * model.vis.map.znear < 1
    assert source.read_bytes() == original


def _g1_viewer_module():
    from importlib.util import module_from_spec, spec_from_file_location
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / 'scripts/view_phase2_g1_navigation.py'
    spec = spec_from_file_location('phase2_g1_visual_gait_test_module', path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_visual_gait_joint_offsets_respect_actual_g1_ranges_and_are_deterministic():
    from pathlib import Path
    import mujoco

    viewer = _g1_viewer_module()
    result = Path(__file__).resolve().parents[1] / \
        'results/phase2_mujoco/g1_g1footprint_feedback_seed42_smoke_final'
    model = mujoco.MjModel.from_xml_string(viewer.display_scene_xml(result))
    first = viewer.gait_joint_targets(model, 1.234, 0.8, -1)
    second = viewer.gait_joint_targets(model, 1.234, 0.8, -1)
    assert first == second
    expected = {
        'left_hip_pitch_joint', 'right_hip_pitch_joint',
        'left_hip_roll_joint', 'right_hip_roll_joint',
        'left_knee_joint', 'right_knee_joint',
        'left_ankle_roll_joint', 'right_ankle_roll_joint',
        'left_ankle_pitch_joint', 'right_ankle_pitch_joint',
        'left_shoulder_pitch_joint', 'right_shoulder_pitch_joint',
        'left_elbow_joint', 'right_elbow_joint',
    }
    assert set(first) == expected
    for name, offset in first.items():
        jid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name)
        low, high = model.jnt_range[jid]
        assert low <= offset <= high
    forward = viewer.gait_joint_targets(model, 1.0, 1.0, 1)
    sidestep = viewer.gait_joint_targets(model, 1.0, 1.0, 2)
    assert sidestep['left_hip_roll_joint'] != 0
    assert abs(sidestep['left_hip_pitch_joint']) < abs(forward['left_hip_pitch_joint'])


def test_visual_gait_interpolates_heading_by_shortest_arc_and_root_continuously():
    import math

    viewer = _g1_viewer_module()
    a, b = math.radians(170), math.radians(-170)
    midpoint = viewer.interpolate_heading(a, b, 0.5)
    assert abs(abs(midpoint)-math.pi) < 1e-9
    frame = viewer.interpolate_frame(
        {'position': (1, 2), 'heading_yaw': a},
        {'position': (3, 6), 'heading_yaw': b}, 0.25)
    assert frame['position'] == (1.5, 3.0)
    assert abs(frame['heading_yaw']-math.radians(175)) < 1e-9


def test_visual_gait_start_stop_transitions_are_smooth_and_return_to_stand():
    viewer = _g1_viewer_module()
    assert viewer.smooth_gait_envelope(0, True) == 0
    assert 0 < viewer.smooth_gait_envelope(0.11, True) < 1
    assert viewer.smooth_gait_envelope(viewer.GAIT_RAMP_SECONDS, True) == 1
    assert viewer.smooth_gait_envelope(0, False) == 1
    assert 0 < viewer.smooth_gait_envelope(0.11, False) < 1
    assert viewer.smooth_gait_envelope(viewer.GAIT_RAMP_SECONDS, False) == 0


def test_visual_gait_samples_are_deterministic_for_forward_lateral_backward_and_turns():
    import math

    viewer = _g1_viewer_module()
    trajectory = [
        {'position': (0, 0), 'heading_yaw': 0.0},
        {'position': (1, 0), 'heading_yaw': 0.0},       # forward
        {'position': (1, 1), 'heading_yaw': 0.0},       # lateral
        {'position': (0, 1), 'heading_yaw': 0.0},       # backward
        {'position': (0, 1), 'heading_yaw': math.pi/2}, # in-place turn
        {'position': (0, 1), 'heading_yaw': math.pi/2}, # stop
        {'position': (0, 2), 'heading_yaw': math.pi/2}, # resume laterally
    ]
    first = list(viewer.playback_samples(trajectory, 0.12, 0.75, fps=30))
    second = list(viewer.playback_samples(trajectory, 0.12, 0.75, fps=30))
    assert first == second
    assert len(first) == 32  # six route segments plus a full stand-pose settle
    assert first[0][2] == 0 and first[0][3] == 0
    assert all(sample[1] in trajectory for sample in first)
    assert min(sample[0]['position'][0] for sample in first) >= 0
    assert max(sample[0]['position'][0] for sample in first) <= 1
    assert any(sample[4] < 0 for sample in first)
    final_pose = first[-1]
    assert final_pose[3] == 0
    # Stopping and restarting reverses the envelope without a pose discontinuity.
    movement_stop_start = [sample[3] for sample in first]
    assert all(0 <= value <= 1 for value in movement_stop_start)
    assert max(abs(b-a) for a, b in zip(movement_stop_start, movement_stop_start[1:])) <= \
        1/30/viewer.GAIT_RAMP_SECONDS + 1e-9


def test_visual_gait_default_headless_replay_preserves_saved_results():
    import hashlib
    from pathlib import Path

    viewer = _g1_viewer_module()
    result = Path(__file__).resolve().parents[1] / \
        'results/phase2_mujoco/g1_g1footprint_feedback_seed42_smoke_final'
    trajectory = result / 'trajectory.json'
    full = result.parents[0] / 'g1_3d_perception_footprint_feedback_full_288'
    protected = [trajectory, full/'episodes.csv', full/'summary.json']
    before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in protected}
    default = viewer.replay(result, 0.1, viewer=False)
    explicit_default = viewer.replay(result, 0.1, viewer=False, visual_gait=False)
    assert default == explicit_default
    assert sum(count > 0 for count in default) == 0
    visual_audit = {}
    rendered = viewer.replay(result, 0.18, viewer=False, visual_gait=True,
                             contact_audit=visual_audit)
    assert len(rendered) > len(default)
    assert visual_audit['rendered_poses'] == len(rendered)
    assert visual_audit.get('unwanted_contact_frames', 0) == 0
    assert {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in protected} == before
