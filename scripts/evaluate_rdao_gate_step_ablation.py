"""Post-hoc causal gate-step ablations in selected saved Phase 2 development cases.

Test whether the SECOND/THIRD already-observed online gate override explains
rescue loss and detours, without presuming a deployable decision rule.

All gate eligibility and action safety use PUBLIC observed memory only, as in
online_safe_gate_screen. The allowed absolute steps are deliberately selected
from previously COMMITTED development traces: these are diagnostic
interventions using hindsight, NOT an online RDAO v2 algorithm.

This program validates frozen baseline fidelity, previous first/every replay
outcomes, no contact regressions and the original preserved Phase1.5 manifest.
Does NOT access held-out environments or alter saved originals.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

import evaluate_rdao_phase2 as evaluator
import phase2_mujoco_navigation as navigation
from evaluate_rdao_one_shot_interventions import (
    _bool, _compare_trace, _first_difference, _key, _load_csv,
    _metrics, _read_saved_traces, _sha, _write_csv,
)
from evaluate_rdao_online_safe_gate_screen import run_candidate

PRIMARY = ROOT / "results/phase2_mujoco/rdao_v1_phase2_evaluation"
SCREEN = ROOT / "results/phase2_mujoco/rdao_v1_online_safe_gate_fit72_screen_v1"
FORENSIC = ROOT / "results/phase2_mujoco/rdao_v1_online_safe_gate_forensics_v1"
DEFAULT_OUTPUT = ROOT / "results/phase2_mujoco/rdao_v1_online_gate_step_ablation_v1"
DEFAULT_WORLDS = ("M:80030009", "M:80030000",
                  "R:80000022", "M:80030010")
COMPARE_METRICS = ("success", "elapsed_steps", "observations",
                   "travel_distance_m", "turns", "unwanted_contacts")


def _jsonable(v):
    if isinstance(v, float) and not math.isfinite(v):
        return None
    if isinstance(v, dict):
        return {str(k): _jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    return v


def _metrics_match(first, second):
    return all(first[key] == second[key] for key in COMPARE_METRICS)


def _full_screen_index():
    rows = _load_csv(SCREEN / "paired_online_gate.csv")
    if len(rows) != 144:
        raise RuntimeError("Expected both policies on original 72 episodes")
    return {(r["world_identity"], int(r["schedule"]), int(r["seed"]),
             r["policy"]): r for r in rows}


def _gate_steps():
    gates = _load_csv(FORENSIC / "focus_gate_events.csv")
    result = {}
    for gate in gates:
        if gate["policy"] != "every" or not _bool(gate["override_applied"]):
            continue
        key = (gate["world_identity"], int(gate["schedule"]))
        result.setdefault(key, []).append(int(gate["step"]))
    for key, steps in result.items():
        if steps != sorted(set(steps)):
            raise RuntimeError(f"Unordered/duplicate saved gated steps: {key}")
    return result


def _regimes(steps):
    """No gate, original first gate, selective second/third, and all gates."""
    steps = tuple(steps)
    if not steps:
        return [("none", ())]
    out = [("none", ()), ("first", steps[:1])]
    if len(steps) >= 2:
        out.append(("first_second", steps[:2]))
    if len(steps) >= 3:
        out.append(("first_third", (steps[0], steps[2])))
    if len(steps) >= 2:
        out.append(("all", steps))
    return out


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--world", action="append", default=None,
                        help="Known fit world suffix; repeat for multiple worlds")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing overwrite: {args.output}")

    chosen = tuple(args.world or DEFAULT_WORLDS)
    original_rows = _load_csv(PRIMARY / "primary_episodes.csv")
    original_index = {_key(row): row for row in original_rows}
    frozen_traces = _read_saved_traces()
    if len(original_index) != 72 or set(original_index) != set(frozen_traces):
        raise RuntimeError("Expected exact frozen 72-episode primary evidence")

    approved_worlds = {x["identity"]: x for x in navigation.admitted_worlds()}
    if len(approved_worlds) != 36:
        raise RuntimeError("Admitted 36 fit worlds changed")
    keys = sorted(
        (k for k in original_index
         if any(k[0].endswith(suffix) for suffix in chosen)),
        key=lambda k: (k[0], k[1]))
    if len(keys) != 2 * len(set(chosen)):
        raise RuntimeError("Expected exactly two schedule pairs per selected world")
    preserved = navigation.verify_preserved_prefix()
    source_files = (
        PRIMARY / "primary_episodes.csv",
        PRIMARY / "primary_traces.jsonl.gz",
        SCREEN / "paired_online_gate.csv",
        FORENSIC / "focus_gate_events.csv",
    )
    source_hashes = {str(path.relative_to(ROOT)): _sha(path) for path in source_files}
    gate_index = _gate_steps()
    screen = _full_screen_index()
    rows, trace_records = [], []

    for case_num, (identity, schedule, seed) in enumerate(keys, 1):
        if seed != 42:
            raise RuntimeError("Frozen primary seed differs")
        payload = approved_worlds[identity]
        original_row, original_trace = evaluator._instrumented_case(
            payload, schedule, "rdao_v1")
        if evaluator._signature(original_row) != evaluator._signature(
                original_index[(identity, schedule, seed)]):
            raise RuntimeError("Primary baseline row failed reproduction")
        _compare_trace(frozen_traces[(identity, schedule, seed)],
                       original_trace)
        base_metrics = _metrics(original_index[(identity, schedule, seed)])
        expected_steps = gate_index.get((identity, schedule), ())
        if not expected_steps:
            raise RuntimeError(f"No pre-registered saved gate override steps: {identity}/{schedule}")

        # Reproduce pre-existing original online first/every arms before
        # considering any retrospectively step-selected diagnostic.
        for policy in ("first", "every"):
            row, trace, state = run_candidate(payload, schedule, policy)
            got = _metrics(row)
            saved = screen.get((identity, schedule, seed, policy))
            if saved is None:
                raise RuntimeError("Saved full-screen policy entry missing")
            compared = {
                "success": _bool(saved["gated_success"]),
                "elapsed_steps": int(saved["gated_elapsed_steps"]),
                "observations": int(saved["gated_observations"]),
                "travel_distance_m": float(saved["gated_travel_distance_m"]),
                "turns": int(saved["gated_turns"]),
                "unwanted_contacts": int(saved["gated_unwanted_contacts"]),
            }
            if not _metrics_match(got, compared):
                raise RuntimeError(
                    f"Cannot reproduce the committed {policy} full-screen arm: "
                    f"{identity}/{schedule} got {got} expected {compared}")
            if policy == "every":
                applied = [e["step"] for e in state["events"]
                           if e["override_applied"]]
                if applied != list(expected_steps):
                    raise RuntimeError("Saved every override step sequence not reproduced")

        for regime, allowlist in _regimes(expected_steps):
            row, trace, state = run_candidate(payload, schedule, "every",
                                              allowed_gate_steps=allowlist)
            met = _metrics(row)
            if (met["observations"] > 20
                    or met["unwanted_contacts"] != 0
                    or int(row.get("g1_unselected_action_shield_queries", 0)) != 0
                    or not _bool(row["g1_shield_query_count_valid"])):
                raise RuntimeError(f"Safety or budget check failed: {identity}/{schedule}/{regime}")
            overrides = [int(e["step"]) for e in state["events"]
                         if e["override_applied"]]
            if any(t not in allowlist for t in overrides):
                raise RuntimeError("Gate override outside approved diagnostic step list")
            if not overrides:
                _compare_trace(original_trace, trace)
            else:
                _compare_trace(original_trace, trace, before_step=min(overrides))
            if regime == "none":
                if not _metrics_match(met, base_metrics):
                    raise RuntimeError("Disabled-gate experiment differs from frozen baseline")
            if regime in ("first", "all"):
                reference_policy = "first" if regime == "first" else "every"
                saved = screen[(identity, schedule, seed, reference_policy)]
                compared = {
                    "success": _bool(saved["gated_success"]),
                    "elapsed_steps": int(saved["gated_elapsed_steps"]),
                    "observations": int(saved["gated_observations"]),
                    "travel_distance_m": float(saved["gated_travel_distance_m"]),
                    "turns": int(saved["gated_turns"]),
                    "unwanted_contacts": int(saved["gated_unwanted_contacts"]),
                }
                if not _metrics_match(met, compared):
                    raise RuntimeError(
                        f"Step-filter regime {regime} differs from saved {reference_policy}: "
                        f"{identity}/{schedule}")
            item = {
                "world_identity": identity, "schedule": schedule,
                "seed": seed, "regime": regime,
                "preselected_all_override_steps": json.dumps(expected_steps),
                "allowed_step_interventions": json.dumps(allowlist),
                "actually_applied_gate_steps": json.dumps(overrides),
                "eligible_gate_candidates_excluded": sum(
                    e.get("guard") == "diagnostic_step_filter_forced_normal_replan"
                    for e in state["events"]),
                "baseline_success": base_metrics["success"],
                "success": met["success"],
                "baseline_steps": base_metrics["elapsed_steps"],
                "steps": met["elapsed_steps"],
                "delta_steps": met["elapsed_steps"] - base_metrics["elapsed_steps"],
                "baseline_observations": base_metrics["observations"],
                "observations": met["observations"],
                "delta_observations": met["observations"] - base_metrics["observations"],
                "baseline_distance_m": base_metrics["travel_distance_m"],
                "distance_m": met["travel_distance_m"],
                "delta_distance_m": met["travel_distance_m"] - base_metrics["travel_distance_m"],
                "turns": met["turns"],
                "unwanted_contacts": met["unwanted_contacts"],
                "first_action_or_pose_difference_from_original":
                    _first_difference(original_trace, trace),
            }
            rows.append(item)
            trace_records.append({
                "identity": identity, "schedule": schedule,
                "regime": regime, "allowed_steps": list(allowlist),
                "actual_overrides": overrides,
                "events": state["events"], "metrics": met, "trace": trace,
            })
        print(f"Completed case {case_num}/{len(keys)}: {identity} schedule {schedule}",
              flush=True)

    if navigation.verify_preserved_prefix() != preserved:
        raise RuntimeError("Protected Phase1.5 preservation changed")
    if {str(p.relative_to(ROOT)): _sha(p) for p in source_files} != source_hashes:
        raise RuntimeError("Protected inputs changed")

    summary = {
        "status": "RETROSPECTIVE_GATE_STEP_CAUSAL_ABLATION_NOT_AN_ONLINE_POLICY",
        "selected_worlds": list(chosen),
        "episode_pairs": len(keys),
        "baseline_and_existing_first_every_reproduced": True,
        "preserved_phase15": preserved,
        "source_hashes": source_hashes,
        "notes": [
            "Step allowlists were selected after reading prior outcomes and cannot be deployed online.",
            "Removing an earlier gate changes subsequent trajectory, observation timing, and availability of later gate steps.",
            "If a later event vanishes or changes under the intervention, the scenario is not a controlled isolation of that event's independent effect.",
            "No held-out worlds have been read or simulated.",
            "The G1 is a kinematic-root MuJoCo navigation proxy, not actual biped walking.",
            "Two schedule repeats per world are correlated, not independent world replications.",
        ],
    }
    args.output.mkdir(parents=True)
    _write_csv(args.output / "step_ablation_comparison.csv", rows)
    with gzip.open(args.output / "step_ablation_traces.jsonl.gz",
                   "wt", encoding="utf-8") as stream:
        for item in trace_records:
            stream.write(json.dumps(_jsonable(item), sort_keys=True,
                                    allow_nan=False) + "\n")
    (args.output / "summary.json").write_text(
        json.dumps(summary, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "cases": len(keys),
        "regimes": len(rows),
        "high_interest_results": [
            {
                "world": row["world_identity"].split(":")[-2] + ":" +
                         row["world_identity"].split(":")[-1],
                "schedule": row["schedule"], "regime": row["regime"],
                "allowed": row["allowed_step_interventions"],
                "applied": row["actually_applied_gate_steps"],
                "success": row["success"],
                "steps": row["steps"],
                "observations": row["observations"],
                "distance_m": row["distance_m"],
            }
            for row in rows if (
                row["world_identity"].endswith("M:80030009")
                or (row["world_identity"].endswith("M:80030000") and row["schedule"] == 1)
            )
        ],
    }, indent=2))


if __name__ == "__main__":
    run()
