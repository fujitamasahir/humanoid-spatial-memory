"""Resumable execution of the pinned 3780-episode development tuning matrix only."""
import argparse
import csv
import io
import json
from pathlib import Path
import sys
from time import perf_counter
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from spatial_memory.tuning_spec import (load_tuning_manifest,jobs,candidates,digest,file_sha256,
    MANIFEST_SHA256,EPISODE_CONFIG,SELECTION_VERSION,execute_tuning_job)
from spatial_memory.tuning_store import (canonical_bytes,atomic_bytes,writer_lease,checkpoint,
    recover_staging,inventory)
from spatial_memory.tuning_selection import select_parameters
from spatial_memory.provenance import provenance
from spatial_memory.task_policies import PolicyController

RAW=ROOT/'results/raw/phase1_4b_tuning'
COMPACT=ROOT/'results/phase1_4b'


def contract_and_provenance(plan):
    config=dict(purpose='tuning',manifest_sha256=MANIFEST_SHA256,episode_config=EPISODE_CONFIG,
        caps=[2,4,8],grid=candidates(),episodes=3780,job_plan_sha256=digest(plan),
        selection_algorithm=SELECTION_VERSION)
    prov=provenance(ROOT,config)
    identity=dict(config=config,source_sha256=prov['source_sha256'],
                  python=prov['python'],platform=prov['platform'],packages=prov['packages'])
    return dict(run_id=digest(identity),identity=identity,provenance=prov)


def write_csv(path,rows):
    buf=io.StringIO(newline='')
    writer=csv.DictWriter(buf,fieldnames=list(rows[0]),lineterminator='\n')
    writer.writeheader()
    for row in rows:
        writer.writerow({k:json.dumps(v,sort_keys=True) if isinstance(v,(dict,list,tuple)) else v for k,v in row.items()})
    atomic_bytes(path,buf.getvalue().encode())


def seal_results(raw,compact,run,plan):
    expected={j['episode_id']:j for j in plan}
    rows,entries,missing=inventory(raw,expected,run['run_id'],require_complete=True)
    by_id={r['episode_id']:r for r in rows}
    rows=[by_id[j['episode_id']] for j in plan]
    result=select_parameters(rows)
    # Full metrics remain small; full decision/truth arrays stay in per-episode gzip files.
    atomic_bytes(compact/'episodes.jsonl',b''.join(canonical_bytes(r) for r in rows))
    table=[{k:v for k,v in row.items() if k!='metrics'}|row['metrics'] for row in rows]
    write_csv(compact/'episodes.csv',table)
    write_csv(compact/'candidate_scores.csv',[dict(method=s['method'],candidate=s['candidate'],
        parameters=s['tuned_parameters'],**s['means']) for s in result['candidates']])
    atomic_bytes(compact/'candidate_scores.json',canonical_bytes(result))
    storage=dict(format='per-episode-gzip-json-v1',storage_root=raw.resolve().as_posix(),
        repository_relative_root=raw.resolve().relative_to(ROOT).as_posix() if raw.resolve().is_relative_to(ROOT) else None,
        run_id=run['run_id'],manifest_sha256=MANIFEST_SHA256,
        compressed_bytes=sum(e['compressed_bytes'] for e in entries),episodes=entries,
        trace_semantics='Complete original frames, evaluator truth and feasibility samples; no fields dropped.',
        recovery=list(sorted(p.name for p in (raw/'quarantine').glob('*'))))
    atomic_bytes(compact/'trace_storage_manifest.json',canonical_bytes(storage))
    atomic_bytes(compact/'run_provenance.json',canonical_bytes(run))
    lock=dict(schema='phase1.4b-parameter-lock-v1',selection_algorithm_version=SELECTION_VERSION,
        development_only=True,assessment_outcomes_accessed=False,episode_count=3780,
        tuning_manifest_sha256=MANIFEST_SHA256,run_id=run['run_id'],
        source_sha256=run['identity']['source_sha256'],
        source_files_sha256=run['provenance']['source_files_sha256'],
        configuration=run['identity']['config'],configuration_sha256=digest(run['identity']['config']),
        environment=dict(python=run['identity']['python'],platform=run['identity']['platform'],packages=run['identity']['packages']),
        selected=result['selected'],full_candidate_grid=result['candidates'],
        counts=dict(environments=35,families=7,caps=3,candidates_per_method=9,episodes_per_candidate=105,episodes_per_method=945),
        artifact_sha256={name:file_sha256(compact/name) for name in (
            'episodes.jsonl','episodes.csv','candidate_scores.json','candidate_scores.csv','trace_storage_manifest.json','run_provenance.json')})
    atomic_bytes(compact/'parameter_lock.json',canonical_bytes(lock),immutable=True)
    atomic_bytes(compact/'parameter_lock.sha256',(file_sha256(compact/'parameter_lock.json')+'  parameter_lock.json\n').encode(),immutable=True)
    return result


def run_matrix(manifest,raw,compact,max_new=None):
    raw,compact=Path(raw),Path(compact)
    if raw.resolve()==compact.resolve() or raw.resolve() in compact.resolve().parents or compact.resolve() in raw.resolve().parents:
        raise ValueError('Trace and compact artifact directories must be separate')
    plan=jobs(manifest);expected={j['episode_id']:j for j in plan}
    contract=contract_and_provenance(plan)
    compact.mkdir(parents=True,exist_ok=True)
    with writer_lease(raw):
        path=raw/'run.json'
        if path.exists():
            run=json.loads(path.read_text())
            if run['identity']!=contract['identity'] or run['run_id']!=contract['run_id']:
                raise ValueError('Cannot resume after source/config/dependency/plan change')
        else:
            run=contract
            atomic_bytes(path,canonical_bytes(run),immutable=True)
        recovery=recover_staging(raw,expected,run['run_id'])
        if recovery:
            atomic_bytes(raw/('recovery-'+digest(recovery)+'.json'),canonical_bytes(recovery),immutable=True)
        rows,entries,missing=inventory(raw,expected,run['run_id'])
        completed={r['episode_id'] for r in rows}
        initial=len(completed)
        records={r['environment_sha256']:r for r in manifest['records']}
        begin=perf_counter();executed=0
        # One untimed synthetic public-memory warmup per tuned method, each session.
        if max_new!=0:
            for method in dict.fromkeys(c['method'] for c in candidates()):
                warm=PolicyController(np.zeros((3,5),np.int8),method,goal=(4,1),max_observations=4)
                warm.decide(1,(1,1))
        for job in plan:
            if job['episode_id'] in completed:
                continue
            if max_new is not None and executed>=max_new:
                break
            result=execute_tuning_job(job,records[job['environment_sha256']])
            checkpoint(raw,job,result,run['run_id'])
            del result
            completed.add(job['episode_id']);executed+=1
            if executed%100==0:
                print(f'Committed {len(completed)}/3780 episodes; session seconds={perf_counter()-begin:.1f}',flush=True)
        status=dict(run_id=run['run_id'],completed=len(completed),expected=3780,
                    executed_this_session=executed,already_completed=initial,
                    session_seconds=perf_counter()-begin,recovery_actions=len(recovery))
        atomic_bytes(raw/f'session-{initial:04d}-{len(completed):04d}.json',canonical_bytes(status))
        if len(completed)==3780:
            seal_results(raw,compact,run,plan)
            status['sealed']=True
        print(json.dumps(status),flush=True)
        return status


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,default=ROOT/'results/phase1_4a/manifests/tuning.json')
    parser.add_argument('--max-new-episodes',type=int)
    args=parser.parse_args()
    if args.max_new_episodes is not None and args.max_new_episodes<0:
        parser.error('max-new-episodes must be nonnegative')
    manifest=load_tuning_manifest(ROOT,args.manifest)
    run_matrix(manifest,RAW,COMPACT,args.max_new_episodes)


if __name__=='__main__':
    main()
