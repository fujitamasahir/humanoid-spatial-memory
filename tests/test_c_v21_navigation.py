"""Scoped integration and fail-closed gates, no formal fixtures or FIT reads."""
from pathlib import Path
import sys,json
import numpy as np
import pytest
sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
import c_v21_navigation as nav
import evaluate_c_v21_fit72 as screen
from spatial_memory.multistep_evi import ARMS


@pytest.mark.parametrize('arm',list(ARMS))
def test_controller_hook_changes_only_evi_function(monkeypatch,arm):
    original=nav.runner.PersistenceEVIController
    def fake(*a,**kw):
        initial=np.zeros((4,6),dtype=np.int8)
        agent=nav.runner.PersistenceEVIController(initial,'age',persistence=False,
            max_observations=20,sensor=dict(range_m=6.,cell_size=.75,horizontal_fov_deg=120.,ray_count=61))
        assert agent.belief is None and agent.evi_function is ARMS[arm]
        assert agent.cap==20 and agent.used==1
        return {},{},{}
    monkeypatch.setattr(nav.fit,'run_measured',fake)
    row,trace,diag=nav.run_case({},0,arm,{})
    assert diag['multistep_arm']==arm
    assert nav.runner.PersistenceEVIController is original


def test_hook_restored_after_sensor_error(monkeypatch):
    original=nav.runner.PersistenceEVIController
    def broken(*a,**kw):raise RuntimeError('synthetic provider error')
    monkeypatch.setattr(nav.fit,'run_measured',broken)
    with pytest.raises(RuntimeError):nav.run_case({},0,'ms_k',{})
    assert nav.runner.PersistenceEVIController is original


@pytest.mark.parametrize('status',['INVALID_STOP_BEFORE_FIT','VALID_REJECTED_STOP_BEFORE_FIT'])
def test_negative_review_stops_before_fit_access(tmp_path,monkeypatch,status):
    (tmp_path/'synthetic').mkdir()
    (tmp_path/'synthetic/results.json').write_text(json.dumps({'numeric_gate':{'status':'PASS'}}))
    (tmp_path/'gate_review.json').write_text(json.dumps({'status':status,'FIT_authorized':False}))
    (tmp_path/'protocol_binding.json').write_text('{}')
    monkeypatch.setattr(screen,'OUT',tmp_path)
    def forbidden():raise AssertionError('FIT accessed before gate')
    monkeypatch.setattr(screen.fit,'verify_original_data_integrity',forbidden)
    with pytest.raises(RuntimeError,match='gate blocks'):screen.run(True)
