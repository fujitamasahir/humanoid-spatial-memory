"""Development-only procedural scenarios; generation is independent of agents."""
from dataclasses import asdict
import hashlib
import json
import numpy as np
from .simulation import Scenario


def generate_scenario(template, seed):
    """Realize a template once per paired seed, before either method runs."""
    data = dict(template)
    variation = data.pop('variation', None)
    if variation is None:
        return Scenario.from_dict(data)
    if data['split'] != 'development':
        raise ValueError('Procedural generation is restricted to development')
    rng = np.random.default_rng(np.random.SeedSequence([seed, 1101]))
    kind = variation['kind']
    if kind not in {'empty', 'temporary', 'persistent', 'mixed', 'alternative'}:
        raise ValueError('Unknown development scenario kind')
    # Crossing location, dwell time and direction vary independently of sensing.
    x = int(rng.integers(3, 8))
    dwell = int(rng.integers(2, 7))
    direction = int(rng.choice([-1, 1]))
    if kind in {'temporary', 'mixed'}:
        edge = 3 + 2 * direction
        path = [[x, 3]] * dwell + [[x, 3 + direction], [x, edge]]
        path += [[x, edge]] * int(rng.integers(1, 5))
        path += [[x, 3 + direction]]
        data['pedestrians'] = [path]
    if kind in {'persistent', 'mixed', 'alternative'}:
        cell = [int(rng.integers(4, 8)), 3]
        data['changes'] = [dict(step=int(rng.integers(2, 5)), action='add', cell=cell)]
    return Scenario.from_dict(data)


def scenario_record(scenario):
    return asdict(scenario)


def scenario_hash(scenario):
    raw = json.dumps(scenario_record(scenario), sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(raw.encode()).hexdigest()
