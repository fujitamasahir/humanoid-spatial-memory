"""Summarize frozen RDAO v1 shadow visibility probes at the DECISION level.

Never re-run policies, generate worlds, use hidden ground truth as a controller
input, or modify existing experiment/probe files. Descriptive development data
only. Do not interpret a shadow-visible cell as a causal success improvement.

Run after scripts/diagnose_rdao_visibility_replay.py --scope primary.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]
RDAO_DIR = ROOT / "results/phase2_mujoco/rdao_v1_phase2_evaluation"
PROBE_DIR = ROOT / "results/phase2_mujoco/rdao_v1_visibility_probe_primary"
BASE_DIR = ROOT / "results/phase2_mujoco/g1_forward_first_61ray_emergency_safety_full_288_v1"
DEFAULT_OUT = ROOT / "results/phase2_mujoco/rdao_v1_opportunity_analysis"

NUMERIC_FIELDS = (
    "step", "newly_visible", "new_free", "new_occupied", "new_near_route",
    "predicted_zero_but_visible", "missed_near_route",
    "center_outside_fov_but_visible", "center_outside_range_but_visible",
    "occlusion_or_other_zero_but_visible",
)
REASONS = (
    "no_visible_uncertain_route_relevant_region",
    "best_region_score_below_budget_adjusted_threshold",
    "observation_budget_exhausted",
)


def read_csv(path: Path):
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def parse_bool(value) -> bool:
    if value in (True, "True", "true", "1"):
        return True
    if value in (False, "False", "false", "0"):
        return False
    raise ValueError(f"Invalid boolean {value!r}")


def episode_key(row):
    return (row["world_identity"], int(row["schedule"]), int(row["seed"]))


def write_csv(path: Path, rows, columns):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def percent(numerator, denominator):
    return round(100.0 * numerator / denominator, 3) if denominator else None


def decision_summary(rows):
    by_reason = defaultdict(list)
    for row in rows:
        by_reason[row["rejection_reason"]].append(row)
    result = []
    for reason in sorted(by_reason):
        part = by_reason[reason]
        n = len(part)
        with_route = sum(row["new_near_route"] > 0 for row in part)
        with_missed = sum(row["missed_near_route"] > 0 for row in part)
        result.append({
            "reason": reason,
            "rejected_decisions": n,
            "with_new_route_near_cells": with_route,
            "with_predicted_zero_route_near_cells": with_missed,
            "fraction_with_new_route_near_pct": percent(with_route, n),
            "fraction_with_missed_route_near_pct": percent(with_missed, n),
            "sum_newly_visible": sum(row["newly_visible"] for row in part),
            "sum_new_near_route": sum(row["new_near_route"] for row in part),
            "sum_missed_near_route": sum(row["missed_near_route"] for row in part),
        })
    return result


def cohort_metrics(rows, selected_keys):
    part = [row for row in rows if episode_key(row) in selected_keys]
    def count(key):
        return sum(row[key] > 0 for row in part)
    early = [row for row in part if row["step"] <= 20]
    return {
        "episodes": len(selected_keys),
        "rejected_decisions": len(part),
        "fraction_decisions_with_new_route_near_pct": percent(count("new_near_route"), len(part)),
        "fraction_decisions_with_predicted_zero_route_near_pct":
            percent(count("missed_near_route"), len(part)),
        "first_20_rejected_decisions": len(early),
        "first_20_fraction_new_route_near_pct":
            percent(sum(row["new_near_route"] > 0 for row in early), len(early)),
        "first_20_fraction_missed_route_near_pct":
            percent(sum(row["missed_near_route"] > 0 for row in early), len(early)),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe", type=Path, default=PROBE_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite output: {args.output}")

    summary = json.loads((args.probe / "summary.json").read_text())
    if summary["scope"] != "primary" or summary["status"] != "DESCRIPTIVE_EVALUATOR_ONLY_NOT_CAUSAL":
        raise ValueError("Expected the frozen primary diagnostic probe, not a different scope")
    records = read_csv(args.probe / "rejected_decisions.csv")
    for row in records:
        for name in NUMERIC_FIELDS:
            row[name] = int(row[name])
    if len(records) != int(summary["rejected_decisions"]):
        raise ValueError("Probe row count differs from saved verified summary")
    if any(sum(row[col] for row in records) != summary["totals"][col]
           for col in NUMERIC_FIELDS if col in summary["totals"]):
        raise ValueError("Probe totals differ from saved verified summary")
    if len({(episode_key(row), row["step"]) for row in records}) != len(records):
        raise ValueError("Duplicate step within an episode's rejected decisions")
    if any(row["missed_near_route"] > row["new_near_route"] or
           row["predicted_zero_but_visible"] > row["newly_visible"] for row in records):
        raise ValueError("Inconsistent shadow observation counters")

    rdao = read_csv(RDAO_DIR / "primary_episodes.csv")
    baselines = read_csv(BASE_DIR / "episodes.csv")
    rdao_index = {episode_key(row): row for row in rdao}
    baseline_index = {(episode_key(row), row["method"]): row for row in baselines}
    if len(rdao) != 72 or len(rdao_index) != 72:
        raise ValueError("Expected 72 unique RDAO primary episodes")
    if len(baselines) != 288 or len(baseline_index) != 288:
        raise ValueError("Expected 288 unique historical baseline episodes")
    if any(episode_key(row) not in rdao_index for row in records):
        raise ValueError("Unknown episode in visibility probe")
    if any(row["rejection_reason"] not in REASONS for row in records):
        raise ValueError("Unexpected rejected-decision reason")

    by_episode = defaultdict(list)
    for row in records:
        by_episode[episode_key(row)].append(row)
    episodes = []
    for key, source in sorted(rdao_index.items()):
        decisions = sorted(by_episode.get(key, []), key=lambda row: row["step"])
        success = parse_bool(source["success"])
        control = {}
        for policy in ("periodic", "age", "uncertainty"):
            row = baseline_index.get((key, policy))
            if row is None:
                raise ValueError(f"Missing paired {policy} baseline for {key}")
            control[policy] = parse_bool(row["success"])
        missed_events = [r for r in decisions if r["missed_near_route"] > 0]
        new_events = [r for r in decisions if r["new_near_route"] > 0]
        # Report earliest opportunity as a hypothesis; no counterfactual claim.
        first = missed_events[0] if missed_events else None
        episodes.append({
            "world_identity": key[0], "schedule": key[1], "seed": key[2],
            "mechanism": source["mechanism"],
            "rdao_success": success, "periodic_success": control["periodic"],
            "age_success": control["age"], "uncertainty_success": control["uncertainty"],
            "rdao_steps": int(source["elapsed_steps"]),
            "rdao_observations": int(source["observation_count"]),
            "rejected_decisions": len(decisions),
            "decisions_with_new_route_near": len(new_events),
            "decisions_with_predicted_zero_route_near": len(missed_events),
            "first_missed_route_near_step": first["step"] if first else "",
            "first_missed_route_near_reason": first["rejection_reason"] if first else "",
            "sum_new_route_near": sum(x["new_near_route"] for x in decisions),
            "sum_predicted_zero_route_near": sum(x["missed_near_route"] for x in decisions),
            "first20_decisions_with_predicted_zero_route_near":
                sum(x["missed_near_route"] > 0 for x in decisions if x["step"] <= 20),
        })

    failed = {episode_key(e) for e in rdao if not parse_bool(e["success"])}
    succeeded = set(rdao_index) - failed
    fail_periodic_win = {(ep["world_identity"], ep["schedule"], ep["seed"]) for ep in episodes
                         if not ep["rdao_success"] and ep["periodic_success"]}
    fail_age_win = {(ep["world_identity"], ep["schedule"], ep["seed"]) for ep in episodes
                    if not ep["rdao_success"] and ep["age_success"]}
    priority = [e for e in episodes if not e["rdao_success"] and
                e["decisions_with_predicted_zero_route_near"] > 0]
    priority.sort(key=lambda row: (
        not row["periodic_success"], not row["age_success"],
        int(row["first_missed_route_near_step"]),
        -int(row["first20_decisions_with_predicted_zero_route_near"]),
        row["world_identity"], row["schedule"]))
    summary_out = {
        "status": "EXPLORATORY_DESCRIPTIVE_NOT_CAUSAL",
        "source": str(args.probe.relative_to(ROOT)) if args.probe.is_relative_to(ROOT) else str(args.probe),
        "probe_rejected_decisions": len(records),
        "probe_accepted_observations_exactly_verified":
            summary["accepted_observations_exactly_verified"],
        "rdao_failed_episodes": len(failed),
        "rdao_success_episodes": len(succeeded),
        "rdao_failed_but_periodic_succeeded_episodes": len(fail_periodic_win),
        "rdao_failed_but_age_succeeded_episodes": len(fail_age_win),
        "rejected_decision_reason_counts":
            dict(sorted(Counter(r["rejection_reason"] for r in records).items())),
        "reason_summary": decision_summary(records),
        "cohorts": {
            "rdao_success": cohort_metrics(records, succeeded),
            "rdao_failure": cohort_metrics(records, failed),
            "rdao_failure_periodic_success": cohort_metrics(records, fail_periodic_win),
            "rdao_failure_age_success": cohort_metrics(records, fail_age_win),
        },
        "priority_episodes_with_predicted_zero_route_near": len(priority),
        "limitations": [
            "The 72 worlds/schedules are development fit data, not held-out validation.",
            "Per-step cell counts re-count cells across different rejection steps.",
            "Longer failed episodes have more opportunities; compare per-decision and first-20 rates.",
            "Visible unknown cells can be navigation-irrelevant, and false-negative prediction does not prove a route would change.",
            "No intervention or causal outcome claim is made; the shadow sensor is evaluator-only.",
        ],
    }
    args.output.mkdir(parents=True)
    write_csv(args.output / "decision_reason_summary.csv",
              summary_out["reason_summary"],
              list(summary_out["reason_summary"][0]) if summary_out["reason_summary"] else ["reason"])
    write_csv(args.output / "episode_opportunity_summary.csv", episodes, list(episodes[0]))
    write_csv(args.output / "priority_failure_cases.csv", priority,
              list(episodes[0]))
    (args.output / "summary.json").write_text(json.dumps(
        summary_out, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(json.dumps({
        "output": str(args.output),
        "rdao_failures": len(failed),
        "rdao_fail_periodic_success": len(fail_periodic_win),
        "rdao_fail_age_success": len(fail_age_win),
        "reason_summary": summary_out["reason_summary"],
        "cohorts": summary_out["cohorts"],
        "priority_first_10": [
            {k: p[k] for k in (
                "world_identity", "schedule", "periodic_success", "age_success",
                "first_missed_route_near_step", "first_missed_route_near_reason",
                "decisions_with_predicted_zero_route_near")} for p in priority[:10]
        ],
    }, indent=2))


if __name__ == "__main__":
    main()
