"""Fast contract tests for post-hoc gate-step ablation design and metrics.

No MuJoCo, hidden geometry or held-out worlds are accessed.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from evaluate_rdao_gate_step_ablation import (
    _gate_steps, _metrics_match, _regimes
)


def test_subsets_handle_three_candidate_events():
    assert _regimes([26, 50, 55]) == [
        ("none", ()), ("first", (26,)),
        ("first_second", (26, 50)),
        ("first_third", (26, 55)),
        ("all", (26, 50, 55)),
    ]


def test_subset_of_one_event_never_invents_extra_gates():
    assert _regimes([3]) == [("none", ()), ("first", (3,))]


def test_subset_of_two_events_is_explicit_about_redundant_all():
    assert _regimes([20, 45]) == [
        ("none", ()), ("first", (20,)),
        ("first_second", (20, 45)), ("all", (20, 45)),
    ]


def test_exact_metrics_match_flags_contacts_and_distance():
    baseline = {
        "success": True, "elapsed_steps": 77, "observations": 6,
        "travel_distance_m": 45.0, "turns": 7, "unwanted_contacts": 0,
    }
    assert _metrics_match(baseline, dict(baseline))
    for key, val in [
        ("success", False), ("elapsed_steps", 78),
        ("observations", 7), ("travel_distance_m", 45.75),
        ("turns", 8), ("unwanted_contacts", 1),
    ]:
        change = dict(baseline)
        change[key] = val
        assert not _metrics_match(baseline, change)


def test_gate_steps_read_only_every_applied_candidates(monkeypatch):
    import evaluate_rdao_gate_step_ablation as module
    rows = [
        {"world_identity": "fit:M:80030009", "schedule": "0",
         "policy": "every", "override_applied": "True", "step": "26"},
        {"world_identity": "fit:M:80030009", "schedule": "0",
         "policy": "first", "override_applied": "True", "step": "26"},
        {"world_identity": "fit:M:80030009", "schedule": "0",
         "policy": "every", "override_applied": "False", "step": "30"},
        {"world_identity": "fit:M:80030009", "schedule": "0",
         "policy": "every", "override_applied": "True", "step": "50"},
        {"world_identity": "fit:M:80030009", "schedule": "0",
         "policy": "every", "override_applied": "True", "step": "55"},
    ]
    monkeypatch.setattr(module, "_load_csv", lambda path: rows)
    assert _gate_steps() == {("fit:M:80030009", 0): [26, 50, 55]}
