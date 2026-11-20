"""Regression for the failed initial formal JSON artifact boundary only."""
import json
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from run_dao_synthetic import json_native
from spatial_memory.discovery_observation import assess, request_rule


def test_actual_assessment_ledger_roundtrips_numpy_counts():
    grid=np.zeros((15,15),dtype=np.int8);last=np.zeros(grid.shape,dtype=np.int64)
    detail=assess(grid,last,5,(3,7),0.)
    rows=[{'detail':detail,**request_rule(detail,5,5,'dao_veto')}]
    restored=json.loads(json.dumps(json_native(rows)))
    assert restored==rows
    assert type(restored[0]['detail']['frontier']['known']) is int
    assert restored[0]['requested'] is True
