"""Observation-only asymmetric endpoint-hazard memory; probabilities uncalibrated."""
from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class PersistenceParameters:
    free_prior_exposure: float = 30.
    occupied_prior_exposure: float = 6.
    prior_transitions: float = .3
    confidence: float = .95
    min_rate: float = .001
    max_rate: float = .35
    free_threshold: float = .2
    occupied_threshold: float = .8
    persistence_horizon: float = 8.

    def __post_init__(self):
        if (not all(np.isfinite(v) for v in vars(self).values()) or
            min(self.free_prior_exposure, self.occupied_prior_exposure,
                self.prior_transitions, self.persistence_horizon) <= 0 or
            not 0 < self.min_rate <= self.max_rate or
            not .5 < self.confidence < 1 or
            not 0 < self.free_threshold < .5 < self.occupied_threshold < 1):
            raise ValueError('Invalid persistence parameters')


class PersistenceMemory:
    def __init__(self, initial, parameters=None):
        initial = np.asarray(initial)
        if initial.ndim != 2:
            raise ValueError('A two-dimensional occupancy grid is required')
        self.params = parameters or PersistenceParameters()
        self.grid = np.full(initial.shape, -1, dtype=np.int8)
        self.last_state = self.grid.copy()
        self.last_observed = np.full(initial.shape, -1, dtype=np.int64)
        self.transitions = np.zeros((2, *initial.shape), dtype=np.int64)
        self.exposure = np.zeros((2, *initial.shape), dtype=float)
        self.latest_step = 0
        self.observed_updates = 0
        self.inference_log = []
        self.calibration = []
        self.update(initial, 0)

    def _check_step(self, step):
        if type(step) is not int or step < self.latest_step:
            raise ValueError('Monotonic integer time required')

    def rates(self):
        p = self.params
        priors = np.array([p.free_prior_exposure, p.occupied_prior_exposure])
        return np.clip((p.prior_transitions+self.transitions) /
                       (priors[:, None, None]+self.exposure), p.min_rate, p.max_rate)

    def probabilities(self, step):
        self._check_step(step)
        a, b = self.rates()
        equilibrium = a/(a+b)
        q = np.where(self.last_state == 1, self.params.confidence,
                     1-self.params.confidence)
        age = np.maximum(0, step-self.last_observed)
        prob = equilibrium + (q-equilibrium)*np.exp(-(a+b)*age)
        return np.where(self.last_observed < 0, .5, prob)

    def persistence_confidence(self):
        return np.exp(-self.rates()[1]*self.params.persistence_horizon)

    def project(self, step):
        p = self.probabilities(step)
        known = self.last_observed >= 0
        grid = np.full(self.grid.shape, -1, dtype=np.int8)
        grid[known & (p <= self.params.free_threshold)] = 0
        occupied = (p >= self.params.occupied_threshold) | (
            (self.last_state == 1) & (p > self.params.free_threshold))
        grid[known & occupied] = 1
        return grid

    def infer(self, step):
        projected = self.project(step)
        changed = int(np.count_nonzero(projected != self.grid))
        self.grid[:] = projected
        self.latest_step = step
        self.inference_log.append({'step': step, 'changed_cells': changed})
        return changed

    def update(self, observation, step):
        self._check_step(step)
        observation = np.asarray(observation)
        if observation.shape != self.grid.shape or not np.isin(observation, [-1, 0, 1]).all():
            raise ValueError('Invalid observation')
        visible = observation >= 0
        repeated = visible & (self.last_observed >= 0)
        predicted = self.probabilities(step)
        # Pre-update predictions only; unknown coverage retained explicitly.
        self.calibration.append({'step': step,
            'probability': predicted[visible].tolist(),
            'outcome': observation[visible].astype(int).tolist(),
            'previously_known': repeated[visible].tolist()})
        for state in (0, 1):
            mask = repeated & (self.last_state == state)
            self.exposure[state, mask] += step-self.last_observed[mask]
            self.transitions[state, mask] += observation[mask] != state
        self.last_state[visible] = observation[visible]
        self.last_observed[visible] = step
        self.latest_step = step
        self.grid[:] = self.project(step)
        self.observed_updates += 1


def calibration_summary(records):
    """Policy-selected pre-scan predictions, not full-world calibration."""
    p = np.array([v for r in records if r['step'] > 0 for v in r['probability']])
    y = np.array([v for r in records if r['step'] > 0 for v in r['outcome']])
    bins = []
    for i in range(10):
        mask = (p >= i/10) & ((p < (i+1)/10) if i < 9 else (p <= 1))
        bins.append({'lower': i/10, 'count': int(mask.sum()),
                     'mean_probability': float(p[mask].mean()) if mask.any() else None,
                     'occupied_fraction': float(y[mask].mean()) if mask.any() else None})
    return {'samples': len(p), 'brier': float(np.mean((p-y)**2)) if len(p) else None,
            'log_loss': float(-np.mean(y*np.log(np.clip(p, 1e-9, 1))+
                (1-y)*np.log(np.clip(1-p, 1e-9, 1)))) if len(p) else None,
            'reliability_bins': bins}
