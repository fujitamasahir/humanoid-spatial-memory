"""Fast contracts for frozen RDAO footprint-online forensic trace comparison."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from analyze_rdao_footprint_visibility_online_forensics import (
    build_timeline, category, check_case, first_differences, frame_features,
)


def row(**kwargs):
    return dict({
        "original_success": "True",
        "variant_success": "True",
        "delta_steps": "2",
        "original_elapsed_steps": "2", "variant_elapsed_steps": "2",
        "original_observations": "1", "variant_observations": "2",
        "first_changed_observation_step": "1",
        "first_changed_action_or_pose_step": "2",
    }, **kwargs)


def frame(step, observed=False, action=None, pos=None, *,
          count=1, reason=None):
    return {
        "step": step, "observation_granted": observed,
        "observation_count": count,
        "position": pos or [0, 0], "heading_yaw": 0.,
        "action": action or ["turn", 1],
        "moved": False, "blocked": False,
        "rdao": {"reason": reason, "score": .1, "threshold": .2,
                 "nominal_route": [["move", [1, 0]]],
                 "candidate_regions": []},
    }


def traces():
    initial = frame(0, observed=True)
    left = {"steps": [initial,
                     frame(1, observed=False, count=1, reason="none"),
                     frame(2, observed=False, count=1)]}
    right = {"steps": [initial,
                      frame(1, observed=True, count=2, reason="granted"),
                      frame(2, observed=False, action=["turn", 0], count=2)]}
    return left, right


def test_separates_observation_change_and_later_action_change():
    left, right = traces()
    assert first_differences(left, right) == (1, 2)


def test_same_trace_has_no_divergence():
    left, _ = traces()
    assert first_differences(left, left) == (None, None)


def test_first_sensing_must_precede_action_change():
    left, right = traces()
    assert check_case(left, right, row()) == (1, 2)


def test_cannot_claim_action_before_observation_change():
    left, right = traces()
    right["steps"][1]["action"] = ["move", [1, 0]]
    with pytest.raises(RuntimeError, match="before visibility"):
        check_case(left, right, row(
            first_changed_action_or_pose_step="1",
            first_changed_observation_step="2"))


def test_forensic_timeline_keeps_both_arm_snapshots():
    left, right = traces()
    timeline = build_timeline("fit:M:case", 0, row(), left, right)
    assert len(timeline) == 3
    assert timeline[1]["first_observation_change"]
    assert timeline[2]["first_action_change"]
    assert timeline[1]["original_observation_granted"] is False
    assert timeline[1]["footprint_observation_granted"] is True


def test_categories_distinguish_censored_failures_and_arrival_change():
    assert category(row()) == "common_success_worse"
    assert category(row(delta_steps="-4")) == "common_success_better"
    assert category(row(delta_steps="0")) == "common_success_same_steps"
    assert category(row(original_success="False", variant_success="False")) == (
        "both_horizon_censored_failures")
    assert category(row(original_success="False", variant_success="True")) == "rescued"
    assert category(row(original_success="True", variant_success="False")) == "harmed"


def test_frame_features_preserve_reason_and_observation_map_count():
    f = frame(5, observed=True)
    f["rdao"]["observation_effect"] = {
        "memory_changed_cell_count": 6, "route_after": [["turn", 3]]}
    result = frame_features(f)
    assert result["observed_memory_changed_cells"] == 6
    assert "turn" in result["new_route_first_action"]
    assert result["observation_granted"]
