"""Public-grid topology features and bounded C v2.0b candidate ranking.

This module is isolated from the frozen original and C v2.0 selectors. It uses
only the remembered ternary grid and public planning/sensor configuration.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from time import perf_counter_ns
import math
import numpy as np

from .evi import EVIParameters, visible_cells
from .navigation import plan


@dataclass(frozen=True)
class TopologyEVIParameters:
    max_candidates: int = 3
    sensing_cost: float = .5
    plan_cost: float = .01
    scarcity_cost: float = .5
    failure_cost: float = 80.

    def __post_init__(self):
        if self.max_candidates != 3:
            raise ValueError('C-Topology3 fixes K=3')
        if (not all(math.isfinite(v) and v >= 0 for v in
                    (self.sensing_cost, self.plan_cost, self.scarcity_cost,
                     self.failure_cost)) or self.failure_cost <= 0):
            raise ValueError('Invalid EVI parameters')


_DIRS = ((1, 0), (0, 1), (-1, 0), (0, -1))


def _is_open(grid, cell, unknown):
    x, y = cell
    return (0 <= y < grid.shape[0] and 0 <= x < grid.shape[1]
            and grid[y, x] != 1
            and not (unknown == 'blocked' and grid[y, x] == -1))


def _graph(grid, unknown):
    h, w = grid.shape
    nodes = [(x, y) for y in range(h) for x in range(w)
             if _is_open(grid, (x, y), unknown)]
    node_set = set(nodes)
    adj = {v: tuple((v[0]+dx, v[1]+dy) for dx, dy in _DIRS
                    if (v[0]+dx, v[1]+dy) in node_set) for v in nodes}
    return nodes, adj


def _bfs_dist(adj, start):
    if start not in adj:
        return {}
    dist = {start: 0}
    queue = deque([start])
    while queue:
        u = queue.popleft()
        for v in adj[u]:
            if v not in dist:
                dist[v] = dist[u] + 1
                queue.append(v)
    return dist


def analyze_public_topology(grid, start, goal, unknown='optimistic'):
    """Return Tarjan topology and bounded cell features in O(V+E).

    DFS also emits vertex-biconnected edge blocks. No per-candidate path search
    is performed. Occupied-cell shortcut estimates reuse two terminal BFS maps.
    """
    if unknown not in {'optimistic', 'blocked'}:
        raise ValueError('Invalid unknown handling')
    started = perf_counter_ns()
    nodes, adj = _graph(grid, unknown)
    disc, low, parent, component = {}, {}, {}, {}
    articulation, bridges, blocks = set(), set(), []
    edge_stack = []
    clock = 0
    visits = 0

    def dfs(u, comp_id):
        nonlocal clock, visits
        clock += 1
        disc[u] = low[u] = clock
        component[u] = comp_id
        children = 0
        for v in adj[u]:
            visits += 1
            if v not in disc:
                parent[v] = u
                children += 1
                edge_stack.append((u, v))
                dfs(v, comp_id)
                low[u] = min(low[u], low[v])
                if low[v] > disc[u]:
                    bridges.add(tuple(sorted((u, v))))
                if low[v] >= disc[u]:
                    if u in parent or children > 1:
                        articulation.add(u)
                    block = []
                    while edge_stack:
                        edge = edge_stack.pop()
                        block.append(edge)
                        if edge == (u, v):
                            break
                    if block:
                        blocks.append(tuple(block))
            elif parent.get(u) != v and disc[v] < disc[u]:
                low[u] = min(low[u], disc[v])
                edge_stack.append((u, v))
        return children

    comp_id = 0
    start = tuple(start)
    ordered_nodes = ([start] if start in adj else []) + [n for n in nodes if n != start]
    for node in ordered_nodes:
        if node not in disc:
            comp_id += 1
            dfs(node, comp_id)
            if edge_stack:
                blocks.append(tuple(edge_stack))
                edge_stack.clear()
    goal = tuple(goal)
    separating = set()
    # Root DFS at start's connected component and identify the goal-containing
    # child subtree whose low-link cannot reach the root side after deletion.
    if start in disc and goal in disc and component[start] == component[goal] and start != goal:
        tin, tout = {}, {}
        children_by_parent = {n: [] for n in nodes}
        for v, p in parent.items():
            children_by_parent[p].append(v)
        tick = 0
        def intervals(u):
            nonlocal tick
            tick += 1; tin[u] = tick
            for v in children_by_parent[u]: intervals(v)
            tout[u] = tick
        intervals(start)
        for v in articulation:
            if v in (start, goal):
                continue
            goal_child = next((c for c in children_by_parent[v]
                               if tin[c] <= tin[goal] <= tout[c]), None)
            if goal_child is not None and low[goal_child] >= disc[v]:
                separating.add(v)

    # Contract bridge-connected regions into a bridge forest, then mark the
    # bridges on the unique component path between current position and goal.
    bridge_adj = {n: [] for n in nodes}
    for u, v in bridges:
        bridge_adj[u].append(v); bridge_adj[v].append(u)
    relevant_bridges = set()
    # A BFS in the bridge forest is one linear pass, not one per candidate.
    def bridge_component(seed, assigned):
        stack = [seed]; assigned[seed] = len(assigned)+1
        while stack:
            u = stack.pop()
            for v in adj[u]:
                if tuple(sorted((u, v))) in bridges or v in assigned:
                    continue
                assigned[v] = assigned[seed]
                stack.append(v)
    bridge_region = {}
    for node in nodes:
        if node not in bridge_region:
            bridge_component(node, bridge_region)
    region_adj = {}
    for u, v in bridges:
        a, b = bridge_region[u], bridge_region[v]
        region_adj.setdefault(a, []).append((b, (u, v)))
        region_adj.setdefault(b, []).append((a, (u, v)))
    if start in bridge_region and goal in bridge_region:
        prev = {bridge_region[start]: None}
        q = deque([bridge_region[start]])
        while q and bridge_region[goal] not in prev:
            a = q.popleft()
            for b, edge in region_adj.get(a, ()):
                if b not in prev:
                    prev[b] = (a, edge); q.append(b)
        cur = bridge_region[goal]
        if cur in prev:
            while prev[cur] is not None:
                prior, edge = prev[cur]
                relevant_bridges.add(tuple(sorted(edge)))
                cur = prior

    ds, dg = _bfs_dist(adj, start), _bfs_dist(adj, goal)
    baseline = ds.get(goal, math.inf)
    # Candidate-specific details are later made by constant-degree neighbor
    # scans; the graph traversals themselves are independent of candidate K.
    elapsed = perf_counter_ns() - started
    operations = visits + len(nodes) + 2*sum(len(x) for x in adj.values())
    relevant_bridge_degree={v:0 for e in relevant_bridges for v in e}
    for u,v in relevant_bridges:
        relevant_bridge_degree[u]+=1; relevant_bridge_degree[v]+=1
    relevant_bridge_endpoints=set(relevant_bridge_degree)
    cyclic_block_vertices=set()
    for block in blocks:
        verts={v for edge in block for v in edge}
        if len(verts)>=3 and len(block)>=len(verts):
            cyclic_block_vertices.update(verts)
    return {'nodes': nodes, 'node_set': set(nodes), 'adj': adj, 'component': component,
        'articulation': articulation, 'separating': separating,
        'bridges': bridges, 'relevant_bridges': relevant_bridges,
        'relevant_bridge_endpoints': relevant_bridge_endpoints,
        'relevant_bridge_degree':relevant_bridge_degree,
        'cyclic_block_vertices':cyclic_block_vertices,
        'bridge_region': bridge_region, 'blocks': blocks,
        'ds': ds, 'dg': dg, 'baseline_distance': baseline,
        'elapsed_ns': elapsed, 'operations': operations,
        'vertices': len(nodes), 'edges': sum(map(len, adj.values()))//2}


def _candidate_topology_features(grid, cell, graph, start, goal, route=()):
    x, y = cell
    route_set=route if isinstance(route,set) else set(route)
    if cell in graph['separating']:
        return (0, len(graph['separating']), 0), 'start_goal_separator'
    if cell in graph['node_set']:
        if cell == tuple(goal):
            return (0, len(graph['separating'])+1, 0), 'goal_terminal'
        if cell in graph['separating']:
            return (0, len(graph['separating']), 0), 'start_goal_separator'
        if cell in graph['relevant_bridge_endpoints']:
            incident_count=graph['relevant_bridge_degree'][cell]
            return (2, incident_count, 0), 'relevant_bridge_endpoint'
        if cell in graph['articulation'] and cell in route_set:
            return (3, 1, 0), 'route_articulation_not_terminal_separator'
        if cell in graph['cyclic_block_vertices'] and cell in route_set:
            return (4, 1, 0), 'route_cell_with_alternative_cycle'
        if cell in graph['articulation']:
            return (5, 0, 0), 'irrelevant_articulation'
        return (6, 0, 0), 'other_traversable'
    if cell == tuple(goal):
        return (0, 1, 0), 'occupied_goal_terminal'
    # Currently occupied uncertain cell. A single bounded neighbor pair scan
    # estimates if revealing it free would join terminal components or shorten
    # the best public path. Occupied outcome handling still occurs in EVI.
    neighbors = [(x+dx, y+dy) for dx, dy in _DIRS
                 if (x+dx, y+dy) in graph['node_set']]
    connects_terminals = (tuple(start) in graph['component'] and
        tuple(goal) in graph['component'] and any(
            graph['component'].get(a) == graph['component'][tuple(start)] and
            graph['component'].get(b) == graph['component'][tuple(goal)]
            for a in neighbors for b in neighbors))
    best = math.inf
    for a in neighbors:
        if a not in graph['ds']:
            continue
        for b in neighbors:
            if b in graph['dg']:
                best = min(best, graph['ds'][a]+2+graph['dg'][b])
    gain = (max(0, graph['baseline_distance']-best)
            if math.isfinite(graph['baseline_distance']) and math.isfinite(best)
            else 0)
    if connects_terminals:
        return (1, 1, int(gain)), 'occupied_connectivity_shortcut'
    if gain > 0:
        return (1, 0, int(gain)), 'occupied_distance_shortcut'
    return (5, 0, 0), 'occupied_no_public_shortcut'


def rank_topology_candidates(grid, probability, candidates, graph, start, goal, route=()):
    features = {}
    route_set=set(route)
    for cell in candidates:
        structural, label = _candidate_topology_features(grid, cell, graph, start, goal, route_set)
        q = float(probability[cell[1], cell[0]])
        # Class ascending; severity and path gain descending; uncertainty
        # descending; coordinates ascending for deterministic ties.
        features[cell] = {'structural': structural, 'label': label,
                          'uncertainty': q*(1-q)}
    ordered = sorted(candidates, key=lambda c: (
        features[c]['structural'][0], -features[c]['structural'][1],
        -features[c]['structural'][2], -features[c]['uncertainty'], c[1], c[0]))
    return ordered, features


def information_value_topology(grid, probability, position, goal, yaw,
                               unknown, sensor, remaining, parameters=None):
    """Original V/D and prices, with K=3 public topology shortlist."""
    p = parameters or TopologyEVIParameters()
    if p.max_candidates != 3:
        raise ValueError('C-Topology3 fixes K=3')
    nominal = plan(grid, position, goal, unknown)
    calls = 1
    footprint = visible_cells(grid, position, yaw, **sensor)
    candidates = [c for c in footprint if c != tuple(position) and
                  .05 < float(probability[c[1], c[0]]) < .95]
    graph_started=perf_counter_ns()
    graph = analyze_public_topology(grid, position, goal, unknown)
    ordered, features = rank_topology_candidates(grid, probability, candidates,
                                                  graph, position, goal, nominal or [])
    graph_elapsed=perf_counter_ns()-graph_started
    graph_operations=graph['operations']+20*len(candidates)+len(nominal or [])
    best = {'value': 0., 'delay_regret': 0., 'cell': None,
            'occupied_probability': None}
    for cell in ordered[:3]:
        routes = []
        for outcome in (0, 1):
            cf = grid.copy(); cf[cell[1], cell[0]] = outcome
            routes.append(plan(cf, position, goal, unknown)); calls += 1
        def loss(route, occupied):
            if not route:
                return p.failure_cost
            return len(route)-1 + (p.failure_cost if occupied and cell in route else 0)
        q = float(probability[cell[1], cell[0]])
        losses = [[loss(route, outcome) for outcome in (0, 1)]
                  for route in routes]
        before = min((1-q)*row[0]+q*row[1] for row in losses)
        after = (1-q)*min(row[0] for row in losses)+q*min(row[1] for row in losses)
        value = max(0., before-after)
        actions = [tuple(route[1]) if len(route) > 1 else None for route in routes]
        delay = value*min(q, 1-q) if actions[0] != actions[1] else 0.
        if (delay, value) > (best['delay_regret'], best['value']):
            best = {'value': value, 'delay_regret': delay, 'cell': cell,
                    'occupied_probability': q}
    cost = p.sensing_cost+p.plan_cost*calls+p.scarcity_cost/max(1, remaining)
    selected = ordered[:3]
    return {**best, 'cost': cost, 'net_value': best['delay_regret']-cost,
        'plan_calls': calls, 'visible_cells': len(footprint),
        'nominal_route': nominal, 'candidate_count': len(candidates),
        'shortlisted_candidates': [{'cell': c,
            'score': features[c]['structural'], 'topology_class': features[c]['label'],
            'uncertainty': features[c]['uncertainty'],
            'q_occupied': float(probability[c[1], c[0]]),
            'on_nominal_route': c in set(nominal or [])} for c in selected],
        'graph_analysis_ns': graph_elapsed,
        'graph_vertices': graph['vertices'], 'graph_edges': graph['edges'],
        'graph_operation_count': graph_operations,
        'graph_work_bound': 20*(graph['vertices']+graph['edges'])}


def exhaustive_public_values(grid, probability, position, goal, unknown,
                             candidates, parameters=None, remaining=10):
    """Offline diagnostic only: evaluate every eligible cell with frozen V/D."""
    p = parameters or EVIParameters(max_candidates=3)
    nominal = plan(grid, position, goal, unknown)
    rows = []
    calls = 1
    for cell in candidates:
        routes = []
        for outcome in (0, 1):
            cf = grid.copy(); cf[cell[1], cell[0]] = outcome
            routes.append(plan(cf, position, goal, unknown)); calls += 1
        q = float(probability[cell[1], cell[0]])
        def loss(route, occupied):
            if not route: return p.failure_cost
            return len(route)-1+(p.failure_cost if occupied and cell in route else 0)
        rows_by_outcome = [[loss(r, o) for o in (0, 1)] for r in routes]
        before = min((1-q)*r[0]+q*r[1] for r in rows_by_outcome)
        after = (1-q)*min(r[0] for r in rows_by_outcome)+q*min(r[1] for r in rows_by_outcome)
        value = max(0., before-after)
        actions = [tuple(r[1]) if len(r)>1 else None for r in routes]
        delay = value*min(q,1-q) if actions[0] != actions[1] else 0.
        rows.append({'cell': cell, 'V': value, 'D': delay, 'q': q})
    common_cost = p.sensing_cost+p.plan_cost*7+p.scarcity_cost/max(1, remaining)
    return rows, common_cost, calls
