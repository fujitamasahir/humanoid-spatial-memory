"""Experimental literal v0.2 lex-min backend; no changed equivalence or format.

Only mathematical graph benchmarks use this module pending scientific review.
"""
from time import perf_counter
from .phase15_topology import CanonicalizationLimit


def exact_certificate(graph, *, max_nodes=100_000, max_seconds=5., statistics=None):
    started=perf_counter(); nodes=0; pruned=0; leaves=0; incumbent=None
    a=graph.matrix; n=graph.n
    initial=tuple(tuple(i for i in range(n) if a[i][i]==v)
                  for v in sorted({a[i][i] for i in range(n)}))

    def search(partition, prefix):
        nonlocal nodes,pruned,leaves,incumbent
        nodes+=1
        if nodes>max_nodes or perf_counter()-started>max_seconds:
            raise CanonicalizationLimit('literal branch-and-bound resource guard')
        if incumbent is not None and prefix>incumbent[:len(prefix)]:
            pruned+=1; return
        if not partition:
            leaves+=1; incumbent=prefix; return
        options=[]; best=None; representatives=[]
        for v in partition[0]:
            if any(all(a[v][k]==a[u][k] for k in range(n) if k not in (u,v))
                   and a[v][v]==a[u][u] for u in representatives):
                continue
            representatives.append(v); remaining=[]
            for cell in partition:
                groups={}
                for u in cell:
                    if u!=v: groups.setdefault(a[v][u],[]).append(u)
                remaining.extend(tuple(groups[key]) for key in sorted(groups))
            row=tuple(a[v][u] for cell in remaining for u in cell)
            if best is None or row<best: best=row; options=[tuple(remaining)]
            elif row==best: options.append(tuple(remaining))
        for remaining in options:
            search(remaining,prefix+best)

    try:
        search(initial,())
        return (n,*sorted(a[i][i] for i in range(n)),*incumbent)
    finally:
        if statistics is not None:
            statistics.update(vertices=n,nodes=nodes,seconds=perf_counter()-started,
                              prefix_prunes=pruned,completed_leaves=leaves)
