import csv
import json
from pathlib import Path

import numpy as np

from spatial_memory.emergency_safety import (EmergencySafetyController,
    IndependentEmergencySafetySensor)
from spatial_memory.evaluation import run_episode
from spatial_memory.mujoco_navigation import MujocoNavigationScene
from spatial_memory.simulation import Scenario, World


ROOT = Path(__file__).resolve().parents[1]


def scenario(*, start=(1, 3), goal=(7, 3), pedestrians=(), extra_walls=(),
             width=9, height=7):
    walls = {(x, y) for x in range(width) for y in range(height)
             if x in (0, width-1) or y in (0, height-1)}
    walls.update(extra_walls)
    return Scenario.from_dict(dict(name='emergency-safety-test', split='development',
        width=width, height=height, start=start, goal=goal, walls=tuple(walls),
        obstacles=(), changes=(), pedestrians=pedestrians))


def measurement(scene, cells, motion, *, grid=None):
    if grid is None:
        grid = np.zeros((scene.scenario.height, scene.scenario.width), dtype=np.int8)
    return {'grid': grid, 'visible_pedestrian_cells': tuple(cells),
            'motion_estimate': motion, 'record': {}}


def test_emergency_sensor_is_360_degree_and_sees_visible_capsule_proxy():
    s = scenario(pedestrians=(((3, 3),),))
    scene = MujocoNavigationScene(s)
    sensor = IndependentEmergencySafetySensor(scene)
    assert sensor.rays.ray_backend == 'multi'
    scan = sensor.scan(World(s), s.start, 0.0)
    assert sensor.rays.horizontal_fov_deg == 360.0
    assert sensor.rays.range_m == 2.0
    assert sensor.rays.ray_count == 181
    expected_angles = np.deg2rad(np.arange(-180, 182, 2))
    assert np.allclose(sensor.rays._ray_cosines, np.cos(expected_angles), atol=1e-15)
    assert np.allclose(sensor.rays._ray_sines, np.sin(expected_angles), atol=1e-15)
    assert scan['record']['hits_by_type']['pedestrians'] > 0
    assert scan['visible_pedestrian_cells']
    assert scan['record']['free_cells'] > 0
    assert scan['record']['occupied_cells'] > 0


def test_emergency_sensor_respects_wall_occlusion():
    s = scenario(start=(2, 3), pedestrians=(((4, 3),),), extra_walls=((3, 3),))
    scene = MujocoNavigationScene(s)
    scan = IndependentEmergencySafetySensor(scene).scan(World(s), s.start, 0.0)
    assert scan['record']['hits_by_type']['walls'] > 0
    assert scan['record']['hits_by_type']['pedestrians'] == 0
    assert not scan['visible_pedestrian_cells']


def test_multiray_181_matches_saved_sensor_observations_and_reference_intersections():
    """Validate distance/geom returns and exact old trace at the target states."""
    import json
    import sys
    sys.path.insert(0, str(ROOT / 'scripts'))
    import evaluate_g1_static_independent_safety as evaluator
    from spatial_memory.simulation import scenario_from_bprime
    from spatial_memory.mujoco_perception import MujocoRayPerception

    trace_path = ROOT / 'results/phase2_mujoco/g1_static_independent_safety_R80000001_s1_v5/safety_episode_trace.json'
    trace = json.loads(trace_path.read_text())
    _row, _events, payload = evaluator._load_source_episode()
    target = scenario_from_bprime(payload, 1)
    scene = MujocoNavigationScene(target)
    world = World(target)
    reference = MujocoRayPerception(scene, range_m=2.0,
        horizontal_fov_deg=360.0, ray_count=181, sample_spacing_m=0.075,
        ray_backend='single')
    optimized = MujocoRayPerception(scene, range_m=2.0,
        horizontal_fov_deg=360.0, ray_count=181, sample_spacing_m=0.075,
        ray_backend='multi')
    safety_sensor = IndependentEmergencySafetySensor(scene, ray_backend='multi')

    for frame in trace[1:]:
        expected = frame['emergency_safety_scan']
        world.step = int(frame['step'])
        position = expected['position_before_action']
        yaw = expected['heading_yaw_before_action']
        optimized_record = safety_sensor.scan(world, position, yaw)['record']
        assert optimized_record == expected

        if frame['step'] not in (1, 50, 52, 54, 59, 76):
            continue
        reference_grid = reference.observe(world, position, yaw)
        reference_distances = reference.last_ray_distances.copy()
        reference_geoms = reference.last_ray_geom_ids.copy()
        optimized_grid = optimized.observe(world, position, yaw)
        optimized_distances = optimized.last_ray_distances.copy()
        optimized_geoms = optimized.last_ray_geom_ids.copy()
        assert np.array_equal(reference_grid, optimized_grid)
        in_range_reference = (reference_distances >= 0) & (reference_distances <= 2.0)
        in_range_optimized = ((optimized_distances >= 0)
                              & (optimized_distances <= 2.0))
        assert np.array_equal(in_range_reference, in_range_optimized)
        assert np.array_equal(reference_geoms[in_range_reference],
                              optimized_geoms[in_range_optimized])
        assert np.allclose(reference_distances[in_range_reference],
                           optimized_distances[in_range_optimized],
                           atol=1e-12, rtol=1e-12)


def test_emergency_sensor_uses_only_current_simulated_proxy_pose_not_future_index():
    s = scenario(pedestrians=(((3, 3), (4, 3)),))
    world = World(s)
    scene = MujocoNavigationScene(s)

    class CurrentOnly:
        def __len__(self):
            return 2

        def __getitem__(self, index):
            assert index == 0, 'safety sensor attempted to read a future proxy pose'
            return (3, 3)

    object.__setattr__(s, 'pedestrians', (CurrentOnly(),))
    world.people = lambda: (_ for _ in ()).throw(AssertionError('controller read hidden occupancy'))
    scan = IndependentEmergencySafetySensor(scene).scan(world, s.start, 0.0)
    assert scan['record']['hits_by_type']['pedestrians'] > 0


def test_approaching_proxy_blocks_selected_destination_but_departing_proxy_does_not():
    scene = MujocoNavigationScene(scenario(start=(2, 3)))
    controller = EmergencySafetyController(scene)
    approaching = measurement(scene, [(4, 3)],
        {'state': 'measured_motion', 'velocity_cells_per_step': [-1.0, 0.0]})
    decision = controller.choose(None, (2, 3), (7, 3), 0.0,
        ('move', (3, 3)), approaching, 4)
    assert decision is not None
    assert decision['action'][0] == 'wait'
    assert decision['intervention']['selected_action_footprint_cells_at_risk']

    departing = measurement(scene, [(4, 3)],
        {'state': 'measured_motion', 'velocity_cells_per_step': [1.0, 0.0]})
    assert controller.choose(None, (2, 3), (7, 3), 0.0,
        ('move', (3, 3)), departing, 4) is None


def test_safe_selected_escape_is_preserved_when_the_current_footprint_is_threatened():
    scene = MujocoNavigationScene(scenario(start=(3, 3), goal=(7, 3)))
    controller = EmergencySafetyController(scene)
    unknown = measurement(scene, [(3, 4)],
        {'state': 'unknown', 'velocity_cells_per_step': None})
    # The current footprint is in the one-step set, while the eastward target
    # is outside it. Keep the already-selected safe forward escape.
    assert controller.choose(None, (3, 3), (7, 3), 0.0,
        ('move', (4, 3)), unknown, 5) is None


def test_unknown_motion_with_stationary_exposure_uses_only_observed_clear_escape():
    scene = MujocoNavigationScene(scenario(start=(3, 3), goal=(7, 3)))
    controller = EmergencySafetyController(scene)
    unknown = {'state': 'unknown', 'velocity_cells_per_step': None}
    scan = measurement(scene, [(4, 3)], unknown)
    decision = controller.choose(None, (3, 3), (7, 3), 0.0,
        ('move', (4, 3)), scan, 9)
    assert decision is not None
    assert decision['action'] == ('sidestep', (3, 4))
    assert decision['intervention']['escape_clearance_source'].startswith('latest independent sensor')

    unknown_grid = np.full((scene.scenario.height, scene.scenario.width), -1, dtype=np.int8)
    unknown_grid[3, 3] = 0  # Only the present footprint cell is measured free.
    blocked = measurement(scene, [(4, 3)], unknown, grid=unknown_grid)
    rejected = controller.choose(None, (3, 3), (7, 3), 0.0,
        ('move', (4, 3)), blocked, 9)
    assert rejected is not None
    assert rejected['action'][0] == 'wait'
    assert rejected['intervention']['reason'] == 'emergency_dynamic_hazard_no_observed_clear_escape'


def test_retreat_is_used_only_when_observed_clear_and_lateral_escape_is_not():
    scene = MujocoNavigationScene(scenario(start=(3, 3), goal=(7, 3)))
    controller = EmergencySafetyController(scene)
    unknown = {'state': 'unknown', 'velocity_cells_per_step': None}
    grid = np.zeros((scene.scenario.height, scene.scenario.width), dtype=np.int8)
    grid[4, 3] = 1  # Observed capsule cell blocks the upper side step.
    grid[2, 3] = -1  # Lower side step is not observed clear.
    scan = measurement(scene, [(4, 3)], unknown, grid=grid)
    decision = controller.choose(None, (3, 3), (7, 3), 0.0,
        ('move', (4, 3)), scan, 10)
    assert decision is not None
    assert decision['action'] == ('retreat', (2, 3))
    assert decision['intervention']['escape_clearance_source'].startswith('latest independent sensor')


def test_safety_scans_do_not_refresh_or_modify_static_spatial_memory():
    s = scenario(pedestrians=(((3, 3),),))
    scene = MujocoNavigationScene(s)
    sensor = IndependentEmergencySafetySensor(scene, range_m=2.0, ray_count=181)
    config = dict(sensor=dict(radius=2, occlusion=True, noise=0.0), update_interval=4,
        unknown='optimistic', max_steps=3, observation_cost=1, max_observations=20)
    initial_memory = []

    def scan(world, position, yaw):
        return sensor.scan(world, position, yaw)

    def planner(grid, position, goal, unknown, yaw, blocked):
        return [('wait', 'synthetic_hold')]

    metrics, frames = run_episode(s, config, 'static', 42,
        _frame_callback=scene.update,
        _g1_planner=planner,
        _action_checker=lambda *_: (_ for _ in ()).throw(AssertionError('wait must not query shield')),
        _emergency_safety_sensor=scan,
        _emergency_safety_controller=lambda *_: None)
    initial_memory = frames[0]['memory']
    assert metrics['observation_count'] == 1
    assert metrics['emergency_safety_scans'] == 3
    assert metrics['emergency_safety_raycasts'] == 3 * 181
    assert all(np.array_equal(frame['memory'], initial_memory) for frame in frames)
    assert all(frame['emergency_safety_scan']['step'] == frame['step'] for frame in frames[1:])


def test_synthetic_safety_replay_is_deterministic():
    def replay():
        s = scenario(pedestrians=(((3, 3), (4, 3)),), start=(2, 3), goal=(7, 3))
        scene = MujocoNavigationScene(s)
        sensor = IndependentEmergencySafetySensor(scene)
        config = dict(sensor=dict(radius=2, occlusion=True, noise=0.0), update_interval=4,
            unknown='optimistic', max_steps=4, observation_cost=1, max_observations=20)
        return run_episode(s, config, 'static', 42, _frame_callback=scene.update,
            _g1_planner=lambda *_: [('wait', 'synthetic_hold')],
            _action_checker=lambda *_: None,
            _emergency_safety_sensor=lambda w, p, y: sensor.scan(w, p, y))[1]

    first, second = replay(), replay()
    assert [f['emergency_safety_scan'] for f in first[1:]] == [
        f['emergency_safety_scan'] for f in second[1:]]


def test_saved_r80000001_static_baseline_failure_is_exact_and_contactful():
    path = ROOT / 'results/phase2_mujoco/g1_forward_first_shield_turns_v3_pedestrian_avoidance_full_288/episodes.csv'
    with path.open(newline='') as handle:
        rows = list(csv.DictReader(handle))
    row = next(r for r in rows if r['world_identity'] == 'phase1.5-v0.4-BPRIME-1:fit:R:80000001'
               and r['schedule'] == '1' and r['method'] == 'static' and r['seed'] == '42')
    assert row['success'] == 'False'
    assert row['elapsed_steps'] == '80'
    assert row['g1_unwanted_contact_pairs'] == '234'
    assert row['g1_lateral_actions'] == '0'
    report = json.loads((ROOT / 'results/phase2_mujoco/g1_static_independent_safety_R80000001_s1_v5/episode_comparison.json').read_text())
    step52 = next(x for x in report['baseline_timeline_evaluator_diagnostic_only'] if x['step'] == 52)
    step53 = next(x for x in report['baseline_timeline_evaluator_diagnostic_only'] if x['step'] == 53)
    assert step52['robot_position_before_action'] == [10, 4]
    assert step52['robot_position_after_action'] == [11, 4]
    assert step52['capsule_cells_evaluator_only_after_world_advance'] == [[11, 5]]
    assert step53['capsule_cells_evaluator_only_after_world_advance'] == [[11, 4]]
    assert step53['pedestrian_contact_pairs_after_action'] > 0


def test_target_safety_run_prevents_contact_without_expanding_static_budget_or_shield_queries():
    report = json.loads((ROOT / 'results/phase2_mujoco/g1_static_independent_safety_R80000001_s1_v5/episode_comparison.json').read_text())
    result = report['with_independent_safety_sensor']
    assert result['success'] is True
    assert result['g1_unwanted_contact_pairs'] == 0
    assert result['spatial_memory_observations'] == 1
    assert result['emergency_safety_scans'] == result['elapsed_steps']
    assert result['emergency_safety_raycasts'] == result['emergency_safety_scans'] * 181
    assert result['g1_actual_collision_shield_queries'] == result['g1_selected_actions_requiring_collision_check']
    assert result['g1_unattempted_collision_queries'] == 0
    assert result['g1_shield_query_count_valid'] is True
