"""Fast tests of opt-in RDAO v2 viewpoint-aware observation scoring.

All tests use public synthetic ternary grids, not MuJoCo or hidden worlds.
"""
import math
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

from spatial_memory import rdao as rdao_module
from spatial_memory.rdao import RDAOController
from spatial_memory.rdao_v2 import (
    DEFER_SCORE_MULTIPLIER, RDAOv2ViewpointController,
    footprint_visibility_public, next_public_viewpoint,
    viewpoint_quality_public,
)
from analyze_rdao_visibility_extent_audit import footprint_visibility


def agent(grid):
    return RDAOv2ViewpointController(
        grid, goal=(7, 7), max_observations=20,
        local_extents=(0.0, 0.0), cell_size_m=.75)


def kwargs():
    return {
        "cell_size_m": .75, "range_m": 6.,
        "horizontal_fov_deg": 120., "ray_count": 61,
        "unknown_open_probability": .5,
    }


def test_matches_saved_footprint_audit_geometry_on_synthetic_public_maps():
    grid = np.zeros((16, 16), dtype=np.int8)
    grid[6, 6] = -1
    grid[8, 5] = 1
    for yaw in [0., math.pi/2, math.pi, -math.pi/2]:
        for target in [(6, 7), (7, 6), (11, 5), (9, 8), (4, 4)]:
            a = footprint_visibility_public(
                grid, (5, 5), yaw, target, **kwargs())
            b = footprint_visibility(
                grid, (5, 5), yaw, target,
                cell_size_m=.75, range_m=6., fov_deg=120.,
                ray_count=61, unknown_open=.5)
            assert a == b


def test_view_quality_corrects_binary_angle_blindness():
    grid = np.zeros((16, 16), dtype=np.int8)
    grid[7, 5] = -1
    pos, cell = (3, 3), (5, 7)  # 63.4 degrees, just beyond center half-FOV.
    old = footprint_visibility_public(
        grid, pos, 0., cell, **kwargs())
    turned = footprint_visibility_public(
        grid, pos, math.pi/2, cell, **kwargs())
    assert old > 0.
    assert turned == old  # pure feasibility is essentially binary
    now_quality = viewpoint_quality_public(
        grid, pos, 0., cell, **kwargs())
    turn_quality = viewpoint_quality_public(
        grid, pos, math.pi/2, cell, **kwargs())
    assert 0 < now_quality < turn_quality
    assert turn_quality <= turned


def test_next_viewpoint_uses_public_turn_and_known_free_translation():
    grid = np.zeros((12, 12), dtype=np.int8)
    assert next_public_viewpoint(grid, (3, 3), 0., [("turn", 1)]) == (
        (3, 3), math.pi/2, "turn")
    assert next_public_viewpoint(grid, (3, 3), 0.,
                                 [("move", (4, 3))]) == (
        (4, 3), 0., "move_known_free")
    grid[3, 4] = -1
    assert next_public_viewpoint(grid, (3, 3), 0.,
                                 [("move", (4, 3))]) is None
    assert next_public_viewpoint(grid, (3, 3), 0., []) is None


def test_v2_reduces_candidate_score_when_turn_yields_better_view(monkeypatch):
    grid = np.zeros((16, 16), dtype=np.int8)
    grid[7, 5] = -1
    controller = agent(grid)

    def dummy_parent(self, step, position, yaw, route, planning_ns):
        item = {
            "region": (2, 3),
            "cells": [(5, 7)],
            "visibility": 1.0,
            "score": .43,
            "counterfactual": {"first_action_changes": True},
        }
        return [tuple(position)], [item], item, planning_ns

    monkeypatch.setattr(RDAOController, "_candidate_scores", dummy_parent)
    _, results, best, _ = controller._candidate_scores(
        7, (3, 3), 0., [("turn", 1)], 0)
    assert results[0]["v2_deferred"] is True
    assert results[0]["score"] == pytest.approx(.43*DEFER_SCORE_MULTIPLIER)
    assert results[0]["v2_next_view_quality"] > (
        results[0]["v2_current_view_quality"])
    assert best is results[0]


def test_no_deferral_for_translation_into_unknown(monkeypatch):
    grid = np.zeros((16, 16), dtype=np.int8)
    grid[3, 4] = -1
    c = agent(grid)

    def synthetic(self, step, pos, yaw, route, ns):
        item = {
            "region": (2, 2), "cells": [(5, 7)],
            "visibility": 1.0, "score": .43,
        }
        return [tuple(pos)], [item], item, ns

    monkeypatch.setattr(RDAOController, "_candidate_scores", synthetic)
    _, rows, best, _ = c._candidate_scores(
        7, (3, 3), 0., [("move", (4, 3))], 0)
    assert rows[0]["v2_next_view_action"] is None
    assert rows[0]["v2_deferred"] is False
    assert best["score"] == .43


def test_v2_restores_original_visibility_hook_after_success():
    grid = np.zeros((9, 9), dtype=np.int8)
    grid[4, 3] = -1
    c = agent(grid)
    old = rdao_module.predicted_cell_visibility
    c.set_context(1, (1, 4), 0.0)
    result = c.decide(1, (1, 4))
    assert rdao_module.predicted_cell_visibility is old
    assert result["rdao"]["remaining_observation_budget"] == 19
    assert result["rdao"]["decision_time_ns"] >= 0
    assert any("v2_deferred" in x
               for x in result["rdao"]["candidate_regions"])
    assert c.used == 1  # only the real authorized refresh changes count


def test_v2_restores_original_visibility_hook_on_exception(monkeypatch):
    grid = np.zeros((9, 9), dtype=np.int8)
    c = agent(grid)
    original = rdao_module.predicted_cell_visibility

    def fail(*args):
        assert rdao_module.predicted_cell_visibility is footprint_visibility_public
        raise RuntimeError("fake failure")

    monkeypatch.setattr(RDAOController, "_regions", fail)
    with pytest.raises(RuntimeError, match="fake failure"):
        c._regions(1, (1, 4), 0., [])
    assert rdao_module.predicted_cell_visibility is original
