"""DAO engineering prototype: public-map discovery, never a physical reading.

No simulator, planner, shield, belief inference or dataset dependency. A route
is an optional public point-grid prefix supplied by the caller, not computed
here. This module does not establish calibrated expected information gain.
"""
from __future__ import annotations
from dataclasses import dataclass
import math
import numpy as np
from .memory import Memory

MODES = ('dao_veto', 'dao_trigger', 'dao_route', 'dao_combined',
         'periodic4', 'periodic5', 'age4', 'age5', 'age6')


@dataclass(frozen=True)
class DAOParameters:
    age: int = 5
    radius: int = 3
    fraction: float = .5
    new_cells: int = 5
    stale_cells: int = 3
    cooldown: int = 3
    fallback_age: int = 10
    route_moves: int = 5
    route_band: int = 1

    def __post_init__(self):
        if any(type(v) is not int or v < 1 for k, v in vars(self).items()
               if k != 'fraction') or not 0 < self.fraction <= 1:
            raise ValueError('Invalid DAO parameters')


def _grid(grid):
    grid = np.asarray(grid)
    if grid.ndim != 2 or not grid.size or grid.size > 4096 or not np.isin(grid, [-1, 0, 1]).all():
        raise ValueError('DAO requires a nonempty ternary grid of at most 4096 cells')
    return grid


def _point(point, shape):
    if len(point) != 2 or any(not isinstance(v, (int, np.integer)) for v in point):
        raise ValueError('Integer public grid pose required')
    x, y = map(int, point)
    if not (0 <= x < shape[1] and 0 <= y < shape[0]):
        raise ValueError('Point outside public map')
    return x, y


def predicted_footprints(grid, position, yaw, *, range_m=6., cell_size=.75,
                         horizontal_fov_deg=120., ray_count=61):
    """Same angular/sample convention as evi.visible_cells, plus first-unknown stop.

    Frontier is a subset of optimistic public visibility. It is NOT a lower
    bound on physical 3D visibility. Current cell is excluded from both sets.
    Both sets include the remembered occupied endpoint. At most 61*81 samples.
    """
    grid = _grid(grid); position = _point(position, grid.shape)
    if (ray_count != 61 or not all(math.isfinite(v) for v in
            (yaw, range_m, cell_size, horizontal_fov_deg)) or
            cell_size <= 0 or not 0 < range_m/cell_size <= 8 or
            not 0 < horizontal_fov_deg <= 120):
        raise ValueError('Unsupported bounded sensor geometry')
    optimistic, frontier = set(), set(); samples = 0
    distances = np.linspace(0, range_m/cell_size, math.ceil(range_m/cell_size/.1)+1)
    for angle in np.linspace(-horizontal_fov_deg/2, horizontal_fov_deg/2, 61):
        theta = yaw + math.radians(angle); stopped = False
        for d in distances:
            samples += 1
            x = math.floor(position[0]+d*math.cos(theta)+.5)
            y = math.floor(position[1]+d*math.sin(theta)+.5)
            if not (0 <= x < grid.shape[1] and 0 <= y < grid.shape[0]):
                break
            cell = (x, y)
            if cell != position:
                optimistic.add(cell)
                if not stopped:
                    frontier.add(cell)
                    if grid[y, x] == -1:
                        stopped = True
            if grid[y, x] == 1:
                break
    return {'optimistic': optimistic, 'frontier': frontier, 'samples': samples,
            'predicted_rays': 61, 'actual_sensor_calls': 0, 'plan_calls': 0}


def assess(grid, last_observed, step, position, yaw, *, route=None,
           parameters=None, sensor=None):
    p = parameters or DAOParameters(); grid = _grid(grid)
    last = np.asarray(last_observed)
    if (last.shape != grid.shape or not np.issubdtype(last.dtype, np.integer) or
            type(step) is not int or step < 0 or (last < -1).any() or
            (last > step).any() or not np.array_equal(last >= 0, grid >= 0)):
        raise ValueError('Inconsistent authorized timestamps')
    position = _point(position, grid.shape)
    footprints = predicted_footprints(grid, position, yaw, **(sensor or {}))
    x, y = position; r = p.radius
    # Bounded local window, original circular Age semantics.
    x0, x1 = max(0, x-r), min(grid.shape[1], x+r+1)
    y0, y1 = max(0, y-r), min(grid.shape[0], y+r+1)
    yy, xx = np.ogrid[y0:y1, x0:x1]; local = last[y0:y1, x0:x1]
    known = (local >= 0) & ((xx-x)**2+(yy-y)**2 <= r*r)
    scores = {str(age): float(np.mean((step-local[known]) >= age)) if known.any() else 0.
              for age in (4, 5, 6)}
    oldest = int(np.max(step-local[known])) if known.any() else 0
    prefix = []
    if route is not None:
        for cell in route:
            prefix.append(_point(cell, grid.shape))
            if len(prefix) >= p.route_moves+1:
                break
        if prefix and prefix[0] != position:
            raise ValueError('Public route must start at current pose')
        if any(abs(a[0]-b[0])+abs(a[1]-b[1]) != 1 for a, b in zip(prefix, prefix[1:])):
            raise ValueError('Public route must be cardinal and contiguous')
        if any(grid[c[1], c[0]] == 1 for c in prefix):
            raise ValueError('Nominal route cannot cross remembered occupancy')
    route_cells = prefix[1:]
    detail = {'age_scores': scores, 'oldest_local_age': oldest,
              'local_known_cells': int(known.sum()), 'route_available': bool(route_cells),
              'predicted_rays': 61, 'sample_visits': footprints['samples'],
              'plan_calls': 0, 'actual_sensor_calls': 0}
    for name in ('frontier', 'optimistic'):
        cells = footprints[name]
        new = {c for c in cells if grid[c[1], c[0]] == -1}
        stale = {c for c in cells if last[c[1], c[0]] >= 0 and step-last[c[1], c[0]] >= p.age}
        known_count = sum(grid[c[1], c[0]] >= 0 for c in cells)
        relevant = {c for c in new if any(abs(c[0]-v[0])+abs(c[1]-v[1]) <= p.route_band for v in route_cells)}
        detail[name] = {'visible': len(cells), 'new': len(new), 'stale': len(stale),
                        'known': known_count, 'stale_fraction': len(stale)/known_count if known_count else 0.,
                        'route_new': len(relevant)}
    return detail


def request_rule(detail, step, scan_gap, mode, parameters=None):
    """Pure rule: same-state mechanism ablations; not episode scan-count ordering."""
    if mode not in MODES or type(step) is not int or type(scan_gap) is not int or not 0 <= scan_gap <= step:
        raise ValueError('Invalid mode/time')
    p = parameters or DAOParameters()
    age5 = step > 0 and detail['age_scores']['5'] >= p.fraction
    fallback = step > 0 and detail['oldest_local_age'] >= p.fallback_age
    f = detail['frontier']
    discovery = f['new'] >= p.new_cells
    verification = f['stale'] >= p.stale_cells or (f['known'] > 0 and f['stale_fraction'] >= p.fraction)
    early = step > 0 and scan_gap >= p.cooldown and discovery
    route_early = early and f['route_new'] > 0
    if mode.startswith('periodic'):
        requested = step > 0 and step % int(mode[-1]) == 0; reason = 'fixed_clock'
    elif mode.startswith('age'):
        requested = step > 0 and detail['age_scores'][mode[-1]] >= p.fraction; reason = 'fixed_age'
    elif mode == 'dao_veto':
        requested = fallback or (age5 and (discovery or verification)); reason = 'veto_or_fallback'
    elif mode == 'dao_trigger':
        requested = fallback or age5 or early; reason = 'discovery_trigger_or_anchor'
    elif mode == 'dao_route':
        requested = fallback or age5 or route_early; reason = 'route_discovery_trigger_or_anchor'
    else:
        requested = fallback or (age5 and (discovery or verification)) or early; reason = 'combined'
    return {'requested': bool(requested), 'age5_anchor': bool(age5),
            'fallback': bool(fallback), 'discovery_high': bool(discovery),
            'verification_high': bool(verification), 'early': bool(early),
            'route_early': bool(route_early), 'reason': reason}


class DiscoveryController:
    """Authorized-only memory, finite cap, compatible decide/refresh boundary.

    Caller must supply fresh public context before EACH decide; route optional.
    No automatic navigation runner is enabled by this engineering prototype.
    """
    def __init__(self, initial, *, mode='dao_veto', max_observations=20,
                 parameters=None, sensor=None):
        if mode not in MODES or type(max_observations) is not int or not 1 <= max_observations <= 20:
            raise ValueError('Invalid mode/cap')
        initial = _grid(initial)
        self.memory = Memory(initial.shape); self.memory.update(initial)
        self.last_observed = np.where(initial >= 0, 0, -1).astype(np.int64)
        self.mode, self.cap, self.used = mode, max_observations, 1
        self.parameters = parameters or DAOParameters(); self.sensor = dict(sensor or {})
        self.requests = self.denied = 0; self.last_scan_step = 0
        self._latest = 0; self._pending = None; self._context = None
        self.decisions = []

    def set_navigation_context(self, *, goal, yaw, route=None, **unused):
        # No extra context (e.g. actual geometry) is consumed.
        goal = _point(goal, self.memory.grid.shape)
        if not math.isfinite(yaw):
            raise ValueError('Finite public heading required')
        self._context = (goal, float(yaw), None if route is None else tuple(map(tuple, route)))

    def decide(self, step, position):
        if type(step) is not int or step <= self._latest or self._pending is not None or self._context is None:
            raise RuntimeError('Need increasing decision, fresh context and no unconsumed grant')
        goal, yaw, route = self._context
        detail = assess(self.memory.grid, self.last_observed, step, position, yaw,
                        route=route, parameters=self.parameters, sensor=self.sensor)
        result = request_rule(detail, step, step-self.last_scan_step, self.mode, self.parameters)
        granted = result['requested'] and self.used < self.cap
        self.requests += int(result['requested']); self.denied += int(result['requested'] and not granted)
        self.decisions.append({'step': step, 'goal': goal, **detail, **result,
                               'granted': bool(granted), 'used_before': self.used})
        self._pending = step if granted else None; self._latest = step; self._context = None
        return {'observation_requested': result['requested'], 'observation_granted': bool(granted),
                'observation_score': detail['frontier']['new'], 'observation_position': tuple(position)}

    def refresh(self, observation, step):
        if self._pending != step or self._pending is None or self.used >= self.cap:
            raise RuntimeError('Unauthorized paid observation')
        observation = np.asarray(observation)
        if observation.shape != self.memory.grid.shape or not np.isin(observation, [-1, 0, 1]).all():
            raise ValueError('Invalid ternary observation')
        visible = observation >= 0
        self.memory.update(observation); self.last_observed[visible] = step
        self.used += 1; self.last_scan_step = step; self._pending = None
