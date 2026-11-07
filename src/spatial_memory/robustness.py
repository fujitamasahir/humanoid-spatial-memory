"""Development generation and truth validation; never imported by agent policies."""
from copy import deepcopy
import numpy as np
from .simulation import Scenario, World
from .navigation import plan

FAMILIES = ('irrelevant', 'outdated', 'critical', 'detour', 'reopen', 'occluded', 'budget')


def generate_robustness(family, seed, timing=0, dwell_shift=0):
    if family not in FAMILIES:
        raise ValueError('Unknown development family')
    rng = np.random.default_rng(np.random.SeedSequence([seed, 1300]))
    w = int(rng.integers(13, 18))
    h = 9
    y = int(rng.choice([3, 5]))
    start, goal = [1, y], [w-2, y]
    gate = int(rng.integers(4, w-4))
    walls = {(x, 0) for x in range(w)} | {(x, h-1) for x in range(w)}
    walls |= {(0, z) for z in range(h)} | {(w-1, z) for z in range(h)}
    # Parallel routes joined at ends; interior opening creates a side room/dead end.
    if family in {'critical', 'reopen', 'occluded', 'budget'}:
        walls |= {(x, y-1) for x in range(2, w-2) if x != gate}
        walls |= {(x, y+1) for x in range(2, w-2) if x != gate}
    if family == 'outdated':
        walls |= {(gate, z) for z in range(1, h-1) if z in {y-2, y+2}}
    if family == 'detour':
        # Two passages through a room divider: direct gate and a longer bypass.
        walls |= {(gate, z) for z in range(1, h-1) if z not in {y, y+2}}
    obstacles, changes, pedestrians = [], [], []
    event = max(1, int(rng.integers(2, 7)) + timing)
    if family in {'outdated', 'detour', 'budget'}:
        changes.append(dict(step=event, action='add', cell=[gate, y]))
    if family == 'reopen':
        obstacles = [[gate, y]]
        changes.append(dict(step=max(2, event+5), action='remove', cell=[gate, y]))
    if family == 'occluded':
        # Occupied foreground occludes an important downstream route cell.
        obstacles = [[gate-1, y]]
        changes = [dict(step=event, action='add', cell=[gate+1, y]),
                   dict(step=event+4, action='remove', cell=[gate-1, y])]
    if family == 'irrelevant':
        # Changes in side rooms, outside the direct route; unknown remains unscored.
        changes = [dict(step=event, action='add', cell=[gate, 1]),
                   dict(step=event+5, action='remove', cell=[gate, 1])]
    if family in {'critical', 'budget', 'irrelevant'}:
        count = int(rng.integers(1, 4))
        for i in range(count):
            x = min(w-3, gate+i)
            # Adjacent wait/cross/return cycle, including wraparound validity.
            # Side rooms for irrelevant events, critical route otherwise.
            py = 1 if family == 'irrelevant' else y
            dwell = max(1, int(rng.integers(2, 7))+dwell_shift)
            delay = max(1, int(rng.integers(1, 6))+timing)
            a, b = [x, py], [x, py+1]
            if tuple(b) in walls:
                walls.remove(tuple(b))
            if tuple(a) in walls:
                walls.remove(tuple(a))
            pedestrians.append([b]*delay+[a]*dwell+[b])
    data = dict(name=family, split='development', width=w, height=h, start=start,
                goal=goal, walls=sorted(walls), obstacles=obstacles,
                pedestrians=pedestrians, changes=changes)
    return Scenario.from_dict(data)


def truth_audit(scenario, horizon):
    """Persistent geometry reachability at every change epoch, not a safety oracle.

    Temporary pedestrians are deliberately excluded. A closed route before a
    removal is allowed; at least one epoch and the final epoch must be reachable.
    """
    if scenario.split != 'development':
        raise ValueError('Held-out evaluation is reserved')
    world = World(scenario)
    records = []
    for t in range(horizon+1):
        if t == 0 or t == horizon or any(e['step'] == t for e in scenario.changes):
            route = plan(world.geometry().astype(np.int8), scenario.start, scenario.goal)
            records.append(dict(step=t, reachable=bool(route), shortest_length=len(route)-1 if route else None))
        if t < horizon:
            world.advance()
    if not records[-1]['reachable'] or not any(r['reachable'] for r in records):
        raise ValueError('Invalid terminal topology')
    return records


def episode_config(config, setting):
    result = deepcopy(config)
    for key in ('max_observations', 'update_interval'):
        if key in setting:
            result[key] = setting[key]
    result['sensor'].update(setting.get('sensor', {}))
    result['adaptive'].update(setting.get('adaptive', {}))
    return result
