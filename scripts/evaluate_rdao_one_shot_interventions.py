"""Exploratory causal intervention replays for RDAO v1 rejected observations.

A single *ordinary authorized* MuJoCo memory observation is forced at an
outcome-selected, pre-recorded rejected step, followed by the original policy
and unchanged safety controller. The step was selected offline using a
diagnostic-only shadow probe; no shadow data enter the deployed controller.

Variants:
  extra: force one observation (preserving the original 20-observation cap).
  swap:  force it, then suppress the next *naturally requested* observation
         as a timing-replacement control. Not guaranteed exact final dose.

The original RDAO run is replayed first and its actions, poses, observations,
contacts, and outcomes must match the frozen primary record exactly.
Historical code/results and held-out worlds remain untouched.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

import evaluate_rdao_phase2 as rdao_eval
import phase2_mujoco_navigation as nav
from spatial_memory.rdao import RDAOController

BASE = ROOT / "results/phase2_mujoco/rdao_v1_phase2_evaluation"
PROBE = ROOT / "results/phase2_mujoco/rdao_v1_visibility_probe_primary"
ANALYSIS = ROOT / "results/phase2_mujoco/rdao_v1_opportunity_analysis"
DEFAULT_OUTPUT = ROOT / "results/phase2_mujoco/rdao_v1_one_shot_interventions_v1"
FIELDS = (
    "step", "position", "heading_yaw", "action", "moved", "blocked",
    "contacts", "observation_granted", "observation_count",
    "emergency_intervention",
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_csv(path: Path):
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _bool(value):
    if isinstance(value, bool):
        return value
    if str(value).lower() in ("true", "1"):
        return True
    if str(value).lower() in ("false", "0"):
        return False
    raise ValueError(f"Not a boolean: {value!r}")


def _key(item):
    return (item["world_identity"], int(item["schedule"]), int(item["seed"]))


def _semantics(frame):
    return {name: frame.get(name) for name in FIELDS}


def _read_saved_traces():
    path = BASE / "primary_traces.jsonl.gz"
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        traces = [json.loads(line) for line in stream if line.strip()]
    if len(traces) != 72:
        raise ValueError("Expected 72 frozen primary RDAO traces")
    index = {}
    for trace in traces:
        name, schedule, variant, seed = trace["key"]
        if variant != "rdao_v1" or seed != 42:
            raise ValueError("Unexpected variant or seed in frozen traces")
        key = (name, int(schedule), int(seed))
        if key in index:
            raise ValueError("Duplicate frozen trace")
        index[key] = trace
    return index


def _compare_trace(saved, replayed, *, before_step=None):
    """Time measurements are excluded; pose/action/safety/observation is exact."""
    if before_step is None and len(saved["steps"]) != len(replayed["steps"]):
        raise RuntimeError("Unmodified RDAO replay has a different episode length")
    for old, new in zip(saved["steps"], replayed["steps"]):
        if before_step is not None and int(old["step"]) >= before_step:
            break
        if _semantics(old) != _semantics(new):
            raise RuntimeError(
                f"Frozen behavior mismatch at step {old['step']}: "
                f"saved={_semantics(old)} replay={_semantics(new)}")


def _first_difference(saved, changed):
    old = {int(frame["step"]): frame for frame in saved["steps"]}
    new = {int(frame["step"]): frame for frame in changed["steps"]}
    for step in sorted(set(old) | set(new)):
        if step not in old or step not in new:
            return step
        before, after = old[step], new[step]
        if any(before.get(field) != after.get(field) for field in
               ("position", "heading_yaw", "action", "moved", "blocked")):
            return step
    return None


def _saved_observation_steps(trace):
    return [int(f["step"]) for f in trace["steps"] if f["observation_granted"]]


class InterventionRDAO(RDAOController):
    """RDAO unchanged except for one forced authorized observation at a fixed step."""

    force_step = None
    variant = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.force_fired = False
        self.suppressed_next = False

    def decide(self, step, position):
        old_region_attempts = dict(self.region_last_attempted)
        decision = super().decide(step, position)
        diag = decision["rdao"]

        if step == self.force_step:
            if self.force_fired or decision["observation_granted"]:
                raise RuntimeError("Forced step must be an originally rejected observation")
            if self.remaining is not None and self.remaining <= 0:
                raise RuntimeError("Forced step unexpectedly exhausted observation budget")
            # Reproduce the exact pre-observation record expected by the
            # ORIGINAL refresh() method for map, route and action diagnostics.
            route = diag["nominal_route"]
            cost = self._route_cost(route)
            if not math.isfinite(cost):
                cost = float(self.memory.grid.size)
            diag["_pre_observation"] = {
                "grid": self.memory.grid.copy(), "route": route, "cost": cost,
                "position": tuple(map(int, position)),
                "heading_yaw": float(self.heading_yaw),
            }
            diag.update(requested=True, granted=True,
                        reason="one_shot_development_intervention",
                        intervention_forced=True)
            decision["observation_requested"] = True
            decision["observation_granted"] = True
            self.requests += 1
            self.force_fired = True

        elif (self.variant == "swap" and self.force_fired
              and not self.suppressed_next and decision["observation_granted"]):
            # The previous force is the new earlier observation. Explicitly
            # replace only the FIRST subsequent natural observation request.
            self.region_last_attempted.clear()
            self.region_last_attempted.update(old_region_attempts)
            self.requests -= 1
            diag.pop("_pre_observation", None)
            diag.update(requested=False, granted=False,
                        reason="one_shot_intervention_suppressed_next",
                        intervention_suppressed=True)
            decision["observation_requested"] = False
            decision["observation_granted"] = False
            self.suppressed_next = True

        return decision


def _run_with_intervention(payload, schedule, step, variant):
    if variant not in ("extra", "swap"):
        raise ValueError(variant)
    original = rdao_eval.RDAOController
    InterventionRDAO.force_step = int(step)
    InterventionRDAO.variant = variant
    # evaluate_rdao_phase2._instrumented_case references this class both in
    # its factory and isinstance checks, so all original trace hooks remain on.
    rdao_eval.RDAOController = InterventionRDAO
    try:
        return rdao_eval._instrumented_case(payload, int(schedule), "rdao_v1")
    finally:
        rdao_eval.RDAOController = original


def _metrics(row):
    return {
        "success": _bool(row["success"]),
        "elapsed_steps": int(row["elapsed_steps"]),
        "observations": int(row["observation_count"]),
        "travel_distance_m": float(row["travel_distance_m"]),
        "turns": int(row["g1_in_place_turns"]),
        "blocked_attempts": int(row["g1_footprint_blocked_attempts"]),
        "emergency_interventions": int(row["emergency_safety_interventions"]),
        "unwanted_contacts": int(row["g1_unwanted_contact_pairs"]),
        "scheduler_ms": float(row.get("rdao_scheduler_total_ms", 0.0)),
    }


def _select(args, source):
    priority = _load_csv(ANALYSIS / "priority_failure_cases.csv")
    if args.cohort == "priority":
        candidates = [r for r in priority if _bool(r["periodic_success"])]
    else:
        candidates = [r for r in _load_csv(ANALYSIS / "episode_opportunity_summary.csv")
                      if _bool(r["rdao_success"])
                      and str(r["first_missed_route_near_step"]).strip()]
        candidates.sort(key=lambda r: (
            r["mechanism"], r["world_identity"], int(r["schedule"])))
    if args.world:
        candidates = [r for r in candidates if args.world in r["world_identity"]]
    selected = candidates[:args.max_cases]
    if not selected:
        raise ValueError("No requested cohort cases found")
    output = []
    for item in selected:
        key = _key(item)
        step = int(item["first_missed_route_near_step"])
        if key not in source or not 1 <= step < 80:
            raise ValueError(f"Invalid frozen intervention target {key}: {step}")
        if _bool(source[key]["success"]) != _bool(item["rdao_success"]):
            raise ValueError(f"Saved outcomes changed for {key}")
        output.append((key, step))
    if len(set(key for key, step in output)) != len(output):
        raise ValueError("Duplicate selected world/schedule")
    return output


def _write_csv(path: Path, rows):
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort", choices=("priority", "controls"), default="priority")
    parser.add_argument("--max-cases", type=int, default=10)
    parser.add_argument("--world", help="Optional substring such as M:80030010")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    if args.max_cases < 1:
        parser.error("--max-cases must be positive")

    output = args.output or Path(str(DEFAULT_OUTPUT) + "_" + args.cohort)
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite existing results: {output}")

    primary = _load_csv(BASE / "primary_episodes.csv")
    source = {_key(item): item for item in primary}
    if len(source) != 72 or len(primary) != 72:
        raise ValueError("Frozen RDAO primary run should have 72 unique cases")
    saved_traces = _read_saved_traces()
    if set(saved_traces) != set(source):
        raise ValueError("Frozen RDAO rows and traces do not have identical episode keys")
    selected = _select(args, source)

    # The probe is for OFFLINE TARGET SELECTION only; never access its hidden
    # truth or shadow measurements in the experimental controller.
    probe = json.loads((PROBE / "summary.json").read_text())
    if (probe.get("scope") != "primary"
            or probe.get("accepted_observations_exactly_verified") != 584):
        raise ValueError("Wrong visibility-probe source")
    frozen_files = [
        BASE / "primary_episodes.csv", BASE / "primary_traces.jsonl.gz",
        ANALYSIS / "priority_failure_cases.csv",
        ANALYSIS / "episode_opportunity_summary.csv",
        PROBE / "summary.json",
    ]
    hashes_before = {str(p.relative_to(ROOT)): _sha(p) for p in frozen_files}
    original_preservation = nav.verify_preserved_prefix()
    by_world = {w["identity"]: w for w in nav.admitted_worlds()}
    if len(by_world) != 36:
        raise ValueError("Expected exactly 36 admitted fit worlds")
    summaries = []
    for index, (key, step) in enumerate(selected, 1):
        identity, schedule, seed = key
        payload = by_world[identity]
        stored = saved_traces[key]

        # Faithfully reproduce the original episode with absolutely no
        # intervention before drawing any counterfactual conclusion.
        original_row, original_trace = rdao_eval._instrumented_case(
            payload, schedule, "rdao_v1")
        if rdao_eval._signature(original_row) != rdao_eval._signature(source[key]):
            raise RuntimeError(f"Unmodified RDAO row failed reproduction: {key}")
        _compare_trace(stored, original_trace)
        saved_target = next((f for f in stored["steps"] if f["step"] == step), None)
        if (not saved_target or not saved_target.get("rdao")
                or saved_target["rdao"]["granted"]):
            raise RuntimeError(f"Target is not a saved denied step: {key} step={step}")

        base_metrics = _metrics(source[key])
        for mode in ("extra", "swap"):
            row, trace = _run_with_intervention(payload, schedule, step, mode)
            _compare_trace(stored, trace, before_step=step)
            target = next((f for f in trace["steps"] if f["step"] == step), None)
            if not target or not target["rdao"].get("intervention_forced"):
                raise RuntimeError("Injected step missing in observed intervention trace")
            effect = target["rdao"]["observation_effect"]
            if not effect or not target["observation_granted"]:
                raise RuntimeError("Intervention did not receive ordinary sensor measurement")
            suppressed = [f["step"] for f in trace["steps"] if
                          f.get("rdao", {}).get("intervention_suppressed")]
            if mode == "extra" and suppressed:
                raise RuntimeError("Extra intervention unexpectedly suppressed observations")
            if mode == "swap" and len(suppressed) > 1:
                raise RuntimeError("Swap intervention suppressed more than one observation")

            now = _metrics(row)
            summaries.append({
                "world_identity": identity, "schedule": schedule, "seed": seed,
                "cohort": args.cohort, "forced_step": step, "variant": mode,
                "baseline_success": base_metrics["success"],
                "success": now["success"],
                "success_changed": int(now["success"]) - int(base_metrics["success"]),
                "baseline_steps": base_metrics["elapsed_steps"],
                "elapsed_steps": now["elapsed_steps"],
                "delta_steps": now["elapsed_steps"] - base_metrics["elapsed_steps"],
                "baseline_observations": base_metrics["observations"],
                "observations": now["observations"],
                "delta_observations": now["observations"] - base_metrics["observations"],
                "baseline_distance_m": base_metrics["travel_distance_m"],
                "distance_m": now["travel_distance_m"],
                "delta_distance_m": now["travel_distance_m"] - base_metrics["travel_distance_m"],
                "baseline_turns": base_metrics["turns"], "turns": now["turns"],
                "baseline_blocked_attempts": base_metrics["blocked_attempts"],
                "blocked_attempts": now["blocked_attempts"],
                "baseline_safety_interventions": base_metrics["emergency_interventions"],
                "safety_interventions": now["emergency_interventions"],
                "unwanted_contacts": now["unwanted_contacts"],
                "baseline_scheduler_ms": base_metrics["scheduler_ms"],
                "scheduler_ms": now["scheduler_ms"],
                "first_action_or_pose_divergence_step": _first_difference(stored, trace),
                "original_observation_steps": json.dumps(_saved_observation_steps(stored)),
                "intervention_observation_steps": json.dumps(_saved_observation_steps(trace)),
                "suppressed_step": suppressed[0] if suppressed else "",
                "swap_completed": mode == "swap" and len(suppressed) == 1,
                "exact_final_dose_match": now["observations"] == base_metrics["observations"],
                "forced_memory_changed_cells": effect["memory_changed_cell_count"],
                "forced_selected_astar_action_changed": effect["selected_action_changed"],
                "forced_astar_route_cost_changed": effect["route_cost_changed"],
            })
        print(f"Completed {index}/{len(selected)}: {identity} schedule {schedule}", flush=True)

    # Fail closed on any unexpected modification of admitted data.
    if nav.verify_preserved_prefix() != original_preservation:
        raise RuntimeError("Preserved Phase 1.5 material changed")
    if {str(p.relative_to(ROOT)): _sha(p) for p in frozen_files} != hashes_before:
        raise RuntimeError("An input frozen artifact changed during intervention replay")

    overall = {}
    for mode in ("extra", "swap"):
        group = [r for r in summaries if r["variant"] == mode]
        overall[mode] = {
            "cases": len(group), "successes": sum(r["success"] for r in group),
            "baseline_successes": sum(r["baseline_success"] for r in group),
            "rescued_failures": sum(not r["baseline_success"] and r["success"] for r in group),
            "harmed_successes": sum(r["baseline_success"] and not r["success"] for r in group),
            "mean_observation_delta": sum(r["delta_observations"] for r in group) / len(group),
            "mean_censored_step_delta": sum(r["delta_steps"] for r in group) / len(group),
            "exact_final_dose_matches": sum(r["exact_final_dose_match"] for r in group),
            "swap_completed": sum(r["swap_completed"] for r in group),
            "episodes_with_forced_astar_action_change": sum(
                r["forced_selected_astar_action_changed"] for r in group),
        }

    record = {
        "status": "EXPLORATORY_DEVELOPMENT_INTERVENTION_NOT_HELD_OUT",
        "cohort": args.cohort, "selected": [
            {"world_identity": k[0], "schedule": k[1], "seed": k[2], "forced_step": s}
            for k, s in selected],
        "overall": overall,
        "frozen_input_sha256": hashes_before,
        "phase15_preservation": original_preservation,
        "causal_scope": ("One authorized observation imposed at an externally "
            "pre-selected development step, not a new online observation policy."),
        "notes": [
            "Priority cases are specifically RDAO failures rescued by Periodic: outcome-selected, not representative.",
            "Normal RDAO decision, observation model and independent Emergency Safety remain unchanged except forced step and optional later suppression.",
            "The step was selected with evaluator-only shadow sensing, never passed as a live value-of-information score.",
            "Swap replaces one subsequent naturally requested observation, not necessarily the same final observation count.",
            "Observation budget is unchanged; compare actual dose explicitly.",
            "No evidence of generalization or superiority over Periodic/Age is established by this test.",
        ],
    }
    output.mkdir(parents=True)
    _write_csv(output / "episode_intervention_comparison.csv", summaries)
    (output / "summary.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"output": str(output), **overall}, indent=2))


if __name__ == "__main__":
    main()
