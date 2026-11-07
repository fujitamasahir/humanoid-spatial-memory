"""Execute only the pinned 13,440-job Phase 1.4C matrix, with exact resume."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
from time import perf_counter
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from spatial_memory.assessment_spec import load_inputs, jobs, execute_job, METHODS, CAPS, MANIFEST_SHA256, LOCK_SHA256
from spatial_memory.assessment_store import canonical_bytes, atomic_bytes, writer_lease, recover_staging, inventory, checkpoint
from spatial_memory.manifests import digest
from spatial_memory.provenance import provenance
from spatial_memory.task_policies import PolicyController

RAW = ROOT / 'results/raw/phase1_4c_assessment'
COMPACT = ROOT / 'results/phase1_4c'


def preflight(manifest, lock, plan):
    records = manifest['records']
    return dict(parameter_lock_sha256=LOCK_SHA256, assessment_manifest_sha256=MANIFEST_SHA256,
                selected_parameters={m: s['parameters'] for m, s in lock['selected'].items()},
                environments=len(records), layout_clusters=len({r['layout_sha256'] for r in records}),
                clusters_per_family={f: len({r['layout_sha256'] for r in records if r['family'] == f})
                                     for f in sorted({r['family'] for r in records})},
                methods=METHODS, caps=CAPS, episodes=len(plan),
                assessment_tuning_environment_overlap=0,
                assessment_used_for_selection=False,
                selection_evidence='Pinned lock assessment_outcomes_accessed=false; tuning loader and 3780-job selection ledger use only tuning inputs.',
                algorithms_unchanged=True,
                adapter_change='Only internal assessment purpose admission; public gates unchanged.',
                regenerated_assessment_environments=False)


def run(max_new=None, preflight_only=False):
    manifest, lock = load_inputs(ROOT)
    plan = jobs(manifest, lock)
    COMPACT.mkdir(parents=True, exist_ok=True)
    atomic_bytes(COMPACT / 'preflight.json', canonical_bytes(preflight(manifest, lock, plan)))
    if preflight_only:
        print('Preflight passed; no assessment policy executed.')
        return
    config = dict(purpose='assessment', manifest_sha256=MANIFEST_SHA256,
                  lock_sha256=LOCK_SHA256, job_plan_sha256=digest(plan), episodes=13440,
                  bootstrap=dict(seed=1404001, replicates=10000, max_attempts=100000,
                                 unit='global layout hash', statistic='equal-family paired mean'))
    prov = provenance(ROOT, config)
    identity = dict(config=config, source_sha256=prov['source_sha256'], python=prov['python'],
                    platform=prov['platform'], packages=prov['packages'])
    contract = dict(run_id=digest(identity), identity=identity, provenance=prov)
    expected = {j['episode_id']: j for j in plan}
    with writer_lease(RAW):
        path = RAW / 'run.json'
        if path.exists():
            saved = json.loads(path.read_text())
            if saved['identity'] != identity or saved['run_id'] != contract['run_id']:
                raise ValueError('Cannot resume after source/config/dependency change')
            contract = saved
        else:
            atomic_bytes(path, canonical_bytes(contract), immutable=True)
        recovered = recover_staging(RAW, expected, contract['run_id'])
        if recovered:
            atomic_bytes(RAW / ('recovery-' + digest(recovered) + '.json'), canonical_bytes(recovered), immutable=True)
        rows, entries, missing = inventory(RAW, expected, contract['run_id'])
        completed = {r['episode_id'] for r in rows}
        initial = len(completed)
        records = {r['environment_sha256']: r for r in manifest['records']}
        if max_new != 0:
            for method in METHODS:
                warm = PolicyController(np.zeros((3, 5), np.int8), method, goal=(4, 1), max_observations=4)
                warm.decide(1, (1, 1))
        begin = perf_counter()
        executed = 0
        for job in plan:
            if job['episode_id'] in completed:
                continue
            if max_new is not None and executed >= max_new:
                break
            result = execute_job(job, records[job['environment_sha256']])
            checkpoint(RAW, job, result, contract['run_id'])
            del result
            completed.add(job['episode_id'])
            executed += 1
            if executed % 100 == 0:
                print(f'Committed {len(completed)}/13440; session seconds={perf_counter()-begin:.1f}', flush=True)
        status = dict(run_id=contract['run_id'], expected=13440, completed=len(completed),
                      already_completed=initial, executed_this_session=executed,
                      session_seconds=perf_counter()-begin, recovery_actions=len(recovered))
        atomic_bytes(RAW / f'session-{initial:05d}-{len(completed):05d}.json', canonical_bytes(status))
        if len(completed) == 13440:
            rows, entries, missing = inventory(RAW, expected, contract['run_id'], require_complete=True)
            by_id = {r['episode_id']: r for r in rows}
            atomic_bytes(COMPACT / 'episodes.jsonl', b''.join(canonical_bytes(by_id[j['episode_id']]) for j in plan))
            atomic_bytes(COMPACT / 'trace_storage_manifest.json', canonical_bytes(dict(
                storage_root=RAW.resolve().as_posix(), repository_relative_root=RAW.relative_to(ROOT).as_posix(),
                run_id=contract['run_id'], episodes=entries,
                compressed_bytes=sum(e['compressed_bytes'] for e in entries),
                trace_semantics='Full original decisions, memory, observations and evaluator truth; no fields dropped.')))
            atomic_bytes(COMPACT / 'run_provenance.json', canonical_bytes(contract))
        print(json.dumps(status), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--max-new-episodes', type=int)
    parser.add_argument('--preflight-only', action='store_true')
    args = parser.parse_args()
    if args.max_new_episodes is not None and args.max_new_episodes < 0:
        parser.error('max-new-episodes must be nonnegative')
    run(args.max_new_episodes, args.preflight_only)
