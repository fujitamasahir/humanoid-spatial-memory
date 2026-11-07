"""Benchmark-only v0.3 PROPOSAL; never imported by artifact audit infrastructure.

Install pynauty==2.8.8.1 in the isolated directory documented in the report.
Canonical bytes intentionally differ from the frozen v0.2 lex-min bytes.
"""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'results/runs/phase1_5b01_dependencies'))
sys.path.insert(0,str(ROOT/'src'))
import pynauty
from spatial_memory.phase15_topology import serialize_order


def encode(graph):
    """Lossless colored simple incidence graph: vertex loops and edge weights."""
    colors={}; adjacency={i:[] for i in range(graph.n)}
    for i in range(graph.n): colors.setdefault((0,graph.matrix[i][i]),set()).add(i)
    for u,v in graph.edges():
        e=len(adjacency); adjacency[e]=[u,v]
        adjacency[u].append(e); adjacency[v].append(e)
        colors.setdefault((1,graph.matrix[u][v]),set()).add(e)
    return pynauty.Graph(len(adjacency),directed=False,adjacency_dict=adjacency,
                         vertex_coloring=[colors[k] for k in sorted(colors)])


def certificate(graph):
    if graph.n==0: return (0,)
    order=pynauty.canon_label(encode(graph))
    # Nauty's lab array lists old vertices at canonical positions.
    return serialize_order(graph,[v for v in order if v<graph.n])
