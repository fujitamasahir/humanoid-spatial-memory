"""Fast contract tests for retrospective second-scan causes.

No MuJoCo backend or held-out worlds are invoked.
"""
import copy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

import evaluate_rdao_footprint_second_sensing_interventions as audit


def frame(step, *, observed=False, flag=False, pos=(4, 6), yaw=0.,
          raw_value=1, changed=1, pre_value=-1):
    eff = {
        "received_observation_values": [{"cell": [5, 6], "value": raw_value}],
        "visible_cell_count": 1,
        "memory_changed_cell_count": changed,
        "memory_before": [[pre_value, -1], [0, 0]],
        "memory_after": [[raw_value, -1], [0, 0]],
    } if observed else None
    return {
        "step": step, "observation_granted": observed,
        "position": list(pos), "heading_yaw": yaw,
        "action": ["turn", 1],
        "rdao": {
            "position": list(pos), "heading_yaw": yaw,
            "intervention_second_forced": flag,
            "observation_effect": eff,
        },
    }


def fixtures():
    base = {"steps": [
        frame(0), frame(1), frame(2), frame(3),
    ]}
    footprint = copy.deepcopy(base)
    forced = copy.deepcopy(base)
    footprint["steps"][2] = frame(2, observed=True, changed=2)
    forced["steps"][2] = frame(2, observed=True, flag=True, changed=1,
                               pre_value=0)
    return base, footprint, forced


def test_second_scan_compares_raw_sensor_not_memory_prior():
    base, fp, forced = fixtures()
    details = audit.check_second_sensor(fp, base, forced, 2)
    assert details["raw_visible_cells"] == 1
    assert details["changed_cells_footprint"] == 2
    assert details["changed_cells_second"] == 1
    assert not details["pre_memory_exact_match"]


def test_rejects_different_actual_raw_sensor_value():
    base, fp, forced = fixtures()
    forced["steps"][2]["rdao"]["observation_effect"][
        "received_observation_values"][0]["value"] = 0
    with pytest.raises(RuntimeError, match="raw 61-ray scan differs"):
        audit.check_second_sensor(fp, base, forced, 2)


def test_rejects_different_pre_action_sensor_pose():
    base, fp, forced = fixtures()
    forced["steps"][2]["rdao"]["heading_yaw"] = 1.0
    with pytest.raises(RuntimeError, match="same-pose sensor"):
        audit.check_second_sensor(fp, base, forced, 2)


def test_rejects_already_granted_second_scan():
    base, fp, forced = fixtures()
    base["steps"][2] = frame(2, observed=True)
    with pytest.raises(RuntimeError, match="not a new Footprint scan"):
        audit.check_second_sensor(fp, base, forced, 2)


def test_rejects_missing_forced_second_scan_flag():
    base, fp, forced = fixtures()
    forced["steps"][2]["rdao"]["intervention_second_forced"] = False
    with pytest.raises(RuntimeError, match="flag not preserved"):
        audit.check_second_sensor(fp, base, forced, 2)


def test_second_forced_class_inherits_first_extra_swap_controller():
    from evaluate_rdao_one_shot_interventions import InterventionRDAO
    assert issubclass(audit.SecondForcedScanRDAO, InterventionRDAO)
    assert all(mode in ("extra", "swap") for _, _, _, mode, _ in audit.TARGETS)
    assert all(first < second for _, _, first, _, second in audit.TARGETS)
    assert len({(w, s, mode) for w, s, _, mode, _ in audit.TARGETS}) == 6
