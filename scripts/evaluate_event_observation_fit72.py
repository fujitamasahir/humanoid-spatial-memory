"""Matched FIT72 evaluation of Periodic+Event and Age+Event candidates (A).

Prospective policy uses only past selected-action REJECTION or past observed-map
NO ROUTE as event signals; it never reads the real world geometry or emergency
sensor to decide memory scans. The frozen Periodic/Age update laws, G1 planner,
pedestrian tracking, actual selected-action shield, emergency sensing, MuJoCo
scene, ray geometry, cap20 and motion policy all remain exactly unchanged.

For EACH 36-maze x 2-correlated-schedule key:
1. Reproduce frozen Periodic and Age baseline metrics+semantic trace.
2. Run Periodic+Event and Age+Event at the SAME key/config/seed.
3. Save outcomes, observation/event history, exact traces and pair summaries.
4. Check all original evidence hashes and Phase1.5 preserved-prefix integrity.

This FIT study is exploratory, not held-out confirmation. No RDAO-based
event information is used. No threshold tuning or world-specific rules.

Usage:
  .venv/bin/python scripts/evaluate_event_observation_fit72.py --max-cases 2 \
    --output results/phase2_mujoco/event_observation_smoke2_v1
  .venv/bin/python scripts/evaluate_event_observation_fit72.py
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/"src"), str(ROOT/"scripts")]

import evaluate_phase2_61ray_emergency_safety_full_288 as base
import evaluate_rdao_phase2 as rdao_evaluator
import phase2_mujoco_navigation as navigation
from evaluate_rdao_one_shot_interventions import (
    _bool, _compare_trace, _load_csv, _metrics, _sha, _write_csv,
)
from evaluate_rdao_online_safe_gate_screen import _jsonable
from spatial_memory.event_observation import (
    EventObservationParameters, EventTriggeredObservationController,
)

BASE = ROOT/"results/phase2_mujoco/g1_forward_first_61ray_emergency_safety_full_288_v1"
DEFAULT_OUTPUT = ROOT/"results/phase2_mujoco/event_observation_fit72_v1"
PROTECTED = (
    BASE/"episodes.csv",
    base.BASELINE/"provenance.json",
    BASE/"episode_traces.jsonl.gz",
    BASE/"artifact_manifest.json",
    base.BASELINE/"artifact_manifest.json",
)


def run_candidate(payload, schedule, method, config):
    """Only the observation controller and public-feedback callbacks change.

    Original evaluator callbacks perform all actual sensing/motion/safety.
    Patches are single-threaded, scoped to this one run, restored on errors.
    """
    if method not in ("periodic", "age"):
        raise ValueError(f"Not a baseline observation policy: {method}")
    original_episode = base.run_episode
    context = {"controller": None}

    def injected_episode(scenario, run_config, mode, **kwargs):
        if mode != method:
            raise RuntimeError("Controller and benchmark policy disagree")

        def factory(initial, mode, *, interval, radius, parameters,
                    max_observations):
            agent = EventTriggeredObservationController(
                initial, mode, interval=interval, radius=radius,
                parameters=parameters, max_observations=max_observations,
                event_parameters=EventObservationParameters())
            context["controller"] = agent
            return agent

        previous_check = kwargs.get("_action_checker")
        previous_plan = kwargs.get("_g1_planner")
        if previous_check is None or previous_plan is None:
            raise RuntimeError("Required actual G1 planner/shield was not supplied")

        def selected_action_check(world, position, action, yaw):
            result = previous_check(world, position, action, yaw)
            if bool(result[0]):
                context["controller"].note_selected_action_rejected(world.step)
            return result

        def observed_map_plan(grid, position, goal, unknown, yaw, blocked):
            route = previous_plan(grid, position, goal, unknown, yaw, blocked)
            if not route:
                # NORMAL observed-map G1 planner output ONLY. Do not use
                # scene occupancy or unseen action shield queries.
                context["controller"].note_no_route(
                    # Run-loop world.step is not passed to this planner;
                    # count the decision's most recent time through a
                    # private controller counter set in decide.
                    context["controller"].last_decision_step)
            return route

        kwargs["_controller_factory"] = factory
        kwargs["_action_checker"] = selected_action_check
        kwargs["_g1_planner"] = observed_map_plan
        return original_episode(scenario, run_config, mode, **kwargs)

    base.run_episode = injected_episode
    try:
        row, trace = base.run_case(
            payload, schedule, method,
            json.loads(json.dumps(config)), with_safety=True)
    finally:
        base.run_episode = original_episode
    agent = context["controller"]
    if agent is None:
        raise RuntimeError("Candidate observer was not initialized")
    row["event_scheduler_total_ms"] = agent.scheduler_decision_total_ns / 1e6
    row["event_observation_count"] = agent.event_observation_count
    row["ordinary_observation_count"] = agent.ordinary_observation_count
    row["feedback_blocked_count"] = agent.feedback_blocked_count
    row["feedback_no_route_count"] = agent.feedback_no_route_count
    row["event_observation_decision_count"] = len(agent.decisions)
    row["event_observation_decision_history"] = agent.decisions
    row["event_observation_log"] = agent.observation_log
    row["event_policy"] = "event_"+method
    row["event_rule"] = "selected_action_rejected_or_observed_map_no_route"
    return row, trace


def make_pair_row(key, method, reference, candidate):
    old, new = _metrics(reference), _metrics(candidate)
    return {
        "world_identity":key[0], "schedule":key[1], "seed":key[2],
        "reference_method":method, "candidate_method":"event_"+method,
        "reference_success":old["success"], "candidate_success":new["success"],
        "reference_steps_h80":old["elapsed_steps"],
        "candidate_steps_h80":new["elapsed_steps"],
        "reference_distance_m":old["travel_distance_m"],
        "candidate_distance_m":new["travel_distance_m"],
        "reference_observations":old["observations"],
        "candidate_observations":new["observations"],
        "reference_memory_rays":old["observations"] * 61,
        "candidate_memory_rays":new["observations"] * 61,
        "reference_unwanted_contacts":old["unwanted_contacts"],
        "candidate_unwanted_contacts":new["unwanted_contacts"],
        "reference_emergency_scans":int(reference["emergency_safety_scans"]),
        "candidate_emergency_scans":int(candidate["emergency_safety_scans"]),
        "reference_emergency_rays":int(reference["emergency_safety_raycasts"]),
        "candidate_emergency_rays":int(candidate["emergency_safety_raycasts"]),
        "reference_emergency_interventions":
            old["emergency_interventions"],
        "candidate_emergency_interventions":
            new["emergency_interventions"],
        "candidate_triggered_scans":int(candidate["event_observation_count"]),
        "candidate_ordinary_scans":int(candidate["ordinary_observation_count"]),
        "candidate_blocked_feedback_count":
            int(candidate["feedback_blocked_count"]),
        "candidate_no_route_feedback_count":
            int(candidate["feedback_no_route_count"]),
        "candidate_scheduler_total_ms":float(candidate["event_scheduler_total_ms"]),
        "candidate_episode_wall_seconds":
            float(candidate["episode_wall_time_seconds"]),
        "reference_episode_wall_seconds":
            float(reference["episode_wall_time_seconds"]),
    }


def aggregate_pairs(rows):
    if not rows:
        raise ValueError("No matched event observer episodes")
    old_success = [x for x in rows if x["reference_success"]]
    new_success = [x for x in rows if x["candidate_success"]]
    common_success = [x for x in rows if x["reference_success"] and
                      x["candidate_success"]]
    def avg(field):
        return statistics.mean(float(x[field]) for x in rows)
    def delta(field):
        return sum(float(x["candidate_"+field]) -
                   float(x["reference_"+field]) for x in rows)
    return {
        "episodes":len(rows), "independent_maze_layouts":
            len({x["world_identity"] for x in rows}),
        "baseline_successes":len(old_success),
        "candidate_successes":len(new_success),
        "rescued_failures":sum(not x["reference_success"]
                              and x["candidate_success"] for x in rows),
        "harmed_successes":sum(x["reference_success"]
                              and not x["candidate_success"] for x in rows),
        "baseline_mean_observations":avg("reference_observations"),
        "candidate_mean_observations":avg("candidate_observations"),
        "total_delta_observations":delta("observations"),
        "baseline_mean_memory_rays":avg("reference_memory_rays"),
        "candidate_mean_memory_rays":avg("candidate_memory_rays"),
        "total_delta_memory_rays":delta("memory_rays"),
        "baseline_mean_censored_steps":avg("reference_steps_h80"),
        "candidate_mean_censored_steps":avg("candidate_steps_h80"),
        "total_delta_censored_steps":delta("steps_h80"),
        "baseline_mean_distance_m":avg("reference_distance_m"),
        "candidate_mean_distance_m":avg("candidate_distance_m"),
        "total_delta_distance_m":delta("distance_m"),
        "baseline_mean_emergency_scans":avg("reference_emergency_scans"),
        "candidate_mean_emergency_scans":avg("candidate_emergency_scans"),
        "baseline_mean_emergency_rays":avg("reference_emergency_rays"),
        "candidate_mean_emergency_rays":avg("candidate_emergency_rays"),
        "candidate_mean_scheduler_ms":avg("candidate_scheduler_total_ms"),
        "baseline_mean_wall_time_seconds":avg("reference_episode_wall_seconds"),
        "candidate_mean_wall_time_seconds":avg("candidate_episode_wall_seconds"),
        "candidate_event_triggered_scans":sum(
            x["candidate_triggered_scans"] for x in rows),
        "candidate_blocked_feedback":sum(
            x["candidate_blocked_feedback_count"] for x in rows),
        "candidate_no_route_feedback":sum(
            x["candidate_no_route_feedback_count"] for x in rows),
        "baseline_unwanted_contact_pairs":sum(
            x["reference_unwanted_contacts"] for x in rows),
        "candidate_unwanted_contact_pairs":sum(
            x["candidate_unwanted_contacts"] for x in rows),
        "paired_common_success": {
            "episodes":len(common_success),
            "steps_better":sum(
                x["candidate_steps_h80"] < x["reference_steps_h80"]
                for x in common_success),
            "steps_equal":sum(
                x["candidate_steps_h80"] == x["reference_steps_h80"]
                for x in common_success),
            "steps_worse":sum(
                x["candidate_steps_h80"] > x["reference_steps_h80"]
                for x in common_success),
            "distance_better":sum(
                x["candidate_distance_m"] < x["reference_distance_m"]
                for x in common_success),
            "distance_equal":sum(
                x["candidate_distance_m"] == x["reference_distance_m"]
                for x in common_success),
            "distance_worse":sum(
                x["candidate_distance_m"] > x["reference_distance_m"]
                for x in common_success),
            "total_delta_steps":sum(
                x["candidate_steps_h80"]-x["reference_steps_h80"]
                for x in common_success),
            "total_delta_distance_m":sum(
                x["candidate_distance_m"]-x["reference_distance_m"]
                for x in common_success),
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-cases", type=int, default=None,
                        help="First N world x schedule pairs (both policies)")
    parser.add_argument("--output",type=Path,default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.max_cases is not None and args.max_cases < 1:
        parser.error("--max-cases must be positive")
    if args.output.exists():
        raise FileExistsError(f"Will not overwrite saved result {args.output}")
    # The config provenance comes from the preceding, fully hashed
    # 288-row G1 experiment, but the COMPARISON ARM MUST be the
    # preserved 61-ray Emergency Safety H80 matrix, not that predecessor.
    _, _, provenance, _ = base.load_baseline()
    frozen = base.frozen_config(provenance)
    baseline_rows = _load_csv(BASE/"episodes.csv")
    baseline_index = {
        (row["world_identity"], int(row["schedule"]),
         row["method"], int(row["seed"])): row
        for row in baseline_rows
    }
    source_hashes = {str(p.relative_to(ROOT)):_sha(p) for p in PROTECTED}
    prefix = navigation.verify_preserved_prefix()
    worlds = {x["identity"]:x for x in navigation.admitted_worlds()}
    keys = sorted({
        (x["world_identity"],int(x["schedule"]),int(x["seed"]))
        for x in baseline_rows if x["method"] in ("periodic","age")})
    if (len(worlds) != 36 or len(keys) != 72 or
        len(baseline_rows) != 288 or len(baseline_index) != 288 or
        set(worlds) != {x[0] for x in keys} or
        set(row["method"] for row in baseline_rows) !=
            {"periodic", "age", "static", "uncertainty"}):
        raise RuntimeError("Missing 72 paired original FIT cases")
    with gzip.open(BASE/"episode_traces.jsonl.gz","rt",encoding="utf-8") as stream:
        traces = [json.loads(s) for s in stream if s.strip()]
    saved_traces = {(x["key"][0],int(x["key"][1]),x["key"][2],
                     int(x["key"][3])): x for x in traces}
    if len(saved_traces) != 288 or len(traces) != 288:
        raise RuntimeError("Expected complete frozen 288 trace matrix")
    if args.max_cases is not None:
        keys = keys[:args.max_cases]
    output, logs = [], []
    for i, key in enumerate(keys, 1):
        payload = worlds[key[0]]
        for method in ("periodic","age"):
            refkey = (key[0],key[1],method,key[2])
            reference = baseline_index[refkey]
            reproduced, baseline_trace = base.run_case(
                payload,key[1],method,json.loads(json.dumps(frozen)),with_safety=True)
            if rdao_evaluator._signature(reference) != rdao_evaluator._signature(reproduced):
                raise RuntimeError(f"Frozen baseline metric reproduction failed {refkey}")
            _compare_trace(saved_traces[refkey], base._jsonable_row(baseline_trace))
            candidate,trace = run_candidate(payload,key[1],method,frozen)
            if (not _bool(candidate["g1_shield_query_count_valid"])
                or int(candidate["g1_unselected_action_shield_queries"]) != 0
                or int(candidate["observation_count"]) > 20
                or int(candidate["observation_count"]) !=
                        1 + len(candidate["event_observation_log"])):
                raise RuntimeError(f"Event candidate safety/count invariant violated {refkey}")
            scan_steps=[int(frame["step"]) for frame in trace["steps"]
                        if frame["observation_granted"]]
            logged_steps=[int(e["step"]) for e in
                          candidate["event_observation_log"]]
            if scan_steps != logged_steps:
                raise RuntimeError(f"Event realized observation steps differ from log {refkey}")
            if candidate["event_observation_count"] + candidate[
                    "ordinary_observation_count"] != len(scan_steps):
                raise RuntimeError("Event scan classification did not partition scans")
            output.append(make_pair_row(key, method, reference, candidate))
            logs.append({
                "key":[*key,method],
                "variant":"event_"+method,
                "candidate_row":_jsonable(candidate),
                "candidate_trace":trace,
            })
        print(f"Completed world/schedule {i}/{len(keys)}: {key[:2]}",
              flush=True)
    if (navigation.verify_preserved_prefix() != prefix or
        {str(p.relative_to(ROOT)):_sha(p) for p in PROTECTED} != source_hashes):
        raise RuntimeError("Protected historical evidence changed during study")
    summary = {
        "status":"EVENT_TRIGGERED_PERIODIC_AGE_DEV_FIT_NOT_HELD_OUT",
        "worlds":len({x["world_identity"] for x in output}),
        "episodes_per_arm":len(keys),
        "event_periodic_vs_periodic":aggregate_pairs(
            [x for x in output if x["reference_method"]=="periodic"]),
        "event_age_vs_age":aggregate_pairs(
            [x for x in output if x["reference_method"]=="age"]),
        "candidate_policy": {
            "event_signals":[
                "past selected-action true-shield rejection",
                "past observed-map planner returned no route"],
            "periodic_due":"steps since last authorized observation >= frozen interval",
            "age_due":"unaltered frozen local stale-fraction rule",
            "event_min_steps_after_any_scan":EventObservationParameters(
                ).min_steps_since_any_observation,
            "event_min_steps_after_event_scan":EventObservationParameters(
                ).min_steps_since_event_observation,
            "max_memory_observations":20,
            "emergency_sensing_and_action_shield_unchanged":True,
        },
        "source_sha256":source_hashes,
        "phase15_preservation":prefix,
        "limitations":[
            "Development FIT72 alone cannot establish generalization.",
            "Paired schedules of the same maze are correlated.",
            "No hidden occupancy or emergency sensor output is used by this event policy.",
            "Total emergency ray scans must also be reported.",
            "A reduction in total travel due to newly failed episodes is NOT a successful route-efficiency improvement.",
            "Fewer memory scans caused by early horizon completion or failure are not equivalent in utility.",
            "Do not optimize event cooldown, threshold or triggers on this same repeatedly inspected development set.",
        ],
    }
    args.output.mkdir(parents=True)
    _write_csv(args.output/"event_observation_pairs.csv",output)
    with gzip.open(args.output/"event_observation_traces.jsonl.gz","wt",
                   encoding="utf-8") as stream:
        for item in logs:
            stream.write(json.dumps(_jsonable(item),sort_keys=True,
                                    allow_nan=False)+"\n")
    (args.output/"summary.json").write_text(
        json.dumps(summary,sort_keys=True,indent=2,allow_nan=False)+"\n",
        encoding="utf-8")
    print(json.dumps({
        "result_dir":str(args.output),
        "event_periodic":summary["event_periodic_vs_periodic"],
        "event_age":summary["event_age_vs_age"],
    },indent=2,allow_nan=False))


if __name__=="__main__":
    main()
