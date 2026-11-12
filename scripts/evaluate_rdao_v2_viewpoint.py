"""Matched 72-episode Phase 2 online development screen of experimental RDAO v2.

RDAO v2 (next-viewpoint observation competition) is an opt-in controller,
NOT a proven replacement for RDAO v1. One frozen hypothesis, selected from
public-route opportunity reasoning without fit-world/step allowlists.

Compare to original 57/72 RDAO v1 and to already saved footprint-only
59/72; ordinary Periodic and Age each reached 66/72 on these FIT cases.
Report goal completions, paired common-success steps/distance, contacts,
observation dose, actual action divergence and computation cost.
Original RDAO episode is re-simulated and reproduced before each v2 case.
Do not read withheld/evaluation-only world data or inspect shadow sensors.
No controller in the frozen baseline repo is altered.
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
from spatial_memory.rdao_v2 import (
    RDAOv2ViewpointController, MIN_RELATIVE_GAIN,
    MIN_ABSOLUTE_GAIN, DEFER_SCORE_MULTIPLIER,
)

BASE = ROOT / "results/phase2_mujoco/rdao_v1_phase2_evaluation"
FOOTPRINT = ROOT / "results/phase2_mujoco/rdao_v1_footprint_visibility_online_fit72_v1"
DEFAULT_OUTPUT = ROOT / "results/phase2_mujoco/rdao_v2_viewpoint_fit72_v1"
PROTECTED = (
    BASE / "primary_episodes.csv",
    BASE / "primary_traces.jsonl.gz",
    BASE / "experiment_manifest.json",
    FOOTPRINT / "paired_visibility_online.csv",
    FOOTPRINT / "summary.json",
)


def evaluate_v2(payload, schedule):
    """Scoped evaluator controller replacement; no changes to its G1 backend."""
    original = evaluator.RDAOController
    evaluator.RDAOController = RDAOv2ViewpointController
    try:
        return evaluator._instrumented_case(payload, schedule, "rdao_v1")
    finally:
        evaluator.RDAOController = original


def disposition(original, candidate):
    if original and candidate:
        return "common_success"
    if not original and candidate:
        return "rescued"
    if original and not candidate:
        return "harmed"
    return "both_horizon_censored"


def compare_footprint(rows, previously_saved):
    """Descriptive paired outcome contrast, no extra simulator calls."""
    contrasts = []
    for item in rows:
        key = (item["world_identity"], item["schedule"], item["seed"])
        old = previously_saved.get(key)
        if old is None:
            raise ValueError(f"Missing previously saved Footprint episode: {key}")
        s = _bool(old["variant_success"])
        v = item["variant_success"]
        contrasts.append({
            "world_identity": item["world_identity"],
            "schedule": item["schedule"],
            "footprint_success": s,
            "v2_success": v,
            "footprint_observations": int(old["variant_observations"]),
            "v2_observations": item["variant_observations"],
            "footprint_steps_h80": int(old["variant_elapsed_steps"]),
            "v2_steps_h80": item["variant_elapsed_steps"],
            "footprint_distance_m": float(old["variant_travel_distance_m"]),
            "v2_distance_m": item["variant_travel_distance_m"],
            "footprint_unwanted_contacts":
                int(old["variant_unwanted_contacts"]),
            "v2_unwanted_contacts": item["variant_unwanted_contacts"],
            "outcome": disposition(s, v),
        })
    return {
        "footprint_successes": sum(r["footprint_success"] for r in contrasts),
        "v2_successes": sum(r["v2_success"] for r in contrasts),
        "v2_rescues_vs_footprint": sum(
            r["outcome"] == "rescued" for r in contrasts),
        "v2_harms_vs_footprint": sum(
            r["outcome"] == "harmed" for r in contrasts),
        "mean_footprint_observations": statistics.mean(
            r["footprint_observations"] for r in contrasts),
        "mean_v2_observations": statistics.mean(
            r["v2_observations"] for r in contrasts),
        "mean_footprint_censored_steps": statistics.mean(
            r["footprint_steps_h80"] for r in contrasts),
        "mean_v2_censored_steps": statistics.mean(
            r["v2_steps_h80"] for r in contrasts),
        "mean_footprint_distance_m": statistics.mean(
            r["footprint_distance_m"] for r in contrasts),
        "mean_v2_distance_m": statistics.mean(
            r["v2_distance_m"] for r in contrasts),
        "paired_common_success": {
            "episodes": len([
                r for r in contrasts
                if r["footprint_success"] and r["v2_success"]]),
            "step_better": sum(
                r["v2_steps_h80"] < r["footprint_steps_h80"]
                for r in contrasts if
                r["footprint_success"] and r["v2_success"]),
            "step_same": sum(
                r["v2_steps_h80"] == r["footprint_steps_h80"]
                for r in contrasts if
                r["footprint_success"] and r["v2_success"]),
            "step_worse": sum(
                r["v2_steps_h80"] > r["footprint_steps_h80"]
                for r in contrasts if
                r["footprint_success"] and r["v2_success"]),
        },
    }, contrasts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-cases", type=int, default=None,
                        help="First N frozen fit episodes for a smoke test")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.max_cases is not None and args.max_cases < 1:
        parser.error("--max-cases must be positive")
    if args.output.exists():
        raise FileExistsError(f"Never overwrite a saved run: {args.output}")

    saved_rows = _load_csv(BASE / "primary_episodes.csv")
    source = {_key(row): row for row in saved_rows}
    frozen_traces = _read_saved_traces()
    footprint_rows = _load_csv(FOOTPRINT / "paired_visibility_online.csv")
    footprint = {_key(row): row for row in footprint_rows}
    if (len(source) != 72 or len(saved_rows) != 72 or
            len(frozen_traces) != 72 or len(footprint) != 72 or
            len(footprint_rows) != 72 or set(source) != set(frozen_traces)
            or set(source) != set(footprint)):
        raise RuntimeError("Expected all 72 matched frozen source cases")
    hashes = {str(p.relative_to(ROOT)): _sha(p) for p in PROTECTED}
    preserved_prefix = navigation.verify_preserved_prefix()
    worlds = {world["identity"]: world for world in navigation.admitted_worlds()}
    if len(worlds) != 36 or {k[0] for k in source} != set(worlds):
        raise RuntimeError("Admitted FIT worlds differ from the frozen 36")

    selected = sorted(source, key=lambda key: (key[0], key[1], key[2]))
    if args.max_cases is not None:
        selected = selected[:args.max_cases]
    rows, traces = [], []
    for i, key in enumerate(selected, 1):
        world, schedule, seed = key
        if seed != 42:
            raise RuntimeError("Unexpected historical seed")
        baseline, original_trace = evaluator._instrumented_case(
            worlds[world], schedule, "rdao_v1")
        if evaluator._signature(baseline) != evaluator._signature(source[key]):
            raise RuntimeError(f"Original RDAO v1 not reproduced: {key}")
        _compare_trace(frozen_traces[key], original_trace)
        variant, trace = evaluate_v2(worlds[world], schedule)
        before, after = _metrics(source[key]), _metrics(variant)
        if (after["observations"] > 20 or
                int(variant.get("g1_unselected_action_shield_queries", 0)) != 0 or
                not _bool(variant["g1_shield_query_count_valid"])):
            raise RuntimeError(f"V2 observation cap/shield invariant violated: {key}")
        if sum(bool(f["observation_granted"]) for f in trace["steps"]) != after["observations"]:
            raise RuntimeError("Realized v2 observation count differs from saved trace")
        if any((f.get("rdao") or {}).get("observation_effect") is not None
               and not f["observation_granted"] for f in trace["steps"]):
            raise RuntimeError("V2 performed an unauthorized memory observation")
        change = first_observation_difference(original_trace, trace)
        action_change = _first_difference(original_trace, trace)
        if change is None:
            _compare_trace(original_trace, trace)
        else:
            _compare_trace(original_trace, trace, before_step=change)
            if action_change is not None and action_change < change:
                raise RuntimeError("V2 actions changed before first sensing difference")

        v2_deferred_regions = 0
        v2_deferred_steps = 0
        for f in trace["steps"]:
            diag = f.get("rdao") or {}
            n = sum(bool(item.get("v2_deferred"))
                    for item in diag.get("candidate_regions") or [])
            v2_deferred_regions += n
            v2_deferred_steps += int(n > 0)

        record = {
            "world_identity": world, "schedule": schedule, "seed": seed,
            "first_changed_observation_step":
                change if change is not None else "",
            "first_changed_action_or_pose_step":
                action_change if action_change is not None else "",
            "delta_steps": after["elapsed_steps"] - before["elapsed_steps"],
            "delta_observations": after["observations"] - before["observations"],
            "delta_distance_m":
                after["travel_distance_m"] - before["travel_distance_m"],
            "v2_deferred_candidate_region_scores": v2_deferred_regions,
            "v2_steps_with_deferred_region": v2_deferred_steps,
        }
        for label, metrics in (("original", before), ("variant", after)):
            record.update({f"{label}_{field}": value
                           for field, value in metrics.items()})
        rows.append(record)
        traces.append({
            "key": list(key), "variant": "rdao_v2_viewpoint",
            "metrics": after, "trace": trace,
        })
        print(f"Completed {i}/{len(selected)}: {world} schedule {schedule}",
              flush=True)

    if navigation.verify_preserved_prefix() != preserved_prefix:
        raise RuntimeError("Phase1.5 preservation changed")
    if {str(p.relative_to(ROOT)): _sha(p) for p in PROTECTED} != hashes:
        raise RuntimeError("Saved source changed while v2 ran")

    aggregates = aggregate(rows)
    footprint_result, footprint_contrasts = compare_footprint(rows, footprint)
    summary = {
        "status": "RDAO_V2_VIEWPOINT_DEV_FIT_SCREEN_NOT_DEPLOYED_NOT_HELD_OUT",
        "variant": "RDAOv2ViewpointController",
        "parameters": {
            "min_relative_next_visibility_gain": MIN_RELATIVE_GAIN,
            "min_absolute_next_visibility_gain": MIN_ABSOLUTE_GAIN,
            "score_multiplier_if_next_view_is_better": DEFER_SCORE_MULTIPLIER,
            "only_defer_move_into_known_free": True,
            "observation_cap": 20,
            "no_first_action_gate": True,
        },
        "episodes": len(rows), "worlds": len({x["world_identity"] for x in rows}),
        "original_and_v2": aggregates,
        "footprint_and_v2": footprint_result,
        "v2_unwanted_contact_pairs": aggregates["variant_contacts"],
        "v2_deferred_candidate_region_scores": sum(
            x["v2_deferred_candidate_region_scores"] for x in rows),
        "v2_steps_with_deferred_region": sum(
            x["v2_steps_with_deferred_region"] for x in rows),
        "source_hashes": hashes,
        "phase15_preservation": preserved_prefix,
        "limitations": [
            "The view-ahead rule and constants are an exploratory development hypothesis; do not tune on held-out worlds.",
            "The 36 FIT mazes were repeatedly examined, so these results are NOT independent generalization evidence.",
            "The next viewpoint is computed on public remembered cells only, not a shield-verified actual next pose.",
            "Deferring a scan does not guarantee the next scan is authorized, useful or still reachable.",
            "Footprint predicted-visibility score is an uncalibrated public-map feasibility estimate.",
            "Mean capped steps among failures are right-censored, not actual goal completion times.",
            "Two pedestrian schedules in one maze are correlated rather than independent world samples.",
            "The v2 controller is single-threaded because original v1 uses a module visibility function hook.",
            "Selected-action true-geometry shield and independent emergency ray sensor are unchanged.",
            "No dynamic walking or real Unitree G1 hardware has been evaluated.",
        ],
    }

    args.output.mkdir(parents=True)
    _write_csv(args.output / "paired_rdao_v2_viewpoint.csv", rows)
    _write_csv(args.output / "paired_footprint_vs_v2.csv", footprint_contrasts)
    with gzip.open(args.output / "v2_traces.jsonl.gz", "wt", encoding="utf-8") as f:
        for tr in traces:
            f.write(json.dumps(_jsonable(tr), allow_nan=False,
                               sort_keys=True)+"\n")
    (args.output / "summary.json").write_text(
        json.dumps(summary, sort_keys=True, indent=2, allow_nan=False)+"\n",
        encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "v1_vs_v2": aggregates,
        "footprint_vs_v2": footprint_result,
        "unwanted_contacts": aggregates["variant_contacts"],
        "deferred_regions": summary["v2_deferred_candidate_region_scores"],
    }, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
