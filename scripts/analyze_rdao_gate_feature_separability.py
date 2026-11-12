"""Read-only separability audit of the previously extracted RDAO gate features.

Avoid converting episode-level labels into per-event causal labels. In this
audit the ONLY causal-action screening arm is 'first': exactly one gated
action per episode. Repeated pedestrian schedules are not independent worlds.
All observations were made on reused Phase 2 FIT worlds.

This report tests *identifiability of simple public-map features*, not a
learned or deployable RDAO v2 policy. There is NO threshold optimization.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "results/phase2_mujoco" /
          "rdao_v1_gate_event_route_features_v1/gate_event_route_features.csv")
DEFAULT_OUTPUT = ROOT / "results/phase2_mujoco/rdao_v1_gate_feature_separability_audit_v1"
SIMPLE_FEATURES = (
    "nominal_cost_increase",
    "first_occupied_translation_in_old_nominal_route",
    "nonbackward_observed_free_neighbors",
)


def _num(record, key):
    value = record[key]
    return None if value == "" else float(value)


def step_effect(row):
    """Classify *paired* outcomes, not the intrinsic value of an event."""
    if row["policy"] != "first" or int(row["total_gate_overrides_in_episode"]) != 1:
        raise ValueError("Event outcome is not isolated to one episode-level gate")
    outcome = row["paired_outcome"]
    delta = float(row["delta_censored_steps"])
    if outcome == "rescued":
        return "rescued"
    if outcome == "harmed":
        return "harmed"
    if outcome == "common_failure":
        # Both endpoints were horizon-censored. Delta steps is not arrival time.
        return "both_failed_by_horizon"
    if outcome != "common_success":
        raise ValueError(f"Unexpected outcome label: {outcome}")
    return ("faster_success" if delta < 0 else
            "slower_success" if delta > 0 else "same_arrival_step")


def simple_signature(row):
    """An intentionally small, diagnosis-only three-feature tuple."""
    return (
        _num(row, "nominal_cost_increase"),
        _num(row, "first_occupied_translation_in_old_nominal_route"),
        _num(row, "nonbackward_observed_free_neighbors"),
    )


def contradictions(rows):
    """Find identical 3-feature tuples with different paired effects."""
    by_sig = defaultdict(list)
    for row in rows:
        by_sig[simple_signature(row)].append(row)
    conflicting = []
    for signature, records in sorted(by_sig.items(), key=lambda v: str(v[0])):
        effects = sorted({step_effect(row) for row in records})
        if len(effects) <= 1:
            continue
        conflicting.append({
            "features": {key: v for key, v in zip(SIMPLE_FEATURES, signature)},
            "distinct_effect_categories": effects,
            "worlds": len({r["world_identity"] for r in records}),
            "episodes": [
                {"world": r["world_identity"].split(":")[-2] + ":" +
                          r["world_identity"].split(":")[-1],
                 "schedule": int(r["schedule"]),
                 "step": int(r["step"]), "effect": step_effect(r),
                 "delta_censored_steps": float(r["delta_censored_steps"]),
                 "delta_distance_m": float(r["delta_distance_m"])}
                for r in records
            ],
        })
    return conflicting


def _mean(records, key):
    values = [_num(row, key) for row in records]
    non_null = [v for v in values if v is not None]
    return sum(non_null) / len(non_null) if non_null else None


def summarize(rows):
    first = [row for row in rows if row["policy"] == "first"]
    every = [row for row in rows if row["policy"] == "every"]
    if len(rows) != 107 or len(first) != 34 or len(every) != 73:
        raise ValueError("Expected frozen 34 first and 73 every gate events")
    if any(int(row["total_gate_overrides_in_episode"]) != 1 for row in first):
        raise ValueError("First-only experiment unexpectedly contains >1 gate")
    if any(row["actual_action_equals_proposed"] != "True" for row in rows):
        raise ValueError("Some observed online gates were vetoed by selected-action safety")
    counter = Counter(step_effect(row) for row in first)
    if (counter["rescued"] != 4 or counter["harmed"] != 0 or
            counter["slower_success"] != 14 or
            counter["same_arrival_step"] != 5 or
            counter["both_failed_by_horizon"] != 11):
        # The expected common-success same-step count can be rechecked
        # against the committed paired CSV; fail closed on a mismatch.
        raise ValueError(f"First-only effect labels differ from frozen results: {counter}")
    collisions = contradictions(first)
    unique_worlds = {row["world_identity"] for row in first}
    world_schedule_counts = defaultdict(set)
    for row in first:
        world_schedule_counts[row["world_identity"]].add(int(row["schedule"]))
    by_effect = {}
    for name in sorted(counter):
        records = [row for row in first if step_effect(row) == name]
        by_effect[name] = {
            "episodes": len(records),
            "unique_worlds": len({row["world_identity"] for row in records}),
            "mean_nominal_cost_increase": _mean(records, "nominal_cost_increase"),
            "mean_first_blocker_translation": _mean(
                records, "first_occupied_translation_in_old_nominal_route"),
            "mean_observed_free_nonbackward_branches": _mean(
                records, "nonbackward_observed_free_neighbors"),
            "mean_memory_changed_cells": _mean(records, "memory_changed_cells"),
            "mean_delta_censored_steps": _mean(records, "delta_censored_steps"),
        }
    return {
        "status": "POSTHOC_FIT_FEATURE_SEPARABILITY_AUDIT_NOT_TRAINING",
        "event_counts": {"first": len(first), "every": len(every)},
        "first_distinct_worlds": len(unique_worlds),
        "first_worlds_with_two_schedules": sum(
            len(v) == 2 for v in world_schedule_counts.values()),
        "first_step_effects": dict(counter),
        "first_effect_feature_distributions": by_effect,
        "identical_three_feature_conflicts": collisions,
        "unknown_neighbor_count_distribution": dict(Counter(
            row["nonbackward_unknown_neighbors"] for row in first)),
        "revisited_origin_within_six_steps_first": sum(
            row["revisited_origin_within_6_steps"] != "" for row in first),
        "caveats": [
            "These are two outcome-informed fit worlds for rescue; no held-out validation.",
            "The two schedules of a world are correlated rather than independent maze replicates.",
            "Event labels from EVERY are omitted from causal classifier comparisons because multiple gates may fire per episode.",
            "The selected three-feature signature is a negative diagnostic only, not a proof that no richer predictive features exist.",
            "Same arrival step can conceal changed distances, observations or trajectory shape.",
            "Both failed by horizon are censored; no arrival-time equivalence is asserted.",
            "The nominal RDAO A* route cost is NOT the executed pedestrian-aware G1 policy value.",
            "The old nominal route's now-known blockers are public updated observations, NOT oracle geometry.",
            "Return-to-origin is a POSTHOC future label, never a decision-time feature.",
            "A deterministic optimal path planner on one fixed updated map satisfies V(s) <= c(s,a)+V(s'): such myopic value comparison alone cannot demonstrate that old-action gating improves expected performance.",
        ],
    }


def _write_csv(path, data):
    if not data:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        out = csv.DictWriter(f, fieldnames=list(data[0]))
        out.writeheader()
        out.writerows(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Never overwrite prior analysis: {args.output}")
    with SOURCE.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    result = summarize(rows)
    result["source_file_sha256"] = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    args.output.mkdir(parents=True)
    (args.output / "summary.json").write_text(
        json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8")
    first_rows = [dict(row, paired_first_gate_effect=step_effect(row),
                       simple_feature_signature=json.dumps(simple_signature(row)))
                  for row in rows if row["policy"] == "first"]
    _write_csv(args.output / "first_gate_outcomes_and_features.csv", first_rows)
    print(json.dumps({
        "output": str(args.output),
        "first_distinct_worlds": result["first_distinct_worlds"],
        "events": result["event_counts"],
        "effects": result["first_step_effects"],
        "simple_signature_conflicts": result["identical_three_feature_conflicts"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
