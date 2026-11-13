"""First 72-case fitted-development screen for opt-in RDAO v2.2 decision-protected quality.

Preserve the original v1, frozen footprint-only and frozen v2 outcomes.
v2.2 discounts current-view angular quality only when the existing public-map
A* counterfactual predicts no first-action or reachability change.

Reproduce each original v1 episode and semantic trajectory before
running the candidate. Read public fit36 worlds only, no shadow sensing,
no future world information, no action shield changes. Save all results
and report ALL unwanted contacts (never omit failures). Not held-out.
"""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

import evaluate_rdao_phase2 as evaluator
import phase2_mujoco_navigation as navigation
from evaluate_rdao_one_shot_interventions import (
    _bool, _compare_trace, _first_difference, _key, _load_csv, _metrics,
    _read_saved_traces, _sha, _write_csv,
)
from evaluate_rdao_footprint_visibility_online import (
    aggregate, first_observation_difference,
)
from evaluate_rdao_online_safe_gate_screen import _jsonable
from spatial_memory.rdao_v22_decision_protected import RDAOv22DecisionProtectedController
from spatial_memory.rdao_v2 import (
    MIN_RELATIVE_GAIN, MIN_ABSOLUTE_GAIN, DEFER_SCORE_MULTIPLIER,
)

PRIMARY = ROOT / "results/phase2_mujoco/rdao_v1_phase2_evaluation"
FOOTPRINT = ROOT / "results/phase2_mujoco/rdao_v1_footprint_visibility_online_fit72_v1"
V2 = ROOT / "results/phase2_mujoco/rdao_v2_viewpoint_fit72_v1"
DEFAULT_OUTPUT = ROOT / "results/phase2_mujoco/rdao_v22_decision_protected_fit72_v1"
PROTECTED = (
    PRIMARY / "primary_episodes.csv",
    PRIMARY / "primary_traces.jsonl.gz",
    PRIMARY / "experiment_manifest.json",
    FOOTPRINT / "paired_visibility_online.csv",
    FOOTPRINT / "summary.json",
    V2 / "paired_rdao_v2_viewpoint.csv",
    V2 / "summary.json",
)


def evaluate_v22(world, schedule):
    original = evaluator.RDAOController
    evaluator.RDAOController = RDAOv22DecisionProtectedController
    try:
        return evaluator._instrumented_case(world, schedule, "rdao_v1")
    finally:
        evaluator.RDAOController = original


def compare_saved(rows, saved, name):
    """Compare same episode IDs, including non-success and H80 censoring."""
    contrasts = []
    for row in rows:
        key = (row["world_identity"], row["schedule"], row["seed"])
        previous = saved.get(key)
        if previous is None:
            raise RuntimeError(f"Missing saved {name} control {key}")
        common = {
            "world_identity": row["world_identity"],
            "schedule": row["schedule"],
            "seed": row["seed"],
            "reference": name,
            "reference_success": _bool(previous["variant_success"]),
            "candidate_success": row["variant_success"],
            "reference_observations": int(previous["variant_observations"]),
            "candidate_observations": row["variant_observations"],
            "reference_steps_h80": int(previous["variant_elapsed_steps"]),
            "candidate_steps_h80": row["variant_elapsed_steps"],
            "reference_distance_m": float(previous["variant_travel_distance_m"]),
            "candidate_distance_m": row["variant_travel_distance_m"],
            "reference_unwanted_contacts": int(
                previous["variant_unwanted_contacts"]),
            "candidate_unwanted_contacts": row["variant_unwanted_contacts"],
        }
        common["delta_observations"] = (
            common["candidate_observations"]-common["reference_observations"])
        common["delta_steps_h80"] = (
            common["candidate_steps_h80"]-common["reference_steps_h80"])
        common["delta_distance_m"] = (
            common["candidate_distance_m"]-common["reference_distance_m"])
        contrasts.append(common)
    common_success = [
        x for x in contrasts if x["reference_success"] and x["candidate_success"]]
    return {
        "reference": name,
        "episodes": len(contrasts),
        "reference_successes": sum(x["reference_success"] for x in contrasts),
        "candidate_successes": sum(x["candidate_success"] for x in contrasts),
        "rescues": sum(not x["reference_success"] and x["candidate_success"]
                       for x in contrasts),
        "harms": sum(x["reference_success"] and not x["candidate_success"]
                     for x in contrasts),
        "mean_reference_observations": statistics.mean(
            x["reference_observations"] for x in contrasts),
        "mean_candidate_observations": statistics.mean(
            x["candidate_observations"] for x in contrasts),
        "mean_reference_steps_h80": statistics.mean(
            x["reference_steps_h80"] for x in contrasts),
        "mean_candidate_steps_h80": statistics.mean(
            x["candidate_steps_h80"] for x in contrasts),
        "mean_reference_distance_m": statistics.mean(
            x["reference_distance_m"] for x in contrasts),
        "mean_candidate_distance_m": statistics.mean(
            x["candidate_distance_m"] for x in contrasts),
        "total_delta_observations": sum(
            x["delta_observations"] for x in contrasts),
        "total_delta_steps_h80": sum(
            x["delta_steps_h80"] for x in contrasts),
        "total_delta_distance_m": sum(
            x["delta_distance_m"] for x in contrasts),
        "common_success": {
            "episodes": len(common_success),
            "step_better": sum(x["delta_steps_h80"] < 0
                               for x in common_success),
            "step_same": sum(x["delta_steps_h80"] == 0
                             for x in common_success),
            "step_worse": sum(x["delta_steps_h80"] > 0
                              for x in common_success),
            "distance_better": sum(x["delta_distance_m"] < 0
                                   for x in common_success),
            "distance_same": sum(x["delta_distance_m"] == 0
                                 for x in common_success),
            "distance_worse": sum(x["delta_distance_m"] > 0
                                  for x in common_success),
        },
    }, contrasts


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-cases", type=int, default=None,
                        help="First N episodes only, for a separate pilot directory")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.max_cases is not None and args.max_cases < 1:
        parser.error("--max-cases must be positive")
    if args.output.exists():
        raise FileExistsError(f"Will not overwrite evidence at {args.output}")

    original_rows = _load_csv(PRIMARY / "primary_episodes.csv")
    original_index = {_key(x): x for x in original_rows}
    original_traces = _read_saved_traces()
    footprint_rows = _load_csv(FOOTPRINT / "paired_visibility_online.csv")
    footprint_index = {_key(x): x for x in footprint_rows}
    v2_rows = _load_csv(V2 / "paired_rdao_v2_viewpoint.csv")
    v2_index = {_key(x): x for x in v2_rows}
    if (len(original_rows) != 72 or len(original_index) != 72
            or len(original_traces) != 72
            or len(footprint_rows) != 72 or len(footprint_index) != 72
            or len(v2_rows) != 72 or len(v2_index) != 72
            or set(original_index) != set(original_traces)
            or set(original_index) != set(v2_index)
            or set(original_index) != set(footprint_index)):
        raise RuntimeError("Frozen 72-case comparisons are missing or disagree")
    preserved = navigation.verify_preserved_prefix()
    fingerprints = {str(p.relative_to(ROOT)): _sha(p) for p in PROTECTED}
    worlds = {x["identity"]: x for x in navigation.admitted_worlds()}
    if len(worlds) != 36 or set(worlds) != {k[0] for k in original_index}:
        raise RuntimeError("Cannot verify original 36 FIT worlds")

    selected = sorted(original_index, key=lambda k: (k[0], k[1], k[2]))
    if args.max_cases is not None:
        selected = selected[:args.max_cases]
    results, saved_traces = [], []
    for ix, key in enumerate(selected, 1):
        world, schedule, seed = key
        if seed != 42:
            raise RuntimeError("Unexpected seed")
        original, original_trace = evaluator._instrumented_case(
            worlds[world], schedule, "rdao_v1")
        if evaluator._signature(original) != evaluator._signature(
                original_index[key]):
            raise RuntimeError(f"Original v1 metric mismatch: {key}")
        _compare_trace(original_traces[key], original_trace)
        candidate, trace = evaluate_v22(worlds[world], schedule)
        prev, now = _metrics(original_index[key]), _metrics(candidate)
        if (now["observations"] > 20 or
                int(candidate.get("g1_unselected_action_shield_queries", 0)) != 0 or
                not _bool(candidate["g1_shield_query_count_valid"])):
            raise RuntimeError(f"Observation budget or shield query violation: {key}")
        if sum(bool(f["observation_granted"]) for f in trace["steps"]) != (
                now["observations"]):
            raise RuntimeError("Realized candidate observation count mismatch")
        if any((f.get("rdao") or {}).get("observation_effect") is not None
               and not f["observation_granted"] for f in trace["steps"]):
            raise RuntimeError("Unauthorized memory update in candidate")
        obs_change = first_observation_difference(original_trace, trace)
        motion_change = _first_difference(original_trace, trace)
        if obs_change is None:
            _compare_trace(original_trace, trace)
        else:
            _compare_trace(original_trace, trace, before_step=obs_change)
            if motion_change is not None and motion_change < obs_change:
                raise RuntimeError("Action differed BEFORE first sensing change")
        rec = {
            "world_identity": world, "schedule": schedule, "seed": seed,
            "first_changed_observation_step":
                obs_change if obs_change is not None else "",
            "first_changed_action_or_pose_step":
                motion_change if motion_change is not None else "",
            "delta_observations": now["observations"]-prev["observations"],
            "delta_steps": now["elapsed_steps"]-prev["elapsed_steps"],
            "delta_distance_m":
                now["travel_distance_m"]-prev["travel_distance_m"],
        }
        for label, met in (("original", prev), ("variant", now)):
            rec.update({f"{label}_{k}": v for k, v in met.items()})
        rec["v22_protected_region_scores"] = sum(
            bool(region.get("v22_protected_immediate_decision"))
            for frame in trace["steps"]
            for region in (frame.get("rdao") or {}).get("candidate_regions") or [])
        rec["v22_discounted_region_scores"] = sum(
            region.get("v22_current_view_discount", 1.0) < 1.0
            for frame in trace["steps"]
            for region in (frame.get("rdao") or {}).get("candidate_regions") or [])
        rec["v22_deferred_regions"] = sum(
            bool(region.get("v2_deferred"))
            for f in trace["steps"]
            for region in (f.get("rdao") or {}).get("candidate_regions") or [])
        rec["v22_steps_with_deferral"] = sum(
            any(region.get("v2_deferred")
                for region in (f.get("rdao") or {}).get("candidate_regions") or [])
            for f in trace["steps"])
        results.append(rec)
        saved_traces.append({
            "key": list(key),
            "variant": "rdao_v22_current_quality",
            "metrics": now, "trace": trace,
        })
        print(f"Completed {ix}/{len(selected)}: {world} schedule {schedule}",
              flush=True)

    if navigation.verify_preserved_prefix() != preserved:
        raise RuntimeError("Phase1.5 preservation manifest was modified")
    if {str(p.relative_to(ROOT)): _sha(p) for p in PROTECTED} != fingerprints:
        raise RuntimeError("Frozen source files changed during run")
    v1_summary = aggregate(results)
    footprint_summary, fp_contrast = compare_saved(
        results, footprint_index, "footprint_only")
    v2_summary, v2_contrast = compare_saved(
        results, v2_index, "v2_viewpoint")
    summary = {
        "status": "RDAO_V22_CURRENT_VIEW_QUALITY_DEV_FIT_NOT_HELD_OUT",
        "variant": "RDAOv22DecisionProtectedController",
        "hypothesis": "Discount edge observations only for noncritical immediate route counterfactuals; protect all candidate regions whose free/occupied states change first action or reachability",
        "prespecified_v2_unchanged": True,
        "v22_relative_to_v1": v1_summary,
        "v22_relative_to_footprint": footprint_summary,
        "v22_relative_to_v2": v2_summary,
        "v22_protected_region_scores": sum(
            x["v22_protected_region_scores"] for x in results),
        "v22_discounted_region_scores": sum(
            x["v22_discounted_region_scores"] for x in results),
        "v22_deferred_region_scores": sum(
            x["v22_deferred_regions"] for x in results),
        "v22_steps_with_deferral": sum(
            x["v22_steps_with_deferral"] for x in results),
        "v22_unwanted_contact_pairs": v1_summary["variant_contacts"],
        "parameters": {
            "current_view_visibility": "v2 footprint visibility for protected decision-changing regions; angular quality discount only for noncritical regions",
            "next_view_visibility": "footprint_extent * angular_coverage",
            "next_view_min_relative_gain": MIN_RELATIVE_GAIN,
            "next_view_min_absolute_gain": MIN_ABSOLUTE_GAIN,
            "next_view_score_multiplier": DEFER_SCORE_MULTIPLIER,
            "original_v1_score_threshold_and_budget_price": True,
            "no_step_world_allowlist": True,
            "max_memory_observations": 20,
        },
        "source_hashes": fingerprints,
        "phase15_preservation": preserved,
        "limitations": [
            "Original and alternative results use repeatedly inspected fit36 world layouts, not independent holdout.",
            "Only noncritical current-view candidate scoring changes; G1 physical actions and shield remain untouched.",
            "Angular overlap quality is a geometric heuristic, not an actual observation return probability.",
            "No guarantee the next hypothetical move or turn passes true physical action shield.",
            "Reducing observations can decrease goal success; both successes and harmed successes must be counted.",
            "H80-censored steps do not measure time-to-goal for failures.",
            "Two pedestrian schedules per maze are correlated.",
            "v2.1 uses a single-threaded module-level visibility hook; not for concurrent use.",
            "No dynamic walking hardware or full articulated biped motion is evaluated.",
        ],
    }
    args.output.mkdir(parents=True)
    _write_csv(args.output/"paired_v22_vs_v1.csv", results)
    _write_csv(args.output/"paired_v22_vs_footprint.csv", fp_contrast)
    _write_csv(args.output/"paired_v22_vs_v2.csv", v2_contrast)
    with gzip.open(args.output/"v22_traces.jsonl.gz",
                   "wt", encoding="utf-8") as f:
        for item in saved_traces:
            f.write(json.dumps(_jsonable(item), sort_keys=True,
                               allow_nan=False)+"\n")
    (args.output/"summary.json").write_text(
        json.dumps(summary, sort_keys=True, indent=2,
                   allow_nan=False)+"\n", encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "v1_comparison": v1_summary,
        "v2_comparison": v2_summary,
        "footprint_comparison": footprint_summary,
        "unwanted_contacts": v1_summary["variant_contacts"],
    }, sort_keys=True, indent=2, allow_nan=False))


if __name__ == "__main__":
    run()
