"""Evaluator-only access to persistent truth and departed pedestrian traces."""
import numpy as np


def map_errors(memory, geometry, changed, departed):
    known = memory >= 0
    mismatch = memory != geometry.astype(np.int8)
    return {
        'stale_map_errors': int(np.count_nonzero(known & mismatch)),
        'false_persistent_occupancy_updates': int(np.count_nonzero(
            (memory == 1) & ~geometry & departed)),
        'missed_persistent_changes': int(np.count_nonzero(
            changed & (~known | mismatch))),
    }


def run_episode(scenario, config, method, seed):
    from .simulation import World
    from .observation import Sensor
    from .memory import Baseline
    from .navigation import plan

    world = World(scenario)
    sensor = Sensor(**config['sensor'])
    # Per-time streams keep sensor noise paired regardless of observation schedules.
    def observe():
        rng = np.random.default_rng(np.random.SeedSequence([seed, world.step]))
        return sensor.observe(world.occupancy(), position, rng)

    position = scenario.start
    initial = observe()
    agent = Baseline(initial.shape, initial, method, config['update_interval'])
    observations, collisions, distance = 1, 0, 0
    path_taken, frames = [position], []
    totals = dict.fromkeys(map_errors(agent.memory.grid, world.geometry(),
                           np.zeros(initial.shape, bool), np.zeros(initial.shape, bool)), 0)
    pedestrian_source = np.zeros(initial.shape, bool)
    changed = np.zeros(initial.shape, bool)

    def attribute_observation(observation):
        # Evaluator bookkeeping only: which current occupied map entries were
        # actually written from transient occupancy? Never passed to the agent.
        people = np.zeros(initial.shape, bool)
        for x, y in world.people():
            people[y, x] = True
        visible = observation >= 0
        source = (observation == 1) & people & ~world.geometry()
        pedestrian_source[visible] = source[visible]

    attribute_observation(initial)

    def capture(planned):
        people = np.zeros(initial.shape, bool)
        for x, y in world.people():
            people[y, x] = True
        departed = pedestrian_source & ~people
        errors = map_errors(agent.memory.grid, world.geometry(), changed, departed)
        for key, value in errors.items():
            totals[key] += value
        frames.append(dict(step=world.step, position=position, geometry=world.geometry().copy(),
            people=people.copy(), memory=agent.memory.grid.copy(), planned=planned,
            executed=list(path_taken), errors=errors))

    capture(plan(agent.memory.grid, position, scenario.goal, config['unknown']))
    for _ in range(config['max_steps']):
        if position == scenario.goal:
            break
        before = world.geometry()
        world.advance()
        changed[:] |= before != world.geometry()
        if agent.needs_observation(world.step):
            observation = observe()
            agent.refresh(observation)
            attribute_observation(observation)
            observations += 1
        planned = plan(agent.memory.grid, position, scenario.goal, config['unknown'])
        # Contacts from a human/object entering the stationary robot are counted once
        # per step, and movement contacts separately. No privileged map correction.
        collisions += int(world.occupancy()[position[1], position[0]])
        if len(planned) > 1:
            nxt, contact = world.move(position, planned[1])
            collisions += contact
            distance += int(nxt != position)
            position = nxt
            path_taken.append(position)
        capture(planned)
    metrics = dict(scenario=scenario.name, split=scenario.split, seed=seed, method=method,
        success=position == scenario.goal, collision_count=collisions, travel_distance=distance,
        elapsed_steps=world.step, observation_count=observations,
        observation_cost=observations*config['observation_cost'], **totals)
    metrics.update({'final_'+key: value for key, value in frames[-1]['errors'].items()})
    return metrics, frames
