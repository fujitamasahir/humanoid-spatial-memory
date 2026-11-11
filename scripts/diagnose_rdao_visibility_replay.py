"""Evaluator-only visibility replay for the saved Phase 2 RDAO v1 trajectories.

Replays the saved robot poses and world event clock WITHOUT calling the policy,
changing its memory, adding authorized observations, or changing actions.
Shadow MuJoCo raycasts are diagnostic probes, never controller inputs.

The probe must first exactly reproduce every saved granted observation; otherwise
it refuses to report rejected-step results. No held-out worlds are loaded.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

import evaluate_phase2_61ray_emergency_safety_full_288 as base
import phase2_mujoco_navigation as nav
from spatial_memory.mujoco_navigation import MujocoNavigationScene
from spatial_memory.mujoco_perception import MujocoRayPerception
from spatial_memory.rdao import RDAOParameters, predicted_cell_visibility, route_positions
from spatial_memory.simulation import World, scenario_from_bprime

INPUT_DIR = ROOT / "results/phase2_mujoco/rdao_v1_phase2_evaluation"
CASE_NAMES = ("A", "B", "C")


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_traces(scope: str):
    if scope == "cases":
        paths = [INPUT_DIR / f"case_{case}_rdao_trace.json" for case in CASE_NAMES]
        return [json.loads(path.read_text()) for path in paths], paths
    path = INPUT_DIR / "primary_traces.jsonl.gz"
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        traces = [json.loads(line) for line in stream if line.strip()]
    if len(traces) != 72:
        raise ValueError(f"Expected 72 frozen primary traces, got {len(traces)}")
    return traces, [path]


def _actual_values(effect, shape):
    """Reconstruct the saved raw observation, not the accumulated memory."""
    result = np.full(shape, -1, dtype=np.int8)
    for rec in effect["received_observation_values"]:
        x, y = map(int, rec["cell"])
        if result[y, x] != -1:
            raise ValueError("Duplicate cell in saved observation")
        result[y, x] = int(rec["value"])
    return result


def _near_route(cell, position, route, lookahead):
    positions = route_positions(position, route)[:lookahead + 1]
    return bool(positions) and min(
        abs(int(cell[0]) - int(x)) + abs(int(cell[1]) - int(y))
        for x, y in positions
    ) <= 1


def _probe_trace(trace, payload, config):
    identity, schedule, policy, seed = trace["key"]
    if policy != "rdao_v1" or int(seed) != 42 or int(schedule) not in (0, 1):
        raise ValueError(f"Unexpected trace identity: {trace['key']}")
    scenario = scenario_from_bprime(payload, int(schedule))
    world = World(scenario)
    scene = MujocoNavigationScene(
        scenario, cell_size=config["mujoco_cell_size_m"],
        timestep=config["mujoco_timestep_seconds"])
    sensor = MujocoRayPerception(scene, **config["mujoco_ray_sensor"])
    params = RDAOParameters()
    memory = None
    results = []
    accepted_checks = 0
    steps = trace["steps"]
    if not steps or steps[0]["step"] != 0:
        raise ValueError("Trace does not start at the initial step")

    for frame in steps:
        step = int(frame["step"])
        while world.step < step:
            world.advance()
        if world.step != step:
            raise ValueError("Out-of-order saved steps")
        diag = frame.get("rdao")
        if step == 0:
            if diag is not None:
                raise ValueError("Initial frame unexpectedly has RDAO decision")
            memory = sensor.observe(world, frame["position"], frame["heading_yaw"]).copy()
            continue
        if diag is None or int(diag["step"]) != step:
            raise ValueError("Missing or misaligned RDAO diagnostic")
        position = tuple(map(int, diag["position"]))
        yaw = float(diag["heading_yaw"])
        before = memory.copy()
        shadow = sensor.observe(world, position, yaw)
        if diag["granted"]:
            effect = diag.get("observation_effect")
            if not effect:
                raise ValueError(f"Missing saved observation at {identity} step {step}")
            saved = _actual_values(effect, shadow.shape)
            if not np.array_equal(saved, shadow):
                raise ValueError(f"Replay sensor mismatch: {identity} schedule {schedule} step {step}")
            if not np.array_equal(before, np.asarray(effect["memory_before"], dtype=np.int8)):
                raise ValueError(f"Replay pre-memory mismatch: {identity} schedule {schedule} step {step}")
            memory[shadow >= 0] = shadow[shadow >= 0]
            if not np.array_equal(memory, np.asarray(effect["memory_after"], dtype=np.int8)):
                raise ValueError(f"Replay post-memory mismatch: {identity} schedule {schedule} step {step}")
            accepted_checks += 1
            continue

        # No memory update here. The shadow sensor is evaluator-only.
        newly_seen = np.argwhere((before == -1) & (shadow >= 0))
        counts = Counter()
        half_fov = math.radians(sensor.horizontal_fov_deg) / 2
        for y, x in newly_seen:
            cell = (int(x), int(y))
            dx, dy = cell[0] - position[0], cell[1] - position[1]
            distance = math.hypot(dx, dy) * scene.cell_size
            rel_angle = (math.atan2(dy, dx) - yaw + math.pi) % (2 * math.pi) - math.pi
            visibility = predicted_cell_visibility(
                before, position, yaw, cell, cell_size_m=scene.cell_size,
                range_m=sensor.range_m, horizontal_fov_deg=sensor.horizontal_fov_deg,
                ray_count=sensor.ray_count,
                unknown_open_probability=params.unknown_blocker_open_probability)
            near = _near_route(cell, position, diag["nominal_route"],
                               params.route_lookahead_actions)
            counts["newly_visible"] += 1
            counts["new_free" if int(shadow[y, x]) == 0 else "new_occupied"] += 1
            counts["new_near_route"] += int(near)
            missed = visibility <= 0.0
            counts["predicted_zero_but_visible"] += int(missed)
            counts["missed_near_route"] += int(missed and near)
            counts["center_outside_fov_but_visible"] += int(abs(rel_angle) > half_fov + 1e-10)
            counts["center_outside_range_but_visible"] += int(distance > sensor.range_m + 1e-10)
            counts["occlusion_or_other_zero_but_visible"] += int(
                missed and abs(rel_angle) <= half_fov + 1e-10
                and distance <= sensor.range_m + 1e-10)
        results.append(dict(
            world_identity=identity, schedule=int(schedule), seed=int(seed),
            step=step, position_x=position[0], position_y=position[1],
            heading_yaw=yaw, rejection_reason=diag["reason"],
            score=diag["score"], threshold=diag["threshold"],
            logged_candidate_regions=len(diag["candidate_regions"]),
            **{name: counts[name] for name in (
                "newly_visible", "new_free", "new_occupied", "new_near_route",
                "predicted_zero_but_visible", "missed_near_route",
                "center_outside_fov_but_visible", "center_outside_range_but_visible",
                "occlusion_or_other_zero_but_visible")}))
    expected = sum(bool(frame.get("rdao", {}).get("granted")) for frame in steps)
    if accepted_checks != expected:
        raise ValueError("Not all saved accepted observations were validated")
    return results, accepted_checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", choices=("cases", "primary"), default="cases")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or ROOT / "results/phase2_mujoco" / f"rdao_v1_visibility_probe_{args.scope}"
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite prior diagnostic output: {output}")
    traces, inputs = _load_traces(args.scope)
    config = base.frozen_config(base.load_baseline()[2])
    worlds = nav.admitted_worlds()
    if len(worlds) != 36:
        raise ValueError("Expected exactly 36 admitted fit worlds")
    by_identity = {w["identity"]: w for w in worlds}
    preservation_before = nav.verify_preserved_prefix()
    rows = []
    accepted = 0
    for trace in traces:
        identity = trace["key"][0]
        if identity not in by_identity:
            raise ValueError(f"Not an admitted fit world: {identity}")
        results, checks = _probe_trace(trace, by_identity[identity], config)
        rows.extend(results)
        accepted += checks
    if nav.verify_preserved_prefix() != preservation_before:
        raise RuntimeError("Frozen Phase 1.5 data changed during diagnostic replay")

    by_reason = Counter(row["rejection_reason"] for row in rows)
    metrics = ("newly_visible", "new_free", "new_occupied", "new_near_route",
               "predicted_zero_but_visible", "missed_near_route",
               "center_outside_fov_but_visible", "center_outside_range_but_visible",
               "occlusion_or_other_zero_but_visible")
    summary = {
        "status": "DESCRIPTIVE_EVALUATOR_ONLY_NOT_CAUSAL",
        "scope": args.scope, "episode_count": len(traces),
        "rejected_decisions": len(rows),
        "accepted_observations_exactly_verified": accepted,
        "rejection_reason_counts": dict(sorted(by_reason.items())),
        "totals": {name: sum(int(row[name]) for row in rows) for name in metrics},
        "episodes_with_new_visible_near_route": len({
            (row["world_identity"], row["schedule"])
            for row in rows if row["new_near_route"] > 0}),
        "input_sha256": {p.relative_to(ROOT).as_posix(): _hash(p) for p in inputs},
        "source_sha256": {p: _hash(ROOT / p) for p in (
            "src/spatial_memory/rdao.py", "src/spatial_memory/mujoco_perception.py",
            "src/spatial_memory/simulation.py", "scripts/diagnose_rdao_visibility_replay.py")},
        "limits": [
            "World truth is used only by the diagnostic shadow sensor, never the original agent.",
            "Saved actions and observation timings are frozen; no counterfactual outcome is estimated.",
            "A sensor-visible unknown cell need not change the G1 route or improve success.",
            "Center-cell-angle disagreement is not by itself a rejected decision.",
            "Development cases and primary fit worlds are not independent held-out evidence."]}
    output.mkdir(parents=True)
    with (output / "rejected_decisions.csv").open("w", encoding="utf-8", newline="") as stream:
        if rows:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    (output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"output": str(output), **{k: summary[k] for k in (
        "scope", "episode_count", "rejected_decisions",
        "accepted_observations_exactly_verified", "totals")}}, indent=2))


if __name__ == "__main__":
    main()
