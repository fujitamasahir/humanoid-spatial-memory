"""Synthetic contracts for decision-protected v2.2 scoring."""
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/"src"),str(ROOT/"scripts")]

from spatial_memory import rdao as rdao_module
from spatial_memory.rdao_v2 import RDAOv2ViewpointController
from spatial_memory.rdao_v22_decision_protected import (
    RDAOv22DecisionProtectedController,
    protects_immediate_route_decision,
)


def make_controller():
    grid = np.zeros((12, 12), dtype=np.int8)
    grid[5, 6] = -1
    return RDAOv22DecisionProtectedController(
        grid, goal=(10, 10), max_observations=20,
        local_extents=(0.0, 0.0), cell_size_m=.75)


def test_protect_first_action_change():
    assert protects_immediate_route_decision({
        "free_reachable": True, "occupied_reachable": True,
        "first_action_changes": True})
    assert protects_immediate_route_decision({
        "free_reachable": True, "occupied_reachable": False,
        "first_action_changes": False})
    assert not protects_immediate_route_decision({
        "free_reachable": True, "occupied_reachable": True,
        "first_action_changes": False})
    assert not protects_immediate_route_decision({})


def fake_base(self, step, pos, yaw, route, ns):
    rows = [
        {
            "region": (1, 1), "cells": [(5, 6)],
            "visibility": 1.0, "score": .40,
            "counterfactual": {
                "free_reachable": True, "occupied_reachable": True,
                "first_action_changes": True,
            }, "v2_current_view_quality": .20
        },
        {
            "region": (2, 1), "cells": [(5, 6)],
            "visibility": 1.0, "score": .35,
            "counterfactual": {
                "free_reachable": True, "occupied_reachable": True,
                "first_action_changes": False,
            }, "v2_current_view_quality": .20
        },
        {
            "region": (3, 1), "cells": [(5, 6)],
            "visibility": 1.0, "score": .30,
            "counterfactual": {
                "free_reachable": True, "occupied_reachable": False,
                "first_action_changes": False,
            }, "v2_current_view_quality": .20
        },
    ]
    return [tuple(pos)], rows, rows[0], ns


def test_preserves_critical_region_score_and_discount_noncritical(monkeypatch):
    monkeypatch.setattr(RDAOv2ViewpointController, "_candidate_scores",
                        fake_base)
    c = make_controller()
    _, rows, best, _ = c._candidate_scores(
        5, (4, 4), 0., [("turn", 1)], 0)
    assert len(rows) == 3
    assert rows[0]["v22_protected_immediate_decision"]
    assert rows[0]["score"] == pytest.approx(.40)
    assert rows[0]["v22_current_view_discount"] == 1.0
    assert not rows[1]["v22_protected_immediate_decision"]
    assert rows[1]["score"] == pytest.approx(.35*.2)
    assert rows[1]["v22_current_view_discount"] == pytest.approx(.2)
    assert rows[2]["v22_protected_immediate_decision"]
    assert rows[2]["score"] == pytest.approx(.30)
    assert best is rows[0]


def test_noncritical_discount_uses_public_geometry_without_next_pose(monkeypatch):
    def base_without_quality(self, step, pos, yaw, route, ns):
        row = {
            "region": (1, 1), "cells": [(5, 6)],
            "visibility": 1.0, "score": .4,
            "counterfactual": {"free_reachable": True,
                               "occupied_reachable": True,
                               "first_action_changes": False},
            "v2_current_view_quality": None,
        }
        return [tuple(pos)], [row], row, ns

    monkeypatch.setattr(RDAOv2ViewpointController, "_candidate_scores",
                        base_without_quality)
    c = make_controller()
    _, results, _, _ = c._candidate_scores(
        5, (4, 4), 0., [], 0)
    assert 0 <= results[0]["v22_current_view_discount"] <= 1
    assert results[0]["score"] <= .4


def test_unmodified_rdao_module_visibility_restored():
    c = make_controller()
    old = rdao_module.predicted_cell_visibility
    c.set_context(1, (2, 5), 0.)
    result = c.decide(1, (2, 5))
    assert rdao_module.predicted_cell_visibility is old
    assert c.used == 1
    assert result["rdao"]["remaining_observation_budget"] == 19


def test_v22_stays_under_same_public_safety_api():
    c = make_controller()
    assert isinstance(c, RDAOv2ViewpointController)
    assert c.cap == 20 and c.remaining == 19
    assert hasattr(c, "refresh")
    assert hasattr(c, "record_blocked_action")
