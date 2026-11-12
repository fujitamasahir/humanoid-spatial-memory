"""Fast tests of single-variable RDAO footprint visibility online intervention.

No MuJoCo world construction, no hidden geometry, no held-out data.
"""
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

import evaluate_rdao_footprint_visibility_online as audit
import spatial_memory.rdao as rdao_module


def test_footprint_predictor_keeps_public_geometry_and_interface():
    grid = np.full((16, 16), -1, dtype=np.int8)
    grid[5, 5] = 0
    args = dict(cell_size_m=.75, range_m=6.,
                horizontal_fov_deg=120., ray_count=61,
                unknown_open_probability=.5)
    # Candidate cell center lies outside 60 degree cone, finite cell enters.
    old = rdao_module.predicted_cell_visibility(
        grid, (5, 5), 0.0, (6, 7), **args)
    new = audit.footprint_predictor(grid, (5, 5), 0.0, (6, 7), **args)
    assert old == 0.0
    assert new > 0.0


def test_public_known_occluder_still_blocks():
    grid = np.full((16, 16), -1, dtype=np.int8)
    grid[5, 6] = 1
    args = dict(cell_size_m=.75, range_m=6.,
                horizontal_fov_deg=120., ray_count=61,
                unknown_open_probability=.5)
    assert audit.footprint_predictor(
        grid, (5, 5), 0.0, (8, 5), **args) == 0.0


def test_monkeypatch_restores_original_after_success(monkeypatch):
    old = rdao_module.predicted_cell_visibility

    def fake_episode(payload, schedule, method):
        assert rdao_module.predicted_cell_visibility is audit.footprint_predictor
        assert (payload, schedule, method) == ("fake", 0, "rdao_v1")
        return {"success": True}, {"steps": []}

    monkeypatch.setattr(audit.evaluator, "_instrumented_case", fake_episode)
    row, trace = audit.evaluate_footprint("fake", 0)
    assert row["success"]
    assert rdao_module.predicted_cell_visibility is old


def test_monkeypatch_restores_original_on_failure(monkeypatch):
    old = rdao_module.predicted_cell_visibility

    def raise_error(*args):
        assert rdao_module.predicted_cell_visibility is audit.footprint_predictor
        raise RuntimeError("sim failed")

    monkeypatch.setattr(audit.evaluator, "_instrumented_case", raise_error)
    with pytest.raises(RuntimeError, match="sim failed"):
        audit.evaluate_footprint("fake", 0)
    assert rdao_module.predicted_cell_visibility is old


def test_sensing_change_is_distinct_from_action_change():
    before = {"steps": [
        {"step": 0, "observation_granted": True},
        {"step": 1, "observation_granted": False},
        {"step": 2, "observation_granted": True},
    ]}
    after = {"steps": [
        {"step": 0, "observation_granted": True},
        {"step": 1, "observation_granted": True},
        {"step": 2, "observation_granted": False},
    ]}
    assert audit.first_observation_difference(before, after) == 1
    assert audit.first_observation_difference(before, before) is None


def test_aggregate_counts_rescues_harms_and_common_success_efficiency():
    def record(world, before, after, old_steps, new_steps, old_dist, new_dist):
        return {
            "world_identity": "fit:" + world,
            "original_success": before, "variant_success": after,
            "original_elapsed_steps": old_steps, "variant_elapsed_steps": new_steps,
            "original_observations": 10, "variant_observations": 8,
            "original_travel_distance_m": old_dist, "variant_travel_distance_m": new_dist,
            "original_scheduler_ms": 1.0, "variant_scheduler_ms": 1.25,
            "variant_unwanted_contacts": 0,
            "first_changed_observation_step": 3,
            "first_changed_action_or_pose_step": 4,
            "delta_steps": new_steps - old_steps,
            "delta_distance_m": new_dist - old_dist,
        }
    data = [
        record("A", False, True, 80, 28, 40., 15.),
        record("B", True, False, 74, 80, 32., 35.),
        record("C", True, True, 40, 44, 20., 22.),
    ]
    a = audit.aggregate(data)
    assert a["original_successes"] == 2
    assert a["variant_successes"] == 2
    assert a["rescued_failures"] == 1
    assert a["harmed_successes"] == 1
    assert a["paired_common_success"]["episodes"] == 1
    assert a["paired_common_success"]["steps_worse"] == 1
    assert a["paired_common_success"]["distance_worse"] == 1
    assert a["mean_original_observations"] == 10
    assert a["mean_variant_observations"] == 8
