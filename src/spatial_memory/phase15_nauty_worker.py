"""Private POSIX worker. No generators, numpy, policies or evaluator inputs."""
import hashlib
import json
from pathlib import Path
import resource
import sys
from time import perf_counter, process_time

LIMIT=512*1024*1024
resource.setrlimit(resource.RLIMIT_AS,(LIMIT,LIMIT))
ROOT=Path(__file__).resolve().parents[2]
PIN=json.loads((ROOT/'configs/phase15_nauty_backend.json').read_text(encoding='utf-8-sig'))
for name,expected in PIN['dependency_sha256'].items():
    if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=expected:
        raise RuntimeError('Pinned dependency mismatch: '+name)
sys.path.insert(0,str(ROOT/'results/runs/phase1_5b01_dependencies'))
import pynauty
if pynauty.__version__!=PIN['pynauty_version']: raise RuntimeError('Backend version mismatch')


def canonical(matrix):
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


if __name__=='__main__':
    for line in sys.stdin:
        started=perf_counter(); cpu=process_time()
        try:
            request=json.loads(line); order=canonical(request['matrix'])
            reply=dict(id=request['id'],order=order,namespace=PIN['namespace'],
                cpu_seconds=process_time()-cpu,worker_seconds=perf_counter()-started,
                peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                address_space_limit=list(resource.getrlimit(resource.RLIMIT_AS)))
        except MemoryError:
            reply={'error':'memory_exhaustion'}
        except Exception as error:
            reply={'error':'worker_error','detail':type(error).__name__}
        print(json.dumps(reply),flush=True)
