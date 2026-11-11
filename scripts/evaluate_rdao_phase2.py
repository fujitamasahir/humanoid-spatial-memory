"""Evaluate Route-Decision-Aware Observation v1 on saved Phase 2 fit worlds.

Stages are append-only and resumable: ``cases`` (3 diagnostic episodes plus
baseline reproductions), ``primary`` (72 RDAO episodes), ``ablations`` (216
episodes), and ``matched`` (72 post-hoc observation-count matched controls).
No environments are generated and the held-out suite is never loaded.
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
import statistics
import sys
import time
from time import perf_counter_ns

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'scripts')]

import numpy as np
import evaluate_phase2_61ray_emergency_safety_full_288 as base
import phase2_mujoco_navigation as nav
from spatial_memory.memory import Memory
from spatial_memory.mujoco_perception import MujocoRayPerception
from spatial_memory.navigation import HEADINGS, heading_index
from spatial_memory.rdao import RDAOController, RDAOParameters

H80 = base.DEFAULT_OUTPUT
H800_TIMED = ROOT / 'results/phase2_mujoco/g1_forward_first_61ray_emergency_safety_full_288_h800_timed_v1'
DEFAULT_OUTPUT = ROOT / 'results/phase2_mujoco/rdao_v1_phase2_evaluation'
SEED = 42
TARGETS = (
    ('case_A', 'phase1.5-v0.4-BPRIME-1:fit:R:80000003', 1),
    ('case_B', 'phase1.5-v0.4-BPRIME-1:fit:R:80000007', 0),
    ('case_C', 'phase1.5-v0.4-BPRIME-1:fit:R:80000021', 1),
)
ABLATIONS = {
    'rdao_v1_no_route_relevance': {'use_route_relevance': False},
    'rdao_v1_no_visibility': {'use_visibility': False},
    'rdao_v1_no_timing': {'use_timing': False},
}
PARAMETERS = RDAOParameters()
CURRENT: dict | None = None
H800_TIMED_HASHES: dict[str, str] = {}


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _write_json(path: Path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def _append(path: Path, value: dict):
    with path.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(value, sort_keys=True, allow_nan=False) + '\n')
        stream.flush()
        os.fsync(stream.fileno())


def _load_records(path: Path):
    if not path.exists():
        return []
    with path.open(encoding='utf-8') as stream:
        return [json.loads(line) for line in stream if line.strip()]


def _key(record):
    return record['variant'], record['world_identity'], int(record['schedule']), int(record['seed'])


def _key4(record):
    return (record['world_identity'], int(record['schedule']), record['method'], int(record.get('seed', SEED)))


def _csv_write(path: Path, rows):
    rows = list(rows)
    fields = sorted({key for row in rows for key in row})
    with path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def _read_gzip_jsonl(path: Path):
    rows = []
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        rows.extend(json.loads(line) for line in stream if line.strip())
    return rows


def _write_gzip_jsonl(path: Path, rows):
    with gzip.open(path, 'wt', encoding='utf-8', newline='\n', compresslevel=6) as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True, allow_nan=False) + '\n')


def _normalize_final_position(value):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            value = value.strip('()[]').split(',')
    return tuple(int(v) for v in value)


def _signature(row):
    success = row['success'] if isinstance(row['success'], bool) else str(row['success']).lower() == 'true'
    return (success, int(row['elapsed_steps']), _normalize_final_position(row['final_position']),
        int(row.get('g1_forward_actions', 0)), int(row.get('g1_lateral_actions', 0)),
        int(row.get('g1_backward_actions', 0)), int(row.get('g1_in_place_turns', 0)),
        int(row.get('g1_waits', 0)), int(row.get('g1_pedestrian_contact_pairs', 0)),
        int(row.get('g1_unwanted_contact_pairs', 0)), int(row.get('observation_count', 0)),
        int(row.get('g1_actual_collision_shield_queries', 0)),
        int(row.get('emergency_safety_scans', 0)), int(row.get('emergency_safety_raycasts', 0)))


class MatchedQuotaController:
    """Descriptive post-hoc evenly spaced dose control, not an online policy."""
    def __init__(self, initial, *, target_observations, target_horizon, cap):
        self.memory = Memory(initial.shape)
        self.memory.update(np.asarray(initial, dtype=np.int8))
        self.cap = cap
        self.used = 1
        self.requests = self.denied = 0
        self.target_observations = max(1, int(target_observations))
        self.target_horizon = max(1, int(target_horizon))
        extra = self.target_observations - 1
        self.schedule = tuple(sorted({max(1, min(self.target_horizon,
            (i * self.target_horizon) // (extra + 1))) for i in range(1, extra + 1)}))

    def decide(self, step, position):
        requested = int(step) in self.schedule
        granted = requested and (self.cap is None or self.used < self.cap)
        self.requests += int(requested)
        self.denied += int(requested and not granted)
        return {'observation_requested': bool(requested), 'observation_granted': bool(granted),
                'observation_score': None, 'observation_position': position,
                'matched_schedule': self.schedule}

    def refresh(self, observation, step):
        if self.cap is not None and self.used >= self.cap:
            raise ValueError('Matched control observation budget exhausted')
        self.memory.update(np.asarray(observation, dtype=np.int8))
        self.used += 1


def _instrumented_case(payload, schedule, variant, *, target_count=None, target_horizon=None):
    """Reuse the frozen episode adapter; inject only the observation controller."""
    global CURRENT
    config = base.frozen_config(base.load_baseline()[2])
    context = {'variant': variant, 'world_identity': payload['identity'],
               'schedule': int(schedule), 'seed': SEED, 'controller': None,
               'sensor_times': {}, 'step': 0, 'heading_yaw': 0.0,
               'target_count': target_count, 'target_horizon': target_horizon}
    CURRENT = context
    original_run_episode, original_trace = base.run_episode, base._trace_record
    original_observe = MujocoRayPerception.observe

    def factory(initial, method, *, interval, radius, parameters, max_observations):
        if variant == 'rdao_v1_matched_quota':
            agent = MatchedQuotaController(initial, target_observations=target_count,
                target_horizon=target_horizon, cap=max_observations)
        else:
            options = ABLATIONS.get(variant, {})
            agent = RDAOController(initial, goal=tuple(context['goal']),
                max_observations=max_observations, unknown=config['unknown'],
                local_extents=config['g1_navigation']['local_half_extents_m'],
                cell_size_m=config['mujoco_cell_size_m'],
                range_m=config['mujoco_ray_sensor']['range_m'],
                horizontal_fov_deg=config['mujoco_ray_sensor']['horizontal_fov_deg'],
                ray_count=config['mujoco_ray_sensor']['ray_count'], parameters=PARAMETERS,
                **options)
            agent.episode_id = (f"{context['world_identity']}/schedule{context['schedule']}/"
                                f"{variant}/seed{context['seed']}")
        context['controller'] = agent
        return agent

    def injected_run_episode(scenario, run_config, method, **kwargs):
        context['goal'] = tuple(scenario.goal)
        old_scan = kwargs.get('_emergency_safety_sensor')
        if old_scan is not None:
            def tracked_scan(world, position, yaw):
                context['step'] = int(world.step)
                context['heading_yaw'] = float(yaw)
                agent = context.get('controller')
                if isinstance(agent, RDAOController):
                    agent.set_context(world.step, position, yaw)
                return old_scan(world, position, yaw)
            kwargs['_emergency_safety_sensor'] = tracked_scan
        old_check = kwargs.get('_action_checker')
        if old_check is not None:
            def tracked_check(world, position, action, yaw):
                result = old_check(world, position, action, yaw)
                agent = context.get('controller')
                if result[0] and isinstance(agent, RDAOController):
                    agent.record_blocked_action(position, heading_index(yaw), action)
                return result
            kwargs['_action_checker'] = tracked_check
        kwargs['_controller_factory'] = factory
        return original_run_episode(scenario, run_config, method, **kwargs)

    def timed_observe(sensor, world, position, yaw):
        begin = perf_counter_ns()
        try:
            return original_observe(sensor, world, position, yaw)
        finally:
            elapsed = perf_counter_ns() - begin
            step = int(world.step)
            context['sensor_times'][step] = elapsed
            agent = context.get('controller')
            if isinstance(agent, RDAOController):
                agent.note_observation_duration(step, elapsed)

    def enriched_trace(row, frames):
        trace = original_trace(row, frames)
        for item, frame in zip(trace['steps'], frames):
            diagnostic = frame.get('rdao')
            if diagnostic is not None:
                clean = {k: v for k, v in diagnostic.items() if not k.startswith('_')}
                item['rdao'] = base._jsonable_row(clean)
            item['actual_action'] = frame.get('navigation_action')
            item['actual_action_reason'] = frame.get('navigation_action_reason')
        return trace

    base.run_episode = injected_run_episode
    base._trace_record = enriched_trace
    MujocoRayPerception.observe = timed_observe
    try:
        row, trace = base.run_case(payload, schedule, variant, config, with_safety=True)
        trace = base._jsonable_row(trace)
        agent = context['controller']
        # The callback wrapper does not attach Sensor.last_stats to generic
        # evaluator bookkeeping. Ray totals are exact from authorized count x
        # the pinned 61 rays per memory observation.
        row['mujoco_sensor_rays'] = int(row['observation_count']) * int(config['mujoco_ray_sensor']['ray_count'])
        row['spatial_memory_rays'] = row['mujoco_sensor_rays']
        row['episode_key'] = [payload['identity'], int(schedule), variant, SEED]
        if isinstance(agent, RDAOController):
            steps = [step.get('rdao') for step in trace['steps'] if step.get('rdao')]
            row['rdao_request_count'] = int(agent.requests)
            row['rdao_denied_request_count'] = int(agent.denied)
            row['rdao_scheduler_total_ms'] = sum(s['decision_time_ns'] for s in steps) / 1e6
            row['rdao_planning_total_ms'] = sum(s['planning_time_ns'] for s in steps) / 1e6
            row['rdao_scheduler_mean_ms'] = (row['rdao_scheduler_total_ms'] / len(steps)) if steps else 0.0
            row['rdao_decision_count'] = len(steps)
            row['rdao_observation_sensor_calls_timed'] = len(context['sensor_times'])
        elif isinstance(agent, MatchedQuotaController):
            row['matched_target_observations'] = int(target_count)
            row['matched_schedule_steps'] = list(agent.schedule)
            row['matched_actual_observations'] = int(row['observation_count'])
        return row, trace
    finally:
        base.run_episode, base._trace_record = original_run_episode, original_trace
        MujocoRayPerception.observe = original_observe
        CURRENT = None


def _load_h80():
    global H800_TIMED_HASHES
    _artifact_hashes = base.file_hashes(H80)
    H800_TIMED_HASHES = base.file_hashes(H800_TIMED)
    rows = base._read_csv(H80 / 'episodes.csv') if hasattr(base, '_read_csv') else list(csv.DictReader((H80/'episodes.csv').open()))
    index = {_key4(row): row for row in rows}
    traces = {tuple(record['key']): record for record in _read_gzip_jsonl(H80 / 'episode_traces.jsonl.gz')}
    timed = {tuple(record['key']): record for record in _read_gzip_jsonl(H800_TIMED/'phase_timings.jsonl.gz')}
    if len(rows) != 288 or len(index) != 288 or len(traces) != 288:
        raise ValueError('Saved 80-step matrix must have 288 unique rows and traces')
    if len(timed) != 288:
        raise ValueError('Saved 800-step timing file must contain the matching 288 episodes')
    for key, row in index.items():
        calls = timed[key]['observation_decision_ns']
        steps = int(row['elapsed_steps'])
        if len(calls) < steps:
            raise ValueError(f'No 800-step timing prefix for saved 80-step episode {key}')
        row['baseline_scheduler_decision_ms'] = sum(calls[:steps]) / 1e6
    return rows, index, traces, _artifact_hashes


def _run_case_stage(output, worlds, h80_index, h80_traces):
    records_path = output / 'case_records.jsonl'
    old = _load_records(records_path)
    index = {_key(r): r for r in old}
    expected = []
    for name, identity, schedule in TARGETS:
        for policy in ('periodic', 'uncertainty', 'rdao_v1'):
            expected.append(((name, identity, schedule, policy, SEED), (identity, schedule, policy)))
    world_by_id = {p['identity']: p for p in worlds}
    for number, (compound, work) in enumerate(expected, 1):
        name, identity, schedule, policy, seed = compound
        key = (policy, identity, schedule, seed)
        if key in index:
            continue
        payload = world_by_id.get(identity)
        if payload is None:
            raise ValueError(f'Target case is not among the 36 admitted fit worlds: {identity}')
        if policy in {'periodic', 'uncertainty'}:
            row, trace = base.run_case(payload, schedule, policy,
                base.frozen_config(base.load_baseline()[2]), with_safety=True)
            row['episode_key'] = [identity, schedule, policy, seed]
            saved = h80_index[(identity, schedule, policy, seed)]
            saved_trace = h80_traces[(identity, schedule, policy, seed)]
            exact = _signature(row) == _signature(saved) and base._jsonable_row(trace) == saved_trace
            if not exact:
                raise RuntimeError(f'Historical {policy} reproduction mismatch for {identity} schedule {schedule}')
            row['historical_behavior_exact'] = True
        else:
            row, trace = _instrumented_case(payload, schedule, policy)
            row['historical_behavior_exact'] = None
        record = {'variant': policy, 'world_identity': identity, 'schedule': schedule,
                  'seed': seed, 'case': name, 'row': base._jsonable_row(row), 'trace': trace}
        _append(records_path, record)
        index[key] = record
        print(f'Cases progress: {len(index)}/{len(expected)}; completed {name}/{policy}', flush=True)
    case_records = list(index.values())
    rdao_records = [r for r in case_records if r['variant'] == 'rdao_v1']
    noninitial = sum(max(0, int(r['row']['observation_count']) - 1) for r in rdao_records)
    requests = sum(int(r['row'].get('rdao_request_count', 0)) for r in rdao_records)
    denied = sum(int(r['row'].get('rdao_denied_request_count', 0)) for r in rdao_records)
    decisions = sum(int(r['row'].get('rdao_decision_count', 0)) for r in rdao_records)
    contacts = sum(int(r['row'].get('g1_unwanted_contact_pairs', 0)) for r in rdao_records)
    smoke = {'status': 'DIAGNOSTIC_ONLY', 'case_count': len(rdao_records),
        'noninitial_observations': noninitial, 'requests': requests, 'denials': denied,
        'decision_count': decisions, 'request_fraction': requests / max(1, decisions),
        'unwanted_contact_pairs': contacts,
        'observation_activation_warning': noninitial == 0,
        'every_step_request_warning': requests / max(1, decisions) >= .8,
        'tuning_after_case_inspection': False}
    _write_json(output / 'three_case_smoke_diagnostic.json', smoke)
    _write_case_products(output, case_records)
    return smoke


def _write_case_products(output, records):
    rdao = [r for r in records if r['variant'] == 'rdao_v1']
    csv_rows = []
    divergences = []
    analysis_lines = ['# Three diagnostic RDAO cases', '',
        'These are development cases, not an independent validation sample. Step divergence establishes temporal ordering only; no intervention replay was used to claim causation.', '']
    for record in rdao:
        key = tuple(record['row']['episode_key'])
        row = record['row']
        trace = record['trace']
        steps = trace['steps']
        for step in steps:
            diag = step.get('rdao', {})
            csv_rows.append({'case': record['case'], 'world_identity': key[0],
                'schedule': key[1], 'policy': key[2], 'step': step['step'],
                'position': step['position'], 'heading_yaw': step['heading_yaw'],
                'last_observation_step': diag.get('last_observation_step'),
                'remaining_budget': diag.get('remaining_observation_budget'),
                'route_relevance': diag.get('route_relevance'), 'uncertainty': diag.get('uncertainty'),
                'predicted_visibility': diag.get('predicted_visibility'), 'decision_impact': diag.get('decision_impact'),
                'timing': diag.get('timing'), 'score': diag.get('score'), 'threshold': diag.get('threshold'),
                'requested': diag.get('requested', False), 'granted': diag.get('granted', False),
                'reason': diag.get('reason'), 'decision_time_ns': diag.get('decision_time_ns'),
                'planning_time_ns': diag.get('planning_time_ns'),
                'observation_time_ns': diag.get('observation_time_ns'),
                'actual_action': step.get('action'), 'blocked': step.get('blocked'),
                'safety_intervention': step.get('emergency_intervention')})
        for baseline_policy in ('periodic', 'uncertainty'):
            b = next(x for x in records if x['world_identity'] == key[0]
                     and x['schedule'] == key[1] and x['variant'] == baseline_policy)
            baseline_steps = b['trace']['steps']
            movement_diff = next((i for i, (left, right) in enumerate(zip(baseline_steps, steps))
                         if any(left.get(field) != right.get(field) for field in
                             ('position', 'heading_yaw', 'action'))), None)
            observation_diff = next((i for i, (left, right) in enumerate(zip(baseline_steps, steps))
                         if any(left.get(field) != right.get(field) for field in
                             ('observation_granted', 'observation_count'))), None)
            movement_step = steps[movement_diff]['step'] if movement_diff is not None else None
            observation_step = steps[observation_diff]['step'] if observation_diff is not None else None
            divergences.append({'case': record['case'], 'world_identity': key[0],
                'schedule': key[1], 'comparison_policy': baseline_policy,
                'first_divergence_step': movement_step,
                'first_movement_or_action_divergence_step': movement_step,
                'first_observation_timing_divergence_step': observation_step,
                'rdao_success': row['success'], 'rdao_steps': row['elapsed_steps'],
                'comparison_success': b['row']['success'], 'comparison_steps': b['row']['elapsed_steps']})
        analysis_lines += [f"## {record['case']} — {key[0]}, schedule {key[1]}", '',
            f"RDAO: success={row['success']}, steps={row['elapsed_steps']}, observations={row['observation_count']}, safety interventions={row['emergency_safety_interventions']}, blocked attempts={row['g1_footprint_blocked_attempts']}.",
            f"RDAO observation steps: {[s['step'] for s in steps if s.get('observation_granted')]}."]
        for item in divergences[-2:]:
            if item['case'] == record['case'] and item['world_identity'] == key[0] and item['schedule'] == key[1]:
                analysis_lines.append(f"Versus {item['comparison_policy']}: first observation-timing difference at step {item['first_observation_timing_divergence_step']}; first position/heading/action difference at step {item['first_movement_or_action_divergence_step']}; baseline success={item['comparison_success']} at {item['comparison_steps']} steps.")
        analysis_lines.append('The RDAO timeline and observation-time route/memory snapshots show what the scheduler estimated and what the authorized 3D observation changed. These traces do not by themselves establish the intervention as the cause of an outcome difference.')
        analysis_lines.append('')
        _write_json(output / f"{record['case']}_rdao_trace.json", trace)
    _csv_write(output / 'three_case_observation_timeline.csv', csv_rows)
    _csv_write(output / 'three_case_first_divergences.csv', divergences)
    (output/'three_case_analysis.md').write_text('\n'.join(analysis_lines),encoding='utf-8')


def _run_primary(output, worlds):
    records_path = output / 'primary_records.jsonl'
    old = _load_records(records_path)
    index = {_key(r): r for r in old}
    expected = [(p, schedule) for p in worlds for schedule in (0, 1)]
    started = time.monotonic()
    for number, (payload, schedule) in enumerate(expected, 1):
        key = ('rdao_v1', payload['identity'], schedule, SEED)
        if key in index:
            continue
        row, trace = _instrumented_case(payload, schedule, 'rdao_v1')
        record = {'variant': 'rdao_v1', 'world_identity': payload['identity'],
            'schedule': schedule, 'seed': SEED, 'row': base._jsonable_row(row), 'trace': trace}
        _append(records_path, record)
        index[key] = record
        if len(index) % 6 == 0 or number == len(expected):
            elapsed = time.monotonic() - started
            done = len(index)
            eta = elapsed / max(1, done) * (len(expected) - done)
            print(f'RDAO primary {done}/72 ({100*done/72:.1f}%), elapsed {elapsed/60:.1f} min, ETA {eta/60:.1f} min', flush=True)
    if len(index) != 72:
        raise RuntimeError('Primary RDAO evaluation did not produce all 72 episodes')
    _write_stage_products(output, 'primary', list(index.values()))


def _run_ablations(output, worlds):
    records_path = output / 'ablation_records.jsonl'
    old = _load_records(records_path)
    index = {_key(r): r for r in old}
    expected = [(payload, schedule, variant) for variant in ABLATIONS
                for payload in worlds for schedule in (0, 1)]
    started = time.monotonic()
    for number, (payload, schedule, variant) in enumerate(expected, 1):
        key = (variant, payload['identity'], schedule, SEED)
        if key in index:
            continue
        row, trace = _instrumented_case(payload, schedule, variant)
        record = {'variant': variant, 'world_identity': payload['identity'],
            'schedule': schedule, 'seed': SEED, 'row': base._jsonable_row(row), 'trace': trace}
        _append(records_path, record)
        index[key] = record
        if len(index) % 12 == 0 or number == len(expected):
            elapsed = time.monotonic() - started
            done = len(index)
            eta = elapsed / max(1, done) * (len(expected) - done)
            print(f'RDAO ablations {done}/216 ({100*done/216:.1f}%), elapsed {elapsed/60:.1f} min, ETA {eta/60:.1f} min', flush=True)
    if len(index) != 216:
        raise RuntimeError('RDAO ablation evaluation did not produce 216 episodes')
    _write_stage_products(output, 'ablations', list(index.values()))


def _run_matched(output, worlds):
    primary = _load_records(output / 'primary_records.jsonl')
    primary_index = {(r['world_identity'], int(r['schedule'])): r for r in primary}
    if len(primary_index) != 72:
        raise ValueError('Run the complete primary stage before matched-dose controls')
    records_path = output / 'matched_records.jsonl'
    old = _load_records(records_path)
    index = {_key(r): r for r in old}
    expected = [(p, schedule) for p in worlds for schedule in (0, 1)]
    started = time.monotonic()
    for number, (payload, schedule) in enumerate(expected, 1):
        key = ('rdao_v1_matched_quota', payload['identity'], schedule, SEED)
        if key in index:
            continue
        dose = primary_index[(payload['identity'], schedule)]['row']
        row, trace = _instrumented_case(payload, schedule, 'rdao_v1_matched_quota',
            target_count=int(dose['observation_count']), target_horizon=int(dose['elapsed_steps']))
        record = {'variant': 'rdao_v1_matched_quota', 'world_identity': payload['identity'],
            'schedule': schedule, 'seed': SEED, 'row': base._jsonable_row(row), 'trace': trace,
            'matched_to_rdao_observation_count': int(dose['observation_count']),
            'matched_to_rdao_horizon': int(dose['elapsed_steps'])}
        _append(records_path, record)
        index[key] = record
        if len(index) % 6 == 0 or number == len(expected):
            elapsed = time.monotonic() - started
            eta = elapsed / max(1, len(index)) * (72 - len(index))
            print(f'Matched-dose control {len(index)}/72, elapsed {elapsed/60:.1f} min, ETA {eta/60:.1f} min', flush=True)
    _write_stage_products(output, 'matched', list(index.values()))


def _write_stage_products(output, name, records):
    rows = [r['row'] for r in records]
    _csv_write(output / f'{name}_episodes.csv', rows)
    _write_gzip_jsonl(output / f'{name}_traces.jsonl.gz', [r['trace'] for r in records])


def _as_bool(value):
    return value if isinstance(value, bool) else str(value).lower() == 'true'


def _metric(row, metric):
    if metric == 'success':
        return float(_as_bool(row['success']))
    if metric == 'contact_free_success':
        return float(_as_bool(row['success']) and int(row.get('g1_unwanted_contact_pairs', 0)) == 0)
    if metric == 'horizon_censored_arrival_steps':
        return float(row['elapsed_steps'])
    if metric == 'scheduler_ms':
        return float(row.get('rdao_scheduler_total_ms', row.get('baseline_scheduler_decision_ms', 0)))
    if metric == 'observation_count':
        return float(row['observation_count'])
    if metric == 'travel_distance_m':
        return float(row['travel_distance_m'])
    if metric == 'turns':
        return float(row['g1_in_place_turns'])
    if metric == 'blocked_attempts':
        return float(row['g1_footprint_blocked_attempts'])
    if metric == 'safety_interventions':
        return float(row['emergency_safety_interventions'])
    if metric == 'safety_waits':
        return float(row['emergency_safety_wait_interventions'])
    if metric == 'episode_runtime_ms':
        return float(row['episode_wall_time_seconds']) * 1000
    raise KeyError(metric)


def _paired_comparison(new_rows, base_rows, new_method, baseline_method):
    new_index = {(r['world_identity'], int(r['schedule'])): r for r in new_rows}
    old_index = {_key4(r): r for r in base_rows}
    metrics = ('success', 'contact_free_success', 'horizon_censored_arrival_steps',
        'observation_count', 'travel_distance_m', 'turns', 'blocked_attempts',
        'safety_interventions', 'safety_waits', 'scheduler_ms', 'episode_runtime_ms')
    rows = []
    for metric in metrics:
        paired = []
        for (identity, schedule), new in new_index.items():
            old = old_index[(identity, schedule, baseline_method, SEED)]
            paired.append({'world_identity': identity, 'schedule': schedule,
                'mechanism': identity.split(':fit:')[1].split(':')[0],
                'baseline': _metric(old, metric), 'rdao': _metric(new, metric),
                'delta': _metric(new, metric) - _metric(old, metric)})
        # Use mechanism-stratified resampling at the environment-cluster level.
        grouped = {}
        for item in paired:
            grouped.setdefault(item['world_identity'], []).append(item['delta'])
        by_family = {'R': [], 'BP': [], 'M': []}
        for identity, deltas in grouped.items():
            family = identity.split(':fit:')[1].split(':')[0]
            by_family[family].append(statistics.mean(deltas))
        observed = statistics.mean(v for values in by_family.values() for v in values)
        rng = np.random.default_rng(42)
        boot = []
        for _ in range(3000):
            samples = []
            for values in by_family.values():
                samples.extend(rng.choice(values, size=len(values), replace=True).tolist())
            boot.append(statistics.mean(samples))
        boot.sort()
        rows.append({'comparison': f'{new_method} minus {baseline_method}', 'metric': metric,
            'baseline_mean': statistics.mean(x['baseline'] for x in paired),
            'rdao_mean': statistics.mean(x['rdao'] for x in paired),
            'paired_mean_delta': observed,
            'cluster_bootstrap_95_ci_low': boot[74], 'cluster_bootstrap_95_ci_high': boot[2924],
            'environment_clusters': len(grouped), 'episodes': len(paired),
            'cluster_unit': 'world identity; two schedules averaged within environment',
            'family_stratified': True})
    return rows


def _make_figures(output, baseline_rows, rdao_rows, case_records, ablation_records, matched_rows):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    output.mkdir(parents=True, exist_ok=True)
    colors = {'static': '#777777', 'periodic': '#2878b5', 'age': '#3a9d5d',
              'uncertainty': '#a35aa0', 'rdao_v1': '#d97822'}
    rows_by_method = {m: [r for r in baseline_rows if r['method'] == m]
                      for m in ('static', 'periodic', 'age', 'uncertainty')}
    rows_by_method['rdao_v1'] = rdao_rows
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for method, rows in rows_by_method.items():
        ax.scatter([float(r['observation_count']) for r in rows], [float(r['elapsed_steps']) for r in rows],
            s=24, alpha=.7, color=colors[method], label=method)
    ax.set(xlabel='Spatial-memory observation count (includes initial)',
           ylabel='Steps to goal or horizon 80', title='Observation cost vs horizon-censored arrival steps')
    ax.legend(frameon=False, fontsize=8); fig.tight_layout(); fig.savefig(output/'observations_vs_arrival.png', dpi=160); plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4.5))
    for method, rows in rows_by_method.items():
        ax.scatter([float(r['observation_count']) for r in rows], [float(r['travel_distance_m']) for r in rows],
            s=24, alpha=.7, color=colors[method], label=method)
    ax.set(xlabel='Spatial-memory observation count (includes initial)', ylabel='Travel distance (m)',
           title='Observation cost vs traveled distance (0.75 m/cell)')
    ax.legend(frameon=False, fontsize=8); fig.tight_layout(); fig.savefig(output/'observations_vs_distance.png', dpi=160); plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4.5))
    methods = list(rows_by_method)
    ax.scatter([statistics.mean(float(r['observation_count']) for r in rows_by_method[m]) for m in methods],
        [sum(_as_bool(r['success']) for r in rows_by_method[m]) / len(rows_by_method[m]) for m in methods],
        s=70, c=[colors[m] for m in methods])
    for method in methods:
        x = statistics.mean(float(r['observation_count']) for r in rows_by_method[method])
        y = sum(_as_bool(r['success']) for r in rows_by_method[method]) / len(rows_by_method[method])
        ax.annotate(method, (x, y), xytext=(4, 4), textcoords='offset points', fontsize=8)
    ax.set(xlabel='Mean observations per episode', ylabel='Goal completion fraction', ylim=(-.03, 1.03),
           title='Success vs observation cost')
    fig.tight_layout(); fig.savefig(output/'success_vs_observation_cost.png', dpi=160); plt.close(fig)

    fig, axes = plt.subplots(3, 1, figsize=(8, 6), sharex=True)
    for ax, case in zip(axes, ('case_A', 'case_B', 'case_C')):
        records = [r for r in case_records if r.get('case') == case]
        for rec in records:
            if rec['variant'] not in ('periodic', 'uncertainty', 'rdao_v1'):
                continue
            obs = [s['step'] for s in rec['trace']['steps'] if s.get('observation_granted')]
            ax.vlines(obs, .05, .88, alpha=.8, label=rec['variant'])
        ax.set_ylabel(case); ax.set_yticks([])
    axes[-1].set_xlabel('Simulation step'); axes[0].legend(ncol=3, fontsize=8, frameon=False)
    fig.suptitle('Observed spatial-memory timing in the three development cases')
    fig.tight_layout(); fig.savefig(output/'three_case_observation_timing.png', dpi=160); plt.close(fig)

    # Maps are empirical RDAO memory snapshots saved only at actual observations.
    for record in [r for r in case_records if r.get('variant') == 'rdao_v1']:
        for step in record['trace']['steps']:
            effect = step.get('rdao', {}).get('observation_effect')
            if not effect:
                continue
            before, after = np.asarray(effect['memory_before']), np.asarray(effect['memory_after'])
            fig, axes = plt.subplots(1, 2, figsize=(8, 3.6))
            for ax, grid, title, route in ((axes[0], before, 'Before observation', effect['route_before']),
                                           (axes[1], after, 'After observation', effect['route_after'])):
                ax.imshow(grid, origin='lower', cmap='gray_r', vmin=-1, vmax=1, interpolation='nearest')
                if route:
                    pos = [tuple(step['position'])]
                    for kind, value in route:
                        if kind == 'move': pos.append(tuple(value))
                        else: pos.append(pos[-1])
                    ax.plot([p[0] for p in pos], [p[1] for p in pos], color='#00a9d6', linewidth=1.8)
                ax.scatter([step['position'][0]], [step['position'][1]], c='#cc3355', s=24, marker='o')
                ax.set_title(title); ax.set_xticks([]); ax.set_yticks([])
            fig.suptitle(f"{record['case']} memory and G1-A* route at step {step['step']}")
            fig.tight_layout()
            fig.savefig(output/f"{record['case']}_memory_route_step_{step['step']}.png", dpi=150)
            plt.close(fig)
            break


def _finalize(output, baseline_rows):
    # Repair only derived ray-count fields in this new output. Each memory
    # observation uses the frozen 61-ray sensor; the value is exact and the
    # original Phase 2/Phase 1.5 result directories remain read-only.
    stage_paths = ('case_records.jsonl','primary_records.jsonl','ablation_records.jsonl','matched_records.jsonl')
    for filename in stage_paths:
        path=output/filename
        records=_load_records(path)
        for record in records:
            rays=int(record['row']['observation_count'])*61
            record['row']['mujoco_sensor_rays']=rays
            record['row']['spatial_memory_rays']=rays
        path.write_text(''.join(json.dumps(r,sort_keys=True,allow_nan=False)+'\n' for r in records),encoding='utf-8')
    cases = _load_records(output/'case_records.jsonl')
    primary = _load_records(output/'primary_records.jsonl')
    abl = _load_records(output/'ablation_records.jsonl')
    matched = _load_records(output/'matched_records.jsonl')
    if len(primary) != 72 or len(abl) != 216 or len(matched) != 72:
        raise ValueError('Final report requires completed primary, ablation, and matched-control stages')
    for record in [*cases,*primary,*abl,*matched]:
        row=record['row']
        if int(row['mujoco_sensor_rays']) != 61*int(row['observation_count']):
            raise RuntimeError(f'Spatial-memory ray count derivation failed for {row.get("episode_key")}')
        if int(row['emergency_safety_raycasts']) != 61*int(row['emergency_safety_scans']):
            raise RuntimeError(f'Emergency sensor ray count mismatch for {row.get("episode_key")}')
        if int(row.get('g1_unselected_action_shield_queries',0)) != 0:
            raise RuntimeError(f'Unselected action shield queries recorded for {row.get("episode_key")}')
    _write_stage_products(output,'primary',[r for r in primary])
    _write_stage_products(output,'ablations',abl)
    _write_stage_products(output,'matched',matched)
    _write_case_products(output,cases)
    _write_json(output/'metric_derivation.json',{
        'metric':'mujoco_sensor_rays and spatial_memory_rays',
        'formula':'observation_count * 61',
        'observation_count_includes':'initial authorized spatial-memory observation and all later grants',
        'source':'Each authorized call uses the frozen 61-ray MuJoCo memory sensor; generic evaluator ray statistics are not exposed through the timed callback adapter.',
        'raw_action_policy_changed':False,'existing_experiment_files_modified':False})
    primary_rows = [r['row'] for r in primary]
    comparisons = []
    for baseline_method in ('static','periodic','age','uncertainty'):
        comparisons.extend(_paired_comparison(primary_rows,
            [r for r in baseline_rows if r['method'] == baseline_method], 'rdao_v1', baseline_method))
    _csv_write(output/'paired_baseline_comparisons.csv', comparisons)
    ablation_summary = {}
    full_index = {(r['world_identity'],int(r['schedule'])):r['row'] for r in primary}
    for variant in ABLATIONS:
        rows = [r['row'] for r in abl if r['variant'] == variant]
        outcomes = base._aggregate(rows)
        ablation_summary[variant] = {'outcomes': outcomes,
            'mean_rdao_observations': statistics.mean(r['observation_count'] for r in rows),
            'mean_full_rdao_observations': statistics.mean(full_index[(r['world_identity'],int(r['schedule']))]['observation_count'] for r in rows),
            'mean_scheduler_ms': statistics.mean(r.get('rdao_scheduler_total_ms',0) for r in rows)}
    matched_rows = [r['row'] for r in matched]
    dose_match = {'target_episode_count':72,
        'mean_requested_rdao_observations':statistics.mean(int(r['matched_to_rdao_observation_count']) for r in matched),
        'mean_actual_control_observations':statistics.mean(int(r['row']['observation_count']) for r in matched),
        'exact_episode_count_matches':sum(int(r['row']['observation_count']) == int(r['matched_to_rdao_observation_count']) for r in matched),
        'matched_control_outcomes':base._aggregate(matched_rows),
        'rdao_outcomes':base._aggregate(primary_rows),
        'control_definition':'Deterministic periodic observations spread evenly across each paired RDAO elapsed horizon; the per-episode quota is set post hoc from that episode’s RDAO observation count. Descriptive dose-matched control, not an online policy.'}
    summary = {'status':'COMPLETE_RDAO_V1_PHASE2_EVALUATION',
        'design':{'worlds':36,'mechanisms':{'R':12,'BP':12,'M':12},'schedules':[0,1],
            'seed':SEED,'horizon':80,'policies':['static','periodic','age','uncertainty','rdao_v1'],
            'primary_episode_count':360,'new_rdao_episode_count':72,
            'grid_scale_m_per_cell':.75,'world_generation':False},
        'primary_rdao_outcomes':base._aggregate(primary_rows),
        'baseline_outcomes':{m:base._aggregate([r for r in baseline_rows if r['method']==m])
                             for m in ('static','periodic','age','uncertainty')},
        'diagnostic_cases': [{'case':r.get('case'),'world_identity':r['world_identity'],
            'schedule':int(r['schedule']),'variant':r['variant'],
            'success':r['row']['success'],'steps':r['row']['elapsed_steps'],
            'observations':r['row']['observation_count'],
            'unwanted_contact_pairs':r['row'].get('g1_unwanted_contact_pairs',0)}
            for r in cases],
        'paired_comparisons':comparisons,
        'ablations':ablation_summary,'observation_count_matched_control':dose_match,
        'case_smoke':json.loads((output/'three_case_smoke_diagnostic.json').read_text()),
        'rdao_scheduler_time':{'mean_episode_ms':statistics.mean(r['rdao_scheduler_total_ms'] for r in primary_rows),
            'p95_episode_ms':sorted(r['rdao_scheduler_total_ms'] for r in primary_rows)[math.ceil(.95*len(primary_rows))-1],
            'mean_decision_ms':statistics.mean(r['rdao_scheduler_total_ms']/max(1,r['rdao_decision_count']) for r in primary_rows),
            'total_planning_ms':sum(r['rdao_planning_total_ms'] for r in primary_rows)},
        'limits':['One seed (42) and 36 saved development worlds; schedules are paired within each world.',
            'Cluster bootstrap resamples worlds stratified by mechanism; there are only 12 world identities per mechanism.',
            'RDAO is development-scoped and has no independent confirmatory test.',
            'Navigation is kinematic G1 root motion, not physical biped locomotion.',
            'RDAO V is a remembered-map estimate, not measured sensor visibility; safety sensing remains independent.']}
    experiment_path=output/'experiment_manifest.json'
    experiment=json.loads(experiment_path.read_text())
    experiment['source_hashes_at_finalization']={p:_sha((ROOT/p).read_bytes())
        for p in (*base.SOURCE_FILES,'src/spatial_memory/rdao.py','scripts/evaluate_rdao_phase2.py')}
    experiment['post_run_amendments']=[
        {'scope':'diagnostic report generation','change':'Separately report first observation-timing difference and first movement/action difference. No episode code or data changed.'},
        {'scope':'derived ray-count metric','change':'Set the new result rows spatial_memory_rays=mujoco_sensor_rays=observation_count×61, matching the frozen ray configuration. This is deterministic bookkeeping and does not alter decisions or simulation.'}]
    experiment['baseline_observation_scheduler_timing_source']=H800_TIMED.relative_to(ROOT).as_posix()
    experiment['baseline_timing_prefix_rule']='Take the first saved observation-decision timing calls equal to the exact horizon-80 elapsed step count; prior trace-prefix verification shows the same decisions through that horizon.'
    _write_json(experiment_path,experiment)
    _write_json(output/'summary.json',summary)
    _make_figures(output/'figures',baseline_rows,primary_rows,cases,abl,matched_rows)
    _write_final_report(output,summary,comparisons,ablation_summary,dose_match)
    # A deterministic inventory of the finished, newly generated result bundle.
    # The manifest excludes itself so its entries can be independently checked.
    artifact_manifest = {
        'format': 'sha256-path-size-v1',
        'files': [
            {'path': p.relative_to(output).as_posix(), 'bytes': p.stat().st_size,
             'sha256': _sha(p.read_bytes())}
            for p in sorted(output.rglob('*'))
            if p.is_file() and p.name != 'artifact_manifest.json'
        ],
    }
    _write_json(output/'artifact_manifest.json', artifact_manifest)
    return summary


def _write_final_report(output, summary, comparisons, ablations, dose_match):
    rdao = summary['primary_rdao_outcomes']
    lines = ['# Route-Decision-Aware Observation v1 — Phase 2 validation', '',
        '## Research question and algorithm', '',
        'RDAO v1 requests a spatial-memory observation when a currently sensor-reachable, uncertain map region can change the actual orientation-aware, forward-motion G1 A* route, with a timing weight favoring near-term decisions and a threshold increased by remaining-path cost per remaining observation budget. The score is `V × U × D × T`; it is a deterministic heuristic, not calibrated value of information.',
        '', 'Candidate regions are 2×2 grid blocks containing unknown or stale cells near the nominal route. For each, the scheduler plans the current route and counterfactual routes with the region set free and occupied. Route relevance is based on reachability, normalized G1 action-cost difference, and first-action changes. It uses no hypothetical MuJoCo shield calls.',
        '', '## Development cases and smoke check', '',
        f"- RDAO made {summary['case_smoke']['noninitial_observations']} noninitial observations across the three diagnostic episodes, with {summary['case_smoke']['requests']} requests over {summary['case_smoke']['decision_count']} decisions and {summary['case_smoke']['denials']} budget denials.",
        f"- Observation activation warning: {summary['case_smoke']['observation_activation_warning']}; near-every-step request warning: {summary['case_smoke']['every_step_request_warning']}.",
        '- Periodic and Uncertainty target-case replays were compared to saved traces and episode rows before RDAO runs.',
        '- Case timelines, first-divergence rows, full diagnostic traces, and map/route snapshots are in this result directory.',
        '', '## Full matched comparison', '',
        f"- RDAO: {rdao['goal_completions']}/72 goals, {rdao['contact_free_goal_completions']}/72 contact-free goals, {rdao['episodes_with_unwanted_contact']} episodes with unwanted contact.",
        f"- Mean observations: {rdao['mean_spatial_memory_observations']:.2f}; mean arrival/horizon steps: {rdao['mean_goal_step_successes']:.2f} among successes (paired tables also use horizon-censored steps for every episode).",
        '- The historical 288 baseline records are reused; only the 72 new RDAO episodes are simulated for the primary comparison.',
        '- Paired 95% intervals resample world identities stratified by R/BP/M, averaging the two schedules within a world. This small development set does not support generalization claims.',
        '', '### Paired estimates', '',
        '| Baseline | Metric | RDAO − baseline | Cluster bootstrap 95% CI |',
        '|---|---|---:|---:|']
    for item in comparisons:
        if item['metric'] in ('success','contact_free_success','observation_count','horizon_censored_arrival_steps','travel_distance_m','turns','blocked_attempts','safety_interventions','scheduler_ms'):
            lines.append(f"| {item['comparison'].split(' minus ')[1]} | {item['metric']} | {item['paired_mean_delta']:.3f} | [{item['cluster_bootstrap_95_ci_low']:.3f}, {item['cluster_bootstrap_95_ci_high']:.3f}] |")
    lines += ['', '## Ablations and dose control', '',
        '| Condition | Goals / 72 | Mean observations | Mean scheduler ms/episode |',
        '|---|---:|---:|---:|',
        f"| Full RDAO v1 | {rdao['goal_completions']} | {rdao['mean_spatial_memory_observations']:.2f} | {summary['rdao_scheduler_time']['mean_episode_ms']:.3f} |"]
    for variant, item in ablations.items():
        lines.append(f"| {variant} | {item['outcomes']['goal_completions']} | {item['mean_rdao_observations']:.2f} | {item['mean_scheduler_ms']:.3f} |")
    lines += [
        f"- Matched periodic control: exact achieved count in {dose_match['exact_episode_count_matches']}/72 episodes; mean target {dose_match['mean_requested_rdao_observations']:.2f}, actual {dose_match['mean_actual_control_observations']:.2f}. It is post hoc and descriptive.",
        f"- Matched control outcomes: {dose_match['matched_control_outcomes']['goal_completions']}/72 goals and {dose_match['matched_control_outcomes']['mean_spatial_memory_observations']:.2f} mean observations.",
        '', '## Inputs, integrity, and limitations', '',
        '- The scheduler receives ternary memory, observed-cell timestamps, pose/heading, goal, public G1 footprint, blocked-action feedback, sensor geometry, and observation budget. It does not receive `World`, true occupancy, future pedestrian positions, change schedules, evaluator contacts, or privileged visibility labels.',
        '- Emergency Safety and selected-action MuJoCo collision checks are unchanged and remain independent. No unselected action shield query is used.',
        '- The 36 previously admitted fit worlds, 0.75 m/cell assumption, 61-ray sensors, seed 42, schedules, and 80-step horizon are retained. No environment is generated and no held-out test suite is loaded.',
        '- The earlier Phase 1 `disruption-visible` gate became inactive and matched Static; RDAO is a separate algorithm and no prior result is reinterpreted.',
        '- This is kinematic navigation with prescribed pedestrian proxies, not physically controlled humanoid locomotion. A single seed and development data limit causal and statistical claims.',
        '', '## Reproduction', '',
        '```sh',
        '.venv/bin/python -m pytest tests/test_rdao.py -q',
        '.venv/bin/python scripts/evaluate_rdao_phase2.py --stage cases',
        '.venv/bin/python scripts/evaluate_rdao_phase2.py --stage primary --resume',
        '.venv/bin/python scripts/evaluate_rdao_phase2.py --stage ablations --resume',
        '.venv/bin/python scripts/evaluate_rdao_phase2.py --stage matched --resume',
        '```', '']
    (output/'validation_report.md').write_text('\n'.join(lines), encoding='utf-8')


def _stage(output, name, run_fn):
    lock = output/'run.lock'
    fd = os.open(lock, os.O_CREAT|os.O_EXCL|os.O_WRONLY, 0o600)
    os.write(fd, json.dumps({'pid':os.getpid(),'stage':name,'started':time.time()}).encode()); os.close(fd)
    try:
        run_fn()
    finally:
        lock.unlink(missing_ok=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=('cases','primary','ablations','matched','finalize','all'),default='all')
    parser.add_argument('--output',type=Path,default=DEFAULT_OUTPUT)
    parser.add_argument('--resume',action='store_true')
    args=parser.parse_args()
    if args.output.exists() and not args.resume:
        raise FileExistsError(f'Refusing to overwrite existing results: {args.output}')
    args.output.mkdir(parents=True,exist_ok=True)
    worlds=nav.admitted_worlds()
    if len(worlds)!=36: raise ValueError('Expected the existing 36 admitted fit worlds; no generation is permitted')
    preserved=nav.verify_preserved_prefix()
    base_rows,base_index,base_traces,base_hashes=_load_h80()
    meta_path=args.output/'experiment_manifest.json'
    if not meta_path.exists():
        _write_json(meta_path,{'experiment':'Phase 2 RDAO v1 evaluation','commit':os.popen('git rev-parse HEAD').read().strip(),
            'baseline_result_dir':H80.relative_to(ROOT).as_posix(),'baseline_artifact_hashes':base_hashes,
            'baseline_h800_timing_result_dir':H800_TIMED.relative_to(ROOT).as_posix(),
            'baseline_h800_timing_artifacts':H800_TIMED_HASHES,
            'source_hashes':{p:_sha((ROOT/p).read_bytes()) for p in (*base.SOURCE_FILES,'src/spatial_memory/rdao.py','scripts/evaluate_rdao_phase2.py')},
            'world_identities':[p['identity'] for p in worlds],'world_count':36,'schedules':[0,1],
            'seed':SEED,'horizon':80,'max_observations':20,'grid_scale_m_per_cell':.75,
            'memory_sensor':{'range_m':6,'horizontal_fov_deg':120,'rays':61},
            'independent_safety_sensor':base.SAFETY_CONFIG,'parameters':vars(PARAMETERS),
            'changed_conditions':['new observation policy RDAO v1'],'threshold_selected_before_case_results':True,
            'held_out_loaded':False,'environment_generation':False,'phase15_preserved_files_verified':preserved})
    if args.stage in ('cases','all'):
        _stage(args.output,'cases',lambda:_run_case_stage(args.output,worlds,base_index,base_traces))
    if args.stage in ('primary','all'):
        _stage(args.output,'primary',lambda:_run_primary(args.output,worlds))
    if args.stage in ('ablations','all'):
        _stage(args.output,'ablations',lambda:_run_ablations(args.output,worlds))
    if args.stage in ('matched','all'):
        _stage(args.output,'matched',lambda:_run_matched(args.output,worlds))
    if args.stage in ('finalize','all'):
        summary=_finalize(args.output,base_rows)
        print(json.dumps({'status':summary['status'],'rdao_goal_completions':summary['primary_rdao_outcomes']['goal_completions'],
            'rdao_observations':summary['primary_rdao_outcomes']['total_spatial_memory_observations'],
            'output':args.output.relative_to(ROOT).as_posix()},indent=2),flush=True)
    if nav.verify_preserved_prefix()!=preserved:
        raise RuntimeError('Phase 1.5 preservation manifest changed during RDAO evaluation')
    if base.file_hashes(H80)!=base_hashes or base.file_hashes(H800_TIMED)!=H800_TIMED_HASHES:
        raise RuntimeError('Previously saved Phase 2 evaluation data changed during RDAO work')


if __name__=='__main__':
    main()
