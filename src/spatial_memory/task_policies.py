"""Frozen Phase 1.4 public-history schedules; query gate is conceptual only.

No environment/configuration objects, sensor masks, or evaluation labels enter
this module. Timing is diagnostic and never affects a request.
"""
from dataclasses import dataclass
from time import perf_counter
import numpy as np
from .scheduling import AdaptiveObserver, AdaptiveParameters, ObservationController
from .observation import line_cells
from .policy_planning import PlanningMeter

METHODS = ('static', 'age', 'uncertainty', 'periodic1', 'periodic2', 'periodic5',
           'fixed-rate', 'random-quota', 'quota-periodic', 'route-weighted',
           'disruption-visible', 'query-gate-conceptual')
ABLATIONS = ('no-route-disruption', 'no-visibility', 'fixed-rate',
             'exclude-unknown', 'no-budget-threshold', 'no-alternative-candidates')


@dataclass(frozen=True)
class PolicyParameters:
    fixed_rate: float = .05
    entropy_threshold: float = .75
    route_weight: float = 3.0
    route_threshold: float = .75
    disruption_threshold: float = .1
    budget_price: float = .1
    reliability_threshold: float = .9
    visibility_fraction: float = .5

    def __post_init__(self):
        if not all(np.isfinite(v) for v in vars(self).values()):
            raise ValueError('Nonfinite policy parameter')
        if (not 0 < self.fixed_rate <= .35 or not 0 < self.entropy_threshold <= 1
            or self.route_weight < 0 or not 0 < self.route_threshold <= 1
            or self.disruption_threshold < 0 or self.budget_price < 0
            or not .5 < self.reliability_threshold <= 1
            or not 0 <= self.visibility_fraction <= 1):
            raise ValueError('Invalid policy parameters')


def precommit_schedule(method, cap, horizon, rng=None):
    if type(horizon) is not int or horizon < 1:
        raise ValueError('Invalid horizon')
    if cap is not None and (type(cap) is not int or cap < 1):
        raise ValueError('Invalid cap')
    quota = min(cap-1, horizon) if cap is not None else 8
    if quota > horizon:
        raise ValueError('Unlimited quota needs a horizon of at least eight')
    if method == 'random-quota':
        if rng is None:
            raise ValueError('Random schedule requires an independent RNG')
        return tuple(sorted(int(t) for t in rng.choice(np.arange(1,horizon+1), quota, replace=False)))
    if method == 'quota-periodic':
        return tuple(j*horizon//quota for j in range(1,quota+1))
    raise ValueError('Not a quota method')


def disk_cells(shape, position, radius):
    """Lexicographic (x,y), not array iteration order."""
    return [(x,y) for x in range(shape[1]) for y in range(shape[0])
            if (x-position[0])**2+(y-position[1])**2 <= radius**2]


def belief(observer, step, fixed_rate=None):
    observer._check_step(step)
    rate = observer.rates() if fixed_rate is None else fixed_rate
    age = np.maximum(0, step-observer.last_observed)
    sign = np.where(observer.memory.grid == 1, 1., -1.)
    probability = .5 + sign*(observer.parameters.confidence-.5)*np.exp(-2*rate*age)
    probability[observer.last_observed < 0] = .5
    entropy = -probability*np.log2(probability)-(1-probability)*np.log2(1-probability)
    return probability, entropy


def ray_prediction(probability, position, cell, known):
    blockers = sorted(set(line_cells(position, cell)) - {position, cell})
    value = np.float64(1.)
    for x,y in blockers:
        value *= 1-probability[y,x]
    return float(value), any(not known[y,x] for x,y in blockers)


def route_cost(route, size):
    return len(route)-1 if route else size+1


class TaskObserver:
    """Pure request computation from public pose, goal and observation history."""
    def __init__(self, initial, method, *, goal, radius=3, parameters=None,
                 ablation=None, schedule=(), observation_cost=1.5):
        if method not in METHODS or method in METHODS[:6]:
            raise ValueError('Expected a new policy')
        if ablation is not None and (method != 'disruption-visible' or ablation not in ABLATIONS):
            raise ValueError('Ablations apply only to disruption-visible')
        if not np.isfinite(observation_cost) or observation_cost < 0:
            raise ValueError('Invalid observation cost')
        if len(goal) != 2 or any(type(c) is not int for c in goal):
            raise ValueError('Invalid goal')
        if not (0 <= goal[0] < initial.shape[1] and 0 <= goal[1] < initial.shape[0]):
            raise ValueError('Goal outside map')
        self.history = AdaptiveObserver(initial, 'uncertainty', radius, AdaptiveParameters())
        self.memory = self.history.memory
        self.method, self.goal, self.radius = method, tuple(goal), radius
        self.parameters = parameters or PolicyParameters()
        self.ablation, self.schedule = ablation, frozenset(schedule)
        self.schedule_order = tuple(sorted(self.schedule))
        self.observation_cost = observation_cost
        self.planner = PlanningMeter()

    def refresh(self, observation, step):
        self.history.refresh(observation, step)

    def decide(self, step, position, remaining):
        p = self.parameters
        if self.method in {'random-quota','quota-periodic'}:
            self.history._check_step(step)
            return dict(requested=bool(step>0 and step in self.schedule), score=None, threshold=None,
                        details=dict(schedule=self.schedule_order,visibility=[]))
        fixed = p.fixed_rate if self.method == 'fixed-rate' else (.05 if self.ablation == 'fixed-rate' else None)
        probability, entropy = belief(self.history, step, fixed)
        grid = self.memory.grid
        cells = disk_cells(grid.shape, position, self.radius)
        known = self.history.last_observed >= 0
        # For the exclude-unknown ablation, unknown ray blockers stay exactly .5.
        # Other cells retain history-based probabilities.
        visibility_probability = probability.copy()
        visibility_probability[~known] = .5
        prediction = []
        for cell in (cells if self.method in {'disruption-visible','query-gate-conceptual'} else []):
            value, unknown_blocker = ray_prediction(visibility_probability, position, cell, known)
            if self.ablation == 'no-visibility':
                value = 1.0
            prediction.append(dict(cell=cell, probability=value, unknown_blocker=bool(unknown_blocker)))
        vis = {tuple(item['cell']): item['probability'] for item in prediction}
        details = dict(probabilities=probability.tolist(), entropy=entropy.tolist(),
                       visibility=prediction, candidates=[], route=[], masked_route=[],
                       ablation=self.ablation)
        requested, score, threshold = False, None, None
        if self.method in {'random-quota','quota-periodic'}:
            requested = step in self.schedule
            details['schedule'] = sorted(self.schedule)
        elif self.method == 'fixed-rate':
            eligible = [(x,y) for x,y in cells if known[y,x]]
            score = float(np.mean([entropy[y,x] for x,y in eligible])) if eligible else 0.
            threshold = p.entropy_threshold
            requested = bool(eligible) and score > threshold
        else:
            route = self.planner(grid, position, self.goal)
            details['route'] = route
            route_set = set(route)
            if self.method == 'route-weighted':
                weights = [1+p.route_weight*int(c in route_set) for c in cells]
                score = float(sum(np.float64(w)*entropy[y,x] for w,(x,y) in zip(weights,cells))/sum(weights)) if cells else 0.
                threshold = p.route_threshold
                details['weights'] = weights
                requested = bool(cells) and score > threshold
            elif self.method == 'query-gate-conceptual':
                reliability = np.maximum(probability,1-probability)
                reliability[~known] = .5
                masked = grid.copy()
                masked[reliability < p.reliability_threshold] = 1
                masked[position[1],position[0]] = grid[position[1],position[0]]
                masked_route = self.planner(masked, position, self.goal)
                low = [c for c in route if c != position and reliability[c[1],c[0]] < p.reliability_threshold]
                # U can extend outside the sensor disk: V there is zero.
                score = float(sum(np.float64(vis.get(c,0.)) for c in low)/len(low)) if low else 0.
                threshold = p.visibility_fraction
                next_cell = lambda r: r[1] if len(r)>1 else position
                degradation = route_cost(masked_route,grid.size)-route_cost(route,grid.size)
                requested = (bool(route) and bool(low) and next_cell(route)!=next_cell(masked_route)
                             and degradation >= 1 and score >= threshold)
                details.update(masked_route=masked_route, low_confidence_cells=low,
                               cost_increase=degradation)
            else:
                candidates = [c for c in cells if c != position]
                if self.ablation == 'exclude-unknown':
                    candidates = [c for c in candidates if known[c[1],c[0]]]
                if self.ablation == 'no-alternative-candidates':
                    candidates = [c for c in candidates if c in route_set]
                mass, score = np.float64(0.), np.float64(0.)
                for x,y in candidates:
                    costs = []
                    for state in (0,1):
                        counterfactual = grid.copy()
                        counterfactual[y,x] = state
                        costs.append(route_cost(self.planner(counterfactual,position,self.goal),grid.size))
                    disruption = min(grid.size,abs(costs[1]-costs[0]))/grid.size
                    if self.ablation == 'no-route-disruption':
                        disruption = 1.
                    risk = (probability[y,x] if grid[y,x]==0 else
                            1-probability[y,x] if grid[y,x]==1 else .5)
                    visible = vis[(x,y)]
                    score += np.float64(visible)*risk*disruption
                    mass += np.float64(visible)
                    details['candidates'].append(dict(cell=(x,y), costs=costs, disruption=float(disruption),
                                                       risk=float(risk), visibility=visible))
                h = max(1,route_cost(route,grid.size))
                price = 0. if self.ablation == 'no-budget-threshold' else p.budget_price
                threshold = p.disruption_threshold*self.observation_cost + (0. if remaining is None else price*h/max(1,remaining))
                score = float(score)
                requested = bool(candidates) and score > threshold and mass >= .25
                details.update(visible_mass=float(mass), remaining_path_estimate=h)
        return dict(requested=bool(step>0 and requested), score=score, threshold=threshold, details=details)


class PolicyController:
    """Shared budget gate; legacy schedules delegate to unchanged baseline code."""
    def __init__(self, initial, method, *, goal, radius=3, max_observations=None,
                 parameters=None, ablation=None, schedule=(), observation_cost=1.5):
        if method not in METHODS:
            raise ValueError('Unknown frozen method')
        if max_observations is not None and (type(max_observations) is not int or max_observations < 1):
            raise ValueError('Invalid observation cap')
        if method in METHODS[:6]:
            if ablation is not None or parameters is not None:
                raise ValueError('Historical definitions are frozen')
            interval = int(method[-1]) if method.startswith('periodic') else 2
            legacy_name = 'periodic' if method.startswith('periodic') else method
            self.observer = ObservationController(initial,legacy_name,interval=interval,radius=radius,
                                                  max_observations=max_observations)
            # Diagnostic public-history shadow: never influences the legacy decision.
            self.shadow = AdaptiveObserver(initial,'uncertainty',radius)
            self.legacy = True
        else:
            self.observer = TaskObserver(initial,method,goal=goal,radius=radius,parameters=parameters,
                                         ablation=ablation,schedule=schedule,observation_cost=observation_cost)
            self.legacy = False
        self.memory = self.observer.memory
        self.cap, self.used, self.requests, self.denied = max_observations, 1, 0, 0
        self.last_step = 0

    def decide(self, step, position):
        if type(step) is not int or step <= self.last_step:
            raise ValueError('Decisions require strictly increasing positive time')
        self.last_step = step
        begin = perf_counter()
        before = (0,0.) if self.legacy else self.observer.planner.snapshot()
        if self.legacy:
            decision = self.observer.decide(step,position)
            requested, granted = decision['observation_requested'], decision['observation_granted']
            # Ray predictions are diagnostic for legacy policies; measured separately.
            elapsed = perf_counter()-begin
            diagnostic_begin = perf_counter()
            probability, _ = belief(self.shadow,step)
            known = self.shadow.last_observed>=0
            prediction = []
            for cell in disk_cells(self.memory.grid.shape,position,self.shadow.radius):
                value, unknown = ray_prediction(probability,position,cell,known)
                prediction.append(dict(cell=cell,probability=value,unknown_blocker=bool(unknown)))
            details = dict(visibility=prediction, diagnostic_only=True)
            diagnostic_seconds = perf_counter()-diagnostic_begin
            score, threshold = decision['observation_score'], None
        else:
            result = self.observer.decide(step,position,None if self.cap is None else self.cap-self.used)
            elapsed = perf_counter()-begin
            diagnostic_seconds = 0.
            if not result['details']['visibility']:
                diagnostic_begin = perf_counter()
                probability,_ = belief(self.observer.history,step,
                    self.observer.parameters.fixed_rate if self.observer.method=='fixed-rate' else None)
                known = self.observer.history.last_observed>=0
                prediction=[]
                for cell in disk_cells(self.memory.grid.shape,position,self.observer.radius):
                    value,unknown=ray_prediction(probability,position,cell,known)
                    prediction.append(dict(cell=cell,probability=value,unknown_blocker=bool(unknown)))
                result['details']['visibility']=prediction
                result['details']['visibility_diagnostic_only']=True
                diagnostic_seconds=perf_counter()-diagnostic_begin
            requested = result['requested']
            granted = requested and (self.cap is None or self.used < self.cap)
            details, score, threshold = result['details'], result['score'], result['threshold']
        self.requests += int(requested)
        self.denied += int(requested and not granted)
        after = (0,0.) if self.legacy else self.observer.planner.snapshot()
        return dict(observation_requested=bool(requested),observation_granted=bool(granted),
                    observation_score=score,observation_position=position,threshold=threshold,
                    reason='threshold_or_schedule_met' if requested else 'criterion_not_met',
                    remaining_budget=None if self.cap is None else self.cap-self.used,
                    scheduler_seconds=elapsed,diagnostic_seconds=diagnostic_seconds,
                    scheduler_astar_calls=after[0]-before[0],scheduler_astar_seconds=after[1]-before[1],
                    policy_details=details)

    def refresh(self, observation, step):
        if self.cap is not None and self.used >= self.cap:
            raise ValueError('Observation budget exhausted')
        self.observer.refresh(observation,step)
        if self.legacy:
            self.shadow.refresh(observation,step)
        self.used += 1
