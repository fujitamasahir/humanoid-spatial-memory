"""Unit tests for a purely online, world-independent safe replanning gate."""
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from evaluate_rdao_online_safe_gate_screen import online_gate_decision

KWARGS = {
    "heading": 0,
    "unknown": "optimistic",
    "local_extents": (.1, .1),
    "cell_size": .75,
    "blocked_actions": frozenset(),
    "static_obstacle_cells": frozenset(),
    "pedestrian_context": {},
    "step": 19,
}


def policy(before, after, **updates):
    kw = dict(KWARGS, **updates)
    def original_planner(grid, start, goal, **kwargs):
        assert kwargs["step"] == 19
        return ([("turn", 1)] if grid[3, 5] == 1
                else [("move", (5, 4))])
    return original_planner, kw


@pytest.mark.parametrize("mode", ["first", "every"])
def test_public_safe_forward_reuses_prior_action(mode):
    before = np.zeros((9, 9), dtype=np.int8)
    before[3, 5] = -1
    after = before.copy()
    after[3, 5] = 1
    planner, kwargs = policy(before, after)
    route, details = online_gate_decision(
        before, after, (4, 4), (7, 4), kwargs, planner,
        prior_overrides=0, policy=mode)
    assert route == [("move", (5, 4))]
    assert details["override_applied"]
    assert details["guard"] == "passed_observed_cell_and_footprint_checks"
    assert details["changed_cells"] == 1


def test_first_mode_does_not_override_twice():
    before = np.zeros((9, 9), dtype=np.int8)
    before[3, 5] = -1
    after = before.copy()
    after[3, 5] = 1
    planner, kw = policy(before, after)
    route, details = online_gate_decision(
        before, after, (4, 4), (7, 4), kw, planner,
        prior_overrides=1, policy="first")
    assert route == [("turn", 1)]
    assert details["guard"] == "first_override_already_used"
    assert not details["override_applied"]


def test_every_mode_can_override_subsequent_eligible_events():
    before = np.zeros((9, 9), dtype=np.int8)
    before[3, 5] = -1
    after = before.copy()
    after[3, 5] = 1
    planner, kw = policy(before, after)
    route, details = online_gate_decision(
        before, after, (4, 4), (7, 4), kw, planner,
        prior_overrides=3, policy="every")
    assert route == [("move", (5, 4))]
    assert details["override_applied"]


def test_does_not_gate_when_after_map_unchanged():
    arr = np.zeros((9, 9), dtype=np.int8)
    planner, kw = policy(arr, arr)
    route, details = online_gate_decision(
        arr, arr, (4, 4), (7, 4), kw, planner,
        prior_overrides=0, policy="every")
    assert route == [("move", (5, 4))]
    assert details["guard"] == "no_new_map_cells"


def test_does_not_gate_if_new_first_action_is_not_turn():
    before = np.zeros((9, 9), dtype=np.int8)
    after = before.copy()
    after[2, 6] = 1
    planner, kw = policy(before, after)
    route, details = online_gate_decision(
        before, after, (4, 4), (7, 4), kw, planner,
        prior_overrides=0, policy="every")
    assert route == [("move", (5, 4))]
    assert not details["override_applied"]
    assert details["guard"] == "new_first_action_not_turn"


def test_rejects_occupied_new_destination():
    before = np.zeros((9, 9), dtype=np.int8)
    before[3, 5] = -1
    after = before.copy()
    after[3, 5] = 1
    after[4, 5] = 1
    planner, kw = policy(before, after)
    route, details = online_gate_decision(
        before, after, (4, 4), (7, 4), kw, planner,
        prior_overrides=0, policy="first")
    assert route == [("turn", 1)]
    assert details["guard"] == "destination_not_observed_free_after_update"


def test_rejects_previous_action_suppressed_by_blocked_feedback():
    from spatial_memory.navigation import blocked_action_key
    before = np.zeros((9, 9), dtype=np.int8)
    before[3, 5] = -1
    after = before.copy()
    after[3, 5] = 1
    k = blocked_action_key((4, 4), 0, ("move", (5, 4)))
    planner, kw = policy(before, after, blocked_actions=frozenset({k}))
    route, details = online_gate_decision(
        before, after, (4, 4), (7, 4), kw, planner,
        prior_overrides=0, policy="every")
    assert route == [("turn", 1)]
    assert details["guard"] == "action_previously_blocked"


def test_invalid_policy_and_map_shape_fail_closed():
    grid = np.zeros((9, 9), dtype=np.int8)
    planner, kw = policy(grid, grid)
    with pytest.raises(ValueError, match="Invalid gate policy"):
        online_gate_decision(grid, grid, (4, 4), (7, 4),
                             kw, planner, prior_overrides=0, policy="oops")
    with pytest.raises(ValueError, match="shapes do not match"):
        online_gate_decision(grid, grid[:8], (4, 4), (7, 4),
                             kw, planner, prior_overrides=0, policy="first")
