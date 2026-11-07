"""Observation-history-only schedules, without simulator, goal or planner access."""
from dataclasses import dataclass
import numpy as np
from .memory import Baseline, Memory


@dataclass(frozen=True)
class AdaptiveParameters:
    age_steps: int = 4
    stale_fraction: float = 0.5
    entropy_threshold: float = 0.75
    confidence: float = 0.95
    prior_flips: float = 0.3
    prior_exposure: float = 6.0
    min_rate: float = 0.01
    max_rate: float = 0.35

    def __post_init__(self):
        if (not all(np.isfinite(v) for v in vars(self).values())
            or not isinstance(self.age_steps, int) or self.age_steps < 1
            or not 0 < self.stale_fraction <= 1
            or not 0 < self.entropy_threshold <= 1 or not 0.5 < self.confidence < 1
            or self.prior_flips <= 0 or self.prior_exposure <= 0
            or not 0 < self.min_rate <= self.max_rate):
            raise ValueError('Invalid adaptive parameters')


class AdaptiveObserver:
    """Last-write map plus timestamps and optional history-based confidence model."""
    def __init__(self, initial, method, radius, parameters=None):
        if method not in {'age', 'uncertainty'} or radius < 0:
            raise ValueError('Invalid adaptive observer')
        self.method, self.radius = method, radius
        self.parameters = parameters or AdaptiveParameters()
        self.memory = Memory(initial.shape)
        self.last_observed = np.full(initial.shape, -1, dtype=np.int64)
        self.flips = np.zeros(initial.shape, dtype=np.int64)
        self.exposure = np.zeros(initial.shape, dtype=float)
        self.latest_step = 0
        self.refresh(initial, 0)

    def _check_step(self, step):
        if not isinstance(step, int) or step < self.latest_step:
            raise ValueError('Observation history requires monotonic integer time')

    def refresh(self, observation, step):
        self._check_step(step)
        # Validate before mutating any history.
        if observation.shape != self.memory.grid.shape or not np.isin(observation, [-1, 0, 1]).all():
            raise ValueError('Invalid observation')
        visible = observation >= 0
        repeated = visible & (self.last_observed >= 0)
        self.flips[repeated] += observation[repeated] != self.memory.grid[repeated]
        self.exposure[repeated] += step - self.last_observed[repeated]
        self.memory.update(observation)
        self.last_observed[visible] = step
        self.latest_step = step

    def rates(self):
        p = self.parameters
        return np.clip((p.prior_flips + self.flips) / (p.prior_exposure + self.exposure),
                       p.min_rate, p.max_rate)

    def uncertainty(self, step):
        """Binary entropy in bits. Unknown cells have entropy 1 but are not scored."""
        self._check_step(step)
        p = self.parameters
        age = np.maximum(0, step - self.last_observed)
        sign = np.where(self.memory.grid == 1, 1.0, -1.0)
        probability = 0.5 + sign * (p.confidence - 0.5) * np.exp(-2 * self.rates() * age)
        probability[self.last_observed < 0] = 0.5
        return -probability*np.log2(probability) - (1-probability)*np.log2(1-probability)

    def score(self, step, position):
        self._check_step(step)
        yy, xx = np.indices(self.memory.grid.shape)
        footprint = ((xx-position[0])**2 + (yy-position[1])**2 <= self.radius**2)
        known = footprint & (self.last_observed >= 0)
        if not known.any():
            return 0.0
        if self.method == 'age':
            return float(np.mean(step-self.last_observed[known] >= self.parameters.age_steps))
        return float(np.mean(self.uncertainty(step)[known]))

    def threshold(self):
        return (self.parameters.stale_fraction if self.method == 'age'
                else self.parameters.entropy_threshold)


class ObservationController:
    """Shared cap includes initialization; denial never calls a sensor or refresh."""
    def __init__(self, initial, method, *, interval=2, radius=3,
                 parameters=None, max_observations=None):
        cap = max_observations
        if cap is not None and (type(cap) is not int or cap < 1):
            raise ValueError('Observation cap must be null or a positive integer')
        self.cap, self.used = cap, 1
        self.requests = self.denied = 0
        if method in {'static', 'periodic'}:
            self.agent = Baseline(initial.shape, initial, method, interval)
        else:
            self.agent = AdaptiveObserver(initial, method, radius, parameters)
        self.memory = self.agent.memory

    def decide(self, step, position):
        if isinstance(self.agent, AdaptiveObserver):
            score = self.agent.score(step, position)
            requested = step > 0 and score >= self.agent.threshold()
        else:
            score = None
            requested = self.agent.needs_observation(step)
        allowed = requested and (self.cap is None or self.used < self.cap)
        self.requests += int(requested)
        self.denied += int(requested and not allowed)
        return dict(observation_requested=bool(requested), observation_granted=bool(allowed),
                    observation_score=score, observation_position=position)

    def refresh(self, observation, step):
        if self.cap is not None and self.used >= self.cap:
            raise ValueError('Observation budget exhausted')
        if isinstance(self.agent, AdaptiveObserver):
            self.agent.refresh(observation, step)
        else:
            self.agent.refresh(observation)
        self.used += 1
