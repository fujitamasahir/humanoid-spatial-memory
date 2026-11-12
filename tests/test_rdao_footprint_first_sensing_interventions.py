"""Contract tests for first changed footprint observation causal ablation.

No MuJoCo rollouts, no shadow truth and no held-out world files.
"""
import copy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from evaluate_rdao_footprint_first_sensing_interventions import (
    first_sensing_delta,
    intervention_matches_first_footprint_scan,
    selected_targets,
    TARGETS,
    IDENTITY,
)


def frame(step, *, observation, effect=None, action=None):
    return {
        "step": step,
        "position": [10, 8],
        "heading_yaw": 0.,
        "observation_granted": bool(observation),
        "action": action or ["turn", 0],
        "rdao": {"observation_effect": effect},
    }


def three_traces():
    effect = {
        "memory_before": [[-1, 0], [0, -1]],
        "memory_after": [[1, 0], [0, -1]],
        "received_observation_values": [
            {"cell": [0, 0], "value": 1},
        ],
        "memory_changed_cell_count": 1,
        "visible_cell_count": 1,
        "route_after": [["turn", 1]],
    }
    original = {"steps": [
        frame(0, observation=True),
        frame(1, observation=False),
        frame(2, observation=False),
    ]}
    footprint = {"steps": [
        frame(0, observation=True),
        frame(1, observation=True, effect=effect, action=["turn", 1]),
        frame(2, observation=False),
    ]}
    forced = copy.deepcopy(footprint)
    forced["steps"][1]["rdao"]["intervention_forced"] = True
    return original, footprint, forced


def test_first_added_scan_detection_uses_observation_flag_not_action():
    original, candidate, _ = three_traces()
    assert first_sensing_delta(original, candidate) == (1, False, True)


def test_fidelity_requires_same_raw_and_memory():
    original, candidate, forced = three_traces()
    feat = intervention_matches_first_footprint_scan(
        original, candidate, forced, 1)
    assert feat["first_step_action_matches_footprint"]
    assert feat["post_update_route_matches_footprint"]
    assert feat["changed_cells"] == 1
    assert feat["visible_cells"] == 1


def test_fidelity_rejects_sensor_difference():
    original, candidate, forced = three_traces()
    forced["steps"][1]["rdao"]["observation_effect"][
        "received_observation_values"][0]["value"] = 0
    with pytest.raises(RuntimeError, match="same-pose memory mismatch"):
        intervention_matches_first_footprint_scan(original, candidate,
                                                  forced, 1)


def test_fidelity_rejects_nonidentical_pre_observation_pose():
    original, candidate, forced = three_traces()
    forced["steps"][1]["position"] = [11, 8]
    with pytest.raises(RuntimeError, match="pre-observation position"):
        intervention_matches_first_footprint_scan(original, candidate,
                                                  forced, 1)


def test_first_sensing_delta_requires_real_mismatch():
    original, _, _ = three_traces()
    with pytest.raises(RuntimeError, match="no divergent"):
        first_sensing_delta(original, copy.deepcopy(original))


def test_selected_targets_use_saved_step_with_identity_and_schedule():
    original, candidate, _ = three_traces()
    rows = {}
    orig = {}
    new = {}
    for world, schedule in TARGETS:
        key = (IDENTITY + world, schedule, 42)
        rows[key] = {"first_changed_observation_step": "1"}
        orig[key] = original
        new[key] = candidate
    result = selected_targets(rows, orig, new, max_cases=2)
    assert len(result) == 2
    assert result[0][0][-1] == 42
    assert result[0][1] == 1


def test_selected_targets_reject_unchanged_first_scan():
    original, candidate, _ = three_traces()
    rows = {}
    orig = {}
    new = {}
    for world, schedule in TARGETS:
        key = (IDENTITY + world, schedule, 42)
        rows[key] = {"first_changed_observation_step": "1"}
        orig[key] = original
        new[key] = candidate
    new[(IDENTITY + TARGETS[0][0], TARGETS[0][1], 42)] = original
    with pytest.raises(RuntimeError, match="no divergent"):
        selected_targets(rows, orig, new, max_cases=1)
