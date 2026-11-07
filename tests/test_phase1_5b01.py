"""Mathematical literal-format backend checks; no world generation."""
from itertools import combinations
import random
import pytest
from spatial_memory import phase15_topology as old
from spatial_memory.phase15_exact_bnb import exact_certificate


def test_all_small_simple_graphs_against_exhaustive_oracle():
    for n in range(1,6):
        edges=list(combinations(range(n),2))
        for mask in range(1<<len(edges)):
            g=old.graph_from_edges(n,[e for i,e in enumerate(edges) if mask>>i&1])
            assert exact_certificate(g)==old.brute_certificate(g)


def test_random_loops_parallel_and_relabeling():
    rng=random.Random(150150)
    for n in range(1,7):
        for _ in range(15):
            a=[[0]*n for _ in range(n)]
            for i in range(n):
                for j in range(i,n): a[i][j]=a[j][i]=rng.randrange(3)
            g=old.Graph(tuple(map(tuple,a))); order=list(range(n)); rng.shuffle(order)
            expected=old.brute_certificate(g)
            assert exact_certificate(g)==expected
            assert exact_certificate(old.induced(g,order))==expected


def test_symmetric_and_near_operations():
    for g in (old.graph_from_edges(6,[(i,(i+1)%6) for i in range(6)]),
              old.graph_from_edges(6,[(0,i) for i in range(1,6)]),
              old.graph_from_edges(4,[(0,1)]*3+[(1,2),(2,3),(3,0),(0,0)])):
        variants=[old.suppress(g)]
        variants += [old.delete_leaf(g,u) for u in range(g.n) if g.degree(u)==1]
        variants += [old.contract_edge(g,u,v) for u,v in g.edges()]
        for v in variants: assert exact_certificate(v)==old.brute_certificate(v)


def test_guards_return_no_partial_certificate():
    g=old.graph_from_edges(4,[(0,1),(1,2),(2,3)])
    for limits in ({'max_nodes':0},{'max_seconds':-1}):
        with pytest.raises(old.CanonicalizationLimit): exact_certificate(g,**limits)


def test_empty_graph_certificate():
    assert exact_certificate(old.graph_from_edges(0,[]))==(0,)
