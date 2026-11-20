import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from analyze_h2_controlled_compute_postrun import compute_case_repetition_variability


def test_case_variation_separates_repeat_and_case_spread():
    rows = []
    for case, offset in ((0, 0.0), (1, 10.0)):
        for repetition, jitter in enumerate((0.0, 1.0, -1.0, 2.0, -2.0), start=1):
            rows.append({
                "model_id": "toy",
                "case_index": case,
                "repetition": repetition,
                "initialization_ns": 1_000_000,
                "decision_ns": int((offset + jitter + 5) * 1_000_000),
                "memory_update_ns": 2_000_000,
                "total_model_computation_ns": int((offset + jitter + 8) * 1_000_000),
            })

    cases, summary = compute_case_repetition_variability(rows)
    decision_cases = [row for row in cases if row["component"] == "observation_decision"]
    decision_summary = next(row for row in summary if row["component"] == "observation_decision")
    assert len(decision_cases) == 2
    assert all(row["repetitions"] == 5 for row in decision_cases)
    assert decision_cases[0]["mean_ms"] == 5.0
    assert decision_cases[1]["mean_ms"] == 15.0
    assert decision_summary["case_count"] == 2
    assert decision_summary["between_case_sd_of_case_means_ms"] > decision_summary["mean_within_case_repetition_sd_ms"]
