"""Authorized frozen development artifacts only. No policies or navigation imports.

Requires committed stage bindings, a committed seal, and independently reviewed
preceding partitions. Interrupted uncheckpointed attempts cannot be replayed.
"""
import argparse
from collections import Counter
from contextlib import ExitStack
import gzip,hashlib,json,os,platform,subprocess,sys
from pathlib import Path
from time import perf_counter,process_time
from spatial_memory import phase15_bprime as bp
from spatial_memory.phase15_macos_monitored import MonitoredBackend
from spatial_memory.phase15_bprime_access import StageBinding
from spatial_memory.phase15_bprime_protocol import validate_inventory,digest,canonical_bytes
from spatial_memory.phase15_bprime_store import Checkpoints
from spatial_memory.phase15_bprime_coordinator import Coordinator
from spatial_memory.phase15_bprime_development import Builder
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/phase15_macos_development'
RAW=ROOT/'results/raw/phase15_macos_development'


def committed(path):
 raw=path.read_bytes();saved=subprocess.run(['git','show','HEAD:'+str(path.relative_to(ROOT))],cwd=ROOT,capture_output=True,check=True).stdout
 if raw!=saved:raise bp.IntegrityError('Required review is not committed')
 return json.loads(raw)


def exclusive(path,value):
 with path.open('xb') as f:f.write(canonical_bytes(value));f.flush();os.fsync(f.fileno())


def main():
 p=argparse.ArgumentParser();p.add_argument('--partition',choices=list(bp.PARTITIONS),required=True);a=p.parse_args()
 start=perf_counter();cpu=process_time();seal=committed(OUT/'reference_seal.json')
 if seal['included_identities']!=2368 or seal['rejected_nonreferences']!=2276:raise bp.IntegrityError('Reference scope changed')
 ref=RAW/'references';inv=json.loads((ref/'inventory.json').read_bytes());ledger=json.loads((ref/'ledger.json').read_bytes())
 if digest(inv)!=seal['inventory_sha256'] or digest(ledger)!=seal['ledger_sha256']:raise bp.IntegrityError('Reference seal changed')
 backend=MonitoredBackend();journal=RAW/'backend_resources'/a.partition;journal.mkdir(parents=True,exist_ok=True)
 ordinal=len(list(journal.glob('*.json.gz')));native_cpu=0;native_calls=0
 def drain(label):
  nonlocal ordinal,native_cpu,native_calls
  if not backend.events:return
  events=backend.events;backend.events=[]
  native_cpu+=sum(e.get('cpu_seconds',0) for e in events);native_calls+=len(events)
  body=dict(partition=a.partition,label=label,events=events)
  data=gzip.compress(canonical_bytes(body),mtime=0)
  path=journal/f'{ordinal:08d}.json.gz'
  with path.open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
  ordinal+=1
 last=None;counts=Counter();outcomes=Counter();status='STARTING';coordinator=None
 report_path=OUT/f'{a.partition}_execution.json'
 if report_path.exists():raise bp.IntegrityError('Preserve existing completed/stopped execution report')
 try:
  binding=StageBinding.load((ROOT/f'configs/phase15_macos_bindings/{a.partition}.json').resolve())
  runtime=json.loads(binding.manifest_bytes)['runtime']
  if (runtime['python']!=sys.version or runtime['executable_sha256']!=hashlib.sha256(Path(sys.executable).resolve().read_bytes()).hexdigest()
      or runtime['machine']!=platform.machine() or runtime['system']!=platform.system()):raise bp.IntegrityError('Unpinned execution runtime')
  references=validate_inventory(inv,ledger,ref,expected_digest=seal['inventory_sha256'],expected_ledger_digest=seal['ledger_sha256'],backend=backend,binding=binding)
  drain('reference-validation')
  with ExitStack() as stack:
   previous=[]
   for stage in list(bp.PARTITIONS)[:list(bp.PARTITIONS).index(a.partition)]:
    review=committed(OUT/f'{stage}_population_review.json')
    if review.get('status')!='PASS':raise bp.IntegrityError('Previous population review not passed')
    bound=StageBinding.load((ROOT/f'configs/phase15_macos_bindings/{stage}.json').resolve())
    store=Checkpoints(RAW/stage,partition=stage,binding=bound,backend=backend)
    stack.enter_context(store.writer());earlier=Coordinator(store,references,backend=backend,previous=tuple(previous));earlier.restore();earlier.completion();previous.append(earlier)
   store=Checkpoints(RAW/a.partition,partition=a.partition,binding=binding,backend=backend)
   stack.enter_context(store.writer());coordinator=Coordinator(store,references,backend=backend,previous=tuple(previous));rows=coordinator.restore()
   for _,record in rows:outcomes[record['outcome']]+=1
   drain('deterministic-restoration')
   while True:
    if process_time()-cpu+native_cpu>30*3600:raise bp.IntegrityError('Development CPU allowance exhausted')
    entry=coordinator.execute_one(Builder(backend));drain('candidate:'+str(coordinator.sequence-1))
    if entry is None:
     completion=coordinator.completion();drain('completion-validation')
     exclusive(OUT/f'{a.partition}_completion.json',completion);status='COMPLETE_PENDING_INDEPENDENT_AND_VISUAL_REVIEW';break
    last=entry
    body=json.loads(gzip.decompress((store.root/entry['path']).read_bytes()))['payload'];outcomes[body['outcome']]+=1
    counts=coordinator.index.credits(a.partition)
    if coordinator.sequence%100==0:
     print(json.dumps(dict(partition=a.partition,attempts=coordinator.sequence,counts=dict(counts),outcomes=dict(outcomes))),flush=True)
    if coordinator.stopped:status='TERMINAL_SCIENTIFIC_OR_IMPLEMENTATION_STOP';break
    if coordinator.sequence%100==0 and sum(f.stat().st_size for f in RAW.rglob('*') if f.is_file())>15_000_000_000:raise bp.IntegrityError('Development storage allowance exhausted')
 except BaseException as error:
  status='STOPPED_REVIEW_REQUIRED';failure=repr(error)
  if 'candidate allowance exhausted' in str(error):status='FROZEN_CANDIDATE_ALLOWANCE_EXHAUSTED'
  print(json.dumps(dict(status=status,error=failure)),flush=True)
 finally:
  drain('exit');backend.close()
  # No overwrite, retries, seed substitutions, or automatic continuation after stop.
  if coordinator is not None:
   counts=coordinator.index.credits(a.partition)
   report=dict(status=status,partition=a.partition,attempts=coordinator.sequence,counts=dict(counts),outcomes=dict(outcomes),
      candidate_indices={m:coordinator.cursors.get((a.partition,m),0) for m in bp.MECHANISMS},
      last_publication=last,reference_inventory_sha256=seal['inventory_sha256'],backend_pin_sha256=backend.pin_sha,
      elapsed_seconds=perf_counter()-start,parent_cpu_seconds=process_time()-cpu,worker_cpu_seconds=native_cpu,
      native_calls=native_calls,hard_memory_enforced=False,failure=locals().get('failure'),registered_navigation_executions=0,
      assessment_access=False,final_held_out_access=False)
   exclusive(report_path,report);print(json.dumps(report),flush=True)
 if status!='COMPLETE_PENDING_INDEPENDENT_AND_VISUAL_REVIEW':sys.exit(2)

if __name__=='__main__':main()
