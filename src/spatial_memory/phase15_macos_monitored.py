"""Option B macOS C3 backend: measured peak acceptance, never a hard RSS cap."""
import ctypes
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import selectors
import subprocess
import sys
from time import perf_counter
from .phase15_nauty import Backend as Base,BackendFailure,NAMESPACE,LIMIT
from .phase15_topology import serialize_order

ROOT=Path(__file__).resolve().parents[2]
PROFILE='phase1.5-v0.4-MACOS-RSS-B1'
INTERVAL=.010


class Usage(ctypes.Structure):
    _fields_=[('uuid',ctypes.c_ubyte*16),('values',ctypes.c_uint64*18)]


def resident_bytes(pid):
    lib=ctypes.CDLL('/usr/lib/libproc.dylib',use_errno=True)
    lib.proc_pid_rusage.argtypes=[ctypes.c_int,ctypes.c_int,ctypes.c_void_p]
    info=Usage()
    if lib.proc_pid_rusage(pid,2,ctypes.byref(info))!=0:
        raise BackendFailure('resource_evidence: parent libproc sampling failed')
    value=int(info.values[6])
    if value<=0:raise BackendFailure('resource_evidence: invalid parent RSS')
    return value


class MonitoredBackend(Base):
    def __init__(self,*,pin_path=ROOT/'configs/phase15_macos_option_b.json'):
        super().__init__()
        if sys.platform!='darwin' or platform.machine()!='arm64':raise BackendFailure('macOS ARM64 required')
        self.pin_path=Path(pin_path).resolve();raw=self.pin_path.read_bytes()
        self.pin_sha=hashlib.sha256(raw).hexdigest();self.pin=json.loads(raw)
        if self.pin['profile']!=PROFILE or self.pin['namespace']!=NAMESPACE:raise BackendFailure('integrity: wrong resource profile')
        if self.pin['threshold_bytes']!=LIMIT or self.pin['monitoring_interval_seconds']!=INTERVAL:
            raise BackendFailure('integrity: changed resource policy')
        self.events=[];self.teardown=None
        self._verify()

    def _verify(self):
        if hashlib.sha256(self.pin_path.read_bytes()).hexdigest()!=self.pin_sha:raise BackendFailure('integrity: changed pin')
        for p,h in self.pin['artifact_sha256'].items():
            path=(ROOT/p).resolve()
            if not path.is_relative_to(ROOT) or hashlib.sha256(path.read_bytes()).hexdigest()!=h:
                raise BackendFailure('integrity: changed source/native artifact '+p)

    def _start(self):
        self._verify()
        self.process=subprocess.Popen([sys.executable,'-I',str(Path(__file__).with_name('phase15_macos_monitored_worker.py')),
            str(self.pin_path),self.pin_sha],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        os.set_blocking(self.process.stdin.fileno(),False);os.set_blocking(self.process.stdout.fileno(),False)

    def close(self):
        if self.process is None:return
        p=self.process;started=perf_counter()
        try:
            if p.returncode is None:
                try:p.kill()
                except ProcessLookupError:pass
                try:
                    _,status,usage=os.wait4(p.pid,0)
                    p.returncode=os.waitstatus_to_exitcode(status)
                    self.teardown=dict(exitcode=p.returncode,peak_rss_bytes=int(usage.ru_maxrss),
                                       seconds=perf_counter()-started,reaped=True)
                except ChildProcessError:
                    self.teardown=dict(exitcode=p.wait(),peak_rss_bytes=None,seconds=perf_counter()-started,reaped=True)
            else:self.teardown=dict(exitcode=p.returncode,peak_rss_bytes=None,reaped=True,seconds=perf_counter()-started)
        finally:
            if self.teardown is not None:
                self.teardown['stderr']=p.stderr.read(65536).decode(errors='replace')
            for stream in (p.stdin,p.stdout,p.stderr):stream.close()
            self.process=None

    def exact_certificate(self,graph,*,statistics=None):
        start=perf_counter();deadline=start+5;self.counter+=1;samples=[];output=bytearray();event=dict(id=self.counter,profile=PROFILE,vertices=graph.n)
        def sample():
            value=resident_bytes(self.process.pid);samples.append(dict(offset_seconds=perf_counter()-start,measured_at=perf_counter(),rss_bytes=value))
            if value>LIMIT:raise BackendFailure('resource_excess: parent observed RSS above threshold')
        try:
            if self.process is None:self._start()
            sample();request=json.dumps(dict(id=self.counter,matrix=graph.matrix)).encode()+b'\n'
            sent=0;output=bytearray();next_sample=perf_counter()+INTERVAL
            with selectors.DefaultSelector() as selector:
                selector.register(self.process.stdin,selectors.EVENT_WRITE);selector.register(self.process.stdout,selectors.EVENT_READ)
                while True:
                    now=perf_counter()
                    if now>=deadline:raise BackendFailure('timeout: five-second parent deadline')
                    if now>=next_sample:sample();next_sample=perf_counter()+INTERVAL
                    ready=selector.select(max(0,min(deadline,next_sample)-perf_counter()))
                    done=False
                    for key,_ in ready:
                        if key.fileobj is self.process.stdin:
                            sent+=os.write(self.process.stdin.fileno(),request[sent:])
                            if sent==len(request):selector.unregister(self.process.stdin)
                        else:
                            chunk=os.read(self.process.stdout.fileno(),65536)
                            if not chunk:raise BackendFailure('worker_crash: incomplete response')
                            output.extend(chunk)
                            if len(output)>1048576:raise BackendFailure('resource_evidence: oversized response')
                            if b'\n' in output:done=True;break
                    if done:break
            sample()
            if output.count(b'\n')!=1 or not output.endswith(b'\n'):raise BackendFailure('resource_evidence: framing')
            reply=json.loads(output)
            event['reply']=reply
            if reply.get('error'):raise BackendFailure('worker_error: '+reply['error'])
            order=reply['order'];peak=reply['peak_rss_bytes']
            if (reply['id']!=self.counter or reply['namespace']!=NAMESPACE or reply['profile']!=PROFILE
                or reply['pin_sha256']!=self.pin_sha or reply['rss_unit']!='bytes'
                or type(peak) is not int or peak<=0
                or any(type(v) is not int for v in order) or sorted(order)!=list(range(graph.n))):
                raise BackendFailure('resource_evidence: invalid identity/permutation/peak')
            if peak>LIMIT:raise BackendFailure('resource_excess: worker lifetime peak above threshold')
            if any(type(reply[k]) not in (int,float) or not math.isfinite(reply[k]) or reply[k]<0 for k in ('cpu_seconds','worker_seconds')):
                raise BackendFailure('resource_evidence: invalid timing values')
            measured=reply['peak_measured_at']
            if type(measured) not in (int,float) or not start<=measured<=perf_counter():raise BackendFailure('resource_evidence: invalid peak timestamp')
            if any(s['rss_bytes']>peak for s in samples if s['measured_at']<=measured):raise BackendFailure('resource_evidence: parent RSS exceeds subsequent worker lifetime peak')
            if perf_counter()>deadline:raise BackendFailure('timeout: late response')
            event.update(status='certified',seconds=perf_counter()-start,cpu_seconds=reply['cpu_seconds'],
                worker_seconds=reply['worker_seconds'],peak_rss_bytes=peak,peak_rss_kib=peak/1024,
                native_search_nodes=None,parent_samples=samples,hard_memory_enforced=False,
                monitoring_interval_seconds=INTERVAL)
            if statistics is not None:statistics.update(event)
            self.events.append(event)
            return (NAMESPACE,*serialize_order(graph,order))
        except Exception as error:
            event.update(status='failed',seconds=perf_counter()-start,error=str(error),parent_samples=samples,
                         response_bytes=bytes(output).decode(errors='replace'))
            self.close();event['teardown']=self.teardown;self.events.append(event)
            if statistics is not None:statistics.update(event)
            if isinstance(error,BackendFailure):raise
            raise BackendFailure('resource_evidence: '+type(error).__name__) from error
