"""Synthetic storage/verification checks; no assessment policy execution."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import numpy as np
import pytest

from spatial_memory.assessment_spec import load_inputs, jobs, execute_job, METHODS, CAPS, LOCK_SHA256
from spatial_memory.assessment_store import checkpoint, inventory, recover_staging, writer_lease, canonical_bytes
from spatial_memory.protocol_evaluation import run_protocol_episode
from spatial_memory.robustness import generate_robustness
from spatial_memory.tuning_spec import EPISODE_CONFIG, file_sha256

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('assessment_analysis', ROOT/'scripts/analyze_locked_assessment.py')
analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)


def fixture_result(cap=2):
    scenario = generate_robustness('detour', 6102)
    metrics, frames, samples = run_protocol_episode(scenario, {**EPISODE_CONFIG, 'max_observations':cap}, 'fixed-rate', 6102)
    metrics['purpose'] = 'assessment'
    job = dict(episode_id='synthetic',method='fixed-rate',seed=6102,cap=cap,replicate=0,parameters=metrics['policy_parameters'])
    return scenario, job, dict(metrics=metrics,frames=frames,feasibility_samples=samples)


def test_pinned_assessment_matrix_and_immutable_lock():
    manifest, lock = load_inputs(ROOT)
    plan = jobs(manifest, lock)
    assert len(plan) == len({j['episode_id'] for j in plan}) == 13440
    assert set(j['method'] for j in plan) == set(METHODS)
    assert set(j['cap'] for j in plan) == set(CAPS)
    assert sum(j['method']=='random-quota' for j in plan) == 4200
    assert file_sha256(ROOT/'results/phase1_4b/parameter_lock.json') == LOCK_SHA256
    assert len({r['layout_sha256'] for r in manifest['records']}) == 37


def test_reject_alternate_input_before_open(tmp_path):
    with pytest.raises(ValueError, match='pinned assessment'):
        load_inputs(ROOT, tmp_path/'assessment.json')


def test_adapter_preserves_historical_parameter_gate(monkeypatch):
    from spatial_memory.manifests import environment_hash
    from spatial_memory.task_policies import PolicyParameters
    from dataclasses import asdict
    scenario = generate_robustness('detour', 6102)
    record = dict(partition='assessment', scenario=asdict(scenario))
    calls = []
    def capture(*args, **kwargs):
        calls.append(kwargs)
        return {}, [], []
    monkeypatch.setattr('spatial_memory.protocol_evaluation._run_instrumented_episode', capture)
    for method in METHODS:
        execute_job(dict(method=method, seed=6102, cap=2, noise=0., replicate=0,
                         parameters=asdict(PolicyParameters()), environment_sha256=environment_hash(scenario)),record)
        assert (calls[-1]['parameters'] is None) == (method in METHODS[:6])


@pytest.mark.parametrize('cap',[1,2,None])
def test_full_trace_independent_ledgers(cap):
    scenario, job, result = fixture_result(cap)
    bundle = dict(job=job, result=result, run_id='test')
    # Serialize arrays exactly as the saved trace format does.
    bundle = json.loads(canonical_bytes(bundle))
    assert analysis.verify_trace(bundle, scenario) >= 20
    bundle['result']['metrics']['dynamic_contacts'] += 1
    with pytest.raises(AssertionError):
        analysis.verify_trace(bundle, scenario)


def test_resume_duplicate_and_lease(tmp_path):
    _, job, result = fixture_result()
    with writer_lease(tmp_path):
        with pytest.raises(ValueError,match='writer'):
            with writer_lease(tmp_path):
                pass
        path = checkpoint(tmp_path, job, result, 'test')
        sha = file_sha256(path)
        rows, entries, missing = inventory(tmp_path, {job['episode_id']:job}, 'test', require_complete=True)
        assert len(rows) == 1 and not missing and file_sha256(path) == sha
        with pytest.raises(ValueError,match='Duplicate'):
            checkpoint(tmp_path, job, result, 'test')
        assert file_sha256(path) == sha
        with pytest.raises(ValueError,match='Duplicate'):
            recover_staging(tmp_path, {job['episode_id']:job}, 'test')


def test_reject_changed_replicate(tmp_path):
    _, job, result = fixture_result()
    result['metrics']['replicate'] = 1
    with pytest.raises(ValueError, match='configuration'):
        checkpoint(tmp_path, job, result, 'test')


def test_bootstrap_shared_clusters_and_family_gate():
    records = [dict(family=f,layout_sha256=str(i)) for f in ('a','b') for i in range(35)]
    w, audit = analysis.bootstrap_weights(records)
    assert w.shape == (10000,70)
    assert np.allclose(w.sum(axis=1),1)
    assert np.array_equal(w[:,:35],w[:,35:])
    assert audit['clusters'] == 35
    w2, audit2 = analysis.bootstrap_weights(records)
    assert np.array_equal(w,w2) and audit == audit2
    assert analysis.bootstrap_weights(records[:20])[0] is None
    records = [dict(family='a',layout_sha256=str(i)) for i in range(35)]+[dict(family='b',layout_sha256='0')]
    assert analysis.bootstrap_weights(records)[0] is None
