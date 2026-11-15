"""Prospective H2 high-frequency dynamic-object evaluation and replay exporter.

This module wraps the frozen H2 final benchmark API. It does not edit or
replace any frozen policy, sensor, planner, shield, or historical output.
"""
from __future__ import annotations

import argparse
import base64
import csv
import gzip
import hashlib
import json
import math
import os
import platform
import statistics
import subprocess
import sys
import time
import types
from collections import Counter, deque
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'src')]
import h2_final_common as frozen
import evaluate_phase2_61ray_emergency_safety_full_288 as evaluator
from spatial_memory import evaluation as evaluation_module
from spatial_memory import simulation as simulation_module
from spatial_memory.scheduling import ObservationController
from spatial_memory.simulation import Scenario, World

OUT = ROOT / 'results/phase2_mujoco/h2_high_frequency_dynamics_v1'
PROTOCOL = ROOT / 'docs/h2_high_frequency_dynamics_protocol_v1.md'
SCHEMA = ROOT / 'docs/h2_high_frequency_dynamics_replay_schema.md'
SOURCE_COMMIT = '12dc945c7da496e6cfc5dd79d6977b4c48d705c1'
ENGINE_NAMESPACE = 'h2-high-frequency-dynamics-v1'
SEED = 42
MAX_STEPS = 80
MAX_OBJECTS = 4
ARM_IDS = frozen.ARMS + ('uncertainty',)
ARM_LABELS = frozen.LABELS + ('Uncertainty',)
BASE_ARMS = frozen.ARMS
BASE_LABELS = frozen.LABELS
_FROZEN_FACTORY = frozen.factory


def sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      allow_nan=False).encode('utf-8')


def write_exclusive(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as f:
        f.write(json.dumps(value, sort_keys=True, indent=2,
                           allow_nan=False) + '\n')
        f.flush()
        os.fsync(f.fileno())


def atomic_gzip_json(path: Path, value) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(value, sort_keys=True, separators=(',', ':'),
                     allow_nan=False).encode('utf-8')
    packed = gzip.compress(raw, mtime=0)
    tmp = path.with_name(path.name + f'.{os.getpid()}.tmp')
    with tmp.open('xb') as f:
        f.write(packed)
        f.flush()
        os.fsync(f.fileno())
    if path.exists():
        tmp.unlink()
        raise FileExistsError(path)
    os.replace(tmp, path)
    return hashlib.sha256(packed).hexdigest()


def rng_for(map_identity: str, schedule: int, seed: int, step: int,
            purpose: str) -> np.random.Generator:
    """Independent framed Philox stream; deliberately has no model argument."""
    fields = (ENGINE_NAMESPACE, map_identity, str(schedule), str(seed),
              str(step), purpose)
    framed = b''.join(len(v.encode()).to_bytes(4, 'little') + v.encode()
                      for v in fields)
    key = hashlib.sha256(framed).digest()[:16]
    return np.random.Generator(np.random.Philox(int.from_bytes(key, 'little')))


def stream_id(map_identity: str, schedule: int, step: int, purpose: str) -> str:
    return hashlib.sha256(canonical([ENGINE_NAMESPACE, map_identity,
                                    str(schedule), str(SEED), str(step),
                                    purpose])).hexdigest()


def pack_2bit_grid(grid) -> str:
    """Compact portable y-major ternary grid: -1,0,1 => 0,1,2."""
    values = (np.asarray(grid, dtype=np.int8).reshape(-1) + 1).astype(np.uint8)
    if np.any(values > 2):
        raise ValueError('Ternary grid contained a value outside -1/0/1')
    out = np.zeros((len(values) + 3) // 4, dtype=np.uint8)
    for i in range(4):
        part = values[i::4]
        out[:len(part)] |= part << (2 * i)
    return base64.b64encode(out.tobytes()).decode('ascii')


def pack_bool_grid(grid) -> str:
    bits = np.asarray(grid, dtype=np.uint8).reshape(-1)
    return base64.b64encode(np.packbits(bits, bitorder='little').tobytes()).decode('ascii')


def _neighbors(cell, width, height):
    x, y = cell
    for q in ((x - 1, y), (x, y - 1), (x, y + 1), (x + 1, y)):
        if 0 <= q[0] < width and 0 <= q[1] < height:
            yield q


def _critical_cut_cells(walls, objects, start, goal, width, height):
    """Tarjan DFS: free vertices whose removal separates current cell and goal."""
    blocked = set(walls) | set(objects)
    if start in blocked or goal in blocked:
        return set(), False
    disc, low, parent = {}, {}, {}
    counter = 0

    def dfs(v):
        nonlocal counter
        counter += 1
        disc[v] = low[v] = counter
        for w in _neighbors(v, width, height):
            if w in blocked:
                continue
            if w not in disc:
                parent[w] = v
                dfs(w)
                low[v] = min(low[v], low[w])
            elif parent.get(v) != w:
                low[v] = min(low[v], disc[w])

    dfs(start)
    if goal not in disc:
        return set(), False
    ancestors = []
    v = goal
    while v != start:
        ancestors.append(v)
        v = parent[v]
    critical = set()
    child = goal
    for ancestor in ancestors[1:]:
        # Walk goal's DFS-tree path upward; child is the branch containing goal.
        if low[child] >= disc[ancestor]:
            critical.add(ancestor)
        child = ancestor
    return critical, True


class HighFrequencyEngine:
    """Generator-only state and transition rules; never receives policy memory."""
    def __init__(self, scenario, map_identity, schedule, seed, initial_objects):
        self.width, self.height = scenario.width, scenario.height
        self.walls = set(scenario.walls)
        self.goal = tuple(scenario.goal)
        self.map_identity, self.schedule, self.seed = map_identity, schedule, seed
        self.initial_objects = sorted(map(tuple, initial_objects))
        if len(self.initial_objects) > MAX_OBJECTS:
            raise ValueError('Saved initial object placement exceeds max=4')
        self.object_ids = {cell: f'obj_{i:04d}' for i, cell in
                           enumerate(self.initial_objects, 1)}
        self.next_id = len(self.object_ids) + 1
        self.scene = None
        self.robot_cell = tuple(scenario.start)
        self.robot_yaw = 0.0
        self.events = []
        self.transition_ns = []
        self.rejection_totals = Counter()
        self.object_histogram = Counter({str(len(self.object_ids)): 1})
        self.no_ops = 0
        self.event_counts = Counter()
        self.changed_cell_distances = []

    def _geometry_overlap(self, cell):
        """Conservative AABB separation from the actual G1 collision-geom bounds."""
        if self.scene is None:
            raise RuntimeError('Actual MuJoCo G1 geometry is not initialized')
        hx, hy = self.scene.footprint_half_extents_local
        c, s = abs(math.cos(self.robot_yaw)), abs(math.sin(self.robot_yaw))
        robot_hx, robot_hy = c * hx + s * hy, s * hx + c * hy
        wx, wy = self.scene.grid_to_world(self.robot_cell)
        ox, oy = self.scene.grid_to_world(cell)
        half_object = 0.505 * self.scene.cell_size
        return (abs(wx - ox) <= robot_hx + half_object + 1e-9
                and abs(wy - oy) <= robot_hy + half_object + 1e-9)

    def _reason(self, cell, objects, people, robot, critical,
                check_distance=True):
        if cell in self.walls:
            return 'static_wall'
        if cell in objects:
            return 'existing_object'
        if cell in people:
            return 'pedestrian_overlap'
        if cell == self.goal:
            return 'goal_protected'
        if check_distance and max(abs(cell[0] - robot[0]),
                                  abs(cell[1] - robot[1])) < 2:
            return 'robot_exclusion_zone'
        if self._geometry_overlap(cell):
            return 'robot_geometry_overlap'
        if cell in critical:
            return 'goal_connectivity'
        return None

    def _candidates(self, world, objects_before):
        robot, people = self.robot_cell, set(world.people())
        critical, connected = _critical_cut_cells(
            self.walls, objects_before, robot, self.goal, self.width, self.height)
        if not connected:
            raise RuntimeError('Current truth path disconnected before transition')
        all_cells = [(x, y) for y in range(self.height) for x in range(self.width)]
        rejected = Counter()
        additions = []
        if len(objects_before) < MAX_OBJECTS:
            for cell in all_cells:
                reason = self._reason(cell, objects_before, people, robot, critical)
                if reason:
                    rejected[reason] += 1
                else:
                    additions.append(cell)
        removals = sorted(objects_before)
        relocations = []
        for source in sorted(objects_before):
            after_remove = set(objects_before) - {source}
            critical_without_source, connected_after_remove = _critical_cut_cells(
                self.walls, after_remove, robot, self.goal, self.width, self.height)
            if not connected_after_remove:
                raise RuntimeError('Removing an object unexpectedly disconnected grid')
            for target in all_cells:
                if target == source:
                    rejected['same_source_destination'] += 1
                    continue
                reason = self._reason(target, after_remove, people, robot,
                                      critical_without_source)
                if reason:
                    rejected[reason] += 1
                else:
                    relocations.append((source, target))
        types = []
        if additions:
            types.append('addition')
        if removals:
            types.append('removal')
        if relocations:
            types.append('relocation')
        return additions, removals, relocations, types, rejected

    def transition(self, world):
        started = time.perf_counter_ns()
        step = int(world.step)
        objects_before = sorted(world.objects)
        people = sorted(world.people())
        count_before = len(objects_before)
        additions, removals, relocations, types, rejected = self._candidates(
            world, set(objects_before))
        rejected.update({})
        rng_type = rng_for(self.map_identity, self.schedule, self.seed, step,
                           'operation-type')
        rng_choice = rng_for(self.map_identity, self.schedule, self.seed, step,
                             'operation-candidate')
        record = dict(step=step, event_type='no_op', object_id=None,
            previous_cell=None, new_cell=None, from_cell=None, to_cell=None,
            object_count_before=count_before, object_count_after=count_before,
            robot_cell=list(self.robot_cell), robot_heading_yaw=float(self.robot_yaw),
            objects_before=[{'object_id': self.object_ids[c], 'cell': list(c)}
                            for c in objects_before],
            pedestrians=[{'pedestrian_id': f'ped_{i:02d}', 'cell': list(c)}
                         for i, c in enumerate(people)],
            connectivity_preserved=True, exclusion_zone_validated=True,
            geometry_clearance_validated=True,
            candidate_rejections=dict(sorted(rejected.items())),
            feasible_event_types=types,
            random_stream_id=stream_id(self.map_identity, self.schedule, step,
                                       'operation-type'))
        if types:
            kind = types[int(rng_type.integers(len(types)))]
            record['event_type'] = kind
            if kind == 'addition':
                target = additions[int(rng_choice.integers(len(additions)))]
                oid = f'obj_{self.next_id:04d}'
                self.next_id += 1
                world.objects.add(target)
                self.object_ids[target] = oid
                record.update(object_id=oid, new_cell=list(target),
                              to_cell=list(target))
                changed = [target]
            elif kind == 'removal':
                source = removals[int(rng_choice.integers(len(removals)))]
                oid = self.object_ids.pop(source)
                world.objects.remove(source)
                record.update(object_id=oid, previous_cell=list(source),
                              from_cell=list(source))
                changed = [source]
            else:
                source, target = relocations[int(rng_choice.integers(len(relocations)))]
                oid = self.object_ids[source]
                world.objects.remove(source)
                world.objects.add(target)
                del self.object_ids[source]
                self.object_ids[target] = oid
                record.update(object_id=oid, previous_cell=list(source),
                              new_cell=list(target), from_cell=list(source),
                              to_cell=list(target))
                changed = [source, target]
            if kind == 'addition':
                record['exclusion_zone_validated'] = all(
                    max(abs(target[0]-self.robot_cell[0]),
                        abs(target[1]-self.robot_cell[1])) >= 2 for target in changed)
            record['connectivity_preserved'] = _critical_cut_cells(
                self.walls, world.objects, self.robot_cell, self.goal,
                self.width, self.height)[1]
            if not record['connectivity_preserved']:
                raise AssertionError('Transition generator broke goal connectivity')
            record['object_count_after'] = len(world.objects)
            record['changed_cell_distance_from_robot'] = [
                int(max(abs(c[0]-self.robot_cell[0]), abs(c[1]-self.robot_cell[1])))
                for c in changed]
            self.changed_cell_distances.extend(record['changed_cell_distance_from_robot'])
            self.event_counts[kind] += 1
        else:
            record['no_op_reason'] = 'no_feasible_addition_removal_or_relocation'
            record['connectivity_preserved'] = bool(_critical_cut_cells(
                self.walls, world.objects, self.robot_cell, self.goal,
                self.width, self.height)[1])
            self.no_ops += 1
        record['objects_after'] = [
            {'object_id': self.object_ids[c], 'cell': list(c)}
            for c in sorted(world.objects)]
        record['duration_ns'] = time.perf_counter_ns() - started
        self.transition_ns.append(record['duration_ns'])
        self.rejection_totals.update(rejected)
        self.object_histogram[str(len(world.objects))] += 1
        self.events.append(record)
        return record

    def metrics(self):
        n = len(self.events)
        changed = sum(self.event_counts.values())
        return {
            'dynamic_steps': n, 'environment_changes': changed,
            'environment_change_rate': changed / max(1, n),
            'environment_no_ops': self.no_ops,
            'addition_count': self.event_counts['addition'],
            'removal_count': self.event_counts['removal'],
            'relocation_count': self.event_counts['relocation'],
            'mean_object_count': statistics.mean(
                int(x['object_count_after']) for x in self.events) if n else 0,
            'object_count_step_distribution': dict(sorted(self.object_histogram.items())),
            'changed_cells_per_step_mean': statistics.mean(
                len(x['changed_cell_distance_from_robot']) for x in self.events
                if x['event_type'] != 'no_op') if changed else 0,
            'changed_cell_chebyshev_distance_mean': statistics.mean(
                self.changed_cell_distances) if self.changed_cell_distances else 0,
            'candidate_rejections_by_reason': dict(sorted(self.rejection_totals.items())),
            'connectivity_violations': sum(not e['connectivity_preserved'] for e in self.events),
            'exclusion_zone_violations': sum(not e['exclusion_zone_validated'] for e in self.events),
            'transition_generation_ns': self.transition_ns,
            'transition_generation_total_ms': sum(self.transition_ns) / 1e6,
        }


def _dummy_slots(scenario, initial_objects):
    people = {c for path in scenario.pedestrians for c in path}
    unavailable = set(scenario.walls) | {scenario.start, scenario.goal} | people | set(initial_objects)
    free = [(x, y) for y in range(scenario.height) for x in range(scenario.width)
            if (x, y) not in unavailable]
    free.sort(key=lambda c: (-abs(c[0]-scenario.start[0])-
                             abs(c[1]-scenario.start[1]), c))
    if len(free) < MAX_OBJECTS:
        raise RuntimeError('Could not allocate four MuJoCo object mocap slots')
    return tuple(free[:MAX_OBJECTS])


def run_dynamic_case(payload, schedule, arm):
    """Run one frozen arm with only the environment transition wrapper added."""
    context = {}
    original_scenario = simulation_module.scenario_from_bprime
    original_world = simulation_module.World
    original_scene = evaluator.MujocoNavigationScene
    original_episode = evaluation_module.run_episode
    original_base_episode = evaluator.run_episode
    original_base_scenario = evaluator.scenario_from_bprime
    original_base_scene = evaluator.MujocoNavigationScene

    def scenario_adapter(_payload, _schedule):
        source = original_scenario(_payload, _schedule)
        initial = tuple(source.obstacles)
        engine = HighFrequencyEngine(source, _payload['identity'], _schedule,
                                     SEED, initial)
        slots = _dummy_slots(source, initial)
        context.update(source=source, engine=engine, slots=slots,
                       observations={}, captured_frames=[],
                       scene_update_ns=[], replay_capture_ns=[])
        return Scenario.from_dict(dict(name=source.name, split=source.split,
            width=source.width, height=source.height, start=source.start,
            goal=source.goal, walls=source.walls, obstacles=slots,
            pedestrians=source.pedestrians, changes=()))

    def scene_factory(scenario, **kwargs):
        scene = original_scene(scenario, **kwargs)
        engine = context['engine']
        engine.scene = scene
        slots = list(scene._object_mocaps.values())
        if len(slots) != MAX_OBJECTS:
            raise RuntimeError('MuJoCo scene did not allocate four dynamic object slots')
        original_sync = scene._sync_environment

        def sync(world):
            for index, mocap_id in enumerate(scene.pedestrian_mocaps):
                path = scene.scenario.pedestrians[index]
                scene.data.mocap_pos[mocap_id] = (*scene.grid_to_world(
                    path[world.step % len(path)]), 0)
            cells = sorted(world.objects)
            for index, mocap_id in enumerate(slots):
                cell = cells[index] if index < len(cells) else None
                scene.data.mocap_pos[mocap_id] = (
                    (*scene.grid_to_world(cell), 0) if cell is not None else (0, 0, -1000))

        scene._sync_environment = sync
        context['scene'] = scene
        return scene

    class DynamicWorld(original_world):
        def __init__(self, scenario):
            super().__init__(scenario)
            engine = context['engine']
            self.objects = set(engine.initial_objects)
            self.initial_geometry = self.geometry().copy()

        def advance(self):
            self.step += 1
            context['engine'].transition(self)

    def dynamic_evaluator(scenario, config, method, **kwargs):
        provider = kwargs.get('_observation_provider')
        if provider:
            def capture_observation(world, position, yaw):
                value = provider(world, position, yaw)
                context['observations'][int(world.step)] = np.asarray(value).copy()
                return value
            kwargs['_observation_provider'] = capture_observation
        callback = kwargs.get('_frame_callback')
        if callback is None:
            raise RuntimeError('Expected the frozen MuJoCo frame callback')

        def capture_frame(world, frame):
            started = time.perf_counter_ns()
            extra = callback(world, frame)
            context['scene_update_ns'].append(time.perf_counter_ns() - started)
            context['captured_frames'].append(frame)
            engine = context['engine']
            engine.robot_cell = tuple(frame['position'])
            engine.robot_yaw = float(frame.get('heading_yaw', 0.0))
            return extra

        kwargs['_frame_callback'] = capture_frame
        simulation_module.World = DynamicWorld
        try:
            result = original_episode(scenario, config, method, **kwargs)
        finally:
            simulation_module.World = original_world
        return result

    # The frozen adapter calls this local scenario adapter and frozen.run_case
    # supplies the ordinary per-arm timing/instrumentation wrapper around it.
    simulation_module.scenario_from_bprime = scenario_adapter
    evaluator.scenario_from_bprime = scenario_adapter
    evaluator.MujocoNavigationScene = scene_factory
    evaluator.run_episode = dynamic_evaluator
    evaluator.scenario_from_bprime = scenario_adapter
    evaluator.MujocoNavigationScene = scene_factory
    try:
        row, _trace, diagnostics = frozen.run_case(payload, schedule, arm)
    finally:
        simulation_module.scenario_from_bprime = original_scenario
        simulation_module.World = original_world
        evaluator.MujocoNavigationScene = original_scene
        evaluator.run_episode = original_base_episode
        evaluator.scenario_from_bprime = original_base_scenario
        evaluator.MujocoNavigationScene = original_base_scene
        evaluation_module.run_episode = original_episode
    frames = context['captured_frames']
    if not frames or len(frames) != row['elapsed_steps'] + 1:
        raise RuntimeError('Replay capture does not match episode step count')
    engine = context['engine']
    scene = context['scene']
    obs_by_step = context['observations']
    step_records = []
    for frame in frames:
        step = int(frame['step'])
        start_log = time.perf_counter_ns()
        if step == 0:
            event = dict(step=0, event_type='initial_state', object_id=None,
                object_count_before=len(engine.initial_objects),
                object_count_after=len(engine.initial_objects),
                objects_before=[{'object_id': f'obj_{i:04d}', 'cell': list(c)}
                                for i, c in enumerate(engine.initial_objects, 1)],
                objects_after=[{'object_id': f'obj_{i:04d}', 'cell': list(c)}
                               for i, c in enumerate(engine.initial_objects, 1)],
                connectivity_preserved=True, exclusion_zone_validated=True,
                geometry_clearance_validated=True,
                random_stream_id=None)
            before_cell = tuple(frame['position'])
            before_yaw = float(frame.get('heading_yaw', 0.0))
        else:
            event = engine.events[step - 1]
            before_cell = tuple(event['robot_cell'])
            before_yaw = float(event['robot_heading_yaw'])
        observation = obs_by_step.get(step)
        obs_cells = [] if observation is None else [
            [int(x), int(y), int(observation[y, x])]
            for y, x in np.argwhere(observation >= 0)]
        root = scene.data.qpos[scene.robot_qpos_adr:scene.robot_qpos_adr+3].tolist()
        people = [{'pedestrian_id': f'ped_{i:02d}',
                   'cell': list(path[step % len(path)])}
                  for i, path in enumerate(scene.scenario.pedestrians)]
        truth = np.asarray(frame['geometry'], dtype=bool)
        for ped in people:
            x, y = ped['cell']
            truth[y, x] = True
        step_records.append({
            'step': step,
            'event': event,
            'objects_before': event.get('objects_before', event.get('objects_after', [])),
            'objects_after': event.get('objects_after', []),
            'pedestrians_xy': people,
            'robot_position_before_action_xy': list(before_cell),
            'robot_position_after_action_xy': list(frame['position']),
            'robot_world_position_after_action_m': root,
            'robot_heading_before_action_rad': before_yaw,
            'robot_heading_after_action_rad': float(frame.get('heading_yaw', 0.0)),
            'executed_action': frame.get('navigation_action'),
            'planned_path_xy': frame.get('planned', []),
            'observation_requested': bool(frame.get('observation_requested', step == 0)),
            'observation_granted': bool(frame.get('observation_granted', step == 0)),
            'paid_observation_count': int(frame.get('observation_count', 1)),
            'spatial_memory_ternary_packed_2bit_base64': pack_2bit_grid(frame['memory']),
            'observed_cells_xy_value': obs_cells,
            'observed_grid_ternary_packed_2bit_base64':
                None if observation is None else pack_2bit_grid(observation),
            'ground_truth_occupancy_packed_bits_base64': pack_bool_grid(truth),
            'ground_truth_static_and_object_occupancy_packed_bits_base64':
                pack_bool_grid(frame['geometry']),
            'emergency_safety_scan': frame.get('emergency_safety_scan'),
            'emergency_safety_intervention': frame.get('emergency_safety_intervention'),
            'selected_action_shield_rejection': {
                'rejected': bool(frame.get('footprint_blocked', False)),
                'reason': frame.get('blocked_reason'),
                'attempt_pedestrian_pairs': int(frame.get('g1_attempt_pedestrian_contact_pairs', 0)),
                'attempt_wall_pairs': int(frame.get('g1_attempt_wall_contact_pairs', 0)),
                'attempt_object_pairs': int(frame.get('g1_attempt_persistent_obstacle_contact_pairs', 0)),
            },
            'unwanted_contacts': {k: int(frame.get(k, 0)) for k in (
                'g1_pedestrian_contact_pairs', 'g1_wall_contact_pairs',
                'g1_persistent_obstacle_contact_pairs', 'g1_unwanted_floor_contact_pairs',
                'g1_self_contact_pairs')},
            'goal_reached': tuple(frame['position']) == tuple(payload['world']['goal']),
            'failure_or_termination_reason': row.get('failure_reason'),
        })
        context['replay_capture_ns'].append(time.perf_counter_ns() - start_log)
    dyn_metrics = engine.metrics()
    row.update(dyn_metrics)
    row['controller_mode'] = row.get('method')
    row['method'] = arm
    row['scene_frame_update_ns'] = context['scene_update_ns']
    row['scene_frame_update_total_ms'] = sum(context['scene_update_ns']) / 1e6
    row['replay_logging_ns'] = context['replay_capture_ns']
    row['replay_logging_total_ms'] = sum(context['replay_capture_ns']) / 1e6
    row['high_frequency_engine'] = ENGINE_NAMESPACE
    diagnostics.update(dynamic_transition_ns=engine.transition_ns,
                       scene_frame_update_ns=context['scene_update_ns'],
                       replay_logging_ns=context['replay_capture_ns'])
    replay = {
        'schema_version': '1.0.0',
        'episode_key': [payload['identity'], int(schedule), arm, SEED],
        'arm': arm, 'map': payload['identity'], 'map_family': payload['mechanism'],
        'schedule': int(schedule), 'seed': SEED,
        'grid': {'width': 25, 'height': 25, 'cell_size_m': 0.75},
        'coordinate_convention': 'x east, y north; lower-left origin; yaw radians CCW from G1 local +X',
        'static_walls_xy': [list(c) for c in sorted(engine.walls)],
        'start_xy': list(payload['world']['start']), 'goal_xy': list(payload['world']['goal']),
        'initial_robot': {'position_xy': list(payload['world']['start']), 'heading_rad': 0.0},
        'initial_objects': [{'object_id': f'obj_{i:04d}', 'cell': list(c)}
                            for i, c in enumerate(engine.initial_objects, 1)],
        'initial_pedestrians': step_records[0]['pedestrians_xy'],
        'steps': step_records,
        'outcome': {'success': bool(row['success']), 'goal_step': row['goal_step'],
                    'failure_reason': row.get('failure_reason'),
                    'unwanted_contact_pairs': int(row.get('g1_unwanted_contact_pairs', 0))},
        'metrics': row,
        'engine_specification': {
            'namespace': ENGINE_NAMESPACE, 'type_selection': 'uniform over feasible event types',
            'candidate_selection': 'uniform over sorted feasible candidates',
            'crn_key_fields': ['namespace', 'map_identity', 'schedule', 'seed', 'step', 'purpose'],
            'model_id_in_random_key': False, 'maximum_objects': MAX_OBJECTS,
            'connectivity': '4-connected ground-truth occupancy check in generator only',
            'robot_clearance': 'MuJoCo-derived G1 collision-geom AABB bound plus 3x3 cell exclusion',
        },
    }
    return row, replay, diagnostics


def _extend_frozen_arms():
    if frozen.ARMS == ARM_IDS:
        return
    if frozen.ARMS != BASE_ARMS:
        raise RuntimeError('Frozen arm registry changed during H2 extension')
    frozen.ARMS = ARM_IDS
    frozen.LABELS = ARM_LABELS

    def factory(initial, arm, cfg, options, goal):
        if arm == 'uncertainty':
            return ObservationController(initial, 'uncertainty', **options)
        return _FROZEN_FACTORY(initial, arm, cfg, options, goal)
    frozen.factory = factory


def source_maps():
    summary = json.loads((frozen.OUT / 'maps/summary.json').read_text())
    records = summary['maps']
    if len(records) != 36:
        raise ValueError('Expected the 36 saved H2 final maps')
    maps = []
    for record in records:
        path = frozen.OUT / 'maps' / record['path']
        payload = json.loads(path.read_text())
        if sha(path) != record['sha256']:
            raise ValueError(f'Saved H2 map hash mismatch: {path.name}')
        maps.append((payload, record['sha256']))
    return maps


def make_binding():
    if OUT.exists() and any(OUT.iterdir()):
        raise FileExistsError(f'New versioned output already exists: {OUT}')
    OUT.mkdir(parents=True, exist_ok=True)
    import importlib.metadata
    sources = [PROTOCOL, SCHEMA, Path(__file__), ROOT / 'tests/test_h2_high_frequency_dynamics.py',
               ROOT / 'scripts/h2_final_common.py',
               ROOT / 'scripts/run_h2_final.py', ROOT / 'scripts/evaluate_phase2_61ray_emergency_safety_full_288.py',
               ROOT / 'src/spatial_memory/evaluation.py', ROOT / 'src/spatial_memory/simulation.py',
               ROOT / 'src/spatial_memory/scheduling.py', ROOT / 'src/spatial_memory/mujoco_navigation.py',
               ROOT / 'src/spatial_memory/mujoco_perception.py', ROOT / 'src/spatial_memory/emergency_safety.py',
               ROOT / 'src/spatial_memory/navigation.py']
    maps = source_maps()
    maps_dir = OUT / 'maps'
    maps_dir.mkdir(exist_ok=True)
    source_map_index = json.loads((frozen.OUT/'maps/summary.json').read_text())['maps']
    map_manifest = []
    for index, (payload, digest) in enumerate(maps, 1):
        filename = f'map_{index:02d}_{payload["mechanism"]}.json'
        source_path = frozen.OUT/'maps'/source_map_index[index-1]['path']
        target_path = maps_dir/filename
        with target_path.open('xb') as f:
            f.write(source_path.read_bytes()); f.flush(); os.fsync(f.fileno())
        if sha(target_path) != digest:
            raise ValueError(f'Byte-copy verification failed for {filename}')
        map_manifest.append({'identity':payload['identity'],'path':filename,
                             'sha256':digest,'source_path':source_path.relative_to(ROOT).as_posix()})
    write_exclusive(maps_dir/'source_manifest.json', map_manifest)
    prior = frozen.OUT
    prior_binding = json.loads((prior/'binding.json').read_text())
    manifests = []
    for path in sorted(prior.rglob('artifact_manifest.json')):
        if path.name == 'artifact_manifest.json':
            manifest_doc = json.loads(path.read_text())
            entries = manifest_doc if isinstance(manifest_doc, list) else manifest_doc.get('files', [])
            for entry in entries:
                target = path.parent/entry['path']
                if not target.is_file() or sha(target) != entry['sha256']:
                    raise ValueError(f'Prior H2 manifest verification failed: {target}')
        manifests.append({'path': path.relative_to(ROOT).as_posix(), 'sha256': sha(path)})
    preserved = {
        'status': 'PASS',
        'phase15_integrity': __import__('verify_dao_integrity').verify(),
        'prior_h2_manifests': manifests,
        'prior_h2_map_count': len(maps),
        'prior_h2_primary_count': json.loads((prior/'primary/summary.json').read_text())['completed'],
        'prior_h2_fit_replay_count': json.loads((prior/'fit_replay/summary.json').read_text())['completed'],
    }
    write_exclusive(OUT/'prior_preservation.json', preserved)
    write_exclusive(OUT/'binding.json', {
        'protocol': 'h2_high_frequency_dynamics_v1',
        'source_commit': subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip(),
        'required_h2_base_commit': SOURCE_COMMIT,
        'h2_final_binding_sha256': sha(prior/'binding.json'),
        'frozen_h2_source_bindings': prior_binding.get('sources', {}),
        'sources': {p.relative_to(ROOT).as_posix(): sha(p) for p in sources},
        'maps': [{'identity': p['identity'], 'sha256': h} for p,h in maps],
        'arms': list(ARM_IDS), 'max_steps': MAX_STEPS,
        'runtime': {'python': sys.version, 'platform': platform.platform(),
                    'mujoco': importlib.metadata.version('mujoco'),
                    'numpy': np.__version__, 'hostname': platform.node()},
        'seed': SEED, 'object_count_limits': [0, MAX_OBJECTS],
        'protocol_sha256': sha(PROTOCOL), 'replay_schema_sha256': sha(SCHEMA),
    })


def _case_order(maps):
    return [(idx, payload, schedule) for idx,(payload,_) in enumerate(maps, 1)
            for schedule in (0,1)]


def _load_gz(path):
    with gzip.open(path, 'rt', encoding='utf-8') as f:
        return json.load(f)


def _verify_existing(path, expected_key):
    item = _load_gz(path)
    if item['replay']['episode_key'] != expected_key:
        raise ValueError(f'Replay key mismatch: {path}')
    if len(item['replay']['steps']) != int(item['row']['elapsed_steps']) + 1:
        raise ValueError(f'Replay step-count mismatch: {path}')
    if any(s['step'] != i for i,s in enumerate(item['replay']['steps'])):
        raise ValueError(f'Replay has missing or reordered step: {path}')
    return item


def _save_episode(stage, case_index, arm, row, replay, diagnostics):
    path = OUT / 'replays' / stage / f'episode_{case_index:03d}_{arm}.json.gz'
    body = {'row': row, 'replay': replay, 'diagnostics': diagnostics}
    digest = atomic_gzip_json(path, body)
    with (OUT / stage / 'journal.jsonl').open('a', encoding='utf-8') as f:
        f.write(json.dumps({'case': case_index, 'arm': arm,
                            'path': path.relative_to(OUT).as_posix(),
                            'sha256': digest}, sort_keys=True) + '\n')
        f.flush(); os.fsync(f.fileno())


def _run_stage(stage, cases, arms, dynamic):
    stage_dir = OUT / stage
    stage_dir.mkdir(parents=True, exist_ok=True)
    journal = stage_dir / 'journal.jsonl'
    if not journal.exists():
        journal.touch(exist_ok=False)
    completed = {}
    for line in journal.read_text().splitlines():
        item = json.loads(line)
        path = OUT / item['path']
        if sha(path) != item['sha256']:
            raise ValueError(f'Journal SHA-256 mismatch: {path}')
        key = (int(item['case']), item['arm'])
        _verify_existing(path, [cases[key[0]-1][1]['identity'],
                               cases[key[0]-1][2], key[1], SEED])
        if key in completed:
            raise ValueError(f'Duplicate episode journal key: {key}')
        completed[key] = path
    started = time.monotonic()
    total = len(cases)*len(arms)
    print(f'{stage}: 0/{total} complete (0%); elapsed 0.0 min; ETA pending', flush=True)
    for case_index, (map_index, payload, schedule) in enumerate(cases, 1):
        arm_order = list(arms)
        if stage == 'primary':
            shift = (case_index-1) % len(arms)
            arm_order = arm_order[shift:] + arm_order[:shift]
        for arm in arm_order:
            key = (case_index, arm)
            if key not in completed:
                if dynamic:
                    row, replay, diagnostics = run_dynamic_case(payload, schedule, arm)
                else:
                    row, trace, diagnostics = frozen.run_case(payload, schedule, arm)
                    row['controller_mode'] = row.get('method')
                    row['method'] = arm
                    # Original-condition replay retains the saved schedules and all
                    # navigation traces, with current-format geometry/memory grids.
                    replay = _original_replay(payload, schedule, arm, row, trace)
                _save_episode(stage, case_index, arm, row, replay, diagnostics)
                completed[key] = OUT/'replays'/stage/f'episode_{case_index:03d}_{arm}.json.gz'
            n = len(completed)
            if n % 26 == 0 or n == total:
                elapsed = time.monotonic()-started
                eta = elapsed/n*(total-n) if n else 0
                print(f'{stage}: {n}/{total} complete ({100*n/total:.1f}%); '
                      f'elapsed {elapsed/60:.1f} min; ETA {eta/60:.1f} min', flush=True)
    rows = []
    for (case_index, arm), path in sorted(completed.items()):
        item = _load_gz(path)
        rows.append(item['row'])
    _write_metrics_csv(stage_dir/'episodes.csv', rows)
    summary = {'stage': stage, 'status': 'COMPLETE', 'episodes': len(rows),
        'arms': list(arms), 'source_commit': json.loads((OUT/'binding.json').read_text())['source_commit'],
        'total_goal_completions': sum(bool(r['success']) for r in rows),
        'total_unwanted_contacts': sum(int(r.get('g1_unwanted_contact_pairs', 0)) for r in rows),
        'replay_count': len(rows), 'wall_seconds': time.monotonic()-started}
    write_exclusive(stage_dir/'summary.json', summary) if not (stage_dir/'summary.json').exists() else None
    return rows


def _write_metrics_csv(path, rows):
    if path.exists():
        return
    fields = sorted({k for r in rows for k in r if not isinstance(r[k], (dict, list))})
    with path.open('x', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fields, lineterminator='\n')
        writer.writeheader()
        writer.writerows({k:r.get(k) for k in fields} for r in rows)
        f.flush(); os.fsync(f.fileno())


def _original_replay(payload, schedule, arm, row, trace):
    from spatial_memory.simulation import scenario_from_bprime
    scenario = scenario_from_bprime(dict(payload, partition='fit'), schedule)
    steps = []
    source_steps = trace['steps']
    for frame in source_steps:
        step = int(frame['step'])
        geometry = np.zeros((scenario.height, scenario.width), dtype=np.uint8)
        for x,y in (*scenario.walls, *scenario.obstacles):
            geometry[y,x] = 1
        people = [{'pedestrian_id': f'ped_{i:02d}',
                   'cell': list(path[step % len(path)])}
                  for i,path in enumerate(scenario.pedestrians)]
        occ = geometry.copy()
        for person in people:
            x,y=person['cell'];occ[y,x]=1
        steps.append({'step':step, 'event': {'event_type':'saved_original_schedule',
            'objects_after':[{'object_id':f'obj_{i:04d}','cell':list(c)}
                             for i,c in enumerate(sorted(scenario.obstacles),1)]},
            'objects_before':[], 'objects_after':[{'object_id':f'obj_{i:04d}','cell':list(c)}
                for i,c in enumerate(sorted(scenario.obstacles),1)],
            'pedestrians_xy':people,
            'robot_position_before_action_xy':frame.get('position'),
            'robot_position_after_action_xy':frame.get('position'),
            'robot_heading_before_action_rad':frame.get('heading_yaw',0),
            'robot_heading_after_action_rad':frame.get('heading_yaw',0),
            'executed_action':frame.get('action'), 'planned_path_xy':[],
            'observation_requested':bool(frame.get('observation_granted',False)),
            'observation_granted':bool(frame.get('observation_granted',False)),
            'paid_observation_count':int(frame.get('observation_count',0)),
            'spatial_memory_ternary_y_major':None,
            'observed_cells_xy_value':[], 'observed_grid_ternary_y_major':None,
            'ground_truth_occupancy_y_major':occ.tolist(),
            'ground_truth_static_and_object_occupancy_y_major':geometry.tolist(),
            'emergency_safety_scan':frame.get('emergency_scan'),
            'emergency_safety_intervention':frame.get('emergency_intervention'),
            'selected_action_shield_rejection':{'rejected':bool(frame.get('blocked'))},
            'unwanted_contacts':frame.get('contacts',{}),
            'goal_reached':frame.get('position') == list(scenario.goal),
            'failure_or_termination_reason':row.get('failure_reason')})
    return {'schema_version':'1.0.0','episode_key':[payload['identity'],schedule,arm,SEED],
        'arm':arm,'map':payload['identity'],'map_family':payload['mechanism'],
        'schedule':schedule,'seed':SEED,'grid':{'width':25,'height':25,'cell_size_m':.75},
        'coordinate_convention':'x east,y north,lower-left origin,yaw radians CCW from G1 local +X',
        'static_walls_xy':[list(c) for c in sorted(scenario.walls)],
        'start_xy':list(scenario.start),'goal_xy':list(scenario.goal),
        'initial_robot':{'position_xy':list(scenario.start),'heading_rad':0},
        'initial_objects':[{'object_id':f'obj_{i:04d}','cell':list(c)}
                           for i,c in enumerate(sorted(scenario.obstacles),1)],
        'initial_pedestrians':steps[0]['pedestrians_xy'],'steps':steps,
        'outcome':{'success':bool(row['success']),'goal_step':row.get('goal_step'),
                   'failure_reason':row.get('failure_reason')},'metrics':row,
        'engine_specification':{'namespace':'saved_original_H2_schedule'}}


def _analysis(rows, out_dir):
    """Fixed paired whole-maze bootstrap and descriptive plots/tables."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from collections import defaultdict
    by_arm = {arm: [r for r in rows if r['method'] == arm] for arm in ARM_IDS}
    summary = {}
    for arm, group in by_arm.items():
        n=max(1,len(group))
        summary[arm] = {
            'episodes':len(group),'goal_completions':sum(bool(r['success']) for r in group),
            'goal_completion_rate':sum(bool(r['success']) for r in group)/n,
            'contact_free_goal_completions':sum(bool(r.get('g1_contact_free_success')) for r in group),
            'episodes_with_unwanted_contact':sum(int(r.get('g1_unwanted_contact_pairs',0))>0 for r in group),
            'mean_paid_observations':statistics.mean(float(r['observation_count']) for r in group),
            'mean_steps':statistics.mean(float(r['elapsed_steps']) for r in group),
            'mean_distance_m':statistics.mean(float(r.get('travel_distance_m',0)) for r in group),
            'mean_decision_ms':statistics.mean(sum(r.get('timing_ns',{}).get('decision',[]))/1e6 for r in group),
            'mean_episode_wall_s':statistics.mean(float(r.get('episode_wall_time_seconds',0)) for r in group),
            'mean_dynamic_changes':statistics.mean(float(r.get('environment_changes',0)) for r in group),
            'mean_change_rate':statistics.mean(float(r.get('environment_change_rate',0)) for r in group),
            'mean_additions':statistics.mean(float(r.get('addition_count',0)) for r in group),
            'mean_removals':statistics.mean(float(r.get('removal_count',0)) for r in group),
            'mean_relocations':statistics.mean(float(r.get('relocation_count',0)) for r in group),
            'mean_raycasts':statistics.mean(float(r.get('emergency_safety_raycasts',0))+
                float(r.get('spatial_memory_rays',0)) for r in group),
            'mean_transition_ms':statistics.mean(float(r.get('transition_generation_total_ms',0)) for r in group),
            'mean_scene_update_ms':statistics.mean(float(r.get('scene_frame_update_total_ms',0)) for r in group),
            'mean_replay_logging_ms':statistics.mean(float(r.get('replay_logging_total_ms',0)) for r in group),
        }
    (out_dir/'analysis').mkdir(exist_ok=True)
    write_exclusive(out_dir/'analysis/summary.json', {
        'episodes':len(rows),'arms':summary,
        'bootstrap':{'clusters':'map; both schedules retained','draws':5000,
                     'seed':2026111401,'interval':'percentile 95% exploratory'},
        'limitations':'Unadjusted exploratory comparisons; not independent confirmation.'})
    # Paired map-cluster bootstrap for success, observations, distance, decision and wall.
    contrasts=[]
    key_metrics={'success':lambda r:float(bool(r['success'])),'paid':lambda r:float(r['observation_count']),
        'steps':lambda r:float(r['elapsed_steps']),'distance_m':lambda r:float(r.get('travel_distance_m',0)),
        'decision_ms':lambda r:sum(r.get('timing_ns',{}).get('decision',[]))/1e6,
        'wall_s':lambda r:float(r.get('episode_wall_time_seconds',0))}
    cluster=defaultdict(lambda:defaultdict(list))
    for r in rows: cluster[r['world_identity']][r['method']].append(r)
    maps=sorted(cluster)
    rng=np.random.default_rng(2026111401)
    for arm in ARM_IDS:
        if arm=='periodic4': continue
        for base in ('periodic4','age4','age5'):
            boot={m:[] for m in key_metrics}
            for _ in range(5000):
                sampled=rng.choice(maps,len(maps),replace=True)
                for metric,fn in key_metrics.items():
                    diffs=[]
                    for map_id in sampled:
                        a=cluster[map_id].get(arm,[]);b=cluster[map_id].get(base,[])
                        for i in range(min(len(a),len(b))): diffs.append(fn(a[i])-fn(b[i]))
                    boot[metric].append(float(np.mean(diffs)) if diffs else 0.)
            row={'arm':arm,'baseline':base}
            for metric,values in boot.items():
                row[metric+'_mean_difference']=float(np.mean(values))
                row[metric+'_ci95_low']=float(np.quantile(values,.025))
                row[metric+'_ci95_high']=float(np.quantile(values,.975))
            contrasts.append(row)
    with (out_dir/'analysis/paired_whole_maze_bootstrap.csv').open('x',newline='',encoding='utf-8') as f:
        fields=sorted({k for r in contrasts for k in r});w=csv.DictWriter(f,fields,lineterminator='\n');w.writeheader();w.writerows(contrasts)
    # Metric table with family strata.
    for family in ('R','BP','M'):
        family_rows=[r for r in rows if r.get('mechanism')==family]
        if not family_rows: continue
        with (out_dir/f'analysis/family_{family}.csv').open('x',newline='',encoding='utf-8') as f:
            fields=['arm','episodes','goals','success_rate','mean_paid_observations','mean_steps','mean_distance_m','contact_episodes']
            w=csv.DictWriter(f,fields,lineterminator='\n');w.writeheader()
            for arm in ARM_IDS:
                group=[r for r in family_rows if r['method']==arm];n=max(1,len(group))
                w.writerow({'arm':arm,'episodes':len(group),'goals':sum(bool(r['success']) for r in group),
                    'success_rate':sum(bool(r['success']) for r in group)/n,
                    'mean_paid_observations':statistics.mean([r['observation_count'] for r in group]) if group else 0,
                    'mean_steps':statistics.mean([r['elapsed_steps'] for r in group]) if group else 0,
                    'mean_distance_m':statistics.mean([r.get('travel_distance_m',0) for r in group]) if group else 0,
                    'contact_episodes':sum(int(r.get('g1_unwanted_contact_pairs',0))>0 for r in group)})
    # Deterministic, English-language figures.
    names=[a.replace('_','\n') for a in ARM_IDS]
    fig,ax=plt.subplots(figsize=(14,5));ax.bar(names,[summary[a]['goal_completion_rate'] for a in ARM_IDS],color='#3979ad');ax.set_ylim(0,1);ax.set_ylabel('Goal completion rate');ax.set_title('High-frequency dynamic environment: goal completion');fig.tight_layout();fig.savefig(out_dir/'analysis/success_by_model.png',dpi=150);plt.close(fig)
    fig,ax=plt.subplots(figsize=(14,5));ax.bar(names,[summary[a]['mean_paid_observations'] for a in ARM_IDS],color='#36a5a5');ax.set_ylabel('Paid observations per episode');ax.set_title('Observation cost');fig.tight_layout();fig.savefig(out_dir/'analysis/paid_observations_by_model.png',dpi=150);plt.close(fig)
    fig,ax=plt.subplots(figsize=(8,6));
    for arm in ARM_IDS:
        ax.scatter(summary[arm]['mean_paid_observations'],summary[arm]['goal_completion_rate'],label=arm)
    ax.set_xlabel('Mean paid observations');ax.set_ylabel('Goal completion rate');ax.set_ylim(0,1);ax.legend(fontsize=7,ncol=2);ax.set_title('Success versus observation cost');fig.tight_layout();fig.savefig(out_dir/'analysis/success_vs_paid.png',dpi=150);plt.close(fig)
    return summary


def run_all(stages=('smoke','original_uncertainty','primary','analysis')):
    current = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    subprocess.run(['git','merge-base','--is-ancestor',SOURCE_COMMIT,current],cwd=ROOT,check=True)
    _extend_frozen_arms()
    maps=source_maps()
    cases=_case_order(maps)
    for stage in stages:
        if stage=='smoke':
            _run_stage(stage,cases[:4],ARM_IDS,True)
        elif stage=='original_uncertainty':
            _run_stage(stage,cases,('uncertainty',),False)
        elif stage=='primary':
            _run_stage(stage,cases,ARM_IDS,True)
        elif stage=='analysis':
            primary=[]
            for path in sorted((OUT/'replays/primary').glob('episode_*.json.gz')):
                primary.append(_load_gz(path)['row'])
            if len(primary)!=936: raise RuntimeError('Analysis requires 936 primary episodes')
            original=[]
            for path in sorted((OUT/'replays/original_uncertainty').glob('episode_*.json.gz')):
                original.append(_load_gz(path)['row'])
            if len(original)!=72: raise RuntimeError('Analysis requires 72 original-condition episodes')
            summary=_analysis(primary,OUT)
            original_summary=_analysis_original_uncertainty(original)
            write_exclusive(OUT/'analysis/original_uncertainty_summary.json',original_summary)
            report=_report(summary, original_summary, OUT)
            (OUT/'analysis/report.md').write_text(report,encoding='utf-8')
        else: raise ValueError(stage)


def _analysis_original_uncertainty(rows):
    return {'episodes':len(rows),'arm':'uncertainty','goal_completions':sum(bool(r['success']) for r in rows),
        'mean_paid_observations':statistics.mean(r['observation_count'] for r in rows),
        'mean_steps':statistics.mean(r['elapsed_steps'] for r in rows),
        'mean_distance_m':statistics.mean(r.get('travel_distance_m',0) for r in rows),
        'condition':'saved original scheduled environment dynamics; same 36 maps and 2 schedules'}


def _report(summary, original, out):
    lines=['# H2 High-Frequency Dynamic Environment Evaluation', '',
        'Descriptive robustness extension on the same admitted H2 maps. This is not independent validation.', '',
        '## High-frequency results', '',
        '| Arm | Goals / 72 | Rate | Contact episodes | Mean paid obs. | Mean steps | Mean distance (m) | Mean dynamic changes | Mean decision (ms) | Mean wall (s) |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for arm in ARM_IDS:
        s=summary[arm]
        lines.append(f"| {arm} | {s['goal_completions']}/72 | {s['goal_completion_rate']:.3f} | {s['episodes_with_unwanted_contact']} | {s['mean_paid_observations']:.2f} | {s['mean_steps']:.2f} | {s['mean_distance_m']:.2f} | {s['mean_dynamic_changes']:.2f} | {s['mean_decision_ms']:.3f} | {s['mean_episode_wall_s']:.3f} |")
    lines += ['', '## Original-condition Uncertainty comparison', '',
        f"Uncertainty completed {original['goal_completions']}/{original['episodes']} goals; mean paid observations {original['mean_paid_observations']:.2f}, mean steps {original['mean_steps']:.2f}, mean distance {original['mean_distance_m']:.2f} m.", '',
        '## Interpretation and limits', '',
        'Object transitions are state-dependent. Different policies can realize different event paths despite common random streams; results estimate performance under a shared transition mechanism, not identical realized environments. The change frequency and transition mechanism changed together, so differences cannot be attributed to frequency alone.',
        'The whole-maze bootstrap and family summaries are exploratory, unadjusted comparisons. No independent-test or superiority claim is made. The episode replays contain explicit step states and event histories; inspect their manifests and the replay schema for provenance and reconstruction.', '',
        '## Artifacts', '',
        '- Full primary metric rows: `primary/episodes.csv`',
        '- 936 complete primary replays: `replays/primary/`',
        '- 72 original-condition Uncertainty replays: `replays/original_uncertainty/`',
        '- Smoke records: `replays/smoke/`',
        '- Paired whole-maze bootstrap: `analysis/paired_whole_maze_bootstrap.csv`',
        '- Protocol and schema: `docs/h2_high_frequency_dynamics_protocol_v1.md`, `docs/h2_high_frequency_dynamics_replay_schema.md`', '']
    return '\n'.join(lines)


def manifest(directory):
    directory=Path(directory)
    entries=[]
    for path in sorted(directory.rglob('*')):
        if path.is_file() and path.name!='artifact_manifest.json':
            entries.append({'path':path.relative_to(directory).as_posix(),
                'bytes':path.stat().st_size,'sha256':sha(path)})
    write_exclusive(directory/'artifact_manifest.json',entries)
    return entries


def verify_replays():
    expected={'smoke':52,'original_uncertainty':72,'primary':936}
    report={}
    for stage,count in expected.items():
        directory=OUT/'replays'/stage
        files=sorted(directory.glob('episode_*.json.gz'))
        if len(files)!=count: raise ValueError(f'{stage}: expected {count} replay files, got {len(files)}')
        events=0;changes=0
        for path in files:
            item=_load_gz(path);steps=item['replay']['steps']
            if len(steps)!=item['row']['elapsed_steps']+1:raise ValueError(f'Frame count mismatch: {path}')
            for i,step in enumerate(steps):
                if step['step']!=i:raise ValueError(f'Step-order mismatch: {path}')
                if i and step['event'].get('step')!=i:raise ValueError(f'Event-step mismatch: {path}')
                if i:
                    events+=1;changes+=step['event']['event_type']!='no_op'
                    if not step['event']['connectivity_preserved']:raise ValueError('Connectivity failure recorded')
                    if not step['event']['exclusion_zone_validated']:raise ValueError('Exclusion violation recorded')
            # Apply explicit object_after states and validate stable IDs/counts.
            current={x['object_id']:tuple(x['cell']) for x in item['replay']['initial_objects']}
            for step in steps[1:]:
                current={x['object_id']:tuple(x['cell']) for x in step['objects_after']}
                if not 0<=len(current)<=MAX_OBJECTS:raise ValueError('Object-count replay violation')
                if len({tuple(v) for v in current.values()})!=len(current):raise ValueError('Duplicate object cell')
        report[stage]={'episodes':count,'environment_steps':events,'changes':int(changes),
                       'change_rate':changes/max(1,events)}
    return report


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('stage',choices=('prepare','smoke','original_uncertainty','primary','analysis','verify','all'))
    args=parser.parse_args()
    if args.stage=='prepare':
        _extend_frozen_arms();make_binding();print(f'Prepared immutable binding at {OUT}',flush=True)
        return
    if not (OUT/'binding.json').is_file():
        raise SystemExit('Missing prepared binding. Run the `prepare` stage, commit its source binding, then continue.')
    binding=json.loads((OUT/'binding.json').read_text())
    if binding['required_h2_base_commit']!=SOURCE_COMMIT:
        raise SystemExit('Frozen source commit binding mismatch')
    for relative, digest in binding['sources'].items():
        if sha(ROOT/relative) != digest:
            raise SystemExit(f'Source commitment changed after preparation: {relative}')
    _extend_frozen_arms()
    if args.stage=='all':
        for stage in ('smoke','original_uncertainty','primary','analysis'):
            if stage=='smoke' and (OUT/'smoke/summary.json').exists():continue
            if stage=='original_uncertainty' and (OUT/'original_uncertainty/summary.json').exists():continue
            if stage=='primary' and (OUT/'primary/summary.json').exists():continue
            if stage=='analysis' and (OUT/'analysis/summary.json').exists():continue
            run_all((stage,))
    elif args.stage=='verify':
        print(json.dumps(verify_replays(),indent=2,sort_keys=True))
    else:run_all((args.stage,))


if __name__=='__main__':
    main()
