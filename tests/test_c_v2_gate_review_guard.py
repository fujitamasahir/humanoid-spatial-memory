import json

import pytest

from scripts.evaluate_c_v2_candidate_coverage_fit72 import read_accepted_gate


def test_reviewed_invalid_numeric_pass_is_blocked(tmp_path):
    gate=tmp_path/'synthetic_mechanism_results.json'
    gate.write_text(json.dumps({'mechanism_gate':{'status':'PASS'}}))
    (tmp_path/'gate_review.json').write_text(json.dumps({'status':'INVALID_STOP_BEFORE_FIT'}))
    with pytest.raises(RuntimeError,match='blocks FIT72'):
        read_accepted_gate(gate)


def test_conforming_numeric_pass_without_review_remains_supported(tmp_path):
    gate=tmp_path/'gate.json'
    gate.write_text(json.dumps({'mechanism_gate':{'status':'PASS'}}))
    assert read_accepted_gate(gate)=='PASS'


def test_c_v2b_gate_requires_adjacent_passing_review(tmp_path):
    gate=tmp_path/'synthetic_mechanism_results.json'
    gate.write_text(json.dumps({'protocol':'docs/phase2_c_v2b_topology_protocol.md',
        'mechanism_gate':{'status':'PASS'}}))
    with pytest.raises(RuntimeError,match='requires a passing gate_review'):
        read_accepted_gate(gate)


def test_rejected_numeric_gate_is_returned_for_existing_guard(tmp_path):
    gate=tmp_path/'gate.json'
    gate.write_text(json.dumps({'mechanism_gate':{'status':'REJECTED'}}))
    assert read_accepted_gate(gate)=='REJECTED'
