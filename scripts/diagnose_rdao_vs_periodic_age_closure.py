"""Close RDAO development with paired failure forensics and optional causal replay.

Scope: pre-existing 36 FIT mazes x two correlated pedestrian schedules, H80.
Targets are ALL v2 failures where at least one frozen Periodic/Age comparator
reached goal. Observational timing differences are NOT themselves causal.

Offline:
  read frozen baseline H80 traces and saved v2 full instrumented traces;
  compare first observation and actual action/pose divergence, per-step RDAO
  decision score, denied/suppressed scan, and prior blocked/emergency feedback.

Optional --intervene:
  for each target, select the first N successful-baseline-only observations
  with the SAME pre-action pose/yaw on the common executed-trajectory prefix.
  Force one REAL authorized spatial-memory sensor scan at the selected
  time in a live replay, either as extra or swapping the next natural scan.
  Do NOT reuse baseline sensor output at a different pose. This is a
  retrospective, post-hoc diagnostic, NOT a deployable online policy.
  No shield, emergency controller, hidden truth or sensor geometry is
  modified. Cap20, source hashes and prefix reproduction are enforced.

Results alone may NOT identify every root cause. If no same-pose missed scan
precedes path divergence, record "unidentified" instead of guessing.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/"src"), str(ROOT/"scripts")]

import evaluate_rdao_phase2 as evaluator
import phase2_mujoco_navigation as navigation
from evaluate_rdao_one_shot_interventions import (
    _bool, _compare_trace, _first_difference, _key, _load_csv, _metrics,
    _sha, _write_csv,
)
from evaluate_rdao_footprint_visibility_online import first_observation_difference
from evaluate_rdao_online_safe_gate_screen import _jsonable
from spatial_memory.rdao_v2 import RDAOv2ViewpointController

H80 = ROOT/"results/phase2_mujoco/g1_forward_first_61ray_emergency_safety_full_288_v1"
V2 = ROOT/"results/phase2_mujoco/rdao_v2_viewpoint_fit72_v1"
DEFAULT_OUTPUT = ROOT/"results/phase2_mujoco/rdao_closure_periodic_age_forensics_v1"
PROTECTED = (
    H80/"episodes.csv",
    H80/"episode_traces.jsonl.gz",
    V2/"paired_rdao_v2_viewpoint.csv",
    V2/"v2_traces.jsonl.gz",
    V2/"summary.json",
)


def traces_from_saved_baseline(path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]
    index = {}
    for rec in records:
        world, schedule, method, seed = rec["key"]
        key = (world, int(schedule), method, int(seed))
        if key in index:
            raise ValueError(f"Duplicate baseline trace {key}")
        index[key] = rec
    if len(index) != 288 or len(records) != 288:
        raise ValueError("Expected 288 frozen baseline traces")
    return index


def traces_from_saved_v2(path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]
    index = {}
    for rec in records:
        world, schedule, seed = rec["key"]
        key = (world, int(schedule), int(seed))
        if rec.get("variant") != "rdao_v2_viewpoint" or key in index:
            raise ValueError(f"Unexpected saved v2 trace {key}")
        index[key] = rec["trace"]
    if len(index) != 72 or len(records) != 72:
        raise ValueError("Expected 72 frozen v2 traces")
    return index


def observation_steps(trace):
    return [int(f["step"]) for f in trace["steps"]
            if f["observation_granted"]]


def frame_index(trace):
    return {int(f["step"]): f for f in trace["steps"]}


def initial_shared_pose_missed_scans(v2_trace, baseline_trace):
    """Time steps with same pre-action observation viewpoint and baseline scan.

    Both traces store position/yaw AFTER action in frame t. Therefore
    the viewpoint at the START of t is the t-1 frame's pose/yaw. Do
    NOT compare the positions recorded at t, which can already differ
    because of sensing and action at t.
    """
    v2 = frame_index(v2_trace)
    base = frame_index(baseline_trace)
    shared = []
    for step in sorted(set(v2) & set(base)):
        if step < 1:
            continue
        vb, bb = v2.get(step-1), base.get(step-1)
        if vb is None or bb is None:
            continue
        if (vb.get("position") != bb.get("position") or
                vb.get("heading_yaw") != bb.get("heading_yaw")):
            break
        # Once an earlier executed action differs, future action outcomes
        # may reconverge; preserve only the initial common-action prefix.
        if step > 1 and (
                vb.get("action") != bb.get("action") or
                vb.get("moved") != bb.get("moved") or
                vb.get("blocked") != bb.get("blocked")):
            break
        if (bool(base[step]["observation_granted"]) and
                not bool(v2[step]["observation_granted"])):
            diag = v2[step].get("rdao") or {}
            if diag.get("remaining_observation_budget") in (0, None):
                continue
            shared.append({
                "step": step,
                "rdao_score": diag.get("score"),
                "rdao_threshold": diag.get("threshold"),
                "rdao_reason": diag.get("reason"),
                "rdao_v2_deferred_candidates": sum(bool(
                    x.get("v2_deferred")) for x in
                    diag.get("candidate_regions") or []),
            })
    return shared


def changed_action(frame_a, frame_b):
    return any(frame_a.get(k) != frame_b.get(k) for k in (
        "position", "heading_yaw", "action", "moved", "blocked"))


def row_summary(key, v2row, comparator, baserow, v2trace, basetrace):
    v2obs, otherobs = observation_steps(v2trace), observation_steps(basetrace)
    iv2, ib = frame_index(v2trace), frame_index(basetrace)
    first_obs = first_observation_difference(v2trace, basetrace)
    first_action = _first_difference(v2trace, basetrace)
    common = initial_shared_pose_missed_scans(v2trace, basetrace)
    first_denial = (next((x["step"] for x in common), None))
    return {
        "world_identity": key[0], "schedule": key[1], "seed": key[2],
        "comparator": comparator,
        "v2_success": _bool(v2row["variant_success"]),
        "comparator_success": _bool(baserow["success"]),
        "v2_steps_h80": int(v2row["variant_elapsed_steps"]),
        "comparator_steps_h80": int(baserow["elapsed_steps"]),
        "v2_observations": int(v2row["variant_observations"]),
        "comparator_observations": int(baserow["observation_count"]),
        "v2_observation_steps": json.dumps(v2obs),
        "comparator_observation_steps": json.dumps(otherobs),
        "first_observation_schedule_difference": first_obs or "",
        "first_action_or_pose_difference": first_action or "",
        "first_shared_pose_baseline_only_observation": first_denial or "",
        "shared_pose_baseline_only_steps": json.dumps([
            x["step"] for x in common]),
        "common_preaction_missed_scan_count": len(common),
        "hypothesis_status": (
            "candidate_same_viewpoint_missed_scan_precedes_or_matches_divergence"
            if common and (first_action is None or first_denial <= first_action)
            else "NO_COMMON_PREFIX_SCAN_CAUSE_IDENTIFIED"),
    }


def timeline_rows(key, policy, a, b):
    av, bv = frame_index(a), frame_index(b)
    rows = []
    for step in sorted(set(av) | set(bv)):
        x, y = av.get(step), bv.get(step)
        if x is None or y is None:
            continue
        r = x.get("rdao") or {}
        best = (sorted(r.get("candidate_regions") or [],
                       key=lambda z: float(z.get("score") or 0),
                       reverse=True) or [None])[0]
        rows.append({
            "world_identity": key[0], "schedule": key[1],
            "comparator": policy, "step": step,
            "v2_observed": bool(x["observation_granted"]),
            "baseline_observed": bool(y["observation_granted"]),
            "v2_previous_pose": json.dumps(av[step-1]["position"])
                if step-1 in av else "",
            "baseline_previous_pose": json.dumps(bv[step-1]["position"])
                if step-1 in bv else "",
            "same_pose_and_yaw_at_start":
                step-1 in av and step-1 in bv and
                av[step-1]["position"] == bv[step-1]["position"] and
                av[step-1]["heading_yaw"] == bv[step-1]["heading_yaw"],
            "v2_action": json.dumps(x.get("action")),
            "baseline_action": json.dumps(y.get("action")),
            "v2_position_after": json.dumps(x.get("position")),
            "baseline_position_after": json.dumps(y.get("position")),
            "actual_action_or_pose_diverged": changed_action(x, y),
            "v2_rdao_reason": r.get("reason"),
            "v2_rdao_score": r.get("score"),
            "v2_rdao_threshold": r.get("threshold"),
            "v2_nominal_first_action": json.dumps(
                (r.get("nominal_route") or [None])[0]),
            "v2_candidate_region_count": len(r.get("candidate_regions") or []),
            "v2_best_region": json.dumps(best.get("region"))
                if best is not None else "",
            "v2_best_route_relevance": best.get("route_relevance")
                if best is not None else "",
            "v2_best_predicted_visibility": best.get("visibility")
                if best is not None else "",
            "v2_deferred_regions": sum(bool(z.get("v2_deferred"))
                for z in r.get("candidate_regions") or []),
            "v2_blocked": bool(x.get("blocked")),
            "baseline_blocked": bool(y.get("blocked")),
            "v2_emergency_intervention": bool(x.get("emergency_intervention")),
            "baseline_emergency_intervention": bool(
                y.get("emergency_intervention")),
        })
    return rows


class DiagnosticV2ForcedScan(RDAOv2ViewpointController):
    """Post-hoc force at an indexed decision step; never deployed as a policy."""
    force_step = None
    intervention = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.forced = False
        self.suppressed = False

    def decide(self, step, position):
        original_cooldowns = dict(self.region_last_attempted)
        decision = super().decide(step, position)
        diag = decision["rdao"]
        if step == self.force_step:
            if decision["observation_granted"] or self.forced:
                raise RuntimeError("Forced step was naturally observed or repeated")
            if self.remaining is not None and self.remaining <= 0:
                raise RuntimeError("Forced observation exceeds remaining cap")
            route = diag["nominal_route"]
            cost = self._route_cost(route)
            if not math.isfinite(cost):
                cost = float(self.memory.grid.size)
            diag["_pre_observation"] = {
                "grid": self.memory.grid.copy(), "route": route, "cost": cost,
                "position": tuple(map(int, position)),
                "heading_yaw": float(self.heading_yaw),
            }
            diag.update(requested=True, granted=True, intervention_forced=True,
                        reason="RETROSPECTIVE_FORCED_REAL_SENSOR_SCAN")
            decision["observation_requested"] = True
            decision["observation_granted"] = True
            self.requests += 1
            self.forced = True
        elif (self.intervention == "swap" and self.forced and
              not self.suppressed and decision["observation_granted"]):
            self.region_last_attempted.clear()
            self.region_last_attempted.update(original_cooldowns)
            self.requests -= 1
            diag.pop("_pre_observation", None)
            diag.update(requested=False, granted=False,
                        intervention_suppressed=True,
                        reason="RETROSPECTIVE_SWAP_NEXT_NATURAL_SCAN")
            decision["observation_requested"] = False
            decision["observation_granted"] = False
            self.suppressed = True
        return decision


def simulate_v2(payload, schedule, *, force_step=None, intervention=None):
    original = evaluator.RDAOController
    if force_step is None:
        controller = RDAOv2ViewpointController
    else:
        class BoundController(DiagnosticV2ForcedScan):
            pass
        BoundController.force_step = int(force_step)
        BoundController.intervention = intervention
        controller = BoundController
    evaluator.RDAOController = controller
    try:
        return evaluator._instrumented_case(payload, int(schedule), "rdao_v1")
    finally:
        evaluator.RDAOController = original


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--intervene", action="store_true",
                        help="Run causal one-scan extra/swap replays")
    parser.add_argument("--max-interventions-per-case", type=int, default=2)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.max_interventions_per_case < 1 or args.max_interventions_per_case > 5:
        parser.error("max interventions per case must be 1..5")
    if args.output.exists():
        raise FileExistsError(f"Will not overwrite existing output: {args.output}")

    base_rows = _load_csv(H80/"episodes.csv")
    v2_rows = _load_csv(V2/"paired_rdao_v2_viewpoint.csv")
    baselines = {(r["world_identity"], int(r["schedule"]), r["method"],
                  int(r["seed"])): r for r in base_rows}
    v2index = {_key(row): row for row in v2_rows}
    bt = traces_from_saved_baseline(H80/"episode_traces.jsonl.gz")
    vt = traces_from_saved_v2(V2/"v2_traces.jsonl.gz")
    if (len(baselines) != 288 or len(v2index) != 72 or
            set(bt) != set(baselines) or set(vt) != set(v2index)):
        raise RuntimeError("Frozen matched H80 or v2 evidence mismatch")
    hashes = {str(p.relative_to(ROOT)): _sha(p) for p in PROTECTED}
    preserved = navigation.verify_preserved_prefix()
    worlds = {x["identity"]: x for x in navigation.admitted_worlds()}
    if len(worlds) != 36 or set(worlds) != {k[0] for k in v2index}:
        raise RuntimeError("Frozen FIT world identities do not match")

    selected = [
        key for key, v2 in sorted(v2index.items())
        if not _bool(v2["variant_success"]) and any(
            _bool(baselines[(key[0], key[1], policy, key[2])]["success"])
            for policy in ("periodic", "age")
        )
    ]
    if len(selected) != 8:
        raise RuntimeError(f"Expected 8 v2-baseline failure contrast episodes; got {len(selected)}")
    summaries, timelines, replays = [], [], []
    for key in selected:
        for policy in ("periodic", "age"):
            base = baselines[(key[0], key[1], policy, key[2])]
            if not _bool(base["success"]):
                continue
            saved = bt[(key[0], key[1], policy, key[2])]
            v2 = vt[key]
            summary = row_summary(key, v2index[key], policy, base, v2, saved)
            summaries.append(summary)
            timelines.extend(timeline_rows(key, policy, v2, saved))

        if not args.intervene:
            continue
        # Pre-register at most two unique same-viewpoint baseline-only
        # observations from the initial common-action prefix. No
        # successful-baseline sensor values are read by the controller.
        all_targets = sorted({
            x for policy in ("periodic", "age")
            for x in observation_steps(bt[(key[0], key[1], policy, key[2])])
            if x in set(
                y["step"] for y in initial_shared_pose_missed_scans(
                    vt[key], bt[(key[0], key[1], policy, key[2])]))
        })[:args.max_interventions_per_case]
        if not all_targets:
            replays.append({
                "world_identity": key[0], "schedule": key[1],
                "seed": key[2], "intervention": "NONE",
                "status": "NO_SHARED_VIEWPOINT_BASELINE_ONLY_SCAN_BEFORE_DIVERGENCE",
            })
            continue
        original_row, original_trace = simulate_v2(worlds[key[0]], key[1])
        actual = _metrics(original_row)
        savedmetrics = v2index[key]
        if (actual["success"] != _bool(savedmetrics["variant_success"])
            or actual["elapsed_steps"] != int(savedmetrics["variant_elapsed_steps"])
            or actual["observations"] != int(savedmetrics["variant_observations"])):
            raise RuntimeError(f"Frozen v2 outcome not reproduced: {key}")
        _compare_trace(vt[key], original_trace)
        for step in all_targets:
            for mode in ("extra", "swap"):
                row, trace = simulate_v2(
                    worlds[key[0]], key[1], force_step=step, intervention=mode)
                _compare_trace(vt[key], trace, before_step=step)
                injected = next((x for x in trace["steps"]
                                 if int(x["step"]) == step), None)
                if (injected is None or not injected.get("observation_granted")
                    or not (injected.get("rdao") or {}).get("intervention_forced")):
                    raise RuntimeError("Realized forced scan not found")
                result = _metrics(row)
                if result["observations"] > 20 or (
                    not _bool(row["g1_shield_query_count_valid"]) or
                    int(row["g1_unselected_action_shield_queries"]) != 0):
                    raise RuntimeError("Action shield or observation budget violated")
                effect = injected["rdao"].get("observation_effect")
                if not effect:
                    raise RuntimeError("No memory effect from the real forced scan")
                suppressed = [int(x["step"]) for x in trace["steps"]
                    if (x.get("rdao") or {}).get("intervention_suppressed")]
                record = {
                    "world_identity": key[0], "schedule": key[1], "seed": key[2],
                    "intervention": mode, "forced_step": step,
                    "status": "ACTUAL_REAL_SENSOR_INTERVENTION",
                    "baseline_v2_success": actual["success"],
                    "new_success": result["success"],
                    "baseline_v2_steps_h80": actual["elapsed_steps"],
                    "new_steps_h80": result["elapsed_steps"],
                    "baseline_v2_observations": actual["observations"],
                    "new_observations": result["observations"],
                    "baseline_v2_distance_m": actual["travel_distance_m"],
                    "new_distance_m": result["travel_distance_m"],
                    "new_unwanted_contacts": result["unwanted_contacts"],
                    "real_sensor_visible_cells": effect["visible_cell_count"],
                    "real_memory_changed_cells": effect["memory_changed_cell_count"],
                    "suppressed_natural_steps": json.dumps(suppressed),
                    "actual_first_action_or_pose_divergence":
                        _first_difference(vt[key], trace),
                }
                replays.append(record)
                print("Intervention", key, step, mode, "goal", result["success"],
                      "observations", result["observations"], flush=True)

    if ({str(p.relative_to(ROOT)): _sha(p) for p in PROTECTED} != hashes
            or navigation.verify_preserved_prefix() != preserved):
        raise RuntimeError("Frozen evidence altered during diagnostic")
    args.output.mkdir(parents=True)
    _write_csv(args.output/"paired_failure_cases.csv", summaries)
    _write_csv(args.output/"paired_failure_step_timeline.csv", timelines)
    if replays:
        _write_csv(args.output/"forced_one_scan_replays.csv", replays)
    summary = {
        "status": "RDAO_RETROSPECTIVE_CLOSURE_NOT_ONLINE_NOT_HELD_OUT",
        "v2_versus_successful_baselines": len(selected),
        "distinct_maze_identities": len({x[0] for x in selected}),
        "successful_baseline_pair_rows": len(summaries),
        "causal_interventions_executed": sum(x.get("status") ==
            "ACTUAL_REAL_SENSOR_INTERVENTION" for x in replays),
        "rescued_interventions": sum(x.get("new_success") is True for x in
            replays if x.get("status") == "ACTUAL_REAL_SENSOR_INTERVENTION"),
        "prior_saved_evidence_hashes": hashes,
        "phase15_preservation": preserved,
        "limitations": [
            "Missed observation is NOT a causal mechanism without a realized intervention.",
            "Baseline and RDAO paths diverge, so same step does NOT mean same viewpoint.",
            "Forced steps are selected post hoc and may not reproduce a full baseline strategy.",
            "A one-scan failure to rescue does not prove that scanning timing is irrelevant.",
            "Extra and swap may spend different realized observation counts due to feedback.",
            "Never use baseline observations or privileged scene truth in online policies.",
            "Two pedestrian schedules of one maze are correlated, not independent evidence.",
            "H80 is right-censored; distance in failures is not goal-reaching route length.",
        ],
    }
    (args.output/"summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, allow_nan=False)+"\n",
        encoding="utf-8")
    print(json.dumps({
        "output": str(args.output), "failure_episode_keys": selected,
        "successful_pairs": len(summaries),
        "interventions": summary["causal_interventions_executed"],
        "rescued": summary["rescued_interventions"],
    }, indent=2))


if __name__ == "__main__":
    main()
