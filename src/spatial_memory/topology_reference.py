"""Independent brute-force public graph reference for offline validation only.

This module intentionally does not import or share helpers with production
Tarjan code. Its high-order per-vertex/edge BFS work is unsuitable online.
"""
from collections import deque
import math


def _ref_open(grid,cell,unknown):
    col,row=cell
    if row<0 or row>=grid.shape[0] or col<0 or col>=grid.shape[1]:return False
    value=int(grid[row,col])
    return value!=1 and not (unknown=='blocked' and value==-1)


def _ref_graph(grid,unknown,extra_open=(),removed_vertex=None,removed_edge=None):
    extra=set(extra_open);vertices=[]
    for row in range(grid.shape[0]):
        for col in range(grid.shape[1]):
            cell=(col,row)
            if _ref_open(grid,cell,unknown) or cell in extra:
                if cell!=removed_vertex:vertices.append(cell)
    vertex_set=set(vertices);adj={v:[] for v in vertices}
    for x,y in vertices:
        for nxt in ((x+1,y),(x,y+1),(x-1,y),(x,y-1)):
            if nxt not in vertex_set:continue
            edge=tuple(sorted(((x,y),nxt)))
            if removed_edge is not None and edge==removed_edge:continue
            adj[(x,y)].append(nxt)
    return vertices,adj


def _components(adj):
    labels={};members=[]
    for seed in adj:
        if seed in labels:continue
        cid=len(members);labels[seed]=cid;queue=deque([seed]);group=[]
        while queue:
            u=queue.popleft();group.append(u)
            for v in adj[u]:
                if v not in labels:labels[v]=cid;queue.append(v)
        members.append(group)
    return labels,members


def _shortest(adj,start,goal):
    if start not in adj or goal not in adj:return math.inf
    dist={start:0};queue=deque([start])
    while queue:
        u=queue.popleft()
        if u==goal:return dist[u]
        for v in adj[u]:
            if v not in dist:dist[v]=dist[u]+1;queue.append(v)
    return math.inf


def brute_force_topology_reference(grid,start,goal,unknown='optimistic',eligible_nontraversable=()):
    """Recompute connectivity after every vertex, edge, and candidate restore."""
    if unknown not in {'optimistic','blocked'}:raise ValueError('Invalid unknown handling')
    start=tuple(start);goal=tuple(goal)
    vertices,adj=_ref_graph(grid,unknown)
    labels,groups=_components(adj);base_cc=len(groups)
    baseline=_shortest(adj,start,goal)
    articulation=set();separating=set();cycle_vertices=set()
    for v in vertices:
        vv,aa=_ref_graph(grid,unknown,removed_vertex=v)
        _,cc=_components(aa)
        if len(cc)>base_cc:articulation.add(v)
        if start!=goal and v not in (start,goal) and math.isfinite(baseline) and not math.isfinite(_shortest(aa,start,goal)):
            separating.add(v)
        neighbors=[n for n in adj[v] if n!=v]
        for i,a in enumerate(neighbors):
            for b in neighbors[i+1:]:
                if math.isfinite(_shortest(aa,a,b)):
                    cycle_vertices.add(v);break
            if v in cycle_vertices:break
    bridges=set();relevant_bridges=set()
    for u in vertices:
        for v in adj[u]:
            edge=tuple(sorted((u,v)))
            if u>=v:continue
            vv,aa=_ref_graph(grid,unknown,removed_edge=edge)
            _,cc=_components(aa)
            if len(cc)>base_cc:bridges.add(edge)
            if math.isfinite(baseline) and not math.isfinite(_shortest(aa,start,goal)):
                relevant_bridges.add(edge)
    shortcuts={}
    for cell in eligible_nontraversable:
        cell=tuple(cell)
        if cell in adj:continue
        if cell==goal:
            shortcuts[cell]={'kind':'nontraversable_goal_terminal','distance_gain':0,'connectivity_restored':False}
            continue
        _,restored_adj=_ref_graph(grid,unknown,extra_open=(cell,))
        restored_dist=_shortest(restored_adj,start,goal)
        connectivity=not math.isfinite(baseline) and math.isfinite(restored_dist)
        gain=(int(baseline-restored_dist) if math.isfinite(baseline) and math.isfinite(restored_dist) and restored_dist<baseline else 0)
        if connectivity:kind='nontraversable_connectivity_restoration'
        elif gain>0:kind='nontraversable_distance_shortcut'
        else:kind='nontraversable_no_route_benefit'
        shortcuts[cell]={'kind':kind,'distance_gain':gain,'connectivity_restored':connectivity,
                         'restored_distance':restored_dist}
    return {'vertices':set(vertices),'adjacency':adj,'components':labels,
        'component_count':base_cc,'baseline_reachable':math.isfinite(baseline),
        'baseline_distance':baseline,'articulation':articulation,
        'start_goal_separating':separating,'bridges':bridges,
        'terminal_relevant_bridges':relevant_bridges,'cycle_vertices':cycle_vertices,
        'nontraversable_shortcuts':shortcuts}
