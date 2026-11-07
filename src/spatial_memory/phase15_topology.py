"""Exact v0.2 raster quotient and bounded exhaustive canonical labeling.

No hash is used to decide graph equivalence. A resource failure returns no key.
"""
from dataclasses import dataclass
from functools import lru_cache
from itertools import permutations
from time import perf_counter
from .phase15_generators import components, neighbors, row_key


class CanonicalizationLimit(RuntimeError):
    pass


@dataclass(frozen=True)
class Graph:
    matrix: tuple

    def __post_init__(self):
        n=len(self.matrix)
        if any(len(row)!=n for row in self.matrix): raise ValueError('Not square')
        if any(type(v) is not int or v<0 for row in self.matrix for v in row):
            raise ValueError('Nonnegative integer multiplicities required')
        if any(self.matrix[i][j]!=self.matrix[j][i] for i in range(n) for j in range(n)):
            raise ValueError('Not undirected')

    @property
    def n(self): return len(self.matrix)

    def degree(self,i): return sum(self.matrix[i])+self.matrix[i][i]

    def edges(self):
        return [(i,j) for i in range(self.n) for j in range(i+1,self.n) if self.matrix[i][j]]


def graph_from_edges(n, edges):
    a=[[0]*n for _ in range(n)]
    for u,v in edges:
        a[u][v]+=1
        if u!=v: a[v][u]+=1
    return Graph(tuple(map(tuple,a)))


def induced(graph, vertices):
    return Graph(tuple(tuple(graph.matrix[i][j] for j in vertices) for i in vertices))


def suppress(graph):
    """Suppress degree-two paths; a pure cycle becomes one vertex/one loop."""
    a={i:{j:graph.matrix[i][j] for j in range(graph.n) if graph.matrix[i][j]}
       for i in range(graph.n)}
    while True:
        eligible=[u for u in a if sum(a[u].values())+a[u].get(u,0)==2]
        if not eligible: break
        u=min(eligible)
        if a[u].get(u)==1: # already a normalized isolated cycle
            other=[v for v in eligible if v!=u and a[v].get(v)!=1]
            if not other: break
            u=min(other)
        adjacent=[v for v in a[u] if v!=u]
        if len(adjacent)==1: # parallel corridor sides collapse to one loop
            v=adjacent[0]
            del a[v][u]; del a[u]
            a[v][v]=a[v].get(v,0)+1
        elif len(adjacent)==2:
            v,w=adjacent
            del a[v][u]; del a[w][u]; del a[u]
            a[v][w]=a[v].get(w,0)+1; a[w][v]=a[w].get(v,0)+1
        else:
            raise ValueError('Invalid degree-two multigraph')
    vertices=sorted(a)
    return Graph(tuple(tuple(a[u].get(v,0) for v in vertices) for u in vertices))


def raster_quotient(free):
    free=set(map(tuple,free)); marked=set()
    for x,y in free:
        square={(x,y),(x+1,y),(x,y+1),(x+1,y+1)}
        if square<=free: marked.update(square)
    regions=components(marked); owner={}
    nodes=regions+[{c} for c in sorted(free-marked,key=row_key)]
    nodes.sort(key=lambda comp:row_key(min(comp,key=row_key)))
    for i,comp in enumerate(nodes):
        for c in comp: owner[c]=i
    edges=set()
    for c,u in owner.items():
        for nxt in neighbors(c):
            if nxt in owner and owner[nxt]!=u:
                edges.add(tuple(sorted((u,owner[nxt]))))
    raw=graph_from_edges(len(nodes),sorted(edges))
    return suppress(raw),dict(free_cells=len(free),marked_cells=len(marked),
                             room_regions=len(regions),quotient_vertices=raw.n,
                             normalized_vertices=suppress(raw).n)


def serialize_order(graph, order):
    return (graph.n,*(graph.matrix[i][i] for i in order),
            *(graph.matrix[order[i]][order[j]] for i in range(graph.n) for j in range(i+1,graph.n)))


def brute_certificate(graph):
    """Independent all-permutations reference, small graphs only."""
    if graph.n>8: raise ValueError('Reference limit is eight vertices')
    return min((serialize_order(graph,p) for p in permutations(range(graph.n))),default=(0,))


def exact_certificate(graph, *, max_nodes=100_000, max_seconds=5., statistics=None):
    """Lex-min loops then upper triangle, with exact row-prefix pruning.

    Within cells tied by loops and already serialized rows, sorting adjacency
    to the next selected vertex minimizes the next row. Only candidates with
    the smallest next row can attain the global minimum. No degree/WL shortcut.
    """
    started=perf_counter(); visited=0
    loops=sorted({graph.matrix[i][i] for i in range(graph.n)})
    initial=tuple(tuple(i for i in range(graph.n) if graph.matrix[i][i]==count) for count in loops)

    @lru_cache(maxsize=None)
    def search(partition):
        nonlocal visited
        visited+=1
        if visited>max_nodes or perf_counter()-started>max_seconds:
            raise CanonicalizationLimit(f'exact labeling exceeded nodes={visited}, elapsed={perf_counter()-started:.6f}')
        if not partition: return ()
        options=[]; best_row=None; representatives=[]
        for v in partition[0]:
            # A true twin transposition is a proved automorphism.
            if any(all(graph.matrix[v][k]==graph.matrix[u][k]
                       for k in range(graph.n) if k not in (u,v))
                   and graph.matrix[v][v]==graph.matrix[u][u] for u in representatives):
                continue
            representatives.append(v)
            remaining=[]
            for cell in partition:
                groups={}
                for u in cell:
                    if u!=v: groups.setdefault(graph.matrix[v][u],[]).append(u)
                remaining.extend(tuple(groups[key]) for key in sorted(groups))
            row=tuple(graph.matrix[v][u] for cell in remaining for u in cell)
            if best_row is None or row<best_row: best_row=row; options=[tuple(remaining)]
            elif row==best_row: options.append(tuple(remaining))
        suffix=min(search(p) for p in options)
        return best_row+suffix

    try:
        suffix=search(initial)
        return (graph.n,*sorted(graph.matrix[i][i] for i in range(graph.n)),*suffix)
    finally:
        if statistics is not None:
            statistics.update(vertices=graph.n,nodes=visited,seconds=perf_counter()-started)


def delete_leaf(graph,u):
    if graph.degree(u)!=1: raise ValueError('Not a leaf')
    return suppress(induced(graph,[i for i in range(graph.n) if i!=u]))


def contract_edge(graph,u,v):
    if u==v or not graph.matrix[u][v]: raise ValueError('Only non-loop edges contract')
    # Contract one edge, not every parallel edge; remaining parallel edges become loops.
    mapping={i:(u if i==v else i) for i in range(graph.n)}
    labels=sorted(set(mapping.values())); index={a:i for i,a in enumerate(labels)}
    edges=[]
    for a in range(graph.n):
        for b in range(a,graph.n):
            count=graph.matrix[a][b]-int(a==min(u,v) and b==max(u,v))
            edges.extend([(index[mapping[a]],index[mapping[b]])]*count)
    return suppress(graph_from_edges(len(labels),edges))


def near_certificates(graph, *, measurements=None, **limits):
    variants=[('self',suppress(graph))]
    variants.extend((f'leaf:{u}',delete_leaf(graph,u)) for u in range(graph.n) if graph.degree(u)==1)
    variants.extend((f'edge:{u}:{v}',contract_edge(graph,u,v)) for u,v in graph.edges())
    result=set()
    for operation,variant in variants:
        stats={}
        try: result.add(exact_certificate(variant,statistics=stats,**limits))
        finally:
            if measurements is not None: measurements.append(dict(operation=operation,**stats))
    return frozenset(result)


def raster_certificate(free,width=25,height=25):
    grid={(x,y) for x,y in free}; representations=[]
    if width!=height: # historical rectangular rasters retain dimension in comparison
        for flip_x in (False,True):
            for flip_y in (False,True):
                cells={(width-1-x if flip_x else x,height-1-y if flip_y else y) for x,y in grid}
                representations.append((width,height,''.join('1' if (x,y) in cells else '0' for y in range(height) for x in range(width))))
        transposed={(y,x) for x,y in grid}
        for flip_x in (False,True):
            for flip_y in (False,True):
                cells={(height-1-x if flip_x else x,width-1-y if flip_y else y) for x,y in transposed}
                representations.append((height,width,''.join('1' if (x,y) in cells else '0' for y in range(width) for x in range(height))))
    else:
        for reflected in (False,True):
            cells={(width-1-x if reflected else x,y) for x,y in grid}
            for _ in range(4):
                representations.append((width,height,''.join('1' if (x,y) in cells else '0' for y in range(height) for x in range(width))))
                cells={(width-1-y,x) for x,y in cells}
    return min(representations)


class IndependenceIndex:
    """Transitive lineage/near/raster union; cross-split bridges are rejected."""
    def __init__(self):
        self.records=[]; self.parent=[]

    def root(self,i):
        if self.parent[i]!=i: self.parent[i]=self.root(self.parent[i])
        return self.parent[i]

    def matches(self, keys, raster, lineage):
        return [i for i,r in enumerate(self.records) if
                r['keys']&keys or r['raster']==raster or r['lineage']==lineage]

    def admit(self, *, partition, mechanism, keys, exact, raster, lineage, identity):
        matches=self.matches(keys,raster,lineage)
        if any(self.records[i]['partition']!=partition for i in matches):
            return dict(accepted=False,reason='cross_partition_or_historical',matches=matches)
        i=len(self.records); self.parent.append(i)
        self.records.append(dict(partition=partition,mechanism=mechanism,keys=keys,
                                 exact=exact,raster=raster,lineage=lineage,identity=identity))
        roots={self.root(j) for j in matches}
        for root in roots: self.parent[root]=i
        return dict(accepted=not matches,reason='independent' if not matches else 'same_partition_related',
                    matches=matches,merged_components=len(roots),record_index=i,
                    exact_matches=[j for j in matches if self.records[j]['exact']==exact])

    def clusters(self,partition):
        result={}
        for i,r in enumerate(self.records):
            if r['partition']==partition: result.setdefault(self.root(i),[]).append(i)
        return list(result.values())
