import base64
import numpy as np
import pytest

from run_h2_full_spatial_memory_replay import _safe_state, pack_grid
from h2_high_frequency_dynamics import unpack_2bit_grid


def test_full_memory_pack_round_trips_y_major_ternary_grid():
    grid = np.arange(625, dtype=np.int8).reshape(25, 25) % 3 - 1
    packed = pack_grid(grid)
    assert np.array_equal(unpack_2bit_grid(packed), grid)


def test_full_memory_pack_rejects_invalid_shape_or_values():
    with pytest.raises(ValueError):
        pack_grid(np.zeros((24, 25), dtype=np.int8))
    invalid = np.zeros((25, 25), dtype=np.int8); invalid[0, 0] = 2
    with pytest.raises(ValueError):
        pack_grid(invalid)


def test_controller_snapshot_omits_forbidden_evaluator_state_keys():
    state = {'grid': np.zeros((25, 25), dtype=np.int8),
             'rng': {'seed': 42}, 'world': {'hidden_occupancy': [1]},
             'decisions': [{'step': 2, 'requested': False}]}
    saved = _safe_state(state)
    assert 'grid' in saved and 'decisions' in saved
    assert 'rng' not in saved and 'world' not in saved


def test_controller_snapshot_has_no_reference_to_input_arrays():
    grid = np.zeros((25, 25), dtype=np.int8)
    saved = _safe_state({'grid': grid})
    grid[0, 0] = 1
    assert unpack_2bit_grid(saved['grid']['data'])[0, 0] == 0
