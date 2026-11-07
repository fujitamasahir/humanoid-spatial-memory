"""Option B synthetic fixtures; no registered world construction."""
import ctypes
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from time import perf_counter
import pytest
from spatial_memory.phase15_macos_monitored import MonitoredBackend,PROFILE,LIMIT
from spatial_memory.phase15_nauty import BackendFailure
from spatial_memory.phase15_topology import graph_from_edges


def call():
    b=MonitoredBackend()
    try:return b.exact_certificate(graph_from_edges(2,[(0,1)])),b.events[-1]
    finally:b.close()


def test_normal_concurrent_workers():
    with ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(lambda _:call(),range(6)))
    assert len({r[0] for r in results})==1
    assert all(r[1]['parent_samples'] and r[1]['peak_rss_bytes']<=LIMIT for r in results)


@pytest.mark.parametrize('kind',['sustained','transient','crash','timeout','partial','malformed','missing'])
def test_failed_native_and_resource_workers_stop(monkeypatch,kind):
    b=MonitoredBackend()
    prefix="import ctypes,time,sys,json,resource; "
    code={
      'sustained':prefix+"c=ctypes.CDLL(None);c.malloc.restype=ctypes.c_void_p;p=c.malloc(560*1024*1024);ctypes.memset(p,1,560*1024*1024);time.sleep(30)",
      'transient':prefix+"c=ctypes.CDLL(None);c.malloc.restype=ctypes.c_void_p;c.free.argtypes=[ctypes.c_void_p];p=c.malloc(560*1024*1024);ctypes.memset(p,1,560*1024*1024);c.free(p);time.sleep(.02);print(json.dumps({'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}),flush=True)",
      'crash':"import os;os._exit(7)",
      'timeout':prefix+"ctypes.CDLL(None).sleep(30)",
      'partial':prefix+"sys.stdout.write('{');sys.stdout.flush();time.sleep(30)",
      'malformed':"print('bad json',flush=True)",
      'missing':"print('{}',flush=True)"}[kind]
    processes=[]
    def start():
        b.process=subprocess.Popen([sys.executable,'-I','-c',code],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        os.set_blocking(b.process.stdin.fileno(),False);os.set_blocking(b.process.stdout.fileno(),False);processes.append(b.process)
    monkeypatch.setattr(b,'_start',start)
    began=perf_counter()
    with pytest.raises(BackendFailure):b.exact_certificate(graph_from_edges(1,[]))
    assert perf_counter()-began<7 and b.process is None and processes[0].returncode is not None
    assert b.events[-1]['status']=='failed' and b.events[-1]['teardown']['reaped']
    if kind=='sustained':assert 'resource_excess' in b.events[-1]['error']


def test_missing_parent_measurement_fails_closed(monkeypatch):
    import spatial_memory.phase15_macos_monitored as module
    def fail(pid):raise BackendFailure('resource_evidence: synthetic missing sample')
    monkeypatch.setattr(module,'resident_bytes',fail)
    b=MonitoredBackend()
    with pytest.raises(BackendFailure,match='resource_evidence'):b.exact_certificate(graph_from_edges(1,[]))
    assert b.process is None


def test_transient_native_peak_detected_when_parent_samples_miss_it(monkeypatch):
    """A complete reply must reject the lifetime peak even after free()."""
    import spatial_memory.phase15_macos_monitored as module
    b=MonitoredBackend();processes=[]
    code="""
import ctypes,json,resource,sys,time
r=json.loads(sys.stdin.readline())
c=ctypes.CDLL(None);c.malloc.argtypes=[ctypes.c_size_t];c.malloc.restype=ctypes.c_void_p;c.free.argtypes=[ctypes.c_void_p]
p=c.malloc(560*1024*1024)
if not p:raise MemoryError('probe allocation refused')
ctypes.memset(p,1,560*1024*1024);c.free(p)
peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
print(json.dumps(dict(id=r['id'],order=[0],namespace='phase1.5-v0.3-CANON-1',
profile=PROFILE,pin_sha256=PIN,rss_unit='bytes',cpu_seconds=0,worker_seconds=0,
peak_rss_bytes=peak,peak_measured_at=time.perf_counter())),flush=True)
time.sleep(30)
""".replace('profile=PROFILE','profile='+repr(PROFILE)).replace('pin_sha256=PIN','pin_sha256='+repr(b.pin_sha))
    def start():
        b.process=subprocess.Popen([sys.executable,'-I','-c',code],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        os.set_blocking(b.process.stdin.fileno(),False);os.set_blocking(b.process.stdout.fileno(),False);processes.append(b.process)
    monkeypatch.setattr(b,'_start',start)
    monkeypatch.setattr(module,'resident_bytes',lambda _:1)
    with pytest.raises(BackendFailure,match='worker lifetime peak above threshold'):
        b.exact_certificate(graph_from_edges(1,[]))
    assert b.events[-1]['teardown']['reaped'] and processes[0].returncode is not None


def test_monitored_c3_1215_independent_literal_fixtures():
    import ast,itertools,random
    from types import SimpleNamespace
    from pathlib import Path
    from spatial_memory import phase15_topology as top,phase15_exact_bnb as bnb
    root=Path(__file__).resolve().parents[1];source=root/'scripts/benchmark_phase1_5b01.py'
    tree=ast.parse(source.read_text())
    selected=ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('reference','variants','correctness')],type_ignores=[])
    b=MonitoredBackend()
    try:
        context=dict(old=top,bnb=bnb,permutations=itertools.permutations,combinations=itertools.combinations,random=random,
            proposal=SimpleNamespace(certificate=lambda g:b.exact_certificate(g)[1:]))
        exec(compile(selected,str(source),'exec'),context)
        result=context['correctness']()
        previous=json.loads((root/'results/phase1_5b02/preflight.json').read_text())['correctness']
        assert result['total_graphs']==1215 and result['relation_bijection']
        assert result['distinct_reference_classes']==previous['distinct_reference_classes']
        assert result['byte_mismatches']==previous['byte_mismatches']
    finally:b.close()
