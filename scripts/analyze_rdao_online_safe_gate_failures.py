"""Forensic analysis of the saved RDAO v1 online route-inertia gate experiment.

Reads previously committed CSVs and JSONL.gz traces only; performs NO MuJoCo
replay, NO observations, NO simulator calls, and NEVER opens held-out worlds.

Reports matched-pair success transitions and runtime/trajectory deltas,
including cases harmed *without* a goal-outcome change, then saves
action/observation timelines and naturally triggered gate events for
representative rescued, harmed, and detoured development worlds.

Both pedestrian schedules are correlated observations of one world;
no statistical independence of the 72 episodes is implied.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[1]
SAVED = ROOT / "results/phase2_mujoco/rdao_v1_online_safe_gate_fit72_screen_v1"
PRIMARY = ROOT / "results/phase2_mujoco/rdao_v1_phase2_evaluation"
DEFAULT_OUTPUT = ROOT / "results/phase2_mujoco/rdao_v1_online_safe_gate_forensics_v1"
DEFAULT_FOCUS = (
    "M:80030009",  # first-only rescue at the horizon
    "M:80030010",  # both-rule rescue
    "M:80030000",  # every-rule loss
    "R:80000022",  # first-only severe detour despite goal completion
    "R:80000018",  # no rescue, despite gate override
)
METRICS = ("elapsed_steps", "observations", "travel_distance_m", "turns")


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def read_gzip_jsonl(path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line_number, line in enumerate(f, 1):
            if line.strip():
                try:
                    yield json.loads(line)
                except (ValueError, TypeError) as exc:
                    raise ValueError(f"Invalid JSONL record {path}:{line_number}") from exc


def sha256(path):
    hash_object = hashlib.sha256()
    with path.open("rb") as f:
        for part in iter(lambda: f.read(1024 * 1024), b""):
            hash_object.update(part)
    return hash_object.hexdigest()


def report_key(row):
    return row["world_identity"], int(row["schedule"]), int(row["seed"]), row["policy"]


def evidence_key(record):
    world, schedule, seed = record["key"]
    return str(world), int(schedule), int(seed), str(record["policy"])


def frozen_trace_key(record):
    world, schedule, method, seed = record["key"]
    if method != "rdao_v1":
        raise ValueError(f"Unexpected frozen reference method: {method}")
    return str(world), int(schedule), int(seed)


def _frame_field(frame, key):
    if frame is None:
        return None
    return frame.get(key)


def _action_pose(frame):
    if frame is None:
        return None
    return (frame.get("action"), frame.get("position"),
            frame.get("heading_yaw"))


def _first_difference(a, b, projection):
    if a is None or b is None:
        return None
    left = {int(f["step"]): f for f in a["steps"]}
    right = {int(f["step"]): f for f in b["steps"]}
    for step in sorted(set(left) | set(right)):
        if projection(left.get(step)) != projection(right.get(step)):
            return step
    return None


def first_action_pose_divergence(a, b):
    return _first_difference(a, b, _action_pose)


def first_sensing_divergence(a, b):
    return _first_difference(a, b, lambda f: _frame_field(f, "observation_granted"))


def outcome_category(row):
    original = row["baseline_success"] == "True"
    updated = row["gated_success"] == "True"
    if updated and not original:
        return "rescued"
    if original and not updated:
        return "harmed"
    return "common_success" if original else "common_failure"


def paired_summary(rows):
    result = {}
    for policy in ("first", "every"):
        data = [r for r in rows if r["policy"] == policy]
        groups = {kind: [r for r in data if outcome_category(r) == kind]
                  for kind in ("rescued", "harmed", "common_success", "common_failure")}
        by_group = {}
        for category, group in groups.items():
            entry = {
                "episodes": len(group),
                "worlds": len({r["world_identity"] for r in group}),
                "world_ids": sorted({r["world_identity"] for r in group})
                if category in ("rescued", "harmed") else None,
            }
            for metric in METRICS:
                diffs = [
                    float(r["gated_" + metric]) - float(r["baseline_" + metric])
                    for r in group
                ]
                entry["total_delta_" + metric] = round(sum(diffs), 8)
                entry["mean_delta_" + metric] = round(sum(diffs) / len(diffs), 8) if diffs else None
                entry["improved_" + metric] = sum(v < -1e-8 for v in diffs)
                entry["unchanged_" + metric] = sum(abs(v) <= 1e-8 for v in diffs)
                entry["worsened_" + metric] = sum(v > 1e-8 for v in diffs)
            by_group[category] = entry
        result[policy] = {
            "episodes": len(data),
            "baseline_successes": sum(r["baseline_success"] == "True" for r in data),
            "gated_successes": sum(r["gated_success"] == "True" for r in data),
            "episodes_with_override": sum(int(r["gate_overrides"]) > 0 for r in data),
            "groups": by_group,
        }
    return result


def write_csv(path, rows, fieldnames):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def pretty(value):
    if value is None:
        return ""
    if isinstance(value, (list, dict, tuple)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--world", action="append", default=None,
                        help="World identity suffix. Repeat to select several.")
    parser.add_argument("--all-changed", action="store_true",
                        help="Include every world with any recorded metric change")
    args = parser.parse_args()
    output = args.output
    if output.exists():
        raise FileExistsError(f"Refusing to replace existing forensic results: {output}")

    source_csv = SAVED / "paired_online_gate.csv"
    source_gz = SAVED / "online_gate_traces.jsonl.gz"
    screen_summary_path = SAVED / "summary.json"
    frozen_csv = PRIMARY / "primary_episodes.csv"
    frozen_gz = PRIMARY / "primary_traces.jsonl.gz"
    input_paths = (source_csv, source_gz, screen_summary_path,
                   frozen_csv, frozen_gz)
    if not all(p.is_file() for p in input_paths):
        raise FileNotFoundError("One or more frozen input artifacts are missing")

    summary = json.loads(screen_summary_path.read_text(encoding="utf-8"))
    expected = summary.get("source_hashes", {})
    for source in (frozen_csv, frozen_gz):
        relative = str(source.relative_to(ROOT))
        if sha256(source) != expected.get(relative):
            raise RuntimeError(f"Protected frozen primary artifact differs: {relative}")
    if summary.get("episodes") != 72 or summary.get("worlds") != 36:
        raise RuntimeError("Online-screen case count differs from original")

    rows = read_csv(source_csv)
    indexed = {report_key(r): r for r in rows}
    if len(rows) != 144 or len(indexed) != 144:
        raise RuntimeError("Expected 144 unique policy/case comparison records")
    schedule_keys = {(k[0], k[1], k[2]) for k in indexed}
    if len(schedule_keys) != 72:
        raise RuntimeError("Expected 72 unique original episode identities")
    if {k[3] for k in indexed} != {"first", "every"}:
        raise RuntimeError("Expected both online policy arms")

    focus_suffixes = tuple(args.world or DEFAULT_FOCUS)
    if args.all_changed:
        chosen = {
            r["world_identity"]
            for r in rows
            if (r["baseline_success"] != r["gated_success"]
                or any(abs(float(r["gated_" + metric]) -
                           float(r["baseline_" + metric])) > 1e-8
                       for metric in METRICS))
        }
    else:
        chosen = {
            r["world_identity"]
            for r in rows if any(r["world_identity"].endswith(suffix)
                                 for suffix in focus_suffixes)
        }
        if len(chosen) != len(set(focus_suffixes)):
            raise ValueError("One or more requested world suffixes did not uniquely match")
    if not chosen:
        raise ValueError("No focus worlds selected")

    trace_index = {}
    for record in read_gzip_jsonl(source_gz):
        k = evidence_key(record)
        if k in trace_index:
            raise RuntimeError(f"Duplicate gated trace: {k}")
        if k in indexed and k[0] in chosen:
            trace_index[k] = record
    expected_focus = {k for k in indexed if k[0] in chosen}
    if set(trace_index) != expected_focus:
        missing = expected_focus - set(trace_index)
        raise RuntimeError(f"Missing committed focus traces: {sorted(missing)[:5]}")
    frozen_index = {}
    for record in read_gzip_jsonl(frozen_gz):
        k = frozen_trace_key(record)
        if k in frozen_index:
            raise RuntimeError(f"Duplicate frozen trace: {k}")
        if k[0] in chosen:
            frozen_index[k] = record
    if {(k[0], k[1], k[2]) for k in expected_focus} != set(frozen_index):
        raise RuntimeError("Missing frozen primary baselines for focus worlds")

    summary_rows = []
    event_rows = []
    timeline_rows = []
    for k in sorted(expected_focus):
        world, schedule, seed, policy = k
        record = trace_index[k]
        original = frozen_index[(world, schedule, seed)]
        trace = record["trace"]
        row = indexed[k]
        event_list = record.get("gate_events", [])
        override_steps = [int(e["step"]) for e in event_list if e.get("override_applied")]
        first_div = first_action_pose_divergence(original, trace)
        first_obs_div = first_sensing_divergence(original, trace)
        other_policy = "every" if policy == "first" else "first"
        other_trace = trace_index[(world, schedule, seed, other_policy)]["trace"]
        comparative_div = first_action_pose_divergence(trace, other_trace)
        if override_steps and first_div is not None and first_div < min(override_steps):
            raise RuntimeError(f"Action/pose diverged before any override: {k}")

        report = {
            "world_identity": world, "schedule": schedule, "seed": seed,
            "policy": policy, "outcome": outcome_category(row),
            "baseline_success": row["baseline_success"],
            "gated_success": row["gated_success"],
            "first_gate_step": override_steps[0] if override_steps else "",
            "gate_override_steps": pretty(override_steps),
            "total_gate_overrides": len(override_steps),
            "first_action_pose_divergence_from_original": first_div or "",
            "first_observation_timing_divergence_from_original": first_obs_div or "",
            "first_action_pose_divergence_from_other_gate_policy": comparative_div or "",
        }
        for m in METRICS:
            report["baseline_" + m] = row["baseline_" + m]
            report["gated_" + m] = row["gated_" + m]
            report["delta_" + m] = round(float(row["gated_" + m]) -
                                         float(row["baseline_" + m]), 5)
        summary_rows.append(report)

        for event in event_list:
            event_rows.append({
                "world_identity": world, "schedule": schedule, "policy": policy,
                "step": int(event["step"]),
                "override_applied": bool(event.get("override_applied")),
                "guard": event.get("guard"),
                "position": pretty(event.get("position")),
                "changed_cells": event.get("changed_cells"),
                "prior_action": pretty(event.get("prior_action")),
                "new_action": pretty(event.get("new_action")),
                "chosen_action": pretty(event.get("chosen_action")),
            })

        original_steps = {int(f["step"]): f for f in original["steps"]}
        gated_steps = {int(f["step"]): f for f in trace["steps"]}
        for step in sorted(set(original_steps) | set(gated_steps)):
            base_frame = original_steps.get(step)
            gate_frame = gated_steps.get(step)
            e = next((event for event in event_list
                      if int(event["step"]) == step and event.get("override_applied")), None)
            timeline_rows.append({
                "world_identity": world, "schedule": schedule,
                "policy": policy, "step": step,
                "base_position": pretty(_frame_field(base_frame, "position")),
                "gated_position": pretty(_frame_field(gate_frame, "position")),
                "base_action": pretty(_frame_field(base_frame, "action")),
                "gated_action": pretty(_frame_field(gate_frame, "action")),
                "base_observed": _frame_field(base_frame, "observation_granted"),
                "gated_observed": _frame_field(gate_frame, "observation_granted"),
                "base_scheduler_reason": (
                    (base_frame.get("rdao") or {}).get("reason") if base_frame else None),
                "gated_scheduler_reason": (
                    (gate_frame.get("rdao") or {}).get("reason") if gate_frame else None),
                "gate_override_at_step": bool(e),
                "gate_prior_action": pretty(e.get("prior_action")) if e else "",
                "gate_replanned_action": pretty(e.get("new_action")) if e else "",
            })

    per_group = paired_summary(rows)
    result_summary = {
        "status": "POSTHOC_FIT_WORLD_ONLINE_GATE_FORENSICS_NOT_HELD_OUT",
        "scope": {"worlds": sorted(chosen), "policies": ["first", "every"],
                  "schedule_count": 2, "source_episodes": 72},
        "paired_aggregate": per_group,
        "input_sha256": {str(p.relative_to(ROOT)): sha256(p) for p in input_paths},
        "notes": [
            "The same world repeated under two schedules is not an independent world.",
            "Failure episodes are censored at 80 steps and cannot be treated as actual arrival times.",
            "A single observed-safe action may still produce a longer or less reliable trajectory.",
            "Per-step action/pose comparison is purely diagnostic; no simulation was rerun.",
            "The gate was designed after inspecting fit-world outcomes. No held-out claims.",
            "Mean observation count differences are partly a function of changed episode lengths.",
        ],
    }

    output.mkdir(parents=True)
    write_csv(output / "focus_episode_comparison.csv", summary_rows,
              list(summary_rows[0]))
    write_csv(output / "focus_gate_events.csv", event_rows,
              ["world_identity", "schedule", "policy", "step", "override_applied",
               "guard", "position", "changed_cells", "prior_action",
               "new_action", "chosen_action"])
    write_csv(output / "focus_action_timeline.csv", timeline_rows,
              list(timeline_rows[0]))
    (output / "summary.json").write_text(
        json.dumps(result_summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    condensed = {
        "output": str(output),
        "worlds_analyzed": len(chosen),
        "first": {
            "rescued": per_group["first"]["groups"]["rescued"]["episodes"],
            "harmed": per_group["first"]["groups"]["harmed"]["episodes"],
            "common_success_worse_steps":
                per_group["first"]["groups"]["common_success"]["worsened_elapsed_steps"],
            "common_success_better_steps":
                per_group["first"]["groups"]["common_success"]["improved_elapsed_steps"],
        },
        "every": {
            "rescued": per_group["every"]["groups"]["rescued"]["episodes"],
            "harmed": per_group["every"]["groups"]["harmed"]["episodes"],
        },
        "focus_overrides": [
            {"world": r["world_identity"].split(":")[-2] + ":" +
                       r["world_identity"].split(":")[-1],
             "schedule": r["schedule"], "policy": r["policy"],
             "outcome": r["outcome"], "step": r["first_gate_step"],
             "override_steps": r["gate_override_steps"],
             "delta_steps": r["delta_elapsed_steps"],
             "delta_distance_m": r["delta_travel_distance_m"]}
            for r in summary_rows if r["schedule"] == 0
        ],
    }
    print(json.dumps(condensed, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
