#!/usr/bin/env python3
"""Reconcile H2 FIT72 replay parity against identity-matched source records.

This is an audit-only pass. It reads completed recovery records and historical
FIT72 evidence, does not rerun an episode, and never edits replay payloads.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/phase2_mujoco/h2_full_spatial_memory_replay_v1"
RDAO = ROOT / "results/phase2_mujoco/rdao_v1_phase2_evaluation/primary_records.jsonl"
BAGE = ROOT / "results/phase2_mujoco/persistence_evi_fit72_restored_local_v1"


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def _episode_records():
    with (OUT / "replay_index.csv").open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    result = {}
    for row in rows:
        if row["dataset"] == "fit72_known" and row["model_id"] in ("rdao_v1", "b_age"):
            key = (row["model_id"], row["map_identity"], int(row["schedule"]))
            with gzip.open(OUT / row["path"], "rt", encoding="utf-8") as f:
                result[key] = json.load(f)
    return rows, result


def _rdao_primary():
    records = {}
    with RDAO.open("rb") as f:
        for line_number, raw in enumerate(f, 1):
            record = json.loads(raw)
            key = (record["world_identity"], int(record["schedule"]))
            if key in records:
                raise ValueError(f"Duplicate RDAO v1 primary record: {key}")
            records[key] = {"record": record, "line": line_number,
                            "sha256": sha_bytes(raw)}
    return records


def _bage_history():
    records = {}
    for path in sorted(BAGE.glob("episode_*_b_age.json.gz")):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            record = json.load(f)
        row = record["row"]
        key = (row["world_identity"], int(row["schedule"]))
        if key in records:
            raise ValueError(f"Duplicate B+Age historical record: {key}")
        records[key] = {"record": record, "path": path,
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    return records


def _first_trace_difference(old, new):
    old_steps, new_steps = old.get("steps", []), new.get("steps", [])
    fields = ("step", "position", "heading_yaw", "action", "moved", "blocked",
              "contacts", "observation_granted", "observation_count",
              "emergency_intervention")
    for i in range(max(len(old_steps), len(new_steps))):
        if i >= len(old_steps) or i >= len(new_steps):
            return i, "frame_count", old_steps[i] if i < len(old_steps) else None, new_steps[i] if i < len(new_steps) else None
        a, b = old_steps[i], new_steps[i]
        changed = [name for name in fields if a.get(name) != b.get(name)]
        if changed:
            return i, ",".join(changed), a, b
    return None, "", None, None


def reconcile():
    from run_h2_final import compare_saved

    index_rows, episodes = _episode_records()
    history = _rdao_primary()
    bage_history = _bage_history()
    if len(history) != 72:
        raise RuntimeError(f"Expected 72 RDAO v1 primary records; found {len(history)}")
    original = {}
    for row in index_rows:
        if row["dataset"] == "fit72_known":
            key = (row["model_id"], row["map_identity"], int(row["schedule"]))
            original[key] = row

    reconciled = []
    for key, row in sorted(original.items()):
        status = row["parity_status"]
        source = row["historical_records"]
        detail = row["parity_detail"] or ""
        if key[0] == "rdao_v1":
            old_ref = history.get((key[1], key[2]))
            if old_ref is None:
                raise RuntimeError(f"No identity-matched RDAO v1 primary record for {key}")
            current = episodes[key]
            compare_saved(old_ref["record"], current["row"],
                          current["source_trace_for_exact_parity"])
            status = "PASS_EXACT_TRACE_AND_METRIC_SIGNATURE"
            source = json.dumps([{"source": "results/phase2_mujoco/rdao_v1_phase2_evaluation/primary_records.jsonl",
                                  "line": old_ref["line"], "sha256": old_ref["sha256"]}], sort_keys=True)
            detail = "Direct comparison to identity-matched RDAO v1 primary record; alternate variants excluded."
        reconciled.append({"model_id": key[0], "map_identity": key[1], "schedule": key[2],
                           "initial_status": row["parity_status"], "status": status,
                           "historical_sources": source, "detail": detail,
                           "replay_path": row["path"], "replay_sha256": row["sha256"]})

    b_age = []
    mismatches = [r for r in reconciled if r["model_id"] == "b_age"]
    if len(mismatches) != 72:
        raise RuntimeError(f"Expected 72 B+Age cases; found {len(mismatches)}")
    for row in mismatches:
        key = (row["model_id"], row["map_identity"], int(row["schedule"]))
        current = episodes[key]
        old_ref = bage_history.get((key[1], key[2]))
        if old_ref is None:
            raise RuntimeError(f"No identity-matched B+Age historical record for {key}")
        hist_path, hist_sha, old = old_ref["path"], old_ref["sha256"], old_ref["record"]
        step, fields, before, after = _first_trace_difference(
            old.get("trace", {}), current["source_trace_for_exact_parity"] or {})
        if step is None:
            raise RuntimeError(f"Metric mismatch without a trace difference: {key}")
        b_age.append({"model_id": "b_age", "map_identity": row["map_identity"],
            "schedule": row["schedule"], "historical_source": hist_path.relative_to(ROOT).as_posix(),
            "historical_sha256": hist_sha, "recovery_source": row["replay_path"],
            "recovery_sha256": row["replay_sha256"], "first_divergent_step": step,
            "first_divergent_fields": fields,
            "historical_position": json.dumps(before.get("position") if before else None),
            "recovery_position": json.dumps(after.get("position") if after else None),
            "historical_heading": before.get("heading_yaw") if before else None,
            "recovery_heading": after.get("heading_yaw") if after else None,
            "historical_action": json.dumps(before.get("action") if before else None),
            "recovery_action": json.dumps(after.get("action") if after else None),
            "historical_observation_granted": before.get("observation_granted") if before else None,
            "recovery_observation_granted": after.get("observation_granted") if after else None,
            "historical_success": old["row"].get("success"),
            "recovery_success": current["row"].get("success"),
            "historical_steps": old["row"].get("elapsed_steps"),
            "recovery_steps": current["row"].get("elapsed_steps"),
            "historical_observations": old["row"].get("observation_count"),
            "recovery_observations": current["row"].get("observation_count")})

    counts = Counter(x["status"] for x in reconciled)
    if counts != Counter({"PASS_EXACT_TRACE_AND_METRIC_SIGNATURE": 2520,
                          "FIRST_TIME_FIT72_EVALUATION": 1296,
                          "MISMATCH": 72}):
        raise RuntimeError(f"Unexpected reconciled FIT72 status counts: {counts}")
    with (OUT / "parity_reconciliation.csv").open("x", newline="", encoding="utf-8") as f:
        fields = list(reconciled[0]); w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(reconciled)
    with (OUT / "fit72_b_age_mismatch_analysis.csv").open("x", newline="", encoding="utf-8") as f:
        fields = list(b_age[0]); w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(b_age)
    reconciliation = {(r["model_id"], r["map_identity"], int(r["schedule"])): r
                      for r in reconciled}
    with (OUT / "replay_index.csv").open(encoding="utf-8", newline="") as f:
        all_index_rows = list(csv.DictReader(f))
    replay_fields = list(all_index_rows[0])
    with (OUT / "replay_index_reconciled.csv").open("x", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=replay_fields); writer.writeheader()
        for item in all_index_rows:
            row_copy = dict(item)
            if row_copy["dataset"] == "fit72_known":
                key = (row_copy["model_id"], row_copy["map_identity"], int(row_copy["schedule"]))
                fixed = reconciliation[key]
                row_copy["parity_status"] = fixed["status"]
                row_copy["parity_detail"] = fixed["detail"]
                row_copy["historical_records"] = fixed["historical_sources"]
            writer.writerow(row_copy)
    summary = {"status": "RECONCILED_WITH_MISMATCHES", "task_b_episodes": 3888,
        "task_b_parity": dict(counts), "rdao_v1_identity_matched_exact_records": 72,
        "b_age_actual_trace_and_metric_mismatches": 72,
        "first_divergence_step_counts": dict(sorted(Counter(str(r["first_divergent_step"]) for r in b_age).items())),
        "rdao_source": RDAO.relative_to(ROOT).as_posix(),
        "rdao_source_file_sha256": hashlib.sha256(RDAO.read_bytes()).hexdigest(),
        "bage_historical_commit": "3d66e54fd19c0f5ccc6261ec08eb9dd91efd8fdb",
        "interpretation": "RDAO v1 now compares against the exact identity-matched primary records. B+Age remains non-identical and is reported as such; this recovery used the active H2 binding, not a silent historical-code substitution."}
    (OUT / "parity_reconciliation_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    note = """# H2 Replay Recovery Addendum — Parity Reconciliation\n\nThe original Task B indexer did not include plain `.jsonl` historical records and also admitted generic RDAO method labels as model identity. A read-only reconciliation pass compared all 72 RDAO v1 episodes directly with `rdao_v1_phase2_evaluation/primary_records.jsonl`, keyed by exact world identity and schedule; all 72 matched both step traces and metric signatures. Alternative RDAO variants were excluded. The raw replay episodes and the initial parity fields inside them remain unchanged.\n\nThe 72 B+Age FIT72 replays remain genuine mismatches against the saved `persistence_evi_fit72_restored_local_v1` episodes. The saved FIT72 provenance pins commit `3d66e54`; this recovery used the active H2 recovery binding. The mismatch is not called a successful reproduction. `fit72_b_age_mismatch_analysis.csv` reports first divergent step, actions, poses, observations, outcomes, and both source hashes. In the first inspected episode, divergence begins at step 4: the historical run turns while the recovery run selects a forward move that the current footprint/safety path rejects. This is a diagnosed source/behavior discrepancy, not evidence that every mismatch has the same cause.\n\n## Current FIT72 reconciliation counts\n\n- Exact historical parity: 2,520 / 3,888\n- First-time FIT72 evaluations: 1,296 / 3,888\n- Actual mismatch: 72 / 3,888 (all B+Age)\n- Uncomparable: 0 / 3,888\n\nTask A remains 864 / 864 exact. The combined archive remains descriptive; this report does not claim complete exact reproduction for Task B.\n"""
    (OUT / "H2_RECOVERY_ADDENDUM.md").write_text(note)
    summary_path = OUT / "summary.json"
    full_summary = json.loads(summary_path.read_text())
    full_summary["task_b"]["initial_indexer_parity"] = full_summary["task_b"]["parity"]
    full_summary["task_b"]["parity"] = dict(counts)
    full_summary["task_b"]["exact_reproduction_status"] = "PARTIAL_WITH_72_B_AGE_MISMATCHES"
    full_summary["parity_reconciliation"] = "parity_reconciliation.csv supersedes initial indexer labels for FIT72 records"
    summary_path.write_text(json.dumps(full_summary, sort_keys=True, indent=2) + "\n")
    final_report = OUT / "final_report.md"
    report_text = final_report.read_text()
    marker = "## Parity reconciliation addendum"
    if marker not in report_text:
        final_report.write_text(report_text + "\n" + marker + "\n\n"
            "Task A is exact for 864/864. After identity-matched FIT72 reconciliation, Task B has "
            "2,520 exact historical matches, 1,296 first-time cases, and 72 B+Age mismatches. "
            "See `H2_RECOVERY_ADDENDUM.md`, `parity_reconciliation.csv`, and "
            "`fit72_b_age_mismatch_analysis.csv`. The archive is complete; Task B is not a fully "
            "exact reproduction.\n")
    completion_path = OUT / "completion_record.json"
    completion = json.loads(completion_path.read_text())
    completion["reconciliation_sha256"] = sha(OUT / "parity_reconciliation_summary.json")
    completion["exact_reproduction_status"] = "PARTIAL_WITH_72_B_AGE_MISMATCHES"
    completion["summary_sha256"] = sha(summary_path)
    completion_path.write_text(json.dumps(completion, sort_keys=True, indent=2) + "\n")
    manifest_entries = []
    for path in sorted(OUT.rglob("*")):
        if path.is_file() and path.name != "artifact_manifest.json":
            manifest_entries.append({"path": path.relative_to(OUT).as_posix(),
                                     "bytes": path.stat().st_size, "sha256": sha_bytes(path.read_bytes())})
    (OUT / "artifact_manifest.json").write_text(json.dumps({
        "schema": "h2_full_spatial_memory_replay_manifest_v1", "files": manifest_entries
    }, sort_keys=True, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    reconcile()
