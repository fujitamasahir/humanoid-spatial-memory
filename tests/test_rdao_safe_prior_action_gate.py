"""Contract tests for safe pre-update first-action diagnostic.

No MuJoCo simulation, hidden geometry or unselected shield queries.
"""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from evaluate_rdao_safe_prior_action_gate import select_safe_preupdate_action
from spatial_memory.navigation import blocked_action_key


def _evaluate(before, after, blocked=frozenset(), heading=0, planner=None):
    def fake_policy(grid, start, goal, **kwargs):
        if planner:
            return planner(grid, start, goal, **kwargs)
        # An observed obstacle adjacent to the path changes the preferred
        # route but does not obstruct the next forward step.
        return [("turn", 1)] if grid[3, 5] == 1 else [("move", (5, 4))]
    return select_safe_preupdate_action(
        before, after, (4, 4), (7, 4), heading=heading,
        unknown="optimistic", local_extents=(.1, .1), cell_size=.75,
        blocked_actions=blocked, old_planner=fake_policy,
        planner_kwargs={"static_obstacle_cells": frozenset(),
                        "pedestrian_context": {}, "step": 3})


def test_safe_forward_action_can_be_kept_after_real_observation():
    before = np.zeros((9, 9), dtype=np.int8)
    before[3, 5] = -1
    after = before.copy()
    after[3, 5] = 1
    route, detail = _evaluate(before, after)
    assert route == [("move", (5, 4))]
    assert detail["override_applied"]
    assert detail["new_action"] == ("turn", 1)
    assert detail["chosen_action"] == ("move", (5, 4))
    assert detail["guard"] == "passed_observed_cell_and_footprint_checks"


def test_post_update_occupied_destination_blocks_the_gate():
    before = np.zeros((9, 9), dtype=np.int8)
    before[3, 5] = -1
    after = before.copy()
    after[3, 5] = 1
    after[4, 5] = 1
    route, detail = _evaluate(before, after)
    assert route == [("turn", 1)]
    assert not detail["override_applied"]
    assert detail["guard"] == "destination_not_observed_free_after_update"


def test_blocked_feedback_always_blocks_the_gate():
    before = np.zeros((9, 9), dtype=np.int8)
    before[3, 5] = -1
    after = before.copy()
    after[3, 5] = 1
    key = blocked_action_key((4, 4), 0, ("move", (5, 4)))
    route, detail = _evaluate(before, after, frozenset({key}))
    assert route == [("turn", 1)]
    assert not detail["override_applied"]
    assert detail["guard"] == "action_previously_blocked"


def test_no_override_if_original_and_updated_action_match():
    before = np.zeros((9, 9), dtype=np.int8)
    after = before.copy()
    route, detail = _evaluate(before, after)
    assert route == [("move", (5, 4))]
    assert not detail["override_applied"]
    assert detail["guard"] == "same_first_action_no_gate_needed"


def test_one_step_forward_and_motion_geometry_required():
    before = np.zeros((9, 9), dtype=np.int8)
    after = before.copy()
    planner = lambda grid, start, goal, **kw: (
        [("turn", 1)] if grid[3, 5] == 1 else [("move", (6, 4))])
    before[3, 5] = -1
    after[3, 5] = 1
    route, detail = _evaluate(before, after, planner=planner)
    assert route == [("turn", 1)]
    assert not detail["override_applied"]
    assert detail["guard"] == "prior_action_not_one_step_forward"


def test_unsafe_swept_footprint_does_not_use_unselected_shield():
    before = np.zeros((9, 9), dtype=np.int8)
    after = before.copy()
    before[3, 5] = -1
    after[3, 5] = 1
    # Occupied neighbor near the robot footprint is separately rejected by
    # public sweep even though the center destination remains free.
    after[4, 4] = 1
    route, detail = _evaluate(before, after)
    assert route == [("turn", 1)]
    assert not detail["override_applied"]
    assert detail["guard"] == "footprint_conflicts_with_observed_obstacle"
