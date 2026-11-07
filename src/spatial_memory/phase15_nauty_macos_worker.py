"""Isolated native compatibility worker. Never a production-memory admission.

Uses byte-identical approved graph encoding/canon_label; no generators imported.
"""
import hashlib
import json
from pathlib import Path
import platform
import resource
import sys
from time import perf_counter, process_time

ROOT=Path(__file__).resolve().parents[2]
NAMESPACE='phase1.5-macos-C3-COMPATIBILITY-CANDIDATE'
LIMIT=536870912


def canonical(matrix, pynauty):
    n=len(matrix); colors={}; adjacency={i:[] for i in range(n)}
    for i in range(n): colors.setdefault((0,matrix[i][i]),set()).add(i)
    for u in range(n):
        for v in range(u+1,n):
            if matrix[u][v]:
                e=len(adjacency); adjacency[e]=[u,v]
                adjacency[u].append(e); adjacency[v].append(e)
                colors.setdefault((1,matrix[u][v]),set()).add(e)
    if not n: return []
    g=pynauty.Graph(len(adjacency),directed=False,adjacency_dict=adjacency,
        vertex_coloring=[colors[k] for k in sorted(colors)])
    return [v for v in pynauty.canon_label(g) if v<n]


def main():
    if sys.platform!='darwin' or platform.machine()!='arm64':raise RuntimeError('macOS ARM64 required')
    pin_path=Path(sys.argv[1]);pin_raw=pin_path.read_bytes();pin_sha=hashlib.sha256(pin_raw).hexdigest()
    if pin_sha!=sys.argv[2]:raise RuntimeError('Configuration changed since parent validation')
    pin=json.loads(pin_raw)
    if not pin['validation_only'] or pin['namespace']!=NAMESPACE:raise RuntimeError('Compatibility-only profile required')
    for name,expected in pin['artifact_sha256'].items():
        path=(ROOT/name).resolve()
        if not path.is_relative_to(ROOT) or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
            raise RuntimeError('Pinned native/source mismatch: '+name)
    sys.path.insert(0,str(ROOT/pin['package_root']))
    import pynauty
    if pynauty.__version__!='2.8.8.1' or pynauty._nauty_version!='nauty2_8_8':
        raise RuntimeError('Pinned algorithm version mismatch')
    for line in sys.stdin:
        started=perf_counter();cpu=process_time()
        try:
            request=json.loads(line);matrix=request['matrix'];n=len(matrix)
            if (any(len(row)!=n for row in matrix) or
                any(type(v) is not int or v<0 for row in matrix for v in row) or
                any(matrix[i][j]!=matrix[j][i] for i in range(n) for j in range(n))):
                raise ValueError('Invalid multigraph')
            order=canonical(matrix,pynauty)
            reply=dict(id=request['id'],order=order,namespace=NAMESPACE,
                cpu_seconds=process_time()-cpu,worker_seconds=perf_counter()-started,
                peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                rss_unit='bytes',validation_only=True,hard_memory_enforced=False,pin_sha256=pin_sha)
        except MemoryError:reply={'error':'memory_exhaustion'}
        except Exception as error:reply={'error':'worker_error','detail':type(error).__name__}
        print(json.dumps(reply),flush=True)


if __name__=='__main__':main()
