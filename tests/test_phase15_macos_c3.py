"""Native ARM64 compatibility/resource fixtures only; no world constructors."""
import ast
import hashlib
import json
import os
from pathlib import Path
import resource
import selectors
import subprocess
import sys
from time import perf_counter
from types import SimpleNamespace
import pytest
from spatial_memory import phase15_topology as top, phase15_exact_bnb as bnb
from spatial_memory.phase15_nauty import BackendFailure
from spatial_memory.phase15_nauty_macos import MacBackend, VALIDATION_NAMESPACE, ROOT

pytestmark=pytest.mark.skipif(sys.platform!='darwin' or __import__('platform').machine()!='arm64',reason='Native macOS ARM64 validation only')
EVIDENCE={}


@pytest.fixture(scope='session',autouse=True)
def save_evidence(tmp_path_factory):
    yield
    requested=os.environ.get('PHASE15_MACOS_TEST_REPORT')
    path=Path(requested) if requested else tmp_path_factory.mktemp('macos-c3-evidence')/'synthetic_verification.json'
    if path.exists():raise RuntimeError('Preserve existing macOS validation evidence')
    path.write_text(json.dumps(EVIDENCE,indent=2,sort_keys=True)+'\n')


def test_default_backend_remains_blocked():
    with pytest.raises(BackendFailure,match='BLOCKED'):MacBackend()


def test_existing_1215_fixtures_independent_literal_oracle():
    # Execute only the immutable mathematical fixture functions, not the old
    # module imports (which select a Linux binary) or any audit/replay entrypoint.
    source=ROOT/'scripts/benchmark_phase1_5b01.py';tree=ast.parse(source.read_text())
    selected=ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef)
                             and n.name in ('reference','variants','correctness')],type_ignores=[])
    backend=MacBackend(validation_only=True)
    try:
        import itertools,random
        context=dict(old=top,bnb=bnb,permutations=itertools.permutations,
                     combinations=itertools.combinations,random=random,
                     proposal=SimpleNamespace(certificate=lambda g:backend.exact_certificate(g)[1:]))
        exec(compile(selected,str(source),'exec'),context)
        result=context['correctness']()
        assert result['total_graphs']==1215 and result['relation_bijection']
        previous=json.loads((ROOT/'results/phase1_5b02/preflight.json').read_text())['correctness']
        assert result['distinct_reference_classes']==previous['distinct_reference_classes']
        assert result['byte_mismatches']==previous['byte_mismatches']
        EVIDENCE['synthetic_correctness']=dict(result,fixture_source_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
    finally:backend.close()


def test_fresh_worker_relabeling_and_resource_units():
    graph=top.graph_from_edges(5,[(0,0),(0,1),(0,1),(1,2),(2,3),(3,4)])
    keys=[];measurements=[]
    for order in ([0,1,2,3,4],[4,2,0,3,1],[1,2,3,4,0]):
        backend=MacBackend(validation_only=True)
        try:
            stats={};keys.append(backend.exact_certificate(top.induced(graph,order),statistics=stats))
            assert keys[-1][0]==VALIDATION_NAMESPACE and stats['hard_memory_enforced'] is False
            measurements.append(stats)
        finally:backend.close()
    assert len(set(keys))==1
    EVIDENCE['fresh_process']=dict(checks=3,measurements=measurements)


@pytest.mark.parametrize('code,expected',[
 ("import ctypes;ctypes.CDLL(None).sleep(30)",'timeout'),
 ("import os;os._exit(7)",'worker_crash'),
 ("print('bad json',flush=True)",'invalid_output'),
 ("import sys,time;sys.stdout.write('{');sys.stdout.flush();time.sleep(30)",'timeout'),
 ("print('{\"error\":\"memory_exhaustion\"}',flush=True)",'memory_exhaustion'),
 ("print('{\"id\":1,\"order\":[0],\"namespace\":\"wrong\"}',flush=True)",'invalid_output'),
])
def test_parent_native_failures_are_killed_and_reaped(monkeypatch,code,expected):
    backend=MacBackend(validation_only=True);processes=[]
    def start():
        backend.process=subprocess.Popen([sys.executable,'-I','-c',code],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        os.set_blocking(backend.process.stdin.fileno(),False);os.set_blocking(backend.process.stdout.fileno(),False)
        processes.append(backend.process)
    monkeypatch.setattr(backend,'_start',start)
    started=perf_counter()
    with pytest.raises(BackendFailure,match=expected):backend.exact_certificate(top.graph_from_edges(1,[]))
    elapsed=perf_counter()-started
    assert elapsed<7 and processes[0].poll() is not None and backend.process is None
    EVIDENCE.setdefault('failure_probes',[]).append(dict(code=code,expected=expected,
        elapsed_seconds=elapsed,exitcode=processes[0].returncode,reaped=True,
        decision_deadline_seconds=5,teardown_latency_separate=True))


@pytest.mark.parametrize('mode',['python-touched','native-touched','mmap-touched'])
def test_controlled_memory_probe_reports_real_limit_failure(mode):
    # At most 64 MiB explicitly allocated, in a disposable child. Failure to
    # establish the hard limit is BLOCKED, not disguised as a successful cap.
    code=r'''
import ctypes,json,mmap,os,resource,sys
limit=536870912
result=dict(mode=sys.argv[1],rss_unit='bytes',limit_bytes=limit,
            initial_limits=resource.getrlimit(resource.RLIMIT_AS),
            rss_before=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
try:
 resource.setrlimit(resource.RLIMIT_AS,(limit,limit))
 result['hard_limit_set']=True
except (OSError,ValueError) as error:
 result.update(hard_limit_set=False,error=repr(error))
result['limits_after']=resource.getrlimit(resource.RLIMIT_AS)
size=64*1024*1024
try:
 if sys.argv[1]=='python-touched':
  block=bytearray(size)
  for i in range(0,size,4096):block[i]=1
 elif sys.argv[1]=='native-touched':
  libc=ctypes.CDLL(None);libc.malloc.argtypes=[ctypes.c_size_t];libc.malloc.restype=ctypes.c_void_p
  ptr=libc.malloc(size)
  if not ptr:raise MemoryError('native allocation refused')
  ctypes.memset(ptr,1,size)
 else:
  block=mmap.mmap(-1,size)
  for i in range(0,size,4096):block[i]=1
 result['allocated_touched_bytes']=size
 result['rss_after']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
 class MachInfo(ctypes.Structure):
  _fields_=[('virtual_size',ctypes.c_uint64),('resident_size',ctypes.c_uint64),
            ('resident_size_max',ctypes.c_uint64),('user_seconds',ctypes.c_int),
            ('user_microseconds',ctypes.c_int),('system_seconds',ctypes.c_int),
            ('system_microseconds',ctypes.c_int),('policy',ctypes.c_int),('suspend_count',ctypes.c_int)]
 libc=ctypes.CDLL(None);info=MachInfo();count=ctypes.c_uint(ctypes.sizeof(info)//ctypes.sizeof(ctypes.c_uint))
 libc.task_info.argtypes=[ctypes.c_uint,ctypes.c_uint,ctypes.c_void_p,ctypes.POINTER(ctypes.c_uint)]
 task=ctypes.c_uint.in_dll(libc,'mach_task_self_').value
 status=libc.task_info(task,20,ctypes.byref(info),ctypes.byref(count))
 if status!=0:raise RuntimeError('Mach task_info failed: '+str(status))
 result['mach_resident_bytes']=info.resident_size
 result['mach_resident_peak_bytes']=info.resident_size_max
except (MemoryError,OSError) as error:
 result['allocation_error']=repr(error)
print(json.dumps(result))
'''
    completed=subprocess.run([sys.executable,'-I','-c',code,mode],capture_output=True,text=True,timeout=15,check=True)
    result=json.loads(completed.stdout)
    # This migration records the target-host failure. A different result needs
    # a fresh enforcement review rather than automatically claiming equivalence.
    assert result['hard_limit_set'] is False
    assert result['allocated_touched_bytes']==64*1024*1024
    assert result['rss_after']-result['rss_before']>32*1024*1024
    assert 0.5<result['rss_after']/result['mach_resident_peak_bytes']<2
    result['enforcement_gate']='BLOCKED: unable to establish hard limit; controlled allocations are diagnostics only'
    EVIDENCE.setdefault('memory_probes',[]).append(result)


def test_worker_encoding_is_unchanged_approved_ast():
    original=ast.parse((ROOT/'src/spatial_memory/phase15_nauty_worker.py').read_text())
    migrated=ast.parse((ROOT/'src/spatial_memory/phase15_nauty_macos_worker.py').read_text())
    a=next(n for n in original.body if isinstance(n,ast.FunctionDef) and n.name=='canonical')
    b=next(n for n in migrated.body if isinstance(n,ast.FunctionDef) and n.name=='canonical')
    assert ast.dump(ast.Module(body=a.body,type_ignores=[]),include_attributes=False)==ast.dump(ast.Module(body=b.body,type_ignores=[]),include_attributes=False)



def test_changed_pin_or_dependency_digest_refuses_before_worker(tmp_path):
    pin=json.loads((ROOT/'configs/phase15_nauty_macos_validation.json').read_text())
    pin['artifact_sha256'][next(iter(pin['artifact_sha256']))]='0'*64
    path=tmp_path/'changed-pin.json';path.write_text(json.dumps(pin))
    with pytest.raises(BackendFailure,match='mismatch'):
        MacBackend(validation_only=True,pin_path=path)


def test_candidate_namespace_cannot_enter_frozen_production_index():
    from spatial_memory.phase15_bprime_protocol import AdmissionIndex,Record,Lineage
    from spatial_memory.phase15_bprime import IntegrityError
    candidate=Record('validation-only','fit','BP',(VALIDATION_NAMESPACE,1,0),
                     frozenset({(VALIDATION_NAMESPACE,1,0)}),(1,1,'1'),Lineage({'validation-root'}))
    with pytest.raises(IntegrityError,match='profile conflict'):
        AdmissionIndex().classify(candidate)
