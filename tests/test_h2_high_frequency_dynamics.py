from types import SimpleNamespace

import numpy as np

from scripts.h2_high_frequency_dynamics import (
    ENGINE_NAMESPACE, HighFrequencyEngine, _critical_cut_cells, pack_2bit_grid,
    rng_for, run_dynamic_case, source_maps, unpack_2bit_grid,
)


class FakeScene:
    cell_size = 0.75
    footprint_half_extents_local = (0.24, 0.20)

    def grid_to_world(self, cell):
        return ((cell[0] - 3) * self.cell_size,
                (cell[1] - 3) * self.cell_size)


def _scenario(width=7, height=7, start=(0, 0), goal=(6, 6), walls=(), pedestrians=()):
    return SimpleNamespace(width=width, height=height, start=start, goal=goal,
                           walls=tuple(walls), pedestrians=tuple(pedestrians))


class FakeWorld:
    def __init__(self, scenario, objects=()):
        self.scenario = scenario
        self.width, self.height = scenario.width, scenario.height
        self.objects = set(objects)
        self.step = 0

    def people(self):
        return {path[self.step % len(path)] for path in self.scenario.pedestrians}


def test_framed_philox_stream_is_deterministic_and_model_independent():
    a = rng_for('map-a', 0, 42, 3, 'operation-type').integers(0, 10, 20)
    b = rng_for('map-a', 0, 42, 3, 'operation-type').integers(0, 10, 20)
    c = rng_for('map-a', 0, 42, 4, 'operation-type').integers(0, 10, 20)
    assert np.array_equal(a, b)
    assert not np.array_equal(a, c)
    assert ENGINE_NAMESPACE == 'h2-high-frequency-dynamics-v1'


def test_cut_vertex_filter_preserves_start_goal_connectivity():
    critical, connected = _critical_cut_cells(set(), set(), (0, 0), (4, 0), 5, 1)
    assert connected
    assert critical == {(1, 0), (2, 0), (3, 0)}
    critical, connected = _critical_cut_cells(set(), set(), (0, 0), (4, 2), 5, 3)
    assert connected
    assert (2, 1) not in critical  # an alternate 4-connected route remains


def test_initial_and_dynamic_objects_respect_limits_and_ids():
    scenario = _scenario()
    engine = HighFrequencyEngine(scenario, 'map-x', 0, 42, ())
    engine.scene = FakeScene()
    world = FakeWorld(scenario)
    engine.robot_cell = scenario.start
    for step in range(1, 45):
        world.step = step
        event = engine.transition(world)
        assert 0 <= len(world.objects) <= 4
        assert len(engine.object_ids) == len(world.objects)
        assert len(set(engine.object_ids.values())) == len(engine.object_ids)
        assert event['connectivity_preserved']
        assert event['exclusion_zone_validated']
        if event['event_type'] == 'relocation':
            assert event['from_cell'] != event['to_cell']
            assert event['object_id'] in {x['object_id'] for x in event['objects_after']}
        if event['event_type'] == 'addition':
            assert event['object_id'].startswith('obj_')
            assert event['object_count_after'] == event['object_count_before'] + 1
        if event['event_type'] == 'removal':
            assert event['object_count_after'] == event['object_count_before'] - 1
    assert all(event['event_type'] in {'addition', 'removal', 'relocation', 'no_op'}
               for event in engine.events)
    assert {event['event_type'] for event in engine.events} >= {
        'addition', 'removal', 'relocation'}


def test_no_op_is_explicit_when_no_transition_is_feasible():
    scenario = _scenario(width=3, height=1, start=(0, 0), goal=(2, 0))
    engine = HighFrequencyEngine(scenario, 'narrow', 0, 42, ())
    engine.scene = FakeScene()
    world = FakeWorld(scenario)
    world.step = 1
    event = engine.transition(world)
    assert event['event_type'] == 'no_op'
    assert event['no_op_reason']
    assert engine.no_ops == 1


def test_goal_termination_stops_navigation_environment_transitions():
    scenario = _scenario(start=(0, 0), goal=(6, 6))
    engine = HighFrequencyEngine(scenario, 'terminal', 0, 42, ())
    assert engine.episode_active()
    engine.robot_cell = scenario.goal
    assert not engine.episode_active()
    assert engine.events == []


def test_full_object_count_disables_additions():
    scenario = _scenario()
    initial = [(2, 2), (2, 3), (3, 2), (3, 3)]
    engine = HighFrequencyEngine(scenario, 'full', 0, 42, initial)
    engine.scene = FakeScene()
    world = FakeWorld(scenario, initial)
    world.step = 1
    event = engine.transition(world)
    assert event['event_type'] in {'removal', 'relocation'}
    assert 'addition' not in event['feasible_event_types']
    assert len(world.objects) <= 4


def test_memory_grid_packing_preserves_ternary_values():
    grid = np.asarray([[-1, 0, 1], [1, -1, 0]], dtype=np.int8)
    packed = pack_2bit_grid(grid)
    raw = np.frombuffer(__import__('base64').b64decode(packed), dtype=np.uint8)
    decoded = []
    for byte in raw:
        decoded.extend([int((byte >> (2*i)) & 3)-1 for i in range(4)])
    assert decoded[:grid.size] == grid.reshape(-1).tolist()


def test_saved_map_dynamic_episode_captures_complete_fail_closed_replay():
    payload, _ = source_maps()[0]
    row, replay, diagnostics = run_dynamic_case(payload, 0, 'periodic4')
    assert row['dynamic_steps'] == row['elapsed_steps']
    assert row['environment_change_rate'] == 1.0
    assert row['observation_count'] <= 20
    assert row['g1_shield_query_count_valid']
    assert row['g1_unselected_action_shield_queries'] == 0
    assert len(replay['steps']) == row['elapsed_steps'] + 1
    assert len(diagnostics['dynamic_transition_ns']) == row['elapsed_steps']
    assert all(len(step['objects_after']) <= 4 for step in replay['steps'])
    assert all(unpack_2bit_grid(step['spatial_memory_ternary_packed_2bit_base64']).shape == (25,25)
               for step in replay['steps'])
    assert all(step['event']['connectivity_preserved'] for step in replay['steps'][1:])

