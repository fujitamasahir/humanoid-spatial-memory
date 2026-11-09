"""Rebuild one saved Phase 2 episode trace and export its moving proxy replay.

This is presentation-only: it loads one admitted saved fit record, repeats the
specified Phase 2 episode to recover its per-frame poses, verifies the result
against the full-run CSV and non-move action log, then exports an MP4/GIF. It
does not generate candidate worlds or alter the source run.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import phase2_mujoco_navigation as runner
from spatial_memory.evaluation import run_episode
from spatial_memory.mujoco_navigation import MujocoNavigationScene
from spatial_memory.mujoco_perception import MujocoRayPerception
from spatial_memory.navigation import (HEADINGS, assess_observed_pedestrian_risk,
                                        heading_index, plan_g1_default_policy)
from spatial_memory.pedestrian_tracking import ObservedPedestrianTracker
from spatial_memory.simulation import scenario_from_bprime

DEFAULT_RESULT = ROOT / "results/phase2_mujoco/g1_forward_first_shield_turns_v1_full_288"
DEFAULT_OUTPUT = ROOT / "results/phase2_mujoco/g1_pedestrian_capsule_replay_M80030007_periodic_s1_v1"
DEFAULT_IDENTITY = "phase1.5-v0.4-BPRIME-1:fit:M:80030007"
DEFAULT_METHOD = "periodic"
DEFAULT_SCHEDULE = 1
REPLAY_WALL_RGBA = "0.18 0.23 0.30 0.16"
REPLAY_CAPSULE_RGBA = "0.95 0.30 0.22 0.24"


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode()


def load_payload(identity: str) -> tuple[dict, Path, bytes]:
    target = hashlib.sha256(identity.encode()).hexdigest() + ".json.gz"
    for root in runner.STORES:
        path = ROOT / root / "records" / target
        if path.is_file():
            raw = path.read_bytes()
            wrapper = json.loads(gzip.decompress(raw))
            payload = wrapper.get("payload")
            if (wrapper.get("identity") != identity or payload.get("identity") != identity
                    or wrapper.get("payload_sha256") != digest(canonical(payload))):
                raise ValueError("Saved fit record identity or payload hash did not verify")
            return payload, path, raw
    raise FileNotFoundError(f"Saved fit record not found: {identity}")


def replay(result_dir: Path, output_dir: Path, fps: int, speed: float,
           identity: str, method: str, schedule: int) -> dict:
    result_dir = result_dir.resolve()
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite {output_dir}")
    source_episode_bytes = (result_dir / "episodes.csv").read_bytes()
    source_action_bytes = (result_dir / "action_events.json").read_bytes()
    source_provenance_bytes = (result_dir / "provenance.json").read_bytes()
    rows = list(csv.DictReader(source_episode_bytes.decode().splitlines()))
    matches = [r for r in rows if r["world_identity"] == identity
               and int(r["schedule"]) == schedule and r["method"] == method]
    if len(matches) != 1:
        raise ValueError(f"Expected one saved episode row, found {len(matches)}")
    source_row = matches[0]
    provenance = json.loads(source_provenance_bytes)
    config = json.loads(json.dumps(provenance["policy_config"]))
    payload, record_path, record_bytes = load_payload(identity)
    world_payloads = {item["identity"]: item for item in runner.admitted_worlds()}
    if identity not in world_payloads or world_payloads[identity]["identity"] != payload["identity"]:
        raise ValueError("Target fit identity is not admitted by the existing saved-world inventory")
    scenario = scenario_from_bprime(payload, schedule)
    scene = MujocoNavigationScene(scenario,
        cell_size=config["mujoco_cell_size_m"],
        timestep=config["mujoco_timestep_seconds"])
    perception = MujocoRayPerception(scene, **config["mujoco_ray_sensor"])
    tracker = ObservedPedestrianTracker(max_age_steps=8)
    state = {"static_obstacle_cells": set(), "static_obstacle_step": -1,
             "planner_step": 0, "action_shield_queries": 0,
             "last_reason": "no_feasible_forward_route"}
    config["g1_navigation"]["local_half_extents_m"] = list(scene.footprint_half_extents_local)

    def planner(grid, position, goal, unknown, yaw, blocked):
        state["planner_step"] += 1
        context = tracker.context()
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
            if kind == "turn":
                state["last_reason"] = "route_direction_change"
            elif kind == "sidestep":
                state["last_reason"] = "observed_static_obstacle_blocks_forward_path"
            elif kind == "retreat":
                state["last_reason"] = assess_observed_pedestrian_risk(
                    position, heading_index(yaw), context,
                    step=state["planner_step"]) or "observed_oncoming_pedestrian_imminent"
            elif kind == "wait":
                state["last_reason"] = str(value)
            else:
                state["last_reason"] = "forward_route_segment"
        else:
            state["last_reason"] = "no_feasible_forward_route"
        return route

    def record_observation(_observation, step, _position):
        stats = perception.last_stats
        tracker.observe(step, stats.get("visible_pedestrian_cells", ()))
        state["static_obstacle_cells"] = {
            tuple(cell) for cell in stats.get("visible_persistent_obstacle_cells", ())}
        state["static_obstacle_step"] = int(step)

    def action_reason(_action, _position, _yaw):
        return state["last_reason"]

    def check_action(world, position, action, yaw):
        state["action_shield_queries"] += 1
        kind, value = action
        if kind in {"move", "sidestep", "retreat"}:
            return scene.check_move(world, position, tuple(value), yaw, target_yaw=yaw)
        return scene.check_turn(world, position, yaw, HEADINGS[int(value)])

    metrics, frames = run_episode(scenario, config, method, seed=42,
        _frame_callback=scene.update, _observation_provider=perception.observe,
        _g1_planner=planner, _action_checker=check_action,
        _initial_observation_callback=record_observation,
        _observation_callback=record_observation, _g1_action_reason=action_reason)
    selected_checks = sum(frame.get("navigation_action") is not None
                          and frame["navigation_action"][0] != "wait" for frame in frames)
    metrics["g1_actual_collision_shield_queries"] = state["action_shield_queries"]
    metrics["g1_selected_actions_requiring_collision_check"] = selected_checks
    metrics["g1_unattempted_collision_queries"] = 0
    metrics["g1_shield_query_count_valid"] = state["action_shield_queries"] == selected_checks
    metrics["travel_distance_m"] = metrics["travel_distance"] * scene.cell_size

    # Require exact agreement for the persisted episode outcomes and counters.
    comparisons = {
        "success": metrics["success"] == (source_row["success"] == "True"),
        "contact_free_success": metrics["g1_contact_free_success"] == (source_row["contact_free_success"] == "True"),
        "elapsed_steps": int(metrics["elapsed_steps"]) == int(source_row["elapsed_steps"]),
        "forward_actions": int(metrics["g1_forward_actions"]) == int(source_row["g1_forward_actions"]),
        "in_place_turns": int(metrics["g1_in_place_turns"]) == int(source_row["g1_in_place_turns"]),
        "blocked_attempts": int(metrics["g1_footprint_blocked_attempts"]) == int(source_row["g1_footprint_blocked_attempts"]),
        "pedestrian_contacts": int(metrics["g1_pedestrian_contact_pairs"]) == int(source_row["g1_pedestrian_contact_pairs"]),
        "unwanted_contacts": int(metrics["g1_unwanted_contact_pairs"]) == int(source_row["g1_unwanted_contact_pairs"]),
    }
    source_events = [e for e in json.loads(source_action_bytes)
        if e["world_identity"] == identity and e["schedule_index"] == schedule
        and e["method"] == method]
    rebuilt_events = []
    for frame in frames:
        action = frame.get("navigation_action")
        if action is not None and action[0] != "move":
            rebuilt_events.append(dict(world_identity=identity, schedule_index=schedule,
                method=method, step=frame["step"], position=list(frame["position"]),
                heading_yaw=frame.get("heading_yaw"), action_kind=action[0],
                action_value=action[1], reason=frame.get("navigation_action_reason"),
                accepted=not frame.get("blocked", False),
                collision_checked=action[0] != "wait"))
    comparisons["non_move_action_trace"] = rebuilt_events == source_events
    if not all(comparisons.values()):
        raise RuntimeError(f"Replay did not match saved episode; refusing export: {comparisons}")

    output_dir.mkdir(parents=True)
    source_dir = output_dir / "replay_source"
    source_dir.mkdir()
    scenario_json = dict(width=scenario.width, height=scenario.height,
                         cell_size_m=scene.cell_size, start=list(scenario.start),
                         goal=list(scenario.goal))
    trajectory = [dict(step=f["step"], position=list(f["position"]),
        planned=f.get("planned", []), moved=bool(f.get("moved", False)),
        blocked=bool(f.get("blocked", False)),
        heading_yaw=float(f.get("heading_yaw", 0.0)),
        heading_changed=bool(f.get("heading_changed", False)),
        navigation_action=f.get("navigation_action"),
        navigation_action_reason=f.get("navigation_action_reason"),
        people=f.get("g1_pedestrians", []),
        active_objects=f.get("g1_active_objects", []),
        g1_pedestrian_contact_pairs=int(f.get("g1_pedestrian_contact_pairs", 0)),
        g1_wall_contact_pairs=int(f.get("g1_wall_contact_pairs", 0)),
        g1_persistent_obstacle_contact_pairs=int(f.get("g1_persistent_obstacle_contact_pairs", 0)))
        for f in frames]
    (source_dir / "scenario.json").write_text(json.dumps(scenario_json, indent=2)+"\n")
    (source_dir / "trajectory.json").write_text(json.dumps(trajectory, indent=2)+"\n")
    # The saved experiment's MJCF includes the same fixed-path capsule geometry.
    (source_dir / "scene.xml").write_text(scene.xml+"\n")
    source_summary = dict(success=metrics["success"],
        contact_free_success=metrics["g1_contact_free_success"],
        g1_unwanted_contact_pairs=metrics["g1_unwanted_contact_pairs"],
        g1_pedestrian_contact_pairs=metrics["g1_pedestrian_contact_pairs"],
        elapsed_steps=metrics["elapsed_steps"], final_position=list(metrics["final_position"]),
        g1_forward_actions=metrics["g1_forward_actions"],
        g1_in_place_turns=metrics["g1_in_place_turns"],
        g1_footprint_blocked_attempts=metrics["g1_footprint_blocked_attempts"])
    (source_dir / "summary.json").write_text(json.dumps(source_summary, indent=2)+"\n")
    model_files = json.loads(source_provenance_bytes)["robot_model_files"]
    (source_dir / "provenance.json").write_text(json.dumps({
        "robot_model": "third_party/unitree_g1/g1.xml; actual Unitree G1 model",
        "robot_model_files": model_files,
        "reconstructed_from": str(result_dir.relative_to(ROOT)),
        "source_world_identity": identity, "schedule_index": schedule,
        "method": method, "episode_seed": 42,
    }, indent=2)+"\n")
    replay_report = {
        "status": "PASS_DETERMINISTIC_EPISODE_REPLAY_MATCH",
        "source_full_run": str(result_dir.relative_to(ROOT)),
        "source_episode": {"world_identity": identity, "schedule_index": schedule,
                           "method": method, "episode_seed": 42},
        "source_files_sha256": {
            "episodes.csv": digest(source_episode_bytes),
            "action_events.json": digest(source_action_bytes),
            "provenance.json": digest(source_provenance_bytes),
        },
        "fit_record": {"path": record_path.relative_to(ROOT).as_posix(),
                       "sha256": digest(record_bytes)},
        "replay_comparisons": comparisons,
        "saved_episode_metrics": source_summary,
        "pedestrian_proxy": {"kind": "MuJoCo mocap capsule; not a humanoid model",
            "radius_m": 0.19, "centerline_endpoints_z_m": [0.20, 1.28],
            "overall_height_m": 1.46, "trajectory_source": "saved B-prime schedule positions"},
        "trajectory_frames": len(trajectory),
        "note": "The 288-episode result retained action events, not per-frame pose trajectories. This display trace was rebuilt by deterministic replay and accepted only after saved outcome counters and all recorded non-move actions matched exactly. No candidate or maze was regenerated.",
    }
    (output_dir / "replay_validation.json").write_text(json.dumps(replay_report, indent=2, sort_keys=True)+"\n")

    exporter_path = ROOT / "scripts/export_phase2_portfolio_demo.py"
    spec = importlib.util.spec_from_file_location("phase2_portfolio_exporter", exporter_path)
    exporter = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(exporter)
    # Presentation-only overrides: make layered walls subdued, and render the
    # collision proxy as a translucent volume so it does not hide G1 during
    # the already-recorded contact episodes. Geometry and collision filters
    # are unchanged; the contact audit still runs against the original shapes.
    exporter.WALL_RGBA = REPLAY_WALL_RGBA
    original_display_xml = exporter.make_display_xml

    def display_xml_with_visible_proxy(source, *, offwidth=1280, offheight=720):
        display_xml = original_display_xml(source, offwidth=offwidth, offheight=offheight)
        display_root = ET.fromstring(display_xml)
        proxy = display_root.find(".//geom[@name='pedestrian_geom_0']")
        if proxy is not None:
            proxy.set("rgba", REPLAY_CAPSULE_RGBA)
        return ET.tostring(display_root, encoding="unicode")

    exporter.make_display_xml = display_xml_with_visible_proxy
    render_dir = output_dir / "portfolio_export"
    exporter.render_frames(source_dir, render_dir, camera_mode="tracking",
        fps=fps, width=1280, height=720, speed=speed,
        export_mp4=True, export_gif=True)
    exporter.encode_mp4(render_dir, fps)
    exporter.encode_gif(render_dir, fps)
    metadata_path = render_dir / "metadata.json"
    metadata = json.loads(metadata_path.read_text())
    metadata["trajectory_origin"] = replay_report["note"]
    metadata["pedestrian_proxy"] = replay_report["pedestrian_proxy"]
    metadata["source_experiment_episode"] = replay_report["source_episode"]
    metadata["walls_rgba"] = REPLAY_WALL_RGBA
    metadata["pedestrian_proxy_rgba"] = REPLAY_CAPSULE_RGBA
    metadata["wall_style_note"] = "Presentation-only subdued blue-gray tint and 0.16 alpha; applied only to wall geoms to reduce layered-wall washout."
    metadata["proxy_style_note"] = "The capsule remains the original 0.19 m radius collision geometry and follows its saved schedule; only its display alpha is 0.24 so the G1 remains visible during recorded contacts. Collision geometry, filters, and the contact audit are unchanged."
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True)+"\n")
    (render_dir / "presentation_note.md").write_text(
        "# Presentation-only moving pedestrian proxy replay\n\n"
        f"- Replayed saved episode: `{identity}`, schedule {schedule}, method `{method}`.\n"
        "- The pedestrian is a 0.19 m radius MuJoCo mocap capsule following the stored B-prime schedule; it is not a humanoid model. Its centerline is 1.08 m and total capsule height is 1.46 m.\n"
        "- The full 288 run did not retain per-frame poses. This trace was reconstructed by deterministic replay; saved episode metrics and all recorded non-move action events matched.\n"
        f"- Presentation wall RGBA: `{REPLAY_WALL_RGBA}`. The proxy display alpha is `{REPLAY_CAPSULE_RGBA.split()[-1]}`; geometry, filters, and G1 are unchanged.\n"
        "- Presentation-only kinematic replay; no walking controller. Contact in the source episode is intentionally visible and remains reported in the source experiment metrics.\n")
    exporter.write_artifact_manifest(render_dir)
    return replay_report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result-dir", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--fps", type=int, default=24)
    parser.add_argument("--speed", type=float, default=0.15,
                        help="seconds per experiment step; 0.15 gives an approximately 13-second replay")
    parser.add_argument("--identity", default=DEFAULT_IDENTITY)
    parser.add_argument("--method", choices=("static", "periodic", "event_triggered"),
                        default=DEFAULT_METHOD)
    parser.add_argument("--schedule", type=int, default=DEFAULT_SCHEDULE)
    args = parser.parse_args()
    report = replay(args.result_dir, args.output_dir, args.fps, args.speed,
                    args.identity, args.method, args.schedule)
    print(json.dumps({"status": report["status"],
        "output": str(args.output_dir / "portfolio_export"),
        "gif": str(args.output_dir / "portfolio_export/portfolio_demo.gif"),
        "mp4": str(args.output_dir / "portfolio_export/portfolio_demo.mp4"),
        "trajectory_frames": report["trajectory_frames"],
        "replay_comparisons": report["replay_comparisons"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
