"""Causal first-sensing interventions for the footprint-only RDAO fit screen.

The 72-episode footprint policy changed ONLY visibility scoring. This
POSTHOC diagnostic intervenes at its first earlier-than-baseline observation
for a fixed list of previously inspected FIT cases.

For each case we compare:
  Original: frozen RDAO v1 (reproduced exactly).
  Footprint: saved previously evaluated footprint-only policy (not rerun).
  Forced-extra: force one ordinary authorized 61-ray observation with the
    ORIGINAL RDAO predictor, then use the original RDAO normally.
  Forced-swap: the same force, then cancel only the NEXT naturally requested
    observation; equal final observed count is NOT guaranteed.

The ordinary forced scan must exactly equal the saved footprint scan at
the selected step (raw cell values and updated public memory). First-scan
fidelity is required, and later decisions may differ. The original
independent emergency controller, selected-action collision shield and
20-observation cap remain unchanged. NO shadow/oracle data or held-out
worlds enter the policy. These retrospective step selections are NOT a
deployable online scheduling rule.

Creates new results only; never overwrites protected results.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import gzip
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

import evaluate_rdao_phase2 as evaluator
import phase2_mujoco_navigation as navigation
from evaluate_rdao_one_shot_interventions import (
    _bool, _compare_trace, _first_difference, _key, _load_csv,
    _metrics, _read_saved_traces, _run_with_intervention,
    _saved_observation_steps, _sha, _write_csv,
)
from evaluate_rdao_online_safe_gate_screen import _jsonable
from analyze_rdao_footprint_visibility_online_forensics import first_differences

PRIMARY = ROOT / "results/phase2_mujoco/rdao_v1_phase2_evaluation"
FOOTPRINT = ROOT / "results/phase2_mujoco/rdao_v1_footprint_visibility_online_fit72_v1"
FORENSICS = ROOT / "results/phase2_mujoco/rdao_v1_footprint_visibility_online_forensics_v1"
DEFAULT_OUT = ROOT / "results/phase2_mujoco/rdao_v1_footprint_first_sensing_causes_v1"
IDENTITY = "phase1.5-v0.4-BPRIME-1:fit:"
TARGETS = (
    ("R:80000017", 0),    # rescued and shorter, fewer scans
    ("M:80030007", 1),    # rescued, emergency intervention drop
    ("R:80000022", 0),    # major detour
    ("R:80000022", 1),    # correlated second schedule
    ("BP:80010001", 0),   # delayed path detour
    ("BP:80010004", 0),   # early observation preceded detour
    ("BP:80010013", 0),   # faster common success
    ("M:80030009", 0),    # both still failed despite extra sensing
    ("M:80030009", 1),
)
SOURCE_FILES = (
    PRIMARY / "primary_episodes.csv",
    PRIMARY / "primary_traces.jsonl.gz",
    FOOTPRINT / "paired_visibility_online.csv",
    FOOTPRINT / "visibility_online_traces.jsonl.gz",
    FORENSICS / "summary.json",
)


def read_footprint_traces(path):
    result = {}
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            item = json.loads(line)
            if item["variant"] != "rdao_v1_footprint_visibility":
                raise ValueError("Unexpected footprint saved trace variant")
            identity, schedule, seed = item["key"]
            key = (identity, int(schedule), int(seed))
            if key in result:
                raise RuntimeError("Duplicate saved footprint trace")
            result[key] = item["trace"]
    if len(result) != 72:
        raise RuntimeError("Expected exact saved 72 footprint traces")
    return result


def first_sensing_delta(original_trace, footprint_trace):
    before = {int(f["step"]): f for f in original_trace["steps"]}
    after = {int(f["step"]): f for f in footprint_trace["steps"]}
    for step in sorted(set(before) | set(after)):
        a, b = before.get(step), after.get(step)
        if a is None or b is None:
            raise ValueError("Episode ended before a decisive sensing mismatch")
        if bool(a["observation_granted"]) != bool(b["observation_granted"]):
            return step, bool(a["observation_granted"]), bool(b["observation_granted"])
    raise RuntimeError("Selected case has no divergent observation timing")


def intervention_matches_first_footprint_scan(original, footprint, forced, step):
    """Verify FIRST changed scan is physically identical, not only row metrics."""
    a = next(f for f in original["steps"] if int(f["step"]) == step)
    b = next(f for f in footprint["steps"] if int(f["step"]) == step)
    c = next(f for f in forced["steps"] if int(f["step"]) == step)
    if a["observation_granted"] or not b["observation_granted"]:
        raise ValueError("Selected first divergence is not earlier footprint sensing")
    if not c["observation_granted"]:
        raise RuntimeError("One-shot intervention did not grant the sensor")
    effect_b = b["rdao"]["observation_effect"]
    effect_c = c["rdao"]["observation_effect"]
    if not effect_b or not effect_c:
        raise RuntimeError("Missing authorized sensor memory effect")
    fields = (
        "memory_before", "memory_after", "received_observation_values",
        "memory_changed_cell_count", "visible_cell_count",
    )
    for name in fields:
        if effect_b[name] != effect_c[name]:
            raise RuntimeError(f"Forced versus footprint same-pose memory mismatch: {name}")
    # Each frame's top-level position and heading are POST-action.
    # Observations occur BEFORE selected navigation, so compare the
    # pre-action public pose recorded in RDAO diagnostics instead.
    for name in ("position", "heading_yaw"):
        before_value = a["rdao"][name]
        if (before_value != b["rdao"][name]
                or before_value != c["rdao"][name]):
            raise RuntimeError(
                f"Intervention changes pre-observation {name}")
    return {
        "changed_cells": int(effect_c["memory_changed_cell_count"]),
        "visible_cells": int(effect_c["visible_cell_count"]),
        "first_step_action_matches_footprint": c["action"] == b["action"],
        "post_update_route_matches_footprint":
            effect_c.get("route_after") == effect_b.get("route_after"),
    }


def selected_targets(rows, original, footprint, *, max_cases=None):
    selected = []
    for world, schedule in TARGETS:
        key = (IDENTITY+world, schedule, 42)
        if key not in rows or key not in original or key not in footprint:
            raise RuntimeError(f"Missing originally saved target: {key}")
        target, old, new = first_sensing_delta(original[key], footprint[key])
        if old or not new:
            raise RuntimeError(f"First footprint observation mismatch is not added sensing: {key}")
        logged = rows[key]["first_changed_observation_step"]
        if target != int(logged):
            raise RuntimeError(f"Saved first divergence differs: {key}")
        if not 1 <= target < 80:
            raise RuntimeError("Invalid first-divergence intervention step")
        selected.append((key, target))
    if max_cases is not None:
        selected = selected[:max_cases]
    return selected


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--max-cases", type=int, default=None,
                        help="First N of the nine predefined fit cases; omit for all")
    args = parser.parse_args()
    if args.max_cases is not None and args.max_cases < 1:
        parser.error("--max-cases must be positive")
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite: {args.output}")

    source_hashes = {str(p.relative_to(ROOT)): _sha(p) for p in SOURCE_FILES}
    original_rows = _load_csv(PRIMARY / "primary_episodes.csv")
    baseline_index = {_key(row): row for row in original_rows}
    original = _read_saved_traces()
    footprint = read_footprint_traces(FOOTPRINT / "visibility_online_traces.jsonl.gz")
    online_rows = _load_csv(FOOTPRINT / "paired_visibility_online.csv")
    online = {_key(row): row for row in online_rows}
    if (len(original_rows) != 72 or len(baseline_index) != 72
            or len(online_rows) != 72 or len(online) != 72
            or set(original) != set(baseline_index)
            or set(online) != set(footprint)
            or set(online) != set(original)):
        raise RuntimeError("Saved online footprint and frozen RDAO cases differ")
    forensic_report = json.loads((FORENSICS / "summary.json").read_text())
    if forensic_report["episodes"] != 72 or (
        forensic_report["source_hashes"][
            str((FOOTPRINT / "visibility_online_traces.jsonl.gz").relative_to(ROOT))]
            != _sha(FOOTPRINT / "visibility_online_traces.jsonl.gz")):
        raise RuntimeError("Saved forensic/footprint evidence fingerprint differs")
    targets = selected_targets(online, original, footprint,
                               max_cases=args.max_cases)
    admitted = {item["identity"]: item for item in navigation.admitted_worlds()}
    if len(admitted) != 36:
        raise RuntimeError("Expected frozen 36 fit worlds")
    preservation = navigation.verify_preserved_prefix()

    rows, saved_traces = [], []
    for ix, (key, step) in enumerate(targets, 1):
        world, schedule, seed = key
        payload = admitted[world]
        original_row, original_trace = evaluator._instrumented_case(
            payload, schedule, "rdao_v1")
        if evaluator._signature(original_row) != evaluator._signature(
                baseline_index[key]):
            raise RuntimeError("Original frozen result was not reproduced")
        _compare_trace(original[key], original_trace)
        _compare_trace(original_trace, footprint[key], before_step=step)
        original_metrics = _metrics(baseline_index[key])
        footprint_row = online[key]
        footprint_metrics = {
            "success": _bool(footprint_row["variant_success"]),
            "elapsed_steps": int(footprint_row["variant_elapsed_steps"]),
            "observations": int(footprint_row["variant_observations"]),
            "travel_distance_m": float(footprint_row["variant_travel_distance_m"]),
            "turns": int(footprint_row["variant_turns"]),
            "emergency_interventions": int(
                footprint_row["variant_emergency_interventions"]),
            "unwanted_contacts": int(footprint_row["variant_unwanted_contacts"]),
        }
        for mode in ("extra", "swap"):
            observed_row, observed_trace = _run_with_intervention(
                payload, schedule, step, mode)
            _compare_trace(original_trace, observed_trace, before_step=step)
            frame = next(f for f in observed_trace["steps"]
                         if int(f["step"]) == step)
            if not (frame.get("rdao", {}).get("intervention_forced")
                    and frame["observation_granted"]):
                raise RuntimeError("One-shot original RDAO did not grant requested scan")
            scan = intervention_matches_first_footprint_scan(
                original[key], footprint[key], observed_trace, step)
            met = _metrics(observed_row)
            if (met["observations"] > 20 or
                    int(observed_row.get("g1_unselected_action_shield_queries", 0)) != 0 or
                    not _bool(observed_row["g1_shield_query_count_valid"])):
                raise RuntimeError("Intervention violated 20-budget or shield-query invariant")
            # Contact outcomes are empirical safety measurements, not file
            # integrity failures: retain/report any regression rather than
            # silently excluding the candidate run. No rollout is promoted.
            suppressed = [f["step"] for f in observed_trace["steps"] if
                          f.get("rdao", {}).get("intervention_suppressed")]
            if ((mode == "extra" and suppressed)
                    or (mode == "swap" and len(suppressed) > 1)):
                raise RuntimeError("Unexpected post-target observation suppression")
            first_later_sense, first_later_motion = first_differences(
                footprint[key], observed_trace)
            if first_later_sense is not None and first_later_sense < step:
                raise RuntimeError("Forced sensing diverged from Footprint before target")
            if first_later_motion is not None and first_later_motion < step:
                raise RuntimeError("Forced action diverged from Footprint before target")
            record = {
                "world_identity": world, "schedule": schedule, "seed": seed,
                "first_added_footprint_observation_step": step,
                "intervention": mode,
                "original_success": original_metrics["success"],
                "footprint_success": footprint_metrics["success"],
                "forced_success": met["success"],
                "original_steps_h80": original_metrics["elapsed_steps"],
                "footprint_steps_h80": footprint_metrics["elapsed_steps"],
                "forced_steps_h80": met["elapsed_steps"],
                "original_distance_m": original_metrics["travel_distance_m"],
                "footprint_distance_m": footprint_metrics["travel_distance_m"],
                "forced_distance_m": met["travel_distance_m"],
                "original_observations": original_metrics["observations"],
                "footprint_observations": footprint_metrics["observations"],
                "forced_observations": met["observations"],
                "original_turns": original_metrics["turns"],
                "footprint_turns": footprint_metrics["turns"],
                "forced_turns": met["turns"],
                "original_emergency_interventions":
                    original_metrics["emergency_interventions"],
                "footprint_emergency_interventions":
                    footprint_metrics["emergency_interventions"],
                "forced_emergency_interventions":
                    met["emergency_interventions"],
                "forced_unwanted_contacts": met["unwanted_contacts"],
                "forced_first_motion_difference_from_original":
                    _first_difference(original[key], observed_trace),
                "footprint_first_motion_difference_from_original":
                    _first_difference(original[key], footprint[key]),
                "forced_first_action_matches_footprint":
                    scan["first_step_action_matches_footprint"],
                "forced_vs_footprint_first_later_sensing_difference_step":
                    first_later_sense if first_later_sense is not None else "",
                "forced_vs_footprint_first_motion_difference_step":
                    first_later_motion if first_later_motion is not None else "",
                "forced_new_route_matches_footprint":
                    scan["post_update_route_matches_footprint"],
                "first_forced_scan_changed_cells": scan["changed_cells"],
                "first_forced_scan_visible_cells": scan["visible_cells"],
                "suppressed_next_step": suppressed[0] if suppressed else "",
                "swap_completed": mode == "swap" and len(suppressed) == 1,
                "exact_original_dose_match":
                    met["observations"] == original_metrics["observations"],
                "exact_footprint_dose_match":
                    met["observations"] == footprint_metrics["observations"],
                "forced_observation_steps":
                    json.dumps(_saved_observation_steps(observed_trace)),
                "footprint_observation_steps":
                    json.dumps(_saved_observation_steps(footprint[key])),
            }
            rows.append(record)
            saved_traces.append({
                "key": list(key), "step": step, "intervention": mode,
                "scan_exactly_matches_footprint": True,
                "metrics": met, "trace": observed_trace,
            })
        print(f"Completed {ix}/{len(targets)}: {world} schedule {schedule}"
              f" first added scan step {step}", flush=True)

    if navigation.verify_preserved_prefix() != preservation:
        raise RuntimeError("Protected Phase1.5 manifest changed")
    if {str(p.relative_to(ROOT)): _sha(p) for p in SOURCE_FILES} != source_hashes:
        raise RuntimeError("Frozen input changed during intervention")
    if len(rows) != 2 * len(targets):
        raise RuntimeError("Missing forced control arm")
    args.output.mkdir(parents=True)
    _write_csv(args.output / "first_sensing_causal_comparison.csv", rows)
    with gzip.open(args.output / "first_sensing_causal_traces.jsonl.gz",
                   "wt", encoding="utf-8") as stream:
        for record in saved_traces:
            stream.write(json.dumps(_jsonable(record), sort_keys=True,
                                    allow_nan=False) + "\n")
    summary = {
        "status": "RETROSPECTIVE_FIT_FIRST_SENSING_INTERVENTION_NOT_AN_ONLINE_POLICY",
        "world_schedule_cases": len(targets),
        "intervention_arms": dict(Counter(row["intervention"] for row in rows)),
        "source_hashes": source_hashes,
        "phase15_preservation": preservation,
        "forced_first_scan_equals_footprint_scan": True,
        "unwanted_contact_episodes": sum(
            row["forced_unwanted_contacts"] > 0 for row in rows),
        "total_unwanted_contact_pairs": sum(
            row["forced_unwanted_contacts"] for row in rows),
        "not_exact_observation_dose_matched_by_default": True,
        "limitations": [
            "The intervention step is selected with knowledge of the previous Footprint run, so this is causal diagnosis, not a deployable trigger.",
            "Forced-first-sensing reproduces the SAME physical scan, but the existing RDAO scheduler keeps original visibility scoring and original candidate-region cooldown.",
            "The Footprint intervention alters the entire online visibility model and may trigger many later additional observations; this study isolates its FIRST changed sensing decision only.",
            "The SWAP control suppresses the next naturally requested observation; final observation doses can still differ and are reported exactly.",
            "A first scan that matches does not imply the same future observed memory or equal later actions.",
            "Two schedules of the same maze are correlated and not independent random worlds.",
            "Horizon-80 failure is right-censored and cannot be compared as an uncensored arrival time.",
            "Selected-only shield, unchanged emergency sensor, no unwanted contacts and 20 memory observations are required.",
            "All results are previously used 36 development FIT worlds; no held-out suite is read or simulated.",
            "The G1 MuJoCo controller is kinematic-root navigation proxy, not demonstrated dynamic biped locomotion.",
        ],
    }
    (args.output / "summary.json").write_text(
        json.dumps(summary, sort_keys=True, indent=2, allow_nan=False)+"\n",
        encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "cases": len(targets),
        "unwanted_contact_episodes": summary["unwanted_contact_episodes"],
        "total_unwanted_contact_pairs": summary["total_unwanted_contact_pairs"],
        "high_interest": [
            {k: v for k, v in row.items() if k in (
                "world_identity", "schedule", "intervention",
                "first_added_footprint_observation_step",
                "original_success", "footprint_success", "forced_success",
                "original_steps_h80", "footprint_steps_h80", "forced_steps_h80",
                "original_observations", "footprint_observations",
                "forced_observations", "first_forced_scan_changed_cells",
                "forced_first_action_matches_footprint",
                "forced_new_route_matches_footprint",
                "suppressed_next_step", "swap_completed")}
            for row in rows
        ],
    }, indent=2, allow_nan=False))


if __name__ == "__main__":
    run()
