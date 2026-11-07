"""Evaluator-only Phase 1.5 v0.2 artifact constructors. No policy execution.

Specification conflicts require explicit resolutions; no scientific fallback.
"""
from collections import deque
from dataclasses import dataclass
import hashlib
import json
import numpy as np

SIZE = 25
MECHANISMS = ('R', 'B', 'V', 'M')
PARTITIONS = {'fit': (50_000_000, 12), 'calibration': (50_100_000, 6),
              'selection': (50_200_000, 6)}
CATEGORIES = ('none', 'addition', 'removal', 'swap', 'moving')
NSEW = ((0,-1), (1,0), (0,1), (-1,0))
LEX = ((0,-1), (-1,0), (1,0), (0,1))


class SpecificationAmbiguity(ValueError):
    pass


class Rejected(ValueError):
    pass


class DynamicLimit(RuntimeError):
    pass


def row_key(cell):
    return cell[1], cell[0]


def neighbors(cell, directions=NSEW):
    x,y = cell
    return [(x+dx,y+dy) for dx,dy in directions]


def seed_for(partition, mechanism, index):
    if partition not in PARTITIONS or mechanism not in MECHANISMS:
        raise ValueError('Only the three development partitions are admitted')
    if type(index) is not int or not 0 <= index < 10_000:
        raise ValueError('Frozen candidate limit is 10000')
    return PARTITIONS[partition][0]+MECHANISMS.index(mechanism)*10_000+index


def validate_identity(partition, mechanism, seed):
    base = seed_for(partition,mechanism,0)
    if type(seed) is not int or not base <= seed < base+10_000:
        raise ValueError('Seed does not belong to development mechanism block')


class Stream:
    """Exact rational Bernoulli and uniform rejection from raw Philox words."""
    def __init__(self, seed, purpose):
        fields = ('phase1.5-v0.2-artifacts', str(seed), purpose)
        framed = b''.join(len(f.encode()).to_bytes(4,'little')+f.encode() for f in fields)
        self.identity = hashlib.sha256(framed).hexdigest()
        self.raw = np.random.Philox(key=int.from_bytes(bytes.fromhex(self.identity)[:16],'little'))

    def integer(self, n):
        if type(n) is not int or n <= 0 or n > 2**64:
            raise ValueError('Invalid uniform integer bound')
        ceiling = 2**64-(2**64 % n)
        while True:
            value = int(self.raw.random_raw())
            if value < ceiling:
                return value % n

    def choose(self, values):
        return values[self.integer(len(values))]

    def bernoulli(self, numerator, denominator):
        if not 0 <= numerator <= denominator:
            raise ValueError('Invalid rational probability')
        return self.integer(denominator) < numerator

    def permutation(self, values):
        values = list(values)
        for i in range(len(values)-1,0,-1):
            j = self.integer(i+1)
            values[i],values[j] = values[j],values[i]
        return values


def components(cells):
    remaining = set(cells)
    result = []
    while remaining:
        root = min(remaining,key=row_key)
        seen = {root}; queue = deque([root]); remaining.remove(root)
        while queue:
            for nxt in neighbors(queue.popleft()):
                if nxt in remaining:
                    remaining.remove(nxt); seen.add(nxt); queue.append(nxt)
        result.append(seen)
    return result


def distances(cells, root):
    if root not in cells:
        return {}
    result = {root:0}; queue = deque([root])
    while queue:
        cell = queue.popleft()
        for nxt in neighbors(cell):
            if nxt in cells and nxt not in result:
                result[nxt] = result[cell]+1; queue.append(nxt)
    return result


def lattice(n):
    edges = []
    for y in range(n):
        for x in range(n):
            if x+1 < n: edges.append(((x,y),(x+1,y)))
            if y+1 < n: edges.append(((x,y),(x,y+1)))
    return sorted(edges,key=lambda e:(row_key(e[0]),row_key(e[1])))


def tree_with_chords(edges, stream, numerator, denominator):
    parent = {}
    def find(v):
        parent.setdefault(v,v)
        if parent[v] != v: parent[v] = find(parent[v])
        return parent[v]
    selected, unused = [], []
    for a,b in stream.permutation(edges):
        u,v = find(a),find(b)
        if u != v:
            parent[u] = v; selected.append((a,b))
        else:
            unused.append((a,b))
    # Canonical endpoint order, independently sampled Bernoulli for each unused edge.
    def edge_key(edge):
        return tuple(row_key(v) if isinstance(v,tuple) else (v,) for v in edge)
    for edge in sorted(unused,key=edge_key):
        if stream.bernoulli(numerator,denominator): selected.append(edge)
    return selected


def generate_r(stream):
    free = {(6*i+x,6*j+y) for i in range(4) for j in range(4)
            for x in range(1,6) for y in range(1,6)}
    edges = tree_with_chords(lattice(4),stream,3,10)
    doors = []
    for a,b in sorted(edges,key=lambda e:(row_key(e[0]),row_key(e[1]))):
        if a[0] != b[0]:
            cell = (6*max(a[0],b[0]),6*a[1]+1+stream.integer(5))
        else:
            cell = (6*a[0]+1+stream.integer(5),6*max(a[1],b[1]))
        free.add(cell); doors.append(cell)
    return free,dict(room_edges=edges,doors=doors)


def generate_b(stream):
    free = {(x,y) for y in range(1,24) for x in range(1,24)}
    desired = stream.choose((12,16,20)); leaves = [(1,1,23,23)]; splits = []
    while len(leaves) < desired:
        eligible = sorted(r for r in leaves if r[2]-r[0]>=6 or r[3]-r[1]>=6)
        if not eligible: raise Rejected('bsp_unsplittable')
        rect = stream.choose(eligible); x0,y0,x1,y1 = rect
        axes = [a for a in (0,1) if (x1-x0 if a==0 else y1-y0)>=6]
        axis = stream.choose(axes)
        if axis == 0:
            wall = x0+3+stream.integer(x1-x0-5)
            door = (wall,y0+stream.integer(y1-y0+1))
            free.difference_update((wall,y) for y in range(y0,y1+1)); free.add(door)
            children = [(x0,y0,wall-1,y1),(wall+1,y0,x1,y1)]
        else:
            wall = y0+3+stream.integer(y1-y0-5)
            door = (x0+stream.integer(x1-x0+1),wall)
            free.difference_update((x,wall) for x in range(x0,x1+1)); free.add(door)
            children = [(x0,y0,x1,wall-1),(x0,wall+1,x1,y1)]
        leaves.remove(rect); leaves.extend(children)
        splits.append(dict(rect=rect,axis=axis,wall=wall,door=door))
    return free,dict(desired=desired,leaves=sorted(leaves),splits=splits)


def shortest_core_path(core_a, core_b, allowed, tie_rule):
    if tie_rule not in ('bfs_nesw','lex_yx'):
        raise SpecificationAmbiguity('V: lexicographic path versus NSEW BFS conflict')
    directions = NSEW if tie_rule=='bfs_nesw' else LEX
    queue = deque(sorted(core_a,key=row_key)); previous = {c:None for c in queue}
    target = None
    while queue:
        c = queue.popleft()
        if c in core_b: target = c; break
        for nxt in neighbors(c,directions):
            if nxt in allowed and nxt not in previous:
                previous[nxt] = c; queue.append(nxt)
    if target is None: raise Rejected('voronoi_no_corridor')
    path = []
    while target is not None:
        path.append(target); target = previous[target]
    return list(reversed(path))


def generate_v(stream, tie_rule=None):
    if tie_rule is None:
        raise SpecificationAmbiguity('V: lexicographic path versus NSEW BFS conflict')
    interior = sorted(((x,y) for y in range(1,24) for x in range(1,24)),key=row_key)
    count = stream.choose((12,16,20)); seeds = stream.permutation(interior)[:count]
    if any(abs(a[0]-b[0])+abs(a[1]-b[1])<4 for i,a in enumerate(seeds) for b in seeds[i+1:]):
        raise Rejected('voronoi_seed_separation')
    seeds = sorted(seeds,key=row_key)
    labels = {c:min(range(count),key=lambda i:(abs(c[0]-seeds[i][0])+abs(c[1]-seeds[i][1]),row_key(seeds[i]))) for c in interior}
    regions = [{c for c in interior if labels[c]==i} for i in range(count)]
    cores = []
    for i,region in enumerate(regions):
        if len(components(region)) != 1: raise Rejected('voronoi_region_connectivity')
        core = {c for c in region if all(labels.get(n)==i for n in neighbors(c))}
        if not core or len(components(core))!=1 or not any(
            {(x,y),(x+1,y),(x,y+1),(x+1,y+1)}<=core for x,y in core):
            raise Rejected('voronoi_core')
        cores.append(core)
    adjacent = set()
    for c,i in labels.items():
        for nxt in neighbors(c):
            j = labels.get(nxt,i)
            if i != j: adjacent.add(tuple(sorted((i,j))))
    chosen = set(tree_with_chords(sorted(adjacent),stream,1,4))
    free = set().union(*cores)
    for a,b in sorted(chosen):
        free.update(shortest_core_path(cores[a],cores[b],regions[a]|regions[b],tie_rule))
    all_core = set().union(*cores); touches = set()
    owner = {c:i for i,core in enumerate(cores) for c in core}
    for comp in components(free-all_core):
        ids = sorted({owner[n] for c in comp for n in neighbors(c) if n in owner})
        touches.update((a,b) for ii,a in enumerate(ids) for b in ids[ii+1:])
    for c,i in owner.items():
        touches.update(tuple(sorted((i,owner[n]))) for n in neighbors(c) if n in owner and owner[n]!=i)
    if touches != chosen: raise Rejected('voronoi_unintended_adjacency')
    return free,dict(seeds=seeds,region_edges=sorted(chosen),tie_rule=tie_rule)


def generate_m(stream):
    edges = tree_with_chords(lattice(11),stream,3,20)
    free = {(2+2*x,2+2*y) for y in range(11) for x in range(11)}
    for a,b in edges:
        free.add((2+a[0]+b[0],2+a[1]+b[1]))
    return free,dict(coarse_edges=edges)


@dataclass(frozen=True)
class Geometry:
    partition: str
    mechanism: str
    seed: int
    free: frozenset
    construction: dict

    def public_domain(self, start, goal):
        return dict(width=25,height=25,start=list(start),goal=list(goal),
                    occupied_outer_ring=True,start_goal_always_free=True)


def geometry(partition, mechanism, seed, *, v_tie_rule=None):
    validate_identity(partition,mechanism,seed)
    stream = Stream(seed,'geometry')
    if mechanism == 'V': free,detail = generate_v(stream,v_tie_rule)
    else: free,detail = {'R':generate_r,'B':generate_b,'M':generate_m}[mechanism](stream)
    if any(not (1<=x<=23 and 1<=y<=23) for x,y in free): raise Rejected('outer_ring')
    if len(free)<80: raise Rejected('free_count')
    if not .15 <= 1-len(free)/625 <= .85: raise Rejected('density')
    if len(components(free)) != 1: raise Rejected('connectivity')
    return Geometry(partition,mechanism,seed,frozenset(free),detail)


def choose_pair(geo):
    cells = sorted(geo.free,key=row_key); eligible = []
    for start in cells:
        d = distances(geo.free,start)
        eligible.extend((start,goal,d[goal]) for goal in cells if
                        12<=d[goal]<=40 and abs(start[0]-goal[0])+abs(start[1]-goal[1])>=5)
    if not eligible: raise Rejected('no_start_goal_pair')
    return Stream(geo.seed,'start-goal').choose(eligible)


def grow_path(free, protected, length, stream):
    eligible = sorted(set(free)-set(protected),key=row_key)
    if not eligible: raise Rejected('empty_footprint')
    path = [stream.choose(eligible)]
    while len(path)<length:
        available = [c for c in neighbors(path[-1]) if c in free and c not in protected and c not in path]
        if not available: raise Rejected('footprint_dead_end')
        path.append(stream.choose(available))
    return path


def dynamic_schedule(geo, start, goal, schedule, *, retry_rule=None):
    if schedule not in (0,1): raise ValueError('Exactly two schedule identities')
    stream = Stream(geo.seed,f'dynamics-{schedule}')
    category = stream.choose(CATEGORIES)
    if category in ('addition','removal','swap') and retry_rule not in ('fixed','redraw'):
        raise SpecificationAmbiguity('Dynamics: onset/length sampling across retries is unspecified')
    protected = {start,goal}; failures = []
    if category=='none': return dict(category=category,attempts=0,failures=[],events=[],initial=[],positions=[])
    fixed_onset = None if category=='moving' else 2+stream.integer(11)
    fixed_length = stream.choose((4,6,8)) if category=='moving' else stream.choose((2,3,4))
    for attempt in range(1,129):
        length = fixed_length; onset = fixed_onset
        if category!='moving' and retry_rule=='redraw' and attempt>1:
            onset = 2+stream.integer(11); length = stream.choose((2,3,4))
        try:
            f = grow_path(geo.free,protected,length,stream)
            g = grow_path(geo.free,protected|set(f),length,stream) if category=='swap' else []
            initial = f if category in ('removal','swap') else []
            final = f if category=='addition' else g if category=='swap' else []
            for blocked in (initial,final):
                if goal not in distances(set(geo.free)-set(blocked),start):
                    raise Rejected('dynamic_static_connectivity')
            events = []
            if category in ('removal','swap'):
                events += [dict(step=onset,action='remove',cell=c) for c in f]
            if category in ('addition','swap'):
                events += [dict(step=onset,action='add',cell=c) for c in (g if category=='swap' else f)]
            positions = []; dwells = []
            if category=='moving':
                if stream.bernoulli(1,2): f.reverse()
                index=0; direction=1
                while len(positions)<81:
                    dwell=stream.choose((2,3,4) if not positions else (2,3,4,5,6))
                    dwells.append(dwell); positions.extend([f[index]]*dwell)
                    if index==len(f)-1: direction=-1
                    elif index==0: direction=1
                    index += direction
                positions=positions[:81]
            return dict(category=category,attempts=attempt,failures=failures,
                        initial=initial,events=events,positions=positions,
                        footprint=f,other_footprint=g,onset=onset,length=length,dwells=dwells)
        except Rejected as error:
            failures.append(str(error))
    raise DynamicLimit(f'{category}: 128 proposals exhausted; do not replace category/world')


def artifact(geo, start, goal, pair_distance, schedules):
    """Private archive serialization, never a future scheduler input."""
    return dict(partition=geo.partition,mechanism=geo.mechanism,seed=geo.seed,
                lineage=f'{geo.mechanism}:{geo.seed}',width=25,height=25,
                free=sorted(geo.free,key=row_key),construction=geo.construction,
                start=start,goal=goal,distance=pair_distance,schedules=schedules,
                public_domain=None if start is None or goal is None else geo.public_domain(start,goal))


def canonical_bytes(data):
    return json.dumps(data,sort_keys=True,separators=(',',':')).encode()
