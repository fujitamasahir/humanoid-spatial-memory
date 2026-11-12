"""Screen a pre-specified ONLINE observed-safe route-inertia rule in 72 Phase 2 fit episodes.

The input world identity, schedule, success and oracle/shadow occupancy
NEVER participate in decisions. At EVERY *naturally authorized* RDAO
memory observation, the rule may retain the first pre-update forward
action for one step if:
  (a) the NEW default G1 planner wants to turn instead;
  (b) the destination cell is observed FREE in the newly updated map;
  (c) the new observed map permits the old G1 swept footprint;
  (d) no prior selected-action blocked feedback forbids it.

The independent Emergency Safety controller and the selected-action
actual-geometry collision shield are NOT bypassed. A regular G1 planner
is used for both maps with identical public pedestrian/static context.
No observation budget, memory scheduler or geometry configuration
changes. No unselected shield queries or hidden ground truth.

Two prospective conditions (applied without any special step/world):
    first: override at most the first eligible event per episode.
    every: override every eligible event independently.

The original 72-episode RDAO fit replay is verified before running
interventions. This is DEVELOPMENT SCREENING ONLY, NOT HELD OUT.
"""
from __future__ import annotations

import argparse
from collections import Counter
import gzip
import json
import math
from pathlib import Path
import statistics
import sys
from time import perf_counter_ns

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

import evaluate_rdao_phase2 as evaluator
import phase2_mujoco_navigation as navigation
from evaluate_rdao_one_shot_interventions import (
    _bool, _compare_trace, _first_difference, _key, _load_csv,
    _metrics, _read_saved_traces, _sha, _write_csv,
)
from evaluate_rdao_safe_prior_action_gate import select_safe_preupdate_action
from spatial_memory.rdao import RDAOController

PRIMARY = ROOT / "results/phase2_mujoco/rdao_v1_phase2_evaluation"
DEFAULT_OUT = ROOT / "results/phase2_mujoco/rdao_v1_online_safe_gate_fit72_screen_v1"
POLICIES = ("first", "every")


class CandidateOnlineGateRDAO(RDAOController):
    """Capture the pre-observation map only on naturally granted observations."""

    def decide(self, step, position):
        decision = super().decide(step, position)
        if decision["observation_granted"]:
            self.gate_pre_map = self.memory.grid.copy()
            self.gate_pre_step = int(step)
            self.gate_pre_position = tuple(position)
        else:
            self.gate_pre_step = None
        return decision


def online_gate_decision(before, after, start, goal, kwargs, original_planner,
                         *, prior_overrides: int, policy: str):
    """Pure decision-rule helper; no step or world identity is inspected."""
    if policy not in POLICIES:
        raise ValueError(f"Invalid gate policy: {policy}")
    if before.shape != after.shape:
        raise ValueError("Pre/post memory shapes do not match")
    kwargs = dict(kwargs)
    new_route = original_planner(after, start, goal, **kwargs)
    latest = new_route[0] if new_route else None
    result = {
        "override_applied": False, "new_action": latest,
        "prior_action": None, "chosen_action": latest,
        "guard": None, "changed_cells": int((before != after).sum()),
    }
    if policy == "first" and prior_overrides:
        result["guard"] = "first_override_already_used"
        return new_route, result
    if not result["changed_cells"]:
        result["guard"] = "no_new_map_cells"
        return new_route, result
    if latest is None or latest[0] != "turn":
        result["guard"] = "new_first_action_not_turn"
        return new_route, result

    # Avoid calculating the new plan twice. The imported helper also
    # checks footprint safety, observed-free destination, and feedback.
    def cached_planner(grid, p, goal_cell, **kw):
        if grid is after:
            return new_route
        return original_planner(grid, p, goal_cell, **kw)

    planner_kwargs = {
        "static_obstacle_cells": kwargs.get("static_obstacle_cells", frozenset()),
        "pedestrian_context": kwargs.get("pedestrian_context", None),
        "step": kwargs.get("step", 0),
    }
    route, detail = select_safe_preupdate_action(
        before, after, start, goal,
        heading=kwargs["heading"], unknown=kwargs["unknown"],
        local_extents=kwargs["local_extents"],
        cell_size=kwargs["cell_size"],
        blocked_actions=kwargs["blocked_actions"],
        old_planner=cached_planner, planner_kwargs=planner_kwargs,
    )
    result.update(detail)
    return route, result


def run_candidate(payload, schedule, policy, *, allowed_gate_steps=None):
    """Attach online gate; optional step allowlist is diagnostic ONLY.

    allowed_gate_steps=None preserves the original world-agnostic algorithm
    byte-for-byte at the decision site. A supplied allowlist forces the
    normal updated-map G1 plan at other times, even if an online candidate
    would otherwise pass. Such step-specific counterfactuals are deliberately
    evaluator-guided, NOT deployable online policies.
    """
    if allowed_gate_steps is not None:
        allowed_gate_steps = frozenset(int(v) for v in allowed_gate_steps)
    original_controller = evaluator.RDAOController
    original_planner = evaluator.base.plan_g1_default_policy
    state = {"events": [], "overrides": 0, "gate_ns": 0}

    def plan_with_gate(grid, start, goal, **kwargs):
        ctx = evaluator.CURRENT
        agent = ctx["controller"] if ctx else None
        if not isinstance(agent, CandidateOnlineGateRDAO):
            return original_planner(grid, start, goal, **kwargs)
        if getattr(agent, "gate_pre_step", None) != getattr(agent, "current_step", -1):
            return original_planner(grid, start, goal, **kwargs)
        if agent.last_observation_step != agent.current_step:
            return original_planner(grid, start, goal, **kwargs)
        if tuple(start) != agent.gate_pre_position:
            raise RuntimeError("Planner and controller positions differ at memory observation")

        started = perf_counter_ns()
        route, event = online_gate_decision(
            agent.gate_pre_map, grid, start, goal, kwargs,
            original_planner, prior_overrides=state["overrides"], policy=policy)
        elapsed = perf_counter_ns() - started
        event["step"] = int(agent.current_step)
        if allowed_gate_steps is not None:
            candidate = bool(event["override_applied"])
            event["eligible_before_intervention_filter"] = candidate
            event["allowed_by_step_intervention"] = int(agent.current_step) in allowed_gate_steps
            if candidate and not event["allowed_by_step_intervention"]:
                # The old action remains just a rejected candidate.
                # Fall back to the true updated-map G1 route (not a
                # new observation and not an unselected shield query).
                route = original_planner(grid, start, goal, **kwargs)
                event["override_applied"] = False
                event["chosen_action"] = event["new_action"]
                event["guard"] = "diagnostic_step_filter_forced_normal_replan"
        event["gate_eval_ns_including_new_plan"] = int(elapsed)
        event["position"] = [int(start[0]), int(start[1])]
        state["events"].append(event)
        state["gate_ns"] += elapsed
        if event["override_applied"]:
            state["overrides"] += 1
        return route

    evaluator.RDAOController = CandidateOnlineGateRDAO
    evaluator.base.plan_g1_default_policy = plan_with_gate
    try:
        row, trace = evaluator._instrumented_case(payload, schedule, "rdao_v1")
        return row, trace, dict(state)
    finally:
        evaluator.base.plan_g1_default_policy = original_planner
        evaluator.RDAOController = original_controller


def _jsonable(value):
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def _episode_metric(record, prefix):
    v = _metrics(record)
    return {f"{prefix}_{key}": value for key, value in v.items()}


def _summarize(rows, variant):
    items = [r for r in rows if r["policy"] == variant]
    if not items:
        return {}
    m = len(items)
    successful = [r for r in items if r["gated_success"]]
    regressions = [r for r in items if r["baseline_success"] and not r["gated_success"]]
    gains = [r for r in items if not r["baseline_success"] and r["gated_success"]]
    return {
        "episodes": m,
        "unique_worlds": len({r["world_identity"] for r in items}),
        "baseline_successes": sum(r["baseline_success"] for r in items),
        "gated_successes": sum(r["gated_success"] for r in items),
        "rescued_failures": len(gains),
        "harmed_successes": len(regressions),
        "rescue_worlds": sorted({r["world_identity"] for r in gains}),
        "harmed_worlds": sorted({r["world_identity"] for r in regressions}),
        "any_unwanted_contact_episodes": sum(r["gated_unwanted_contacts"] > 0 for r in items),
        "total_unwanted_contacts": sum(r["gated_unwanted_contacts"] for r in items),
        "episodes_with_override": sum(r["gate_overrides"] > 0 for r in items),
        "total_overrides": sum(r["gate_overrides"] for r in items),
        "total_evaluated_observations": sum(r["gate_observation_events"] for r in items),
        "mean_baseline_observations": statistics.mean(r["baseline_observations"] for r in items),
        "mean_gated_observations": statistics.mean(r["gated_observations"] for r in items),
        "mean_baseline_horizon_censored_steps": statistics.mean(r["baseline_elapsed_steps"] for r in items),
        "mean_gated_horizon_censored_steps": statistics.mean(r["gated_elapsed_steps"] for r in items),
        "mean_baseline_distance_m": statistics.mean(r["baseline_travel_distance_m"] for r in items),
        "mean_gated_distance_m": statistics.mean(r["gated_travel_distance_m"] for r in items),
        "mean_baseline_steps_among_successes": (
            statistics.mean(r["baseline_elapsed_steps"] for r in items if r["baseline_success"])
            if any(r["baseline_success"] for r in items) else None),
        "mean_gated_steps_among_successes": (
            statistics.mean(r["gated_elapsed_steps"] for r in successful)
            if successful else None),
        "mean_gate_plan_time_ms_including_normal_plan": statistics.mean(
            r["gate_plan_evaluation_ms"] for r in items),
        "mean_delta_observations": statistics.mean(r["gated_observations"] -
                                                 r["baseline_observations"] for r in items),
        "mean_delta_distance_m": statistics.mean(r["gated_travel_distance_m"] -
                                                r["baseline_travel_distance_m"] for r in items),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--world", help="Filter to ONE admitted world suffix, for pilot fidelity")
    parser.add_argument("--max-cases", type=int, default=None,
                        help="Deterministic prefix of cases; omit for all 72")
    parser.add_argument("--policies", choices=("first", "every", "both"), default="both")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    if args.max_cases is not None and args.max_cases < 1:
        parser.error("max-cases must be >=1")
    output = args.output or DEFAULT_OUT
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite existing results: {output}")

    original_rows = _load_csv(PRIMARY / "primary_episodes.csv")
    originals = {_key(r): r for r in original_rows}
    original_traces = _read_saved_traces()
    if len(originals) != len(original_rows) or len(originals) != 72:
        raise ValueError("Expected 72 unique frozen RDAO episodes")
    if set(originals) != set(original_traces):
        raise ValueError("Frozen trace matrix differs from result rows")
    selected = sorted(originals, key=lambda k: (k[0], k[1], k[2]))
    if args.world:
        selected = [k for k in selected if k[0].endswith(args.world)]
    if args.max_cases is not None:
        selected = selected[:args.max_cases]
    if not selected:
        raise ValueError("No episodes selected")
    policies = POLICIES if args.policies == "both" else (args.policies,)

    preserved = navigation.verify_preserved_prefix()
    worlds = {w["identity"]: w for w in navigation.admitted_worlds()}
    if len(worlds) != 36:
        raise ValueError("Expected 36 frozen admitted fit worlds")
    hashes = {str(p.relative_to(ROOT)): _sha(p) for p in (
        PRIMARY / "primary_episodes.csv", PRIMARY / "primary_traces.jsonl.gz")}
    rows, trace_rows = [], []

    for i, key in enumerate(selected, 1):
        identity, schedule, seed = key
        if seed != 42 or identity not in worlds:
            raise RuntimeError("Unexpected selected case")
        base_row, base_trace = evaluator._instrumented_case(
            worlds[identity], schedule, "rdao_v1")
        if evaluator._signature(base_row) != evaluator._signature(originals[key]):
            raise RuntimeError(f"Historical primary baseline failed reproduction: {key}")
        _compare_trace(original_traces[key], base_trace)

        for policy in policies:
            gated_row, gated_trace, state = run_candidate(worlds[identity],
                                                           schedule, policy)
            base_metrics = _metrics(originals[key])
            metrics = _metrics(gated_row)
            if (metrics["observations"] > 20
                    or int(gated_row.get("g1_unselected_action_shield_queries", 0)) != 0
                    or not _bool(gated_row["g1_shield_query_count_valid"])):
                raise RuntimeError(f"Safety or sensing limit violated for {key}")
            if not state["overrides"]:
                _compare_trace(base_trace, gated_trace)
            else:
                before_step = min(e["step"] for e in state["events"] if
                                  e["override_applied"])
                _compare_trace(base_trace, gated_trace, before_step=before_step)
                first_diff = _first_difference(base_trace, gated_trace)
                # A legitimate gate can be vetoed by the unchanged emergency
                # controller or selected-action collision shield, so an
                # attempted override need not cause actual action divergence.
                if first_diff is not None and first_diff < before_step:
                    raise RuntimeError("Gated action diverged before any override")
            recorded_gate_calls = [
                e for e in state["events"] if e["override_applied"]]
            if policy == "first" and len(recorded_gate_calls) > 1:
                raise RuntimeError("First-only gate applied more than once")
            if sum(f["observation_granted"] for f in gated_trace["steps"]) != metrics["observations"]:
                raise RuntimeError("Observation counts disagree with actual gated trace")
            if not all(f["observation_granted"]
                       for f in gated_trace["steps"]
                       if f.get("rdao", {}).get("observation_effect") is not None):
                raise RuntimeError("Recorded observation effects without authorized sensor")
            report_row = {
                "world_identity": identity, "schedule": schedule, "seed": seed,
                "policy": policy, "gate_observation_events": len(state["events"]),
                "gate_overrides": state["overrides"],
                "first_gate_step": recorded_gate_calls[0]["step"] if recorded_gate_calls else "",
                "first_gate_prior_action": (json.dumps(recorded_gate_calls[0]["prior_action"])
                                            if recorded_gate_calls else ""),
                "first_gate_new_action": (json.dumps(recorded_gate_calls[0]["new_action"])
                                          if recorded_gate_calls else ""),
                "first_action_or_pose_divergence_step": _first_difference(
                    base_trace, gated_trace),
                "gate_plan_evaluation_ms": state["gate_ns"] / 1e6,
                **_episode_metric(originals[key], "baseline"),
                **_episode_metric(gated_row, "gated"),
            }
            rows.append(report_row)
            trace_rows.append({
                "key": list(key), "policy": policy, "gate_events": state["events"],
                "metrics": metrics, "trace": gated_trace,
            })
        print(f"Completed {i}/{len(selected)}: {identity} schedule {schedule}",
              flush=True)

    if navigation.verify_preserved_prefix() != preserved:
        raise RuntimeError("Preservation evidence modified")
    if {str(p.relative_to(ROOT)): _sha(p) for p in (
            PRIMARY / "primary_episodes.csv", PRIMARY / "primary_traces.jsonl.gz")} != hashes:
        raise RuntimeError("Frozen primary evidence modified")
    summary = {
        "status": "EXPLORATORY_FIT_WORLD_ONLINE_GATE_SCREEN_NOT_HELD_OUT",
        "original_method": "rdao_v1",
        "online_signal_only": True,
        "max_memory_observations": 20,
        "worlds": len({k[0] for k in selected}),
        "episodes": len(selected),
        "policies": policies,
        "aggregates": {p: _summarize(rows, p) for p in policies},
        "gate_guard_counts": {p: dict(Counter(
            e["guard"] for rec in trace_rows if rec["policy"] == p
            for e in rec["gate_events"])) for p in policies},
        "source_hashes": hashes,
        "phase15_preservation": preserved,
        "limitations": [
            "All 36 fit worlds are development data previously used to diagnose and choose this gate.",
            "The paired two schedules are correlated and are not 72 independent worlds.",
            "A guard based solely on observed-free destination and public swept footprint can still produce long-term adverse navigation effects.",
            "This is a kinematic-root MuJoCo G1 navigation proxy, not demonstrated dynamic walking.",
            "The independent emergency sensor and actual-model selected-action shield remain unchanged; every safety regression must be reported.",
            "Extra old-policy planning after an observation incurs computation; time is reported but may vary by machine.",
            "A matched observation budget limit is not equal realized observation dose.",
            "No held-out result or superiority over Periodic/Age has been established.",
        ],
    }
    output.mkdir(parents=True)
    _write_csv(output / "paired_online_gate.csv", rows)
    with gzip.open(output / "online_gate_traces.jsonl.gz", "wt", encoding="utf-8") as stream:
        for record in trace_rows:
            stream.write(json.dumps(_jsonable(record), sort_keys=True,
                                    allow_nan=False) + "\n")
    (output / "summary.json").write_text(
        json.dumps(summary, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8")
    print(json.dumps({"output": str(output), "aggregates": summary["aggregates"],
                      "gate_guard_counts": summary["gate_guard_counts"]},
                     indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
