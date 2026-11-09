"""Retrospectively compare saved-maze AABB turns with actual G1 MuJoCo turns."""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from spatial_memory.mujoco_navigation import MujocoNavigationScene
from spatial_memory.navigation import HEADINGS, _turn_clear, plan_g1_forward_facing
from spatial_memory.simulation import Scenario, World, scenario_from_bprime


DEFAULT_PROVENANCE = ROOT / "results/phase2_mujoco/g1_3d_perception_footprint_feedback_full_288/provenance.json"
DEFAULT_FORWARD_RUN = ROOT / "results/phase2_mujoco/g1_forward_first_default_full_288"
DEFAULT_OUTPUT = ROOT / "results/phase2_mujoco/start_turn_clearance_diagnostic_36_v2.json"
CELL_M = 0.75


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read_record(identity: str, roots: list[Path]) -> tuple[dict, Path, bytes]:
    relative = Path("records") / f"{sha(identity.encode())}.json.gz"
    path = next((root / relative for root in roots if (root / relative).is_file()), None)
    if path is None:
        raise FileNotFoundError(f"Missing stored fit candidate: {identity}")
    raw = path.read_bytes()
    wrapper = json.loads(gzip.decompress(raw))
    payload = wrapper.get("payload")
    payload_hash = sha(json.dumps(payload, sort_keys=True, separators=(",", ":"),
                                allow_nan=False).encode())
    if (wrapper.get("identity") != identity or not isinstance(payload, dict)
            or payload.get("identity") != identity
            or wrapper.get("payload_sha256") != payload_hash):
        raise ValueError(f"Stored fit identity/payload commitment mismatch: {identity}")
    return payload, path, raw


def observed_turn(scene, world, position, yaw_from, yaw_to) -> dict:
    blocked, contacts, _, reason = scene.check_turn(world, position, yaw_from, yaw_to)
    return {"clear": not blocked,
            "reason": reason,
            "contacts": {"wall": contacts.wall,
                         "persistent_obstacle": contacts.persistent_obstacle,
                         "pedestrian": contacts.pedestrian,
                         "unwanted_floor": contacts.unwanted_floor,
                         "robot_self": contacts.robot_self}}


def execute_aabb_plan_on_actual_g1(scene, world, start, goal, route) -> dict:
    position = tuple(start)
    heading = 0
    scene._set_pose(position, HEADINGS[heading])
    scene.mj.mj_forward(scene.model, scene.data)
    for number, (kind, target) in enumerate(route, start=1):
        if kind == "turn":
            target_heading = int(target) % 4
            result = observed_turn(scene, world, position,
                                  HEADINGS[heading], HEADINGS[target_heading])
            if not result["clear"]:
                return {"reaches_goal": False, "blocked_at_action": number,
                        "blocked_action": [kind, target], "reason": result["reason"],
                        "contact_counts": result["contacts"], "actions": len(route)}
            heading = target_heading
            scene._set_pose(position, HEADINGS[heading])
            scene.mj.mj_forward(scene.model, scene.data)
        elif kind == "move":
            target_cell = tuple(target)
            blocked, contacts, _, reason = scene.check_move(
                world, position, target_cell, HEADINGS[heading],
                target_yaw=HEADINGS[heading])
            if blocked:
                return {"reaches_goal": False, "blocked_at_action": number,
                        "blocked_action": [kind, list(target_cell)], "reason": reason,
                        "contact_counts": {"wall": contacts.wall,
                                           "persistent_obstacle": contacts.persistent_obstacle,
                                           "pedestrian": contacts.pedestrian},
                        "actions": len(route)}
            position = target_cell
            scene._set_pose(position, HEADINGS[heading])
            scene.mj.mj_forward(scene.model, scene.data)
        else:
            return {"reaches_goal": False, "blocked_at_action": number,
                    "reason": f"unsupported action {kind}", "actions": len(route)}
    return {"reaches_goal": position == tuple(goal), "final_position": list(position),
            "actions": len(route)}


def diagnose_world(identity: str, payload: dict, roots: list[Path]) -> dict:
    geometry = payload["geometry"]
    free = {tuple(map(int, cell)) for cell in geometry["free"]}
    width, height = int(geometry["width"]), int(geometry["height"])
    start, goal = tuple(payload["world"]["start"]), tuple(payload["world"]["goal"])
    directions = (("east", 1, 0), ("north", 0, 1),
                  ("west", -1, 0), ("south", 0, -1))
    walls = {(x, y) for y in range(height) for x in range(width)
             if (x, y) not in free}
    neighboring_walls = [name for name, dx, dy in directions
                         if (start[0]+dx, start[1]+dy) in walls]
    diagonal_directions = (("northeast", 1, 1), ("northwest", -1, 1),
                           ("southwest", -1, -1), ("southeast", 1, -1))
    neighboring_diagonal_walls = [name for name, dx, dy in diagonal_directions
                                  if (start[0]+dx, start[1]+dy) in walls]
    wall_scenario = Scenario.from_dict({
        "name": f"diagnostic:{identity}", "split": "development",
        "width": width, "height": height, "start": list(start), "goal": list(goal),
        "walls": [list(cell) for cell in sorted(walls)], "obstacles": [],
        "pedestrians": [], "changes": [],
    })
    wall_scene = MujocoNavigationScene(wall_scenario, cell_size=CELL_M)
    wall_world = World(wall_scenario)

    # Actual MuJoCo contact checks for the two signed 90-degree turns, with
    # saved maze walls only. These are explicitly retrospective diagnostics.
    actual_start = {
        "left_90": observed_turn(wall_scene, wall_world, start, 0.0, HEADINGS[1]),
        "right_90": observed_turn(wall_scene, wall_world, start, 0.0, HEADINGS[3]),
    }

    known_walls = np.zeros((height, width), dtype=np.int8)
    for x, y in walls:
        known_walls[y, x] = 1
    rectangle_start = {
        "left_90_clear": bool(_turn_clear(known_walls, start, 0, 1,
                                           wall_scene.footprint_half_extents_local, CELL_M)),
        "right_90_clear": bool(_turn_clear(known_walls, start, 0, 3,
                                            wall_scene.footprint_half_extents_local, CELL_M)),
        "half_extents_m": list(wall_scene.footprint_half_extents_local),
    }

    # Also check the original schedule's initial static objects and moving
    # pedestrian positions; this isolates any start-turn restriction beyond walls.
    schedule_checks = {}
    for schedule_index in (0, 1):
        scenario = scenario_from_bprime(payload, schedule_index)
        scene = MujocoNavigationScene(scenario, cell_size=CELL_M)
        world = World(scenario)
        schedule_checks[str(schedule_index)] = {
            "left_90": observed_turn(scene, world, start, 0.0, HEADINGS[1]),
            "right_90": observed_turn(scene, world, start, 0.0, HEADINGS[3]),
            "initial_obstacles": [list(c) for c in sorted(world.objects)],
            "initial_pedestrian_cells": [list(c) for c in sorted(world.people())],
        }

    front_wall = (start[0] + 1, start[1]) in walls
    back_cell = (start[0] - 1, start[1])
    backstep = {"front_cell_is_wall": front_wall,
                "back_cell": list(back_cell), "clear_against_walls": False,
                "left_90_after_backstep": None, "right_90_after_backstep": None,
                "aabb_route_actions_after_backstep": None,
                "actual_g1_route_check_after_backstep": None}
    scene = wall_scene
    if front_wall and (0 <= back_cell[0] < width and back_cell in free):
        scene._set_pose(start, 0.0)
        scene.mj.mj_forward(scene.model, scene.data)
        blocked, contacts, _, reason = scene.check_move(
            wall_world, start, back_cell, 0.0, target_yaw=0.0)
        backstep["clear_against_walls"] = not blocked
        backstep["move_failure_reason"] = reason
        backstep["move_contacts"] = {"wall": contacts.wall}
        if not blocked:
            scene._set_pose(back_cell, 0.0)
            scene.mj.mj_forward(scene.model, scene.data)
            backstep["left_90_after_backstep"] = observed_turn(
                scene, wall_world, back_cell, 0.0, HEADINGS[1])
            backstep["right_90_after_backstep"] = observed_turn(
                scene, wall_world, back_cell, 0.0, HEADINGS[3])

    # Full-map A* is only an upper-bound diagnostic, not an experiment or
    # evidence available to the policy. The selected actions are replayed once
    # against actual G1 contacts to distinguish AABB and physical feasibility.
    aabb_baseline = plan_g1_forward_facing(
        known_walls, start, goal, heading=0, unknown="blocked",
        local_extents=wall_scene.footprint_half_extents_local, cell_size=CELL_M)
    baseline_actual = execute_aabb_plan_on_actual_g1(
        wall_scene, wall_world, start, goal, aabb_baseline) if aabb_baseline else None
    back_route = []
    back_actual = None
    if backstep["clear_against_walls"]:
        back_route = plan_g1_forward_facing(
            known_walls, back_cell, goal, heading=0, unknown="blocked",
            local_extents=wall_scene.footprint_half_extents_local, cell_size=CELL_M)
        back_actual = execute_aabb_plan_on_actual_g1(
            wall_scene, wall_world, back_cell, goal, back_route) if back_route else None
    backstep["aabb_route_actions_after_backstep"] = len(back_route) if back_route else None
    backstep["actual_g1_route_check_after_backstep"] = back_actual

    return {
        "identity": identity, "mechanism": payload["mechanism"],
        "seed": int(payload["index"]), "start": list(start), "goal": list(goal),
        "adjacent_cardinal_wall_count": len(neighboring_walls),
        "adjacent_cardinal_wall_directions": neighboring_walls,
        "adjacent_diagonal_wall_count": len(neighboring_diagonal_walls),
        "adjacent_diagonal_wall_directions": neighboring_diagonal_walls,
        "initial_forward_east_cell_is_wall": front_wall,
        "actual_g1_wall_only_start_turns": actual_start,
        "aabb_full_map_start_turns": rectangle_start,
        "actual_g1_turns_in_initial_saved_schedules": schedule_checks,
        "full_map_aabb_route_actions_without_backstep": len(aabb_baseline) if aabb_baseline else None,
        "actual_g1_check_of_aabb_route_without_backstep": baseline_actual,
        "first_step_backstep_diagnostic": backstep,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provenance", type=Path, default=DEFAULT_PROVENANCE)
    parser.add_argument("--forward-run", type=Path, default=DEFAULT_FORWARD_RUN)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error(f"Refusing to overwrite existing diagnostic: {args.output}")
    csv_output = args.output.with_suffix(".csv")
    if csv_output.exists():
        parser.error(f"Refusing to overwrite existing diagnostic table: {csv_output}")
    provenance_bytes = args.provenance.read_bytes()
    provenance = json.loads(provenance_bytes)
    roots = [ROOT / p for p in provenance["source_store_roots"]]
    details = []
    for identity in provenance["world_identities"]:
        payload, path, raw = read_record(identity, roots)
        detail = diagnose_world(identity, payload, roots)
        detail["source_record"] = path.relative_to(ROOT).as_posix()
        detail["source_record_sha256"] = sha(raw)
        details.append(detail)
    details.sort(key=lambda r: (("R", "BP", "M").index(r["mechanism"]), r["seed"]))

    episodes_path = args.forward_run / "episodes.csv"
    episodes_bytes = episodes_path.read_bytes()
    episodes = list(csv.DictReader(episodes_bytes.decode().splitlines()))
    outcome_by_world = {}
    for row in episodes:
        state = outcome_by_world.setdefault(row["world_identity"], {
            "episodes": 0, "successes": 0, "selected_forward": 0, "selected_turns": 0,
            "no_route_steps": 0, "rotation_collision_attempts": 0,
        })
        state["episodes"] += 1
        state["successes"] += row["success"] == "True"
        state["selected_forward"] += int(row.get("g1_forward_actions", 0))
        state["selected_turns"] += int(row.get("g1_in_place_turns", 0))
        state["no_route_steps"] += int(row.get("g1_navigation_no_route_steps", 0))
        reasons = json.loads(row["g1_blocked_movement_reasons"].replace("'", '"'))
        state["rotation_collision_attempts"] += int(reasons.get("rotation_collision", 0))
    for detail in details:
        detail["forward_first_run_outcomes"] = outcome_by_world.get(detail["identity"], {})

    summary = {}
    for mechanism in ("R", "BP", "M"):
        group = [r for r in details if r["mechanism"] == mechanism]
        episode_rows = [r for r in episodes if r["mechanism"] == mechanism]
        summary[mechanism] = {
            "worlds": len(group),
            "adjacent_wall_count_distribution": {
                str(n): sum(r["adjacent_cardinal_wall_count"] == n for r in group)
                for n in range(5)},
            "adjacent_diagonal_wall_count_distribution": {
                str(n): sum(r["adjacent_diagonal_wall_count"] == n for r in group)
                for n in range(5)},
            "wall_only_actual_left_turns_clear": sum(
                r["actual_g1_wall_only_start_turns"]["left_90"]["clear"] for r in group),
            "wall_only_actual_right_turns_clear": sum(
                r["actual_g1_wall_only_start_turns"]["right_90"]["clear"] for r in group),
            "aabb_left_turns_clear": sum(r["aabb_full_map_start_turns"]["left_90_clear"] for r in group),
            "aabb_right_turns_clear": sum(r["aabb_full_map_start_turns"]["right_90_clear"] for r in group),
            "front_wall_worlds": sum(r["initial_forward_east_cell_is_wall"] for r in group),
            "wall_only_backsteps_clear": sum(
                r["first_step_backstep_diagnostic"]["clear_against_walls"] for r in group),
            "full_map_aabb_routes_after_backstep": sum(
                r["first_step_backstep_diagnostic"]["aabb_route_actions_after_backstep"] is not None
                for r in group),
            "forward_first_episodes": len(episode_rows),
            "forward_first_successes": sum(r["success"] == "True" for r in episode_rows),
            "forward_first_no_route_steps": sum(int(r["g1_navigation_no_route_steps"]) for r in episode_rows),
            "forward_first_rotation_collision_attempts": sum(
                int(json.loads(r["g1_blocked_movement_reasons"].replace("'", '"')).get("rotation_collision", 0))
                for r in episode_rows),
        }
    report = {
        "status": "PASS_RETROSPECTIVE_CLEARANCE_DIAGNOSTIC",
        "interpretation_limits": [
            "Actual G1 checks use the pinned MuJoCo collision geoms at saved start cells; no navigation actions or experiments were run.",
            "The AABB and full-map A* checks are retrospective diagnostics using the saved complete static wall grid; they were not inputs to any policy.",
            "The one-step backstep route result assumes the entire static map is known and does not model sensing, dynamic events after step zero, or a changed experiment policy.",
            "Schedule 0 and 1 turn checks include each saved initial obstacles/pedestrian arrangement; wall-only checks isolate maze walls.",
        ],
        "cell_size_m": CELL_M,
        "provenance": {"path": args.provenance.relative_to(ROOT).as_posix(),
                       "sha256": sha(provenance_bytes)},
        "forward_first_run": {"episodes_csv": (args.forward_run / "episodes.csv").relative_to(ROOT).as_posix(),
                              "sha256": sha(episodes_bytes)},
        "summary_by_mechanism": summary,
        "worlds": details,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    columns = ("mechanism", "seed", "start_x", "start_y", "goal_x", "goal_y",
               "east_wall", "north_wall", "west_wall", "south_wall",
               "adjacent_cardinal_wall_count", "adjacent_diagonal_wall_count",
               "actual_left_90_clear", "actual_right_90_clear",
               "aabb_left_90_clear", "aabb_right_90_clear", "front_east_is_wall",
               "backstep_clear", "aabb_route_actions_after_backstep",
               "actual_g1_reaches_goal_after_backstep")
    import io
    table = io.StringIO()
    writer = csv.DictWriter(table, fieldnames=columns)
    writer.writeheader()
    for row in details:
        directions = set(row["adjacent_cardinal_wall_directions"])
        back = row["first_step_backstep_diagnostic"]
        actual_route = back["actual_g1_route_check_after_backstep"] or {}
        writer.writerow({
            "mechanism": row["mechanism"], "seed": row["seed"],
            "start_x": row["start"][0], "start_y": row["start"][1],
            "goal_x": row["goal"][0], "goal_y": row["goal"][1],
            "east_wall": int("east" in directions), "north_wall": int("north" in directions),
            "west_wall": int("west" in directions), "south_wall": int("south" in directions),
            "adjacent_cardinal_wall_count": row["adjacent_cardinal_wall_count"],
            "adjacent_diagonal_wall_count": row["adjacent_diagonal_wall_count"],
            "actual_left_90_clear": int(row["actual_g1_wall_only_start_turns"]["left_90"]["clear"]),
            "actual_right_90_clear": int(row["actual_g1_wall_only_start_turns"]["right_90"]["clear"]),
            "aabb_left_90_clear": int(row["aabb_full_map_start_turns"]["left_90_clear"]),
            "aabb_right_90_clear": int(row["aabb_full_map_start_turns"]["right_90_clear"]),
            "front_east_is_wall": int(row["initial_forward_east_cell_is_wall"]),
            "backstep_clear": int(back["clear_against_walls"]),
            "aabb_route_actions_after_backstep": back["aabb_route_actions_after_backstep"],
            "actual_g1_reaches_goal_after_backstep": int(actual_route.get("reaches_goal", False)),
        })
    csv_output.write_text(table.getvalue())
    print(json.dumps({"status": report["status"], "output": str(args.output),
                      "table": str(csv_output),
                      "worlds": len(details), "summary_by_mechanism": summary}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
