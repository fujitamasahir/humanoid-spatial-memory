"""Bounded public-map expected-regret approximation, NOT calibrated EVI."""
from dataclasses import dataclass
from time import perf_counter_ns
import math
import numpy as np
from .navigation import plan
from .scheduling import ObservationController
from .persistence import PersistenceMemory


@dataclass(frozen=True)
class EVIParameters:
    max_candidates: int = 3
    sensing_cost: float = .5
    plan_cost: float = .01
    scarcity_cost: float = .5
    failure_cost: float = 80.

    def __post_init__(self):
        if (type(self.max_candidates) is not int or not 1 <= self.max_candidates <= 3 or
            not all(np.isfinite(v) and v >= 0 for k, v in vars(self).items()
                    if k != 'max_candidates') or self.failure_cost <= 0):
            raise ValueError('Invalid EVI parameters')


def visible_cells(grid, position, yaw, *, range_m, cell_size, horizontal_fov_deg,
                  ray_count=61):
    """Memory-only ray traversal; no sensor/scene references or hidden probes."""
    if (ray_count != 61 or not 0 < horizontal_fov_deg <= 360 or
        min(range_m, cell_size) <= 0 or
        not all(math.isfinite(v) for v in (range_m, cell_size, horizontal_fov_deg, yaw))):
        raise ValueError('Invalid public sensor geometry')
    cells = set()
    for angle in np.linspace(-horizontal_fov_deg/2, horizontal_fov_deg/2, ray_count):
        theta = yaw+math.radians(angle)
        for distance in np.linspace(0, range_m/cell_size,
                                    math.ceil(range_m/cell_size/.1)+1):
            x = math.floor(position[0]+distance*math.cos(theta)+.5)
            y = math.floor(position[1]+distance*math.sin(theta)+.5)
            if not (0 <= y < grid.shape[0] and 0 <= x < grid.shape[1]):
                break
            cells.add((x, y))
            if grid[y, x] == 1:
                break
    return cells


def information_value(grid, probability, position, goal, yaw, unknown, sensor,
                      remaining, parameters=None):
    p = parameters or EVIParameters()
    nominal = plan(grid, position, goal, unknown)
    calls = 1
    footprint = visible_cells(grid, position, yaw, **sensor)
    route_cells = nominal or [position]
    candidates = [c for c in footprint if c != position and
                  .05 < probability[c[1], c[0]] < .95]
    def rank(c):
        distance = min(abs(c[0]-r[0])+abs(c[1]-r[1]) for r in route_cells)
        q = probability[c[1], c[0]]
        return (-q*(1-q)/(1+distance), c[1], c[0])
    candidates.sort(key=rank)
    best = {'value': 0., 'delay_regret': 0., 'cell': None, 'occupied_probability': None}
    for cell in candidates[:p.max_candidates]:
        routes = []
        for outcome in (0, 1):
            counterfactual = grid.copy()
            counterfactual[cell[1], cell[0]] = outcome
            routes.append(plan(counterfactual, position, goal, unknown))
            calls += 1
        def loss(route, occupied):
            if not route:
                return p.failure_cost
            return len(route)-1 + (p.failure_cost if occupied and cell in route else 0)
        q = float(probability[cell[1], cell[0]])
        losses = [[loss(route, o) for o in (0, 1)] for route in routes]
        before = min((1-q)*v[0]+q*v[1] for v in losses)
        after = (1-q)*min(v[0] for v in losses)+q*min(v[1] for v in losses)
        value = max(0., before-after)
        actions = [tuple(r[1]) if r and len(r) > 1 else None for r in routes]
        # One-step delay proxy: probability of choosing an outcome-wrong action.
        delay = value*min(q, 1-q) if actions[0] != actions[1] else 0.
        if (delay, value) > (best['delay_regret'], best['value']):
            best = {'value': value, 'delay_regret': delay, 'cell': cell,
                    'occupied_probability': q}
    cost = p.sensing_cost+p.plan_cost*calls+p.scarcity_cost/max(1, remaining)
    return {**best, 'cost': cost, 'net_value': best['delay_regret']-cost,
            'plan_calls': calls, 'visible_cells': len(footprint),
            'nominal_route': nominal}


class PersistenceEVIController:
    """B+Age, C+ternary or B+C. Only explicit public context enters decisions."""
    def __init__(self, initial, method, *, interval=2, radius=3, parameters=None,
                 max_observations=20, persistence=True, evi=True, sensor=None,
                 persistence_parameters=None, evi_parameters=None):
        if method != 'age' or not (persistence or evi):
            raise ValueError('Use Age base and at least one B/C component')
        if max_observations is None or not 1 <= max_observations <= 20:
            raise ValueError('A finite cap no greater than 20 is required')
        self.base = ObservationController(initial, method, interval=interval,
            radius=radius, parameters=parameters, max_observations=max_observations)
        self.belief = PersistenceMemory(initial, persistence_parameters) if persistence else None
        self.memory = self.belief if self.belief is not None else self.base.memory
        self.evi = evi
        self.sensor = dict(sensor or {})
        self.evi_parameters = evi_parameters or EVIParameters()
        self.context = None
        self.decisions = []
        self.observation_log = []
        self.requests = self.denied = 0
        self.scheduler_decision_total_ns = 0
        self._pending = None
        self._before_route = None
        self._prediction = None

    @property
    def used(self):
        return self.base.used

    @property
    def cap(self):
        return self.base.cap

    def set_navigation_context(self, *, goal, yaw, unknown):
        self.context = (tuple(goal), float(yaw), unknown)

    def probabilities(self, step):
        if self.belief is not None:
            return self.belief.probabilities(step)
        history = self.base.agent
        age = np.maximum(0, step-history.last_observed)
        q = .5+np.where(self.memory.grid == 1, .45, -.45)*np.exp(-.1*age)
        return np.where(history.last_observed < 0, .5, q)

    def decide(self, step, position):
        start = perf_counter_ns()
        if self._pending is not None:
            raise RuntimeError('Granted observation must be consumed before next decision')
        if self.belief is not None:
            self.belief.infer(step)
        detail = {}
        if self.evi:
            if self.context is None:
                raise RuntimeError('Public navigation context required')
            goal, yaw, unknown = self.context
            if self.used < self.cap and step > 0:
                detail = information_value(self.memory.grid, self.probabilities(step),
                    position, goal, yaw, unknown, self.sensor, self.cap-self.used,
                    self.evi_parameters)
                request = detail['net_value'] > 0
            else:
                request = False
            allowed = request and self.used < self.cap
        else:
            decision = self.base.decide(step, position)
            request, allowed = decision['observation_requested'], decision['observation_granted']
        self.requests += int(request)
        self.denied += int(request and not allowed)
        self._pending = (step, tuple(position)) if allowed else None
        self._before_route = detail.get('nominal_route')
        if allowed and self._before_route is None and self.context is not None:
            goal, _, unknown = self.context
            self._before_route = plan(self.memory.grid, position, goal, unknown)
        self._prediction = detail if allowed else None
        elapsed = perf_counter_ns()-start
        self.scheduler_decision_total_ns += elapsed
        self.decisions.append({'step': step, 'granted': bool(allowed),
            'used_before': self.used, 'scheduler_ns': elapsed, **detail})
        return {'observation_requested': bool(request), 'observation_granted': bool(allowed),
                'observation_score': detail.get('net_value'), 'observation_position': position}

    def refresh(self, observation, step):
        if self._pending is None or self._pending[0] != step or self.used >= self.cap:
            raise RuntimeError('Unauthorized belief refresh')
        position = self._pending[1]
        before = self.memory.grid.copy()
        self.base.refresh(observation, step)
        if self.belief is not None:
            self.belief.update(observation, step)
        route = None
        if self.context is not None:
            goal, _, unknown = self.context
            route = plan(self.memory.grid, position, goal, unknown)
        old = self._before_route
        first = lambda r: r[1] if r and len(r) > 1 else None
        predicted_cell = self._prediction.get('cell') if self._prediction else None
        observed_outcome = (int(observation[predicted_cell[1], predicted_cell[0]])
                            if predicted_cell is not None else None)
        self.observation_log.append({'step': step,
            'changed_cells': int(np.count_nonzero(before != self.memory.grid)),
            'route_changed': old != route if old is not None else None,
            'action_changed': first(old) != first(route) if old is not None else None,
            'route_length_delta': len(route)-len(old) if route and old else None,
            'predicted_value': self._prediction.get('value') if self._prediction else None,
            'predicted_delay_regret': self._prediction.get('delay_regret') if self._prediction else None,
            'predicted_cell': predicted_cell,
            'observed_candidate_outcome': observed_outcome,
            'realized_route': route})
        self._pending = None
