"""macOS ARM64 C3 compatibility adapter; production use remains blocked.

The temporary validation namespace cannot enter the frozen C3 inventory. It is
projected to the old namespace only by the explicit comparison harness, after
checking all remaining bytes. No environment flag enables population execution.
"""
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
from time import perf_counter
from .phase15_nauty import Backend as LinuxBackend, BackendFailure, LIMIT
from . import phase15_topology as topology

VALIDATION_NAMESPACE = 'phase1.5-macos-C3-COMPATIBILITY-CANDIDATE'
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PIN = ROOT/'configs/phase15_nauty_macos_validation.json'


class MacBackend(LinuxBackend):
    def __init__(self, *, validation_only=False, pin_path=DEFAULT_PIN):
        super().__init__()
        if not validation_only:
            raise BackendFailure('BLOCKED: hard 512-MiB macOS enforcement not demonstrated; production disabled')
        if sys.platform!='darwin' or platform.machine()!='arm64':
            raise BackendFailure('Native macOS ARM64 runtime required')
        self.pin_path=Path(pin_path).resolve()
        raw=self.pin_path.read_bytes()
        self.pin_sha256=hashlib.sha256(raw).hexdigest()
        pin=json.loads(raw)
        if pin.get('validation_only') is not True or pin.get('namespace')!=VALIDATION_NAMESPACE:
            raise BackendFailure('Invalid macOS validation profile')
        for path,expected in pin['artifact_sha256'].items():
            p=(ROOT/path).resolve()
            if not p.is_relative_to(ROOT) or hashlib.sha256(p.read_bytes()).hexdigest()!=expected:
                raise BackendFailure('Pinned macOS artifact/source mismatch: '+path)
        self.pin=pin

    def _start(self):
        import os
        self.process=subprocess.Popen([sys.executable,'-I',
            str(Path(__file__).with_name('phase15_nauty_macos_worker.py')),
            str(self.pin_path),self.pin_sha256],stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        os.set_blocking(self.process.stdin.fileno(),False)
        os.set_blocking(self.process.stdout.fileno(),False)

    def exact_certificate(self, graph, *, statistics=None):
        started=perf_counter();self.counter+=1
        try:
            if self.process is None:self._start()
            request=json.dumps(dict(id=self.counter,matrix=graph.matrix)).encode()+b'\n'
            reply=json.loads(self._exchange(request,started+5))
            if reply.get('error'):raise BackendFailure(reply['error'])
            order=reply['order']
            if (reply['id']!=self.counter or reply['namespace']!=VALIDATION_NAMESPACE
                or any(type(v) is not int for v in order) or sorted(order)!=list(range(graph.n))
                or reply['validation_only'] is not True or reply['hard_memory_enforced'] is not False
                or reply['rss_unit']!='bytes' or type(reply['peak_rss_bytes']) is not int
                or not 0<reply['peak_rss_bytes']<=LIMIT or reply['pin_sha256']!=self.pin_sha256):
                raise BackendFailure('invalid_output: identity, permutation or macOS resource evidence')
            if perf_counter()-started>5:raise BackendFailure('timeout: late output')
            if statistics is not None:
                statistics.update(vertices=graph.n,seconds=perf_counter()-started,
                    cpu_seconds=reply['cpu_seconds'],worker_seconds=reply['worker_seconds'],
                    peak_rss_bytes=reply['peak_rss_bytes'],hard_memory_enforced=False,
                    validation_only=True,native_search_nodes=None,status='certified',
                    certification_scope='mathematical compatibility only')
            return (VALIDATION_NAMESPACE,*topology.serialize_order(graph,order))
        except Exception as error:
            if statistics is not None:statistics.update(status='failed',seconds=perf_counter()-started,error=str(error))
            self.close()
            if isinstance(error,BackendFailure):raise
            raise BackendFailure('invalid_output_or_worker_failure: '+type(error).__name__) from error
