"""Prepare/verify an immutable-prefix continuation, then explicitly execute it.

The original store is read-only. Verification forbids RNG/world construction.
Execution requires its verification report to be committed; no assessment stage
or alternate seed/partition/root is accepted. The scientific fit order continues.
"""
import argparse
from collections import Counter
import gzip,hashlib,json,os,platform,subprocess,sys
from pathlib import Path
from time import perf_counter,process_time
from spatial_memory import phase15_bprime as bp
from spatial_memory.phase15_bprime_access import StageBinding
from spatial_memory.phase15_bprime_protocol import canonical_bytes,digest,validate_inventory
from spatial_memory.phase15_bprime_prefix import ReadOnlyPrefix
from spatial_memory.phase15_bprime_store import Checkpoints
from spatial_memory.phase15_bprime_coordinator import Coordinator
from spatial_memory.phase15_bprime_development import Builder
from spatial_memory.phase15_macos_monitored import MonitoredBackend
ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT/'results/raw/phase15_macos_development'
RAW=ROOT/'results/raw/phase15_bprime_fit_recovery_1'
OUT=ROOT/'results/phase15_bprime_recovery'
BIND=ROOT/'configs/phase15_macos_bindings/fit-recovery-1.json'
STOP='5ed258e6bbdc3a0bfa7cf45e3d2c5a1548fc24f2'
SOURCE='2dcadbef876195b43bab6d3ef0da84151c498348'


def sha(raw):return hashlib.sha256(raw).hexdigest()

def exclusive(path,value):
 with path.open('xb') as f:f.write(canonical_bytes(value));f.flush();os.fsync(f.fileno())

def committed(path,commit='HEAD'):
 data=path.read_bytes();r=subprocess.run(['git','show',commit+':'+str(path.relative_to(ROOT))],cwd=ROOT,capture_output=True,check=True)
 if r.stdout!=data:raise bp.IntegrityError('Uncommitted/changed verification evidence: '+str(path))
 return data


def prepare():
 OUT.mkdir(exist_ok=True)
 prior=ROOT/'results/phase15_macos_development'
 inventory=json.loads(gzip.decompress(committed(prior/'development_storage_manifest.json.gz',STOP)))
 integrity=json.loads(committed(prior/'fit_post_stop_integrity.json',STOP))
 if (integrity['records'],integrity['pending'],integrity['staged'])!=(313,0,0):raise bp.IntegrityError('Original prefix is not complete/checkpointed')
 files=[dict(e,path=e['path'][4:]) for e in inventory['files'] if e['path'].startswith('fit/')]
 if len(files)!=628:raise bp.IntegrityError('Original checkpoint/receipt coverage differs')
 for e in files:
  data=(OLD/'fit'/e['path']).read_bytes()
  if len(data)!=e['bytes'] or sha(data)!=e['sha256']:raise bp.IntegrityError('Original prefix changed')
 prefix=dict(schema=1,partition='fit',root=str((OLD/'fit').relative_to(ROOT)),source_commit=SOURCE,
    original_binding='configs/phase15_macos_bindings/fit.json',original_binding_sha256=integrity['binding_sha256'],
    run_id=integrity['run_id'],records=313,files=files)
 exclusive(OUT/'prefix.json',prefix)
 subprocess.run([sys.executable,str(ROOT/'scripts/freeze_phase15_macos_binding.py'),'--name','fit-recovery-1','--partition','fit','--references',str(OLD/'references'),'--store',str((RAW/'store').relative_to(ROOT))],check=True)
 value=json.loads(BIND.read_bytes());value['readonly_prefix_root']=prefix['root']
 value['continuation_prefix']=dict(path=str((OUT/'prefix.json').relative_to(ROOT)),sha256=digest(prefix))
 for path in (OUT/'prefix.json',ROOT/prefix['original_binding'],prior/'fit_execution.json',prior/'development_storage_manifest.json.gz',prior/'fit_post_stop_integrity.json'):
  value['files']['references'][str(path.relative_to(ROOT))]=sha(path.read_bytes())
 BIND.write_bytes(canonical_bytes(value))
 registry_path=ROOT/'configs/phase15_macos_development_registry.json';registry=json.loads(registry_path.read_bytes());registry['manifests'][str(BIND.relative_to(ROOT))]=sha(BIND.read_bytes())
 temporary=registry_path.with_suffix('.recovery.tmp')
 with temporary.open('xb') as f:f.write(canonical_bytes(registry));f.flush();os.fsync(f.fileno())
 os.replace(temporary,registry_path)
 print(json.dumps(dict(status='PREPARED_REQUIRES_COMMIT',prefix_records=313,prefix_sha256=digest(prefix),binding_sha256=sha(BIND.read_bytes()))),flush=True)


def run(mode):
 verify=mode=='verify';output=OUT/('continuation_verification.json' if verify else 'continuation_execution.json')
 if output.exists():raise bp.IntegrityError('Preserve existing continuation evidence; no automatic retry')
 if not verify:
  proof=json.loads(committed(OUT/'continuation_verification.json'))
  if proof['status']!='PASS_NO_REGISTERED_GENERATION' or proof['binding_sha256']!=sha(BIND.read_bytes()):raise bp.IntegrityError('Continuation not verified under these exact commitments')
 else:
  def denied(*a,**k):raise bp.IntegrityError('Registered RNG/world construction prohibited during verification')
  bp.Stream.__init__=denied;bp.legacy.Stream.__init__=denied;bp.geometry=denied;bp.legacy.geometry=denied
 started=perf_counter();cpu=process_time();binding=StageBinding.load(BIND)
 meta=json.loads(binding.manifest_bytes)['runtime']
 if meta['python']!=sys.version or meta['executable_sha256']!=sha(Path(sys.executable).resolve().read_bytes()) or meta['machine']!=platform.machine():raise bp.IntegrityError('Runtime commitment changed')
 backend=MonitoredBackend();RAW.mkdir(exist_ok=True);resources=RAW/(mode+'-resources');resources.mkdir(exist_ok=False)
 events_cpu=0;calls=0;batch=0;coordinator=None;status='STARTING';failure=None
 def drain(label):
  nonlocal events_cpu,calls,batch
  if not backend.events:return
  events=backend.events;backend.events=[];calls+=len(events);events_cpu+=sum(e.get('cpu_seconds',0) for e in events)
  data=gzip.compress(canonical_bytes(dict(label=label,events=events)),mtime=0)
  with (resources/f'{batch:08d}.json.gz').open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
  batch+=1
 try:
  inv=json.loads((OLD/'references/inventory.json').read_bytes());ledger=json.loads((OLD/'references/ledger.json').read_bytes());seal=json.loads((ROOT/'results/phase15_macos_development/reference_seal.json').read_bytes())
  references=validate_inventory(inv,ledger,OLD/'references',expected_digest=seal['inventory_sha256'],expected_ledger_digest=seal['ledger_sha256'],backend=backend,binding=binding)
  drain('reference-verification');print('References verified; checking unchanged original prefix',flush=True)
  prefix=ReadOnlyPrefix.load(binding,backend=backend);drain('original-prefix-verification')
  store=Checkpoints(RAW/'store',partition='fit',binding=binding,backend=backend)
  with store.writer():
   coordinator=Coordinator(store,references,backend=backend,prefix=prefix)
   rows=coordinator.restore();drain('same-fit-state-reconstruction')
   if verify:
    if len(rows)!=313 or store.scan():raise bp.IntegrityError('Verification requires the exact original 313-record prefix')
    cursors={m:coordinator.cursors.get(('fit',m),0) for m in bp.MECHANISMS};counts=dict(coordinator.index.credits('fit'))
    next_job=coordinator._job()
    if (coordinator.sequence,cursors,counts,next_job)!=(313,dict(R=24,BP=14,V=263,M=12),dict(R=12,BP=12,M=12),dict(identity=bp.Identity('fit','V',80020263).root,partition='fit',mechanism='V',index=263,sequence=313)):
     raise bp.IntegrityError('Same-fit continuation state differs from saved prefix')
    status='PASS_NO_REGISTERED_GENERATION'
   else:
    old_cost=json.loads((ROOT/'results/phase15_macos_development/fit_execution.json').read_bytes());spent=old_cost['parent_cpu_seconds']+old_cost['worker_cpu_seconds']
    outcomes=Counter(v['outcome'] for _,v in rows)
    while True:
     if spent+process_time()-cpu+events_cpu>30*3600:raise bp.IntegrityError('Cumulative development CPU allowance exhausted')
     entry=coordinator.execute_one(Builder(backend));drain('candidate:'+str(coordinator.sequence-1))
     if entry is None:
      completion=coordinator.completion();drain('completion-validation');exclusive(OUT/'fit_completion.json',completion);status='COMPLETE_PENDING_INDEPENDENT_AND_VISUAL_REVIEW';break
     value=json.loads(gzip.decompress((store.root/entry['path']).read_bytes()))['payload'];outcomes[value['outcome']]+=1
     if coordinator.sequence%100==0:print(json.dumps(dict(attempts=coordinator.sequence,credits=dict(coordinator.index.credits('fit')),outcomes=dict(outcomes))),flush=True)
     if coordinator.stopped:status='TERMINAL_STOP';break
     if coordinator.sequence%100==0 and sum(p.stat().st_size for root in (OLD,RAW) for p in root.rglob('*') if p.is_file())>15_000_000_000:raise bp.IntegrityError('Cumulative development storage allowance exhausted')
 except BaseException as error:
  failure=repr(error);status='STOPPED_REVIEW_REQUIRED';print(json.dumps(dict(status=status,failure=failure)),flush=True)
 finally:
  drain('exit');backend.close()
  result=dict(status=status,mode=mode,binding_sha256=binding.approved_sha256,original_run_id=sha((OLD/'fit/run.json').read_bytes()),prefix_sha256=json.loads(binding.manifest_bytes)['continuation_prefix']['sha256'],prefix_records=313,
    original_store=str(OLD/'fit'),continuation_store=str(RAW/'store'),registered_candidates_generated=0 if verify else (coordinator.sequence-313 if coordinator else 0),
    elapsed_seconds=perf_counter()-started,parent_cpu_seconds=process_time()-cpu,worker_cpu_seconds=events_cpu,native_calls=calls,failure=failure)
  if coordinator is not None:
   result.update(total_fit_records=coordinator.sequence,current_credits=dict(coordinator.index.credits('fit')),continuation_run_id=coordinator.store.run_id)
  if verify and status=='PASS_NO_REGISTERED_GENERATION':result.update(next_job=next_job,original_cursors=cursors,original_files_preserved=True)
  exclusive(output,result);print(json.dumps(result),flush=True)
 if status not in ('PASS_NO_REGISTERED_GENERATION','COMPLETE_PENDING_INDEPENDENT_AND_VISUAL_REVIEW'):sys.exit(2)

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=['prepare','verify','execute']);args=parser.parse_args()
 if args.mode=='prepare':prepare()
 else:run(args.mode)
