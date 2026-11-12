"""Retrospective second-sensing ablation following a saved first Footprint scan.

Three hand-selected, previously inspected FIT-world mechanisms are probed:
R:80000017 S0: force12, suppress next naturally granted step14, FORCE20;
M:80030007 S1: force23 as earlier; FORCE48;
R:80000022 S0/S1: force26 with or without suppressing next step27;
                       FORCE30 in each first-scan condition.

All second targets were selected after inspecting the full continuous-Footprint
trajectory: strictly diagnostic, NOT a deployable scheduler or held-out
evaluation. Reproduces the original RDAO, saved first-scan control and
Footprint inputs; performs only the given second-scan change. Checks an
identical pre-sensor pose and raw 61-ray values against the saved Footprint
sensor at the same second step; the *memory_after* may differ if an earlier
arm observed a different map.

Never accesses hidden occupancy or shadow-sensor data. The independent
Emergency Safety and selected-action collision shield remain untouched,
and contact outcomes are recorded rather than suppressed.
"""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

import evaluate_rdao_phase2 as evaluator
import phase2_mujoco_navigation as navigation
from evaluate_rdao_one_shot_interventions import (
    InterventionRDAO, _bool, _compare_trace, _first_difference, _key,
    _load_csv, _metrics, _read_saved_traces, _run_with_intervention,
    _saved_observation_steps, _sha, _write_csv,
)
from evaluate_rdao_footprint_first_sensing_interventions import (
    read_footprint_traces, intervention_matches_first_footprint_scan,
)
from analyze_rdao_footprint_visibility_online_forensics import first_differences
from evaluate_rdao_online_safe_gate_screen import _jsonable

BASE = ROOT / "results/phase2_mujoco/rdao_v1_phase2_evaluation"
FIRST = ROOT / "results/phase2_mujoco/rdao_v1_footprint_first_sensing_causes_v1"
FOOTPRINT = ROOT / "results/phase2_mujoco/rdao_v1_footprint_visibility_online_fit72_v1"
DEFAULT_OUTPUT = ROOT / "results/phase2_mujoco/rdao_v1_footprint_second_sensing_causes_v1"
PREFIX = "phase1.5-v0.4-BPRIME-1:fit:"
# Second step MUST correspond to an actual Footprint observation at a
# same-pose position where the respective frozen first-only control did not
# observe. Values below are diagnostic labels derived from saved FIT traces.
TARGETS = (
    ("R:80000017", 0, 12, "swap", 20),
    ("M:80030007", 1, 23, "extra", 48),
    ("R:80000022", 0, 26, "extra", 30),
    ("R:80000022", 0, 26, "swap", 30),
    ("R:80000022", 1, 26, "extra", 30),
    ("R:80000022", 1, 26, "swap", 30),
)
INPUTS = (
    BASE / "primary_episodes.csv", BASE / "primary_traces.jsonl.gz",
    FIRST / "first_sensing_causal_comparison.csv",
    FIRST / "first_sensing_causal_traces.jsonl.gz",
    FIRST / "summary.json",
    FOOTPRINT / "paired_visibility_online.csv",
    FOOTPRINT / "visibility_online_traces.jsonl.gz",
)


class SecondForcedScanRDAO(InterventionRDAO):
    """Inherit the SAME earlier forced scan and optional one-scan swap."""

    force_step = None
    variant = None
    second_step = None

    def decide(self, step, position):
        result = super().decide(step, position)
        if int(step) != self.second_step:
            return result
        if result["observation_granted"]:
            raise RuntimeError(
                f"Second target {step} was already a naturally authorized observation")
        if self.remaining is not None and self.remaining <= 0:
            raise RuntimeError("Second forced scan would violate 20-observation budget")
        diag = result["rdao"]
        route = diag["nominal_route"]
        cost = self._route_cost(route)
        if not __import__("math").isfinite(cost):
            cost = float(self.memory.grid.size)
        diag["_pre_observation"] = {
            "grid": self.memory.grid.copy(),
            "route": route,
            "cost": cost,
            "position": tuple(map(int, position)),
            "heading_yaw": float(self.heading_yaw),
        }
        diag.update(requested=True, granted=True,
                    reason="second_fit_diagnostic_authorized_observation",
                    intervention_second_forced=True)
        result["observation_requested"] = True
        result["observation_granted"] = True
        self.requests += 1
        return result


def run_second(payload, schedule, *, first_step, mode, second_step):
    if mode not in ("extra", "swap") or second_step <= first_step:
        raise ValueError("Invalid ordered intervention pattern")
    original = evaluator.RDAOController
    SecondForcedScanRDAO.force_step = int(first_step)
    SecondForcedScanRDAO.variant = mode
    SecondForcedScanRDAO.second_step = int(second_step)
    evaluator.RDAOController = SecondForcedScanRDAO
    try:
        return evaluator._instrumented_case(payload, int(schedule), "rdao_v1")
    finally:
        evaluator.RDAOController = original


def read_first_traces(path):
    index = {}
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            obj = json.loads(line)
            if obj["intervention"] not in ("extra", "swap"):
                raise RuntimeError("Unexpected first-scan intervention")
            key = (*obj["key"], obj["intervention"])
            if key in index:
                raise RuntimeError(f"Duplicate first-scan trace {key}")
            index[key] = obj["trace"]
    if len(index) != 18:
        raise RuntimeError("Expected 9 fit cases x 2 saved first-scan controls")
    return index


def check_second_sensor(reference, control, updated, step):
    before = next(f for f in control["steps"] if int(f["step"]) == step)
    fpscan = next(f for f in reference["steps"] if int(f["step"]) == step)
    variant = next(f for f in updated["steps"] if int(f["step"]) == step)
    if before["observation_granted"] or not fpscan["observation_granted"]:
        raise RuntimeError("Selected second intervention is not a new Footprint scan")
    if not variant.get("rdao", {}).get("intervention_second_forced"):
        raise RuntimeError("Second scan flag not preserved in trace")
    if not variant["observation_granted"]:
        raise RuntimeError("Second scan not actually granted")
    for name in ("position", "heading_yaw"):
        x, y, z = (frame["rdao"][name] for frame in (before, fpscan, variant))
        if x != y or x != z:
            raise RuntimeError(f"Second scan is not same-pose sensor: {name}")
    base_eff = fpscan["rdao"].get("observation_effect")
    new_eff = variant["rdao"].get("observation_effect")
    if not base_eff or not new_eff:
        raise RuntimeError("Missing actual authorized sensor results")
    for field in ("received_observation_values", "visible_cell_count"):
        if base_eff[field] != new_eff[field]:
            raise RuntimeError(f"Second raw 61-ray scan differs: {field}")
    return {
        "raw_visible_cells": int(new_eff["visible_cell_count"]),
        "changed_cells_footprint": int(base_eff["memory_changed_cell_count"]),
        "changed_cells_second": int(new_eff["memory_changed_cell_count"]),
        "pre_memory_exact_match": base_eff["memory_before"] == new_eff["memory_before"],
        "post_memory_exact_match": base_eff["memory_after"] == new_eff["memory_after"],
        "selected_step_action_matches_footprint":
            fpscan["action"] == variant["action"],
    }


def _case_key(item):
    return (item["world_identity"], int(item["schedule"]), int(item["seed"]))


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-cases", type=int, default=None,
                        help="First N of 6 predefined diagnosis arms")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.max_cases is not None and args.max_cases < 1:
        parser.error("--max-cases must be a positive integer")
    if args.output.exists():
        raise FileExistsError(f"Refusing overwrite: {args.output}")

    original_rows = _load_csv(BASE / "primary_episodes.csv")
    original_index = {_key(row): row for row in original_rows}
    original_traces = _read_saved_traces()
    first_rows = _load_csv(FIRST / "first_sensing_causal_comparison.csv")
    first_index = {(*_case_key(row), row["intervention"]): row for row in first_rows}
    first_traces = read_first_traces(FIRST / "first_sensing_causal_traces.jsonl.gz")
    footprint = read_footprint_traces(FOOTPRINT / "visibility_online_traces.jsonl.gz")
    footprint_rows = {_key(row): row for row in
                      _load_csv(FOOTPRINT / "paired_visibility_online.csv")}
    if (len(original_index) != 72 or set(original_index) != set(original_traces)
            or len(first_index) != 18 or set(first_index) != set(first_traces)
            or len(footprint_rows) != 72 or set(footprint_rows) != set(footprint)):
        raise RuntimeError("Missing or duplicate verified frozen records")
    original_preservation = navigation.verify_preserved_prefix()
    input_hashes = {str(p.relative_to(ROOT)): _sha(p) for p in INPUTS}
    worlds = {world["identity"]: world for world in navigation.admitted_worlds()}
    if len(worlds) != 36 or set(worlds) != set(original_index_key[0]
                                               for original_index_key in original_index):
        raise RuntimeError("Expected exactly 36 unchanged FIT worlds")
    requested = TARGETS[:args.max_cases]
    if not requested:
        raise RuntimeError("No diagnosis targets selected")
    results, traces = [], []
    for index, (world, sched, first_step, mode, second_step) in enumerate(requested, 1):
        key = (PREFIX + world, sched, 42)
        control_key = (*key, mode)
        if key not in original_index or key not in footprint or control_key not in first_index:
            raise RuntimeError(f"Selected case missing committed evidence: {key}")
        row = first_index[control_key]
        if (int(row["first_added_footprint_observation_step"]) != first_step or
                row["intervention"] != mode):
            raise RuntimeError("Original first-sensing contrast changed")
        payload = worlds[key[0]]
        unmodified_row, unmodified_trace = evaluator._instrumented_case(
            payload, sched, "rdao_v1")
        if evaluator._signature(unmodified_row) != evaluator._signature(original_index[key]):
            raise RuntimeError("Frozen original signature mismatch")
        _compare_trace(original_traces[key], unmodified_trace)

        control_row, control_trace = _run_with_intervention(
            payload, sched, first_step, mode)
        _compare_trace(first_traces[control_key], control_trace)
        original_control_metrics = _metrics(control_row)
        if (original_control_metrics["success"] != _bool(row["forced_success"])
                or original_control_metrics["elapsed_steps"] != int(row["forced_steps_h80"])
                or original_control_metrics["observations"] != int(row["forced_observations"])):
            raise RuntimeError("Saved first-only condition did not reproduce")
        pre = next(f for f in first_traces[control_key]["steps"]
                   if int(f["step"]) == second_step)
        if pre["observation_granted"]:
            raise RuntimeError("Second target was already observed by first-scan condition")
        target_scan = next(f for f in footprint[key]["steps"]
                           if int(f["step"]) == second_step)
        if not target_scan["observation_granted"]:
            raise RuntimeError("Second target was not a saved Footprint scan")

        second_row, second_trace = run_second(
            payload, sched, first_step=first_step, mode=mode, second_step=second_step)
        _compare_trace(control_trace, second_trace, before_step=second_step)
        features = check_second_sensor(footprint[key], control_trace,
                                       second_trace, second_step)
        second_metrics = _metrics(second_row)
        if (second_metrics["observations"] > 20 or
                int(second_row.get("g1_unselected_action_shield_queries", 0)) != 0 or
                not _bool(second_row["g1_shield_query_count_valid"])):
            raise RuntimeError("Safety shield or max20 sensor budget invalid")
        _, motion_diff = first_differences(footprint[key], second_trace)
        result = {
            "world_identity": key[0], "schedule": sched, "seed": 42,
            "first_forced_step": first_step, "base_intervention": mode,
            "second_forced_step": second_step,
            "original_success": _bool(original_index[key]["success"]),
            "footprint_success": _bool(footprint_rows[key]["variant_success"]),
            "first_only_success": original_control_metrics["success"],
            "second_success": second_metrics["success"],
            "original_steps_h80": int(original_index[key]["elapsed_steps"]),
            "footprint_steps_h80": int(footprint_rows[key]["variant_elapsed_steps"]),
            "first_only_steps_h80": original_control_metrics["elapsed_steps"],
            "second_steps_h80": second_metrics["elapsed_steps"],
            "original_distance_m": float(original_index[key]["travel_distance_m"]),
            "footprint_distance_m": float(footprint_rows[key]["variant_travel_distance_m"]),
            "first_only_distance_m": original_control_metrics["travel_distance_m"],
            "second_distance_m": second_metrics["travel_distance_m"],
            "original_observations": int(original_index[key]["observation_count"]),
            "footprint_observations": int(footprint_rows[key]["variant_observations"]),
            "first_only_observations": original_control_metrics["observations"],
            "second_observations": second_metrics["observations"],
            "first_only_emergency_interventions":
                original_control_metrics["emergency_interventions"],
            "second_emergency_interventions":
                second_metrics["emergency_interventions"],
            "second_unwanted_contacts": second_metrics["unwanted_contacts"],
            "first_action_change_due_to_second_scan":
                _first_difference(control_trace, second_trace),
            "second_vs_footprint_first_motion_difference":
                motion_diff if motion_diff is not None else "",
            "first_step_raw_sensor_equal_to_footprint": True,
            "second_step_raw_sensor_equal_to_footprint": True,
            **features,
            "first_only_observation_steps": json.dumps(
                _saved_observation_steps(control_trace)),
            "second_condition_observation_steps": json.dumps(
                _saved_observation_steps(second_trace)),
            "footprint_observation_steps": json.dumps(
                _saved_observation_steps(footprint[key])),
        }
        # The first forced scan was tested and explicitly compared in the
        # prior experiment. Ensure the same outcome still holds here.
        original_frame = next(f for f in original_traces[key]["steps"]
                              if int(f["step"]) == first_step)
        intervention_matches_first_footprint_scan(
            original_traces[key], footprint[key], control_trace, first_step)
        if original_frame["observation_granted"]:
            raise RuntimeError("The first intervention target is not originally denied")
        results.append(result)
        traces.append({
            "key": list(key), "first_intervention": mode,
            "first_forced_step": first_step,
            "second_forced_step": second_step,
            "trace": second_trace,
            "metrics": second_metrics,
        })
        print(f"Completed {index}/{len(requested)}: {world} schedule {sched}"
              f", first {first_step} {mode}, second {second_step}", flush=True)

    if navigation.verify_preserved_prefix() != original_preservation:
        raise RuntimeError("Protected Phase1.5 manifest unexpectedly changed")
    if {str(p.relative_to(ROOT)): _sha(p) for p in INPUTS} != input_hashes:
        raise RuntimeError("Saved input file modified during diagnosis")
    args.output.mkdir(parents=True)
    _write_csv(args.output / "second_sensing_causal_comparison.csv", results)
    with gzip.open(args.output / "second_sensing_causal_traces.jsonl.gz",
                   "wt", encoding="utf-8") as f:
        for record in traces:
            f.write(json.dumps(_jsonable(record), sort_keys=True,
                               allow_nan=False) + "\n")
    summary = {
        "status": "RETROSPECTIVE_FIT_SECOND_SENSING_CAUSAL_ABLATION_NOT_ONLINE_POLICY",
        "arm_count": len(results), "independent_world_layouts":
            len(set(r["world_identity"] for r in results)),
        "source_hashes": input_hashes,
        "protected_phase15_prefix": original_preservation,
        "unwanted_contact_episodes": sum(r["second_unwanted_contacts"] > 0
                                         for r in results),
        "total_unwanted_contact_pairs": sum(r["second_unwanted_contacts"]
                                           for r in results),
        "limitations": [
            "All first/second steps were chosen from outcomes on already inspected development FIT worlds; no model fitting, new worlds or held-out evaluation.",
            "Each fixed two-step intervention changes later memory, sensing and navigation, so its full observed effect is a compound downstream feedback response.",
            "Same pose and raw sensor values at a selected scan are checked against the saved Footprint run, but memory_before may differ after intervening on earlier observations.",
            "The first-only control is rerun and reproduced semantically before making a causal comparison; original RDAO is also reproduced.",
            "The original RDAO predictor is preserved after forced interventions. This is NOT the continuing Footprint visibility policy.",
            "The swap strategy suppresses one future original scheduler observation; it does not guarantee matched final observation dose.",
            "Two pedestrian schedules of the same maze are correlated and not independent worlds.",
            "Unwanted contacts are always reported, not filtered or used as a model feature.",
            "The G1 navigation simulator is a kinematic-root MuJoCo proxy, not full dynamic walking.",
        ],
    }
    (args.output / "summary.json").write_text(
        json.dumps(summary, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "cases": len(results),
        "unwanted_contacts": summary["total_unwanted_contact_pairs"],
        "comparisons": [
            {k: row[k] for k in (
                "world_identity", "schedule", "base_intervention",
                "first_forced_step", "second_forced_step",
                "first_only_success", "second_success",
                "footprint_success", "first_only_steps_h80",
                "second_steps_h80", "footprint_steps_h80",
                "first_only_observations", "second_observations",
                "footprint_observations", "pre_memory_exact_match",
                "post_memory_exact_match",
                "second_vs_footprint_first_motion_difference",
                "second_unwanted_contacts")}
            for row in results],
    }, indent=2, allow_nan=False))


if __name__ == "__main__":
    run()
