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
    from .scheduling import AdaptiveParameters, ObservationController
    from .navigation import plan

    world = World(scenario)
    sensor = Sensor(**config['sensor'])
    # Per-time streams keep sensor noise paired regardless of observation schedules.
    def observe():
        rng = np.random.default_rng(np.random.SeedSequence([seed, world.step]))
        return sensor.observe(world.occupancy(), position, rng)

    position = scenario.start
    initial = observe()
    # Allow-listed public model assumptions only, never scenario schedules/configs.
    agent = ObservationController(initial, method, interval=config['update_interval'],
        radius=config['sensor']['radius'], parameters=AdaptiveParameters(**config.get('adaptive', {})),
        max_observations=config.get('max_observations'))
    observations, blocked_attempts, dynamic_contacts, distance = 1, 0, 0, 0
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

    def capture(planned, decision=None, blocked=False, moved=False):
        people = np.zeros(initial.shape, bool)
        for x, y in world.people():
            people[y, x] = True
        departed = pedestrian_source & ~people
        errors = map_errors(agent.memory.grid, world.geometry(), changed, departed)
        for key, value in errors.items():
            totals[key] += value
        frames.append(dict(step=world.step, position=position, geometry=world.geometry().copy(),
            people=people.copy(), memory=agent.memory.grid.copy(), planned=planned,
            executed=list(path_taken), errors=errors, blocked=bool(blocked), moved=bool(moved),
            observation_count=observations, **(decision or dict(observation_requested=True,
                observation_granted=True, observation_score=None, observation_position=position))))

    capture(plan(agent.memory.grid, position, scenario.goal, config['unknown']))
    for _ in range(config['max_steps']):
        if position == scenario.goal:
            break
        prior_people = world.people()
        before = world.geometry()
        world.advance()
        changed[:] |= before != world.geometry()
        decision = agent.decide(world.step, position)
        if decision["observation_granted"]:
            observation = observe()
            agent.refresh(observation, world.step)
            attribute_observation(observation)
            observations += 1
        planned = plan(agent.memory.grid, position, scenario.goal, config['unknown'])
        # Count new entries, not continuing overlap; at most one dynamic contact per step.
        # Blocked attempts are separate and never correct either map.
        x, y = position
        dynamic_contacts += int((world.geometry()[y, x] and not before[y, x])
                                or (position in world.people() and position not in prior_people))
        contact, moved = 0, False
        if len(planned) > 1:
            nxt, contact = world.move(position, planned[1])
            blocked_attempts += contact
            moved = nxt != position
            distance += int(moved)
            position = nxt
            path_taken.append(position)
        capture(planned, decision, contact, moved)
    failure_reason = None
    if position != scenario.goal:
        if not frames[-1]['planned']:
            failure_reason = 'deadline_no_remembered_route'
        elif len(frames) >= 4 and all(f['blocked'] for f in frames[-3:]):
            failure_reason = 'deadline_repeated_blocked_attempts'
        else:
            failure_reason = 'deadline_before_goal'
    metrics = dict(scenario=scenario.name, split=scenario.split, seed=seed, method=method,
        success=position == scenario.goal,
        blocked_movement_attempts=blocked_attempts, dynamic_contacts=dynamic_contacts,
        collision_count=blocked_attempts + dynamic_contacts, travel_distance=distance,
        max_steps=config["max_steps"], final_position=position,
        elapsed_steps=world.step, observation_count=observations,
        observation_cost=observations*config['observation_cost'],
        max_observations=agent.cap, observation_requests=agent.requests,
        observation_requests_denied=agent.denied, failure_reason=failure_reason, **totals)
    metrics.update({'final_'+key: value for key, value in frames[-1]['errors'].items()})
    return metrics, frames
