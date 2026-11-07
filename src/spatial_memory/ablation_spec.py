"""Frozen Phase 1.4D admission, provenance and exact 1,680-job plan."""
from collections import Counter
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import subprocess

from .assessment_spec import load_inputs, MANIFEST_SHA256, LOCK_SHA256
from .manifests import digest, environment_hash
from .simulation import Scenario
from .task_policies import ABLATIONS
from .tuning_spec import EPISODE_CONFIG, file_sha256

BASE_COMMIT = '9885f1bd0ea3408435304debf6ffce8d99dbde72'
CAPS = (4, 8)
NOISES = (0.0, 0.05)
FROZEN_ABLATIONS = ('no-route-disruption', 'no-visibility', 'fixed-rate',
                    'exclude-unknown', 'no-budget-threshold', 'no-alternative-candidates')
PARAMETERS = dict(fixed_rate=.05, entropy_threshold=.75, route_weight=3.0,
                  route_threshold=.75, disruption_threshold=.4, budget_price=0,
                  reliability_threshold=.9, visibility_fraction=.5)


def original_snapshot(root):
    """Check every original tracked file against Git; also retain raw SHA-256 values."""
    root = Path(root)
    listing = subprocess.check_output(['git', 'ls-tree', '-r', BASE_COMMIT], cwd=root, text=True)
    result = {}
    for line in listing.splitlines():
        header, name = line.split('\t', 1)
        _, kind, expected = header.split()
        if kind != 'blob':
            raise ValueError('Unexpected original tree entry')
        raw = (root / name).read_bytes()
        normalized = raw if name.endswith('.png') else raw.replace(b'\r\n', b'\n')
        actual = hashlib.sha1(b'blob ' + str(len(normalized)).encode() + b'\0' + normalized).hexdigest()
        if actual != expected:
            raise ValueError('Original tracked file changed: ' + name)
        result[name] = hashlib.sha256(raw).hexdigest()
    return result


def load_frozen(root, path=None):
    manifest, lock = load_inputs(root, path)
    if tuple(ABLATIONS) != FROZEN_ABLATIONS:
        raise ValueError('Ablation definitions changed')
    if lock['selected']['disruption-visible']['parameters'] != PARAMETERS:
        raise ValueError('Selected parameters differ from frozen Phase 1.4D contract')
    return manifest, lock


def make_job(record, cap, noise, ablation):
    if cap not in CAPS or noise not in NOISES or ablation not in FROZEN_ABLATIONS:
        raise ValueError('Nonfrozen ablation configuration')
    job = {k: record[k] for k in ('environment_sha256', 'layout_sha256', 'family', 'seed')}
    job.update(schema='phase1.4d-job-v1', method='disruption-visible', cap=cap,
               noise=noise, replicate=0, ablation=ablation, parameters=PARAMETERS.copy(),
               configuration={**EPISODE_CONFIG, 'max_observations': cap,
                              'sensor': {**EPISODE_CONFIG['sensor'], 'noise': noise}})
    return dict(episode_id=digest(job), **job)


def jobs(manifest):
    plan = [make_job(r, cap, noise, ablation) for r in manifest['records']
            for cap in CAPS for noise in NOISES for ablation in FROZEN_ABLATIONS]
    if len(plan) != 1680 or len({j['episode_id'] for j in plan}) != 1680:
        raise ValueError('Incomplete/duplicated frozen ablation matrix')
    if set(Counter(j['ablation'] for j in plan).values()) != {280}:
        raise ValueError('Unbalanced ablation matrix')
    return plan


def execute_job(job, record):
    """Internal adapter called only after pinned-input validation by the runner."""
    if job != make_job(record, job['cap'], job['noise'], job['ablation']):
        raise ValueError('Altered frozen job')
    scenario = Scenario.from_dict(record['scenario'])
    if (record['partition'] != 'assessment' or scenario.split != 'development'
            or not 20000 <= record['seed'] < 30000
            or environment_hash(scenario) != job['environment_sha256']):
        raise ValueError('Only pinned assessment realizations accepted')
    from .protocol_evaluation import _run_instrumented_episode
    metrics, frames, samples = _run_instrumented_episode(
        scenario, job['configuration'], job['method'], job['seed'],
        parameters=job['parameters'], ablation=job['ablation'], replicate=0, purpose='assessment')
    return dict(metrics=metrics, frames=frames, feasibility_samples=samples)


def preflight(root, *, verify_parent_traces=True):
    root = Path(root)
    manifest, lock = load_frozen(root)
    dependencies = {}
    for line in (root/'requirements.txt').read_text().splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        package, required = line.strip().split('==')
        dependencies[package] = version(package)
        if dependencies[package] != required:
            raise ValueError('Pinned dependency version mismatch: '+package)
    snapshot = original_snapshot(root)
    compact = root / 'results/phase1_4c'
    storage = json.loads((compact / 'trace_storage_manifest.json').read_text())
    raw = (root / storage['repository_relative_root']).resolve()
    if (raw/'episodes').is_symlink():
        raise ValueError('Parent episode directory must not be a symlink')
    rows = {}
    for line in (compact / 'episodes.jsonl').read_text().splitlines():
        row = json.loads(line)
        if row['episode_id'] in rows:
            raise ValueError('Duplicate parent record')
        rows[row['episode_id']] = row
    entries = storage['episodes']
    if (len(entries) != 13440 or len(rows) != 13440
            or {e['episode_id'] for e in entries} != set(rows)
            or {p.name for p in (raw / 'episodes').iterdir()} != {k+'.json.gz' for k in rows}):
        raise ValueError('Parent assessment inventory incomplete/conflicting')
    if verify_parent_traces:
        for index, entry in enumerate(entries):
            path = raw / entry['path']
            if entry['path'] != 'episodes/'+entry['episode_id']+'.json.gz' or path.is_symlink():
                raise ValueError('Unexpected parent trace path')
            if path.stat().st_size != entry['compressed_bytes'] or file_sha256(path) != entry['sha256']:
                raise ValueError('Parent trace hash/size mismatch')
            if (index+1) % 2000 == 0:
                print(f'Parent trace hashes verified: {index+1}/13440', flush=True)
    run = json.loads((compact / 'run_provenance.json').read_text())
    for name, sha in run['provenance']['source_files_sha256'].items():
        if hashlib.sha256((root/name).read_bytes().replace(b'\r\n', b'\n')).hexdigest() != sha:
            raise ValueError('Assessment dependency/source changed: '+name)
    historical = {}
    for name in snapshot:
        if (name.startswith(('results/phase1_1/', 'results/phase1_2/', 'results/phase1_3/', 'results/representative/'))
                and name.endswith('results.json')):
            historical[name] = len(json.loads((root/name).read_text(encoding='utf-8-sig'))['episodes'])
    if sum(historical.values()) != 2212:
        raise ValueError('Historical record count differs from 2212')
    plan = jobs(manifest)
    report = dict(base_commit=BASE_COMMIT, parameter_lock_sha256=LOCK_SHA256,
                  assessment_manifest_sha256=MANIFEST_SHA256, original_file_sha256=snapshot,
                  historical_records=historical, historical_record_count=2212,
                  parent_episodes=13440, parent_trace_checksums_verified=13440 if verify_parent_traces else 0,
                  episodes=1680, job_plan_sha256=digest(plan), caps=list(CAPS), noises=list(NOISES),
                  ablations=list(FROZEN_ABLATIONS), parameters=PARAMETERS,
                  definitions='Existing frozen TaskObserver ablation branches; no policy changes.',
                  assessment_regenerated=False, held_out_accessed=False)
    return manifest, report
