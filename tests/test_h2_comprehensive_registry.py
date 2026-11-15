import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def test_registry_has_all_requested_and_authorization_is_explicit():
    rows=json.loads((ROOT/'results/phase2_mujoco/h2_comprehensive_benchmark_v1/protocol/model_registry.json').read_text())
    assert len(rows)==57
    assert sum(r['previously_evaluated'] for r in rows)==13
    assert sum(r['authorization_status']=='eligible' for r in rows)==41
    blocked={r['model_id']:r['authorization_status'] for r in rows if r['authorization_status'].startswith('blocked')}
    assert set(blocked)=={'c_route3','c_routek','c_topology3c'}

