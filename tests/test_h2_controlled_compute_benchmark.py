import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    'h2_controlled_compute', ROOT/'scripts/run_h2_controlled_compute_benchmark.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_semantic_digest_ignores_timing_but_preserves_behavior():
    row = {'success': True, 'elapsed_steps': 4, 'decision_time_ms': 1.2,
           'model_compute_ns': 100, 'evaluation_loop_time_seconds': .01,
           'observation_count': 2}
    replay = {'steps': [{'step': 1, 'position': [1, 2], 'action': 'forward',
                         'diagnostic_timing_ns': [3]}], 'metrics': row}
    original = MODULE.semantic_sha(row, replay)
    changed_time = dict(row, decision_time_ms=99.0, model_compute_ns=900,
                        evaluation_loop_time_seconds=900)
    changed_replay = {'steps': [{'step': 1, 'position': [1, 2], 'action': 'forward',
                                  'diagnostic_timing_ns': [400]}], 'metrics': changed_time}
    assert MODULE.semantic_sha(changed_time, changed_replay) == original
    moved = {'steps': [{'step': 1, 'position': [2, 2], 'action': 'forward',
                        'diagnostic_timing_ns': [400]}], 'metrics': changed_time}
    assert MODULE.semantic_sha(changed_time, moved) != original


def test_quantiles_are_deterministic_and_interpolated():
    assert MODULE._quantile([1, 2, 3, 4, 5], .5) == 3
    assert MODULE._quantile([1, 2, 3, 4, 5], .95) == 4.8
    assert MODULE._stats([10, 20])['mean'] == 15


def test_model_matrix_contains_54_admitted_unique_models():
    ids = MODULE.model_ids()
    assert len(ids) == 54
    assert len(set(ids)) == 54
    assert 'c_route3' not in ids and 'c_topology3c' not in ids


def test_periodic5_returns_before_grid_scoring():
    source = (ROOT/'src/spatial_memory/cadence_age_optimized_v1.py').read_text()
    assert source.index("if mode=='periodic5'") < source.index('yy,xx=np.indices')
    assert "granted=step>0 and step%(age+1)==0" in source


def test_timer_scope_is_frozen_model_components_only():
    source = (ROOT/'scripts/h2_final_common.py').read_text()
    assert "times['initialization'].append" in source
    assert "times['decision'].append" in source
    assert "times['update'].append" in source
    assert 'time.perf_counter_ns()' in source


def test_historical_b_age_nonparity_is_explicitly_classified():
    payload = {'identity': 'fixture', 'mechanism': 'R'}
    row = {'success': True, 'observation_count': 1, 'elapsed_steps': 1,
           'g1_unwanted_contact_pairs': 0}
    diag = {'timing_ns': {'initialization':[10], 'decision':[20], 'update':[30]}}
    result = MODULE._timing_row(1, 1, 1, payload, 0, 'b_age', row, diag,
                                'new', 'historical', 100)
    assert result['parity_match'] is False
    assert result['parity_classification'] == 'EXPECTED_B_AGE_HISTORICAL_IMPLEMENTATION_NONPARITY'
    periodic = MODULE._timing_row(1, 1, 1, payload, 0, 'periodic4', row, diag,
                                  'new', 'historical', 100)
    assert periodic['parity_classification'] == 'UNEXPECTED_SEMANTIC_MISMATCH'


def test_smoke_checkpoint_key_distinguishes_schedule_indices():
    schedule0 = {'case_index': 7, 'schedule': 0, 'model_id': 'periodic4'}
    schedule1 = {'case_index': 7, 'schedule': 1, 'model_id': 'periodic4'}
    assert MODULE._smoke_key(schedule0) != MODULE._smoke_key(schedule1)
