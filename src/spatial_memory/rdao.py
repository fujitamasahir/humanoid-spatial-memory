"""Route-Decision-Aware Observation (RDAO) v1 for Phase 2 G1 navigation.

The scheduler consumes only the ternary spatial-memory grid, public pose,
goal, configured sensor geometry, observation timestamps, budget, and attempted
action feedback. Counterfactuals call the pure observed-map G1 A* planner; they
never call the MuJoCo shield or inspect the simulated world.
"""
from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter_ns
import math

import numpy as np

from .memory import Memory
from .navigation import (HEADINGS, blocked_action_evidence_signature,
                         plan_g1_forward_facing)
from .observation import line_cells


@dataclass(frozen=True)
class RDAOParameters:
    """Interpretable v1 defaults, selected before evaluation on the three cases."""
    score_threshold: float = 0.22
    budget_price: float = 0.04
    stale_after_steps: int = 12
    stale_full_uncertainty_steps: int = 64
    observation_cooldown_steps: int = 4
    route_lookahead_actions: int = 6
    max_candidate_regions: int = 12
    region_width_cells: int = 2
    unknown_blocker_open_probability: float = 0.5

    def __post_init__(self):
        if (not math.isfinite(self.score_threshold) or not 0 < self.score_threshold <= 1
                or not math.isfinite(self.budget_price) or self.budget_price < 0
                or type(self.stale_after_steps) is not int or self.stale_after_steps < 1
                or type(self.stale_full_uncertainty_steps) is not int
                or self.stale_full_uncertainty_steps < self.stale_after_steps
                or type(self.observation_cooldown_steps) is not int
                or self.observation_cooldown_steps < 0
                or type(self.route_lookahead_actions) is not int or self.route_lookahead_actions < 1
                or type(self.max_candidate_regions) is not int or self.max_candidate_regions < 1
                or type(self.region_width_cells) is not int or self.region_width_cells < 1
                or not 0 <= self.unknown_blocker_open_probability <= 1):
            raise ValueError('Invalid RDAO parameters')


def action_cost(route) -> float:
    """G1 route cost: cardinal translation=1, in-place quarter-turn=.25."""
    if not route:
        return math.inf
    return sum(.25 if action[0] == 'turn' else 1.0 for action in route)


def route_positions(start, route):
    """Return one spatial state per action, including in-place turns."""
    positions = [tuple(map(int, start))]
    for kind, value in route:
        if kind == 'move':
            positions.append(tuple(map(int, value)))
        else:
            positions.append(positions[-1])
    return positions


def _wrap_angle(value):
    return (value + math.pi) % (2 * math.pi) - math.pi


def predicted_cell_visibility(grid: np.ndarray, position, yaw: float, cell,
                             *, cell_size_m: float, range_m: float,
                             horizontal_fov_deg: float, ray_count: int,
                             unknown_open_probability: float = .5) -> float:
    """Predict whether a measured ray can reach a cell using remembered map only.

    Candidate-cell angular extent is conservatively widened by the cell
    diagonal. Each discrete ray uses remembered occupied cells as blockers and
    discounts unknown cells by the configured open probability. This predicts
    feasibility; it is not a claim about the actual MuJoCo ray result.
    """
    x, y = map(int, position)
    cx, cy = map(int, cell)
    if not (0 <= cy < grid.shape[0] and 0 <= cx < grid.shape[1]):
        return 0.0
    dx, dy = cx - x, cy - y
    distance = math.hypot(dx, dy) * cell_size_m
    if distance <= 1e-9 or distance > range_m:
        return 0.0
    center_angle = math.atan2(dy, dx)
    relative = _wrap_angle(center_angle - float(yaw))
    half_fov = math.radians(horizontal_fov_deg) / 2
    if abs(relative) > half_fov:
        return 0.0
    ray_step = math.radians(horizontal_fov_deg) / max(1, ray_count - 1)
    angular_radius = math.atan2(cell_size_m * math.sqrt(2) / 2,
                                max(distance, cell_size_m * .25))
    nearest_ray = round((relative + half_fov) / ray_step)
    ray_offset = -half_fov + nearest_ray * ray_step
    if abs(relative - ray_offset) > ray_step / 2 + angular_radius:
        return 0.0
    confidence = 1.0
    for bx, by in line_cells((x, y), (cx, cy)):
        if (bx, by) in {(x, y), (cx, cy)}:
            continue
        if not (0 <= by < grid.shape[0] and 0 <= bx < grid.shape[1]):
            return 0.0
        state = int(grid[by, bx])
        if state == 1:
            return 0.0
        if state == -1:
            confidence *= unknown_open_probability
    return float(confidence)


class RDAOController:
    """Observation scheduler with a legacy-compatible ``decide/refresh`` API."""
    def __init__(self, initial: np.ndarray, *, goal, max_observations: int,
                 unknown: str = 'optimistic', local_extents=(.219, .328),
                 cell_size_m: float = .75, range_m: float = 6.0,
                 horizontal_fov_deg: float = 120.0, ray_count: int = 61,
                 parameters: RDAOParameters | None = None,
                 use_route_relevance: bool = True, use_visibility: bool = True,
                 use_timing: bool = True):
        if np.asarray(initial).ndim != 2 or not np.isin(initial, (-1, 0, 1)).all():
            raise ValueError('RDAO requires a ternary 2D initial observation')
        if len(goal) != 2 or any(type(v) is not int for v in goal):
            raise ValueError('Invalid goal')
        if max_observations is not None and (type(max_observations) is not int or max_observations < 1):
            raise ValueError('Observation cap must be null or a positive integer')
        if unknown not in {'optimistic', 'blocked'}:
            raise ValueError('Invalid unknown-cell policy')
        if len(local_extents) != 2 or min(local_extents) < 0 or cell_size_m <= 0:
            raise ValueError('Invalid public robot footprint or grid scale')
        if range_m <= 0 or horizontal_fov_deg <= 0 or ray_count < 1:
            raise ValueError('Invalid configured sensor geometry')
        self.memory = Memory(initial.shape)
        self.memory.update(np.asarray(initial, dtype=np.int8))
        self.last_observed = np.full(initial.shape, -1, dtype=np.int64)
        self.last_observed[initial >= 0] = 0
        self.goal = tuple(goal)
        self.cap = max_observations
        self.used = 1
        self.requests = self.denied = 0
        self.unknown = unknown
        self.local_extents = tuple(float(v) for v in local_extents)
        self.cell_size_m = float(cell_size_m)
        self.range_m = float(range_m)
        self.horizontal_fov_deg = float(horizontal_fov_deg)
        self.ray_count = int(ray_count)
        self.parameters = parameters or RDAOParameters()
        self.use_route_relevance = bool(use_route_relevance)
        self.use_visibility = bool(use_visibility)
        self.use_timing = bool(use_timing)
        self.position = None
        self.heading_yaw = 0.0
        self.blocked_actions = set()
        self.blocked_signatures = {}
        self.last_observation_step = 0
        self.region_last_attempted = {}
        self.latest_diagnostic = None
        self.episode_id = None

    @property
    def remaining(self):
        return None if self.cap is None else max(0, self.cap - self.used)

    def set_context(self, step, position, heading_yaw, blocked_actions=None):
        self.position = tuple(map(int, position))
        self.heading_yaw = float(heading_yaw)
        if blocked_actions is not None:
            self.blocked_actions = set(blocked_actions)
        self.current_step = int(step)

    def record_blocked_action(self, position, heading, action):
        from .navigation import blocked_action_key
        key = blocked_action_key(position, heading, action)
        self.blocked_actions.add(key)
        self.blocked_signatures[key] = blocked_action_evidence_signature(self.memory.grid, key)

    def _plan(self, grid, position, heading_yaw):
        return plan_g1_forward_facing(grid, position, self.goal,
            heading=int(round(heading_yaw / (math.pi / 2))) % 4,
            unknown=self.unknown, local_extents=self.local_extents,
            cell_size=self.cell_size_m, blocked_actions=frozenset(self.blocked_actions))

    def _route_cost(self, route):
        return action_cost(route)

    def _regions(self, step, position, yaw, nominal_route):
        p = self.parameters
        grid = self.memory.grid
        positions = route_positions(position, nominal_route)
        if not positions:
            positions = [tuple(position)]
        route_lookup = {}
        route_limit = (p.route_lookahead_actions + 1 if self.use_timing else len(positions))
        for i, cell in enumerate(positions[:route_limit]):
            route_lookup.setdefault(cell, i)
        candidates = {}
        for y in range(grid.shape[0]):
            for x in range(grid.shape[1]):
                observed_at = int(self.last_observed[y, x])
                value = int(grid[y, x])
                age = step - observed_at if observed_at >= 0 else None
                if value == -1:
                    uncertainty = 1.0
                elif age is not None and age >= p.stale_after_steps:
                    uncertainty = min(1.0, (age - p.stale_after_steps + 1)
                                      / max(1, p.stale_full_uncertainty_steps - p.stale_after_steps))
                else:
                    continue
                nearest = min((abs(x-rx) + abs(y-ry), route_index)
                              for (rx, ry), route_index in route_lookup.items())
                route_distance, route_index = nearest
                if self.use_route_relevance and nominal_route and route_distance > 1:
                    continue
                if self.use_route_relevance and not nominal_route and abs(x-position[0]) + abs(y-position[1]) > 2:
                    continue
                visibility = (predicted_cell_visibility(grid, position, yaw, (x, y),
                    cell_size_m=self.cell_size_m, range_m=self.range_m,
                    horizontal_fov_deg=self.horizontal_fov_deg, ray_count=self.ray_count,
                    unknown_open_probability=p.unknown_blocker_open_probability)
                    if self.use_visibility else 1.0)
                if visibility <= 0:
                    continue
                region = (x // p.region_width_cells, y // p.region_width_cells)
                key = (region, uncertainty, route_index)
                candidates.setdefault(key, []).append(((x, y), visibility, uncertainty))
        grouped = {}
        for (region, uncertainty, route_index), cells in candidates.items():
            grouped.setdefault(region, []).extend((cell, vis, unc, route_index)
                                                   for cell, vis, unc in cells)
        ranked = []
        for region, cells in grouped.items():
            if step - self.region_last_attempted.get(region, -10**9) < p.observation_cooldown_steps:
                continue
            ranked.append((min(item[3] for item in cells), region, cells))
        ranked.sort(key=lambda item: (item[0], item[1]))
        return positions, ranked[:p.max_candidate_regions]

    def _candidate_scores(self, step, position, yaw, nominal_route, planning_ns):
        p = self.parameters
        grid = self.memory.grid
        positions, regions = self._regions(step, position, yaw, nominal_route)
        nominal_cost = self._route_cost(nominal_route)
        results = []
        for route_index, region, cells in regions:
            coords = [item[0] for item in cells]
            free_grid = grid.copy()
            occupied_grid = grid.copy()
            for x, y in coords:
                if (x, y) != tuple(position):
                    free_grid[y, x] = 0
                    occupied_grid[y, x] = 1
            start_ns = perf_counter_ns()
            if self.use_route_relevance:
                free_route = self._plan(free_grid, position, yaw)
                occupied_route = self._plan(occupied_grid, position, yaw)
                free_cost, occupied_cost = self._route_cost(free_route), self._route_cost(occupied_route)
                if math.isinf(free_cost) and math.isinf(occupied_cost):
                    relevance = 0.0
                elif math.isinf(free_cost) != math.isinf(occupied_cost):
                    relevance = 1.0
                else:
                    finite_costs = [v for v in (free_cost, occupied_cost, nominal_cost) if math.isfinite(v)]
                    scale = max(1.0, nominal_cost if math.isfinite(nominal_cost) else max(finite_costs, default=1.0))
                    relevance = min(1.0, abs(free_cost - occupied_cost) / scale) if math.isfinite(free_cost) and math.isfinite(occupied_cost) else 1.0
                    first_free = free_route[0] if free_route else None
                    first_occupied = occupied_route[0] if occupied_route else None
                    if first_free != first_occupied:
                        relevance = max(relevance, .5)
                counterfactual = {'free_reachable': bool(free_route),
                    'occupied_reachable': bool(occupied_route),
                    'free_cost': free_cost if math.isfinite(free_cost) else None,
                    'occupied_cost': occupied_cost if math.isfinite(occupied_cost) else None,
                    'free_first_action': free_route[0] if free_route else None,
                    'occupied_first_action': occupied_route[0] if occupied_route else None,
                    'first_action_changes': (free_route[0] if free_route else None)
                        != (occupied_route[0] if occupied_route else None)}
            else:
                relevance = 1.0
                counterfactual = {'ablation': 'route_relevance_disabled'}
            planning_ns += perf_counter_ns() - start_ns
            uncertainty = float(np.mean([item[2] for item in cells]))
            visibility = float(np.mean([item[1] for item in cells])) if self.use_visibility else 1.0
            timing = (1.0 / (1.0 + max(0, route_index - 1) / max(1, p.route_lookahead_actions))) if self.use_timing else 1.0
            score = visibility * uncertainty * relevance * timing
            results.append({'region': region, 'cells': coords, 'route_index': route_index,
                'visibility': visibility, 'uncertainty': uncertainty,
                'route_relevance': relevance, 'timing': timing, 'score': score,
                'nominal_route': nominal_route, 'nominal_cost': nominal_cost if math.isfinite(nominal_cost) else None,
                'counterfactual': counterfactual})
        best = max(results, key=lambda item: (item['score'], tuple(item['region']))) if results else None
        return positions, results, best, planning_ns

    def decide(self, step, position):
        start_ns = perf_counter_ns()
        position = tuple(map(int, position))
        if self.position != position:
            self.position = position
        if not hasattr(self, 'current_step') or step != self.current_step:
            self.current_step = int(step)
        planning_start = perf_counter_ns()
        nominal_route = self._plan(self.memory.grid, position, self.heading_yaw)
        planning_ns = perf_counter_ns() - planning_start
        _route_cells, candidates, best, planning_ns = self._candidate_scores(
            step, position, self.heading_yaw, nominal_route, planning_ns)
        p = self.parameters
        remaining = self.remaining
        route_estimate = self._route_cost(nominal_route)
        route_estimate = route_estimate if math.isfinite(route_estimate) else float(self.memory.grid.size)
        threshold = p.score_threshold + (p.budget_price * route_estimate / max(1, remaining)
                                         if remaining is not None and remaining > 0 else 0.0)
        score = float(best['score']) if best else 0.0
        requested = bool(step > 0 and best is not None and score >= threshold)
        granted = bool(requested and (remaining is None or remaining > 0))
        if requested and not granted:
            reason = 'observation_budget_exhausted'
        elif granted:
            reason = 'visible_uncertain_route_region_can_change_g1_plan'
            self.region_last_attempted[tuple(best['region'])] = int(step)
        elif best is None:
            reason = 'no_visible_uncertain_route_relevant_region'
        else:
            reason = 'best_region_score_below_budget_adjusted_threshold'
        self.requests += int(requested)
        self.denied += int(requested and not granted)
        decision_ns = perf_counter_ns() - start_ns
        diagnostic = {
            'episode_id': self.episode_id, 'step': int(step), 'position': position,
            'heading_yaw': float(self.heading_yaw), 'remaining_observation_budget': remaining,
            'last_observation_step': int(self.last_observation_step),
            'nominal_route': nominal_route,
            'nominal_route_cost': (self._route_cost(nominal_route)
                                   if math.isfinite(self._route_cost(nominal_route)) else None),
            'candidate_regions': candidates,
            'route_relevance': best['route_relevance'] if best else 0.0,
            'uncertainty': best['uncertainty'] if best else 0.0,
            'predicted_visibility': best['visibility'] if best else 0.0,
            'decision_impact': best['route_relevance'] if best else 0.0,
            'timing': best['timing'] if best else 0.0,
            'score': score, 'threshold': threshold, 'requested': requested,
            'granted': granted, 'reason': reason,
            'decision_time_ns': int(decision_ns), 'planning_time_ns': int(planning_ns),
            'observation_time_ns': None,
            'observation_effect': None,
        }
        if granted:
            diagnostic['_pre_observation'] = {'grid': self.memory.grid.copy(),
                'route': nominal_route, 'cost': route_estimate,
                'position': position, 'heading_yaw': self.heading_yaw}
        self.latest_diagnostic = diagnostic
        return {'observation_requested': requested, 'observation_granted': granted,
                'observation_score': score, 'observation_position': position,
                'rdao': diagnostic}

    def note_observation_duration(self, step, duration_ns):
        diagnostic = self.latest_diagnostic
        if diagnostic is not None and diagnostic['step'] == int(step):
            diagnostic['observation_time_ns'] = int(duration_ns)

    def refresh(self, observation, step):
        observation = np.asarray(observation, dtype=np.int8)
        if observation.shape != self.memory.grid.shape or not np.isin(observation, (-1, 0, 1)).all():
            raise ValueError('Invalid RDAO observation')
        if self.cap is not None and self.used >= self.cap:
            raise ValueError('Observation budget exhausted')
        diagnostic = self.latest_diagnostic
        before = self.memory.grid.copy()
        visible = observation >= 0
        self.memory.update(observation)
        self.last_observed[visible] = int(step)
        self.last_observation_step = int(step)
        self.used += 1
        # Match the navigation evaluator's public attempted-action feedback:
        # a new authorized map observation can release stale local exclusions.
        for key, signature in list(self.blocked_signatures.items()):
            if blocked_action_evidence_signature(self.memory.grid, key) != signature:
                self.blocked_signatures.pop(key, None)
                self.blocked_actions.discard(key)
        if diagnostic is not None and diagnostic.get('granted'):
            pre = diagnostic.pop('_pre_observation', None)
            if pre is not None:
                after_route = self._plan(self.memory.grid, pre['position'], pre['heading_yaw'])
                changed = np.argwhere(before != self.memory.grid)
                diagnostic['observation_effect'] = {
                    'visible_cells': np.argwhere(visible).tolist(),
                    'received_observation_values': [
                        {'cell': [int(x), int(y)], 'value': int(observation[y, x])}
                        for y, x in np.argwhere(visible)],
                    'memory_changed_cells': [{'cell': [int(x), int(y)],
                        'before': int(before[y, x]), 'after': int(self.memory.grid[y, x])}
                        for y, x in changed],
                    'memory_before': pre['grid'].tolist(),
                    'memory_after': self.memory.grid.tolist(),
                    'route_before': pre['route'], 'route_after': after_route,
                    'first_action_before': pre['route'][0] if pre['route'] else None,
                    'first_action_after': after_route[0] if after_route else None,
                    'route_cost_before': pre['cost'],
                    'route_cost_after': self._route_cost(after_route),
                    'selected_action_changed': (pre['route'][0] if pre['route'] else None)
                        != (after_route[0] if after_route else None),
                    'route_cost_changed': pre['cost'] != self._route_cost(after_route),
                    'visible_cell_count': int(np.count_nonzero(visible)),
                    'memory_changed_cell_count': int(len(changed)),
                }

