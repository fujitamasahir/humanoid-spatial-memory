"""Option B isolated C3 worker. No generators or historical data imported."""
import hashlib
import importlib.util
import json
from pathlib import Path
import resource
import sys
from time import perf_counter,process_time

ROOT=Path(__file__).resolve().parents[2]
PROFILE='phase1.5-v0.4-MACOS-RSS-B1'
NAMESPACE='phase1.5-v0.3-CANON-1'


def main():
    raw=Path(sys.argv[1]).read_bytes();pin_sha=hashlib.sha256(raw).hexdigest()
    if pin_sha!=sys.argv[2]:raise RuntimeError('Pin changed')
    pin=json.loads(raw)
    for p,h in pin['artifact_sha256'].items():
        if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=h:raise RuntimeError('Artifact changed')
    sys.path.insert(0,str(ROOT/pin['package_root']))
    import pynauty
    if pynauty.__version__!='2.8.8.1' or pynauty._nauty_version!='nauty2_8_8':raise RuntimeError('Algorithm changed')
    path=Path(__file__).with_name('phase15_nauty_macos_worker.py')
    spec=importlib.util.spec_from_file_location('approved_encoding',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    for line in sys.stdin:
        started=perf_counter();cpu=process_time()
        try:
            r=json.loads(line);matrix=r['matrix'];n=len(matrix)
            if any(len(row)!=n for row in matrix) or any(type(v) is not int or v<0 for row in matrix for v in row) or any(matrix[i][j]!=matrix[j][i] for i in range(n) for j in range(n)):
                raise ValueError('Malformed multigraph')
            order=module.canonical(matrix,pynauty)
            reply=dict(id=r['id'],order=order,namespace=NAMESPACE,profile=PROFILE,pin_sha256=pin_sha,
                       rss_unit='bytes',cpu_seconds=process_time()-cpu,worker_seconds=perf_counter()-started,
                       peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
            # Allocate the serialized buffer before measuring the final peak.
            encoded=json.dumps(reply)
            reply['peak_rss_bytes']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            reply['peak_measured_at']=perf_counter()
            encoded=json.dumps(reply)
        except Exception as error:encoded=json.dumps(dict(error=repr(error)))
        print(encoded,flush=True)


if __name__=='__main__':main()
