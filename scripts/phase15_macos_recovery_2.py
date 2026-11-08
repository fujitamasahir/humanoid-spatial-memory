"""Verify or execute the separately bound second M3 fit continuation.

`verify` is non-generative. `execute` is gated by committed verification evidence
for this exact binding and starts at sequence 418 / V index 368.
"""
import argparse
from collections import Counter
import gzip, hashlib, json, os, platform, subprocess, sys
from pathlib import Path
from time import perf_counter, process_time

from spatial_memory import phase15_bprime as bp
from spatial_memory.phase15_bprime_access import StageBinding
from spatial_memory.phase15_bprime_protocol import canonical_bytes, validate_inventory
from spatial_memory.phase15_bprime_epochs import ReadOnlyEpochPrefix
from spatial_memory.phase15_bprime_store import Checkpoints
from spatial_memory.phase15_bprime_coordinator import Coordinator
from spatial_memory.phase15_bprime_development import Builder
from spatial_memory.phase15_macos_monitored import MonitoredBackend

ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT/'results/raw/phase15_macos_development'
OUT=ROOT/'results/phase15_bprime_recovery_2'
RAW=ROOT/'results/raw/phase15_bprime_fit_recovery_2'
BIND=ROOT/'configs/phase15_macos_bindings/fit-recovery-2.json'
STOP='5ed258e6bbdc3a0bfa7cf45e3d2c5a1548fc24f2'

def sha(raw): return hashlib.sha256(raw).hexdigest()

def committed(path, commit='HEAD'):
    data=path.read_bytes()
    result=subprocess.run(['git','show',commit+':'+path.relative_to(ROOT).as_posix()],cwd=ROOT,capture_output=True,check=True)
    if result.stdout!=data: raise bp.IntegrityError('Uncommitted/changed evidence: '+str(path))
    return data

def exclusive(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    raw=canonical_bytes(value)
    with path.open('xb') as stream:
        stream.write(raw);stream.flush();os.fsync(stream.fileno())

def run(mode):
    verify=mode=='verify'
    output=OUT/('continuation_verification.json' if verify else 'continuation_execution.json')
    if output.exists(): raise bp.IntegrityError('Existing evidence is immutable; no automatic retry')
    if not verify:
        proof=json.loads(committed(OUT/'continuation_verification.json'))
        if proof.get('status')!='PASS_NO_REGISTERED_GENERATION' or proof.get('binding_sha256')!=sha(BIND.read_bytes()):
            raise bp.IntegrityError('Exact second-continuation verification is not committed')
    else:
        def denied(*a,**k): raise bp.IntegrityError('RNG/world construction prohibited during verification')
        bp.Stream.__init__=denied;bp.legacy.Stream.__init__=denied;bp.geometry=denied;bp.legacy.geometry=denied

    started=perf_counter();cpu=process_time();binding=StageBinding.load(BIND)
    meta=json.loads(binding.manifest_bytes)['runtime']
    if (meta['python']!=sys.version or meta['executable_sha256']!=sha(Path(sys.executable).resolve().read_bytes())
        or meta['machine']!=platform.machine() or meta['system']!=platform.system()):
        raise bp.IntegrityError('Runtime commitment changed')
    backend=MonitoredBackend(pin_path=ROOT/'results/runs/phase15_m3_migration_c3/option_b_pin.json')
    resources=RAW/(mode+'-resources');resources.mkdir(parents=True,exist_ok=False)
    calls=0;worker_cpu=0.0;batch=0;coordinator=None;failure=None;status='STARTING'
    def drain(label):
        nonlocal calls,worker_cpu,batch
        if not backend.events:return
        events=backend.events;backend.events=[];calls+=len(events)
        worker_cpu+=sum(e.get('cpu_seconds',0) for e in events)
        packed=gzip.compress(canonical_bytes(dict(label=label,events=events)),mtime=0)
        with (resources/f'{batch:08d}.json.gz').open('xb') as stream:
            stream.write(packed);stream.flush();os.fsync(stream.fileno())
        batch+=1
    try:
        inv=json.loads((OLD/'references/inventory.json').read_bytes())
        ledger=json.loads((OLD/'references/ledger.json').read_bytes())
        seal=json.loads((ROOT/'results/phase15_macos_development/reference_seal.json').read_bytes())
        refs=validate_inventory(inv,ledger,OLD/'references',expected_digest=seal['inventory_sha256'],
            expected_ledger_digest=seal['ledger_sha256'],backend=backend,binding=binding)
        drain('reference-verification')
        prefix=ReadOnlyEpochPrefix.load(binding,backend=backend);drain('418-record-prefix-verification')
        store=Checkpoints(RAW/'store',partition='fit',binding=binding,backend=backend)
        with store.writer():
            coordinator=Coordinator(store,refs,backend=backend,prefix=prefix)
            rows=coordinator.restore();drain('same-fit-state-reconstruction')
            if verify:
                if len(rows)!=418 or store.scan(): raise bp.IntegrityError('Expected exactly 418 prefix records and empty new store')
                cursors={m:coordinator.cursors.get(('fit',m),0) for m in bp.MECHANISMS}
                counts=dict(coordinator.index.credits('fit'));next_job=coordinator._job()
                expected=dict(identity=bp.Identity('fit','V',80020368).root,partition='fit',mechanism='V',index=368,sequence=418)
                if coordinator.sequence!=418 or cursors!={'R':24,'BP':14,'V':368,'M':12} or counts!={'R':12,'BP':12,'M':12} or next_job!=expected:
                    raise bp.IntegrityError('Restored second-continuation cursor/order differs')
                status='PASS_NO_REGISTERED_GENERATION'
            else:
                old_a=json.loads((ROOT/'results/phase15_macos_development/fit_execution.json').read_bytes())
                old_b=json.loads((ROOT/'results/phase15_bprime_recovery/continuation_execution.json').read_bytes())
                spent=sum(v['parent_cpu_seconds']+v['worker_cpu_seconds'] for v in (old_a,old_b))
                outcomes=Counter(payload['outcome'] for _,payload in rows)
                while True:
                    if spent+process_time()-cpu+worker_cpu>30*3600: raise bp.IntegrityError('Cumulative CPU allowance exhausted')
                    entry=coordinator.execute_one(Builder(backend));drain('candidate:'+str(coordinator.sequence-1))
                    if entry is None:
                        exclusive(OUT/'fit_completion.json',coordinator.completion());status='COMPLETE_PENDING_INDEPENDENT_AND_VISUAL_REVIEW';break
                    payload=json.loads(gzip.decompress((store.root/entry['path']).read_bytes()))['payload'];outcomes[payload['outcome']]+=1
                    if coordinator.stopped: status='TERMINAL_STOP';break
                    if coordinator.sequence%100==0:
                        size=sum(p.stat().st_size for base in (OLD,RAW) for p in base.rglob('*') if p.is_file())
                        if size>15_000_000_000: raise bp.IntegrityError('Cumulative storage allowance exhausted')
    except BaseException as error:
        failure=repr(error);status='STOPPED_REVIEW_REQUIRED'
    finally:
        try: drain('exit')
        finally: backend.close()
        result=dict(status=status,mode=mode,binding_sha256=binding.approved_sha256,
            prefix_sha256=json.loads(binding.manifest_bytes)['continuation_prefix']['sha256'],prefix_records=418,
            registered_candidates_generated=0 if verify else (coordinator.sequence-418 if coordinator else 0),
            elapsed_seconds=perf_counter()-started,parent_cpu_seconds=process_time()-cpu,
            worker_cpu_seconds=worker_cpu,native_calls=calls,failure=failure)
        if coordinator:
            result.update(total_fit_records=coordinator.sequence,current_credits=dict(coordinator.index.credits('fit')),
                          continuation_run_id=store.run_id)
        if verify and status=='PASS_NO_REGISTERED_GENERATION':
            result.update(next_job=next_job,cursors=cursors,credits=counts,all_418_preserved=True)
        exclusive(output,result)
    if status not in ('PASS_NO_REGISTERED_GENERATION','COMPLETE_PENDING_INDEPENDENT_AND_VISUAL_REVIEW'): sys.exit(2)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=['verify','execute'])
    run(parser.parse_args().mode)
