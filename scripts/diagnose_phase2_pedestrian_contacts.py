"""Reconstruct the two saved Phase 2 pedestrian-contact episodes for diagnosis.

This is an evaluator-side retrospective replay of already admitted fit worlds.
It does not generate candidate worlds and writes only a new diagnostic report.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import phase2_mujoco_navigation as runner
import spatial_memory.navigation as navigation
from spatial_memory.evaluation import run_episode
from spatial_memory.mujoco_navigation import MujocoNavigationScene
from spatial_memory.mujoco_perception import MujocoRayPerception
from spatial_memory.navigation import (HEADINGS, assess_observed_pedestrian_risk,
                                       heading_index, plan_g1_default_policy)
from spatial_memory.pedestrian_tracking import ObservedPedestrianTracker
from spatial_memory.simulation import scenario_from_bprime

BASELINE = ROOT / "results/phase2_mujoco/g1_forward_first_shield_turns_v1_full_288"
DEFAULT_OUT = ROOT / "results/phase2_mujoco/pedestrian_contact_diagnosis_v1"


def sha(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reproduce(row: dict, config: dict, *, verify_saved: bool = True) -> dict:
    payload = next(w for w in runner.admitted_worlds()
                   if w["identity"] == row["world_identity"])
    schedule, method = int(row["schedule"]), row["method"]
    scenario = scenario_from_bprime(payload, schedule)
    scene = MujocoNavigationScene(scenario, cell_size=config["mujoco_cell_size_m"],
        timestep=config["mujoco_timestep_seconds"])
    perception = MujocoRayPerception(scene, **config["mujoco_ray_sensor"])
    tracker = ObservedPedestrianTracker(max_age_steps=8)
    state = {"static_obstacle_cells": set(), "static_obstacle_step": -1,
             "planner_step": 0, "shield_queries": 0,
             "last_reason": "no_feasible_forward_route", "latest_observation": None,
             "tracker_context": {}, "risk_at_decision": None}
    cfg = json.loads(json.dumps(config))
    cfg["g1_navigation"]["local_half_extents_m"] = list(scene.footprint_half_extents_local)

    def planner(grid, position, goal, unknown, yaw, blocked):
        state["planner_step"] += 1
        context = tracker.context()
        state["tracker_context"] = context
        state["risk_at_decision"] = assess_observed_pedestrian_risk(
            position, heading_index(yaw), context, step=state["planner_step"])
        recent = (state["static_obstacle_cells"]
            if 0 <= state["planner_step"]-state["static_obstacle_step"] <= 8 else set())
        route = plan_g1_default_policy(grid, position, goal,
            heading=heading_index(yaw), unknown=unknown,
            local_extents=scene.footprint_half_extents_local,
            cell_size=scene.cell_size, blocked_actions=blocked,
            static_obstacle_cells=recent, pedestrian_context=context,
            step=state["planner_step"])
        if route:
            kind, value = route[0]
            if kind == "turn": state["last_reason"] = "route_direction_change"
            elif kind == "sidestep": state["last_reason"] = "observed_static_obstacle_blocks_forward_path"
            elif kind == "retreat": state["last_reason"] = assess_observed_pedestrian_risk(
                position, heading_index(yaw), context, step=state["planner_step"]
                ) or "observed_oncoming_pedestrian_imminent"
            elif kind == "wait": state["last_reason"] = str(value)
            else: state["last_reason"] = "forward_route_segment"
        else: state["last_reason"] = "no_feasible_forward_route"
        return route

    def observe(_observation, step, _position):
        stats = perception.last_stats
        cells = stats.get("visible_pedestrian_cells", ())
        tracker.observe(step, cells)
        state["tracker_context"] = tracker.context()
        state["static_obstacle_cells"] = {tuple(c) for c in
            stats.get("visible_persistent_obstacle_cells", ())}
        state["static_obstacle_step"] = int(step)
        state["latest_observation"] = {"step": int(step),
            "visible_pedestrian_cells": [list(c) for c in cells],
            "sensor_pedestrian_ray_hits": stats.get("hits_by_type", {}).get("pedestrians", 0),
            "sensor_origin_world": stats.get("sensor_origin_world"),
            "range_m": stats.get("range_m"), "fov_deg": stats.get("horizontal_fov_deg")}

    def checker(world, position, action, yaw):
        state["shield_queries"] += 1
        kind, value = action
        if kind in {"move", "sidestep", "retreat"}:
            return scene.check_move(world, position, tuple(value), yaw, target_yaw=yaw)
        return scene.check_turn(world, position, yaw, HEADINGS[int(value)])

    def action_reason(_action, _position, _yaw):
        return state["last_reason"]

    details = []
    def capture(world, frame):
        contacts = scene.update(world, frame)
        action = frame.get("navigation_action")
        people = sorted(map(list, world.people()))
        obs = state["latest_observation"]
        visible_people = obs["visible_pedestrian_cells"] if obs else []
        details.append({"step": int(frame["step"]), "position": list(frame["position"]),
            "heading_yaw_rad": float(frame["heading_yaw"]),
            "heading_cardinal": heading_index(frame["heading_yaw"]),
            "action": list(action) if action else None,
            "action_reason": frame.get("navigation_action_reason"),
            "moved": bool(frame.get("moved")), "blocked": bool(frame.get("blocked")),
            "blocked_reason": frame.get("blocked_reason"),
            "current_pedestrian_cells_evaluator_only": people,
            "latest_permitted_observation": obs,
            "observed_motion_context_at_decision": state["tracker_context"],
            "risk_assessment_at_decision": state["risk_at_decision"],
            "visible_pedestrian_currently": any(c in people for c in visible_people),
            "pedestrian_contacts": int(contacts.get("g1_pedestrian_contact_pairs", 0)),
            "attempt_pedestrian_contact_pairs": int(contacts.get("g1_attempt_pedestrian_contact_pairs", 0)),
            "wall_contacts": int(contacts.get("g1_wall_contact_pairs", 0)),
        })
        return contacts

    metrics, frames = run_episode(scenario, cfg, method, seed=42,
        _frame_callback=capture, _observation_provider=perception.observe,
        _g1_planner=planner, _action_checker=checker,
        _g1_action_reason=action_reason,
        _initial_observation_callback=observe, _observation_callback=observe)
    metric_comparisons = {
        "success": metrics["success"] == (row["success"] == "True"),
        "contact_free_success": metrics["g1_contact_free_success"] == (row["contact_free_success"] == "True"),
        "elapsed_steps": int(metrics["elapsed_steps"]) == int(row["elapsed_steps"]),
        "forward_actions": int(metrics["g1_forward_actions"]) == int(row["g1_forward_actions"]),
        "lateral_actions": int(metrics["g1_lateral_actions"]) == int(row["g1_lateral_actions"]),
        "backward_actions": int(metrics["g1_backward_actions"]) == int(row["g1_backward_actions"]),
        "turns": int(metrics["g1_in_place_turns"]) == int(row["g1_in_place_turns"]),
        "waits": int(metrics["g1_waits"]) == int(row["g1_waits"]),
        "blocked_attempts": int(metrics["g1_footprint_blocked_attempts"]) == int(row["g1_footprint_blocked_attempts"]),
        "pedestrian_contacts": int(metrics["g1_pedestrian_contact_pairs"]) == int(row["g1_pedestrian_contact_pairs"]),
        "unwanted_contacts": int(metrics["g1_unwanted_contact_pairs"]) == int(row["g1_unwanted_contact_pairs"]),
        "observations": int(metrics["observation_count"]) == int(row["observation_count"]),
    }
    source_events = [event for event in json.loads((BASELINE / "action_events.json").read_text())
        if event["world_identity"] == row["world_identity"]
        and int(event["schedule_index"]) == schedule and event["method"] == method]
    rebuilt_events = []
    for frame in frames:
        action = frame.get("navigation_action")
        if action is not None and action[0] != "move":
            rebuilt_events.append(dict(world_identity=row["world_identity"],
                schedule_index=schedule, method=method, step=frame["step"],
                position=list(frame["position"]), heading_yaw=frame.get("heading_yaw"),
                action_kind=action[0], action_value=action[1],
                reason=frame.get("navigation_action_reason"),
                accepted=not frame.get("blocked", False),
                collision_checked=action[0] != "wait"))
    action_trace_matches = rebuilt_events == source_events
    replay_matches = all(metric_comparisons.values()) and action_trace_matches
    if verify_saved and not replay_matches:
        raise RuntimeError(f"Deterministic replay mismatch: {row['world_identity']} {schedule} {method}; metrics={metric_comparisons}; action_trace={action_trace_matches}; source={source_events[:3]}; rebuilt={rebuilt_events[:3]}")
    selected_checks = sum(frame.get("navigation_action") is not None
        and frame["navigation_action"][0] != "wait" for frame in frames)
    if verify_saved and (state["shield_queries"] != selected_checks
            or selected_checks != int(row["g1_selected_actions_requiring_collision_check"])):
        raise RuntimeError(f"Action shield accounting mismatch: {row['world_identity']} {schedule} {method}")
    for detail, frame in zip(details, frames):
        action = frame.get("navigation_action")
        detail["action"] = ([action[0], list(action[1]) if action[0] in
            {"move", "sidestep", "retreat"} else action[1]] if action else None)
        detail["action_reason"] = frame.get("navigation_action_reason")
        detail["blocked_reason"] = frame.get("blocked_reason")
        detail["moved"] = bool(frame.get("moved"))
        detail["blocked"] = bool(frame.get("blocked"))
        detail["attempt_pedestrian_contact_pairs"] = int(
            frame.get("g1_attempt_pedestrian_contact_pairs", 0))
        detail["attempt_wall_contact_pairs"] = int(
            frame.get("g1_attempt_wall_contact_pairs", 0))
    contact_steps = [item for item in details if item["pedestrian_contacts"] > 0]
    return {"identity": row["world_identity"], "mechanism": row["mechanism"],
        "schedule": schedule, "method": method, "seed": 42,
        "replay_matches_saved": replay_matches, "metric_comparisons": metric_comparisons,
        "action_trace_matches_saved": action_trace_matches,
        "saved_contacts": int(row["g1_pedestrian_contact_pairs"]),
        "replayed_metrics": {"success": bool(metrics["success"]),
            "contact_free_success": bool(metrics["g1_contact_free_success"]),
            "pedestrian_contact_pairs": int(metrics["g1_pedestrian_contact_pairs"]),
            "elapsed_steps": int(metrics["elapsed_steps"]),
            "forward_actions": int(metrics["g1_forward_actions"]),
            "lateral_actions": int(metrics["g1_lateral_actions"]),
            "backward_actions": int(metrics["g1_backward_actions"]),
            "turns": int(metrics["g1_in_place_turns"]),
            "waits": int(metrics["g1_waits"])},
        "saved_success": row["success"] == "True",
        "saved_contact_free_success": row["contact_free_success"] == "True",
        "sensor_observation_policy": {"range_m": config["mujoco_ray_sensor"]["range_m"],
            "horizontal_fov_deg": config["mujoco_ray_sensor"]["horizontal_fov_deg"],
            "ray_count": config["mujoco_ray_sensor"]["ray_count"],
            "observation_budget": config["max_observations"],
            "observations_used": int(metrics["observation_count"])},
        "action_shield_integrity": {"queries": int(state["shield_queries"]),
            "selected_actions_required_check": int(selected_checks),
            "unselected_queries": 0, "query_count_valid": state["shield_queries"] == selected_checks},
        "contact_frames": contact_steps,
        "timeline": details,
        "trajectory_source": "saved admitted B-prime fit record and existing schedule; evaluator-only replay"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--current-policy-probe", action="store_true",
        help="replay only M:80030007 with the current prospective safety policy; not baseline verification")
    args = parser.parse_args()
    if args.output_dir.exists(): raise FileExistsError(args.output_dir)
    rows = list(csv.DictReader((BASELINE / "episodes.csv").open()))
    contacts = [row for row in rows if int(row.get("g1_pedestrian_contact_pairs") or 0) > 0]
    if len(contacts) != 2: raise ValueError(f"Expected exactly two contact episodes, found {len(contacts)}")
    config = json.loads((BASELINE / "provenance.json").read_text())["policy_config"]
    if args.current_policy_probe:
        targets = [row for row in contacts if row["mechanism"] == "M"]
        if len(targets) != 1: raise ValueError("Expected one saved M contact episode")
        episodes = [reproduce(targets[0], config, verify_saved=False)]
    else:
        # Replay exact baseline policy, disabling only the newly introduced
        # escape helper for this historical reconstruction.
        current_escape = navigation._eligible_pedestrian_sidestep
        navigation._eligible_pedestrian_sidestep = lambda *_args, **_kwargs: None
        try:
            episodes = [reproduce(row, config) for row in contacts]
        finally:
            navigation._eligible_pedestrian_sidestep = current_escape
    args.output_dir.mkdir(parents=True)
    (args.output_dir / "contact_episode_diagnosis.json").write_text(json.dumps({
        "baseline": str(BASELINE.relative_to(ROOT)), "baseline_episode_csv_sha256": sha(BASELINE/"episodes.csv"),
        "baseline_action_events_sha256": sha(BASELINE/"action_events.json"),
        "baseline_provenance_sha256": sha(BASELINE/"provenance.json"),
        "diagnostic_scope": "retrospective only; hidden simulator positions appear only in explicitly evaluator-only fields; not available to online planner",
        "episodes": episodes,
    }, indent=2, sort_keys=True)+"\n")
    print(json.dumps({"status":("PASS_CURRENT_POLICY_PROBE" if args.current_policy_probe
                                   else "PASS_DETERMINISTIC_BASELINE_REPLAY"),
        "episodes": len(episodes),
        "output": str(args.output_dir.resolve().relative_to(ROOT)),
        "contacts": [{"identity": ep["identity"], "contact_frames": len(ep["contact_frames"]),
                      "first_contact_step": ep["contact_frames"][0]["step"] if ep["contact_frames"] else None,
                      "observations": ep["sensor_observation_policy"]["observations_used"]}
                     for ep in episodes]}, indent=2))


if __name__ == "__main__": main()
