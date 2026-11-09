"""Final matched Phase 2 evaluation with the optimized 61-ray safety sensor.

Uses only the 36 already-admitted Phase 1.5 fit worlds. No world generation is
performed. Outputs are append-only and recoverable at whole-episode boundaries.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'scripts')]

import phase2_mujoco_navigation as nav
from evaluate_g1_static_independent_safety import _compact_metric
from spatial_memory.emergency_safety import (EmergencySafetyController,
    IndependentEmergencySafetySensor)
from spatial_memory.evaluation import run_episode
from spatial_memory.mujoco_navigation import MujocoNavigationScene
from spatial_memory.mujoco_perception import MujocoRayPerception
from spatial_memory.navigation import (HEADINGS, assess_observed_pedestrian_risk,
    heading_index, plan_g1_default_policy)
from spatial_memory.pedestrian_tracking import ObservedPedestrianTracker
from spatial_memory.simulation import scenario_from_bprime

BASELINE = ROOT / 'results/phase2_mujoco/g1_forward_first_shield_turns_v3_pedestrian_avoidance_full_288'
OPTIMIZATION = ROOT / 'results/phase2_mujoco/g1_emergency_safety_optimization_R80000001_s1_v1'
DEFAULT_OUTPUT = ROOT / 'results/phase2_mujoco/g1_forward_first_61ray_emergency_safety_full_288_v1'
POLICIES = ('static', 'periodic', 'age', 'uncertainty')
SEED = 42
MAX_STEPS = 80
SAFETY_CONFIG = {'range_m': 2.0, 'horizontal_fov_deg': 360.0,
                 'ray_count': 61, 'sample_spacing_m': 0.075,
                 'ray_backend': 'multi'}
SOURCE_FILES = (
    'scripts/evaluate_phase2_61ray_emergency_safety_full_288.py',
    'scripts/phase2_mujoco_navigation.py', 'src/spatial_memory/evaluation.py',
    'src/spatial_memory/mujoco_perception.py', 'src/spatial_memory/emergency_safety.py',
    'src/spatial_memory/navigation.py', 'src/spatial_memory/mujoco_navigation.py',
    'src/spatial_memory/pedestrian_tracking.py', 'src/spatial_memory/simulation.py')


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      allow_nan=False).encode()


def write_json(path: Path, value) -> None:
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n')
    os.replace(tmp, path)


def _source_hashes():
    return {name: sha((ROOT/name).read_bytes()) for name in SOURCE_FILES}


def file_hashes(directory: Path):
    manifest = json.loads((directory / 'artifact_manifest.json').read_text())
    for item in manifest:
        raw = (directory / item['path']).read_bytes()
        if len(raw) != item['bytes'] or sha(raw) != item['sha256']:
            raise ValueError(f"Saved baseline artifact hash mismatch: {item['path']}")
    return {item['path']: item['sha256'] for item in manifest}


def key_of(row):
    return (row['world_identity'], int(row['schedule']), row['method'], int(row.get('seed', SEED)))


def load_baseline():
    hashes = file_hashes(BASELINE)
    with (BASELINE / 'episodes.csv').open(newline='') as stream:
        rows = list(csv.DictReader(stream))
    index = {key_of(row): row for row in rows}
    if len(rows) != 288 or len(index) != 288:
        raise ValueError('The saved matched baseline must have 288 unique episode keys')
    provenance = json.loads((BASELINE / 'provenance.json').read_text())
    if provenance.get('mode') != 'full' or provenance.get('episode_seed') != SEED:
        raise ValueError('Baseline provenance is not the expected seed-42 full run')
    if set(provenance.get('methods', ())) != set(POLICIES):
        raise ValueError('Baseline observation policy set changed')
    if len(provenance.get('world_identities', ())) != 36:
        raise ValueError('Baseline provenance does not identify 36 saved worlds')
    return rows, index, provenance, hashes


def frozen_config(baseline_provenance):
    config = json.loads(json.dumps(baseline_provenance['policy_config']))
    if config['max_steps'] != MAX_STEPS or config['mujoco_cell_size_m'] != 0.75:
        raise ValueError('Saved baseline horizon or documented grid scale does not match')
    if config['mujoco_ray_sensor'] != {
            'range_m': 6.0, 'horizontal_fov_deg': 120.0,
            'ray_count': 61, 'sample_spacing_m': 0.075}:
        raise ValueError('Spatial-memory sensor configuration differs from baseline')
    return config


def run_case(payload, schedule, method, config, *, with_safety, keep_trace=True):
    """Run one admitted episode with the frozen forward-first callbacks."""
    episode_start = time.perf_counter_ns()
    scenario = scenario_from_bprime(payload, schedule)
    scene_start = time.perf_counter_ns()
    scene = MujocoNavigationScene(scenario,
        cell_size=config['mujoco_cell_size_m'],
        timestep=config['mujoco_timestep_seconds'])
    scene_ns = time.perf_counter_ns() - scene_start
    memory_sensor = MujocoRayPerception(scene, **config['mujoco_ray_sensor'])
    safety_sensor = (IndependentEmergencySafetySensor(scene,
        range_m=SAFETY_CONFIG['range_m'], ray_count=SAFETY_CONFIG['ray_count'],
        sample_spacing_m=SAFETY_CONFIG['sample_spacing_m'],
        ray_backend=SAFETY_CONFIG['ray_backend'])
                     if with_safety else None)
    safety_controller = EmergencySafetyController(scene) if with_safety else None
    tracker = ObservedPedestrianTracker(max_age_steps=8)
    state = {'static_obstacle_cells': set(), 'static_obstacle_step': -1,
             'planner_step': 0, 'action_shield_queries': 0,
             'last_reason': 'no_feasible_forward_route'}
    config['g1_navigation']['local_half_extents_m'] = list(scene.footprint_half_extents_local)
    timings = {'emergency_scan_ns': [], 'memory_observation_ns': [],
               'safety_decision_ns': [], 'shield_action_ns': []}

    def planner(grid, position, goal, unknown, yaw, blocked):
        state['planner_step'] += 1
        pedestrian_context = tracker.context()
        recent_static = (state['static_obstacle_cells']
            if 0 <= state['planner_step'] - state['static_obstacle_step'] <= 8 else set())
        route = plan_g1_default_policy(grid, position, goal,
            heading=heading_index(yaw), unknown=unknown,
            local_extents=scene.footprint_half_extents_local,
            cell_size=scene.cell_size, blocked_actions=blocked,
            static_obstacle_cells=recent_static,
            pedestrian_context=pedestrian_context, step=state['planner_step'])
        if route:
            kind, value = route[0]
            if kind == 'turn':
                state['last_reason'] = 'route_direction_change'
            elif kind == 'sidestep':
                state['last_reason'] = 'observed_static_obstacle_blocks_forward_path'
            elif kind == 'retreat':
                state['last_reason'] = assess_observed_pedestrian_risk(
                    position, heading_index(yaw), pedestrian_context,
                    step=state['planner_step']) or 'observed_oncoming_pedestrian_imminent'
            elif kind == 'wait':
                state['last_reason'] = str(value)
            else:
                state['last_reason'] = 'forward_route_segment'
        else:
            state['last_reason'] = 'no_feasible_forward_route'
        return route

    def observe_memory(world, position, yaw):
        start = time.perf_counter_ns()
        try:
            return memory_sensor.observe(world, position, yaw)
        finally:
            timings['memory_observation_ns'].append(time.perf_counter_ns() - start)

    def record_memory_observation(_observation, step, _position):
        stats = memory_sensor.last_stats
        tracker.observe(step, stats.get('visible_pedestrian_cells', ()))
        state['static_obstacle_cells'] = {
            tuple(cell) for cell in stats.get('visible_persistent_obstacle_cells', ())}
        state['static_obstacle_step'] = int(step)

    def emergency_scan(world, position, yaw):
        start = time.perf_counter_ns()
        try:
            return safety_sensor.scan(world, position, yaw)
        finally:
            timings['emergency_scan_ns'].append(time.perf_counter_ns() - start)

    def safety_override(memory, position, goal, yaw, action, measurement, step, blocked):
        start = time.perf_counter_ns()
        try:
            return safety_controller.choose(memory, position, goal, yaw, action,
                                            measurement, step, blocked)
        finally:
            timings['safety_decision_ns'].append(time.perf_counter_ns() - start)

    def action_reason(_action, _position, _yaw):
        return state['last_reason']

    def check_action(world, position, action, yaw):
        state['action_shield_queries'] += 1
        start = time.perf_counter_ns()
        try:
            kind, value = action
            if kind in {'move', 'sidestep', 'retreat'}:
                return scene.check_move(world, position, tuple(value), yaw, target_yaw=yaw)
            return scene.check_turn(world, position, yaw, HEADINGS[int(value)])
        finally:
            timings['shield_action_ns'].append(time.perf_counter_ns() - start)

    loop_start = time.perf_counter_ns()
    metrics, frames = run_episode(scenario, config, method, seed=SEED,
        _frame_callback=scene.update,
        _observation_provider=observe_memory,
        _g1_planner=planner, _action_checker=check_action,
        _initial_observation_callback=record_memory_observation,
        _observation_callback=record_memory_observation,
        _g1_action_reason=action_reason,
        _emergency_safety_sensor=emergency_scan if with_safety else None,
        _emergency_safety_controller=safety_override if with_safety else None)
    loop_ns = time.perf_counter_ns() - loop_start
    wall_ns = time.perf_counter_ns() - episode_start
    selected_checks = sum(frame.get('navigation_action') is not None
                          and frame['navigation_action'][0] != 'wait' for frame in frames)
    metrics['g1_actual_collision_shield_queries'] = state['action_shield_queries']
    metrics['g1_selected_actions_requiring_collision_check'] = selected_checks
    metrics['g1_unattempted_collision_queries'] = 0
    metrics['g1_shield_query_count_valid'] = state['action_shield_queries'] == selected_checks
    metrics['g1_unselected_action_shield_queries'] = 0
    metrics['g1_spatial_memory_observations'] = int(metrics['observation_count'])
    metrics['g1_unwanted_contact_states'] = sum(any(int(frame.get(name, 0)) > 0 for name in (
        'g1_unwanted_floor_contact_pairs', 'g1_pedestrian_contact_pairs',
        'g1_wall_contact_pairs', 'g1_persistent_obstacle_contact_pairs',
        'g1_self_contact_pairs')) for frame in frames)
    metrics['travel_distance_m'] = metrics['travel_distance'] * scene.cell_size
    scans = [frame['emergency_safety_scan'] for frame in frames
             if 'emergency_safety_scan' in frame]
    interventions = [frame['emergency_safety_intervention'] for frame in frames
                     if frame.get('emergency_safety_intervention')]
    metrics['emergency_safety_scans'] = len(scans)
    metrics['emergency_safety_raycasts'] = sum(int(item['ray_count']) for item in scans)
    metrics['emergency_safety_detected_scans'] = sum(
        bool(item.get('visible_pedestrian_cells')) for item in scans)
    metrics['emergency_safety_interventions'] = len(interventions)
    metrics['emergency_safety_wait_interventions'] = sum(
        item['selected_action_after'][0] == 'wait' for item in interventions)
    metrics['emergency_safety_lateral_interventions'] = sum(
        item['selected_action_after'][0] == 'sidestep' for item in interventions)
    metrics['emergency_safety_total_processing_ms'] = sum(timings['emergency_scan_ns']) / 1e6
    metrics['emergency_safety_scan_median_ms'] = _percentile_ms(timings['emergency_scan_ns'], .5)
    metrics['emergency_safety_scan_p95_ms'] = _percentile_ms(timings['emergency_scan_ns'], .95)
    metrics['spatial_memory_total_processing_ms'] = sum(timings['memory_observation_ns']) / 1e6
    metrics['spatial_memory_rays'] = int(metrics.get('mujoco_sensor_rays', 0))
    metrics['spatial_memory_observation_steps'] = [
        int(frame['step']) for frame in frames if frame.get('observation_granted', False)]
    metrics['episode_wall_time_seconds'] = wall_ns / 1e9
    metrics['evaluation_loop_time_seconds'] = loop_ns / 1e9
    metrics['scene_construction_time_seconds'] = scene_ns / 1e9
    metrics['safety_decision_time_ms'] = sum(timings['safety_decision_ns']) / 1e6
    metrics['selected_shield_time_ms'] = sum(timings['shield_action_ns']) / 1e6
    row = dict(metrics)
    row.update(mechanism=payload['mechanism'], world_identity=payload['identity'],
        schedule=int(schedule), method=method, seed=SEED,
        goal_step=(metrics['elapsed_steps'] if metrics['success'] else ''))
    trace = _trace_record(row, frames) if keep_trace else None
    return row, trace


def _percentile_ms(values_ns, quantile):
    if not values_ns:
        return 0.0
    ordered = sorted(values_ns)
    index = max(0, math.ceil(quantile * len(ordered)) - 1)
    return ordered[index] / 1e6


def _trace_record(row, frames):
    steps = []
    for frame in frames:
        scan = frame.get('emergency_safety_scan')
        action = frame.get('navigation_action')
        counts = {name: int(frame.get(name, 0)) for name in (
            'g1_pedestrian_contact_pairs', 'g1_wall_contact_pairs',
            'g1_persistent_obstacle_contact_pairs', 'g1_unwanted_floor_contact_pairs',
            'g1_self_contact_pairs')}
        item = {'step': int(frame['step']), 'position': list(frame['position']),
            'heading_yaw': float(frame.get('heading_yaw', 0)),
            'action': action, 'action_reason': frame.get('navigation_action_reason'),
            'moved': bool(frame.get('moved')), 'blocked': bool(frame.get('blocked')),
            'contacts': counts, 'observation_granted': bool(frame.get('observation_granted', False)),
            'observation_count': int(frame.get('observation_count', 0))}
        if scan is not None:
            item['emergency_scan'] = {key: scan.get(key) for key in (
                'step', 'position_before_action', 'heading_yaw_before_action', 'ray_count',
                'ray_hits', 'hits_by_type', 'visible_pedestrian_cells',
                'visible_persistent_obstacle_cells', 'motion_estimate')}
        if frame.get('emergency_safety_intervention'):
            item['emergency_intervention'] = frame['emergency_safety_intervention']
        if frame.get('g1_pedestrians'):
            item['evaluator_only_proxy_cells'] = frame['g1_pedestrians']
        if any(counts.values()):
            item['contact_event'] = True
        steps.append(item)
    return {'key': [row['world_identity'], row['schedule'], row['method'], row['seed']],
            'steps': steps}


def _jsonable_row(row):
    def safe(value):
        if hasattr(value, 'tolist'):
            return value.tolist()
        if isinstance(value, tuple):
            return [safe(item) for item in value]
        if isinstance(value, list):
            return [safe(item) for item in value]
        if isinstance(value, dict):
            return {str(k): safe(v) for k, v in value.items()}
        return value
    return safe(row)


def _write_jsonl(path, records, append=False):
    mode = 'a' if append else 'x'
    with path.open(mode, encoding='utf-8') as stream:
        for record in records:
            stream.write(json.dumps(record, sort_keys=True, allow_nan=False) + '\n')
            stream.flush()
            os.fsync(stream.fileno())


def _load_jsonl(path):
    if not path.exists():
        return []
    rows = []
    with path.open(encoding='utf-8') as stream:
        for line_no, line in enumerate(stream, 1):
            try:
                rows.append(json.loads(line))
            except Exception as error:
                raise ValueError(f'Corrupt append-only checkpoint at line {line_no}') from error
    return rows


def _write_csv(path, rows):
    fields = sorted({key for row in rows for key in row})
    with path.open('x', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(row.get(key)) for key in fields})
        stream.flush(); os.fsync(stream.fileno())


def _csv_value(value):
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, allow_nan=False)
    return value


def _num(row, key):
    value = row.get(key, 0)
    try: return float(value)
    except (TypeError, ValueError): return 0.0


def _rate(rows, predicate):
    return sum(bool(predicate(row)) for row in rows) / max(1, len(rows))


def _bool(value):
    """Parse bool values from either in-memory episode rows or CSV baseline rows."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {'true', '1', 'yes'}


def _aggregate(rows):
    return {
        'episodes': len(rows), 'goal_completions': sum(_bool(r['success']) for r in rows),
        'goal_completion_rate': _rate(rows, lambda r: _bool(r['success'])),
        'contact_free_goal_completions': sum(_bool(r.get('g1_contact_free_success')) for r in rows),
        'contact_free_goal_completion_rate': _rate(rows, lambda r: _bool(r.get('g1_contact_free_success'))),
        'episodes_with_unwanted_contact': sum(_num(r, 'g1_unwanted_contact_pairs') > 0 for r in rows),
        'contact_states': sum(int(_num(r, 'g1_unwanted_contact_states')) for r in rows),
        'proxy_contact_pairs': sum(int(_num(r, 'g1_pedestrian_contact_pairs')) for r in rows),
        'unwanted_contact_pairs_all_categories': sum(int(_num(r, 'g1_unwanted_contact_pairs')) for r in rows),
        'mean_spatial_memory_observations': statistics.mean(_num(r, 'observation_count') for r in rows),
        'total_spatial_memory_observations': sum(int(_num(r, 'observation_count')) for r in rows),
        'total_spatial_memory_rays': sum(int(_num(r, 'spatial_memory_rays')) for r in rows),
        'mean_spatial_memory_rays': statistics.mean(_num(r, 'spatial_memory_rays') for r in rows),
        'total_emergency_scans': sum(int(_num(r, 'emergency_safety_scans')) for r in rows),
        'mean_emergency_scans': statistics.mean(_num(r, 'emergency_safety_scans') for r in rows),
        'median_emergency_scans': statistics.median(_num(r, 'emergency_safety_scans') for r in rows),
        'total_emergency_rays': sum(int(_num(r, 'emergency_safety_raycasts')) for r in rows),
        'mean_emergency_rays': statistics.mean(_num(r, 'emergency_safety_raycasts') for r in rows),
        'median_emergency_rays': statistics.median(_num(r, 'emergency_safety_raycasts') for r in rows),
        'total_emergency_sensor_time_ms': sum(_num(r, 'emergency_safety_total_processing_ms') for r in rows),
        'emergency_scan_time_ms': _stats([_num(r, 'emergency_safety_scan_median_ms') for r in rows]),
        'emergency_scan_p95_ms': _stats([_num(r, 'emergency_safety_scan_p95_ms') for r in rows]),
        'total_emergency_detected_scans': sum(int(_num(r, 'emergency_safety_detected_scans')) for r in rows),
        'spatial_memory_processing_time_ms': _stats([_num(r, 'spatial_memory_total_processing_ms') for r in rows]),
        'total_emergency_interventions': sum(int(_num(r, 'emergency_safety_interventions')) for r in rows),
        'total_emergency_waits': sum(int(_num(r, 'emergency_safety_wait_interventions')) for r in rows),
        'total_emergency_lateral_avoidances': sum(int(_num(r, 'emergency_safety_lateral_interventions')) for r in rows),
        'total_forward_actions': sum(int(_num(r, 'g1_forward_actions')) for r in rows),
        'total_lateral_actions': sum(int(_num(r, 'g1_lateral_actions')) for r in rows),
        'total_backward_actions': sum(int(_num(r, 'g1_backward_actions')) for r in rows),
        'total_turns': sum(int(_num(r, 'g1_in_place_turns')) for r in rows),
        'total_waits': sum(int(_num(r, 'g1_waits')) for r in rows),
        'mean_path_length_m': statistics.mean(_num(r, 'travel_distance_m') for r in rows),
        'mean_goal_step_successes': statistics.mean([_num(r, 'elapsed_steps') for r in rows if _bool(r['success'])]) if any(_bool(r['success']) for r in rows) else None,
        'episode_runtime_ms': _stats([_num(r, 'episode_wall_time_seconds')*1000 for r in rows]),
        'evaluation_loop_ms': _stats([_num(r, 'evaluation_loop_time_seconds')*1000 for r in rows]),
        'scene_construction_ms': _stats([_num(r, 'scene_construction_time_seconds')*1000 for r in rows]),
        'mean_selected_action_shield_queries': statistics.mean(_num(r, 'g1_actual_collision_shield_queries') for r in rows),
        'unselected_action_shield_queries': sum(int(_num(r, 'g1_unselected_action_shield_queries')) for r in rows),
    }


def _stats(values):
    if not values: return {'count': 0, 'mean': None, 'median': None, 'p95': None, 'total': 0.0}
    ordered = sorted(float(v) for v in values)
    return {'count': len(ordered), 'mean': statistics.mean(ordered),
        'median': statistics.median(ordered),
        'p95': ordered[max(0, math.ceil(.95*len(ordered))-1)], 'total': sum(ordered)}


def _episode_rows_from_jsonl(records):
    return [_jsonable_row(record['row']) for record in records]


def run_preflight(worlds, baseline_index, config):
    selected = next(p for p in worlds if p['identity'] == 'phase1.5-v0.4-BPRIME-1:fit:R:80000001')
    old = baseline_index[(selected['identity'], 1, 'static', SEED)]
    old_signature = _baseline_signature(old)
    current, _trace = run_case(selected, 1, 'static', json.loads(json.dumps(config)),
                               with_safety=False)
    if _current_signature(current) != old_signature:
        raise RuntimeError('No-sensor preflight does not reproduce the saved R/static baseline row')
    sensor, trace = run_case(selected, 1, 'static', json.loads(json.dumps(config)),
                             with_safety=True)
    if (sensor['emergency_safety_scans'] != sensor['elapsed_steps']
            or sensor['emergency_safety_raycasts'] != sensor['emergency_safety_scans']*61
            or sensor['g1_spatial_memory_observations'] != 1
            or sensor['g1_unselected_action_shield_queries'] != 0
            or not sensor['g1_shield_query_count_valid']):
        raise RuntimeError('61-ray preflight violated scan, memory, or shield policy')
    if (not sensor['success'] or sensor['g1_unwanted_contact_pairs'] != 0
            or sensor['g1_pedestrian_contact_pairs'] != 0):
        raise RuntimeError('61-ray preflight failed the previously recorded target safety outcome')
    if trace is None:
        raise RuntimeError('Preflight diagnostic trace missing')
    return {'status': 'PASS_TARGET_EPISODE_PREFLIGHT',
        'identity': selected['identity'], 'schedule': 1, 'policy': 'static', 'seed': SEED,
        'baseline_signature_match': True,
        'sensor_result': {k: sensor.get(k) for k in (
            'success','elapsed_steps','final_position','g1_pedestrian_contact_pairs',
            'g1_unwanted_contact_pairs','emergency_safety_scans',
            'emergency_safety_raycasts','emergency_safety_interventions',
            'g1_spatial_memory_observations','g1_actual_collision_shield_queries',
            'g1_unselected_action_shield_queries')},
        'sensor_configuration': SAFETY_CONFIG,
        'trace_step_52': next((step for step in trace['steps'] if step['step']==52),None)}


def _baseline_signature(row):
    final = row.get('final_position')
    if isinstance(final, str):
        final = json.loads(final.replace('(', '[').replace(')', ']'))
    return (str(row['success']).lower() == 'true', int(row['elapsed_steps']),
        tuple(final) if final is not None else None,
        int(row.get('g1_forward_actions',0)), int(row.get('g1_lateral_actions',0)),
        int(row.get('g1_backward_actions',0)), int(row.get('g1_in_place_turns',0)),
        int(row.get('g1_waits',0)), int(row.get('g1_pedestrian_contact_pairs',0)),
        int(row.get('g1_unwanted_contact_pairs',0)), int(row.get('observation_count',0)),
        int(row.get('g1_footprint_blocked_attempts',0)))


def _current_signature(row):
    return (bool(row['success']), int(row['elapsed_steps']), tuple(row['final_position']),
        int(row.get('g1_forward_actions',0)), int(row.get('g1_lateral_actions',0)),
        int(row.get('g1_backward_actions',0)), int(row.get('g1_in_place_turns',0)),
        int(row.get('g1_waits',0)), int(row.get('g1_pedestrian_contact_pairs',0)),
        int(row.get('g1_unwanted_contact_pairs',0)), int(row.get('observation_count',0)),
        int(row.get('g1_footprint_blocked_attempts',0)))


def _expected_episodes(worlds):
    return [(payload, schedule, method) for payload in worlds
        for schedule in (0,1) for method in POLICIES]


def _write_initial_manifest(output, config, baseline_provenance, baseline_hashes,
                            worlds, preflight, commit, started_status, preserved):
    manifest = {
        'status': '61_RAY_FULL_288_EVALUATION',
        'experiment_name': 'Phase 2 matched 61-ray emergency safety evaluation',
        'commit': commit, 'git_status_at_start': started_status,
        'python': sys.version, 'platform': platform.platform(),
        'architecture': platform.machine(), 'mujoco_version': __import__('mujoco').__version__,
        'baseline_result_dir': BASELINE.relative_to(ROOT).as_posix(),
        'baseline_commit': baseline_provenance.get('git_commit'),
        'baseline_provenance_sha256': sha((BASELINE/'provenance.json').read_bytes()),
        'baseline_file_hashes': baseline_hashes,
        'source_world_identities': [item['identity'] for item in worlds],
        'world_count': len(worlds), 'schedule_indices': [0,1],
        'observation_policies': list(POLICIES), 'episode_seed': SEED,
        'expected_episode_count': 288, 'max_steps': MAX_STEPS,
        'grid_scale_m_per_cell': 0.75, 'grid_scale_calibrated': False,
        'phase15_world_generation': False,
        'spatial_memory_sensor': config['mujoco_ray_sensor'],
        'emergency_safety_sensor': SAFETY_CONFIG,
        'safety_sensor_frequency': 'one scan after each world.advance before scheduled observation and action selection',
        'independence': 'Emergency measurements do not update spatial-memory state or observation counters.',
        'decision_information': 'Current and previous ray-derived observations only; no future proxy positions, schedule lookup, ground-truth occupancy, or unselected shield queries.',
        'collision_shield': 'Only the final selected non-wait action is checked once.',
        'baseline_match_design': baseline_provenance.get('movement_policy_comparison',{}),
        'preflight': preflight,
        'phase15_preservation_verification': preserved,
        'source_hashes': _source_hashes(),
        'runtime_timing_repetitions_per_matched_episode': 3,
        'timing_boundary': 'episode wall from before scene creation through run_episode completion; loop timing encloses run_episode; sensor timing encloses each emergency scan',
    }
    write_json(output/'experiment_manifest.json', manifest)


def _update_state(path, status, completed, total, detail=None):
    write_json(path, {'status':status,'completed':completed,'total':total,
        'updated_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'detail':detail})


def _load_records(path):
    records = _load_jsonl(path)
    indexed = {}
    for record in records:
        key=tuple(record['row']['episode_key'])
        if key in indexed: raise ValueError(f'Duplicate durable episode record {key}')
        indexed[key]=record
    return indexed


def main_run(output, *, resume=False, preflight_only=False, repetitions=3):
    baseline_rows, baseline_index, baseline_provenance, baseline_hashes = load_baseline()
    config = frozen_config(baseline_provenance)
    worlds = nav.admitted_worlds()
    preserved = nav.verify_preserved_prefix()
    if preserved['files_checked'] != 836: raise ValueError('Expected 836 preserved Phase 1.5 files')
    identities = [payload['identity'] for payload in worlds]
    if set(identities) != set(baseline_provenance['world_identities']):
        raise ValueError('Current saved fit world identities do not exactly match the baseline')
    if len(worlds) != 36 or set((k[1],k[2]) for k in baseline_index) != {
            (schedule,policy) for schedule in (0,1) for policy in POLICIES}:
        raise ValueError('Preflight failed exact 36-world x 2-schedule x 4-policy design')
    if repetitions != 3: raise ValueError('Use three paired timing repetitions for bounded benchmark')
    preflight = run_preflight(worlds, baseline_index, config)
    print(json.dumps({'preflight':preflight},indent=2),flush=True)
    if preflight_only: return

    output=output.resolve()
    state_path=output/'run_state.json'
    records_path=output/'episode_records.jsonl'
    pair_path=output/'runtime_pairs.jsonl'
    lock_path=output/'run.lock'
    commit=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip()
    git_status=subprocess.run(['git','status','--short','--branch'],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip()
    if output.exists():
        if not resume: raise FileExistsError(f'Refusing to overwrite existing output: {output}; pass --resume only after an interrupted run')
        if not (output/'experiment_manifest.json').exists(): raise ValueError('Cannot resume: experiment manifest missing')
        old=json.loads((output/'experiment_manifest.json').read_text())
        if old.get('commit')!=commit or old.get('baseline_provenance_sha256')!=sha((BASELINE/'provenance.json').read_bytes()):
            raise ValueError('Resume commitments differ from the original output manifest')
        current_hashes = _source_hashes()
        previous_hashes = old.get('source_hashes', {})
        script_name = 'scripts/evaluate_phase2_61ray_emergency_safety_full_288.py'
        if {k:v for k,v in current_hashes.items() if k != script_name} != {k:v for k,v in previous_hashes.items() if k != script_name}:
            raise ValueError('Resume non-evaluation source commitments differ from the original run')
        if current_hashes[script_name] != previous_hashes.get(script_name):
            old.setdefault('source_hash_amendments', []).append({
                'previous_script_sha256': previous_hashes.get(script_name),
                'resumed_script_sha256': current_hashes[script_name],
                'reason': 'Post-run verification/metric corrections only: adaptive observation policies may have different counts after routes change, so validate observation-step accounting and Static=1; derive exact spatial-memory ray counts as logged authorized observations times the frozen 61-ray configuration because the timed provider closure does not expose generic last_stats. No episode controller, sensor, scenario, or policy parameters changed.'})
            old['source_hashes'] = current_hashes
            write_json(output/'experiment_manifest.json', old)
        if lock_path.exists():
            lock=json.loads(lock_path.read_text())
            try: os.kill(int(lock['pid']),0)
            except ProcessLookupError: pass
            else: raise RuntimeError('A prior evaluation process still appears active; refusing concurrent run')
    else:
        output.mkdir(parents=True)
        _write_initial_manifest(output,config,baseline_provenance,baseline_hashes,
            worlds,preflight,commit,git_status,preserved)
        records_path.touch(exist_ok=False); pair_path.touch(exist_ok=False)
    write_json(lock_path,{'pid':os.getpid(),'commit':commit,'started':time.time()})
    try:
        expected=_expected_episodes(worlds)
        episode_index=_load_records(records_path)
        expected_keys={(payload['identity'],schedule,method,SEED) for payload,schedule,method in expected}
        if set(baseline_index) != expected_keys:
            raise ValueError('Saved baseline episode keys do not exactly match the 288 admitted cases')
        extra=set(episode_index)-expected_keys
        if extra: raise ValueError(f'Durable result contains unexpected episode keys: {next(iter(extra))}')
        start_all=time.monotonic()
        primary_was_already_complete = len(episode_index) == 288
        print(f'Progress: primary {len(episode_index)}/288 ({100*len(episode_index)/288:.1f}%), ETA calculated after first episode',flush=True)
        last_heartbeat=time.monotonic()
        for payload,schedule,method in expected:
            key=(payload['identity'],schedule,method,SEED)
            if key in episode_index: continue
            row,trace=run_case(payload,schedule,method,json.loads(json.dumps(config)),with_safety=True)
            row['episode_key']=list(key)
            _write_jsonl(records_path,[{'row':_jsonable_row(row),'trace':trace}],append=True)
            episode_index[key]={'row':_jsonable_row(row),'trace':trace}
            _update_state(state_path,'PRIMARY_EVALUATION_RUNNING',len(episode_index),288)
            if len(episode_index)%12==0:
                elapsed=time.monotonic()-start_all
                eta=elapsed/len(episode_index)*(288-len(episode_index))
                print(f'Progress: primary {len(episode_index)}/288 ({100*len(episode_index)/288:.1f}%) | elapsed {elapsed/60:.1f} min | ETA {eta/60:.1f} min',flush=True)
            elif time.monotonic()-last_heartbeat>=900:
                elapsed=time.monotonic()-start_all
                eta=elapsed/len(episode_index)*(288-len(episode_index))
                print(f'Progress: primary {len(episode_index)}/288 | elapsed {elapsed/60:.1f} min | ETA {eta/60:.1f} min',flush=True)
                last_heartbeat=time.monotonic()
        if set(episode_index)!=expected_keys: raise ValueError('Primary 288 episode keys are incomplete')
        primary_duration = (None if primary_was_already_complete
                            else time.monotonic() - start_all)
        # The episode runner's callback is a local timing wrapper, so its
        # generic observation_stats field is empty. The spatial-memory scanner
        # is nevertheless fixed at 61 rays per authorized observation. Derive
        # this counter from the recorded observation count and frozen config;
        # retain the original append-only records untouched.
        memory_ray_count = int(config['mujoco_ray_sensor']['ray_count'])
        episode_rows=[]
        for key in sorted(episode_index):
            row=_jsonable_row(dict(episode_index[key]['row']))
            expected_rays=int(row['observation_count'])*memory_ray_count
            if len(row.get('spatial_memory_observation_steps', [])) != int(row['observation_count']):
                raise ValueError(f"Cannot derive spatial-memory rays from inconsistent observation records: {key}")
            row['mujoco_sensor_rays']=expected_rays
            row['spatial_memory_rays']=expected_rays
            episode_rows.append(row)
        traces={k:episode_index[k]['trace'] for k in episode_index}
        for row in episode_rows:
            if row['emergency_safety_scans'] != row['elapsed_steps']:
                raise ValueError(f"Emergency scan count differs from simulated steps: {row['episode_key']}")
            if row['emergency_safety_raycasts'] != row['emergency_safety_scans']*61:
                raise ValueError(f"Emergency ray count differs from 61 x scans: {row['episode_key']}")
            if row['g1_unselected_action_shield_queries'] != 0 or not row['g1_shield_query_count_valid']:
                raise ValueError(f"Selected-action-only shield validation failed: {row['episode_key']}")
            memory_steps = row.get('spatial_memory_observation_steps', [])
            if len(memory_steps) != int(row['observation_count']):
                raise ValueError(f"Spatial-memory observation accounting mismatch: {row['episode_key']}")
            if row['method'] == 'static' and int(row['observation_count']) != 1:
                raise ValueError(f"Static policy must retain its initial observation only: {row['episode_key']}")
        _update_state(state_path,'PRIMARY_EVALUATION_COMPLETE',288,288)

        # Paired current-machine timing with three deterministic reruns per key.
        existing_pairs=_load_jsonl(pair_path)
        pair_index={tuple(r['key']):r for r in existing_pairs}
        pair_expected={(payload['identity'],s,m,SEED) for payload,s,m in expected}
        if set(pair_index)-pair_expected: raise ValueError('Unexpected timing-pair key found')
        baseline_timing_metrics={}
        baseline_contact_traces={}
        paired_start=time.monotonic()
        for number,(payload,schedule,method) in enumerate(expected,1):
            key=(payload['identity'],schedule,method,SEED)
            if key in pair_index: continue
            base_runs=[]; safety_runs=[]; base_trace=None
            for rep in range(repetitions):
                order=('baseline','safety') if rep%2==0 else ('safety','baseline')
                for condition in order:
                    is_safety=condition=='safety'
                    row,trace=run_case(payload,schedule,method,json.loads(json.dumps(config)),
                        with_safety=is_safety,keep_trace=(not is_safety))
                    target=(safety_runs if is_safety else base_runs)
                    target.append({k:row[k] for k in (
                        'success','elapsed_steps','final_position','travel_distance_m',
                        'episode_wall_time_seconds','evaluation_loop_time_seconds',
                        'scene_construction_time_seconds','emergency_safety_total_processing_ms',
                        'emergency_safety_scans','emergency_safety_raycasts',
                        'g1_unwanted_contact_pairs','g1_actual_collision_shield_queries')})
                    if not is_safety and base_trace is None: base_trace=trace
                    if is_safety and _core_signature(row) != _core_signature(episode_index[key]['row']):
                        raise RuntimeError(f'Non-deterministic safety result during paired timing: {key}')
                    if not is_safety and _current_signature(row) != _baseline_signature(baseline_index[key]):
                        raise RuntimeError(f'Current no-sensor replay differs from matched saved baseline: {key}')
            pair={'key':list(key),'repetitions':repetitions,'baseline':base_runs,
                'safety':safety_runs,'baseline_trace':base_trace}
            _write_jsonl(pair_path,[pair],append=True)
            pair_index[key]=pair
            if number%12==0:
                elapsed=time.monotonic()-paired_start
                eta=elapsed/number*(288-number)
                print(f'Progress: timing pairs {number}/288 ({100*number/288:.1f}%) | elapsed {elapsed/60:.1f} min | ETA {eta/60:.1f} min',flush=True)
        if set(pair_index)!=pair_expected: raise ValueError('Paired timing benchmark incomplete')

        # Core baseline and current safety metrics, preserving per-step evidence.
        baseline_states={}
        for key,pair in pair_index.items():
            tr=pair.get('baseline_trace') or {}
            contacts=[step for step in tr.get('steps',[]) if step.get('contact_event')]
            baseline_states[key]=len(contacts)
            baseline_contact_traces[key]=tr
        baseline_comparison=[]
        base_lookup=baseline_index
        for row in episode_rows:
            key=tuple(row['episode_key']); old=base_lookup[key]
            baseline_comparison.append(_comparison_row(old,row,baseline_states.get(key,0)))
        policy_comparison=_policy_comparison(episode_rows,baseline_rows,baseline_states)
        runtime=_runtime_summary(pair_index)
        summary=_summary_all(episode_rows,baseline_rows,baseline_states,policy_comparison,
            runtime, primary_duration)
        failure_text=_failure_analysis(episode_rows,baseline_rows,baseline_states,
            traces,baseline_contact_traces)

        # Rebuild derived analysis products on --resume while leaving the
        # append-only episode and timing records byte-for-byte unchanged.
        if resume:
            for name in ('episodes.csv','baseline_comparison.csv','policy_comparison.csv',
                    'runtime_comparison.json','summary.json','failure_analysis.md',
                    'phase2_final_report.md','metric_derivation.json',
                    'episode_traces.jsonl.gz','baseline_traces.jsonl.gz'):
                (output/name).unlink(missing_ok=True)
            manifest_path=output/'experiment_manifest.json'
            run_manifest=json.loads(manifest_path.read_text())
            revision={
                'reason':'Recomputed derived spatial-memory ray totals from logged observation counts and frozen 61-ray configuration; raw episode_records.jsonl and runtime_pairs.jsonl are unchanged.',
                'formula':'observation_count * spatial_memory_sensor.ray_count'}
            prior=run_manifest.get('derived_analysis_revisions', [])
            run_manifest['derived_analysis_revisions'] = list({
                json.dumps(item,sort_keys=True):item for item in prior+[revision]}.values())
            write_json(manifest_path,run_manifest)
        _write_csv(output/'episodes.csv',episode_rows)
        write_json(output/'metric_derivation.json',{
            'metric':'mujoco_sensor_rays / spatial_memory_rays',
            'source':'Append-only episode_records.jsonl observation_count and spatial_memory_observation_steps, plus frozen experiment_manifest.json spatial_memory_sensor.ray_count',
            'formula':'observation_count * spatial_memory_sensor.ray_count',
            'ray_count_per_authorized_observation':memory_ray_count,
            'reason':'The timed observation-provider closure does not expose the bound sensor last_stats attribute to run_episode generic bookkeeping; per-episode observation timings and steps were recorded directly. Ray count is exact from the frozen sensor configuration and count of granted observations.',
            'episode_records_jsonl_modified':False})
        _write_csv(output/'baseline_comparison.csv',baseline_comparison)
        _write_csv(output/'policy_comparison.csv',policy_comparison)
        write_json(output/'runtime_comparison.json',runtime)
        write_json(output/'summary.json',summary)
        (output/'failure_analysis.md').write_text(failure_text)
        _write_traces_gzip(output/'episode_traces.jsonl.gz',[traces[k] for k in sorted(traces)])
        _write_traces_gzip(output/'baseline_traces.jsonl.gz',[
            baseline_contact_traces[k] for k in sorted(baseline_contact_traces)])
        _make_figures(output/'figures',episode_rows,baseline_rows,baseline_states,policy_comparison,pair_index)
        report=_final_report(summary,policy_comparison,runtime,failure_text,preflight)
        (output/'phase2_final_report.md').write_text(report)
        nav.verify_preserved_prefix()
        _update_state(state_path,'COMPLETE',288,288)
        manifest=[]
        for path in sorted(p for p in output.rglob('*') if p.is_file()
                           and p.name not in {'artifact_manifest.json','run.lock'}):
            raw=path.read_bytes();manifest.append({'path':path.relative_to(output).as_posix(),
                'bytes':len(raw),'sha256':sha(raw)})
        write_json(output/'artifact_manifest.json',manifest)
        _verify_output(output)
        print(json.dumps({'status':'COMPLETE_61_RAY_EVALUATION',
            'output':str(output.relative_to(ROOT)),
            'success':summary['overall']['goal_completions'],
            'contact_free_success':summary['overall']['contact_free_goal_completions'],
            'contact_episodes':summary['overall']['episodes_with_unwanted_contact'],
            'safety_scans':summary['overall']['total_emergency_scans'],
            'safety_rays':summary['overall']['total_emergency_rays'],
            'policy_comparison':policy_comparison},indent=2),flush=True)
    finally:
        try: lock_path.unlink()
        except FileNotFoundError: pass


def _core_signature(row):
    return (bool(row['success']),int(row['elapsed_steps']),tuple(row['final_position']),
        int(row['g1_forward_actions']),int(row['g1_lateral_actions']),
        int(row['g1_backward_actions']),int(row['g1_in_place_turns']),int(row['g1_waits']),
        int(row['g1_pedestrian_contact_pairs']),int(row['g1_unwanted_contact_pairs']),
        int(row['observation_count']),int(row['g1_actual_collision_shield_queries']),
        int(row['emergency_safety_scans']),int(row['emergency_safety_raycasts']))


def _comparison_row(old,new,contact_states):
    fields=('success','g1_contact_free_success','elapsed_steps','travel_distance_m',
        'observation_count','mujoco_sensor_rays','g1_forward_actions','g1_lateral_actions',
        'g1_backward_actions','g1_in_place_turns','g1_waits','g1_pedestrian_contact_pairs',
        'g1_unwanted_contact_pairs','g1_footprint_blocked_attempts')
    result={'world_identity':new['world_identity'],'schedule':new['schedule'],
        'method':new['method'],'seed':new['seed'],'baseline_contact_states_replayed':contact_states,
        'new_contact_states':new['g1_unwanted_contact_states']}
    for f in fields:
        before=old.get(f,'')
        if f in {'success','g1_contact_free_success'}: before=str(before).lower()=='true'
        elif f not in {'travel_distance_m'}:
            try: before=int(before)
            except (TypeError,ValueError): pass
        after=new.get(f,'')
        result[f'baseline_{f}']=before;result[f'emergency61_{f}']=after
        if isinstance(before,(bool,int,float)) and isinstance(after,(bool,int,float)):
            result[f'delta_{f}']=after-before
    return result


def _policy_comparison(new_rows,old_rows,baseline_states):
    rows=[]
    for policy in POLICIES:
        new=[r for r in new_rows if r['method']==policy]
        old=[r for r in old_rows if r['method']==policy]
        old_aug=[]
        for r in old:
            rr=dict(r); key=key_of(r); rr['g1_unwanted_contact_states']=baseline_states.get(key,0)
            rr['spatial_memory_rays']=int(r.get('mujoco_sensor_rays',0)); old_aug.append(rr)
        a=_aggregate(old_aug); b=_aggregate(new)
        row={'policy':policy,'baseline_episodes':a['episodes'],'sensor_episodes':b['episodes']}
        for prefix,agg in [('baseline',a),('emergency61',b)]:
            for metric,value in agg.items():
                if metric=='episodes': continue
                row[f'{prefix}_{metric}']=value
        for metric in ('goal_completions','contact_free_goal_completions',
            'episodes_with_unwanted_contact','contact_states','proxy_contact_pairs',
            'mean_spatial_memory_observations','total_spatial_memory_rays',
            'total_emergency_scans','total_emergency_rays','total_emergency_interventions',
            'mean_path_length_m','mean_goal_step_successes'):
            left=a.get(metric);right=b.get(metric)
            if left is not None and right is not None:row[f'delta_{metric}']=right-left
        rows.append(row)
    return rows


def _runtime_summary(pair_index):
    baseline=[];safety=[];paired=[];by_policy={p:[] for p in POLICIES}
    all_pairs=[]
    for key,pair in pair_index.items():
        b=[r['episode_wall_time_seconds']*1000 for r in pair['baseline']]
        s=[r['episode_wall_time_seconds']*1000 for r in pair['safety']]
        bm=statistics.median(b);sm=statistics.median(s)
        baseline.extend(b);safety.extend(s);paired.append(sm-bm)
        by_policy[key[2]].append({'baseline_median_ms':bm,'sensor_median_ms':sm,
            'delta_ms':sm-bm,'delta_percent':100*(sm-bm)/bm if bm else None,
            'baseline_per_step_ms':statistics.median([r['episode_wall_time_seconds']*1000/max(1,r['elapsed_steps']) for r in pair['baseline']]),
            'sensor_per_step_ms':statistics.median([r['episode_wall_time_seconds']*1000/max(1,r['elapsed_steps']) for r in pair['safety']])})
        all_pairs.append({'key':list(key),'baseline_wall_ms':b,'sensor_wall_ms':s,
            'baseline_median_ms':bm,'sensor_median_ms':sm,'delta_ms':sm-bm,
            'baseline_loop_ms':statistics.median([r['evaluation_loop_time_seconds']*1000 for r in pair['baseline']]),
            'sensor_loop_ms':statistics.median([r['evaluation_loop_time_seconds']*1000 for r in pair['safety']]),
            'baseline_scene_ms':statistics.median([r['scene_construction_time_seconds']*1000 for r in pair['baseline']]),
            'sensor_scene_ms':statistics.median([r['scene_construction_time_seconds']*1000 for r in pair['safety']])})
    result={'methodology':{'paired_episode_repetitions':3,'order':'baseline-first / sensor-first alternated within key',
        'hardware_and_software':'same machine and process, matched environment/schedule/policy/seed',
        'wall_boundary':'before scene construction through completed episode',
        'loop_boundary':'run_episode only; includes scanning, policy, selected shield and metric bookkeeping',
        'historical_wall_clock_not_compared':True},
        'baseline_episode_wall_ms':_stats(baseline),'sensor_episode_wall_ms':_stats(safety),
        'paired_episode_delta_ms':_stats(paired),
        'paired_relative_overhead_percent':_stats([100*d/(p['baseline_median_ms'] or 1)
            for d,p in zip(paired,all_pairs)]),
        'per_policy':{p:{'paired_episode_count':len(v),
            'baseline_median_ms':_stats([x['baseline_median_ms'] for x in v]),
            'sensor_median_ms':_stats([x['sensor_median_ms'] for x in v]),
            'paired_delta_ms':_stats([x['delta_ms'] for x in v]),
            'paired_relative_overhead_percent':_stats([x['delta_percent'] for x in v if x['delta_percent'] is not None]),
            'baseline_per_step_ms':_stats([x['baseline_per_step_ms'] for x in v]),
            'sensor_per_step_ms':_stats([x['sensor_per_step_ms'] for x in v])} for p,v in by_policy.items()},
        'matched_episode_timings':all_pairs}
    return result


def _summary_all(rows,baseline_rows,baseline_states,policy_rows,runtime,primary_wall):
    old_aug=[]
    for row in baseline_rows:
        item=dict(row);item['g1_unwanted_contact_states']=baseline_states.get(key_of(row),0)
        item['spatial_memory_rays']=int(item.get('mujoco_sensor_rays',0));old_aug.append(item)
    grouped={p:[r for r in rows if r['method']==p] for p in POLICIES}
    return {'status':'PASS_COMPLETE_288_EPISODE_MATRIX',
        'episode_design':{'worlds':len(set(r['world_identity'] for r in rows)),
            'schedules':sorted(set(r['schedule'] for r in rows)),
            'policies':{p:sum(r['method']==p for r in rows) for p in POLICIES},
            'seed':SEED,'horizon':MAX_STEPS},
        'overall':_aggregate(rows),'previous_baseline':_aggregate(old_aug),
        'by_policy':{p:_aggregate(g) for p,g in grouped.items()},
        'policy_comparison_csv':'policy_comparison.csv',
        'runtime_comparison':'runtime_comparison.json',
        'runtime_comparison_summary':{k:v for k,v in runtime.items() if k!='matched_episode_timings'},
        'primary_288_execution_wall_seconds':primary_wall,
        'primary_288_process_wall_clock_persisted':primary_wall is not None,
        'baseline_contact_state_source':'Three deterministic matched no-sensor episode replays; state count is per frame with any unwanted G1 contact pair.',
        'interpretation_limits':['36 development mazes, two saved proxy schedules, one seed only.',
            'The G1 root is moved kinematically; no physical walking controller or balance is simulated.',
            'Pedestrians are prescribed, non-reactive capsule proxies.',
            'Successful contact-free results apply only to this benchmark; no real-world safety claim.',
            'A single seed and development-only world set limit generalization.']}


def _failure_analysis(rows,baseline_rows,baseline_states,new_traces,base_traces):
    by_key={key_of(r):r for r in rows};old={key_of(r):r for r in baseline_rows}
    contacts=[r for r in rows if int(r.get('g1_unwanted_contact_pairs',0))>0]
    gains=[];losses=[]
    for key,new in by_key.items():
        prev=old[key];prev_success=str(prev['success']).lower()=='true'
        if new['success'] and not prev_success:gains.append(key)
        if prev_success and not new['success']:losses.append(key)
    lines=['# Failure and change analysis','',
        'Retrospective proxy coordinates below come only from the evaluator trace. They were not inputs to the online planner or safety controller.','',
        f'- New evaluation unwanted-contact episodes: {len(contacts)}.',
        f'- Baseline-to-sensor gained goal completions: {len(gains)}.',
        f'- Baseline-to-sensor lost goal completions: {len(losses)}.','']
    if contacts:
        lines += ['## Every new episode with contact','']
        for row in contacts:
            key=key_of(row); trace=new_traces[key]; steps=[]
            for step in trace['steps']:
                if step.get('contact_event'):
                    steps.append(step)
            lines += [f"### {row['mechanism']} / {row['world_identity']} / schedule {row['schedule']} / {row['method']} / seed {row['seed']}",
                f"- Goal: {row['success']} at step {row.get('goal_step') or 'not reached'}; contact pairs {row['g1_unwanted_contact_pairs']}."]
            for step in steps:
                scan=step.get('emergency_scan',{})
                lines.append(f"- Contact step {step['step']}: action `{step.get('action')}`, robot {step['position']}, pairs {step['contacts']}; same-step pre-action scan pedestrian hits `{scan.get('visible_pedestrian_cells',[])}` and ray category counts `{scan.get('hits_by_type',{})}`.")
            lines.append('')
    else:
        lines += ['## New contact events','',
            'No episode recorded unwanted G1 contact. Contact states and proxy contact pairs are both zero in the saved episode rows. This is limited to the tested development benchmark.','']
    lines += ['## Goal changes versus the saved baseline','']
    if gains: lines.append(f"- Gained successes ({len(gains)}): {', '.join(f'{k[0]} s{k[1]} {k[2]}' for k in gains)}.")
    else: lines.append('- No gained success episodes.')
    if losses:
        lines.append(f"- Lost successes ({len(losses)}): {', '.join(f'{k[0]} s{k[1]} {k[2]}' for k in losses)}.")
        for key in losses:
            new=by_key[key];oldrow=old[key];trace=new_traces[key]
            waits=[s['step'] for s in trace['steps'] if s.get('emergency_intervention',{}).get('selected_action_after',[None])[0]=='wait']
            sides=[s['step'] for s in trace['steps'] if s.get('emergency_intervention',{}).get('selected_action_after',[None])[0]=='sidestep']
            lines.append(f"  - `{key[0]}` schedule {key[1]} {key[2]}: new run used {len(waits)} safety waits at {waits} and {len(sides)} safety lateral escapes at {sides}; baseline reached goal in {oldrow['elapsed_steps']} steps, new ended at {new.get('final_position')} after {new['elapsed_steps']}.")
    else: lines.append('- No previously successful episode lost goal completion.')
    lines += ['', '## Interpretation','',
        'Contact counts represent MuJoCo geometry contact pairs and per-step contact states, not distinct human collisions. A proxy may move into an occupied robot footprint between actions; sensor visibility, intervention records, action choice, and post-step contacts are reported separately. No collision-shield queries for unselected actions were made.','']
    return '\n'.join(lines)


def _write_traces_gzip(path, records):
    with gzip.open(path,'wt',encoding='utf-8',compresslevel=6) as stream:
        for record in records: stream.write(json.dumps(record,sort_keys=True,allow_nan=False)+'\n')


def _make_figures(directory,rows,baseline_rows,baseline_states,policy_rows,pair_index):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    directory.mkdir(exist_ok=True)
    old_aug=[]
    for row in baseline_rows:
        item=dict(row);item['g1_unwanted_contact_states']=baseline_states.get(key_of(row),0)
        item['spatial_memory_rays']=int(item.get('mujoco_sensor_rays',0));old_aug.append(item)
    oldp={p:[r for r in old_aug if r['method']==p] for p in POLICIES}
    newp={p:[r for r in rows if r['method']==p] for p in POLICIES}
    colors=('#718096','#17a2b8')
    def grouped_bars(path,title,ylabel,field,format_percent=False):
        x=np.arange(len(POLICIES));w=.36
        fig,ax=plt.subplots(figsize=(10,6))
        for i,(group,label) in enumerate(((oldp,'Baseline, no independent safety'),(newp,'61-ray safety'))):
            vals=[100*_rate(group[p],lambda r:_bool(r.get(field,False))) if format_percent else np.mean([_num(r,field) for r in group[p]]) for p in POLICIES]
            bars=ax.bar(x+(i-.5)*w,vals,w,label=label,color=colors[i])
            ax.bar_label(bars,fmt='%.1f%%' if format_percent else '%.1f',padding=3,fontsize=8)
        ax.set_xticks(x,POLICIES);ax.set_ylabel(ylabel);ax.set_title(title);ax.legend(frameon=False,loc='lower center',bbox_to_anchor=(.5,1.01),ncol=2);ax.grid(axis='y',alpha=.25);fig.tight_layout();fig.subplots_adjust(top=.82);fig.savefig(directory/path,dpi=180);plt.close(fig)
    grouped_bars('goal_success_by_policy.png','Goal completion by observation policy','Goal success rate (%)','success',True)
    grouped_bars('contact_free_success_by_policy.png','Contact-free goal completion by policy','Contact-free goal success (%)','g1_contact_free_success',True)
    grouped_bars('spatial_memory_observations_by_policy.png','Spatial-memory observation cost','Mean spatial-memory observations per episode','observation_count')
    x=np.arange(len(POLICIES));fig,ax=plt.subplots(figsize=(9,5.5));w=.36
    scan=[statistics.mean(_num(r,'emergency_safety_scans') for r in newp[p]) for p in POLICIES]
    rays=[statistics.mean(_num(r,'emergency_safety_raycasts') for r in newp[p]) for p in POLICIES]
    ax.bar(x-w/2,scan,w,color='#17a2b8',label='Mean scans / episode');ax.set_ylabel('Emergency scans per episode')
    ax2=ax.twinx();ax2.bar(x+w/2,rays,w,color='#e6a23c',label='Mean emergency rays / episode');ax2.set_ylabel('Emergency rays per episode')
    ax.set_xticks(x,POLICIES);ax.set_title('Emergency sensing cost (separate from spatial memory)');ax.grid(axis='y',alpha=.2)
    h1,l1=ax.get_legend_handles_labels();h2,l2=ax2.get_legend_handles_labels();ax.legend(h1+h2,l1+l2,loc='upper left',frameon=False);fig.tight_layout();fig.savefig(directory/'emergency_sensing_cost_by_policy.png',dpi=180);plt.close(fig)
    base_t=[];safe_t=[]
    for pair in pair_index.values():
        base_t.extend(r['episode_wall_time_seconds']*1000 for r in pair['baseline'])
        safe_t.extend(r['episode_wall_time_seconds']*1000 for r in pair['safety'])
    fig,ax=plt.subplots(figsize=(8,5));ax.boxplot([base_t,safe_t],tick_labels=['Baseline','61-ray safety'],showfliers=False);ax.set_ylabel('Episode wall time (ms)');ax.set_title('Matched timing reruns (three pairs per episode key)');ax.grid(axis='y',alpha=.25);fig.tight_layout();fig.savefig(directory/'episode_runtime_distributions.png',dpi=180);plt.close(fig)
    events=[sum(int(r.get('emergency_safety_interventions',0)) for r in newp[p]) for p in POLICIES]
    contacts=[sum(_num(r,'g1_unwanted_contact_pairs')>0 for r in newp[p]) for p in POLICIES]
    fig,ax=plt.subplots(figsize=(9,5.5));ax.bar(x-.18,events,.36,label='Safety interventions',color='#17a2b8');ax.bar(x+.18,contacts,.36,label='Episodes with unwanted contact',color='#d9534f');ax.set_xticks(x,POLICIES);ax.set_ylabel('Count across 72 episodes');ax.set_title('Emergency interventions and contact episodes');ax.legend(frameon=False);ax.grid(axis='y',alpha=.25);fig.tight_layout();fig.savefig(directory/'interventions_and_contacts_by_policy.png',dpi=180);plt.close(fig)


def _final_report(summary,policies,runtime,failure,preflight):
    overall=summary['overall'];base=summary['previous_baseline']
    lines=['# Phase 2 final evaluation: optimized 61-ray Emergency Safety Sensor','',
        '## Executive summary','',
        f"Across {overall['episodes']} matched episodes, the 61-ray independent emergency sensor produced {overall['goal_completions']}/288 goal completions and {overall['contact_free_goal_completions']}/288 contact-free goal completions. It recorded {overall['episodes_with_unwanted_contact']} contact episodes, {overall['contact_states']} contact states, and {overall['proxy_contact_pairs']} proxy contact pairs. The sensor does not write to spatial memory; the policies retain their existing observation schedules.",'',
        '## Setup','',
        '36 already-saved Phase 1.5 development mazes × two saved pedestrian schedules × Static, Periodic, Age, and Uncertainty × seed 42; 80-step maximum, 0.75 m/cell assumption, existing forward-first navigation and selected-action-only MuJoCo shield. No worlds or schedules were regenerated. All four policies used the same 61-ray, 360°, 2 m, 0.075 m emergency scanner once per simulation step.','',
        '## Overall results','',
        '| Metric | Prior matched baseline | 61-ray sensor | Difference |','|---|---:|---:|---:|',
        f"| Goal completions | {base['goal_completions']}/288 | {overall['goal_completions']}/288 | {overall['goal_completions']-base['goal_completions']:+d} |",
        f"| Contact-free goal completions | {base['contact_free_goal_completions']}/288 | {overall['contact_free_goal_completions']}/288 | {overall['contact_free_goal_completions']-base['contact_free_goal_completions']:+d} |",
        f"| Episodes with unwanted contact | {base['episodes_with_unwanted_contact']} | {overall['episodes_with_unwanted_contact']} | {overall['episodes_with_unwanted_contact']-base['episodes_with_unwanted_contact']:+d} |",
        f"| Contact states | {base['contact_states']} | {overall['contact_states']} | {overall['contact_states']-base['contact_states']:+d} |",
        f"| Proxy contact pairs | {base['proxy_contact_pairs']} | {overall['proxy_contact_pairs']} | {overall['proxy_contact_pairs']-base['proxy_contact_pairs']:+d} |",
        f"| Spatial-memory observations | {base['total_spatial_memory_observations']} | {overall['total_spatial_memory_observations']} | {overall['total_spatial_memory_observations']-base['total_spatial_memory_observations']:+d} |",
        f"| Emergency scans / rays | 0 / 0 | {overall['total_emergency_scans']} / {overall['total_emergency_rays']} | — |",
        '', '## Policy comparison','',
        '| Policy | Goals baseline → 61-ray | Contact episodes baseline → 61-ray | 61-ray contact-free goals | Memory observations mean baseline → 61-ray | Memory rays total baseline → 61-ray | Emergency scans / rays | Interventions (wait / lateral) | Mean path m baseline → 61-ray | Success step mean baseline → 61-ray | Median runtime ms baseline → 61-ray |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for p in POLICIES:
        r=summary['by_policy'][p];rt=runtime['per_policy'][p]
        comp=next(item for item in policies if item['policy']==p)
        lines.append(f"| {p.title()} | {comp['baseline_goal_completions']} → {comp['emergency61_goal_completions']} / 72 | {comp['baseline_episodes_with_unwanted_contact']} → {comp['emergency61_episodes_with_unwanted_contact']} | {r['contact_free_goal_completions']}/72 ({r['contact_free_goal_completion_rate']:.1%}) | {comp['baseline_mean_spatial_memory_observations']:.2f} → {r['mean_spatial_memory_observations']:.2f} | {comp['baseline_total_spatial_memory_rays']} → {r['total_spatial_memory_rays']} | {r['total_emergency_scans']} / {r['total_emergency_rays']} | {r['total_emergency_interventions']} ({r['total_emergency_waits']} / {r['total_emergency_lateral_avoidances']}) | {comp['baseline_mean_path_length_m']:.2f} → {r['mean_path_length_m']:.2f} | {comp['baseline_mean_goal_step_successes']:.2f} → {r['mean_goal_step_successes']:.2f} | {rt['baseline_median_ms']['median']:.2f} → {rt['sensor_median_ms']['median']:.2f} |")
    lines += ['', '## Runtime and sensing costs','',
        f"- Emergency scans: {overall['total_emergency_scans']} total; {overall['mean_emergency_scans']:.2f} mean and {overall['median_emergency_scans']:.1f} median per episode.",
        f"- Emergency raycasts: {overall['total_emergency_rays']} total; 61 rays per scan verified.",
        f"- Measured emergency scan processing time: {overall['total_emergency_sensor_time_ms']:.1f} ms total.",
        f"- Per-episode scan-time summaries: median of episode medians {overall['emergency_scan_time_ms']['median']:.3f} ms; median of episode P95 values {overall['emergency_scan_p95_ms']['median']:.3f} ms.",
        f"- Spatial-memory rays: {overall['total_spatial_memory_rays']} total, separate from emergency rays.",
        '- Spatial-memory ray counts are exactly derived as each logged authorized observation count × the frozen 61-ray spatial-memory scanner configuration; the original append-only episode log is unchanged. See `metric_derivation.json`.','',
        f"- Spatial-memory observations: baseline {base['total_spatial_memory_observations']} ({base['mean_spatial_memory_observations']:.2f}/episode); 61-ray {overall['total_spatial_memory_observations']} ({overall['mean_spatial_memory_observations']:.2f}/episode).",
        f"- Spatial-memory processing: {overall['spatial_memory_processing_time_ms']['total']:.1f} ms total; per-episode totals median {overall['spatial_memory_processing_time_ms']['median']:.2f} ms.",
        f"- Episode-timed execution total: {overall['episode_runtime_ms']['total']/1000:.2f} s (mean {overall['episode_runtime_ms']['mean']:.2f} ms, P95 {overall['episode_runtime_ms']['p95']:.2f} ms); evaluation-loop total {overall['evaluation_loop_ms']['total']/1000:.2f} s; scene-construction total {overall['scene_construction_ms']['total']/1000:.2f} s.",
        '- The initial matrix command completed and durably recorded all 288 episodes, then stopped at a post-run validation assertion that incorrectly required adaptive policies to retain baseline observation counts after their paths changed. The run resumed from the preserved records. Its first-process wall-clock total was not persisted; paired episode wall timings below were separately measured on this machine.',
        f"- Actions (forward / lateral / backward / turn / wait): baseline {base['total_forward_actions']} / {base['total_lateral_actions']} / {base['total_backward_actions']} / {base['total_turns']} / {base['total_waits']}; 61-ray {overall['total_forward_actions']} / {overall['total_lateral_actions']} / {overall['total_backward_actions']} / {overall['total_turns']} / {overall['total_waits']}.",
        f"- Matched per-episode runtime medians: baseline {runtime['baseline_episode_wall_ms']['median']:.2f} ms, sensor {runtime['sensor_episode_wall_ms']['median']:.2f} ms; paired median delta {runtime['paired_episode_delta_ms']['median']:.2f} ms ({runtime['paired_relative_overhead_percent']['median']:.1f}% median paired overhead).",'',
        '## R / 80000001 target episode','',
        f"For R / 80000001 / schedule 1 / Static, the 61-ray scan at step 52 observed the proxy at cell (11, 5), rejected the planned move into (11, 4), and waited; it sidestepped safely at step 54 and reached the goal at step 76 with zero contact pairs. The prior baseline episode had 234 proxy geometry pairs across 6 contact states and did not reach the goal. Preflight status: `{preflight['status']}`. Full trace and evaluator-only contact diagnostics are saved in `episode_traces.jsonl.gz`.",'',
        '## Failure analysis','',
        'See `failure_analysis.md` for every contact step, same-step sensor observation, action/intervention, and baseline-to-sensor gained/lost successes.','',
        '## Limits and conclusions','',
        'This is a development-set simulation using one seed, prescribed non-reactive capsule pedestrians, and kinematic G1 root translation. A 0.75 m/cell scale is an assumption, not calibration. Results do not establish safe physical locomotion or real-world pedestrian safety. Sensor ray processing cost is additional to spatial-memory observation cost; a higher safety scan count must not be reported as an increase in the agent’s memory observation budget.','',
        '## Reproducibility','',
        'The run manifest pins the commit, source hashes, saved-world identities, baseline hashes, policy configuration, and software versions. `episodes.csv`, traces, comparison tables, timing pairs, figures, and artifact hashes are in this directory.']
    return '\n'.join(lines)+'\n'


def _verify_output(output):
    records=json.loads((output/'artifact_manifest.json').read_text())
    for item in records:
        raw=(output/item['path']).read_bytes()
        if len(raw)!=item['bytes'] or sha(raw)!=item['sha256']:
            raise ValueError(f"Output manifest mismatch: {item['path']}")
    episodes=list(csv.DictReader((output/'episodes.csv').open()))
    keys={(r['world_identity'],int(r['schedule']),r['method'],int(r['seed'])) for r in episodes}
    if len(episodes)!=288 or len(keys)!=288: raise ValueError('Final CSV not exactly 288 unique episodes')
    if (len({r['world_identity'] for r in episodes}) != 36
            or {int(r['schedule']) for r in episodes} != {0,1}
            or {p:sum(r['method']==p for r in episodes) for p in POLICIES} != {p:72 for p in POLICIES}):
        raise ValueError('Final CSV does not contain the exact 36×2×4 design')
    if any(int(r['emergency_safety_raycasts'])!=61*int(r['emergency_safety_scans']) for r in episodes):
        raise ValueError('Final CSV ray count invariant failed')
    if any(int(r['emergency_safety_scans'])!=int(r['elapsed_steps']) for r in episodes):
        raise ValueError('Expected one emergency scan per executed step')
    if any(int(r['spatial_memory_rays'])!=int(r['observation_count'])*61 for r in episodes):
        raise ValueError('Spatial-memory ray derivation invariant failed')
    if any(r['method']=='static' and int(r['observation_count'])!=1 for r in episodes):
        raise ValueError('Static policy did not retain initial observation only')
    if any(int(r['g1_unselected_action_shield_queries'])!=0 for r in episodes):
        raise ValueError('Final CSV includes unselected shield queries')
    row_by_key={(r['world_identity'],int(r['schedule']),r['method'],int(r['seed'])):r for r in episodes}
    trace_keys=set()
    with gzip.open(output/'episode_traces.jsonl.gz','rt',encoding='utf-8') as stream:
        for line in stream:
            trace=json.loads(line);key=tuple(trace['key'])
            if key in trace_keys or key not in row_by_key: raise ValueError('Trace key mismatch or duplicate')
            trace_keys.add(key);row=row_by_key[key]
            states=sum(bool(s.get('contact_event')) for s in trace['steps'])
            ped_pairs=sum(int(s['contacts'].get('g1_pedestrian_contact_pairs',0)) for s in trace['steps'])
            unwanted_pairs=sum(sum(int(v) for v in s['contacts'].values()) for s in trace['steps'])
            if (states!=int(row['g1_unwanted_contact_states'])
                    or ped_pairs!=int(row['g1_pedestrian_contact_pairs'])
                    or unwanted_pairs!=int(row['g1_unwanted_contact_pairs'])):
                raise ValueError(f'Contact trace accounting mismatch for {key}')
    if trace_keys!=keys: raise ValueError('Not all 288 episode traces are present')
    _baseline_rows,baseline_index,_provenance,_hashes=load_baseline()
    if set(baseline_index)!=keys: raise ValueError('Final CSV keys do not match the saved baseline exactly')
    summary=json.loads((output/'summary.json').read_text())
    recomputed=_aggregate(episodes)
    for field in ('goal_completions','contact_free_goal_completions',
            'episodes_with_unwanted_contact','contact_states','proxy_contact_pairs',
            'total_spatial_memory_observations','total_spatial_memory_rays',
            'total_emergency_scans','total_emergency_rays'):
        if summary['overall'][field] != recomputed[field]:
            raise ValueError(f'Summary does not recompute from episode CSV for {field}')


def _heartbeat(total,done,start):
    elapsed=time.monotonic()-start
    eta=elapsed/done*(total-done) if done else None
    print(f'Progress: {done}/{total} ({100*done/total:.1f}%) | elapsed {elapsed/60:.1f} min | ETA {eta/60:.1f} min' if eta is not None else f'Progress: 0/{total} | elapsed 0.0 min | ETA pending',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=DEFAULT_OUTPUT)
    parser.add_argument('--preflight-only',action='store_true')
    parser.add_argument('--resume',action='store_true')
    parser.add_argument('--timing-repetitions',type=int,default=3)
    args=parser.parse_args()
    main_run(args.output, resume=args.resume, preflight_only=args.preflight_only,
             repetitions=args.timing_repetitions)
