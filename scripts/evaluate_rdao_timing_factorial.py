"""Development-only 2x2 timing/observation ablation for a frozen RDAO case.

A single early observation at step 2 can both introduce new map evidence
and suppress/shift the naturally occurring step-3 observation. Separate
these effects by directly controlling authorized sensing at BOTH steps:

  01 = no step-2 observation; allow step-3 observation (frozen baseline)
  00 = no step-2 observation; suppress step-3 observation
  10 = force step-2 observation; suppress step-3 observation
  11 = force step-2 and step-3 observations

Only those two steps are controlled. From step 4 onward, normal RDAO
decides. All sensor data are from ordinary authorized memory raycasts,
never evaluator-only shadow probes. Other worlds, methods and historical
results are not modified or rerun.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

import evaluate_rdao_phase2 as eval_rdao
import phase2_mujoco_navigation as nav
from evaluate_rdao_one_shot_interventions import (
    _bool, _compare_trace, _first_difference, _key,
    _load_csv, _metrics, _read_saved_traces, _sha, _write_csv,
)
from spatial_memory.rdao import RDAOController

PRIMARY = ROOT / "results/phase2_mujoco/rdao_v1_phase2_evaluation"
DEFAULT_OUT = ROOT / "results/phase2_mujoco/rdao_v1_timing_factorial_M80030010"
ARMS = ((0, 1), (0, 0), (1, 0), (1, 1))


class TimingFactorialRDAO(RDAOController):
    """Force or suppress exactly steps 2 and 3; restore ordinary policy from 4."""

    observe_step_2 = False
    observe_step_3 = True

    def decide(self, step, position):
        old_attempts = dict(self.region_last_attempted)
        decision = super().decide(step, position)
        if step not in (2, 3):
            return decision

        intended = self.observe_step_2 if step == 2 else self.observe_step_3
        diagnostic = decision["rdao"]
        natural = bool(decision["observation_granted"])
        diagnostic["timing_factorial"] = True
        diagnostic["natural_observation_granted"] = natural
        diagnostic["target_observation_granted"] = bool(intended)

        if intended and not natural:
            if self.remaining is not None and self.remaining == 0:
                raise RuntimeError("Timing factorial exceeded original sensing cap")
            route = diagnostic["nominal_route"]
            cost = self._route_cost(route)
            if not math.isfinite(cost):
                cost = float(self.memory.grid.size)
            diagnostic["_pre_observation"] = {
                "grid": self.memory.grid.copy(),
                "route": route,
                "cost": cost,
                "position": tuple(map(int, position)),
                "heading_yaw": float(self.heading_yaw),
            }
            self.requests += 1
            decision["observation_requested"] = True
            decision["observation_granted"] = True
            diagnostic.update(
                requested=True, granted=True,
                reason="timing_factorial_force_authorized_memory_observation",
                timing_factorial_forced=True,
            )
        elif not intended and natural:
            # Undo only bookkeeping from the original scheduler deciding to
            # grant the observation. No sensor call / memory refresh occurs.
            self.region_last_attempted.clear()
            self.region_last_attempted.update(old_attempts)
            self.requests -= 1
            diagnostic.pop("_pre_observation", None)
            decision["observation_requested"] = False
            decision["observation_granted"] = False
            diagnostic.update(
                requested=False, granted=False,
                reason="timing_factorial_suppress_authorized_memory_observation",
                timing_factorial_suppressed=True,
            )
        return decision


def run_case(payload, schedule, observe2, observe3):
    original = eval_rdao.RDAOController
    TimingFactorialRDAO.observe_step_2 = bool(observe2)
    TimingFactorialRDAO.observe_step_3 = bool(observe3)
    eval_rdao.RDAOController = TimingFactorialRDAO
    try:
        return eval_rdao._instrumented_case(payload, schedule, "rdao_v1")
    finally:
        eval_rdao.RDAOController = original


def _step_fields(trace, step):
    frame = next((x for x in trace["steps"] if int(x["step"]) == step), None)
    if frame is None:
        raise RuntimeError(f"Missing step {step} in traced episode")
    diag = frame.get("rdao") or {}
    effect = diag.get("observation_effect") or {}
    return {
        "step": step,
        "position_after_action": frame.get("position"),
        "heading_yaw_after_action": frame.get("heading_yaw"),
        "action": frame.get("action"),
        "observed": frame.get("observation_granted"),
        "original_scheduler_would_grant": diag.get("natural_observation_granted"),
        "forced": diag.get("timing_factorial_forced", False),
        "suppressed": diag.get("timing_factorial_suppressed", False),
        "changed_memory_cells": effect.get("memory_changed_cells", []),
        "first_astar_action_changed": effect.get("selected_action_changed"),
        "astar_cost_before": effect.get("route_cost_before"),
        "astar_cost_after": effect.get("route_cost_after"),
    }


def _sanitize(obj):
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (tuple, list)):
        return [_sanitize(item) for item in obj]
    return obj


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--world", default="M:80030010",
                        help="Admitted fit world identity suffix, e.g. M:80030010")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    output = args.output
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite results: {output}")

    original_rows = _load_csv(PRIMARY / "primary_episodes.csv")
    saved_rows = {_key(row): row for row in original_rows}
    saved_traces = _read_saved_traces()
    if len(saved_rows) != 72 or set(saved_rows) != set(saved_traces):
        raise ValueError("Frozen 72-case RDAO primary evidence changed")
    matches = [(key, value) for key, value in saved_rows.items()
               if key[0].endswith(args.world)]
    matches.sort(key=lambda item: item[0][1])
    if len(matches) != 2 or {key[1] for key, _ in matches} != {0, 1}:
        raise ValueError("Expected exactly two admitted schedules for one world")

    preserved = nav.verify_preserved_prefix()
    worlds = {w["identity"]: w for w in nav.admitted_worlds()}
    if len(worlds) != 36:
        raise RuntimeError("Admission world set is not frozen at 36")
    frozen_paths = (
        PRIMARY / "primary_episodes.csv",
        PRIMARY / "primary_traces.jsonl.gz",
    )
    frozen_hashes = {str(p.relative_to(ROOT)): _sha(p) for p in frozen_paths}
    rows, full_traces = [], []
    for key, old in matches:
        world, schedule, seed = key
        if seed != 42 or world not in worlds:
            raise ValueError(f"Unexpected world/seed {key}")
        scene = worlds[world]

        # Reproduce the historical trace and summary WITHOUT INTERVENTION.
        row0, trace0 = eval_rdao._instrumented_case(scene, schedule, "rdao_v1")
        if eval_rdao._signature(row0) != eval_rdao._signature(old):
            raise RuntimeError(f"Original metric signature changed for {key}")
        _compare_trace(saved_traces[key], trace0)
        if (saved_traces[key]["steps"][2]["observation_granted"]
                or not saved_traces[key]["steps"][3]["observation_granted"]):
            raise ValueError("Factorial requires rejected step 2 and granted step 3")

        for observe2, observe3 in ARMS:
            variant = f"{observe2}{observe3}"
            if variant == "01":
                row, trace = row0, trace0
            else:
                row, trace = run_case(scene, schedule, observe2, observe3)
                _compare_trace(saved_traces[key], trace, before_step=2)
            s2, s3 = _step_fields(trace, 2), _step_fields(trace, 3)
            if bool(s2["observed"]) != bool(observe2) or \
               bool(s3["observed"]) != bool(observe3):
                raise RuntimeError(f"Unexpected factorial observation pattern for {key}: {variant}")
            metrics = _metrics(row)
            if (metrics["observations"] > 20
                    or int(row.get("g1_unselected_action_shield_queries", 0)) != 0
                    or not _bool(row["g1_shield_query_count_valid"])):
                raise RuntimeError("Observation cap / selected-action shield invariant violated")
            baseline = _metrics(old)
            rows.append({
                "world_identity": world, "schedule": schedule, "seed": seed,
                "variant": variant, "observe_step2": bool(observe2),
                "observe_step3": bool(observe3),
                "success": metrics["success"],
                "elapsed_steps": metrics["elapsed_steps"],
                "observations": metrics["observations"],
                "distance_m": metrics["travel_distance_m"],
                "turns": metrics["turns"],
                "blocked_attempts": metrics["blocked_attempts"],
                "emergency_interventions": metrics["emergency_interventions"],
                "unwanted_contacts": metrics["unwanted_contacts"],
                "delta_steps_vs_baseline": metrics["elapsed_steps"] - baseline["elapsed_steps"],
                "delta_observations_vs_baseline": metrics["observations"] - baseline["observations"],
                "first_action_or_pose_divergence_step":
                    _first_difference(saved_traces[key], trace),
                "step2_memory_changed": len(s2["changed_memory_cells"]),
                "step3_memory_changed": len(s3["changed_memory_cells"]),
                "step2_first_astar_action_changed": s2["first_astar_action_changed"],
                "step3_first_astar_action_changed": s3["first_astar_action_changed"],
            })
            full_traces.append({
                "world_identity": world, "schedule": schedule,
                "seed": seed, "variant": variant, "metrics": metrics,
                "step2": s2, "step3": s3, "trace": trace,
            })
        print(f"Completed factorial: {world} schedule {schedule}", flush=True)

    if nav.verify_preserved_prefix() != preserved:
        raise RuntimeError("Phase 1.5 evidence modified")
    if {str(p.relative_to(ROOT)): _sha(p) for p in frozen_paths} != frozen_hashes:
        raise RuntimeError("Frozen RDAO source evidence modified")

    summary = {
        "status": "EXPLORATORY_2X2_OBSERVATION_TIMING_DIAGNOSTIC_NOT_POLICY",
        "purpose": "Separate early observation from omission of a later observation",
        "world_suffix": args.world, "episodes_per_variant": 2,
        "arm_definition": {
            "01": "baseline, no observation at 2, natural observation at 3",
            "00": "suppress observation at 3 without early observation",
            "10": "force observation at 2, suppress at 3",
            "11": "force observations at both 2 and 3",
        },
        "arm_aggregates": {
            mode: {
                "goal_completions": sum(r["success"] for r in rows if r["variant"] == mode),
                "steps": [r["elapsed_steps"] for r in rows if r["variant"] == mode],
                "observations": [r["observations"] for r in rows if r["variant"] == mode],
                "distance_m": [r["distance_m"] for r in rows if r["variant"] == mode],
                "unwanted_contacts": sum(r["unwanted_contacts"] for r in rows if r["variant"] == mode),
            } for mode in ("01", "00", "10", "11")
        },
        "frozen_hashes": frozen_hashes,
        "preserved_phase15": preserved,
        "limitations": [
            "The two schedules are correlated repeats of one development world, not two independent worlds.",
            "Outcomes beyond step 3 respond adaptively to changing maps, poses and observation requests.",
            "Each arm has the same maximum observation budget but actual final sensing dose is not fixed.",
            "The designated observation times came from a posthoc, evaluator-guided diagnosis.",
            "No online candidate selection rule or held-out benefit is established.",
        ],
    }
    output.mkdir(parents=True)
    _write_csv(output / "factorial_comparison.csv", rows)
    with gzip.open(output / "factorial_traces.jsonl.gz", "wt", encoding="utf-8") as stream:
        for record in full_traces:
            stream.write(json.dumps(_sanitize(record), sort_keys=True, allow_nan=False) + "\n")
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(json.dumps({"output": str(output), "arm_aggregates": summary["arm_aggregates"]},
                     indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
