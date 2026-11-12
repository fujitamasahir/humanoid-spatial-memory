"""Observed-map route-value descriptors at ALL saved online RDAO gate events.

OFFLINE, read-only, development-only:
- reads the committed 72-episode first/every compressed traces and paired CSV;
- never generates worlds or consults hidden simulator geometry;
- never executes MuJoCo or changes a frozen artifact;
- computes ONLY descriptive decision-time-available features plus separate
  outcome/future labels for inspection, NOT an online learned gate.

Use this to decide whether candidate route values (newly blocked route
prefix, local exits, cost difference) actually separate beneficial and
harmful gate interventions. Do not select thresholds from two pilot worlds.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "results/phase2_mujoco/rdao_v1_online_safe_gate_fit72_screen_v1"
DEFAULT_OUTPUT = ROOT / "results/phase2_mujoco/rdao_v1_gate_event_route_features_v1"
NEIGHBORS = ((1, 0), (-1, 0), (0, 1), (0, -1))


def first_blocker_in_nominal_route(route, updated_grid):
    """First newly-known occupied cell among nominal A* move destinations.

    Step count here is TRANSLATIONS, not action index: turns are excluded.
    Never checks oracle occupancy.
    """
    result = []
    for action in route:
        if action[0] != "move":
            continue
        x, y = map(int, action[1])
        if not (0 <= y < len(updated_grid) and 0 <= x < len(updated_grid[y])):
            raise ValueError("Nominal route target outside observed memory grid")
        result.append(int(updated_grid[y][x]))
    first = next((i + 1 for i, state in enumerate(result) if state == 1), None)
    return first, result[:8]


def public_branch_count(grid, target, origin):
    """Count nearby non-backward cardinal cells already observed free/unknown."""
    x, y = map(int, target)
    px, py = map(int, origin)
    free, optimistic, occupied = 0, 0, 0
    for dx, dy in NEIGHBORS:
        nx, ny = x + dx, y + dy
        if (nx, ny) == (px, py):
            continue
        if not (0 <= ny < len(grid) and 0 <= nx < len(grid[ny])):
            occupied += 1
            continue
        state = int(grid[ny][nx])
        if state == 0:
            free += 1
        elif state == -1:
            optimistic += 1
        elif state == 1:
            occupied += 1
        else:
            raise ValueError(f"Unexpected public memory value: {state}")
    return free, optimistic, occupied


def horizon_return(trace_steps, event_step, pre_position, *, horizon=6):
    """Evaluator-only outcome label: returns to pre-intervention position?"""
    position = list(pre_position)
    for frame in trace_steps:
        step = int(frame["step"])
        if event_step < step <= event_step + horizon and frame["position"] == position:
            return step - event_step
    return None


def one_event(event, frame, case):
    """Features from public memory; labels are kept in separate columns."""
    effect = (frame.get("rdao") or {}).get("observation_effect")
    if effect is None:
        raise RuntimeError("Applied gate lacks an authorized observation_effect")
    old_grid, new_grid = effect["memory_before"], effect["memory_after"]
    prior = event["prior_action"]
    if not prior or prior[0] != "move":
        raise RuntimeError("Applied gate was not a prior forward movement")
    if frame["action"] != prior:
        # A separately authorized emergency action or selected-action shield
        # can veto the proposed gate. Record and analyze these separately.
        actual_action_equals_prior = False
    else:
        actual_action_equals_prior = True
    route = effect["route_before"]
    blocker, prefix = first_blocker_in_nominal_route(route, new_grid)
    from_pos = event["position"]
    dest = prior[1]
    local_free, local_unknown, local_occupied = public_branch_count(
        new_grid, dest, from_pos)
    new_occupied = 0
    new_free = 0
    for y, row in enumerate(new_grid):
        for x, after_value in enumerate(row):
            before_value = int(old_grid[y][x])
            after_value = int(after_value)
            if before_value != 1 and after_value == 1:
                new_occupied += 1
            if before_value == -1 and after_value == 0:
                new_free += 1
    before_cost = effect.get("route_cost_before")
    after_cost = effect.get("route_cost_after")
    cost_delta = (
        float(after_cost) - float(before_cost)
        if isinstance(before_cost, (int, float))
        and isinstance(after_cost, (int, float))
        and math.isfinite(before_cost)
        and math.isfinite(after_cost) else None)
    return {
        "world_identity": case["key"][0],
        "schedule": int(case["key"][1]),
        "policy": case["policy"],
        "step": int(event["step"]),
        "override_applied": True,
        "actual_action_equals_proposed": actual_action_equals_prior,
        "position": json.dumps(from_pos),
        "prior_action": json.dumps(prior),
        "updated_action": json.dumps(event["new_action"]),
        "memory_changed_cells": int(effect["memory_changed_cell_count"]),
        "newly_known_occupied_cells": new_occupied,
        "newly_known_free_cells": new_free,
        "route_cost_before": before_cost,
        "route_cost_after": after_cost,
        "nominal_cost_increase": cost_delta,
        "first_occupied_translation_in_old_nominal_route": blocker,
        "old_nominal_next8_move_occupancies": json.dumps(prefix),
        "nonbackward_observed_free_neighbors": local_free,
        "nonbackward_unknown_neighbors": local_unknown,
        "nonbackward_observed_occupied_or_oob": local_occupied,
        "revisited_origin_within_6_steps": horizon_return(
            case["trace"]["steps"], int(event["step"]), from_pos, horizon=6),
    }


def _load_outcomes(path):
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != 144:
        raise RuntimeError("Expected saved 72 episodes x 2 online rule arms")
    return {(row["world_identity"], int(row["schedule"]), row["policy"]): row
            for row in rows}


def _classify(row):
    orig, new = row["baseline_success"] == "True", row["gated_success"] == "True"
    return ("rescued" if new and not orig else
            "harmed" if orig and not new else
            "common_success" if orig else "common_failure")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing overwrite: {args.output}")
    paired = _load_outcomes(SOURCE / "paired_online_gate.csv")
    rows, cases = [], 0
    with gzip.open(SOURCE / "online_gate_traces.jsonl.gz", "rt",
                   encoding="utf-8") as stream:
        for line in stream:
            case = json.loads(line)
            cases += 1
            key = (case["key"][0], int(case["key"][1]), case["policy"])
            if key not in paired:
                raise RuntimeError(f"Unexpected case: {key}")
            comparison = paired[key]
            frames = {int(frame["step"]): frame for frame in case["trace"]["steps"]}
            for event in case["gate_events"]:
                if not event.get("override_applied"):
                    continue
                step = int(event["step"])
                record = one_event(event, frames[step], case)
                record["paired_outcome"] = _classify(comparison)
                record["baseline_steps"] = int(comparison["baseline_elapsed_steps"])
                record["gated_steps"] = int(comparison["gated_elapsed_steps"])
                record["delta_censored_steps"] = record["gated_steps"] - record["baseline_steps"]
                record["delta_distance_m"] = (
                    float(comparison["gated_travel_distance_m"]) -
                    float(comparison["baseline_travel_distance_m"]))
                record["total_gate_overrides_in_episode"] = int(comparison["gate_overrides"])
                rows.append(record)
    if cases != 144:
        raise RuntimeError(f"Missing saved case traces: got {cases}, expected 144")
    overrides = {p: sum(row["policy"] == p for row in rows)
                 for p in ("first", "every")}
    if overrides != {"first": 34, "every": 73}:
        raise RuntimeError(f"Gate override replay count mismatch: {overrides}")
    if not rows:
        raise RuntimeError("No applied gates found")

    args.output.mkdir(parents=True)
    with (args.output / "gate_event_route_features.csv").open(
            "w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    focus = [row for row in rows
             if row["world_identity"].endswith(("M:80030009", "M:80030010",
                                                "M:80030000", "R:80000022",
                                                "R:80000018"))
             and row["schedule"] == 0]
    (args.output / "summary.json").write_text(
        json.dumps({
            "status": "READ_ONLY_EXPLORATORY_EVENT_FEATURES_FROM_FIT_TRACES",
            "episodes_read": cases, "gate_overrides": overrides,
            "positive_and_negative_outcomes_are_episode_level_not_gate_causal_labels": True,
            "focus_events": focus,
            "notes": [
                "All route and neighborhood values use updated public ternary memory, not actual geometry.",
                "Nominal RDAO A* route is distinct from executed forward-first G1 planner policy.",
                "No per-event effect is identified if multiple gate interventions occurred.",
                "Return-to-origin is a posthoc outcome label, NEVER an online selection feature.",
                "The 36 fit worlds were used to construct the gate; no held-out evaluation here.",
                "Two pedestrian schedules of the same world are correlated.",
            ],
        }, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8")
    print(json.dumps({
        "output": str(args.output), "episodes_read": cases,
        "overrides": overrides, "focus_events": [
            {"world": row["world_identity"].split(":")[-2] + ":" +
                      row["world_identity"].split(":")[-1],
             "policy": row["policy"], "step": row["step"],
             "outcome": row["paired_outcome"],
             "cost_delta": row["nominal_cost_increase"],
             "old_route_first_blocker_move_index":
                 row["first_occupied_translation_in_old_nominal_route"],
             "observed_free_exits": row["nonbackward_observed_free_neighbors"],
             "unknown_exits": row["nonbackward_unknown_neighbors"]}
            for row in focus
        ]}, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
