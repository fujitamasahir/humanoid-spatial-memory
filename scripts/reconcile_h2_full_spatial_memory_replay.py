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
    corrected = {}
    corrected_root = OUT / "task_b_b_age_corrected_v2/episodes/b_age"
    if corrected_root.exists():
        journal_path = OUT / "task_b_b_age_corrected_v2/journal.jsonl"
        journal = {e["path"]: e for e in
                   (json.loads(x) for x in journal_path.read_text().splitlines())
                   if e.get("event") == "episode_committed"}
        for path in sorted(corrected_root.rglob("*.json.gz")):
            rel = path.relative_to(OUT).as_posix()
            event = journal.get(rel)
            if event is None or event["sha256"] != sha(path) or event["bytes"] != path.stat().st_size:
                raise RuntimeError(f"Corrected B+Age journal/hash mismatch: {rel}")
            with gzip.open(path, "rt", encoding="utf-8") as f:
                record = json.load(f)
            key = ("b_age", record["map_identity"], int(record["schedule"]))
            result[key] = record
            corrected[key] = rel
        if len(corrected) != 72 or len(journal) != 72:
            raise RuntimeError(f"Expected 72 journaled corrected B+Age cases; files={len(corrected)} journal={len(journal)}")
    return rows, result, corrected


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
    from run_h2_full_spatial_memory_replay import active_binding_path, load_binding

    load_binding()
    correction_binding_sha = sha(active_binding_path())
    index_rows, episodes, corrected_paths = _episode_records()
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
        elif key[0] == "b_age" and key in corrected_paths:
            old_ref = bage_history.get((key[1], key[2]))
            if old_ref is None:
                raise RuntimeError(f"No identity-matched B+Age primary record for {key}")
            current = episodes[key]
            if current["replay"]["replay_recovery"]["source_binding_sha256"] != correction_binding_sha:
                raise RuntimeError(f"Corrected B+Age record binding mismatch: {key}")
            compare_saved(old_ref["record"], current["row"], current["source_trace_for_exact_parity"])
            status = "PASS_EXACT_TRACE_AND_METRIC_SIGNATURE"
            source = json.dumps([{"source": old_ref["path"].relative_to(ROOT).as_posix(),
                                  "sha256": old_ref["sha256"]}], sort_keys=True)
            detail = "Corrected B+Age-only recovery under binding_amendment_5; initial misconfigured records retained but excluded."
        replay_path = corrected_paths.get(key, row["path"])
        replay_sha = sha(OUT / replay_path) if key in corrected_paths else row["sha256"]
        reconciled.append({"model_id": key[0], "map_identity": key[1], "schedule": key[2],
                           "initial_status": row["parity_status"], "status": status,
                           "historical_sources": source, "detail": detail,
                           "replay_path": replay_path, "replay_sha256": replay_sha})

    b_age = []
    corrected_bage_rows = [r for r in reconciled if r["model_id"] == "b_age"]
    if len(corrected_bage_rows) != 72 or len(corrected_paths) != 72:
        raise RuntimeError(f"Expected 72 corrected B+Age cases; found {len(corrected_paths)}")
    for row in corrected_bage_rows:
        key = (row["model_id"], row["map_identity"], int(row["schedule"]))
        current = episodes[key]
        old_ref = bage_history.get((key[1], key[2]))
        if old_ref is None:
            raise RuntimeError(f"No identity-matched B+Age historical record for {key}")
        hist_path, hist_sha, old = old_ref["path"], old_ref["sha256"], old_ref["record"]
        step, _, _, _ = _first_trace_difference(old.get("trace", {}),
                                                 current["source_trace_for_exact_parity"] or {})
        if step is not None:
            raise RuntimeError(f"Corrected B+Age trace still differs from history at {key}: step {step}")
        corrected_path = corrected_paths[key]
        corrected_sha = sha(OUT / corrected_path)
        b_age.append({"model_id": "b_age", "map_identity": row["map_identity"],
            "schedule": row["schedule"], "historical_source": hist_path.relative_to(ROOT).as_posix(),
            "historical_sha256": hist_sha, "recovery_path": corrected_path,
            "recovery_sha256": corrected_sha, "parity_status": row["status"],
            "historical_success": old["row"].get("success"),
            "recovery_success": current["row"].get("success"),
            "historical_steps": old["row"].get("elapsed_steps"),
            "recovery_steps": current["row"].get("elapsed_steps"),
            "historical_observations": old["row"].get("observation_count"),
            "recovery_observations": current["row"].get("observation_count"),
            "superseded_misconfigured_path": original[key]["path"],
            "superseded_misconfigured_sha256": original[key]["sha256"]})

    counts = Counter(x["status"] for x in reconciled)
    if counts != Counter({"PASS_EXACT_TRACE_AND_METRIC_SIGNATURE": 2592,
                          "FIRST_TIME_FIT72_EVALUATION": 1296}):
        raise RuntimeError(f"Unexpected reconciled FIT72 status counts: {counts}")
    with (OUT / "parity_reconciliation.csv").open("x", newline="", encoding="utf-8") as f:
        fields = list(reconciled[0]); w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(reconciled)
    with (OUT / "fit72_b_age_correction_validation.csv").open("x", newline="", encoding="utf-8") as f:
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
                if key in corrected_paths:
                    path = OUT / corrected_paths[key]
                    episode = episodes[key]
                    row_copy.update({"path": corrected_paths[key],
                        "sha256": sha(path), "bytes": path.stat().st_size,
                        "frames": len(episode["replay"]["steps"]),
                        "steps": int(episode["row"]["elapsed_steps"]),
                        "goal_step": episode["row"].get("goal_step"),
                        "paid_observations": episode["row"]["observation_count"],
                        "success": episode["row"]["success"],
                        "distance_m": episode["row"].get("travel_distance_m", episode["row"].get("travel_distance")),
                        "unwanted_contact_pairs": episode["row"].get("g1_unwanted_contact_pairs", 0)})
            writer.writerow(row_copy)
    # Version the union index rather than modifying the first recovery index.
    prior_path = ROOT / "results/phase2_mujoco/h2_comprehensive_benchmark_v1/combined_dataset/replay_index.json"
    prior = json.loads(prior_path.read_text())
    previous_v2_path = OUT / "combined_replay_index/replay_index_v2.json"
    previous_v2 = json.loads(previous_v2_path.read_text())
    with (OUT / "replay_index_reconciled.csv").open(encoding="utf-8", newline="") as f:
        authoritative_rows = list(csv.DictReader(f))
    legacy_count = int(previous_v2["legacy_entry_count"])
    if len(prior["entries"]) != 7776 or previous_v2["entries"][:legacy_count] != prior["entries"]:
        raise RuntimeError("Prior 7,776 replay entries changed")
    updated_additions = []
    for row in previous_v2["entries"][legacy_count:]:
        dataset = "fit72_known" if row["dataset_id"] == "fit72_known_original" else "h2_unseen"
        match = next((x for x in authoritative_rows if x["dataset"] == dataset
                      and x["model_id"] == row["model_id"]
                      and x["map_identity"] == row["world_identity"]
                      and int(x["schedule"]) == int(row["schedule"])), None)
        if match is None:
            raise RuntimeError(f"Missing reconciled replay index row: {row}")
        if dataset == "fit72_known":
            match = next(x for x in authoritative_rows if x["dataset"] == dataset
                         and x["model_id"] == row["model_id"]
                         and x["map_identity"] == row["world_identity"]
                         and int(x["schedule"]) == int(row["schedule"]))
            fixed = reconciliation[(match["model_id"], match["map_identity"], int(match["schedule"]))]
            row.update({"path": match["path"], "sha256": match["sha256"],
                        "historical_reproduction_status": fixed["status"],
                        "source_artifact_reference": match["path"]})
        updated_additions.append(row)
    union_v3 = {"schema_version": "phase2_combined_replay_index_v3",
        "legacy_index_path": prior_path.relative_to(ROOT).as_posix(),
        "legacy_index_sha256": sha(prior_path), "legacy_entry_count": 7776,
        "new_entry_count": len(updated_additions),
        "correction_note": "Supersedes v2 misconfigured B+Age paths with corrected B+Age-only epoch; legacy 7,776 entries preserved exactly.",
        "entries": prior["entries"] + updated_additions}
    (OUT / "combined_replay_index/replay_index_v3.json").write_text(
        json.dumps(union_v3, sort_keys=True, indent=2) + "\n")
    summary = {"status": "COMPLETE_WITH_FIRST_TIME_FIT72_CASES", "task_b_episodes": 3888,
        "task_b_parity": dict(counts), "rdao_v1_identity_matched_exact_records": 72,
        "b_age_corrected_exact_records": 72, "superseded_misconfigured_b_age_records": 72,
        "rdao_source": RDAO.relative_to(ROOT).as_posix(),
        "rdao_source_file_sha256": hashlib.sha256(RDAO.read_bytes()).hexdigest(),
        "bage_historical_commit": "3d66e54fd19c0f5ccc6261ec08eb9dd91efd8fdb",
        "interpretation": "Every comparable historical FIT72 record matches after correction. The 1,296 cases with no prior keyed result remain first-time descriptive evaluations."}
    (OUT / "parity_reconciliation_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    note = """# H2 Replay Recovery Addendum — Parity Reconciliation\n\nThe first Task B pass had two audit defects. Its historical scanner omitted plain `.jsonl` records and admitted generic RDAO method labels as model identity. RDAO v1 was compared directly to its primary records by exact world identity and schedule; all 72 matched.\n\nThe H2 adapter also mistakenly enabled EVI for `b_age`, so the initial 72 records labeled B+Age actually used B+C. Those original files remain byte-for-byte preserved and are excluded from the authoritative index. The adapter was corrected to `persistence=True, evi=False`; 72 B+Age episodes were recorded in the separate `task_b_b_age_corrected_v2` epoch under append-only `binding_amendment_5.json`. All 72 now match the identity-matched FIT72 traces and metric signatures. The first incomplete correction smoke attempt is retained under `task_b_b_age_corrected/` and excluded.\n\n## Authoritative FIT72 reconciliation counts\n\n- Exact historical parity: 2,592 / 3,888\n- First-time FIT72 evaluations with no prior keyed result: 1,296 / 3,888\n- Mismatches: 0 / 3,888\n- Uncomparable: 0 / 3,888\n\nTask A remains 864 / 864 exact. All comparable historical cases reproduce exactly; the 1,296 cases without historical keyed results are labeled descriptive first-time evaluations. See `replay_index_reconciled.csv`, `parity_reconciliation.csv`, and `fit72_b_age_correction_validation.csv`.\n"""
    (OUT / "H2_RECOVERY_ADDENDUM.md").write_text(note)
    summary_path = OUT / "summary.json"
    full_summary = json.loads(summary_path.read_text())
    full_summary["task_b"]["initial_indexer_parity"] = full_summary["task_b"]["parity"]
    full_summary["task_b"]["parity"] = dict(counts)
    full_summary["task_b"]["exact_reproduction_status"] = "ALL_COMPARABLE_HISTORICAL_CASES_EXACT"
    full_summary["parity_reconciliation"] = "parity_reconciliation.csv supersedes initial indexer labels for FIT72 records"
    def record_binding(row):
        with gzip.open(OUT / row["path"], "rt", encoding="utf-8") as f:
            record = json.load(f)
        return record["replay"]["replay_recovery"]["source_binding_sha256"]
    source_bindings = {}
    for dataset, label in (("h2_unseen", "task_a"), ("fit72_known", "task_b_initial")):
        row = next(x for x in index_rows if x["dataset"] == dataset)
        source_bindings[label] = record_binding(row)
    source_bindings["corrected_b_age"] = correction_binding_sha
    binding_paths = {sha(p): p.name for p in [OUT / "binding.json", *sorted(OUT.glob("binding_amendment_*.json"))]}
    full_summary["binding_epochs"] = {name: {"path": binding_paths.get(digest), "sha256": digest}
                                      for name, digest in source_bindings.items()}
    summary_path.write_text(json.dumps(full_summary, sort_keys=True, indent=2) + "\n")
    final_report = OUT / "final_report.md"
    report_text = final_report.read_text()
    marker = "## Parity reconciliation addendum"
    if marker in report_text:
        report_text = report_text.split(marker, 1)[0].rstrip()
    report_text = report_text.replace(
        "- Active source binding: `binding_amendment_3.json` (SHA-256 `3940d8dcbc3721914efca54368bf81c6006e01ce0ae492c78d301e6a72226bb3`).",
        "- Source bindings are epoch-specific; exact paths and SHA-256 values are listed in `summary.json` under `binding_epochs`. The corrected B+Age epoch uses append-only amendment 5.")
    final_report.write_text(report_text + "\n\n" + marker + "\n\n"
        "Task A is exact for 864/864. After identity-matched FIT72 reconciliation, Task B has "
        "2,592 exact historical matches and 1,296 first-time cases. The first Task B pass "
        "misconfigured B+Age as B+C; those 72 source records remain preserved and are superseded "
        "by the separately bound corrected B+Age epoch. Combined index v3 preserves the previous "
        "7,776 entries exactly and points to the 4,752 authoritative recovery records. See "
        "`H2_RECOVERY_ADDENDUM.md`, `game_schema_compatibility.md`, `parity_reconciliation.csv`, "
        "and `fit72_b_age_correction_validation.csv`. The current website reader still requires "
        "its original index schema and is not directly compatible with v3.\n")
    completion_path = OUT / "completion_record.json"
    completion = json.loads(completion_path.read_text())
    completion["reconciliation_sha256"] = sha(OUT / "parity_reconciliation_summary.json")
    completion["exact_reproduction_status"] = "ALL_COMPARABLE_HISTORICAL_CASES_EXACT"
    completion["binding_epochs"] = full_summary["binding_epochs"]
    completion["binding_sha256"] = correction_binding_sha
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
