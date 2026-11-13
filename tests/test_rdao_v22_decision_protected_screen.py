"""Synthetic RDAO v2.2 screen contracts; no MuJoCo or fitted world data."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/"src"),str(ROOT/"scripts")]

import evaluate_rdao_v22_decision_protected as screen
from spatial_memory.rdao_v22_decision_protected import RDAOv22DecisionProtectedController


def test_candidate_restores_evaluator_controller_after_success(monkeypatch):
    original = screen.evaluator.RDAOController
    def fake(world, schedule, method):
        assert screen.evaluator.RDAOController is RDAOv22DecisionProtectedController
        assert (world, schedule, method) == ("fixture", 1, "rdao_v1")
        return {"success": True}, {"steps": []}
    monkeypatch.setattr(screen.evaluator, "_instrumented_case", fake)
    assert screen.evaluate_v22("fixture", 1)[0]["success"]
    assert screen.evaluator.RDAOController is original


def test_candidate_restores_evaluator_controller_after_exception(monkeypatch):
    original = screen.evaluator.RDAOController
    def failure(*args):
        assert screen.evaluator.RDAOController is RDAOv22DecisionProtectedController
        raise RuntimeError("fake backend crash")
    monkeypatch.setattr(screen.evaluator, "_instrumented_case", failure)
    with pytest.raises(RuntimeError, match="fake backend crash"):
        screen.evaluate_v22("fixture", 0)
    assert screen.evaluator.RDAOController is original


def saved(w, s, success, obs, steps, distance):
    return {
        "world_identity": "fit:"+w, "schedule": s, "seed": 42,
        "variant_success": success, "variant_observations": obs,
        "variant_elapsed_steps": steps, "variant_travel_distance_m": distance,
        "variant_unwanted_contacts": 0,
    }


def test_saved_compare_supports_pilot_subset_and_censored_failures():
    a = saved("A", 0, True, 8, 25, 10.)
    b = saved("B", 1, False, 11, 80, 44.)
    frozen = {
        ("fit:A", 0, 42): saved("A", 0, "False", "11", "80", "40"),
        ("fit:B", 1, 42): saved("B", 1, "False", "9", "80", "42"),
        ("fit:C", 1, 42): saved("C", 1, "True", "3", "15", "7"),
    }
    summary, rows = screen.compare_saved([a,b], frozen, "v2")
    assert summary["episodes"] == 2
    assert summary["rescues"] == 1
    assert summary["harms"] == 0
    assert summary["total_delta_observations"] == -1
    assert summary["common_success"]["episodes"] == 0
    assert len(rows) == 2


def test_missing_frozen_episode_is_key_identified():
    a = saved("A", 0, True, 7, 23, 15.)
    with pytest.raises(RuntimeError, match="Missing saved"):
        screen.compare_saved([a], {}, "v2")
