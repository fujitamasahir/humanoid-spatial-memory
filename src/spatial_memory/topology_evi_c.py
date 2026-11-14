"""Corrected, isolated C v2.0c topology candidate selector.

Production analysis uses iterative Tarjan DFS; brute-force reference code lives
in ``spatial_memory.topology_reference`` and is never imported here.
"""
from __future__ import annotations

from collections import deque
from functools import cmp_to_key
from time import perf_counter_ns
import math
import numpy as np

from .evi import EVIParameters, visible_cells
from .navigation import plan


_DIRS=((1,0),(0,1),(-1,0),(0,-1))


def _open(grid,cell,unknown):
    x,y=cell
    return 0<=y<grid.shape[0] and 0<=x<grid.shape[1] and grid[y,x]!=1 and not (unknown=='blocked' and grid[y,x]==-1)


def _adjacency(grid,unknown):
    nodes=[(x,y) for y in range(grid.shape[0]) for x in range(grid.shape[1]) if _open(grid,(x,y),unknown)]
    node_set=set(nodes)
    adj={u:tuple((u[0]+dx,u[1]+dy) for dx,dy in _DIRS if (u[0]+dx,u[1]+dy) in node_set) for u in nodes}
    return nodes,node_set,adj


def _distances(adj,source,counts):
    if source not in adj:return {}
    dist={source:0};q=deque([source])
    while q:
        u=q.popleft();counts['bfs_vertex_visits']+=1
        for v in adj[u]:
            counts['bfs_edge_inspections']+=1
            if v not in dist:dist[v]=dist[u]+1;q.append(v)
    return dist


def eligible_topology_candidates_c(grid,probability,position,yaw,sensor):
    """Exactly the frozen C visibility/probability eligibility filter."""
    footprint=visible_cells(grid,position,yaw,**sensor)
    candidates=[c for c in footprint if c!=tuple(position) and .05<float(probability[c[1],c[0]])<.95]
    return candidates,footprint


def analyze_public_topology_c(grid,start,goal,unknown='optimistic'):
    """Iterative O(V+E) Tarjan analysis including disconnected components."""
    if unknown not in {'optimistic','blocked'}:raise ValueError('Invalid unknown handling')
    started=perf_counter_ns();start=tuple(start);goal=tuple(goal)
    nodes,node_set,adj=_adjacency(grid,unknown)
    disc={};low={};parent={};children={u:[] for u in nodes};child_count={u:0 for u in nodes};component={}
    roots={};tout={};art=set();bridges=set();blocks=[];edge_stack=[];clock=0;comp_id=0
    counts={'grid_cell_scans':int(grid.size),'adjacency_neighbor_probes':0,
        'vertex_visits':0,'edge_inspections':0,'biconnected_edge_pops':0,
        'component_vertex_visits':0,'component_edge_inspections':0,
        'bridge_forest_edge_visits':0,'bridge_tree_edge_inspections':0,
        'biconnected_block_edge_visits':0,'terminal_articulation_tests':0,
        'terminal_child_edge_checks':0,'cycle_block_vertex_visits':0,
        'bridge_endpoint_set_visits':0,
        'bfs_vertex_visits':0,'bfs_edge_inspections':0}
    counts['adjacency_neighbor_probes']=4*len(nodes)
    order=([start] if start in node_set else [])+[u for u in nodes if u!=start]
    for root in order:
        if root in disc:continue
        comp_id+=1;clock+=1;disc[root]=low[root]=clock;component[root]=comp_id;roots[root]=root
        stack=[(root,0)]
        while stack:
            u,index=stack[-1]
            if index<len(adj[u]):
                v=adj[u][index];stack[-1]=(u,index+1);counts['edge_inspections']+=1
                if v==parent.get(u):continue
                if v not in disc:
                    parent[v]=u;roots[v]=root;children[u].append(v);child_count[u]+=1
                    edge_stack.append((u,v));clock+=1;disc[v]=low[v]=clock;component[v]=comp_id
                    stack.append((v,0))
                elif disc[v]<disc[u]:
                    low[u]=min(low[u],disc[v]);edge_stack.append((u,v))
            else:
                stack.pop();counts['vertex_visits']+=1;tout[u]=clock
                p=parent.get(u)
                if p is None:
                    if child_count[u]>1:art.add(u)
                    if edge_stack:
                        block=[]
                        while edge_stack:
                            block.append(edge_stack.pop());counts['biconnected_edge_pops']+=1
                        if block:blocks.append(tuple(block))
                else:
                    low[p]=min(low[p],low[u])
                    edge=(p,u) if p<u else (u,p)
                    if low[u]>disc[p]:bridges.add(edge)
                    if low[u]>=disc[p]:
                        if parent.get(p) is not None:art.add(p)
                        block=[]
                        while edge_stack:
                            e=edge_stack.pop();counts['biconnected_edge_pops']+=1;block.append(e)
                            if e==(p,u):break
                        if block:blocks.append(tuple(block))

    # Label 2-edge-connected regions by traversing the graph without bridges.
    bridge_region={};region_id=0
    for seed in nodes:
        if seed in bridge_region:continue
        region_id+=1;bridge_region[seed]=region_id;stack=[seed]
        while stack:
            u=stack.pop();counts['component_vertex_visits']+=1
            for v in adj[u]:
                counts['component_edge_inspections']+=1
                edge=(u,v) if u<v else (v,u)
                if edge in bridges or v in bridge_region:continue
                bridge_region[v]=region_id;stack.append(v)
    tree={}
    bridge_degree={}
    for u,v in bridges:
        counts['bridge_forest_edge_visits']+=1
        a,b=bridge_region[u],bridge_region[v]
        tree.setdefault(a,[]).append((b,(u,v)));tree.setdefault(b,[]).append((a,(u,v)))
        bridge_degree[u]=bridge_degree.get(u,0)+1;bridge_degree[v]=bridge_degree.get(v,0)+1
    relevant_bridges=set()
    if start in bridge_region and goal in bridge_region and component[start]==component[goal]:
        source,target=bridge_region[start],bridge_region[goal]
        previous={source:None};q=deque([source])
        while q and target not in previous:
            a=q.popleft()
            for b,e in tree.get(a,()):
                counts['bridge_tree_edge_inspections']+=1
                if b not in previous:previous[b]=(a,e);q.append(b)
        if target in previous:
            cur=target
            while previous[cur] is not None:
                cur,e=previous[cur];relevant_bridges.add(tuple(sorted(e)))

    separators=set()
    if start!=goal and start in disc and goal in disc and component[start]==component[goal]:
        for v in art:
            counts['terminal_articulation_tests']+=1
            if v in (start,goal):continue
            for child in children[v]:
                counts['terminal_child_edge_checks']+=1
                if disc[child]<=disc[goal]<=tout[child] and low[child]>=disc[v]:
                    separators.add(v);break
    ds=_distances(adj,start,counts);dg=_distances(adj,goal,counts)
    baseline=ds.get(goal,math.inf)
    cyclic=set()
    for block in blocks:
        counts['biconnected_block_edge_visits']+=len(block)
        verts={v for e in block for v in e}
        counts['cycle_block_vertex_visits']+=2*len(block)
        if len(verts)>=3 and len(block)>=len(verts):cyclic.update(verts)
    counts['bridge_endpoint_set_visits']=2*len(relevant_bridges)
    elapsed=perf_counter_ns()-started
    vertices=len(nodes);edges=sum(map(len,adj.values()))//2
    # Count material graph/feature operations, not Python bytecodes.
    work=sum(counts.values())+vertices+edges
    return {'nodes':nodes,'node_set':node_set,'adj':adj,'component':component,
        'component_count':comp_id,'articulation':art,'separating':separators,
        'bridges':bridges,'relevant_bridges':relevant_bridges,
        'bridge_degree':bridge_degree,
        'relevant_bridge_endpoints':{v for e in relevant_bridges for v in e},
        'bridge_region':bridge_region,
        'blocks':blocks,'cyclic_block_vertices':cyclic,
        'dist_start':ds,'dist_goal':dg,'baseline_distance':baseline,
        'vertices':vertices,'edges':edges,'operation_counts':counts,
        'graph_work_units':work,'analysis_ns':elapsed}


def _feature(grid,cell,g,start,goal,route_set):
    x,y=cell
    if cell in g['node_set']:
        if cell in (tuple(start),tuple(goal)):
            return (0,1,0),'traversable_terminal'
        if cell in g['separating']:
            return (0,1,0),'start_goal_separating_articulation'
        if cell in g['relevant_bridge_endpoints']:
            return (2,g['bridge_degree'].get(cell,0),0),'terminal_relevant_bridge_endpoint'
        if cell in g['articulation'] and cell in route_set:
            return (3,1,0),'other_route_articulation'
        if cell in g['cyclic_block_vertices'] and cell in route_set:
            return (4,1,0),'route_cell_with_alternative_cycle'
        if cell in g['articulation']:
            return (5,0,0),'irrelevant_articulation'
        return (6,0,0),'other_traversable'
    if cell==tuple(goal):return (0,1,0),'nontraversable_goal_terminal'
    neighbors=[]
    for dx,dy in _DIRS:
        n=(x+dx,y+dy)
        if n in g['node_set']:neighbors.append(n)
    scomp=g['component'].get(tuple(start));gcomp=g['component'].get(tuple(goal))
    distinct_terminals=(scomp is not None and gcomp is not None and scomp!=gcomp)
    creates_connection=distinct_terminals and any(
        g['component'].get(a)==scomp and g['component'].get(b)==gcomp
        for a in neighbors for b in neighbors)
    if creates_connection:return (1,1,0),'nontraversable_connectivity_restoration'
    gain=0
    if math.isfinite(g['baseline_distance']):
        best=min((g['dist_start'].get(a,math.inf)+2+g['dist_goal'].get(b,math.inf)
                  for a in neighbors for b in neighbors),default=math.inf)
        if math.isfinite(best):gain=max(0,int(g['baseline_distance']-best))
    if gain>0:return (1,0,gain),'nontraversable_distance_shortcut'
    return (6,0,0),'nontraversable_no_route_benefit'


def candidate_structural_feature_c(grid,cell,g,start,goal,route=()):
    """Public wrapper used by the separate correctness audit tests."""
    return _feature(grid,tuple(cell),g,tuple(start),tuple(goal),set(route))


def rank_topology_candidates_c(grid,probability,candidates,g,start,goal,route):
    route_set=set(route);features={};counts={'route_set_vertices':len(route_set),
        'candidate_feature_visits':0,'candidate_classification_checks':0,'candidate_neighbor_checks':0,
        'candidate_component_pair_checks':0,'candidate_probability_ops':0,
        'sort_comparisons':0,'route_membership_checks':0}
    for cell in candidates:
        counts['candidate_feature_visits']+=1
        counts['candidate_classification_checks']+=8
        features[cell]=_feature(grid,cell,g,start,goal,route_set)
        counts['candidate_neighbor_checks']+=4
        if cell not in g['node_set']:
            # The shortcut test evaluates at most all ordered pairs of four
            # cardinal neighbors. Count those checks, including absent pairs.
            n=sum((cell[0]+dx,cell[1]+dy) in g['node_set'] for dx,dy in _DIRS)
            counts['candidate_component_pair_checks']+=n*n
        counts['candidate_probability_ops']+=2
        counts['route_membership_checks']+=1
    def compare(a,b):
        counts['sort_comparisons']+=1
        fa,fb=features[a][0],features[b][0]
        qa=float(probability[a[1],a[0]]);qb=float(probability[b[1],b[0]])
        ka=(fa[0],-fa[1],-fa[2],-qa*(1-qa),a[1],a[0])
        kb=(fb[0],-fb[1],-fb[2],-qb*(1-qb),b[1],b[0])
        return -1 if ka<kb else (1 if ka>kb else 0)
    ordered=sorted(candidates,key=cmp_to_key(compare))
    return ordered,features,counts


def information_value_topology_c(grid,probability,position,goal,yaw,unknown,sensor,remaining,parameters=None):
    """Original C V/D and cost equations with corrected C-Topology3 ranking."""
    scheduler_started=perf_counter_ns()
    p=parameters or EVIParameters(max_candidates=3)
    if p.max_candidates!=3:raise ValueError('C-Topology3 fixes K=3')
    nominal=plan(grid,position,goal,unknown)
    candidates,footprint=eligible_topology_candidates_c(grid,probability,position,yaw,sensor)
    topology_started=perf_counter_ns()
    graph=analyze_public_topology_c(grid,position,goal,unknown)
    ordered,features,rank_counts=rank_topology_candidates_c(grid,probability,candidates,graph,position,goal,nominal or [])
    graph_analysis_ns=perf_counter_ns()-topology_started
    best={'value':0.,'delay_regret':0.,'cell':None,'occupied_probability':None};calls=1
    for cell in ordered[:3]:
        routes=[]
        for outcome in (0,1):
            cf=grid.copy();cf[cell[1],cell[0]]=outcome
            routes.append(plan(cf,position,goal,unknown));calls+=1
        def loss(path,occupied):
            if not path:return p.failure_cost
            return len(path)-1+(p.failure_cost if occupied and cell in path else 0)
        q=float(probability[cell[1],cell[0]])
        vals=[[loss(path,o) for o in (0,1)] for path in routes]
        before=min((1-q)*v[0]+q*v[1] for v in vals)
        after=(1-q)*min(v[0] for v in vals)+q*min(v[1] for v in vals)
        value=max(0.,before-after)
        actions=[tuple(path[1]) if len(path)>1 else None for path in routes]
        delay=value*min(q,1-q) if actions[0]!=actions[1] else 0.
        if (delay,value)>(best['delay_regret'],best['value']):
            best={'value':value,'delay_regret':delay,'cell':cell,'occupied_probability':q}
    cost=p.sensing_cost+p.plan_cost*calls+p.scarcity_cost/max(1,remaining)
    counts={**graph['operation_counts'],**rank_counts}
    work=graph['graph_work_units']+sum(rank_counts.values())
    route_set=set(nominal or [])
    scheduler_ns=perf_counter_ns()-scheduler_started
    return {**best,'cost':cost,'net_value':best['delay_regret']-cost,
        'plan_calls':calls,'visible_cells':len(footprint),'nominal_route':nominal,
        'candidate_count':len(candidates),'shortlisted_candidates':[
            {'cell':c,'structural':features[c][0],'topology_class':features[c][1],
             'q_occupied':float(probability[c[1],c[0]]),'on_nominal_route':c in route_set}
            for c in ordered[:3]],
        'graph_analysis_ns':graph_analysis_ns,'graph_vertices':graph['vertices'],
        'graph_edges':graph['edges'],'graph_operation_counts':counts,
        'graph_work_units':work,'graph_work_bound':20*(graph['vertices']+graph['edges']),
        'scheduler_ns':scheduler_ns}
