import base64
import numpy as np
import pytest

from finalize_h2_full_spatial_memory_replay import verify_memory
from run_h2_full_spatial_memory_replay import pack_grid


def test_finalizer_accepts_valid_complete_ternary_grid():
    value = pack_grid(np.tile(np.array([-1, 0, 1], dtype=np.int8), 25*25//3 + 1)[:625].reshape(25, 25))
    verify_memory(value)


def test_finalizer_rejects_short_or_invalid_memory_payload():
    with pytest.raises(ValueError):
        verify_memory(base64.b64encode(b'bad').decode())
    invalid = bytearray(157); invalid[0] = 3
    with pytest.raises(ValueError):
        verify_memory(base64.b64encode(invalid).decode())
