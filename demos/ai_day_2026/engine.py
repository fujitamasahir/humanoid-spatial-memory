"""Local exhibition game engine; reuses the actual Phase 2 G1 navigation stack."""
from __future__ import annotations
import json
import hashlib
import math
import os
import random
import sys
import threading
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'scripts')]

from spatial_memory.emergency_safety import EmergencySafetyController, IndependentEmergencySafetySensor
from spatial_memory.evaluation import run_episode
from spatial_memory.mujoco_navigation import MujocoNavigationScene
from spatial_memory.mujoco_perception import MujocoRayPerception
from spatial_memory.navigation import (HEADINGS, assess_observed_pedestrian_risk,
    heading_index, plan_g1_default_policy)
from spatial_memory.pedestrian_tracking import ObservedPedestrianTracker
from spatial_memory.simulation import Scenario
import phase2_mujoco_navigation as research_nav
import evaluate_phase2_61ray_emergency_safety_full_288 as frozen_eval

CATALOG_PATH = Path(__file__).resolve().parent / 'data' / 'maze_catalog.json'
BINDING_PATH = Path(__file__).resolve().parent / 'data' / 'runtime_binding.json'
CATALOG_SHA256 = 'fe3c41bf93c6694ddbfe9629e4bb333113ecf57fc9b4f615a9570d1aaafbc2d2'
BINDING_SHA256 = '451a9d255f714711037a227876b9f264b2203db8fe556ebdb88506189a5aa3f2'
DIFFICULTIES = {
    'easy': {'step_limit': 80, 'max_static_objects': 4, 'max_pedestrians': 2, 'max_observations': 20},
    'medium': {'step_limit': 120, 'max_static_objects': 2, 'max_pedestrians': 1, 'max_observations': 30},
    'hard': {'step_limit': 160, 'max_static_objects': 1, 'max_pedestrians': 0, 'max_observations': 40},
}
MAX_STATIC_OBJECTS = DIFFICULTIES['easy']['max_static_objects']
MAX_PEDESTRIANS = DIFFICULTIES['easy']['max_pedestrians']
ALLOWED_METHODS = {'periodic', 'age', 'uncertainty'}


def read_catalog() -> dict:
    if hashlib.sha256(CATALOG_PATH.read_bytes()).hexdigest() != CATALOG_SHA256:
        raise ValueError('The standalone maze asset failed its frozen SHA-256 check')
    doc = json.loads(CATALOG_PATH.read_text())
    if doc.get('schema') != 'ai-day-2026-maze-catalog-v1' or len(doc.get('mazes', [])) != 36:
        raise ValueError('The frozen 36-maze catalog is missing or malformed')
    seen = set()
    for maze in doc['mazes']:
        width, height = maze['width'], maze['height']
        if len(maze['wall_rows']) != height or any(len(row) != width or set(row)-{'0','1'} for row in maze['wall_rows']):
            raise ValueError(f'Malformed wall raster for {maze["id"]}')
        if maze['id'] in seen:
            raise ValueError('Duplicate maze identity')
        seen.add(maze['id'])
    return doc


def verify_runtime_binding() -> dict:
    if hashlib.sha256(BINDING_PATH.read_bytes()).hexdigest() != BINDING_SHA256:
        raise ValueError('The frozen implementation binding failed its SHA-256 check')
    binding = json.loads(BINDING_PATH.read_text())
    if binding.get('research_base_commit') != 'b6cb1fa233fbcd30b7ea26e88b865a69db96b91e':
        raise ValueError('Showcase research-base binding was changed')
    if (ROOT/'third_party/unitree_g1.UPSTREAM_COMMIT').read_text().strip() != binding.get('unitree_g1_upstream_commit'):
        raise ValueError('The Unitree G1 upstream commit marker changed')
    for rel, expected in binding['frozen_source_files'].items():
        actual = hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f'Frozen research implementation changed: {rel}')
    for rel, expected in binding['unitree_g1_files'].items():
        actual = hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f'Frozen Unitree G1 model asset changed: {rel}')
    return binding


def _free_set(maze: dict) -> set[tuple[int, int]]:
    return {(x, y) for y, row in enumerate(maze['wall_rows'])
            for x, bit in enumerate(row) if bit == '0'}


def make_scenario(maze: dict, objects: list[list[int]], ped_paths: list[list[list[int]]]) -> Scenario:
    walls = [(x, y) for y, row in enumerate(maze['wall_rows'])
             for x, bit in enumerate(row) if bit == '1']
    return Scenario.from_dict({
        'name': f"BYU-AI-Day-2026:{maze['id']}", 'split': 'development',
        'width': maze['width'], 'height': maze['height'],
        'start': maze['start'], 'goal': maze['goal'], 'walls': walls,
        'obstacles': [tuple(x) for x in objects],
        'pedestrians': [[tuple(x) for x in path] for path in ped_paths],
        'changes': [],
    })


class FootprintReachability:
    """Conservative state-space reachability from actual G1 collision bounds."""
    CELL_M = 0.75
    WALL_HALF_CELL = 0.505

    def __init__(self, half_extents: tuple[float, float], parts=None):
        self.hx, self.hy = map(float, half_extents)
        self.parts = tuple(parts or ())
        self._offset_cache = {}

    @classmethod
    def from_pinned_g1(cls) -> 'FootprintReachability':
        # The small public calibration scene uses the committed G1 MJCF only.
        size = 7
        walls = {(x, y) for x in range(size) for y in range(size)
                 if x in (0, size-1) or y in (0, size-1)}
        scenario = Scenario.from_dict(dict(name='ai-day-footprint-calibration', split='development',
            width=size, height=size, start=(2, 3), goal=(4, 3), walls=sorted(walls),
            obstacles=[], pedestrians=[], changes=[]))
        scene = MujocoNavigationScene(scenario, cell_size=cls.CELL_M)
        root = scene.data.qpos[scene.robot_qpos_adr:scene.robot_qpos_adr+2].copy()
        parts = []
        for geom in sorted(scene._robot_geom_ids):
            world_xy = scene.data.geom_xpos[geom, :2] - root
            local_xy = tuple(map(float, world_xy))
            radius = float(scene.model.geom_rbound[geom])
            if math.isfinite(radius) and radius > 0:
                parts.append((local_xy[0], local_xy[1], radius))
        return cls(scene.footprint_half_extents_local, parts)

    def _clear(self, cell: tuple[float, float], yaw: float,
               occupied: set[tuple[int, int]], width: int, height: int) -> bool:
        x, y = cell
        if self.parts:
            base_x, base_y = math.floor(x), math.floor(y)
            fx, fy = round(x-base_x, 1), round(y-base_y, 1)
            key = (float(yaw), fx, fy)
            offsets = self._offset_cache.get(key)
            if offsets is None:
                c, s = math.cos(yaw), math.sin(yaw)
                half = self.WALL_HALF_CELL*self.CELL_M
                found = []
                for ox in range(-2,3):
                    for oy in range(-2,3):
                        for lx, ly, radius in self.parts:
                            px = fx*self.CELL_M + c*lx - s*ly
                            py = fy*self.CELL_M + s*lx + c*ly
                            dx = max(abs(px-ox*self.CELL_M)-half, 0.0)
                            dy = max(abs(py-oy*self.CELL_M)-half, 0.0)
                            if dx*dx + dy*dy <= radius*radius:
                                found.append((ox,oy)); break
                offsets = self._offset_cache[key] = tuple(found)
            if any((base_x+ox,base_y+oy) in occupied for ox,oy in offsets):
                return False
            # Keep the center and the public collision envelope inside the map.
            if (x <= 0 or y <= 0 or x >= width-1 or y >= height-1):
                return False
            return True
        c, s = abs(math.cos(yaw)), abs(math.sin(yaw))
        hx, hy = c*self.hx + s*self.hy, s*self.hx + c*self.hy
        rx = hx/self.CELL_M + self.WALL_HALF_CELL
        ry = hy/self.CELL_M + self.WALL_HALF_CELL
        # Treat outside-map cells as solid, including the actual wall-box half width.
        if x-rx <= -0.5 or y-ry <= -0.5 or x+rx >= width-0.5 or y+ry >= height-0.5:
            return False
        for ox, oy in occupied:
            dx, dy = abs(x-ox)*self.CELL_M, abs(y-oy)*self.CELL_M
            if dx <= hx + self.WALL_HALF_CELL*self.CELL_M and dy <= hy + self.WALL_HALF_CELL*self.CELL_M:
                return False
        return True

    def _turn_clear(self, cell, from_heading, to_heading, occupied, width, height):
        start, end = HEADINGS[from_heading], HEADINGS[to_heading]
        delta = (end-start+math.pi) % (2*math.pi)-math.pi
        samples = max(1, math.ceil(abs(delta)/0.05))
        return all(self._clear(cell, start+delta*i/samples, occupied, width, height)
                   for i in range(1, samples+1))

    def has_route(self, maze: dict, objects: list[list[int]], *, start_heading: int = 0) -> bool:
        width, height = maze['width'], maze['height']
        occupied = {(x, y) for y, row in enumerate(maze['wall_rows'])
                    for x, bit in enumerate(row) if bit == '1'} | {tuple(x) for x in objects}
        start, goal = tuple(maze['start']), tuple(maze['goal'])
        pose_cache = {}
        def clear(cell, yaw):
            key = (round(float(cell[0]), 3), round(float(cell[1]), 3), round(float(yaw), 3))
            if key not in pose_cache:
                pose_cache[key] = self._clear(cell, yaw, occupied, width, height)
            return pose_cache[key]
        turn_cache = {}
        def turn_clear(cell, h0, h1):
            key = (cell, h0, h1)
            if key not in turn_cache:
                start_yaw, end_yaw = HEADINGS[h0], HEADINGS[h1]
                delta = (end_yaw-start_yaw+math.pi) % (2*math.pi)-math.pi
                samples = max(1, math.ceil(abs(delta)/0.05))
                turn_cache[key] = all(clear(cell, start_yaw+delta*i/samples)
                                      for i in range(1, samples+1))
            return turn_cache[key]
        queue = [(start[0], start[1], start_heading)]
        seen = set(queue)
        cursor = 0
        while cursor < len(queue):
            x, y, heading = queue[cursor]; cursor += 1
            cell = (x, y)
            if cell == goal:
                return True
            for new_heading in range(4):
                if new_heading == heading or not turn_clear(cell, heading, new_heading):
                    continue
                state = (x, y, new_heading)
                if state not in seen:
                    seen.add(state); queue.append(state)
            dx, dy = ((1,0),(0,1),(-1,0),(0,-1))[heading]
            target = (x+dx, y+dy)
            if target in occupied or not clear(target, HEADINGS[heading]):
                continue
            # Check the actual swept centerline at the shield's 1/10-cell granularity.
            if not all(clear((x+dx*i/10, y+dy*i/10), HEADINGS[heading])
                       for i in range(1, 11)):
                continue
            state = (target[0], target[1], heading)
            if state not in seen:
                seen.add(state); queue.append(state)
        return False


def make_pedestrian_paths(maze: dict, starts: list[list[int]], objects: list[list[int]],
                          horizon: int = 80) -> list[list[list[int]]]:
    """Seeded, collision-free cardinal wandering for the full exhibition horizon.

    Avoid immediate reversals when alternatives exist, prefer less visited
    cells, exclude the start/goal and objects, and avoid simultaneous
    pedestrian overlaps or exchanges. Append a reverse trace solely to
    satisfy Scenario's cyclic adjacency contract (not played in the episode).
    """
    if not starts:
        return []
    free = _free_set(maze) - {tuple(x) for x in objects} - {tuple(maze['start']), tuple(maze['goal'])}
    seed_data = json.dumps([maze['id'], sorted(map(tuple, objects)), starts],
                           separators=(',', ':')).encode()
    rng = random.Random(int.from_bytes(hashlib.sha256(seed_data).digest()[:8], 'big'))
    positions = [tuple(cell) for cell in starts]
    paths = [[cell] for cell in positions]
    visits = [{cell: 1} for cell in positions]
    previous = [None for _ in positions]
    for step in range(horizon):
        old = positions.copy()
        order = list(range(len(old)))
        rng.shuffle(order)
        reserved = set(old)
        for i in order:
            x, y = old[i]
            candidates = [q for q in ((x+1,y),(x-1,y),(x,y+1),(x,y-1))
                          if q in free and q not in reserved]
            if any(q != previous[i] for q in candidates):
                candidates = [q for q in candidates if q != previous[i]]
            target = (rng.choices(candidates,
                       weights=[1/(1+visits[i].get(q,0)) for q in candidates], k=1)[0]
                      if candidates else old[i])
            # Keep all previous cells reserved until the next tick: no swaps.
            reserved.add(target)
            positions[i] = target
        for i, pos in enumerate(positions):
            paths[i].append(pos)
            visits[i][pos] = visits[i].get(pos, 0) + 1
            if pos != old[i]:
                previous[i] = old[i]
    return [[list(q) for q in path + path[-2:0:-1]] for path in paths]


class GameEngine:
    def __init__(self, catalog: dict | None = None, reachability: FootprintReachability | None = None,
                 log_path: Path | None = None, frame_delay_s: float = 0.13):
        self.catalog = catalog or read_catalog()
        self.runtime_binding = verify_runtime_binding()
        self.mazes = {m['id']: m for m in self.catalog['mazes']}
        self.reachability = reachability or FootprintReachability.from_pinned_g1()
        self.log_path = log_path or (Path(__file__).resolve().parent / 'logs' / 'challenges.jsonl')
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.frame_delay_s = frame_delay_s
        self.lock = threading.RLock()
        self.condition = threading.Condition(self.lock)
        self.pause_requested = False
        self.resume_layout = None
        self.running = False
        self.skip_playback = threading.Event()
        self.history = {}
        self.counter = 0
        self.state: dict[str, Any] = {'status': 'idle', 'frame_seq': -1}
        self.last_config = None
        self._thread: threading.Thread | None = None
        provenance_path = ROOT/'results/phase2_mujoco/g1_forward_first_shield_turns_v3_pedestrian_avoidance_full_288/provenance.json'
        if not provenance_path.is_file():
            raise FileNotFoundError(f'Matched saved Phase 2 policy configuration missing: {provenance_path}')
        self.config = frozen_eval.frozen_config(json.loads(provenance_path.read_text()))
        self.config['max_steps'] = 80

    def validate(self, maze_id: str, objects: list, pedestrian_starts: list, difficulty: str = 'easy') -> dict:
        maze = self.mazes.get(maze_id)
        if maze is None:
            return {'valid': False, 'errors': ['Unknown admitted maze identity.']}
        rules = DIFFICULTIES.get(difficulty)
        if rules is None:
            return {'valid': False, 'errors': ['Unknown difficulty.']}
        errors = []
        max_objects, max_people = rules['max_static_objects'], rules['max_pedestrians']
        if len(objects) > max_objects:
            errors.append(f'Limit: at most {max_objects} static objects.')
        if len(pedestrian_starts) > max_people:
            errors.append(f'Limit: at most {max_people} pedestrian proxies.')
        def check_cells(cells, label):
            seen = set()
            free = _free_set(maze)
            for raw in cells:
                if not isinstance(raw, (list, tuple)) or len(raw) != 2 or any(type(v) is not int for v in raw):
                    errors.append(f'{label} placement must be a grid cell.')
                    continue
                cell = tuple(raw)
                if cell not in free:
                    errors.append(f'{label} must be placed in an open maze cell.')
                if cell in {tuple(maze['start']), tuple(maze['goal'])}:
                    errors.append(f'{label} cannot cover Start or Goal.')
                if cell in seen:
                    errors.append(f'{label} placements cannot overlap.')
                seen.add(cell)
            return seen
        object_set = check_cells(objects, 'Static object')
        pedestrian_set = check_cells(pedestrian_starts, 'Pedestrian')
        if object_set & pedestrian_set:
            errors.append('A pedestrian cannot start inside a static object.')
        if errors:
            return {'valid': False, 'errors': sorted(set(errors))}
        if not self.reachability.has_route(maze, objects + pedestrian_starts):
            return {'valid': False, 'errors': ['This layout removes all footprint-safe forward-first routes; move or remove an obstacle or pedestrian.']}
        paths = make_pedestrian_paths(maze, pedestrian_starts, objects, rules['step_limit'])
        for path in paths:
            for a, b in zip(path, path[1:]+path[:1]):
                if abs(a[0]-b[0])+abs(a[1]-b[1]) > 1:
                    return {'valid': False, 'errors': ['Generated pedestrian path failed adjacency validation.']}
        return {'valid': True, 'errors': [], 'pedestrian_paths': paths,
                'footprint_half_extents_m': [self.reachability.hx, self.reachability.hy]}

    def start(self, payload: dict) -> dict:
        maze_id = payload.get('maze_id')
        objects = payload.get('objects', [])
        pedestrians = payload.get('pedestrians', [])
        strategy = payload.get('strategy')
        if strategy not in ALLOWED_METHODS:
            return {'ok': False, 'error': 'Choose Periodic, Age, or Uncertainty.'}
        difficulty = payload.get('difficulty', 'easy')
        validation = self.validate(maze_id, objects, pedestrians, difficulty)
        if not validation['valid']:
            return {'ok': False, 'error': ' '.join(validation['errors']), 'validation': validation}
        with self.lock:
            if self.running:
                return {'ok': False, 'error': 'A challenge is already running.'}
            self.counter += 1
            run_config = {'maze_id': maze_id, 'objects': objects, 'pedestrians': pedestrians,
                          'strategy': strategy, 'difficulty': difficulty, 'step_limit': DIFFICULTIES[difficulty]['step_limit'],
                          'max_observations': DIFFICULTIES[difficulty]['max_observations'],
                          'render_3d': bool(payload.get('render_3d', False)), 'seed': 42000+self.counter,
                          'pedestrian_paths': validation['pedestrian_paths']}
            self.last_config = run_config
            self.history.clear()
            self.skip_playback.clear()
            self.pause_requested = False
            self.resume_layout = None
            self.running = True
            self.state = {'status': 'running', 'frame_seq': -1, 'step': 0,
                'maze_id': maze_id, 'strategy': strategy, 'difficulty': difficulty,
                'step_limit': run_config['step_limit'], 'max_observations': run_config['max_observations'],
                'geometry': self.mazes[maze_id]['wall_rows'],
                'start': self.mazes[maze_id]['start'], 'goal': self.mazes[maze_id]['goal'],
                'objects': objects, 'people': pedestrians, 'trajectory': [], 'observations': 1,
                'distance_m': 0.0, 'actual_unwanted_contacts': 0, 'blocked_attempts': 0,
                'events': [], 'contact_events': [], 'edit_events': []}
            self._thread = threading.Thread(target=self._run, args=(run_config,), daemon=True)
            self._thread.start()
            return {'ok': True, 'seed': run_config['seed']}

    def _run(self, run_config: dict):
        try:
            self._run_impl(run_config)
        except Exception as exc:
            with self.lock:
                self.state.update({'status': 'error', 'error': f'{type(exc).__name__}: {exc}'})
        finally:
            with self.lock:
                self.running = False

    def _run_impl(self, run_config: dict):
        challenge_started = time.perf_counter()
        maze = self.mazes[run_config['maze_id']]
        scenario = make_scenario(maze, run_config['objects'], run_config['pedestrian_paths'])
        scene = MujocoNavigationScene(scenario, cell_size=self.config['mujoco_cell_size_m'],
                                      timestep=self.config['mujoco_timestep_seconds'])
        memory_sensor = MujocoRayPerception(scene, **self.config['mujoco_ray_sensor'])
        safety_config = frozen_eval.SAFETY_CONFIG
        safety_sensor = IndependentEmergencySafetySensor(scene,
            range_m=safety_config['range_m'], ray_count=safety_config['ray_count'],
            sample_spacing_m=safety_config['sample_spacing_m'], ray_backend=safety_config['ray_backend'])
        safety_controller = EmergencySafetyController(scene)
        tracker = ObservedPedestrianTracker(max_age_steps=8)
        runtime_counts = {'memory_rays': 0, 'memory_calls': 0}
        state = {'static_obstacle_cells': set(), 'static_obstacle_step': -1,
                 'planner_step': 0, 'action_shield_queries': 0, 'last_reason': 'no_feasible_forward_route'}
        self.config['g1_navigation']['local_half_extents_m'] = list(scene.footprint_half_extents_local)

        def planner(grid, position, goal, unknown, yaw, blocked):
            state['planner_step'] += 1
            ctx = tracker.context()
            recent = (state['static_obstacle_cells'] if 0 <= state['planner_step']-state['static_obstacle_step'] <= 8 else set())
            route = plan_g1_default_policy(grid, position, goal, heading=heading_index(yaw),
                unknown=unknown, local_extents=scene.footprint_half_extents_local,
                cell_size=scene.cell_size, blocked_actions=blocked,
                static_obstacle_cells=recent, pedestrian_context=ctx, step=state['planner_step'])
            if route:
                kind, value = route[0]
                state['last_reason'] = ('route_direction_change' if kind == 'turn' else
                    'observed_static_obstacle_blocks_forward_path' if kind == 'sidestep' else
                    assess_observed_pedestrian_risk(position, heading_index(yaw), ctx, step=state['planner_step']) or 'observed_oncoming_pedestrian_imminent'
                    if kind == 'retreat' else str(value) if kind == 'wait' else 'forward_route_segment')
            else:
                state['last_reason'] = 'no_feasible_forward_route'
            return route

        def observe(world, position, yaw):
            result = memory_sensor.observe(world, position, yaw)
            runtime_counts['memory_rays'] += int(memory_sensor.last_stats.get('ray_count', 0))
            runtime_counts['memory_calls'] += 1
            return result
        # Presentation-only: keep actual detections separate from ground truth.
        seen_objects = set()
        seen_people = set()
        def record(_obs, step, _position):
            stats = memory_sensor.last_stats
            tracker.observe(step, stats.get('visible_pedestrian_cells', ()))
            state['static_obstacle_cells'] = {tuple(c) for c in stats.get('visible_persistent_obstacle_cells', ())}
            state['static_obstacle_step'] = int(step)
            seen_objects.update(state['static_obstacle_cells'])
            seen_people.clear()
            seen_people.update(tuple(c) for c in stats.get('visible_pedestrian_cells', ()))
        def safety_scan(world, position, yaw):
            return safety_sensor.scan(world, position, yaw)
        def safety_choose(memory, position, goal, yaw, action, measurement, step, blocked):
            return safety_controller.choose(memory, position, goal, yaw, action, measurement, step, blocked)
        def checker(world, position, action, yaw):
            state['action_shield_queries'] += 1
            kind, value = action
            if kind in {'move','sidestep','retreat'}:
                return scene.check_move(world, position, tuple(value), yaw, target_yaw=yaw)
            return scene.check_turn(world, position, yaw, HEADINGS[int(value)])
        from showcase_render import ShowcaseRenderer
        visual = ShowcaseRenderer(scene, run_config['strategy']) if run_config.get('render_3d') else None
        def frame_cb(world, frame):
            nonlocal scene, visual
            extra = scene.update(world, frame)
            serial = {
                'step': int(world.step), 'position': list(map(int, frame['position'])),
                'heading_yaw': float(frame.get('heading_yaw', 0)),
                'geometry': frame['geometry'].astype(int).tolist(),
                'memory': frame['memory'].astype(int).tolist(),
                'people': [list(map(int, p)) for p in sorted(world.people())],
                'objects': [list(map(int, p)) for p in sorted(world.objects)],
                'observed_objects': [list(p) for p in sorted(seen_objects)],
                'observed_people': [list(p) for p in sorted(seen_people)],
                'observation_count': int(frame['observation_count']),
                'observation_event': bool(frame.get('observation_granted', False)),
                'observation_score': frame.get('observation_score'),
                'planned': [list(map(int, p)) for p in frame.get('planned', [])],
                'moved': bool(frame.get('moved', False)), 'blocked': bool(frame.get('blocked', False)),
                'action': list(frame['navigation_action']) if frame.get('navigation_action') else None,
                'contacts': {k: int(extra.get(k, 0)) for k in ('g1_pedestrian_contact_pairs',
                    'g1_wall_contact_pairs','g1_persistent_obstacle_contact_pairs',
                    'g1_unwanted_floor_contact_pairs','g1_self_contact_pairs')},
                'emergency_intervention': frame.get('emergency_safety_intervention'),
            }
            if visual is not None:
                serial.update(visual.frame(frame))
            with self.lock:
                self.state.update(serial)
                if self.state.get('status') == 'resuming':
                    self.state['status'] = 'running'
                self.state['frame_seq'] = int(self.state.get('frame_seq', -1))+1
                self.state['observations'] = int(frame['observation_count'])
                self.state['actual_unwanted_contacts'] = int(self.state.get('actual_unwanted_contacts', 0)) + sum(serial['contacts'].values())
                if any(serial['contacts'].values()):
                    self.state['contact_events'] = self.state['contact_events'] + [
                        {'step': serial['step'], 'contacts': serial['contacts']}]
                if serial['observation_event'] and frame['step'] > 0:
                    self.state['events'] = (self.state.get('events', [])+[
                        {'step': int(frame['step']), 'type': 'memory_observation'}])[-30:]
                if serial['emergency_intervention']:
                    self.state['events'] = (self.state.get('events', [])+[
                        {'step': int(frame['step']), 'type': 'safety', 'reason': serial['emergency_intervention'].get('reason')}])[-30:]
                self.state['trajectory'] = (self.state.get('trajectory', [])+[
                    list(map(int, frame['position']))])[-400:]
                self.state['blocked_attempts'] = int(self.state.get('blocked_attempts',0))+int(frame.get('blocked',False))
                self.state['distance_m'] = sum(math.dist(a,b) for a,b in zip(self.state['trajectory'],self.state['trajectory'][1:]))*scene.cell_size
                # Save every evaluator step before WebSocket sampling.
                self.history[serial['step']] = {
                    k: self.state[k] for k in (
                        'step','maze_id','strategy','difficulty','step_limit','max_observations','position',
                        'heading_yaw','memory','people','objects','observed_objects',
                        'observed_people','trajectory','observations','frame_seq','contacts','contact_events')
                }
                if serial.get('render_png'):
                    self.history[serial['step']]['render_png'] = serial['render_png']
            terminal = tuple(frame['position']) == scenario.goal or world.step >= run_config['step_limit']
            edited = self._wait_at_frame(terminal)
            if edited is not None:
                # Keep the *same* evaluator invocation, controller, memory, RNG
                # time stream, blocked-action evidence and observation counter.
                # Only the evaluator-owned environment changes at the next tick.
                new_objects, new_people = edited
                paused_step = int(world.step)
                paths = make_pedestrian_paths(maze, new_people, new_objects,
                    run_config['step_limit']-paused_step)
                # The immutable research Scenario indexes paths by absolute step.
                # Prefix the current location so each new path begins at pause.
                paths = [[path[0]]*paused_step + path for path in paths]
                next_scenario = make_scenario(maze, new_objects, paths)
                replacement = MujocoNavigationScene(next_scenario, cell_size=scene.cell_size,
                    timestep=scene.timestep)
                if visual is not None:
                    phase = visual.phase
                    visual.close()
                    visual = ShowcaseRenderer(replacement, run_config['strategy'])
                    visual.phase = phase
                scene = replacement
                memory_sensor.scene = replacement
                safety_sensor.scene = replacement
                # Apply before the next sensing/action. The frozen evaluator
                # captures old geometry immediately before advance(), so its
                # persistent-change attribution still sees the transition.
                advance = world.advance
                def apply_edit_and_advance():
                    world.advance = advance
                    world.scenario = next_scenario
                    world.objects = set(next_scenario.obstacles)
                    advance()
                world.advance = apply_edit_and_advance
            return extra

        try:
            # The saved matched Phase 2 config and controllers are reused verbatim except
             # for the exhibition-only step and memory observation caps.
            cfg = json.loads(json.dumps(self.config))
            cfg['max_steps'] = run_config['step_limit']
            cfg['max_observations'] = run_config['max_observations']
            metrics, frames = run_episode(scenario, cfg, run_config['strategy'], seed=run_config['seed'],
                _frame_callback=frame_cb, _observation_provider=observe, _g1_planner=planner,
                _action_checker=checker, _initial_observation_callback=record,
                _observation_callback=record, _emergency_safety_sensor=safety_scan,
                _emergency_safety_controller=safety_choose,
                _g1_action_reason=lambda action, position, yaw: state['last_reason'])
            metrics['travel_distance_m'] = float(metrics.get('travel_distance', 0))*scene.cell_size
            metrics['mujoco_sensor_rays'] = runtime_counts['memory_rays']
            metrics['mujoco_sensor_calls'] = runtime_counts['memory_calls']
            metrics['episode_wall_time_seconds'] = time.perf_counter()-challenge_started
            actual = int(metrics.get('g1_unwanted_contact_pairs', 0))
            ai_wins = bool(metrics['success'] and actual == 0)
            result = {k: (v.item() if hasattr(v, 'item') else v) for k,v in metrics.items()
                      if isinstance(v, (str,int,float,bool)) or v is None}
            result.update({'winner': 'AI WINS' if ai_wins else 'HUMAN WINS',
                           'actual_unwanted_contacts': actual,
                           'blocked_attempts_not_contacts': int(metrics.get('g1_footprint_blocked_attempts',0)),
                           'seed': run_config['seed'], 'maze_id': run_config['maze_id'],
                           'strategy': run_config['strategy'], 'difficulty': run_config['difficulty'],
                           'step_limit': run_config['step_limit'], 'max_observations': run_config['max_observations'],
                           'contact_events': list(self.state['contact_events']),
                           'edit_events': list(self.state['edit_events']),
                           'exhibition_layout_edits': len(self.state['edit_events'])})
            log_record = {'timestamp_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
                          'configuration': run_config, 'result': result}
            with self.log_path.open('a', encoding='utf-8') as f:
                f.write(json.dumps(log_record, separators=(',',':'), allow_nan=False)+'\n')
            with self.lock:
                self.state.update({'status': 'finished', 'result': result,
                    'winner': result['winner'], 'step': int(metrics['elapsed_steps']),
                    'observations': int(metrics['observation_count']),
                    'distance_m': float(metrics.get('travel_distance_m',0)),
                    'actual_unwanted_contacts': actual,
                    'blocked_attempts': int(metrics.get('g1_footprint_blocked_attempts',0))})
        except Exception as exc:
            with self.lock:
                self.state.update({'status':'error','error':f'{type(exc).__name__}: {exc}'})
        finally:
            if visual is not None:
                visual.close()
            with self.lock: self.running = False

    def _wait_at_frame(self, terminal=False):
        """Wait on the evaluation worker at a completed-step boundary."""
        deadline = time.monotonic() + self.frame_delay_s
        with self.condition:
            while True:
                if terminal:
                    self.pause_requested = False
                    if self.state.get('status') == 'pausing':
                        self.state['status'] = 'running'
                if self.pause_requested:
                    self.state['status'] = 'paused'
                    self.state['frame_seq'] += 1
                    while self.pause_requested:
                        self.condition.wait()
                    layout = self.resume_layout
                    self.resume_layout = None
                    return layout
                remaining = deadline - time.monotonic()
                if self.skip_playback.is_set() or remaining <= 0:
                    return None
                self.condition.wait(remaining)

    def pause(self):
        with self.condition:
            if not self.running or self.state.get('status') != 'running' or self.skip_playback.is_set():
                return {'ok': False, 'error': 'Challenge is not available to pause.'}
            self.pause_requested = True
            self.state['status'] = 'pausing'
            self.condition.notify_all()
            return {'ok': True}

    def resume(self, step, objects, pedestrians):
        with self.condition:
            if self.state.get('status') != 'paused' or not self.pause_requested or step != self.state.get('step'):
                return {'ok': False, 'error': 'The paused step changed. Wait for the current frame.'}
            old_objects = {tuple(p) for p in self.state['objects']}
            old_people = {tuple(p) for p in self.state['people']}
            maze = self.mazes[self.state['maze_id']]
            rules = DIFFICULTIES[self.state['difficulty']]
            free = _free_set(maze)
            pos = tuple(self.state['position'])
            yaw = self.state['heading_yaw']
            def fail(message):
                return {'ok': False, 'error': message}
            if len(objects) > rules['max_static_objects'] or len(pedestrians) > rules['max_pedestrians']:
                return fail('Placement limit exceeded. Remove an existing hazard first.')
            if any(not isinstance(c, (list, tuple)) or len(c) != 2 or any(type(v) is not int for v in c)
                   for c in objects + pedestrians):
                return fail('Placement must be a grid cell.')
            o, q = set(map(tuple, objects)), set(map(tuple, pedestrians))
            if len(o) != len(objects) or len(q) != len(pedestrians) or o & q:
                return fail('Hazards cannot overlap.')
            if not (o | q) <= free or (o | q) & {tuple(maze['start']), tuple(maze['goal'])}:
                return fail('Use open cells outside Start and Goal.')
            changed = o != old_objects or q != old_people
            if changed:
                added = (o-old_objects) | (q-old_people)
                if pos in added or (added and not self.reachability._clear(pos, yaw, added, maze['width'], maze['height'])):
                    return fail('Keep new hazards clear of the humanoid.')
                # Pedestrians move again on resume. Do not let static edits
                # permanently seal every footprint-safe route from this pose.
                if o != old_objects:
                    from_pose = dict(maze, start=list(pos))
                    if not self.reachability.has_route(from_pose, sorted(o), start_heading=heading_index(yaw)):
                        return fail('This layout blocks every footprint-safe route from the humanoid.')
                self.resume_layout = ([list(c) for c in sorted(o)], [list(c) for c in sorted(q)])
                self.state['edit_events'] = self.state['edit_events'] + [{
                    'paused_step': step, 'effective_step': step+1,
                    'objects_before': [list(c) for c in sorted(old_objects)],
                    'objects_after': self.resume_layout[0],
                    'pedestrians_before': [list(c) for c in sorted(old_people)],
                    'pedestrians_after': self.resume_layout[1],
                }]
            else:
                self.resume_layout = None
            self.pause_requested = False
            self.state['status'] = 'resuming'
            self.condition.notify_all()
            return {'ok': True}

    def reset(self):
        with self.lock:
            if self.running:
                return {'ok': False, 'error': 'Wait for the current challenge to finish before resetting.'}
            self.state = {'status':'idle','frame_seq':-1}
            self.history.clear()
            self.skip_playback.clear()
            return {'ok': True}

    def skip(self):
        with self.lock:
            if self.state.get('status') not in ('running','finished'):
                return {'ok': False, 'error': 'No active challenge.'}
            self.skip_playback.set()
            self.condition.notify_all()
            return {'ok': True}

    def review_index(self):
        with self.lock:
            if self.state.get('status')!='finished':
                return None
            return {'steps': sorted(self.history), 'result': self.state['result']}

    def review_frame(self, step):
        with self.lock:
            if self.state.get('status')!='finished' or step not in self.history:
                return None
            return json.loads(json.dumps(self.history[step], allow_nan=False))

    def snapshot(self):
        with self.lock:
            return json.loads(json.dumps(self.state, allow_nan=False, default=str))
