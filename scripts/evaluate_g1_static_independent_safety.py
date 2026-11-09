"""Compare one saved R/static episode with independent near-field safety sensing.

Only the admitted, already-saved R/80000001 schedule-1 episode is evaluated.
This script does not generate worlds and refuses to overwrite output.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))

import phase2_mujoco_navigation as runner
from spatial_memory.emergency_safety import (EmergencySafetyController,
    IndependentEmergencySafetySensor)
from spatial_memory.evaluation import run_episode
from spatial_memory.mujoco_navigation import MujocoNavigationScene
from spatial_memory.mujoco_perception import MujocoRayPerception
from spatial_memory.navigation import (HEADINGS, assess_observed_pedestrian_risk,
    heading_index, plan_g1_default_policy)
from spatial_memory.pedestrian_tracking import ObservedPedestrianTracker
from spatial_memory.phase15_bprime_protocol import digest
from spatial_memory.simulation import scenario_from_bprime


IDENTITY = 'phase1.5-v0.4-BPRIME-1:fit:R:80000001'
SCHEDULE = 1
METHOD = 'static'
SEED = 42
SOURCE = ROOT / 'results/phase2_mujoco/g1_forward_first_shield_turns_v3_pedestrian_avoidance_full_288'
DEFAULT_OUTPUT = ROOT / 'results/phase2_mujoco/g1_static_independent_safety_R80000001_s1_v1'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_source_episode():
    with (SOURCE / 'episodes.csv').open(newline='') as handle:
        rows = list(csv.DictReader(handle))
    selected = [row for row in rows if row['world_identity'] == IDENTITY
                and int(row['schedule']) == SCHEDULE and row['method'] == METHOD
                and int(row['seed']) == SEED]
    if len(selected) != 1:
        raise ValueError(f'Expected one baseline row, found {len(selected)}')
    with (SOURCE / 'action_events.json').open() as handle:
        events = [item for item in json.load(handle)
                  if item['world_identity'] == IDENTITY
                  and int(item['schedule_index']) == SCHEDULE
                  and item['method'] == METHOD]
    payload = next(item for item in runner.admitted_worlds()
                   if item['identity'] == IDENTITY)
    return selected[0], events, payload


def _config():
    provenance = json.loads((SOURCE / 'provenance.json').read_text())
    return json.loads(json.dumps(provenance['policy_config']))


def _run_episode(payload, config, *, with_safety):
    scenario = scenario_from_bprime(payload, SCHEDULE)
    scene = MujocoNavigationScene(scenario,
        cell_size=config['mujoco_cell_size_m'],
        timestep=config['mujoco_timestep_seconds'])
    memory_perception = MujocoRayPerception(scene, **config['mujoco_ray_sensor'])
    tracker = ObservedPedestrianTracker(max_age_steps=8)
    safety_sensor = IndependentEmergencySafetySensor(scene) if with_safety else None
    safety_controller = EmergencySafetyController(scene) if with_safety else None
    state = {'static_obstacle_cells': set(), 'static_obstacle_step': -1,
             'planner_step': 0, 'action_shield_queries': 0,
             'last_reason': 'no_feasible_forward_route'}
    config['g1_navigation']['local_half_extents_m'] = list(scene.footprint_half_extents_local)

    def planner(grid, position, goal, unknown, yaw, blocked):
        state['planner_step'] += 1
        context = tracker.context()
        recent = (state['static_obstacle_cells']
                  if 0 <= state['planner_step']-state['static_obstacle_step'] <= 8 else set())
        route = plan_g1_default_policy(grid, position, goal,
            heading=heading_index(yaw), unknown=unknown,
            local_extents=scene.footprint_half_extents_local,
            cell_size=scene.cell_size, blocked_actions=blocked,
            static_obstacle_cells=recent, pedestrian_context=context,
            step=state['planner_step'])
        if route:
            kind, value = route[0]
            if kind == 'turn':
                state['last_reason'] = 'route_direction_change'
            elif kind == 'sidestep':
                state['last_reason'] = 'observed_static_obstacle_blocks_forward_path'
            elif kind == 'retreat':
                state['last_reason'] = assess_observed_pedestrian_risk(
                    position, heading_index(yaw), context,
                    step=state['planner_step']) or 'observed_oncoming_pedestrian_imminent'
            elif kind == 'wait':
                state['last_reason'] = str(value)
            else:
                state['last_reason'] = 'forward_route_segment'
        else:
            state['last_reason'] = 'no_feasible_forward_route'
        return route

    def record_memory_observation(_observation, step, _position):
        stats = memory_perception.last_stats
        tracker.observe(step, stats.get('visible_pedestrian_cells', ()))
        state['static_obstacle_cells'] = {
            tuple(cell) for cell in stats.get('visible_persistent_obstacle_cells', ())}
        state['static_obstacle_step'] = int(step)

    def safety_scan(world, position, yaw):
        return safety_sensor.scan(world, position, yaw)

    def safety_override(memory, position, goal, yaw, action, measurement, step, blocked):
        return safety_controller.choose(memory, position, goal, yaw, action,
                                        measurement, step, blocked)

    def action_reason(_action, _position, _yaw):
        return state['last_reason']

    def check_action(world, position, action, yaw):
        state['action_shield_queries'] += 1
        kind, value = action
        if kind in {'move', 'sidestep', 'retreat'}:
            return scene.check_move(world, position, tuple(value), yaw, target_yaw=yaw)
        return scene.check_turn(world, position, yaw, HEADINGS[int(value)])

    metrics, frames = run_episode(scenario, config, METHOD, seed=SEED,
        _frame_callback=scene.update,
        _observation_provider=memory_perception.observe,
        _g1_planner=planner, _action_checker=check_action,
        _initial_observation_callback=record_memory_observation,
        _observation_callback=record_memory_observation,
        _g1_action_reason=action_reason,
        _emergency_safety_sensor=safety_scan if with_safety else None,
        _emergency_safety_controller=safety_override if with_safety else None)
    selected_checks = sum(frame.get('navigation_action') is not None
                          and frame['navigation_action'][0] != 'wait' for frame in frames)
    metrics['g1_actual_collision_shield_queries'] = state['action_shield_queries']
    metrics['g1_selected_actions_requiring_collision_check'] = selected_checks
    metrics['g1_unattempted_collision_queries'] = 0
    metrics['g1_shield_query_count_valid'] = state['action_shield_queries'] == selected_checks
    unwanted_pair_fields = ('g1_unwanted_floor_contact_pairs',
        'g1_pedestrian_contact_pairs', 'g1_wall_contact_pairs',
        'g1_persistent_obstacle_contact_pairs', 'g1_self_contact_pairs')
    metrics['g1_unwanted_contact_states'] = sum(
        any(int(frame.get(key, 0)) > 0 for key in unwanted_pair_fields)
        for frame in frames)
    metrics['g1_action_counts_with_wait'] = dict(
        forward=metrics.get('g1_forward_actions', 0),
        lateral=metrics.get('g1_lateral_actions', 0),
        backward=metrics.get('g1_backward_actions', 0),
        wait=metrics.get('g1_waits', 0),
        turn=metrics.get('g1_in_place_turns', 0))
    metrics['spatial_memory_observations'] = int(metrics['observation_count'])
    metrics['unselected_action_shield_queries'] = 0
    return metrics, frames, scene


def _non_move_trace(frames):
    trace = []
    for frame in frames:
        action = frame.get('navigation_action')
        if action is None or action[0] == 'move':
            continue
        kind, value = action
        trace.append(dict(world_identity=IDENTITY, schedule_index=SCHEDULE,
            method=METHOD, step=frame['step'], position=list(frame['position']),
            heading_yaw=frame.get('heading_yaw'), action_kind=kind,
            action_value=list(value) if isinstance(value, tuple) else value,
            reason=frame.get('navigation_action_reason'),
            accepted=not frame.get('blocked', False), collision_checked=kind != 'wait'))
    return trace


def _compact_metric(metrics):
    fields = ('success', 'contact_free_success', 'elapsed_steps', 'final_position',
        'g1_unwanted_contact_states', 'g1_pedestrian_contact_pairs',
        'g1_unwanted_contact_pairs', 'spatial_memory_observations',
        'emergency_safety_scans', 'emergency_safety_raycasts',
        'emergency_safety_ray_hits', 'emergency_safety_pedestrian_ray_hits',
        'emergency_safety_interventions', 'g1_forward_actions',
        'g1_lateral_actions', 'g1_backward_actions', 'g1_waits',
        'g1_in_place_turns', 'g1_actual_collision_shield_queries',
        'g1_selected_actions_requiring_collision_check',
        'g1_unattempted_collision_queries', 'g1_shield_query_count_valid')
    return {key: metrics.get(key, 0) for key in fields}


def _diagnostic_timeline(frames, steps=(50, 51, 52, 53)):
    by_step = {frame['step']: frame for frame in frames}
    out = []
    for step in steps:
        frame = by_step.get(step)
        if frame is None:
            continue
        previous = by_step.get(step - 1, {})
        out.append({
            'step': step,
            'robot_position_before_action': list(previous.get('position', frame['position'])),
            'robot_position_after_action': list(frame['position']),
            'heading_before_action': previous.get('heading_yaw', frame.get('heading_yaw')),
            'capsule_cells_evaluator_only_after_world_advance': frame.get('g1_pedestrians', []),
            'selected_action': frame.get('navigation_action'),
            'action_reason': frame.get('navigation_action_reason'),
            'moved': bool(frame.get('moved')),
            'blocked': bool(frame.get('blocked')),
            'pedestrian_contact_pairs_after_action': int(frame.get('g1_pedestrian_contact_pairs', 0)),
            'safety_scan': frame.get('emergency_safety_scan'),
            'safety_intervention': frame.get('emergency_safety_intervention'),
        })
    return out


def run(output: Path):
    if output.exists():
        raise FileExistsError(f'Refusing to overwrite {output}')
    preserved = runner.verify_preserved_prefix()
    baseline_row, baseline_events, payload = _load_source_episode()
    config = _config()
    baseline_metrics, baseline_frames, _ = _run_episode(payload, json.loads(json.dumps(config)),
                                                        with_safety=False)
    # The rerun must reproduce the saved v3 episode before any comparison is
    # accepted. This verifies the baseline failure, not just its CSV row.
    comparisons = {
        'success': baseline_metrics['success'] == (baseline_row['success'] == 'True'),
        'elapsed_steps': int(baseline_metrics['elapsed_steps']) == int(baseline_row['elapsed_steps']),
        'pedestrian_contact_pairs': int(baseline_metrics.get('g1_pedestrian_contact_pairs', 0)) == int(baseline_row['g1_pedestrian_contact_pairs']),
        'unwanted_contact_pairs': int(baseline_metrics.get('g1_unwanted_contact_pairs', 0)) == int(baseline_row['g1_unwanted_contact_pairs']),
        'forward_actions': int(baseline_metrics['g1_forward_actions']) == int(baseline_row['g1_forward_actions']),
        'lateral_actions': int(baseline_metrics['g1_lateral_actions']) == int(baseline_row['g1_lateral_actions']),
        'spatial_memory_observations': int(baseline_metrics['observation_count']) == 1,
        'non_move_action_trace': _non_move_trace(baseline_frames) == baseline_events,
        'only_selected_shield_queries': baseline_metrics['g1_shield_query_count_valid'],
    }
    if not all(comparisons.values()):
        raise RuntimeError(f'Saved baseline replay mismatch; refusing comparison: {comparisons}')
    safety_metrics, safety_frames, _ = _run_episode(payload, json.loads(json.dumps(config)),
                                                    with_safety=True)
    # Static spatial memory must remain the initial map at every frame; the
    # emergency sensor is allowed to influence actions only through its own state.
    initial_memory = baseline_frames[0]['memory']
    safety_memory_unchanged = all(
        (frame['memory'] == initial_memory).all() for frame in safety_frames)
    if safety_metrics['observation_count'] != 1 or not safety_memory_unchanged:
        raise RuntimeError('Emergency sensing changed Static spatial memory or its budget')
    if not safety_metrics.get('g1_shield_query_count_valid'):
        raise RuntimeError('Shield query count does not match selected checked actions')

    source_files = ('episodes.csv', 'action_events.json', 'provenance.json', 'run.lock')
    report = {
        'status': 'PASS_SINGLE_EPISODE_INDEPENDENT_SAFETY_EVALUATION',
        'experiment_identity': {'world_identity': IDENTITY, 'schedule': SCHEDULE,
            'observation_policy': METHOD, 'seed': SEED, 'max_steps': config['max_steps']},
        'source_full_run': SOURCE.relative_to(ROOT).as_posix(),
        'source_file_sha256': {name: sha(SOURCE / name) for name in source_files},
        'fit_record': {'path': payload['identity'], 'payload_sha256': digest(payload)},
        'preserved_phase15_evidence': preserved,
        'baseline_replay_comparisons': comparisons,
        'baseline': _compact_metric(baseline_metrics),
        'with_independent_safety_sensor': _compact_metric(safety_metrics),
        'safety_sensor': {
            'name': 'Independent Emergency Safety Sensor',
            'range_m': 2.0, 'horizontal_fov_deg': 360.0, 'ray_count_per_scan': 181,
            'angular_spacing_deg': 2.0, 'sample_spacing_m': 0.075,
            'cadence': 'one scan after each world.advance and before observation scheduling/action selection',
            'measurements': 'MuJoCo first-hit ray intersections, hit classifications, and only ray-traversed free cells; self body excluded',
            'separate_from_spatial_memory': True,
            'spatial_memory_updates_from_safety_scan': 0,
            'future_proxy_positions_accessed': False,
            'direct_proxy_coordinates_accessed_by_controller': False,
            'proxy_motion': 'estimated from successive observed first-hit cell clusters; unknown/stopped direction expands one cardinal step conservatively',
            'shield_role': 'one final selected action check only; no unselected candidate checks',
        },
        'baseline_timeline_evaluator_diagnostic_only': _diagnostic_timeline(baseline_frames),
        'safety_timeline': _diagnostic_timeline(safety_frames),
        'static_memory_unchanged_all_frames': safety_memory_unchanged,
        'protected_source_outputs_modified': False,
        'policy_note': 'This is Static Spatial Memory + Continuous Safety Sensing, not the original Static baseline.',
        'limitations': [
            'The pedestrian is a simplified moving capsule proxy, not a human model.',
            'The result is one saved episode only and does not establish general pedestrian safety.',
            'A reachable-cell safety bound is conservative and may cause waits or detours.',
            'The ray sensor shares the simulated MuJoCo collision world as a physical sensing backend but returns only ray observations to the safety controller.',
        ],
    }
    output.mkdir(parents=True)
    (output / 'episode_comparison.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    (output / 'baseline_metrics.json').write_text(json.dumps(_compact_metric(baseline_metrics), indent=2, sort_keys=True) + '\n')
    (output / 'safety_metrics.json').write_text(json.dumps(_compact_metric(safety_metrics), indent=2, sort_keys=True) + '\n')
    trace = []
    for frame in safety_frames:
        trace.append({key: frame.get(key) for key in (
            'step', 'position', 'heading_yaw', 'navigation_action',
            'navigation_action_reason', 'moved', 'blocked', 'blocked_reason',
            'g1_pedestrians', 'g1_pedestrian_contact_pairs',
            'g1_unwanted_contact_pairs', 'emergency_safety_scan',
            'emergency_safety_intervention') if key in frame})
    (output / 'safety_episode_trace.json').write_text(json.dumps(trace, indent=2) + '\n')
    provenance = {
        'starting_commit': __import__('subprocess').run(
            ['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True,
            text=True, check=True).stdout.strip(),
        'source_hashes': {
            path: sha(ROOT / path) for path in (
                'scripts/evaluate_g1_static_independent_safety.py',
                'scripts/phase2_mujoco_navigation.py',
                'src/spatial_memory/emergency_safety.py',
                'src/spatial_memory/evaluation.py',
                'src/spatial_memory/mujoco_navigation.py',
                'src/spatial_memory/mujoco_perception.py',
                'src/spatial_memory/navigation.py')},
        'source_result_sha256': report['source_file_sha256'],
        'protected_files_rehashed': preserved['files_checked'],
    }
    (output / 'provenance.json').write_text(json.dumps(provenance, indent=2, sort_keys=True) + '\n')
    manifest = []
    for path in sorted(item for item in output.rglob('*') if item.is_file()):
        manifest.append({'path': path.relative_to(output).as_posix(),
                         'bytes': path.stat().st_size, 'sha256': sha(path)})
    (output / 'artifact_manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = run(args.output.resolve())
    print(json.dumps({'status': report['status'], 'output': str(args.output),
        'baseline': report['baseline'],
        'with_independent_safety_sensor': report['with_independent_safety_sensor']}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
