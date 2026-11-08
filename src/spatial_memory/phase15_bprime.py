"""Evaluator-only B′ primitives, pinned to phase1.5-v0.4-BPRIME-1.

No audit driver or navigation entry point. Injected streams permit hand-authored
synthetic fixtures without drawing any registered population identity. Existing
samplers and exact topology operations are imported unchanged.
"""
from dataclasses import dataclass
import hashlib
import numpy as np
from . import phase15_generators as legacy
from . import phase15_topology as topology
from .phase15_nauty import Backend, NAMESPACE as CANONICAL_NAMESPACE

VERSION = 'phase1.5-v0.4-BPRIME-1'
MECHANISMS = ('R', 'BP', 'V', 'M')
# Stable seed blocks: never renumber previously generated M identities.
MECHANISM_SEED_OFFSETS = {'R': 0, 'BP': 10_000, 'V': 20_000, 'M': 30_000}
# Methods used for new spatial-memory experiments; historical seed identities stay valid.
ACTIVE_MECHANISMS = ('R', 'BP', 'M')

PARTITIONS = {'fit': (80_000_000, 12), 'calibration': (80_100_000, 6),
              'selection': (80_200_000, 6)}
PURPOSES = ('partition', 'tree', 'chords', 'doors', 'geometry', 'start-goal',
            'dynamics-0', 'dynamics-1')


class IntegrityError(ValueError):
    """Stop: malformed construction, changed evidence, or unsupported identity."""


def active_quota_complete(credits, partition):
    """Check the three active environment families without generating candidates.

    Historical candidate identities and seed allocations are intentionally stable.
    """
    development_partition(partition)
    target = PARTITIONS[partition][1]
    return all(credits.get(method, 0) == target for method in ACTIVE_MECHANISMS)


def development_partition(partition):
    if partition not in PARTITIONS:
        raise IntegrityError('Development partition required; reserved access denied')
    return partition


def seed_for(partition, mechanism, index):
    development_partition(partition)
    if mechanism not in MECHANISMS or type(index) is not int or not 0 <= index < 10_000:
        raise IntegrityError('Invalid mechanism or exhausted 10000-candidate allowance')
    return PARTITIONS[partition][0] + MECHANISM_SEED_OFFSETS[mechanism] + index


@dataclass(frozen=True)
class Identity:
    partition: str
    mechanism: str
    seed: int

    def __post_init__(self):
        base = seed_for(self.partition, self.mechanism, 0)
        if type(self.seed) is not int or not base <= self.seed < base+10_000:
            raise IntegrityError('Seed outside development mechanism block')

    @property
    def root(self):
        return f'{VERSION}:{self.partition}:{self.mechanism}:{self.seed}'


class Stream(legacy.Stream):
    """Exact inherited integer/permutation laws with new framing and counters."""
    def __init__(self, identity, purpose):
        if not isinstance(identity, Identity):
            raise IntegrityError('Validated development identity required')
        allowed = ({'partition','tree','chords','doors','start-goal','dynamics-0','dynamics-1'}
                   if identity.mechanism=='BP' else {'geometry','start-goal','dynamics-0','dynamics-1'})
        if purpose not in allowed:
            raise IntegrityError('Purpose does not belong to mechanism')
        self._initialize(identity.seed, purpose)

    @classmethod
    def synthetic(cls, seed, purpose):
        # Explicit raw-word fixtures only; no registered old/new seed is admitted.
        if type(seed) is not int or not 0 <= seed < 10_000:
            raise IntegrityError('Synthetic stream requires a fixture seed below 10000')
        obj = cls.__new__(cls)
        obj._initialize(seed, purpose)
        return obj

    def _initialize(self, seed, purpose):
        if purpose not in PURPOSES or np.__version__ != '2.2.6':
            raise IntegrityError('Unpinned purpose or NumPy version')
        fields = (VERSION, str(seed), purpose)
        framed = b''.join(len(f.encode()).to_bytes(4, 'little')+f.encode() for f in fields)
        self.identity = hashlib.sha256(framed).hexdigest()
        self.raw = np.random.Philox(key=int.from_bytes(bytes.fromhex(self.identity)[:16], 'little'))
        self.words = 0
        self.bounds = []

    def integer(self, n):
        if type(n) is not int or not 0 < n <= 2**64:
            raise IntegrityError('Invalid uniform bound')
        self.bounds.append(n)
        ceiling = 2**64 - 2**64 % n
        while True:
            value = int(self.raw.random_raw())
            self.words += 1
            if not 0 <= value < 2**64:
                raise IntegrityError('Invalid raw word')
            if value < ceiling:
                return value % n

    def counters(self):
        return dict(identity=self.identity, words=self.words, bounds=list(self.bounds))


def partition(stream):
    desired = stream.choose((12, 16, 20))
    leaves = [(0, 0, 5, 5)]
    splits = []
    while len(leaves) < desired:
        eligible = sorted(r for r in leaves if r[0] < r[2] or r[1] < r[3])
        if not eligible:
            raise IntegrityError('Construction invariant: premature unsplittability')
        rect = stream.choose(eligible)
        x0, y0, x1, y1 = rect
        axis = stream.choose([a for a in (0, 1) if rect[a] < rect[a+2]])
        cut = stream.choose(list(range(rect[axis]+1, rect[axis+2]+1)))
        if axis == 0:
            children = [(x0, y0, cut-1, y1), (cut, y0, x1, y1)]
        else:
            children = [(x0, y0, x1, cut-1), (x0, cut, x1, y1)]
        leaves.remove(rect)
        leaves.extend(children)
        splits.append(dict(rect=rect, axis=axis, cut=cut, children=children))
    return sorted(leaves), dict(desired=desired, splits=splits)


def validate_rooms(rooms):
    rooms = [tuple(r) for r in rooms]
    if rooms != sorted(rooms) or len(set(rooms)) != len(rooms):
        raise IntegrityError('Rooms must have unique sorted IDs')
    seen = set()
    for x0, y0, x1, y1 in rooms:
        if not all(type(v) is int for v in (x0,y0,x1,y1)) or not (0<=x0<=x1<6 and 0<=y0<=y1<6):
            raise IntegrityError('Malformed macro rectangle')
        cells = {(x,y) for x in range(x0,x1+1) for y in range(y0,y1+1)}
        if seen & cells:
            raise IntegrityError('Overlapping rooms')
        seen |= cells
    if seen != {(x,y) for x in range(6) for y in range(6)}:
        raise IntegrityError('Incomplete partition')
    return rooms


def door_options(a, b):
    ax,ay,az,aw = a
    bx,by,bz,bw = b
    options = []
    if az+1 == bx or bz+1 == ax:
        wall = 4*max(ax,bx)
        options = [(wall,4*j+2) for j in range(max(ay,by),min(aw,bw)+1)]
    elif aw+1 == by or bw+1 == ay:
        wall = 4*max(ay,by)
        options = [(4*i+2,wall) for i in range(max(ax,bx),min(az,bz)+1)]
    return options


def adjacency(rooms):
    rooms = validate_rooms(rooms)
    return [(i,j) for i in range(len(rooms)) for j in range(i+1,len(rooms))
            if door_options(rooms[i],rooms[j])]


def connections(rooms, tree_stream, chord_stream):
    edges = adjacency(rooms)
    parent = list(range(len(rooms)))
    def root(i):
        while parent[i] != i:
            i = parent[i]
        return i
    tree = []
    for u,v in tree_stream.permutation(edges):
        a,b = root(u),root(v)
        if a != b:
            parent[a] = b
            tree.append((u,v))
    if len(tree) != len(rooms)-1:
        raise IntegrityError('Construction invariant: disconnected adjacency')
    unused = sorted(set(edges)-set(tree))
    k = chord_stream.integer(len(unused)+1)
    extra = chord_stream.permutation(unused)[:k]
    selected = sorted(tree+extra)
    return selected, dict(adjacency=edges, tree=tree, unused=unused, K=k,
                          extra=extra, available_rank=len(unused))


def rasterize(rooms, selected, door_stream):
    rooms = validate_rooms(rooms)
    if list(selected) != sorted(set(selected)) or not set(selected) <= set(adjacency(rooms)):
        raise IntegrityError('Invalid selected edge set')
    free = {(x,y) for a,b,c,d in rooms for y in range(4*b+1,4*d+4)
            for x in range(4*a+1,4*c+4)}
    doors = []
    for i,j in selected:
        cell = door_stream.choose(door_options(rooms[i], rooms[j]))
        free.add(cell)
        doors.append(dict(edge=(i,j), cell=cell))
    if (len(legacy.components(free)) != 1 or not 324 <= len(free) <= 529
        or any(not (1<=x<=23 and 1<=y<=23) for x,y in free)):
        raise IntegrityError('Construction invariant: geometry')
    for row in doors:
        x,y = row['cell']
        along = ((x-1,y),(x+1,y)) if x%4==0 else ((x,y-1),(x,y+1))
        across = ((x,y-1),(x,y+1)) if x%4==0 else ((x-1,y),(x+1,y))
        if not all(c in free for c in along) or any(c in free for c in across):
            raise IntegrityError('Construction invariant: door isolation')
    quotient, detail = topology.raster_quotient(free)
    expected = topology.suppress(topology.graph_from_edges(len(rooms),selected))
    # Node IDs may differ; exact correspondence is independently tested. The
    # invariant here is room count and cycle rank, not a heuristic isomorphism.
    if detail['room_regions'] != len(rooms) or cycle_rank(quotient) != cycle_rank(expected):
        raise IntegrityError('Construction invariant: quotient')
    return frozenset(free), dict(doors=doors, room_count=len(rooms),
                                selected_graph_vertices=len(rooms), **detail)


def construct_bp(streams):
    """Single construction with explicit streams, also usable by scripted fixtures."""
    if set(streams) != {'partition','tree','chords','doors'}:
        raise IntegrityError('Exactly four construction streams required')
    rooms, split_detail = partition(streams['partition'])
    selected, graph_detail = connections(rooms, streams['tree'], streams['chords'])
    free, raster_detail = rasterize(rooms,selected,streams['doors'])
    return free, dict(rooms=rooms, selected=selected, **split_detail, **graph_detail,
                      **raster_detail)


def geometry(identity, *, stream_factory=Stream):
    """One development geometry; no iteration, audit, pair or schedule execution."""
    if not isinstance(identity, Identity):
        raise IntegrityError('Validated identity required')
    if identity.mechanism == 'BP':
        streams = {p:stream_factory(identity,p) for p in ('partition','tree','chords','doors')}
        free, detail = construct_bp(streams)
    else:
        streams = {'geometry':stream_factory(identity,'geometry')}
        if identity.mechanism == 'V':
            free,detail = legacy.generate_v(streams['geometry'],'lex_yx')
        else:
            free,detail = {'R':legacy.generate_r,'M':legacy.generate_m}[identity.mechanism](streams['geometry'])
        if any(not (1<=x<=23 and 1<=y<=23) for x,y in free):
            raise legacy.Rejected('outer_ring')
        if len(free)<80:
            raise legacy.Rejected('free_count')
        if not .15<=1-len(free)/625<=.85:
            raise legacy.Rejected('density')
        if len(legacy.components(free))!=1:
            raise legacy.Rejected('connectivity')
    detail = dict(detail, ancestral_roots=[identity.root],
                  stream_counters={p:s.counters() for p,s in streams.items()})
    return legacy.Geometry(identity.partition,identity.mechanism,identity.seed,frozenset(free),detail)


def choose_pair(free, stream):
    cells = sorted(free,key=legacy.row_key)
    pairs = []
    for start in cells:
        distances = legacy.distances(free,start)
        pairs.extend((start,goal,distances[goal]) for goal in cells
                     if goal in distances and 12<=distances[goal]<=40
                     and abs(start[0]-goal[0])+abs(start[1]-goal[1])>=5)
    if not pairs:
        raise legacy.Rejected('no_start_goal_pair')
    return stream.choose(pairs)


def cycle_rank(graph):
    pending = set(range(graph.n))
    count = 0
    while pending:
        count += 1
        todo = [pending.pop()]
        while todo:
            u = todo.pop()
            for v in list(pending):
                if graph.matrix[u][v]:
                    pending.remove(v)
                    todo.append(v)
    edges = sum(graph.matrix[i][j] for i in range(graph.n) for j in range(i,graph.n))
    return edges-graph.n+count


def describe(free, backend=None):
    """Production keys only from the unchanged guarded C3 backend; no fallback."""
    graph, detail = topology.raster_quotient(free)
    owned = backend is None
    backend = Backend() if owned else backend
    if not isinstance(backend,Backend):
        raise IntegrityError('Approved guarded C3 backend required')
    measurements = []
    try:
        keys = backend.near_certificates(graph,measurements=measurements)
        exact = backend.exact_certificate(graph)
        if exact not in keys or any(k[0]!=CANONICAL_NAMESPACE for k in keys):
            raise IntegrityError('Invalid canonical namespace or self key')
        return dict(matrix=graph.matrix, exact=exact, keys=keys,
                    raster=topology.raster_certificate(free), measurements=measurements,
                    cycle_rank=cycle_rank(graph), **detail)
    finally:
        if owned:
            backend.close()


def build_schedule(geo, start, goal, stream):
    """Unchanged baseline schedule body, injected stream; fixed retry rule only."""
    retry_rule = 'fixed'
    category = stream.choose(legacy.CATEGORIES)
    protected = {start,goal}; failures = []
    if category=='none': return dict(category=category,attempts=0,failures=[],events=[],initial=[],positions=[])
    fixed_onset = None if category=='moving' else 2+stream.integer(11)
    fixed_length = stream.choose((4,6,8)) if category=='moving' else stream.choose((2,3,4))
    for attempt in range(1,129):
        length = fixed_length; onset = fixed_onset
        if category!='moving' and retry_rule=='redraw' and attempt>1:
            onset = 2+stream.integer(11); length = stream.choose((2,3,4))
        try:
            f = legacy.grow_path(geo.free,protected,length,stream)
            g = legacy.grow_path(geo.free,protected|set(f),length,stream) if category=='swap' else []
            initial = f if category in ('removal','swap') else []
            final = f if category=='addition' else g if category=='swap' else []
            for blocked in (initial,final):
                if goal not in legacy.distances(set(geo.free)-set(blocked),start):
                    raise legacy.Rejected('dynamic_static_connectivity')
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
        except legacy.Rejected as error:
            failures.append(str(error))
    raise legacy.DynamicLimit(f'{category}: 128 proposals exhausted; do not replace category/world')



def _check_geometry(identity, geo):
    if not isinstance(identity, Identity) or (geo.partition,geo.mechanism,geo.seed)!=(identity.partition,identity.mechanism,identity.seed):
        raise IntegrityError('Geometry and development stream identity disagree')


def pair_for(identity, geo):
    _check_geometry(identity,geo)
    stream = Stream(identity,'start-goal')
    return choose_pair(geo.free,stream),stream.counters()


def schedule_for(identity, geo, start, goal, schedule):
    _check_geometry(identity,geo)
    if type(schedule) is not int or schedule not in (0,1):
        raise IntegrityError('Exactly two schedule identities')
    stream = Stream(identity,f'dynamics-{schedule}')
    result = build_schedule(geo,start,goal,stream)
    return result,stream.counters()


def geometry_payload(geo, start, goal, distance, schedules, lineage):
    from .phase15_bprime_protocol import Lineage
    if not isinstance(lineage,Lineage):
        raise IntegrityError('Explicit complete ancestry required for serialization')
    known = frozenset(geo.construction.get('ancestral_roots',()))
    if not known <= lineage.roots:
        raise IntegrityError('Geometry ancestry cannot be erased by a new identity')
    roots = sorted(lineage.roots)
    result = legacy.artifact(geo,start,goal,distance,schedules)
    result.update(version=VERSION,lineage=roots[0] if len(roots)==1 else None,
                  ancestral_roots=roots)
    return result


def artifact(identity, geo, start, goal, distance, schedules, *, lineage):
    _check_geometry(identity,geo)
    return geometry_payload(geo,start,goal,distance,schedules,lineage)
