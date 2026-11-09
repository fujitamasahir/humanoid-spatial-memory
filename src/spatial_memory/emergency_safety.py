"""Independent, temporary near-field sensing and conservative action overrides.

This sensor is intentionally separate from the agent's scheduled occupancy
observations. It returns only ray-measured cells and never exposes simulator
coordinates, schedules, or future proxy poses to the safety controller.
"""
from __future__ import annotations

import math
from collections import deque

import numpy as np

from .mujoco_perception import MujocoRayPerception
from .navigation import (CARDINALS, _move_clear_observed_free,
                         blocked_action_key, heading_index)
from .pedestrian_tracking import _clusters


class IndependentEmergencySafetySensor:
    """360-degree MuJoCo ray scanner with a short, observation-only track."""

    def __init__(self, scene, *, range_m=2.0, ray_count=181,
                 sample_spacing_m=0.075, ray_backend='multi'):
        self.scene = scene
        self.rays = MujocoRayPerception(scene, range_m=range_m,
            horizontal_fov_deg=360.0, ray_count=ray_count,
            sample_spacing_m=sample_spacing_m, ray_backend=ray_backend)
        self.history = deque(maxlen=3)

    def scan(self, world, position, heading_yaw):
        """Return measured ternary local cells and non-oracular diagnostics."""
        grid = self.rays.observe(world, position, heading_yaw)
        stats = dict(self.rays.last_stats)
        cells = tuple(tuple(map(int, cell))
                      for cell in stats['visible_pedestrian_cells'])
        clusters = _clusters(cells)
        center = clusters[0] if len(clusters) == 1 else None
        step = int(world.step)
        self.history.append((step, center))
        motion = self._motion_estimate()
        free = np.argwhere(grid == 0)
        occupied = np.argwhere(grid == 1)
        record = {
            'step': step,
            'position_before_action': list(map(int, position)),
            'heading_yaw_before_action': float(heading_yaw),
            'range_m': self.rays.range_m,
            'horizontal_fov_deg': self.rays.horizontal_fov_deg,
            'ray_count': self.rays.ray_count,
            'ray_hits': int(stats['ray_hits']),
            'hits_by_type': dict(stats['hits_by_type']),
            'free_cells': int(stats['free_cells']),
            'occupied_cells': int(stats['occupied_cells']),
            'visible_pedestrian_cells': [list(c) for c in cells],
            'visible_persistent_obstacle_cells': stats['visible_persistent_obstacle_cells'],
            'measured_free_cells_xy': [[int(x), int(y)] for y, x in free],
            'measured_occupied_cells_xy': [[int(x), int(y)] for y, x in occupied],
            'estimated_pedestrian_hit_cluster_cells': [list(c) for c in clusters],
            'motion_estimate': motion,
        }
        return {'grid': grid, 'visible_pedestrian_cells': cells,
                'motion_estimate': motion, 'record': record}

    def _motion_estimate(self):
        valid = [(step, center) for step, center in self.history if center is not None]
        if len(valid) < 2:
            return {'state': 'unknown', 'velocity_cells_per_step': None}
        first, last = valid[-2], valid[-1]
        elapsed = last[0] - first[0]
        if elapsed <= 0:
            return {'state': 'unknown', 'velocity_cells_per_step': None}
        vx = (last[1][0] - first[1][0]) / elapsed
        vy = (last[1][1] - first[1][1]) / elapsed
        if abs(vx) + abs(vy) < 0.12:
            prior_movement = any(
                abs(b[1][0] - a[1][0]) + abs(b[1][1] - a[1][1]) >= 0.35
                for a, b in zip(valid[:-2], valid[1:-1]))
            return {'state': 'uncertain_after_recent_motion' if prior_movement else 'stationary_or_unknown',
                    'velocity_cells_per_step': [0.0, 0.0]}
        return {'state': 'measured_motion',
                'velocity_cells_per_step': [float(vx), float(vy)]}


def _cardinal_direction(motion):
    velocity = motion.get('velocity_cells_per_step')
    if motion.get('state') != 'measured_motion' or not velocity:
        return None
    vx, vy = velocity
    if abs(vx) >= abs(vy):
        return (1 if vx > 0 else -1, 0)
    return (0, 1 if vy > 0 else -1)


def _reachable_proxy_cells(measurement):
    current = {tuple(cell) for cell in measurement['visible_pedestrian_cells']}
    if not current:
        return set()
    direction = _cardinal_direction(measurement['motion_estimate'])
    if direction is not None:
        return current | {(x + direction[0], y + direction[1]) for x, y in current}
    # If velocity is unknown or has just stopped, conservatively consider one
    # cardinal proxy step in any direction. This is a reachable-set bound, not
    # a claim about the prescribed next schedule position.
    return current | {(x + dx, y + dy) for x, y in current for dx, dy in CARDINALS}


def _swept_footprint_cells(scene, start, target, yaw):
    """Raster cells touched by the public G1 AABB along a selected translation."""
    x0, y0 = map(float, start)
    x1, y1 = map(float, target)
    distance = math.hypot(x1 - x0, y1 - y0) * scene.cell_size
    samples = max(1, math.ceil(distance / (scene.cell_size / 10)))
    hx, hy = scene.footprint_half_extents_local
    c, s = abs(math.cos(yaw)), abs(math.sin(yaw))
    hx, hy = c * hx + s * hy, s * hx + c * hy
    rx = (hx + 0.505 * scene.cell_size) / scene.cell_size
    ry = (hy + 0.505 * scene.cell_size) / scene.cell_size
    touched = set()
    height, width = scene.scenario.height, scene.scenario.width
    for i in range(samples + 1):
        x = x0 + (x1 - x0) * i / samples
        y = y0 + (y1 - y0) * i / samples
        for cy in range(math.ceil(y - ry), math.floor(y + ry) + 1):
            for cx in range(math.ceil(x - rx), math.floor(x + rx) + 1):
                if 0 <= cx < width and 0 <= cy < height:
                    touched.add((cx, cy))
    return touched


def _footprint_cells(scene, position, yaw):
    return _swept_footprint_cells(scene, position, position, yaw)


class EmergencySafetyController:
    """Override only a selected action threatened by observed near-field motion.

    This class has no reference to the scene, simulator, or collision shield.
    Clearance comes only from the safety sensor's latest ternary ray grid and
    public G1 footprint dimensions. The evaluator checks the final chosen
    action once with the existing MuJoCo shield.
    """

    def __init__(self, scene):
        self.width = scene.scenario.width
        self.height = scene.scenario.height
        self.cell_size = scene.cell_size
        self.local_extents = scene.footprint_half_extents_local
        self.dimensions = _FootprintDimensions(self.width, self.height,
                                               self.cell_size, self.local_extents)

    def choose(self, memory_grid, position, goal, heading_yaw, selected_action,
               measurement, step, blocked_actions=frozenset()):
        del memory_grid, goal  # Memory is never written or read for clearance.
        visible = measurement['visible_pedestrian_cells']
        if not visible:
            return None
        if selected_action is None:
            selected_action = ('wait', 'no_feasible_base_action')
        reachable = _reachable_proxy_cells(measurement)
        kind, value = selected_action
        target = tuple(value) if kind in {'move', 'sidestep', 'retreat'} else tuple(position)
        action_footprint = _footprint_cells(self.dimensions, target, heading_yaw)
        stationary = _footprint_cells(self.dimensions, position, heading_yaw)
        action_risk = action_footprint & reachable
        stationary_risk = stationary & reachable
        if not action_risk and not stationary_risk:
            return None
        if stationary_risk and not action_risk:
            # The planner already chose a measured-safe action that leaves the
            # threatened footprint. Preserve that forward-first escape.
            return None

        # If only the selected destination is threatened and the currently
        # occupied footprint is outside the one-step reachable hazard set,
        # postpone the action. Escape motion is reserved for a threatened
        # stationary footprint so waiting is evaluated rather than assumed safe.
        if action_risk and not stationary_risk:
            intervention_action = ('wait', 'observed_destination_risk_current_footprint_clear')
            escape_sweep = stationary
            reason = 'observed_destination_risk_wait_is_safer_than_selected_action'
            return {
                'action': intervention_action,
                'intervention': {
                    'step': int(step),
                    'position_before_action': list(map(int, position)),
                    'heading_yaw': float(heading_yaw),
                    'selected_action_before': [kind, list(value) if isinstance(value, tuple) else value],
                    'selected_action_after': [intervention_action[0], intervention_action[1]],
                    'reason': reason,
                    'motion_estimate': measurement['motion_estimate'],
                    'visible_pedestrian_cells': [list(cell) for cell in visible],
                    'reachable_proxy_cells_from_observations': [list(cell) for cell in sorted(reachable)],
                    'selected_action_footprint_cells_at_risk': [list(cell) for cell in sorted(action_risk)],
                    'stationary_footprint_cells_at_risk': [],
                    'escape_swept_footprint_cells': [list(cell) for cell in sorted(escape_sweep)],
                    'escape_clearance_source': 'current G1 footprint is outside the observed one-step reachable hazard set',
                },
            }

        face = heading_index(heading_yaw)
        dx, dy = CARDINALS[face]
        left = (-dy, dx)
        side_targets = [
            (position[0] + left[0], position[1] + left[1]),
            (position[0] - left[0], position[1] - left[1]),
        ]
        candidates = []
        scan_grid = measurement['grid']
        for preference, side in enumerate(side_targets):
            if not (0 <= side[0] < self.width and 0 <= side[1] < self.height):
                continue
            if not _move_clear_observed_free(scan_grid, position, side, face,
                                             self.local_extents, self.cell_size):
                continue
            if blocked_action_key(position, face, ('sidestep', side)) in blocked_actions:
                continue
            sweep = _swept_footprint_cells(self.dimensions, position, side, heading_yaw)
            final_footprint = _footprint_cells(self.dimensions, side, heading_yaw)
            if final_footprint & reachable:
                continue
            separation = min((abs(sx - hx) + abs(sy - hy)
                              for sx, sy in final_footprint for hx, hy in reachable), default=0)
            candidates.append((-separation, preference, side, sweep))
        if candidates:
            _, _, escape, escape_sweep = min(candidates)
            intervention_action = ('sidestep', escape)
            reason = 'observed_dynamic_reachable_set_blocks_selected_action'
        else:
            retreat = (position[0] - dx, position[1] - dy)
            retreat_sweep = _swept_footprint_cells(self.dimensions, position,
                                                   retreat, heading_yaw)
            retreat_footprint = _footprint_cells(self.dimensions, retreat, heading_yaw)
            if (0 <= retreat[0] < self.width and 0 <= retreat[1] < self.height
                    and blocked_action_key(position, face, ('retreat', retreat)) not in blocked_actions
                    and not (retreat_footprint & reachable)
                    and _move_clear_observed_free(scan_grid, position, retreat, face,
                        self.local_extents, self.cell_size)):
                intervention_action = ('retreat', retreat)
                escape_sweep = retreat_sweep
                reason = 'observed_dynamic_reachable_set_blocks_selected_action_no_safe_lateral_escape'
            else:
                intervention_action = ('wait', 'emergency_dynamic_hazard_no_observed_clear_escape')
                escape_sweep = stationary
                reason = 'emergency_dynamic_hazard_no_observed_clear_escape'
        return {
            'action': intervention_action,
            'intervention': {
                'step': int(step),
                'position_before_action': list(map(int, position)),
                'heading_yaw': float(heading_yaw),
                'selected_action_before': [kind, list(value) if isinstance(value, tuple) else value],
                'selected_action_after': [intervention_action[0],
                    list(intervention_action[1]) if isinstance(intervention_action[1], tuple)
                    else intervention_action[1]],
                'reason': reason,
                'motion_estimate': measurement['motion_estimate'],
                'visible_pedestrian_cells': [list(cell) for cell in visible],
                'reachable_proxy_cells_from_observations': [list(cell) for cell in sorted(reachable)],
                'selected_action_footprint_cells_at_risk': [list(cell) for cell in sorted(action_risk)],
                'stationary_footprint_cells_at_risk': [list(cell) for cell in sorted(stationary_risk)],
                'escape_swept_footprint_cells': [list(cell) for cell in sorted(escape_sweep)],
                'escape_clearance_source': 'latest independent sensor scan; every swept footprint cell measured free',
            },
        }

class _FootprintDimensions:
    def __init__(self, width, height, cell_size, local_extents):
        self.scenario = type('ScenarioShape', (), {'width': width, 'height': height})()
        self.cell_size = cell_size
        self.footprint_half_extents_local = local_extents
