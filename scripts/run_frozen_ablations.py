"""Run only the 1,680 preregistered diagnostic ablations; exact checkpoint resume."""
import argparse
import json
from pathlib import Path
import sys
from time import perf_counter
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from spatial_memory.ablation_spec import preflight, jobs, execute_job, FROZEN_ABLATIONS, PARAMETERS
from spatial_memory.ablation_store import (canonical_bytes, atomic_bytes, writer_lease,
    recover_staging, inventory, checkpoint)
from spatial_memory.manifests import digest
from spatial_memory.provenance import provenance
from spatial_memory.task_policies import PolicyController, PolicyParameters

RAW = ROOT/'results/raw/phase1_4d_ablations'
COMPACT = ROOT/'results/phase1_4d'


def run(max_new=None, preflight_only=False):
    # Reuse the completed full parent-byte audit during consecutive resume sessions.
    # Every session still revalidates the pinned inputs and all original tracked bytes.
    audit_path = COMPACT/'preflight.json'
    reuse_audit = audit_path.exists() and not preflight_only
    manifest, audit = preflight(ROOT, verify_parent_traces=not reuse_audit)
    if reuse_audit:
        saved_audit = json.loads(audit_path.read_text())
        if saved_audit['parent_trace_checksums_verified'] != 13440:
            raise ValueError('No complete parent-byte audit available')
        audit['parent_trace_checksums_verified'] = 13440
        if audit != saved_audit:
            raise ValueError('Frozen inputs changed since full parent-byte audit')
    plan = jobs(manifest)
    COMPACT.mkdir(parents=True, exist_ok=True)
    atomic_bytes(audit_path, canonical_bytes(audit), immutable=True)
    if preflight_only:
        print('Frozen ablation preflight passed; no experiment executed.', flush=True)
        return
    config = dict(purpose='phase1.4d-diagnostic-ablations', job_plan_sha256=digest(plan),
                  episodes=1680, ablations=list(FROZEN_ABLATIONS), caps=[4,8], noises=[0.,.05],
                  parameters=PARAMETERS, episode_configuration=plan[0]['configuration'],
                  preflight_sha256=digest(audit),
                  bootstrap=dict(seed=1404001, draws=10000, max_attempts=100000,
                                 unit='global layout hash; all settings retained', weighting='equal family'))
    prov = provenance(ROOT, config)
    identity = dict(config=config, source_sha256=prov['source_sha256'],
                    python=prov['python'], platform=prov['platform'], packages=prov['packages'])
    run = dict(run_id=digest(identity), identity=identity, provenance=prov)
    expected = {j['episode_id']:j for j in plan}
    with writer_lease(RAW):
        path = RAW/'run.json'
        if path.exists():
            saved = json.loads(path.read_text())
            if saved['identity'] != identity or saved['run_id'] != run['run_id']:
                raise ValueError('Cannot resume changed source/config/dependency/plan identity')
            run = saved
        else:
            atomic_bytes(path, canonical_bytes(run), immutable=True)
        recovery = recover_staging(RAW, expected, run['run_id'])
        if recovery:
            atomic_bytes(RAW/('recovery-'+digest(recovery)+'.json'), canonical_bytes(recovery), immutable=True)
        rows, entries, missing = inventory(RAW, expected, run['run_id'])
        completed = {r['episode_id'] for r in rows}
        initial = len(completed)
        records = {r['environment_sha256']:r for r in manifest['records']}
        if max_new != 0:
            # One untimed synthetic public-memory decision per ablation, each executing session.
            for ablation in FROZEN_ABLATIONS:
                warm = PolicyController(np.zeros((3,5),np.int8), 'disruption-visible',
                    goal=(4,1), max_observations=4, parameters=PolicyParameters(**PARAMETERS), ablation=ablation)
                warm.decide(1,(1,1))
        begin = perf_counter()
        executed = 0
        for job in plan:
            if job['episode_id'] in completed:
                continue
            if max_new is not None and executed >= max_new:
                break
            result = execute_job(job, records[job['environment_sha256']])
            checkpoint(RAW, job, result, run['run_id'])
            del result
            completed.add(job['episode_id'])
            executed += 1
            if executed % 100 == 0:
                print(f'Committed {len(completed)}/1680; session seconds={perf_counter()-begin:.1f}', flush=True)
        status = dict(run_id=run['run_id'], completed=len(completed), expected=1680,
                      already_completed=initial, executed_this_session=executed,
                      recovery_actions=len(recovery), session_seconds=perf_counter()-begin)
        atomic_bytes(RAW/f'session-{initial:04d}-{len(completed):04d}.json', canonical_bytes(status), immutable=True)
        if len(completed) == 1680:
            rows, entries, missing = inventory(RAW, expected, run['run_id'], require_complete=True)
            by_id = {r['episode_id']:r for r in rows}
            atomic_bytes(COMPACT/'episodes.jsonl', b''.join(canonical_bytes(by_id[j['episode_id']]) for j in plan))
            atomic_bytes(COMPACT/'run_provenance.json', canonical_bytes(run))
            atomic_bytes(COMPACT/'trace_storage_manifest.json', canonical_bytes(dict(
                storage_root=RAW.resolve().as_posix(), repository_relative_root=RAW.relative_to(ROOT).as_posix(),
                run_id=run['run_id'], episodes=entries,
                compressed_bytes=sum(e['compressed_bytes'] for e in entries),
                trace_semantics='Complete original decisions, received observations, memory, evaluator truth and feasibility samples.')))
        print(json.dumps(status), flush=True)
        return status


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preflight-only', action='store_true')
    parser.add_argument('--max-new-episodes', type=int)
    args = parser.parse_args()
    if args.max_new_episodes is not None and args.max_new_episodes < 0:
        parser.error('max-new-episodes must be nonnegative')
    run(args.max_new_episodes, args.preflight_only)
