"""v0.3 exact topology keys, parent-supervised POSIX nauty worker.

The immutable literal backend remains in phase15_topology. No approximate keys.
"""
import json
import os
from pathlib import Path
import selectors
import subprocess
import sys
from time import perf_counter
from . import phase15_topology as old

NAMESPACE='phase1.5-v0.3-CANON-1'
LIMIT=512*1024*1024


class BackendFailure(old.CanonicalizationLimit): pass


class Backend:
    def __init__(self):
        self.process=None; self.counter=0

    def close(self):
        if self.process is not None:
            if self.process.poll() is None: self.process.kill()
            self.process.wait()
            for stream in (self.process.stdin,self.process.stdout,self.process.stderr): stream.close()
            self.process=None

    def _start(self):
        if sys.platform!='linux': raise BackendFailure('Linux enforcement required')
        self.process=subprocess.Popen([sys.executable,str(Path(__file__).with_name('phase15_nauty_worker.py'))],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        os.set_blocking(self.process.stdin.fileno(),False)
        os.set_blocking(self.process.stdout.fileno(),False)

    def _exchange(self,request,deadline):
        sent=0; output=bytearray()
        with selectors.DefaultSelector() as selector:
            selector.register(self.process.stdin,selectors.EVENT_WRITE)
            selector.register(self.process.stdout,selectors.EVENT_READ)
            while True:
                remaining=deadline-perf_counter()
                if remaining<=0: raise BackendFailure('timeout: parent killed worker at five-second deadline')
                events=selector.select(remaining)
                if not events: raise BackendFailure('timeout: parent killed worker at five-second deadline')
                for event,_ in events:
                    if event.fileobj is self.process.stdin:
                        sent+=os.write(self.process.stdin.fileno(),request[sent:])
                        if sent==len(request): selector.unregister(self.process.stdin)
                    else:
                        chunk=os.read(self.process.stdout.fileno(),65536)
                        if not chunk: raise BackendFailure('worker_crash: no complete output')
                        output.extend(chunk)
                        if len(output)>1024*1024: raise BackendFailure('invalid_output: oversized reply')
                        if b'\n' in output:
                            if not output.endswith(b'\n') or output.count(b'\n')!=1:
                                raise BackendFailure('invalid_output: framing')
                            return bytes(output)

    def exact_certificate(self, graph, *, statistics=None):
        started=perf_counter(); self.counter+=1
        try:
            if self.process is None: self._start()
            request=json.dumps(dict(id=self.counter,matrix=graph.matrix)).encode()+b'\n'
            line=self._exchange(request,started+5)
            if not line: raise BackendFailure('worker_crash: no output')
            reply=json.loads(line)
            if reply.get('error'): raise BackendFailure(reply['error'])
            order=reply['order']
            if (reply['id']!=self.counter or reply['namespace']!=NAMESPACE or
                any(type(v) is not int for v in order) or sorted(order)!=list(range(graph.n)) or
                reply['address_space_limit']!=[LIMIT,LIMIT] or
                not 0<reply['peak_rss_kib']<=LIMIT//1024):
                raise BackendFailure('invalid_output: order, identity or resource evidence')
            if perf_counter()-started>5: raise BackendFailure('timeout: late output')
            key=(NAMESPACE,*old.serialize_order(graph,order))
            if statistics is not None:
                statistics.update(vertices=graph.n,seconds=perf_counter()-started,
                    cpu_seconds=reply['cpu_seconds'],worker_seconds=reply['worker_seconds'],
                    peak_rss_kib=reply['peak_rss_kib'],native_search_nodes=None,status='certified')
            return key
        except Exception as error:
            if statistics is not None: statistics.update(status='failed',seconds=perf_counter()-started,error=str(error))
            self.close()
            if isinstance(error,BackendFailure): raise
            raise BackendFailure('invalid_output_or_worker_failure: '+type(error).__name__) from error

    def near_certificates(self,graph,*,measurements=None):
        variants=[('self',old.suppress(graph))]
        variants.extend((f'leaf:{u}',old.delete_leaf(graph,u)) for u in range(graph.n) if graph.degree(u)==1)
        variants.extend((f'edge:{u}:{v}',old.contract_edge(graph,u,v)) for u,v in graph.edges())
        keys=set()
        for operation,g in variants:
            stats={}
            try: keys.add(self.exact_certificate(g,statistics=stats))
            finally:
                if measurements is not None: measurements.append(dict(operation=operation,**stats))
        return frozenset(keys)
