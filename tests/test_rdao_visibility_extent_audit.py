"""Pure tests for RDAO visibility feasibility model comparison.

Never instantiate MuJoCo or load any test/held-out worlds.
"""
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

from analyze_rdao_visibility_extent_audit import (
    add_confusion, footprint_envelope, footprint_visibility,
    frame_samples, quality,
)
from spatial_memory.rdao import predicted_cell_visibility


def test_partial_cell_fov_overlap_is_candidate_when_center_is_outside():
    # 1x2 cell offset: center angle ~63.4deg > 60deg FOV half-angle,
    # but finite cell footprint intersects the 120deg observable wedge.
    grid = np.full((16, 16), -1, dtype=np.int8)
    pos, yaw, target = (5, 5), 0.0, (6, 7)
    assert footprint_envelope(pos, yaw, target)
    assert predicted_cell_visibility(
        grid, pos, yaw, target, cell_size_m=.75, range_m=6.0,
        horizontal_fov_deg=120, ray_count=61) == 0.0
    assert footprint_visibility(grid, pos, yaw, target) > 0


def test_partial_cell_range_overlap_is_candidate_when_center_is_outside():
    grid = np.full((16, 16), -1, dtype=np.int8)
    pos, yaw, target = (5, 5), 0.0, (8, 5)
    assert footprint_envelope(pos, yaw, target, range_m=2.0)
    assert predicted_cell_visibility(
        grid, pos, yaw, target, cell_size_m=.75, range_m=2.0,
        horizontal_fov_deg=120, ray_count=61) == 0.0
    assert footprint_visibility(grid, pos, yaw, target, range_m=2.0) > 0


def test_both_predictors_respect_known_occupied_intermediate_cell():
    grid = np.full((16, 16), -1, dtype=np.int8)
    pos, target = (5, 5), (8, 5)
    grid[5, 6] = 1
    assert footprint_visibility(grid, pos, 0.0, target) == 0.0
    assert predicted_cell_visibility(
        grid, pos, 0.0, target, cell_size_m=.75, range_m=6.0,
        horizontal_fov_deg=120, ray_count=61) == 0.0


def test_binary_metrics_count_positive_and_negative_labels():
    d = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    for y, p in ((True, True), (True, False), (False, True), (False, False)):
        add_confusion(d, y, p)
    metrics = quality(d)
    assert metrics["actual_visible"] == 2
    assert metrics["predicted_visible"] == 2
    assert metrics["precision"] == .5
    assert metrics["recall"] == .5
    assert metrics["false_positive_rate"] == .5


def test_frame_samples_reconstruct_raw_sensor_values_and_old_memory():
    before = np.full((16, 16), -1, dtype=np.int8)
    before[5, 5] = 0
    after = before.copy()
    # Inside ordinary FOV
    after[5, 6] = 0
    # Center outside ordinary FOV, but cell footprint overlaps
    after[7, 6] = 1
    effect = {
        "memory_before": before.tolist(),
        "memory_after": after.tolist(),
        "received_observation_values": [
            {"cell": [6, 5], "value": 0},
            {"cell": [6, 7], "value": 1},
        ],
        "visible_cell_count": 2,
        "memory_changed_cell_count": 2,
        "memory_changed_cells": [
            {"cell": [6, 5], "before": -1, "after": 0},
            {"cell": [6, 7], "before": -1, "after": 1},
        ],
    }
    frame = {
        "step": 6,
        "observation_granted": True,
        "rdao": {
            "granted": True, "position": [5, 5], "heading_yaw": 0.,
            "nominal_route": [["move", [6, 5]], ["move", [7, 5]]],
            "observation_effect": effect,
        },
    }
    results = frame_samples(frame)
    assert results["raw_new"] == 2
    assert results["observed_new_outside_envelope"] == 0
    legacy = results["counts"]["legacy"]["all"]
    footprint = results["counts"]["footprint"]["all"]
    assert legacy["tp"] + legacy["fn"] == 2
    assert footprint["tp"] + footprint["fn"] == 2
    assert legacy["fn"] >= 1
    assert footprint["tp"] >= legacy["tp"]
    assert before[7, 6] == -1
    assert after[7, 6] == 1


def test_frame_samples_reject_inconsistent_frozen_transition():
    before = [[-1] * 7 for _ in range(7)]
    after = [list(row) for row in before]
    after[3][4] = 1
    frame = {
        "step": 3, "observation_granted": True,
        "rdao": {
            "granted": True, "position": [3, 3], "heading_yaw": 0.0,
            "nominal_route": [], "observation_effect": {
                "memory_before": before, "memory_after": after,
                "received_observation_values": [],
                "visible_cell_count": 0,
                "memory_changed_cell_count": 1,
                "memory_changed_cells": [{"cell": [4, 3]}],
            },
        },
    }
    with pytest.raises(ValueError, match="transition"):
        frame_samples(frame)
