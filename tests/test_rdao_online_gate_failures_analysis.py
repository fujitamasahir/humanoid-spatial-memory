"""Fast stdlib-only tests for the read-only RDAO online-gate forensic analyzer."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from analyze_rdao_online_safe_gate_failures import (
    first_action_pose_divergence, first_sensing_divergence,
    outcome_category, paired_summary,
)


def row(policy, before_success, after_success, original_steps,
        new_steps, original_obs, new_obs, orig_dist, new_dist):
    return {
        "policy": policy,
        "world_identity": "phase1.5-v0.4-BPRIME-1:fit:M:80030010",
        "baseline_success": str(before_success),
        "gated_success": str(after_success),
        "baseline_elapsed_steps": str(original_steps),
        "gated_elapsed_steps": str(new_steps),
        "baseline_observations": str(original_obs),
        "gated_observations": str(new_obs),
        "baseline_travel_distance_m": str(orig_dist),
        "gated_travel_distance_m": str(new_dist),
        "baseline_turns": "0",
        "gated_turns": "0",
        "gate_overrides": "1",
    }


def test_classifies_paired_outcomes_without_confusing_timing():
    assert outcome_category(row("first", False, True, 80, 28, 20, 6, 41, 15)) == "rescued"
    assert outcome_category(row("every", True, False, 74, 80, 14, 16, 25, 27)) == "harmed"
    assert outcome_category(row("first", True, True, 24, 46, 7, 8, 12, 26)) == "common_success"
    assert outcome_category(row("every", False, False, 80, 80, 9, 8, 31, 33)) == "common_failure"


def test_common_success_worsening_is_counted_even_when_goal_succeeds():
    r = [
        row("first", True, True, 24, 46, 7, 9, 12, 25.5),
        row("first", False, True, 80, 28, 20, 6, 41.25, 15),
        row("every", True, False, 74, 80, 13, 14, 35, 36.5),
    ]
    summary = paired_summary(r)
    a = summary["first"]["groups"]
    assert a["rescued"]["episodes"] == 1
    assert a["common_success"]["episodes"] == 1
    assert a["common_success"]["worsened_elapsed_steps"] == 1
    assert a["common_success"]["improved_elapsed_steps"] == 0
    assert a["common_success"]["total_delta_elapsed_steps"] == 22
    assert a["common_success"]["total_delta_travel_distance_m"] == 13.5
    assert a["rescued"]["total_delta_elapsed_steps"] == -52
    assert summary["every"]["groups"]["harmed"]["episodes"] == 1


def test_action_divergence_is_distinct_from_sensing_timing():
    original = {"steps": [
        {"step": 0, "position": [2, 2], "action": None,
         "heading_yaw": 0.0, "observation_granted": True},
        {"step": 1, "position": [2, 2], "action": ["turn", 1],
         "heading_yaw": 1.57, "observation_granted": False},
        {"step": 2, "position": [2, 3], "action": ["move", [2, 3]],
         "heading_yaw": 1.57, "observation_granted": True},
    ]}
    changed = {"steps": [
        {"step": 0, "position": [2, 2], "action": None,
         "heading_yaw": 0.0, "observation_granted": True},
        {"step": 1, "position": [2, 2], "action": ["turn", 1],
         "heading_yaw": 1.57, "observation_granted": True},
        {"step": 2, "position": [2, 2], "action": ["turn", 2],
         "heading_yaw": 3.14, "observation_granted": False},
    ]}
    assert first_action_pose_divergence(original, changed) == 2
    assert first_sensing_divergence(original, changed) == 1


def test_different_episode_lengths_are_reported_as_divergences():
    base = {"steps": [{"step": 0, "position": [0, 0],
                       "action": None, "heading_yaw": 0.0,
                       "observation_granted": True},
                      {"step": 1, "position": [1, 0],
                       "action": ["move", [1, 0]], "heading_yaw": 0.0,
                       "observation_granted": False}]}
    gated = {"steps": [base["steps"][0]]}
    assert first_action_pose_divergence(base, gated) == 1
