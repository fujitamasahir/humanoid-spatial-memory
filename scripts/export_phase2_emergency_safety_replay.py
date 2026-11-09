"""Export a presentation replay from a saved Emergency Safety Sensor trace.

This consumes the already-recorded single-episode trace and the matching saved
scene from v7. It does not rerun the experiment or alter its results.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TRACE = ROOT / "results/phase2_mujoco/g1_static_independent_safety_R80000001_s1_v5/safety_episode_trace.json"
DEFAULT_SOURCE = ROOT / "results/phase2_mujoco/g1_pedestrian_capsule_replay_R80000001_static_s1_v7/replay_source"
DEFAULT_OUTPUT = ROOT / "results/phase2_mujoco/g1_pedestrian_capsule_replay_R80000001_static_s1_v8"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace", type=Path, default=DEFAULT_TRACE)
    parser.add_argument("--scene-source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--fps", type=int, default=24)
    parser.add_argument("--speed", type=float, default=0.15)
    args = parser.parse_args()
    trace_path, scene_source, output = args.trace.resolve(), args.scene_source.resolve(), args.output_dir.resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite {output}")
    trace = json.loads(trace_path.read_text())
    if len(trace) != 77 or [int(f["step"]) for f in trace] != list(range(77)):
        raise ValueError("Expected the saved 77-frame safety trace for steps 0..76")
    if list(trace[-1]["position"]) != [17, 9]:
        raise ValueError("Saved safety trace does not end at the admitted goal")
    if any(int(f.get("g1_unwanted_contact_pairs", 0)) for f in trace):
        raise ValueError("Saved safety trace contains unwanted contacts")
    interventions = sum(f.get("emergency_safety_intervention") is not None for f in trace)
    if interventions != 7:
        raise ValueError(f"Expected 7 saved sensor interventions, got {interventions}")

    output.mkdir(parents=True)
    source = output / "replay_source"
    source.mkdir()
    for name in ("scenario.json", "scene.xml"):
        shutil.copyfile(scene_source / name, source / name)
    scenario = json.loads((source / "scenario.json").read_text())
    frames = []
    for frame in trace:
        frames.append({
            "step": int(frame["step"]), "position": frame["position"],
            "planned": [], "moved": bool(frame.get("moved", False)),
            "blocked": bool(frame.get("blocked", False)),
            "heading_yaw": float(frame.get("heading_yaw", 0.0)),
            "heading_changed": False,
            "navigation_action": frame.get("navigation_action"),
            "navigation_action_reason": frame.get("navigation_action_reason"),
            "people": frame.get("g1_pedestrians", []), "active_objects": [],
            "g1_pedestrian_contact_pairs": int(frame.get("g1_pedestrian_contact_pairs", 0)),
            "g1_wall_contact_pairs": 0, "g1_persistent_obstacle_contact_pairs": 0,
        })
    (source / "trajectory.json").write_text(json.dumps(frames, indent=2) + "\n")
    metrics_path = trace_path.parent / "safety_metrics.json"
    metrics = json.loads(metrics_path.read_text())
    (source / "summary.json").write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n")
    source_info = {
        "trajectory_origin": "Direct presentation replay of the saved Emergency Safety Sensor trace; no episode rerun.",
        "source_trace": str(trace_path.relative_to(ROOT)),
        "source_trace_sha256": sha256(trace_path),
        "source_safety_metrics_sha256": sha256(metrics_path),
        "scene_source": str(scene_source.relative_to(ROOT)),
        "scene_sha256": sha256(source / "scene.xml"),
        "source_identity": "phase1.5-v0.4-BPRIME-1:fit:R:80000001",
        "schedule": 1, "observation_policy": "static with Emergency Safety Sensor",
        "seed": 42, "trajectory_frames": len(frames),
        "emergency_safety_scans": metrics["emergency_safety_scans"],
        "emergency_safety_interventions": interventions,
        "goal_reached": metrics["success"], "final_position": metrics["final_position"],
        "unwanted_contact_pairs": metrics["g1_unwanted_contact_pairs"],
        "note": "The saved trace positions, headings, and proxy cells drive this visual replay. Kinematic presentation only; this is not a new experiment or physical walking simulation.",
    }
    (source / "provenance.json").write_text(json.dumps(source_info, indent=2, sort_keys=True) + "\n")
    (output / "replay_validation.json").write_text(json.dumps(source_info, indent=2, sort_keys=True) + "\n")

    exporter_path = ROOT / "scripts/export_phase2_portfolio_demo.py"
    spec = importlib.util.spec_from_file_location("phase2_portfolio_exporter", exporter_path)
    exporter = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(exporter)
    try:
        exporter.render_frames(source, output / "portfolio_export", camera_mode="tracking",
            fps=args.fps, width=1280, height=720, speed=args.speed,
            export_mp4=True, export_gif=True)
        rendered = output / "portfolio_export"
        exporter.encode_mp4(rendered, args.fps)
        exporter.encode_gif(rendered, args.fps)
    except Exception:
        # Leave no ambiguous partial export that could be mistaken for a result.
        shutil.rmtree(output, ignore_errors=True)
        raise
    metadata_path = rendered / "metadata.json"
    metadata = json.loads(metadata_path.read_text())
    metadata.update({
        "source_experiment_episode": {"world_identity": source_info["source_identity"], "schedule_index": 1,
            "observation_policy": source_info["observation_policy"], "seed": 42},
        "source_trace": source_info["source_trace"],
        "source_trace_sha256": source_info["source_trace_sha256"],
        "emergency_safety_interventions": interventions,
        "safety_episode_success": bool(metrics["success"]),
        "safety_episode_unwanted_contact_pairs": int(metrics["g1_unwanted_contact_pairs"]),
        "presentation_note": "Direct replay of the saved Emergency Safety Sensor episode trace; includes recorded waits and lateral avoidance. No experiment was rerun.",
    })
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
    (rendered / "presentation_note.md").write_text(
        "# Emergency Safety Sensor replay (presentation only)\n\n"
        f"- Saved episode: `{source_info['source_identity']}`, schedule 1, seed 42.\n"
        f"- Source trace: `{source_info['source_trace']}` (SHA-256 `{source_info['source_trace_sha256']}`).\n"
        f"- {metrics['emergency_safety_scans']} sensor scans and {interventions} recorded interventions; "
        f"goal reached at {metrics['elapsed_steps']} steps with {metrics['g1_unwanted_contact_pairs']} unwanted contacts.\n"
        "- Recorded positions and proxy cells are replayed as saved. The G1 animation is kinematic display only.\n")
    exporter.write_artifact_manifest(output)
    print(json.dumps({"status": "PASS_SAVED_TRACE_RENDERED", "output": str(output),
        "gif": str(rendered / "portfolio_demo.gif"), "mp4": str(rendered / "portfolio_demo.mp4"),
        "frames": len(frames), "sensor_interventions": interventions}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
