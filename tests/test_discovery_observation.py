import math
import numpy as np
import pytest
from spatial_memory.discovery_observation import (DAOParameters, DiscoveryController,
    assess, predicted_footprints, request_rule, MODES)
from spatial_memory.discovery_reference import footprint_reference, scalar_counts
from spatial_memory.evi import visible_cells


def state(value=0, shape=(15, 15)):
    grid = np.full(shape, value, dtype=np.int8)
    return grid, np.where(grid >= 0, 0, -1).astype(np.int64)


def context(c):
    c.set_navigation_context(goal=(12, 7), yaw=0.)


def test_analytic_frontier_stops_unknown_not_free():
    g, _ = state(); g[7, 9:] = -1
    f = predicted_footprints(g, (7, 7), 0, horizontal_fov_deg=1e-8)
    assert f['frontier'] == {(8, 7), (9, 7)}
    assert f['optimistic'] == {(x, 7) for x in range(8, 15)}
    g[7, 8] = 1
    f = predicted_footprints(g, (7, 7), 0, horizontal_fov_deg=1e-8)
    assert f['frontier'] == f['optimistic'] == {(8, 7)}


def test_unknown_is_not_verification_or_known_change():
    g, t = state(-1); d = assess(g, t, 7, (7, 7), 0.)
    assert d['age_scores']['5'] == 0 and d['frontier']['stale'] == 0
    assert d['frontier']['new'] > 0


def test_randomized_independent_scalar_and_legacy_geometry():
    rng = np.random.default_rng(2026111404)
    for _ in range(160):
        g = rng.choice([-1, 0, 1], (13, 17), p=[.35, .5, .15]).astype(np.int8)
        pos = (int(rng.integers(17)), int(rng.integers(13))); g[pos[1], pos[0]] = 0
        yaw = float(rng.uniform(-math.pi, math.pi)); t = np.where(g >= 0, rng.integers(0, 9, g.shape), -1)
        actual = predicted_footprints(g, pos, yaw); ref = footprint_reference(g.tolist(), pos, yaw)
        assert actual['frontier'] == ref['frontier']
        assert actual['optimistic'] == ref['optimistic'] == visible_cells(g, pos, yaw, range_m=6., cell_size=.75, horizontal_fov_deg=120.)-{pos}
        d = assess(g, t, 10, pos, yaw)
        for name in ('frontier', 'optimistic'):
            assert d[name] == scalar_counts(g.tolist(), t.tolist(), 10, ref[name])
        assert actual['frontier'] <= actual['optimistic'] and actual['samples'] <= 4941


def fake(new=0, stale=0, known=10, route=0, age5=False, oldest=5):
    return {'age_scores': {'4': float(age5), '5': float(age5), '6': 0.},
        'oldest_local_age': oldest, 'frontier': {'new': new, 'stale': stale,
        'known': known, 'stale_fraction': stale/known if known else 0., 'route_new': route}}


@pytest.mark.parametrize('mode', MODES[:4])
def test_bounded_stale_fallback_even_when_age_fraction_low(mode):
    assert request_rule(fake(oldest=10), 10, 1, mode)['requested']
    assert not request_rule(fake(oldest=9), 9, 1, mode)['requested']


def test_veto_and_trigger_route_ablation():
    low = fake(age5=True)
    assert not request_rule(low, 5, 5, 'dao_veto')['requested']
    assert request_rule(fake(stale=3, age5=True), 5, 5, 'dao_veto')['requested']
    high = fake(new=5)
    assert request_rule(high, 3, 3, 'dao_trigger')['requested']
    assert not request_rule(high, 3, 2, 'dao_trigger')['requested']
    assert not request_rule(high, 3, 3, 'dao_route')['requested']
    high['frontier']['route_new'] = 1
    assert request_rule(high, 3, 3, 'dao_route')['requested']
    assert request_rule(low, 5, 5, 'dao_trigger')['requested']


@pytest.mark.parametrize('mode', MODES)
def test_authorization_cap_and_empty_reading(mode):
    g, _ = state(); c = DiscoveryController(g, mode=mode, max_observations=2)
    with pytest.raises(RuntimeError): c.refresh(g, 1)
    for step in range(1, 21):
        context(c); decision = c.decide(step, (7, 7))
        if decision['observation_granted']:
            before = c.memory.grid.copy(); old = c.last_observed.copy()
            with pytest.raises(ValueError): c.refresh(np.full(g.shape, 7), step)
            assert np.array_equal(c.memory.grid, before)
            with pytest.raises(RuntimeError): c.decide(step+1, (7, 7))
            c.refresh(np.full(g.shape, -1), step)
            assert np.array_equal(c.memory.grid, before) and np.array_equal(c.last_observed, old)
    assert c.used == 2 and c.denied > 0
    with pytest.raises(RuntimeError): c.refresh(g, 21)


def test_last_write_persistent_add_remove_no_inference():
    g, _ = state(); c = DiscoveryController(g, mode='age5')
    for step in (5, 10):
        context(c); assert c.decide(step, (7, 7))['observation_granted']
        reading = np.full(g.shape, -1); reading[7, 8] = int(step == 5)
        c.refresh(reading, step)
        assert c.memory.grid[7, 8] == int(step == 5)
        assert c.last_observed[7, 8] == step
    assert c.memory.grid[0, 0] == 0 and c.last_observed[0, 0] == 0


def test_route_validation_and_no_route_degradation():
    g, t = state(); g[:, 10:] = -1; t[g == -1] = -1
    route = [(x, 7) for x in range(7, 13)]
    d = assess(g, t, 3, (7, 7), 0., route=route)
    assert d['frontier']['route_new'] > 0
    assert not assess(g, t, 3, (7, 7), 0.)['route_available']
    with pytest.raises(ValueError): assess(g, t, 3, (7, 7), 0., route=[(7, 7), (9, 7)])
    with pytest.raises(ValueError): assess(g, t, 3, (7, 7), 0., route=[(8, 7)])


@pytest.mark.parametrize('case', ['time', 'shape', 'ternary', 'pose', 'range', 'rays', 'nan', 'oversize'])
def test_invalid_public_inputs(case):
    g, t = state(); pos = (7, 7); yaw = 0.; sensor = {}
    if case == 'time': t[0, 0] = 99
    if case == 'shape': t = t[:1]
    if case == 'ternary': g[0, 0] = 2
    if case == 'pose': pos = (99, 7)
    if case == 'range': sensor = {'range_m': 7.}
    if case == 'rays': sensor = {'ray_count': 62}
    if case == 'nan': yaw = float('nan')
    if case == 'oversize': g, t = state(shape=(65, 65))
    with pytest.raises(ValueError): assess(g, t, 5, pos, yaw, sensor=sensor)


def test_deterministic_controller_fresh_context_and_clock():
    logs = []
    for _ in range(2):
        g, _ = state(-1); g[7, 7] = 0; c = DiscoveryController(g, mode='dao_combined')
        for step in range(1, 16):
            context(c); d = c.decide(step, (7, 7))
            if d['observation_granted']: c.refresh(np.full(g.shape, -1), step)
        with pytest.raises(RuntimeError): c.decide(16, (7, 7))
        context(c)
        with pytest.raises(RuntimeError): c.decide(15, (7, 7))
        logs.append(c.decisions)
    assert logs[0] == logs[1]


def test_no_hidden_planner_sensor_dependency():
    import ast, inspect
    from spatial_memory import discovery_observation as module
    tree = ast.parse(inspect.getsource(module))
    names = [n.module or '' for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    assert set(names) <= {'__future__', 'dataclasses', 'memory'}
    assert not any(isinstance(n, ast.Import) and any(a.name not in ('math', 'numpy') for a in n.names) for n in ast.walk(tree))
