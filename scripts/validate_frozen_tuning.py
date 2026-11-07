"""Independent SQLite/integer-total recomputation of the saved parameter lock."""
from fractions import Fraction
import json
from pathlib import Path
import sqlite3
import sys
from time import perf_counter
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from spatial_memory.tuning_spec import load_tuning_manifest,jobs,file_sha256,MANIFEST_SHA256,digest
from spatial_memory.tuning_store import read_bundle,canonical_bytes,atomic_bytes


def verify(compact,trace_root=None):
    compact=Path(compact);begin=perf_counter()
    lock=json.loads((compact/'parameter_lock.json').read_text())
    if (compact/'parameter_lock.sha256').read_text().split()[0]!=file_sha256(compact/'parameter_lock.json'):
        raise ValueError('Parameter lock checksum mismatch')
    if lock['tuning_manifest_sha256']!=MANIFEST_SHA256 or lock['episode_count']!=3780:
        raise ValueError('Not the frozen complete tuning lock')
    if digest(lock['configuration'])!=lock['configuration_sha256']:
        raise ValueError('Configuration digest mismatch')
    for path,sha in lock['source_files_sha256'].items():
        raw=(ROOT/path).read_bytes().replace(b'\r\n',b'\n')
        import hashlib
        if hashlib.sha256(raw).hexdigest()!=sha:
            raise ValueError('Source changed since lock: '+path)
    for path,sha in lock['artifact_sha256'].items():
        if file_sha256(compact/path)!=sha:
            raise ValueError('Artifact changed since lock: '+path)
    manifest=load_tuning_manifest(ROOT)
    expected={j['episode_id']:j for j in jobs(manifest)}
    db=sqlite3.connect(':memory:')
    db.execute('CREATE TABLE results (id TEXT PRIMARY KEY, method TEXT, candidate INTEGER, family TEXT, cap INTEGER, env TEXT, layout TEXT, cf INTEGER, goal INTEGER, obs INTEGER, elapsed INTEGER)')
    # Read only one compact metric record at a time. Do not call producer's selection.
    metrics_by_id={}
    with (compact/'episodes.jsonl').open() as stream:
        for line in stream:
            row=json.loads(line);key=row['episode_id']
            if key not in expected or {k:row[k] for k in expected[key]}!=expected[key]:
                raise ValueError('Unexpected/conflicting metric job')
            m=row['metrics']
            try:
                db.execute('INSERT INTO results VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                    (key,row['method'],row['candidate'],row['family'],row['cap'],row['environment_sha256'],row['layout_sha256'],
                     int(m['contact_free_success']),int(m['success']),m['observation_count'],m['elapsed_steps']))
            except sqlite3.IntegrityError as error:
                raise ValueError('Duplicate saved episode') from error
            metrics_by_id[key]=m
    if set(metrics_by_id)!=set(expected):
        raise ValueError('Missing saved tuning episodes')
    strata=db.execute('SELECT method,candidate,family,cap,count(*) FROM results GROUP BY method,candidate,family,cap').fetchall()
    if len(strata)!=36*21 or any(row[-1]!=5 for row in strata):
        raise ValueError('Unbalanced family/cap data')
    totals=db.execute('SELECT method,candidate,count(*),sum(cf),sum(goal),sum(obs),sum(elapsed) FROM results GROUP BY method,candidate').fetchall()
    all_scores={};winners={}
    grid={ (c['method'],c['candidate']):c for c in lock['full_candidate_grid']}
    for method,candidate,n,cf,goal,obs,elapsed in totals:
        if n!=105:
            raise ValueError('Incorrect candidate execution count')
        params=tuple(grid[(method,candidate)]['parameter_tuple'])
        rank=(-cf,-goal,obs,elapsed,params) # balanced strata => identical denominator 105
        fractions=dict(contact_free_success=Fraction(cf,n),success=Fraction(goal,n),
                       observation_count=Fraction(obs,n),elapsed_steps=Fraction(elapsed,n),
                       observation_cost=Fraction(3*obs,2*n))
        all_scores[(method,candidate)]={k:[v.numerator,v.denominator] for k,v in fractions.items()}
        if grid[(method,candidate)]['exact_means']!=all_scores[(method,candidate)]:
            raise ValueError('Saved candidate score is incorrect')
        if method not in winners or rank<winners[method][0]:
            winners[method]=(rank,candidate)
    for method,(_,candidate) in winners.items():
        selected=lock['selected'][method]
        if selected['candidate']!=candidate or selected!=grid[(method,candidate)]:
            raise ValueError('Independent winner recomputation disagrees')
    storage=json.loads((compact/'trace_storage_manifest.json').read_text())
    trace_root=Path(trace_root or storage['storage_root'])
    seen=set()
    for entry in storage['episodes']:
        key=entry['episode_id']
        if key in seen or key not in expected:
            raise ValueError('Duplicate/unexpected trace inventory')
        seen.add(key)
        path=(trace_root/entry['path']).resolve()
        if not path.is_relative_to(trace_root.resolve()):
            raise ValueError('Unsafe storage path')
        if file_sha256(path)!=entry['sha256'] or path.stat().st_size!=entry['compressed_bytes']:
            raise ValueError('Full trace checksum/size mismatch')
        bundle=read_bundle(path)
        if bundle['job']!=expected[key] or bundle['result']['metrics']!=metrics_by_id[key] or bundle['run_id']!=lock['run_id']:
            raise ValueError('Trace/metric/job conflict')
        frames=bundle['result']['frames'];m=metrics_by_id[key]
        if len(frames)!=m['elapsed_steps']+1 or sum(f['observation_granted'] for f in frames)!=m['observation_count']:
            raise ValueError('Trace count mismatch')
        del bundle
    if seen!=set(expected):
        raise ValueError('Missing full trace inventory')
    actual={p.name for p in (trace_root/'episodes').glob('*')}
    if actual!={j+'.json.gz' for j in expected}:
        raise ValueError('Missing/extra/duplicate checkpoint files')
    report=dict(status='verified',episodes=3780,trace_hashes_verified=len(seen),candidate_scores_verified=36,
        environment_count=db.execute('SELECT count(DISTINCT env) FROM results').fetchone()[0],
        layout_cluster_count=db.execute('SELECT count(DISTINCT layout) FROM results').fetchone()[0],
        winners={m:c for m,(_,c) in winners.items()},parameter_lock_sha256=file_sha256(compact/'parameter_lock.json'),
        independent_algorithm='sqlite-integer-totals-balanced-strata-v1',seconds=perf_counter()-begin,
        assessment_outcomes_accessed=False)
    db.close()
    return report


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compact',type=Path,default=ROOT/'results/phase1_4b')
    parser.add_argument('--trace-root',type=Path)
    args=parser.parse_args()
    report=verify(args.compact,args.trace_root)
    atomic_bytes(args.compact/'independent_verification.json',canonical_bytes(report))
    print(json.dumps(report))
