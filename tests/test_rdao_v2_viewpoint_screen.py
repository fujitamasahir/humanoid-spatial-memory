"""Fast RDAO v2 paired evaluator contract tests, without MuJoCo."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/"src"), str(ROOT/"scripts")]

import evaluate_rdao_v2_viewpoint as screen
from spatial_memory.rdao_v2 import RDAOv2ViewpointController


def test_runner_restores_evaluator_controller_on_success(monkeypatch):
    original = screen.evaluator.RDAOController

    def run(payload, schedule, policy):
        assert screen.evaluator.RDAOController is RDAOv2ViewpointController
        assert (payload, schedule, policy) == ("fixture", 1, "rdao_v1")
        return {"success": True}, {"steps": []}

    monkeypatch.setattr(screen.evaluator, "_instrumented_case", run)
    row, trace = screen.evaluate_v2("fixture", 1)
    assert row["success"] and trace["steps"] == []
    assert screen.evaluator.RDAOController is original


def test_runner_restores_evaluator_controller_on_exception(monkeypatch):
    original = screen.evaluator.RDAOController

    def fail(*args):
        assert screen.evaluator.RDAOController is RDAOv2ViewpointController
        raise RuntimeError("sim aborted")

    monkeypatch.setattr(screen.evaluator, "_instrumented_case", fail)
    with pytest.raises(RuntimeError, match="sim aborted"):
        screen.evaluate_v2("fixture", 0)
    assert screen.evaluator.RDAOController is original


def case(world, original_success, v2_success, steps, obs, distance):
    return {
        "world_identity": "fit:"+world, "schedule": 0, "seed": 42,
        "original_success": original_success, "variant_success": v2_success,
        "variant_elapsed_steps": steps, "variant_observations": obs,
        "variant_travel_distance_m": distance,
        "variant_unwanted_contacts": 0,
    }


def old_footprint(v2case, *, success, steps, obs, distance):
    return {
        "world_identity": v2case["world_identity"],
        "schedule": str(v2case["schedule"]), "seed": str(v2case["seed"]),
        "variant_success": str(success),
        "variant_elapsed_steps": str(steps),
        "variant_observations": str(obs),
        "variant_travel_distance_m": str(distance),
        "variant_unwanted_contacts": "0",
    }


def test_subset_pilot_comparison_does_not_require_all_72_records():
    a = case("A", False, True, 28, 7, 15.)
    b = case("B", True, False, 80, 10, 38.)
    expected = {
        (a["world_identity"], 0, 42):
            old_footprint(a, success=False, steps=80, obs=8, distance=34.),
        (b["world_identity"], 0, 42):
            old_footprint(b, success=True, steps=40, obs=9, distance=21.),
    }
    summary, rows = screen.compare_footprint([a, b], expected)
    assert len(rows) == 2
    assert summary["v2_rescues_vs_footprint"] == 1
    assert summary["v2_harms_vs_footprint"] == 1
    assert summary["mean_v2_observations"] == 8.5
    assert summary["paired_common_success"]["episodes"] == 0


def test_missing_saved_footprint_row_rejected():
    a = case("A", True, True, 30, 7, 14.)
    with pytest.raises(ValueError, match="Missing"):
        screen.compare_footprint([a], {})


def test_horizon_censor_category_not_mislabeled_as_arrival():
    assert screen.disposition(False, False) == "both_horizon_censored"
    assert screen.disposition(False, True) == "rescued"
    assert screen.disposition(True, False) == "harmed"
