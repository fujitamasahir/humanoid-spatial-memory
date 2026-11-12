"""Contract tests for posthoc first-gate separability audit (no MuJoCo)."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from analyze_rdao_gate_feature_separability import (
    contradictions, simple_signature, step_effect,
)


def record(*, policy="first", outcome="rescued", delta="-52",
           cost="4.5", blocker="3", free="1",
           world="M:80030010", schedule="0", gates="1"):
    return {
        "policy": policy, "paired_outcome": outcome,
        "delta_censored_steps": delta, "delta_distance_m": "-26.25",
        "nominal_cost_increase": cost,
        "first_occupied_translation_in_old_nominal_route": blocker,
        "nonbackward_observed_free_neighbors": free,
        "world_identity": "phase15:fit:" + world,
        "schedule": schedule, "step": "3",
        "total_gate_overrides_in_episode": gates,
    }


def test_first_only_paired_effect_categories():
    assert step_effect(record()) == "rescued"
    assert step_effect(record(outcome="harmed")) == "harmed"
    assert step_effect(record(outcome="common_failure",
                              delta="0")) == "both_failed_by_horizon"
    assert step_effect(record(outcome="common_success",
                              delta="22")) == "slower_success"
    assert step_effect(record(outcome="common_success",
                              delta="-2")) == "faster_success"
    assert step_effect(record(outcome="common_success",
                              delta="0")) == "same_arrival_step"


def test_every_policy_outcomes_must_not_be_treated_as_per_gate_causes():
    with pytest.raises(ValueError, match="not isolated"):
        step_effect(record(policy="every", gates="3"))


def test_signature_overlap_witness_for_different_outcomes():
    positive = record(world="M:80030010")
    unchanged = record(world="M:80030000",
                       outcome="common_failure", delta="0")
    assert simple_signature(positive) == simple_signature(unchanged)
    collisions = contradictions([positive, unchanged])
    assert len(collisions) == 1
    assert collisions[0]["worlds"] == 2
    assert set(collisions[0]["distinct_effect_categories"]) == {
        "rescued", "both_failed_by_horizon",
    }


def test_no_conflict_when_only_correlated_repeats_differ():
    a = record(world="M:80030010", schedule="0")
    b = record(world="M:80030010", schedule="1")
    assert contradictions([a, b]) == []


def test_different_signatures_are_not_conflicts():
    positive = record(cost="3.0", blocker="2")
    neutral = record(world="R:80000018", outcome="common_failure",
                     delta="0", cost="2.75", blocker="6", free="3")
    assert contradictions([positive, neutral]) == []
