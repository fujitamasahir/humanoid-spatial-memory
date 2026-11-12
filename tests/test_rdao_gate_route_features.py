"""Fast pure-stdlib tests for observed-only route event features."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from analyze_rdao_gate_route_features import (
    first_blocker_in_nominal_route, public_branch_count,
    horizon_return, one_event
)


def test_first_blocker_counts_translations_not_turns():
    grid = [[-1] * 7 for _ in range(7)]
    grid[2][4] = 1
    route = [
        ["turn", 1], ["move", [3, 2]], ["move", [4, 2]],
        ["turn", 2], ["move", [4, 3]]
    ]
    index, states = first_blocker_in_nominal_route(route, grid)
    assert index == 2
    assert states == [-1, 1, -1]


def test_no_observed_blocker_is_not_assumed_open():
    grid = [[-1] * 7 for _ in range(7)]
    assert first_blocker_in_nominal_route([["move", [3, 3]]], grid) == (None, [-1])


def test_branch_counts_only_observed_map_and_excludes_return():
    grid = [[-1] * 6 for _ in range(6)]
    # target (3,3), origin (2,3), non-backward neighbors:
    # (4,3) free, (3,2) unknown, (3,4) occupied.
    grid[3][4] = 0
    grid[4][3] = 1
    assert public_branch_count(grid, [3, 3], [2, 3]) == (1, 1, 1)


def test_future_return_is_explicitly_only_posthoc():
    frames = [
        {"step": 10, "position": [3, 3]},
        {"step": 11, "position": [4, 3]},
        {"step": 12, "position": [4, 3]},
        {"step": 13, "position": [3, 3]},
    ]
    assert horizon_return(frames, 10, [3, 3], horizon=6) == 3
    assert horizon_return(frames, 10, [3, 3], horizon=2) is None


def test_event_features_ignore_hidden_occupancy():
    old = [[-1] * 6 for _ in range(6)]
    after = [list(row) for row in old]
    after[3][3] = 0
    after[3][4] = 0
    after[2][4] = 1
    effect = {
        "memory_before": old,
        "memory_after": after,
        "memory_changed_cell_count": 3,
        "route_before": [["move", [3, 3]], ["move", [4, 2]]],
        "route_cost_before": 3.25,
        "route_cost_after": 6.25,
    }
    case = {
        "key": ["fit:M:case", 0, 42],
        "policy": "first",
        "trace": {"steps": [
            {"step": 5, "position": [3, 3]},
            {"step": 6, "position": [4, 3]},
            {"step": 7, "position": [3, 3]},
        ]},
    }
    frame = {"step": 5, "action": ["move", [3, 3]],
             "rdao": {"observation_effect": effect}}
    event = {"step": 5, "position": [2, 3],
             "prior_action": ["move", [3, 3]],
             "new_action": ["turn", 1]}
    rec = one_event(event, frame, case)
    assert rec["first_occupied_translation_in_old_nominal_route"] == 2
    assert rec["nominal_cost_increase"] == 3
    assert rec["newly_known_occupied_cells"] == 1
    assert rec["newly_known_free_cells"] == 2
    assert rec["actual_action_equals_proposed"] is True
    assert rec["memory_changed_cells"] == 3
    assert rec["revisited_origin_within_6_steps"] is None
