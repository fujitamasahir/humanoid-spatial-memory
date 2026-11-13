"""Unit tests for the RDAO closure diagnostics; no MuJoCo."""
import sys
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"src"),str(ROOT/"scripts")]

import diagnose_rdao_vs_periodic_age_closure as d
import evaluate_rdao_phase2 as evaluator
from spatial_memory.rdao_v2 import RDAOv2ViewpointController


def frame(step, *, position=(3, 3), yaw=0., action=None, observed=False,
          remaining=10):
    return {
        "step": step, "position": list(position), "heading_yaw": yaw,
        "action": action or ["move", [4,3]], "moved": True, "blocked": False,
        "observation_granted": observed,
        "rdao": {"remaining_observation_budget":remaining,
                 "reason":"score_below","score": .15,"threshold": .25,
                 "candidate_regions":[]}
    }


def test_prefix_scan_compares_prior_pose_not_updated_pose():
    v = {"steps":[
        frame(0, position=(2,3)),frame(1, position=(3,3)),
        frame(2, position=(4,3)),frame(3, position=(5,3))]}
    b = {"steps":[
        frame(0, position=(2,3)),frame(1, position=(3,3)),
        frame(2, position=(2,3), observed=True),
        frame(3, position=(3,3),observed=True)]}
    targets = d.initial_shared_pose_missed_scans(v,b)
    # step2 both start at (3,3), although positions recorded after
    # the action are different. Step3 is beyond first action divergence.
    assert [x["step"] for x in targets] == [2]


def test_exhausted_budget_excludes_candidate():
    v = {"steps":[frame(0, position=(2,3)),
                  frame(1, position=(3,3), remaining=0)]}
    b = {"steps":[frame(0, position=(2,3)),
                  frame(1, position=(3,3), observed=True)]}
    assert d.initial_shared_pose_missed_scans(v,b) == []


def test_discrepancy_summary_is_observational_not_causal():
    key = ("fit:X",0,42)
    v={"steps":[frame(0,position=(2,3)),
                frame(1,position=(3,3),observed=False)]}
    b={"steps":[frame(0,position=(2,3)),
                frame(1,position=(4,3),observed=True)]}
    result=d.row_summary(
        key,{"variant_success":"False","variant_elapsed_steps":"80",
             "variant_observations":"8"},
        "periodic",{"success":"True","elapsed_steps":"30",
                    "observation_count":"7"},v,b)
    assert result["first_shared_pose_baseline_only_observation"] == 1
    assert result["comparator_success"]
    assert not result["v2_success"]
    assert result["hypothesis_status"].startswith("candidate_")


def test_simulator_hook_restored_on_error(monkeypatch):
    saved=evaluator.RDAOController
    def failure(*args):
        assert issubclass(evaluator.RDAOController,RDAOv2ViewpointController)
        raise RuntimeError("synthetic failure")
    monkeypatch.setattr(evaluator,"_instrumented_case",failure)
    with pytest.raises(RuntimeError,match="synthetic failure"):
        d.simulate_v2({},0,force_step=2,intervention="extra")
    assert evaluator.RDAOController is saved


def test_force_genuinely_denied_step_and_records_real_preobservation(monkeypatch):
    # Deliberately isolate force wiring; inherited decide is pure synthetic.
    from spatial_memory.rdao_v2 import RDAOv2ViewpointController
    import numpy as np
    def mock_decide(self,step,pos):
        return {"observation_requested":False,
                "observation_granted":False,
                "rdao":{"nominal_route":[["move",[2,1]]],
                        "reason":"threshold_below",
                        "remaining_observation_budget":19}}
    monkeypatch.setattr(RDAOv2ViewpointController,"decide",mock_decide)
    c=d.DiagnosticV2ForcedScan(
        np.zeros((6,6),dtype=np.int8),goal=(4,4),max_observations=20)
    c.force_step=5
    c.intervention="extra"
    c.set_context(5,(1,1),0.)
    got=c.decide(5,(1,1))
    assert got["observation_granted"]
    assert got["rdao"]["intervention_forced"]
    assert got["rdao"]["_pre_observation"]["position"]==(1,1)
    assert c.forced
