"""Artifact-only production backend and Linux resource enforcement tests."""
import json
import hashlib
import os
from pathlib import Path
import subprocess
import sys
from time import perf_counter
import pytest
from spatial_memory import phase15_topology as top
from spatial_memory.phase15_nauty import Backend,BackendFailure,LIMIT,NAMESPACE


def test_fresh_process_stability_and_multigraph():
    g=top.graph_from_edges(5,[(0,0),(0,1),(0,1),(1,2),(2,3),(3,4)])
    keys=[]
    for _ in range(3):
        backend=Backend()
        try:
            stats={}; keys.append(backend.exact_certificate(g,statistics=stats))
            assert stats['peak_rss_kib']<LIMIT//1024
            assert backend.exact_certificate(top.induced(g,[4,2,0,3,1]))==keys[-1]
        finally: backend.close()
    assert len(set(keys))==1 and keys[0][0]==NAMESPACE


def test_kernel_memory_limit_in_real_worker_environment():
    # Same Python/exec environment and exact hard limit as production; touch pages.
    code='''import resource,json
resource.setrlimit(resource.RLIMIT_AS,(536870912,536870912))
blocks=[]
try:
 while True:
  b=bytearray(8*1024*1024)
  for i in range(0,len(b),4096): b[i]=1
  blocks.append(b)
except MemoryError:
 print(json.dumps(dict(exhausted=True,peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,limit=resource.getrlimit(resource.RLIMIT_AS),allocated=len(blocks)*8*1024*1024)))
'''
    result=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,timeout=15,check=True)
    body=json.loads(result.stdout)
    assert body['exhausted'] and 300*1024*1024<body['allocated']<LIMIT
    assert body['peak']<LIMIT//1024 and body['limit']==[LIMIT,LIMIT]
    evidence=Path(__file__).resolve().parents[1]/'results/runs/phase1_5b02_memory_probe.json'
    evidence.write_text(json.dumps(body,indent=2)+'\n')


@pytest.mark.parametrize('code,expected',[
    ("import ctypes;ctypes.CDLL(None).sleep(30)",'timeout'),
    ("import os;os._exit(7)",'worker_crash'),
    ("print('bad json',flush=True)",'invalid_output'),
    ("import sys,time;sys.stdout.write('{');sys.stdout.flush();time.sleep(30)",'timeout'),
    ("print('{\"error\":\"memory_exhaustion\"}',flush=True)",'memory_exhaustion')])
def test_parent_stops_failed_native_or_invalid_worker(monkeypatch,code,expected):
    backend=Backend(); processes=[]
    def start():
        backend.process=subprocess.Popen([sys.executable,'-c',code],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        os.set_blocking(backend.process.stdin.fileno(),False)
        os.set_blocking(backend.process.stdout.fileno(),False)
        processes.append(backend.process)
    monkeypatch.setattr(backend,'_start',start)
    begin=perf_counter()
    with pytest.raises(BackendFailure,match=expected): backend.exact_certificate(top.graph_from_edges(1,[]))
    assert perf_counter()-begin<7 and processes[0].poll() is not None and backend.process is None
    evidence=Path(__file__).resolve().parents[1]/'results/runs/phase1_5b02_failure_probes'
    evidence.mkdir(exist_ok=True)
    (evidence/(hashlib.sha256(code.encode()).hexdigest()+'.json')).write_text(json.dumps(dict(
        expected=expected,elapsed_seconds=perf_counter()-begin,exitcode=processes[0].returncode,
        process_reaped=True),indent=2)+'\n')
