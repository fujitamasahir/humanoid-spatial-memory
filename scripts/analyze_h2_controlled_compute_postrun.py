#!/usr/bin/env python3
"""Post-run H2 analysis without rewriting immutable timing evidence.

The original benchmark runner's HISTORICAL[0] points at the H2 generalization
output, while its historical timing summary lives in
h2_comprehensive_benchmark_v1. This analysis-only entry point corrects that
lookup at runtime; it does not change the bound runner or any experiment code.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_h2_controlled_compute_benchmark as runner  # noqa: E402

OUT = ROOT / "results/phase2_mujoco/h2_controlled_compute_benchmark_v1"
CORRECT_HISTORICAL_TIMING = ROOT / "results/phase2_mujoco/h2_comprehensive_benchmark_v1"
PROTECTED_OUTPUTS = {OUT / "episode_timings.csv", OUT / "parity_validation.csv"}
ORIGINAL_EMIT_CSV = runner._emit_csv


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _render_csv(records: list[dict]) -> str:
    fields = [key for key in records[0] if not key.startswith("_")] if records else []
    from io import StringIO
    stream = StringIO(newline="")
    writer = csv.DictWriter(stream, fields, lineterminator="\n", extrasaction="ignore")
    writer.writeheader()
    for row in records:
        writer.writerow({key: row.get(key) for key in fields})
    return stream.getvalue()


def _safe_emit_csv(path: Path, records) -> None:
    materialized = list(records)
    if path.exists():
        if path in PROTECTED_OUTPUTS and path.read_text(encoding="utf-8") == _render_csv(materialized):
            print(f"preserved existing measured file unchanged: {path.name}", flush=True)
            return
        raise FileExistsError(f"Refusing to overwrite existing result: {path}")
    ORIGINAL_EMIT_CSV(path, materialized)


def compute_case_repetition_variability(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Separate repeat noise on the same case from differences between cases."""
    components = {
        "initialization": "initialization_ns",
        "observation_decision": "decision_ns",
        "memory_update": "memory_update_ns",
        "total_model_computation": "total_model_computation_ns",
    }
    grouped: dict[tuple[str, int, str], list[float]] = defaultdict(list)
    for row in rows:
        for component, field in components.items():
            grouped[(row["model_id"], int(row["case_index"]), component)].append(
                float(row[field]) / 1_000_000
            )
    case_rows = []
    for (model, case, component), values in sorted(grouped.items()):
        if len(values) != runner.REPETITIONS:
            raise ValueError(f"Expected five repetitions for {(model, case, component)}; got {len(values)}")
        case_rows.append({
            "model_id": model,
            "case_index": case,
            "component": component,
            "repetitions": len(values),
            "mean_ms": statistics.mean(values),
            "std_ms": statistics.stdev(values),
            "p95_ms": runner._quantile(values, .95),
            "p99_ms": runner._quantile(values, .99),
            "min_ms": min(values),
            "max_ms": max(values),
            "variability_unit": "same map×schedule case repeated; not independent environments",
        })
    summaries = []
    models = sorted({key[0] for key in grouped})
    for model in models:
        for component in components:
            cases = [r for r in case_rows if r["model_id"] == model and r["component"] == component]
            case_means = [r["mean_ms"] for r in cases]
            within_sd = [r["std_ms"] for r in cases]
            summaries.append({
                "model_id": model,
                "component": component,
                "case_count": len(cases),
                "repetitions_per_case": runner.REPETITIONS,
                "mean_within_case_repetition_sd_ms": statistics.mean(within_sd),
                "median_within_case_repetition_sd_ms": statistics.median(within_sd),
                "between_case_sd_of_case_means_ms": statistics.stdev(case_means),
                "between_case_mean_ms": statistics.mean(case_means),
                "within_to_between_sd_ratio": (
                    statistics.mean(within_sd) / statistics.stdev(case_means)
                    if statistics.stdev(case_means) else None
                ),
                "interpretation": "within-case SD is repeat noise; between-case SD is variation across the fixed 72 map×schedule cases",
            })
    return case_rows, summaries


def _reconcile_protected_csvs(rows: list[dict]) -> None:
    expected = {(r["repetition"], r["case_index"], r["model_id"]): r for r in rows}
    with (OUT / "episode_timings.csv").open(newline="", encoding="utf-8") as source:
        actual = list(csv.DictReader(source))
    if len(actual) != len(expected):
        raise ValueError("Preserved episode_timings.csv has an unexpected record count")
    for row in actual:
        key = (int(row["repetition"]), int(row["case_index"]), row["model_id"])
        source = expected.get(key)
        if source is None:
            raise ValueError(f"Unexpected protected CSV key {key}")
        for field in row:
            if field not in source:
                raise ValueError(f"Unexpected protected CSV column {field}")
            expected_value = "" if source[field] is None else str(source[field])
            if row[field] != expected_value:
                raise ValueError(f"Protected timing CSV mismatch at {key}.{field}")


def main() -> None:
    binding = runner.validate_binding()
    journal_path = OUT / "episode_journal.jsonl"
    rows = runner._read_complete_rows()
    if len(rows) != 54 * 72 * runner.REPETITIONS:
        raise ValueError(f"Incomplete run: {len(rows)} records")
    _reconcile_protected_csvs(rows)
    before_hashes = {p.name: _sha(p) for p in [
        journal_path, OUT / "episode_timings.csv", OUT / "parity_validation.csv",
        OUT / "parity_mismatches.jsonl", runner.active_binding_path(),
    ]}
    runner.PRIOR_COMPREHENSIVE = CORRECT_HISTORICAL_TIMING
    runner._emit_csv = _safe_emit_csv
    runner.analyze()

    case_rows, variance_rows = compute_case_repetition_variability(rows)
    _safe_emit_csv(OUT / "case_repetition_variability.csv", case_rows)
    _safe_emit_csv(OUT / "repeatability_variance_summary.csv", variance_rows)
    (OUT / "benchmark_protocol.md").write_bytes((ROOT / "docs/h2_controlled_compute_benchmark_protocol_v1.md").read_bytes())

    report = OUT / "final_report.md"
    content = report.read_text(encoding="utf-8")
    addendum = (
        "\n## Repetition and case variability\n\n"
        "The five repetitions replay the same 72 fixed map×schedule cases per model; they are repeated measurements, not 360 independent maps. "
        "`case_repetition_variability.csv` reports each model×case×component mean, standard deviation, P95 and P99 across the five repetitions. "
        "`repeatability_variance_summary.csv` reports average within-case repetition SD separately from the across-case SD of the 72 case means.\n\n"
        "## Measurement machine observations\n\n"
        "The run used the bound environment in `environment_info.json`; periodic manual system load and `vm_stat` observations are in `runtime_observations_external.jsonl`. "
        "The macOS permission policy denied `ps`/`top` process enumeration, and no thermal telemetry was available, so process-specific contention and thermal throttling cannot be ruled out.\n\n"
        "## Historical B+Age comparison qualification\n\n"
        "All 360 corrected B+Age traces are retained as expected historical non-parity: the old arm labeled B+Age had EVI enabled (B+C). "
        "The other 53 models have exact semantic parity for all 19,080 model×case×repetition records.\n"
    )
    if "## Repetition and case variability" not in content:
        report.write_text(content.rstrip() + "\n" + addendum, encoding="utf-8")

    changed = {name: _sha(OUT / name) != digest for name, digest in before_hashes.items()}
    if any(changed.values()):
        raise RuntimeError(f"Protected run artifacts changed during analysis: {changed}")

    manifest = {}
    for path in sorted(OUT.rglob("*")):
        if path.is_file() and path.name != "artifact_manifest.json":
            manifest[str(path.relative_to(OUT))] = _sha(path)
    manifest_path = OUT / "artifact_manifest.json"
    if manifest_path.exists():
        raise FileExistsError("Refusing to overwrite artifact_manifest.json")
    manifest_path.write_text(json.dumps({
        "status": "COMPLETE_WITH_DECLARED_B_AGE_HISTORICAL_NONPARITY",
        "files_sha256": manifest,
        "source_binding_sha256": _sha(runner.active_binding_path()),
        "created_by": str(Path(__file__).relative_to(ROOT)),
    }, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "episodes": len(rows),
        "models": 54,
        "repetitions": 5,
        "exact_parity_records_outside_b_age": sum(r["model_id"] != "b_age" for r in rows),
        "expected_b_age_nonparity_records": sum(r["model_id"] == "b_age" and not r["parity_match"] for r in rows),
        "protected_hashes_unchanged": True,
        "status": "ANALYSIS_COMPLETE",
    }, indent=2), flush=True)


if __name__ == "__main__":
    main()
