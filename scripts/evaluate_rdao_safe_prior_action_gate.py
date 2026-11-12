"""Development-only: observe at step 3 but optionally retain the prior safe action.

This tests whether the beneficial one-step observation omission in M:80030010
is mainly due to skipping a sensor reading, or due to its immediate A*
replanning effect. Both variants DO perform the original step-3 authorized
memory observation. The gate only asks whether an action selected from the
pre-update memory is STILL SAFE with respect to the updated observed map,
blocked-action feedback and public footprint; the independent actual-geometry
selected-action shield and emergency safety controller remain authoritative.

Baseline: original RDAO v1.
Gated: at step 3 only, after a natural observation, retain the pre-update
default G1 planner's FIRST FORWARD ACTION, if its target is now observed
free and its swept footprint has no observed occupied collision, it is not
blocked, and the default planner no longer selects that same action.

This is an outcome-selected diagnostic, not a proposed online v2 rule.
No hidden simulator geometry, oracle/shadow measurements or unselected action
shields are ever used to select the gated action. Original evidence is read
only and verification is mandatory.
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
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

import evaluate_rdao_phase2 as eval_rdao
import phase2_mujoco_navigation as nav
from evaluate_rdao_one_shot_interventions import (
    _bool, _compare_trace, _first_difference, _key, _load_csv,
    _metrics, _read_saved_traces, _sha, _write_csv,
)
from spatial_memory.navigation import (
    CARDINALS, _move_clear, blocked_action_key,
)
from spatial_memory.rdao import RDAOController

PRIMARY = ROOT / "results/phase2_mujoco/rdao_v1_phase2_evaluation"
DEFAULT_OUTPUT = ROOT / "results/phase2_mujoco/rdao_v1_safe_prior_action_gate_M80030010"


class PriorActionGateRDAO(RDAOController):
    """Capture pre-observation memory without altering RDAO's decisions."""

    gate_step = 3
    gate_events = []

    def decide(self, step, position):
        if int(step) == self.gate_step:
            self.gate_memory_before = self.memory.grid.copy()
            self.gate_position_before = tuple(position)
            self.gate_heading_before = float(self.heading_yaw)
        return super().decide(step, position)


def select_safe_preupdate_action(pre_grid, updated_grid, start, goal, *,
                                 heading, unknown, local_extents,
                                 cell_size, blocked_actions,
                                 old_planner, planner_kwargs):
    """Select an unchanged, observed-safe forward step (or return no gate).

    Same observed pedestrian context, static feedback and current policy
    arguments are used for BOTH forward-policy evaluations. Safety guards
    only inspect updated PUBLIC memory and public robot footprint.
    """
    prior = old_planner(pre_grid, start, goal, heading=heading,
                        unknown=unknown, local_extents=local_extents,
                        cell_size=cell_size, blocked_actions=blocked_actions,
                        **planner_kwargs)
    after = old_planner(updated_grid, start, goal, heading=heading,
                        unknown=unknown, local_extents=local_extents,
                        cell_size=cell_size, blocked_actions=blocked_actions,
                        **planner_kwargs)
    earlier = prior[0] if prior else None
    current = after[0] if after else None
    result = {"prior_action": earlier, "new_action": current,
              "chosen_action": current, "override_applied": False,
              "guard": None}
    if earlier is None or earlier[0] != "move":
        result["guard"] = "prior_action_not_forward"
        return after, result
    if earlier == current:
        result["guard"] = "same_first_action_no_gate_needed"
        return after, result

    target = tuple(earlier[1])
    x, y = map(int, start)
    face = int(heading) % 4
    dx, dy = CARDINALS[face]
    if target != (x + dx, y + dy):
        result["guard"] = "prior_action_not_one_step_forward"
        return after, result
    tx, ty = target
    if not (0 <= tx < updated_grid.shape[1] and
            0 <= ty < updated_grid.shape[0] and updated_grid[ty, tx] == 0):
        result["guard"] = "destination_not_observed_free_after_update"
        return after, result
    if blocked_action_key((x, y), face, earlier) in set(blocked_actions):
        result["guard"] = "action_previously_blocked"
        return after, result
    if not _move_clear(updated_grid, (x, y), target, face,
                       local_extents, cell_size):
        result["guard"] = "footprint_conflicts_with_observed_obstacle"
        return after, result
    result["chosen_action"] = earlier
    result["override_applied"] = True
    result["guard"] = "passed_observed_cell_and_footprint_checks"
    return [earlier], result


def _run_gated(payload, schedule):
    """Monkeypatch only the frozen evaluator's documented G1 planner binding."""
    orig_controller = eval_rdao.RDAOController
    original_policy = eval_rdao.base.plan_g1_default_policy
    PriorActionGateRDAO.gate_events = []

    def policy(grid, position, goal, **kwargs):
        ctx = eval_rdao.CURRENT
        agent = ctx.get("controller") if ctx else None
        if not isinstance(agent, PriorActionGateRDAO):
            return original_policy(grid, position, goal, **kwargs)
        if agent.current_step != agent.gate_step:
            return original_policy(grid, position, goal, **kwargs)
        if not (agent.last_observation_step == agent.gate_step
                and hasattr(agent, "gate_memory_before")):
            return original_policy(grid, position, goal, **kwargs)
        if tuple(map(int, position)) != agent.gate_position_before:
            raise RuntimeError("Agent and real G1 planner pose diverged at intervention")
        local = dict(kwargs)
        planner_kwargs = {
            "static_obstacle_cells": local.pop("static_obstacle_cells", frozenset()),
            "pedestrian_context": local.pop("pedestrian_context", None),
            "step": local.pop("step", agent.gate_step),
        }
        route, event = select_safe_preupdate_action(
            agent.gate_memory_before, grid, position, goal,
            heading=local["heading"], unknown=local["unknown"],
            local_extents=local["local_extents"],
            cell_size=local["cell_size"],
            blocked_actions=local["blocked_actions"],
            old_planner=original_policy, planner_kwargs=planner_kwargs,
        )
        changed = int((agent.gate_memory_before != grid).sum())
        event.update(step=int(agent.gate_step), pose=list(position),
                     changed_memory_cells=changed, action_before_refresh_checked=True,
                     observation_granted=True)
        PriorActionGateRDAO.gate_events.append(event)
        return route

    eval_rdao.RDAOController = PriorActionGateRDAO
    eval_rdao.base.plan_g1_default_policy = policy
    try:
        row, trace = eval_rdao._instrumented_case(payload, schedule, "rdao_v1")
        return row, trace, list(PriorActionGateRDAO.gate_events)
    finally:
        eval_rdao.base.plan_g1_default_policy = original_policy
        eval_rdao.RDAOController = orig_controller


def _sanitized(value):
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: _sanitized(v) for key, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_sanitized(v) for v in value]
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--world", default="M:80030010")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    output = args.output or (
        DEFAULT_OUTPUT if args.world == "M:80030010"
        else ROOT / "results/phase2_mujoco" /
             ("rdao_v1_safe_prior_action_gate_" + args.world.replace(":", "")))
    if output.exists():
        raise FileExistsError(f"Refusing overwrite: {output}")

    original_rows = _load_csv(PRIMARY / "primary_episodes.csv")
    reference = {_key(row): row for row in original_rows}
    frozen_traces = _read_saved_traces()
    if len(original_rows) != 72 or set(reference) != set(frozen_traces):
        raise ValueError("Expected frozen 72 episode case matrix")
    selected = sorted((key for key in reference if key[0].endswith(args.world)),
                      key=lambda k: k[1])
    if len(selected) != 2 or set(k[1] for k in selected) != {0, 1}:
        raise ValueError("Expected exactly two schedules for one world")

    previous = nav.verify_preserved_prefix()
    source_paths = (PRIMARY / "primary_episodes.csv",
                    PRIMARY / "primary_traces.jsonl.gz")
    hashes = {str(p.relative_to(ROOT)): _sha(p) for p in source_paths}
    payloads = {p["identity"]: p for p in nav.admitted_worlds()}
    if len(payloads) != 36:
        raise RuntimeError("Admitted development world count changed")
    comparison = []
    snapshots = []

    for key in selected:
        identity, schedule, seed = key
        if seed != 42:
            raise RuntimeError("Development seed must remain frozen")
        payload = payloads[identity]
        row0, trace0 = eval_rdao._instrumented_case(payload, schedule, "rdao_v1")
        if eval_rdao._signature(row0) != eval_rdao._signature(reference[key]):
            raise RuntimeError(f"Historical baseline row cannot be reproduced: {key}")
        _compare_trace(frozen_traces[key], trace0)
        f3 = next(frame for frame in trace0["steps"] if frame["step"] == 3)
        if not f3["observation_granted"]:
            raise RuntimeError("Chosen case has no natural authorized observation at step3")

        row, trace, events = _run_gated(payload, schedule)
        _compare_trace(trace0, trace, before_step=3)
        if len(events) != 1 or not events[0]["observation_granted"]:
            raise RuntimeError(f"Pre-update planner gate was not evaluated exactly once: {events}")
        frame = next(f for f in trace["steps"] if f["step"] == 3)
        if not frame["observation_granted"]:
            raise RuntimeError("Step3 sensor observation must never be suppressed")
        if frame["rdao"]["observation_effect"] is None:
            raise RuntimeError("No real memory refresh recorded at step3")
        if events[0]["changed_memory_cells"] != frame["rdao"]["observation_effect"]["memory_changed_cell_count"]:
            raise RuntimeError("Logged pre/post memory change count mismatch")
        metrics = _metrics(row)
        if (metrics["observations"] > 20
                or int(row.get("g1_unselected_action_shield_queries", 0)) != 0
                or not _bool(row["g1_shield_query_count_valid"])):
            raise RuntimeError("Safety/observation cap invariant failed")
        baseline = _metrics(reference[key])
        comparison.append({
            "world_identity": identity, "schedule": schedule, "seed": seed,
            "original_success": baseline["success"],
            "gated_success": metrics["success"],
            "original_steps": baseline["elapsed_steps"],
            "gated_steps": metrics["elapsed_steps"],
            "original_observations": baseline["observations"],
            "gated_observations": metrics["observations"],
            "original_distance_m": baseline["travel_distance_m"],
            "gated_distance_m": metrics["travel_distance_m"],
            "original_turns": baseline["turns"],
            "gated_turns": metrics["turns"],
            "original_unwanted_contacts": baseline["unwanted_contacts"],
            "gated_unwanted_contacts": metrics["unwanted_contacts"],
            "original_step3_action": json.dumps(f3["action"]),
            "gated_step3_action": json.dumps(frame["action"]),
            "gated_first_divergence": _first_difference(trace0, trace),
            "step3_observed": frame["observation_granted"],
            "gate_override_applied": events[0]["override_applied"],
            "gate_guard": events[0]["guard"],
            "gate_changed_cells": events[0]["changed_memory_cells"],
            "gate_prior_action": json.dumps(events[0]["prior_action"]),
            "gate_new_action": json.dumps(events[0]["new_action"]),
            "gate_chosen_action": json.dumps(events[0]["chosen_action"]),
        })
        snapshots.append({
            "world_identity": identity, "schedule": schedule, "seed": seed,
            "gate_event": events[0],
            "baseline_metrics": baseline, "gated_metrics": metrics,
            "gated_trace": trace,
        })
        print(f"Completed safe post-observation action gate: {identity} schedule {schedule}",
              flush=True)

    if nav.verify_preserved_prefix() != previous:
        raise RuntimeError("Phase1.5 preservation changed")
    if {str(p.relative_to(ROOT)): _sha(p) for p in source_paths} != hashes:
        raise RuntimeError("Frozen inputs changed during intervention")

    overall = {
        "status": "EXPLORATORY_POST_OBSERVATION_ACTION_GATE_NOT_ONLINE_POLICY",
        "world_suffix": args.world,
        "original_successes": sum(r["original_success"] for r in comparison),
        "gated_successes": sum(r["gated_success"] for r in comparison),
        "cases": len(comparison),
        "overrides_applied": sum(r["gate_override_applied"] for r in comparison),
        "unwanted_contacts": sum(r["gated_unwanted_contacts"] for r in comparison),
        "original_steps": [r["original_steps"] for r in comparison],
        "gated_steps": [r["gated_steps"] for r in comparison],
        "original_observations": [r["original_observations"] for r in comparison],
        "gated_observations": [r["gated_observations"] for r in comparison],
        "frozen_hashes": hashes,
        "preservation": previous,
        "caveats": [
            "One pre-selected original observation step in an outcome-selected fit world.",
            "Only the FIRST previous G1 action can be reused, and only after public map/footprint validation.",
            "Independent Emergency Safety and selected-action collision shield are unchanged.",
            "Actual sensing frequency/dose after intervention may change endogenously.",
            "Any improvement is not evidence of an autonomous deployable RDAO v2.",
        ],
    }
    output.mkdir(parents=True)
    _write_csv(output / "gate_comparison.csv", comparison)
    with gzip.open(output / "gated_traces.jsonl.gz", "wt", encoding="utf-8") as stream:
        for record in snapshots:
            stream.write(json.dumps(_sanitized(record), sort_keys=True, allow_nan=False) + "\n")
    (output / "summary.json").write_text(
        json.dumps(overall, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(json.dumps({"output": str(output), "original_successes": overall["original_successes"],
                      "gated_successes": overall["gated_successes"],
                      "overrides_applied": overall["overrides_applied"],
                      "gated_steps": overall["gated_steps"],
                      "gated_observations": overall["gated_observations"],
                      "unwanted_contacts": overall["unwanted_contacts"]}, indent=2))


if __name__ == "__main__":
    main()
