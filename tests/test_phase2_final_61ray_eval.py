"""Focused checks for the matched final Phase 2 evaluation bookkeeping."""

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/evaluate_phase2_61ray_emergency_safety_full_288.py'
SPEC = importlib.util.spec_from_file_location('phase2_final_61ray_eval', SCRIPT)
EVALUATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EVALUATOR)
_aggregate = EVALUATOR._aggregate
_bool = EVALUATOR._bool


def test_csv_boolean_values_are_parsed_without_truthy_false_strings():
    assert _bool('True') is True
    assert _bool('False') is False
    assert _bool(False) is False


def test_baseline_aggregate_keeps_contact_free_goal_counts_correct():
    rows = [
        {'success': 'True', 'g1_contact_free_success': 'True'},
        {'success': 'False', 'g1_contact_free_success': 'False'},
        {'success': 'True', 'g1_contact_free_success': 'False'},
    ]
    summary = _aggregate(rows)
    assert summary['goal_completions'] == 2
    assert summary['contact_free_goal_completions'] == 1
    assert summary['goal_completion_rate'] == 2 / 3
    assert summary['contact_free_goal_completion_rate'] == 1 / 3
