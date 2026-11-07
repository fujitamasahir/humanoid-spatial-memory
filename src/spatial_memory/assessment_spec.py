"""Pinned Phase 1.4C inputs and matrix; no outcome-driven selection."""
from collections import Counter
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from .manifests import digest, environment_hash, layout_hash
from .simulation import Scenario
from .tuning_spec import candidates, file_sha256, EPISODE_CONFIG
from .task_policies import PolicyParameters
from .robustness import truth_audit

MANIFEST_RELATIVE = 'results/phase1_4a/manifests/assessment.json'
MANIFEST_SHA256 = '6335b77dd5838b2ea312d3293c939354e0b7f454eccbc679f0c59d4fe031c822'
LOCK_SHA256 = 'ecdd2f11e0c279bfa6c8557fcc646c4f714d2c7627deb731cbb366138a64d2f1'
CAPS = (1, 2, 4, 8, 16, None)
METHODS = ('static', 'age', 'uncertainty', 'periodic1', 'periodic2', 'periodic5',
           'fixed-rate', 'random-quota', 'quota-periodic', 'route-weighted',
           'disruption-visible', 'query-gate-conceptual')


def load_inputs(root, path=None):
    root = Path(root).resolve()
    expected = root / MANIFEST_RELATIVE
    if path is not None and Path(path).resolve() != expected:
        raise ValueError('Only the pinned assessment manifest is accepted')
    if file_sha256(expected) != MANIFEST_SHA256:
        raise ValueError('Assessment manifest checksum mismatch')
    lock_path = root / 'results/phase1_4b/parameter_lock.json'
    if file_sha256(lock_path) != LOCK_SHA256:
        raise ValueError('Parameter lock checksum mismatch')
    if (root / 'results/phase1_4b/parameter_lock.sha256').read_text().split() != [LOCK_SHA256, 'parameter_lock.json']:
        raise ValueError('Parameter checksum sidecar mismatch')
    lock = json.loads(lock_path.read_text())
    if (digest(lock['configuration']) != lock['configuration_sha256']
            or hashlib.sha256(json.dumps(lock['source_files_sha256'], sort_keys=True).encode()).hexdigest() != lock['source_sha256']):
        raise ValueError('Parameter lock provenance mismatch')
    if lock['assessment_outcomes_accessed'] is not False:
        raise ValueError('Assessment was accessed during selection')
    if set(lock['selected']) != {c['method'] for c in candidates()}:
        raise ValueError('Require exactly four selected configurations')
    for method, selected in lock['selected'].items():
        candidate = next(c for c in candidates() if c['method'] == method and c['candidate'] == selected['candidate'])
        if any(selected[k] != candidate[k] for k in ('parameters', 'parameter_tuple', 'tuned_parameters')):
            raise ValueError('Selected configuration is not frozen')
    for name, expected_hash in lock['source_files_sha256'].items():
        raw = (root / name).read_bytes().replace(b'\r\n', b'\n')
        # The sole existing-source edit admits assessment to the internal adapter.
        # The public smoke and tuning input gates remain unchanged.
        if name == 'src/spatial_memory/protocol_evaluation.py':
            raw = raw.replace(b"{'smoke','synthetic-regression','tuning','assessment'}", b"{'smoke','synthetic-regression','tuning'}")
        if hashlib.sha256(raw).hexdigest() != expected_hash:
            raise ValueError('Frozen algorithm/source changed: ' + name)
    tuning_path = root / 'results/phase1_4a/manifests/tuning.json'
    if file_sha256(tuning_path) != lock['tuning_manifest_sha256']:
        raise ValueError('Tuning manifest checksum mismatch')
    tuning = json.loads(tuning_path.read_text())
    tuning_hashes = {r['environment_sha256'] for r in tuning['records']}
    for name, sha in lock['artifact_sha256'].items():
        if file_sha256(root / 'results/phase1_4b' / name) != sha:
            raise ValueError('Locked selection artifact changed: ' + name)
    selection_rows = [json.loads(line) for line in (root / 'results/phase1_4b/episodes.jsonl').read_text().splitlines()]
    if (len(selection_rows) != 3780 or len({r['episode_id'] for r in selection_rows}) != 3780
            or any(r['environment_sha256'] not in tuning_hashes or r['metrics']['purpose'] != 'tuning' for r in selection_rows)):
        raise ValueError('Selection ledger contains non-tuning or duplicate records')
    manifest = json.loads(expected.read_text())
    if (manifest['partition'] != 'assessment' or manifest['split'] != 'development'
            or manifest['outcomes_generated'] is not False or manifest['horizon'] != 40):
        raise ValueError('Invalid assessment partition')
    records = manifest['records']
    hashes = set()
    for record in records:
        scenario = Scenario.from_dict(record['scenario'])
        fingerprint = environment_hash(scenario)
        if (record['partition'] != 'assessment' or scenario.split != 'development'
                or not 20000 <= record['seed'] < 30000
                or fingerprint != record['environment_sha256'] or fingerprint in hashes
                or layout_hash(scenario) != record['layout_sha256']):
            raise ValueError('Assessment environment/hash/namespace mismatch')
        if truth_audit(scenario, 40) != record['topology']:
            raise ValueError('Stored assessment topology audit mismatch')
        hashes.add(fingerprint)
    # Audit stored realizations without regenerating any assessment world.
    if (len(records) != 70 or len(Counter(r['family'] for r in records)) != 7
            or set(Counter(r['family'] for r in records).values()) != {10}):
        raise ValueError('Require ten environments in each of seven families')
    if hashes.intersection(r['environment_sha256'] for r in tuning['records']):
        raise ValueError('Assessment/tuning realization overlap')
    if hashes.intersection(manifest['excluded_environment_hashes']):
        raise ValueError('Assessment/historical realization overlap')
    provenance = manifest['provenance']
    if digest(provenance['config']) != provenance['config_sha256']:
        raise ValueError('Manifest configuration provenance mismatch')
    if hashlib.sha256(json.dumps(provenance['source_files_sha256'], sort_keys=True).encode()).hexdigest() != provenance['source_sha256']:
        raise ValueError('Manifest source provenance mismatch')
    return manifest, lock


def jobs(manifest, lock):
    plan = []
    for record in manifest['records']:
        for cap in CAPS:
            for noise in (0.0, 0.05):
                for method in METHODS:
                    for replicate in range(5 if method == 'random-quota' else 1):
                        job = {k: record[k] for k in ('environment_sha256', 'layout_sha256', 'family', 'seed')}
                        job.update(method=method, cap=cap, noise=noise, replicate=replicate,
                                   parameters=lock['selected'].get(method, {}).get('parameters', asdict(PolicyParameters())))
                        plan.append(dict(episode_id=digest(job), **job))
    if len(plan) != 13440 or len({j['episode_id'] for j in plan}) != 13440:
        raise ValueError('Incomplete or duplicated assessment plan')
    return plan


def execute_job(job, record):
    from .protocol_evaluation import _run_instrumented_episode
    scenario = Scenario.from_dict(record['scenario'])
    if (record['partition'] != 'assessment' or scenario.split != 'development'
            or environment_hash(scenario) != job['environment_sha256']):
        raise ValueError('Assessment job/realization mismatch')
    cfg = {**EPISODE_CONFIG, 'max_observations': job['cap'],
           'sensor': {**EPISODE_CONFIG['sensor'], 'noise': job['noise']}}
    metrics, frames, samples = _run_instrumented_episode(
        scenario, cfg, job['method'], job['seed'],
        parameters=None if job['method'] in METHODS[:6] else job['parameters'],
        replicate=job['replicate'], purpose='assessment')
    return dict(metrics=metrics, frames=frames, feasibility_samples=samples)
