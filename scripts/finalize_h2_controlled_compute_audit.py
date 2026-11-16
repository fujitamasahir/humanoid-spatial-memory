#!/usr/bin/env python3
"""Read-only integrity audit and final provenance for the completed H2 matrix."""
from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_h2_controlled_compute_benchmark as runner  # noqa: E402

OUT = ROOT / "results/phase2_mujoco/h2_controlled_compute_benchmark_v1"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_exclusive(path: Path, value: dict) -> None:
    if path.exists():
        raise FileExistsError(f"Refusing to replace completed audit artifact: {path}")
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    binding = runner.validate_binding()
    journal_path = OUT / "episode_journal.jsonl"
    records = runner._load_journal(journal_path, lambda row: (
        int(row["repetition"]), int(row["case_index"]), row["model_id"]))
    expected = 54 * 72 * 5
    if len(records) != expected:
        raise RuntimeError(f"Journal count mismatch: {len(records)}/{expected}")
    values = list(records.values())
    models = {row["model_id"] for row in values}
    repetitions = Counter(int(row["repetition"]) for row in values)
    model_case_counts = Counter(row["model_id"] for row in values)
    parity_failures = [row for row in values if not row["parity_match"]]
    expected_b_age = [row for row in parity_failures if row["model_id"] == "b_age" and
                      row["parity_classification"] == "EXPECTED_B_AGE_HISTORICAL_IMPLEMENTATION_NONPARITY"]
    unexpected = [row for row in parity_failures if row not in expected_b_age]
    if len(models) != 54 or repetitions != Counter({i: 3888 for i in range(1, 6)}):
        raise RuntimeError("Model or repetition coverage is incomplete")
    if any(count != 360 for count in model_case_counts.values()):
        raise RuntimeError("Each model must have 72 cases × 5 repetitions")
    if len(expected_b_age) != 360 or unexpected:
        raise RuntimeError(f"Unexpected parity distribution: expected 360 B+Age, got {len(expected_b_age)}; unexpected={len(unexpected)}")

    required_rows = {
        "episode_timings.csv": 19440,
        "parity_validation.csv": 19440,
        "decision_microbenchmark.csv": 162,
        "model_summary.csv": 54,
        "timing_breakdown.csv": 1080,
        "historical_vs_new_comparison.csv": 54,
        "pareto_frontier.csv": 54,
        "break_even_analysis.csv": 54,
        "poster_10_model_costs.csv": 10,
        "case_repetition_variability.csv": 54 * 72 * 4,
        "repeatability_variance_summary.csv": 54 * 4,
    }
    csv_counts = {}
    for name, wanted in required_rows.items():
        with (OUT / name).open(newline="", encoding="utf-8") as stream:
            count = sum(1 for _ in csv.DictReader(stream))
        csv_counts[name] = count
        if count != wanted:
            raise RuntimeError(f"{name}: {count} records, expected {wanted}")

    validation = json.loads((OUT / "validation_status.json").read_text(encoding="utf-8"))
    preservation = validation["post_run_preservation"]
    if validation["status"] != "COMPLETE_WITH_DECLARED_B_AGE_HISTORICAL_NONPARITY" or preservation["status"] != "PASS":
        raise RuntimeError("Prior preservation or semantic validation gate failed")
    if preservation["protected"]["files_checked"] != 836:
        raise RuntimeError("Protected file count does not match the frozen 836-file gate")

    runtime = [json.loads(line) for line in (OUT / "runtime_observations.jsonl").read_text().splitlines()]
    start = next(item for item in runtime if item.get("event") == "run_start")
    finish = next(item for item in runtime if item.get("event") == "run_complete")
    if finish.get("committed") != expected:
        raise RuntimeError("Run completion record is absent or incomplete")

    metrics = {
        "status": "PASS_WITH_DECLARED_HISTORICAL_B_AGE_NONPARITY",
        "episodes": expected,
        "models": len(models),
        "map_schedule_cases_per_model": 72,
        "repetitions_per_case": 5,
        "records_per_repetition": dict(sorted(repetitions.items())),
        "exact_semantic_parity_records": expected - len(expected_b_age),
        "expected_historical_b_age_nonparity_records": len(expected_b_age),
        "unexpected_semantic_parity_failures": 0,
        "csv_record_counts": csv_counts,
        "protected_file_gate": preservation["protected"],
        "preservation_status": preservation["status"],
        "checkpoint_receipt_pairs": preservation["checkpoint_receipt_pairs"],
        "run_elapsed_seconds": finish["elapsed_seconds"],
        "runtime_resource_snapshot_count": len(runtime),
        "external_resource_snapshot_count": sum(1 for _ in (OUT / "runtime_observations_external.jsonl").open()),
        "process_and_thermal_telemetry_limit": "macOS denied ps/top enumeration; temperature/thermal pressure not directly available; load averages and vm_stat snapshots are recorded",
        "source_binding_sha256": sha(runner.active_binding_path()),
        "binding_source_commit": binding["source_commit"],
        "audit_script_sha256": sha(Path(__file__)),
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    write_exclusive(OUT / "postrun_verification.json", metrics)

    note = OUT / "postrun_analysis_note.md"
    if note.exists():
        raise FileExistsError(f"Refusing to replace {note}")
    note.write_text(
        "# Post-run verification note\n\n"
        "The completed measurement run was inspected before analysis. Its journal, timing CSV, and parity CSV remained unchanged during post-run analysis.\n\n"
        "The first analysis attempt exposed a historical-summary path bug: the runner's `HISTORICAL[0]` resolves to `h2_final_generalization_v1`, but the timing summary required for historical comparisons is stored under `h2_comprehensive_benchmark_v1/analysis/high_frequency_environment_summary.csv`. "
        "The analysis-only wrapper sets that correct path in memory; it does not change the bound runner, model source, timing protocol, or any measured records.\n\n"
        "The legacy `verify` subcommand prints the correct completion status `COMPLETE_WITH_DECLARED_B_AGE_HISTORICAL_NONPARITY` but exits with code 1 because it accepts only the literal status `PASS`. "
        "`postrun_verification.json` is the independent zero-exit audit: it validates all journal hashes, dimensions, record coverage, the declared 360 B+Age historical mismatches, the zero unexpected mismatches, all CSV row counts, and the frozen 836-file preservation gate.\n",
        encoding="utf-8")

    excluded = {"artifact_manifest_final.json"}
    file_hashes = {}
    for path in sorted(OUT.rglob("*")):
        if path.is_file() and path.name not in excluded:
            file_hashes[str(path.relative_to(OUT))] = sha(path)
    write_exclusive(OUT / "artifact_manifest_final.json", {
        "status": metrics["status"],
        "files_sha256": file_hashes,
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "source_binding_sha256": metrics["source_binding_sha256"],
        "audit_script_sha256": metrics["audit_script_sha256"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    })
    print(json.dumps(metrics, indent=2), flush=True)


if __name__ == "__main__":
    main()
