"""Read-only forensic comparison of original vs footprint RDAO online trajectories.

The original and candidate 72-episode gzipped trajectories are ALREADY
committed. This reads them without MuJoCo, replay or intervention. Only
decision-time fields from naturally saved traces are compared; no world
oracle or future observations are provided to the agent.

It distinguishes:
 (i) first authorized observation-timing change,
 (ii) first action/pose change,
 (iii) downstream contact/emergency/turn outcomes,
 (iv) real successes versus horizon80-censored failures.
The feature change was selected posthoc on FIT worlds; a trace-level
diagnosis does NOT establish future generalization.

Run on a fresh, empty output directory. Existing files are never overwritten.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "results/phase2_mujoco/rdao_v1_phase2_evaluation"
VARIANT = ROOT / "results/phase2_mujoco/rdao_v1_footprint_visibility_online_fit72_v1"
VIS = ROOT / "results/phase2_mujoco/rdao_v1_visibility_extent_audit_v1"
DEFAULT_OUTPUT = ROOT / "results/phase2_mujoco/rdao_v1_footprint_visibility_online_forensics_v1"
PREFIX = "phase1.5-v0.4-BPRIME-1:fit:"
TARGETS = (
    ("R:80000017", 0),    # rescued, fewer observations, shorter path
    ("M:80030007", 1),    # rescued, emergency intervention changes
    ("R:80000022", 0),    # large deterioration
    ("R:80000022", 1),
    ("BP:80010001", 0),   # step/distance increase
    ("BP:80010004", 0),
    ("BP:80010013", 0),   # faster existing success
    ("M:80030009", 0),   # failed with additional observations
    ("M:80030009", 1),
)


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_csv(path: Path):
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def read_traces(path: Path, *, variant: bool):
    index = {}
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            record = json.loads(line)
            if variant:
                world, schedule, seed = record["key"]
                trace = record["trace"]
                if record["variant"] != "rdao_v1_footprint_visibility":
                    raise ValueError("Unexpected new candidate name")
            else:
                world, schedule, method, seed = record["key"]
                trace = record
                if method != "rdao_v1":
                    raise ValueError("Unexpected frozen primary method")
            key = (world, int(schedule), int(seed))
            if key in index:
                raise ValueError(f"Duplicate trajectory {key}")
            index[key] = trace
    if len(index) != 72:
        raise RuntimeError(f"Expected 72 original/candidate episodes in {path}")
    return index


def first_differences(left, right):
    """Return first sensing and first executed-action/pose divergence."""
    a = {int(f["step"]): f for f in left["steps"]}
    b = {int(f["step"]): f for f in right["steps"]}
    first_sensing = first_motion = None
    for step in sorted(set(a) | set(b)):
        f, g = a.get(step), b.get(step)
        if f is None or g is None:
            first_sensing = step if first_sensing is None else first_sensing
            first_motion = step if first_motion is None else first_motion
            break
        if (first_sensing is None
                and bool(f["observation_granted"]) !=
                bool(g["observation_granted"])):
            first_sensing = step
        if (first_motion is None and any(f.get(k) != g.get(k) for k in
                ("position", "heading_yaw", "action", "moved", "blocked"))):
            first_motion = step
    return first_sensing, first_motion


def category(row):
    before, after = row["original_success"] == "True", row["variant_success"] == "True"
    if before and after:
        delta = int(row["delta_steps"])
        return "common_success_better" if delta < 0 else (
            "common_success_worse" if delta > 0 else "common_success_same_steps")
    if before:
        return "harmed"
    if after:
        return "rescued"
    return "both_horizon_censored_failures"


def safe_json(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True)


def frame_features(frame):
    if frame is None:
        return dict(exists=False)
    diag = frame.get("rdao") or {}
    effect = diag.get("observation_effect") or {}
    return {
        "exists": True,
        "step": int(frame["step"]),
        "position": safe_json(frame.get("position")),
        "heading_yaw": frame.get("heading_yaw"),
        "action": safe_json(frame.get("action")),
        "observation_granted": bool(frame.get("observation_granted")),
        "observation_count": int(frame.get("observation_count", 0)),
        "observation_reason": diag.get("reason"),
        "decision_score": diag.get("score"),
        "decision_threshold": diag.get("threshold"),
        "selected_candidate_regions": len(diag.get("candidate_regions") or []),
        "nominal_route_first_action": safe_json(
            (diag.get("nominal_route") or [None])[0]),
        "observed_memory_changed_cells": effect.get("memory_changed_cell_count"),
        "new_route_first_action": safe_json(
            (effect.get("route_after") or [None])[0]),
        "emergency_intervention": safe_json(
            frame.get("emergency_intervention")),
        "contact_events": bool(frame.get("contact_event")),
    }


def check_case(source, candidate, row):
    old_steps, new_steps = source["steps"], candidate["steps"]
    if (int(old_steps[0]["step"]) != 0
            or int(new_steps[0]["step"]) != 0
            or int(old_steps[-1]["step"]) != int(row["original_elapsed_steps"])
            or int(new_steps[-1]["step"]) != int(row["variant_elapsed_steps"])):
        raise RuntimeError("Saved elapsed-step count inconsistent with traces")
    for arm, frames in (("original", old_steps), ("variant", new_steps)):
        actual = sum(bool(f["observation_granted"]) for f in frames)
        if actual != int(row[f"{arm}_observations"]):
            raise RuntimeError(f"Saved {arm} observation count differs from frames")
    sensing, motion = first_differences(source, candidate)
    logged_sensing = (int(row["first_changed_observation_step"])
                      if row["first_changed_observation_step"] else None)
    logged_motion = (int(row["first_changed_action_or_pose_step"])
                     if row["first_changed_action_or_pose_step"] else None)
    if sensing != logged_sensing or motion != logged_motion:
        raise RuntimeError("Forensic first divergence inconsistent with online screen")
    if motion is not None and (sensing is None or motion < sensing):
        raise RuntimeError("Action changed before visibility changed sensing")
    a = {int(f["step"]): f for f in old_steps}
    b = {int(f["step"]): f for f in new_steps}
    for step in range(sensing or min(len(old_steps), len(new_steps))):
        if step not in a or step not in b:
            break
        for k in ("position", "heading_yaw", "action",
                  "observation_granted", "observation_count"):
            if a[step].get(k) != b[step].get(k):
                raise RuntimeError("Unexpected prefix divergence before first observation")
    return sensing, motion


def write_csv(path, rows):
    if not rows:
        return
    with path.open("x", encoding="utf-8", newline="") as stream:
        w = csv.DictWriter(stream, fieldnames=list(rows[0]),
                           lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def build_timeline(world, schedule, row, original, candidate,
                   *, before=3, after=14):
    sense, action = first_differences(original, candidate)
    if sense is None:
        return []
    a = {int(f["step"]): f for f in original["steps"]}
    b = {int(f["step"]): f for f in candidate["steps"]}
    start = max(0, sense - before)
    stop = min(80, max(sense, action or sense) + after)
    timeline = []
    for step in range(start, stop + 1):
        af = frame_features(a.get(step))
        bf = frame_features(b.get(step))
        item = {
            "world_identity": world, "schedule": schedule,
            "paired_category": category(row),
            "step": step,
            "first_observation_change": step == sense,
            "first_action_change": action is not None and step == action,
        }
        item.update({f"original_{k}": value for k, value in af.items()})
        item.update({f"footprint_{k}": value for k, value in bf.items()})
        timeline.append(item)
    return timeline


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing overwrite: {args.output}")

    source_paths = [
        BASE / "primary_traces.jsonl.gz",
        VARIANT / "visibility_online_traces.jsonl.gz",
        VARIANT / "paired_visibility_online.csv",
        VIS / "summary.json",
    ]
    fingerprints = {str(p.relative_to(ROOT)): sha(p) for p in source_paths}
    sensor_report = json.loads((VIS / "summary.json").read_text(encoding="utf-8"))
    if fingerprints[str((BASE / "primary_traces.jsonl.gz").relative_to(ROOT))] != (
        sensor_report["source_sha256"][
            "results/phase2_mujoco/rdao_v1_phase2_evaluation/primary_traces.jsonl.gz"]
    ):
        raise RuntimeError("Frozen primary trajectory hash changed")
    original = read_traces(BASE / "primary_traces.jsonl.gz", variant=False)
    updated = read_traces(VARIANT / "visibility_online_traces.jsonl.gz",
                          variant=True)
    rows = read_csv(VARIANT / "paired_visibility_online.csv")
    if len(rows) != 72:
        raise RuntimeError("Expected 72 saved paired cases")
    pair = {}
    for row in rows:
        key = (row["world_identity"], int(row["schedule"]), int(row["seed"]))
        if key in pair:
            raise RuntimeError("Duplicate paired CSV row")
        pair[key] = row
    if set(pair) != set(original) or set(pair) != set(updated):
        raise RuntimeError("Candidate and frozen row/trace episode identities differ")

    focus = { (PREFIX + world, schedule) for world, schedule in TARGETS }
    summary_rows, timelines = [], []
    for key in sorted(pair):
        world, schedule, seed = key
        row = pair[key]
        sensing, motion = check_case(original[key], updated[key], row)
        summary_rows.append({
            "world_identity": world, "schedule": schedule, "seed": seed,
            "category": category(row),
            "original_success": row["original_success"],
            "footprint_success": row["variant_success"],
            "delta_censored_steps": int(row["delta_steps"]),
            "delta_distance_m": float(row["delta_distance_m"]),
            "delta_observations": int(row["delta_observations"]),
            "delta_emergency_interventions": (
                int(row["variant_emergency_interventions"]) -
                int(row["original_emergency_interventions"])),
            "delta_turns": int(row["variant_turns"])-int(row["original_turns"]),
            "first_observation_divergence_step": sensing,
            "first_executed_action_divergence_step": motion,
            "lag_between_sensing_and_action_change": (
                motion - sensing if motion is not None and sensing is not None
                else None),
            "original_observation_steps": safe_json(
                [int(f["step"]) for f in original[key]["steps"]
                 if f["observation_granted"]]),
            "footprint_observation_steps": safe_json(
                [int(f["step"]) for f in updated[key]["steps"]
                 if f["observation_granted"]]),
        })
        if (world, schedule) in focus:
            timelines.extend(build_timeline(
                world, schedule, row, original[key], updated[key]))
    categories = Counter(row["category"] for row in summary_rows)
    expected_categories = {
        "rescued": 2, "harmed": 0,
        "common_success_better": 8, "common_success_same_steps": 42,
        "common_success_worse": 7,
        "both_horizon_censored_failures": 13,
    }
    if {k: categories.get(k, 0) for k in expected_categories} != expected_categories:
        raise RuntimeError(f"Unreproduced paired categories: {categories}")
    if sum(row["delta_censored_steps"] for row in summary_rows) != 6:
        raise RuntimeError("Unexpected horizon-censored step totals")
    if abs(sum(row["delta_distance_m"] for row in summary_rows) - 42.0) > 1e-8:
        raise RuntimeError("Unexpected distance totals")
    if sum(row["delta_observations"] for row in summary_rows) != 59:
        raise RuntimeError("Unexpected observation totals")
    if {str(p.relative_to(ROOT)): sha(p) for p in source_paths} != fingerprints:
        raise RuntimeError("Input changed during audit")
    if not timelines:
        raise RuntimeError("Focus first-divergence data missing")
    args.output.mkdir(parents=True)
    write_csv(args.output / "paired_case_diagnostics.csv", summary_rows)
    write_csv(args.output / "focus_step_timeline.csv", timelines)
    summary = {
        "status": "READ_ONLY_FIT_EPISODE_TRACE_DIAGNOSIS_NOT_NEW_INTERVENTIONS",
        "worlds": len({row["world_identity"] for row in summary_rows}),
        "episodes": len(summary_rows),
        "paired_categories": dict(categories),
        "first_changed_observation_timing": sum(
            row["first_observation_divergence_step"] is not None
            for row in summary_rows),
        "first_changed_executed_action": sum(
            row["first_executed_action_divergence_step"] is not None
            for row in summary_rows),
        "focus_world_schedule_pairs": sorted(
            [dict(world=world, schedule=schedule) for world, schedule in focus],
            key=lambda d: (d["world"], d["schedule"])),
        "source_hashes": fingerprints,
        "total_delta_steps_horizon_censored": 6,
        "total_delta_distance_m": 42.0,
        "total_delta_observations": 59,
        "limitations": [
            "No further MuJoCo simulation or intervention was run.",
            "An observed trajectory divergence after changed sensing may have many downstream causes.",
            "The goal outcome and emergency intervention counts are posthoc labels, not online model inputs.",
            "The two pedestrian schedules per world are correlated; 72 cases do not equal 72 independent mazes.",
            "Original failure at horizon80 is a censored event, not a measured completion time.",
            "All 36 worlds are fitted development worlds, not held-out evaluation.",
            "A visibility model can produce more detections without reducing observations or route cost.",
        ],
    }
    (args.output / "summary.json").write_text(
        json.dumps(summary, sort_keys=True, indent=2, allow_nan=False)+"\n",
        encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "categories": dict(categories),
        "focus_timelines": len(timelines),
        "high_interest": [
            {key: row[key] for key in (
                "world_identity", "schedule", "category",
                "delta_censored_steps", "delta_distance_m",
                "delta_observations", "delta_emergency_interventions",
                "first_observation_divergence_step",
                "first_executed_action_divergence_step")}
            for row in summary_rows if
            (row["world_identity"], row["schedule"]) in focus
        ],
    }, indent=2, allow_nan=False))


if __name__ == "__main__":
    run()
