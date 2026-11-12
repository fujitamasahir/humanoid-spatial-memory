"""Paired ONLINE Phase 2 development-screen for RDAO footprint visibility.

Changes exactly ONE feature of RDAO v1: public remembered-map predicted_cell_visibility
used INSIDE the existing RDAO _regions() candidate scoring. The existing RDAO
route-relevance, timing, cooldown, scoring threshold, max-20 observation budget,
pedestrian-aware G1 planner, independent emergency safety controller, selected-
action actual-geometry collision shield, MuJoCo model and sensor do NOT change.

Variant uses the footprint-aware ANGULAR/RANGE feasibility predictor from the
separately committed diagnostic. Its center-line public-map attenuation is
unchanged. The entire policy still uses only decision-time public inputs, not
the shadow sensor, latent truth, episode identity, step allowlists, or labels.

Reproduce frozen original row+semantic trace for each candidate case BEFORE
intervention. Single-threaded monkeypatch is scoped to the run and restored
unconditionally; no production source or protected results are modified.

All 36 admitted fit worlds / two correlated schedules are DEVELOPMENT data, NOT
held-out. The intervention is exploratory and should not be promoted before an
independent, preregistered final evaluation.
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

import evaluate_rdao_phase2 as evaluator
import phase2_mujoco_navigation as navigation
import spatial_memory.rdao as rdao_module
from analyze_rdao_visibility_extent_audit import footprint_visibility
from evaluate_rdao_one_shot_interventions import (
    _bool, _compare_trace, _first_difference, _key,
    _load_csv, _metrics, _read_saved_traces, _sha, _write_csv,
)
from evaluate_rdao_online_safe_gate_screen import _jsonable

PRIMARY = ROOT / "results/phase2_mujoco/rdao_v1_phase2_evaluation"
VISIBILITY = ROOT / "results/phase2_mujoco/rdao_v1_visibility_extent_audit_v1"
DEFAULT_OUTPUT = ROOT / "results/phase2_mujoco/rdao_v1_footprint_visibility_online_fit72_v1"
SOURCE_FILES = (
    PRIMARY / "primary_episodes.csv",
    PRIMARY / "primary_traces.jsonl.gz",
    PRIMARY / "experiment_manifest.json",
    VISIBILITY / "summary.json",
)


def footprint_predictor(grid, position, yaw, cell, *,
                        cell_size_m, range_m, horizontal_fov_deg,
                        ray_count, unknown_open_probability=.5):
    """Signature-matched opt-in alternative used by _regions on public memory."""
    return footprint_visibility(
        grid, position, yaw, cell, cell_size_m=cell_size_m,
        range_m=range_m, fov_deg=horizontal_fov_deg, ray_count=ray_count,
        unknown_open=unknown_open_probability)


def evaluate_footprint(payload, schedule):
    """Run one experimental episode with model function restored on failure."""
    legacy = rdao_module.predicted_cell_visibility
    if legacy is footprint_predictor:
        raise RuntimeError("Original RDAO predictor was already patched")
    rdao_module.predicted_cell_visibility = footprint_predictor
    try:
        return evaluator._instrumented_case(payload, schedule, "rdao_v1")
    finally:
        rdao_module.predicted_cell_visibility = legacy


def first_observation_difference(original, updated):
    old = {int(f["step"]): f for f in original["steps"]}
    new = {int(f["step"]): f for f in updated["steps"]}
    for step in sorted(set(old) | set(new)):
        a, c = old.get(step), new.get(step)
        if a is None or c is None:
            return step
        if bool(a["observation_granted"]) != bool(c["observation_granted"]):
            return step
    return None


def aggregate(records):
    if not records:
        raise ValueError("Cannot aggregate zero episodes")
    n = len(records)
    orig_success = [r for r in records if r["original_success"]]
    new_success = [r for r in records if r["variant_success"]]
    rescues = [r for r in records if not r["original_success"] and r["variant_success"]]
    harms = [r for r in records if r["original_success"] and not r["variant_success"]]
    common = [r for r in records if r["original_success"] and r["variant_success"]]
    return {
        "episodes": n,
        "worlds": len({r["world_identity"] for r in records}),
        "original_successes": len(orig_success),
        "variant_successes": len(new_success),
        "rescued_failures": len(rescues),
        "harmed_successes": len(harms),
        "rescue_worlds": sorted({r["world_identity"] for r in rescues}),
        "harm_worlds": sorted({r["world_identity"] for r in harms}),
        "variant_contacts": sum(r["variant_unwanted_contacts"] for r in records),
        "episodes_changed_observation_schedule": sum(
            r["first_changed_observation_step"] != "" for r in records),
        "episodes_changed_executed_action_or_pose": sum(
            r["first_changed_action_or_pose_step"] != "" for r in records),
        "mean_original_observations": statistics.mean(
            r["original_observations"] for r in records),
        "mean_variant_observations": statistics.mean(
            r["variant_observations"] for r in records),
        "mean_original_censored_steps": statistics.mean(
            r["original_elapsed_steps"] for r in records),
        "mean_variant_censored_steps": statistics.mean(
            r["variant_elapsed_steps"] for r in records),
        "mean_original_distance_m": statistics.mean(
            r["original_travel_distance_m"] for r in records),
        "mean_variant_distance_m": statistics.mean(
            r["variant_travel_distance_m"] for r in records),
        "mean_original_scheduler_ms": statistics.mean(
            r["original_scheduler_ms"] for r in records),
        "mean_variant_scheduler_ms": statistics.mean(
            r["variant_scheduler_ms"] for r in records),
        "mean_original_steps_successes_only": (
            statistics.mean(r["original_elapsed_steps"] for r in orig_success)
            if orig_success else None),
        "mean_variant_steps_successes_only": (
            statistics.mean(r["variant_elapsed_steps"] for r in new_success)
            if new_success else None),
        "paired_common_success": {
            "episodes": len(common),
            "steps_better": sum(r["delta_steps"] < 0 for r in common),
            "steps_same": sum(r["delta_steps"] == 0 for r in common),
            "steps_worse": sum(r["delta_steps"] > 0 for r in common),
            "distance_better": sum(r["delta_distance_m"] < -1e-8 for r in common),
            "distance_same": sum(abs(r["delta_distance_m"]) <= 1e-8 for r in common),
            "distance_worse": sum(r["delta_distance_m"] > 1e-8 for r in common),
            "total_delta_steps": sum(r["delta_steps"] for r in common),
            "total_delta_distance_m": sum(r["delta_distance_m"] for r in common),
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--world", default=None,
                        help="Optional exact admitted world suffix, for development pilot")
    parser.add_argument("--max-cases", type=int, default=None,
                        help="Run first N cases in frozen identity order")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.max_cases is not None and args.max_cases < 1:
        parser.error("--max-cases must be positive")
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite existing output: {args.output}")

    originals = {_key(row): row
                 for row in _load_csv(PRIMARY / "primary_episodes.csv")}
    frozen_traces = _read_saved_traces()
    if len(originals) != 72 or set(originals) != set(frozen_traces):
        raise RuntimeError("Frozen original 72-case evidence unavailable")

    reference = json.loads((VISIBILITY / "summary.json").read_text())
    saved_primary_hash = reference["source_sha256"][
        "results/phase2_mujoco/rdao_v1_phase2_evaluation/primary_traces.jsonl.gz"]
    if _sha(PRIMARY / "primary_traces.jsonl.gz") != saved_primary_hash:
        raise RuntimeError("Frozen primary source differs from verified feasibility audit")
    if reference["naturally_authorized_noninitial_observations"] != 584:
        raise RuntimeError("Expected 584 verified observational visibility labels")
    if reference["episodes"] != 72:
        raise RuntimeError("Expected full fit visibility audit, not a smoke run")

    protected = {str(p.relative_to(ROOT)): _sha(p) for p in SOURCE_FILES}
    preservation = navigation.verify_preserved_prefix()
    worlds = {world["identity"]: world for world in navigation.admitted_worlds()}
    if len(worlds) != 36 or set(worlds) != {k[0] for k in originals}:
        raise RuntimeError("Admitted 36 Phase 2 fit worlds differ from primary")

    keys = sorted(originals, key=lambda k: (k[0], k[1], k[2]))
    if args.world:
        keys = [k for k in keys if k[0].endswith(args.world)]
    if args.max_cases is not None:
        keys = keys[:args.max_cases]
    if not keys:
        raise RuntimeError("No selected admitted fit-world episodes")

    comparison, trace_records = [], []
    for idx, key in enumerate(keys, 1):
        identity, schedule, seed = key
        if seed != 42:
            raise RuntimeError("Unexpected seed")
        if rdao_module.predicted_cell_visibility is footprint_predictor:
            raise RuntimeError("Visibility predictor was not restored")

        baseline, baseline_trace = evaluator._instrumented_case(
            worlds[identity], schedule, "rdao_v1")
        if evaluator._signature(baseline) != evaluator._signature(originals[key]):
            raise RuntimeError(f"Frozen original outcome not reproduced: {key}")
        _compare_trace(frozen_traces[key], baseline_trace)

        variant, variant_trace = evaluate_footprint(worlds[identity], schedule)
        orig = _metrics(originals[key])
        new = _metrics(variant)
        if (new["observations"] > 20 or
                new["unwanted_contacts"] != 0 or
                int(variant.get("g1_unselected_action_shield_queries", 0)) != 0 or
                not _bool(variant["g1_shield_query_count_valid"])):
            raise RuntimeError(f"Visibility variant violated sensing/safety invariant: {key}")
        if sum(bool(frame["observation_granted"]) for frame in variant_trace["steps"]) != new["observations"]:
            raise RuntimeError("Actual variant observation count mismatch")
        if any(frame.get("rdao", {}).get("observation_effect") is not None
               and not frame.get("observation_granted")
               for frame in variant_trace["steps"]):
            raise RuntimeError("Unapproved RDAO memory update")

        obs_diff = first_observation_difference(baseline_trace, variant_trace)
        action_diff = _first_difference(baseline_trace, variant_trace)
        if obs_diff is None:
            # The policy modification ONLY scores visibility. With identical
            # observations, the memory/action trajectory should be identical.
            _compare_trace(baseline_trace, variant_trace)
        else:
            # The policy may diverge after the new sensing decision, but not
            # before the first newly changed observation decision.
            _compare_trace(baseline_trace, variant_trace,
                           before_step=obs_diff)
            if action_diff is not None and action_diff < obs_diff:
                raise RuntimeError("Changed navigation before sensing diverged")

        report = {
            "world_identity": identity, "schedule": schedule, "seed": seed,
            "first_changed_observation_step": obs_diff if obs_diff is not None else "",
            "first_changed_action_or_pose_step": action_diff if action_diff is not None else "",
            "delta_steps": new["elapsed_steps"] - orig["elapsed_steps"],
            "delta_observations": new["observations"] - orig["observations"],
            "delta_distance_m": new["travel_distance_m"] - orig["travel_distance_m"],
        }
        for prefix, value in (("original", orig), ("variant", new)):
            report.update({f"{prefix}_{name}": v for name, v in value.items()})
        comparison.append(report)
        trace_records.append({
            "key": list(key), "variant": "rdao_v1_footprint_visibility",
            "metrics": new, "first_changed_observation_step": obs_diff,
            "first_changed_action_or_pose_step": action_diff,
            "trace": variant_trace,
        })
        print(f"Completed {idx}/{len(keys)}: {identity} schedule {schedule}", flush=True)

    if navigation.verify_preserved_prefix() != preservation:
        raise RuntimeError("Protected Phase 1.5 preservation changed")
    if {str(p.relative_to(ROOT)): _sha(p) for p in SOURCE_FILES} != protected:
        raise RuntimeError("Protected comparison input changed")

    results = aggregate(comparison)
    summary = {
        "status": "POSTHOC_SELECTED_FIT_VISIBILITY_ONLINE_SCREEN_NOT_HELD_OUT",
        "condition": "footprint_angular_radial_feasibility_in_existing_RDAO_route_regions",
        "changed": "only RDAO predicted_cell_visibility function, no gate",
        "same_route_relevance": True,
        "same_scheduler_threshold": True,
        "same_observation_budget_20": True,
        "same_emergency_and_selected_action_shield": True,
        "source_hashes": protected,
        "phase15_preservation": preservation,
        "aggregates": results,
        "limitations": [
            "This candidate was chosen after examining fit-world sensor and navigation results, so completion is descriptive development screening.",
            "Each world has two correlated pedestrian schedules; the number of independent world layouts is smaller than the episode count.",
            "The offline label is sensor-measured cell feasibility on naturally selected observations, not calibrated prospective observation information.",
            "The candidate changes region visibility scores and therefore may change observation schedule, total dose, paths and measured latency.",
            "A posthoc measured positive on an already observed sample is not evidence that the new policy will observe the same cells prospectively.",
            "Zero unwanted contact is required, but success and observation efficiency must also beat original RDAO and simple Periodic/Age baselines.",
            "Primary G1 is a MuJoCo kinematic-root navigation proxy, not walking dynamics.",
            "No held-out or new independently sampled worlds were used.",
        ],
    }
    args.output.mkdir(parents=True)
    _write_csv(args.output / "paired_visibility_online.csv", comparison)
    with gzip.open(args.output / "visibility_online_traces.jsonl.gz",
                   "wt", encoding="utf-8") as stream:
        for record in trace_records:
            stream.write(json.dumps(_jsonable(record), allow_nan=False,
                                    sort_keys=True) + "\n")
    (args.output / "summary.json").write_text(
        json.dumps(summary, allow_nan=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8")
    print(json.dumps({
        "output": str(args.output), "aggregates": results,
    }, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
