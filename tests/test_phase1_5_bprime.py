"""Deterministic, explicitly constructed fixtures only. No population draws.

Do not run historical suites here: some of those construct registered worlds.
Synthetic oracle keys have a different namespace from production C3 keys.
"""
from collections import Counter, deque
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
import gzip
import hashlib
from itertools import permutations, combinations
import json
from pathlib import Path
import pytest
from spatial_memory import phase15_bprime as bp
from spatial_memory import phase15_bprime_protocol as protocol
from spatial_memory import phase15_bprime_store as storage
from spatial_memory import phase15_generators as old
from spatial_memory import phase15_topology as top
from spatial_memory.phase15_bprime_records import graph_fixture_evidence
from bprime_test_support import binding_for, toy_store, fixture


@pytest.fixture(autouse=True)
def forbid_population_streams_and_entrypoints(monkeypatch):
    def deny(*args,**kwargs):
        pytest.fail('Population RNG/geometry is forbidden in this synthetic suite')
    monkeypatch.setattr(bp.Stream,'__init__',deny)
    monkeypatch.setattr(old.Stream,'__init__',deny)
    monkeypatch.setattr(bp,'geometry',deny)
    monkeypatch.setattr(old,'geometry',deny)


class MathIndex(protocol.AdmissionIndex):
    """Mathematical graph fixtures, never attest production world completeness."""
    def __init__(self):super().__init__(synthetic=True)
    def admit(self,record,*,complete=False):
        return super().admit(record,evidence=graph_fixture_evidence(record,complete))


class Tape(old.Stream):
    """Hand-written uniform indices; never initializes a pseudorandom generator."""
    def __init__(self, values):
        self.values = iter(values)
        self.bounds = []
        self.choices = []

    def integer(self, n):
        value = next(self.values)
        assert type(value) is int and 0<=value<n, (value,n)
        self.bounds.append(n)
        return value

    def choose(self, values):
        self.choices.append(tuple(values))
        return values[self.integer(len(values))]


def zeros():
    return Tape([0]*2000)


def flood(cells, start):
    seen = {start}
    todo = deque([start])
    while todo:
        x,y = todo.popleft()
        for cell in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)):
            if cell in cells and cell not in seen:
                seen.add(cell)
                todo.append(cell)
    return seen


def independent_distances(cells, start):
    seen = {start:0}
    layer = {start}
    while layer:
        nxt = {(x+dx,y+dy) for x,y in layer for dx,dy in ((1,0),(-1,0),(0,1),(0,-1))}
        nxt = (nxt & cells)-seen.keys()
        distance = max(seen.values())+1
        seen.update({c:distance for c in nxt})
        layer = nxt
    return seen


def grid_rooms():
    # Explicit 4×5 macro tiling, never sampled.
    xs = [(0,0),(1,1),(2,3),(4,5)]
    ys = [(0,0),(1,1),(2,2),(3,3),(4,5)]
    return sorted((a,b,c,d) for a,c in xs for b,d in ys)


def oracle_certificate(graph):
    # Separate unpruned permutation enumeration, not production canonicalization.
    n = graph.n
    assert n<=7
    return min((n,*(graph.matrix[i][i] for i in order),
                *(graph.matrix[order[i]][order[j]] for i in range(n) for j in range(i+1,n)))
               for order in permutations(range(n)))


class Oracle:
    def exact_certificate(self, graph):
        return ('synthetic-exact-oracle',*oracle_certificate(graph))

    def near_certificates(self, graph, **unused):
        variants = [top.suppress(graph)]
        variants += [top.delete_leaf(graph,u) for u in range(graph.n) if graph.degree(u)==1]
        variants += [top.contract_edge(graph,u,v) for u,v in graph.edges()]
        return frozenset(self.exact_certificate(g) for g in variants)


def record(identity, graph, *, part='synthetic-fit', mechanism='BP', roots=None):
    oracle = Oracle()
    return protocol.Record(identity,part,mechanism,oracle.exact_certificate(graph),
                           oracle.near_certificates(graph),('synthetic-raster',identity),
                           protocol.Lineage(frozenset(roots or (identity,))))


@pytest.mark.parametrize('choice,n',[ (0,12),(1,16),(2,20)])
def test_partition_exact_choices_and_deterministic_order(choice,n):
    tape = Tape([choice]+[0]*(3*(n-1)))
    rooms,detail = bp.partition(tape)
    assert detail['desired']==n and len(rooms)==n
    assert tape.choices[0]==(12,16,20)
    assert tape.choices[1]==((0,0,5,5),)
    assert tape.choices[2]==(0,1)
    assert tape.choices[3]==(1,2,3,4,5)
    assert tape.choices[4]==((0,0,0,5),(1,0,5,5))
    assert tape.choices[5]==(1,)
    assert tape.bounds[:7]==[3,1,2,5,2,1,5]
    assert len(tape.bounds)==1+3*(n-1)
    assert rooms==sorted(rooms)
    covered = [(x,y) for a,b,c,d in rooms for x in range(a,c+1) for y in range(b,d+1)]
    assert len(covered)==len(set(covered))==36
    if n==12:
        expected = [(0,j,0,j) for j in range(6)]
        expected += [(1,j,1,j) for j in range(4)] + [(1,4,1,5),(2,0,5,5)]
        assert rooms==sorted(expected)
    # Uniform first choice gives exact mass 1/3 to each N; no frequency trial.
    assert Fraction(1,len(tape.choices[0]))==Fraction(1,3)


def test_partition_transition_probabilities_exact_small_choice_sets():
    tape = Tape([0]+[0]*33)
    _,detail = bp.partition(tape)
    product = Fraction(1,3)
    for step in range(11):
        leaf,axis,cut = tape.choices[1+3*step:4+3*step]
        product *= Fraction(1,len(leaf)*len(axis)*len(cut))
        selected = detail['splits'][step]
        assert selected['rect']==leaf[0] and selected['axis']==axis[0] and selected['cut']==cut[0]
    assert 0<product<1
    assert sum(Fraction(1,2*5) for _ in range(10))==1  # first axis/cut law


def test_adjacency_independent_macro_boundary_enumeration():
    rooms = grid_rooms()
    owner = {(x,y):i for i,(a,b,c,d) in enumerate(rooms)
             for x in range(a,c+1) for y in range(b,d+1)}
    expected = set()
    for (x,y),i in owner.items():
        for cell in ((x+1,y),(x,y+1)):
            if cell in owner and owner[cell]!=i:
                expected.add(tuple(sorted((i,owner[cell]))))
    assert bp.adjacency(rooms)==sorted(expected)
    assert len(expected)==31 and len(rooms)==20
    assert bp.door_options((0,0,0,0),(1,1,1,1))==[]  # corner only


@pytest.mark.parametrize('k',[0,1,6,12])
def test_kruskal_and_full_unused_permutation_even_zero(k):
    tree,chords = zeros(),Tape([k]+[0]*11)
    selected,detail = bp.connections(grid_rooms(),tree,chords)
    assert detail['available_rank']==12
    assert tree.bounds==list(range(31,1,-1))
    assert chords.bounds==[13]+list(range(12,1,-1))
    assert len(detail['tree'])==19 and len(selected)==19+k
    connected = {0}
    while True:
        nxt = connected | {v for a,b in selected for u,v in ((a,b),(b,a)) if u in connected}
        if nxt==connected:break
        connected=nxt
    assert len(connected)==20
    assert bp.cycle_rank(top.graph_from_edges(20,selected))==k


def test_extra_subset_distribution_by_exact_three_edge_permutations():
    # Enumerate indices of a toy three-element unused list, not environments.
    subsets = Counter()
    for k in range(4):
        for order in permutations(range(3)):
            subsets[k,frozenset(order[:k])] += 1
    for k in range(4):
        probabilities = [Fraction(count,24) for (size,_),count in subsets.items() if size==k]
        assert sum(probabilities)==Fraction(1,4)
        assert len(set(probabilities))==1


@pytest.mark.parametrize('k',[0,1,6,12])
def test_raster_door_invariants_and_independent_correspondence(k):
    rooms = grid_rooms()
    selected,_ = bp.connections(rooms,zeros(),Tape([k]+[0]*11))
    free,detail = bp.rasterize(rooms,selected,zeros())
    assert len(flood(free,min(free)))==len(free)
    assert 324<=len(free)<=529
    assert all(1<=x<=23 and 1<=y<=23 for x,y in free)
    room_cells = [{(x,y) for x in range(4*a+1,4*c+4) for y in range(4*b+1,4*d+4)}
                  for a,b,c,d in rooms]
    marked = set()
    for x,y in free:
        square = {(x,y),(x+1,y),(x,y+1),(x+1,y+1)}
        if square<=free:marked |= square
    assert marked==set().union(*room_cells)
    marked_components = []
    remaining = set(marked)
    while remaining:
        component = flood(remaining,min(remaining))
        marked_components.append(component)
        remaining -= component
    assert {frozenset(c) for c in marked_components}=={frozenset(c) for c in room_cells}
    owner = {cell:i for i,cells in enumerate(room_cells) for cell in cells}
    doors = free-marked
    assert len(doors)==len(selected)
    actual_edges = set()
    for x,y in doors:
        neighbors = {(x-1,y),(x+1,y),(x,y-1),(x,y+1)} & free
        assert len(neighbors)==2 and neighbors<=marked
        ids = tuple(sorted(owner[c] for c in neighbors))
        assert ids in selected
        actual_edges.add(ids)
        assert x%4==0 and y%4==2 or y%4==0 and x%4==2
    assert actual_edges==set(selected)
    for a,b in combinations(doors,2):
        assert abs(a[0]-b[0])+abs(a[1]-b[1])>=4
    quotient,_ = top.raster_quotient(free)
    assert bp.cycle_rank(quotient)==k
    assert detail['room_count']==detail['selected_graph_vertices']==20


def test_complete_construction_scripted_fixture_not_population_seed():
    streams = dict(partition=Tape([0]+[0]*33),tree=zeros(),chords=zeros(),doors=zeros())
    a = bp.construct_bp(streams)
    b = bp.construct_bp(dict(partition=Tape([0]+[0]*33),tree=zeros(),chords=zeros(),doors=zeros()))
    assert a==b and a[1]['desired']==12
    assert set(streams)=={'partition','tree','chords','doors'}


@pytest.mark.parametrize('rooms,selected',[
    ([(0,0,5,5),(0,0,0,0)],[]), ([(0,0,4,5)],[]),
    ([(0,0,5,5)],[(0,1)]), (grid_rooms(),[]),
])
def test_invalid_construction_stops_without_repair(rooms,selected):
    with pytest.raises(bp.IntegrityError):bp.rasterize(rooms,selected,zeros())


def test_raw_stream_framing_rejection_singletons_and_separation():
    import numpy as np
    s = bp.Stream.synthetic(7,'partition')
    fields = [b'phase1.5-v0.4-BPRIME-1',b'7',b'partition']
    framed = b''.join(len(f).to_bytes(4,'little')+f for f in fields)
    sha = hashlib.sha256(framed).digest()
    assert s.identity==sha.hex()
    independent = np.random.Philox(key=int.from_bytes(sha[:16],'little'))
    expected = [int(independent.random_raw()) for _ in range(5)]
    assert [s.integer(2**64) for _ in range(5)]==expected
    same = bp.Stream.synthetic(7,'partition')
    assert same.identity!=bp.Stream.synthetic(7,'doors').identity
    class Raw:
        def __init__(self):self.values=iter([2**64-1,5,99])
        def random_raw(self):return next(self.values)
    same.raw = Raw()
    assert same.integer(3)==2 and same.words==2
    assert same.integer(1)==0 and same.words==3
    assert same.permutation([])==[] and same.permutation([1])==[1] and same.words==3
    with pytest.raises(bp.IntegrityError):same.integer(True)
    with pytest.raises(bp.IntegrityError):bp.Stream.synthetic(80_010_000,'partition')


def test_raw_replay_fresh_process_on_fixture_seed_only():
    import subprocess,sys,os
    code = "from spatial_memory.phase15_bprime import Stream; s=Stream.synthetic(7,'doors'); print([s.integer(997) for _ in range(10)])"
    env = dict(os.environ,PYTHONPATH=str(Path(__file__).parents[1]/'src'))
    outputs = [subprocess.check_output([sys.executable,'-c',code],env=env) for _ in range(2)]
    assert outputs[0]==outputs[1]


def test_namespace_ranges_and_reserved_access_rejected_before_stream(monkeypatch,tmp_path):
    calls = []
    monkeypatch.setattr(bp.Stream,'_initialize',lambda *a:calls.append(a))
    for part in ('assessment','final','final-held-out','held_out','tuning'):
        with pytest.raises(bp.IntegrityError):bp.Identity(part,'BP',90_010_000)
        with pytest.raises(bp.IntegrityError):protocol.development_path(tmp_path/'absent',part,tmp_path)
    for seed in (50_010_000,80_020_000,90_010_000,100_010_000):
        with pytest.raises(bp.IntegrityError):bp.Identity('fit','BP',seed)
    for part in bp.PARTITIONS:
        for mechanism in bp.MECHANISMS:
            assert bp.seed_for(part,mechanism,9999)-bp.seed_for(part,mechanism,0)==9999
    for path in ('assessment.json','final-held-out/x','../escape'):
        with pytest.raises(bp.IntegrityError):protocol.development_path(tmp_path/path,'fit',tmp_path)
    assert calls==[]


@pytest.mark.parametrize('edges,n',[
    ([(0,1),(1,2),(2,3)],4), ([(0,1),(0,2),(0,3)],4),
    ([(0,1),(1,2),(2,0)],3), ([(0,1),(0,1),(1,1)],2),
])
def test_exact_near_oracle_and_cycle_rank(edges,n):
    graph = top.graph_from_edges(n,edges)
    assert top.exact_certificate(graph)==oracle_certificate(graph)
    reverse = top.induced(graph,list(reversed(range(n))))
    assert oracle_certificate(reverse)==oracle_certificate(graph)
    variants = [top.suppress(graph)]
    variants += [top.delete_leaf(graph,u) for u in range(n) if graph.degree(u)==1]
    variants += [top.contract_edge(graph,u,v) for u,v in graph.edges()]
    assert {bp.cycle_rank(g) for g in variants}=={bp.cycle_rank(graph)}
    assert len(Oracle().near_certificates(graph))>=1


def test_cross_rank_multi_parent_lineage_and_transitive_credit_loss():
    tree = top.graph_from_edges(2,[(0,1)])
    cycle = top.graph_from_edges(1,[(0,0)])
    a = record('synthetic:a',tree,mechanism='R')
    b = record('synthetic:b',cycle,mechanism='BP')
    assert not a.keys & b.keys
    index = MathIndex()
    index.admit(a,complete=True)
    index.admit(b,complete=True)
    assert dict(index.credits('synthetic-fit'))=={'R':1,'BP':1}
    ancestry = protocol.Lineage.derived(a.lineage,b.lineage)
    bridge = replace(record('synthetic:bridge',cycle),lineage=ancestry)
    result = index.admit(bridge)
    assert result['merged_components']==2
    assert dict(index.credits('synthetic-fit'))=={'R':1}
    assert ancestry.roots==a.lineage.roots|b.lineage.roots
    # Cross-partition derivatives reject without changing any existing component.
    later = replace(bridge,identity='synthetic:later',partition='synthetic-calibration')
    assert not index.admit(later)['inserted']
    assert len(index.records)==3
    with pytest.raises(bp.IntegrityError):index.admit(a,complete=True)


def test_near_only_bridge_independent_saved_graph_fixture():
    # leaf/edge edits join two classes of trees. Search is not used: named graphs.
    a = record('synthetic:path',top.graph_from_edges(2,[(0,1)]))
    b = record('synthetic:star',top.graph_from_edges(4,[(0,1),(0,2),(0,3)]))
    assert a.exact!=b.exact and a.keys & b.keys
    index = MathIndex()
    index.admit(a,complete=True)
    result = index.admit(b)
    assert result['exact_matches']==[] and len(index.components('synthetic-fit'))==1


def make_inventory(tmp_path):
    oracle = Oracle()
    raster_fixtures = [ {(0,0),(1,0)},
        {(2,2),(1,2),(3,2),(2,1),(2,3)},
        {(x,y) for x in range(3) for y in range(3) if (x,y)!=(1,1)} ]
    rows,ledger = [],{}
    for i,(category,free) in enumerate(zip(protocol.CATEGORIES,raster_fixtures)):
        graph,_ = top.raster_quotient(free)
        exact,keys = oracle.exact_certificate(graph),oracle.near_certificates(graph)
        geometry = dict(width=5,height=5,free=sorted(map(list,free)))
        body = dict(geometry=geometry,matrix=list(map(list,graph.matrix)),
                    exact=exact,near_certificates=sorted(keys))
        packed = gzip.compress(protocol.canonical_bytes(body),mtime=0)
        path = tmp_path/f'fixture{i}.json.gz'
        path.write_bytes(packed)
        row = dict(identity=f'synthetic:reference{i}',category=category,
            included=category!='rejected_valid',outcome=protocol.OUTCOMES[category][0],
            roots=[f'prior-root:{i}'],aliases=[],source_commit='0'*40,source_path='synthetic-input',
            interpretation='synthetic-static-base',path=path.name,bytes=len(packed),
            sha256=hashlib.sha256(packed).hexdigest(),width=5,height=5,
            matrix=body['matrix'],exact=list(exact),near_keys=list(map(list,sorted(keys))))
        rows.append(row)
        ledger[row['identity']] = {k:row[k] for k in (
            'outcome','sha256','bytes','roots','aliases','source_commit','source_path','interpretation')}
    payload = dict(version=bp.VERSION,schema=1,profile='synthetic',namespace='synthetic-exact-oracle',
                   entries=sorted(rows,key=lambda r:(r['category'],r['identity'])),
                   ledger_sha256=protocol.digest(ledger))
    return payload,ledger


def validate(payload,ledger,root):
    return protocol.validate_inventory(payload,ledger,root,expected_digest=protocol.digest(payload),
        expected_ledger_digest=protocol.digest(ledger),backend=Oracle(),synthetic=True,
        binding=binding_for(root/'bound-store',inventory=payload,ledger=ledger))


def test_reference_categories_rejected_bridge_not_promoted(tmp_path):
    payload,ledger = make_inventory(tmp_path)
    validated = validate(payload,ledger,tmp_path)
    assert len(validated.included)==2 and len(validated.rejected_ledger)==1
    index = MathIndex()
    validated.load(index)
    excluded = validated.rejected_ledger[0]
    assert excluded.identity not in [r.identity for r in index.records]
    # The rejected ring may be independently proposed; its prior rejection alone
    # does not become an exclusion reference. Actual known ancestry still matches.
    new = replace(excluded,identity='synthetic:new',partition='synthetic-fit',category='',
                  mechanism='BP',lineage=protocol.Lineage(frozenset(('fresh-complete-root',))))
    assert index.classify(new)[0]=='independent'
    with pytest.raises(bp.IntegrityError):index.add_reference(excluded)
    with pytest.raises(bp.IntegrityError):validated.load(protocol.AdmissionIndex())


@pytest.mark.parametrize('mutation', ['include','outcome','matrix','namespace','path','ancestry','duplicate','hash'])
def test_reference_inventory_conflicts_stop(tmp_path,mutation):
    payload,ledger = make_inventory(tmp_path)
    row = payload['entries'][0]
    if mutation=='include':row['included']=not row['included']
    elif mutation=='outcome':row['outcome']='independent' if row['outcome']!='independent' else 'historical'
    elif mutation=='matrix':row['matrix']=[[9]]
    elif mutation=='namespace':payload['namespace']='old-version'
    elif mutation=='path':row['path']='../escape'
    elif mutation=='ancestry':row['roots']=['laundered-root']
    elif mutation=='duplicate':payload['entries'].append(deepcopy(row))
    elif mutation=='hash':(tmp_path/row['path']).write_bytes(b'changed')
    with pytest.raises((bp.IntegrityError,OSError)):validate(payload,ledger,tmp_path)


def test_reference_seal_digest_and_missing_archive(tmp_path):
    payload,ledger = make_inventory(tmp_path)
    with pytest.raises(bp.IntegrityError):protocol.validate_inventory(payload,ledger,tmp_path,
        expected_digest='0'*64,expected_ledger_digest=protocol.digest(ledger),backend=Oracle(),synthetic=True)
    (tmp_path/payload['entries'][0]['path']).unlink()
    with pytest.raises(bp.IntegrityError):validate(payload,ledger,tmp_path)


def test_pair_order_and_exact_boundaries_on_explicit_corridor():
    free = frozenset((x,0) for x in range(45))  # abstract pair-rule fixture, not B′ world
    class Last(Tape):
        def choose(self,values):
            self.choices.append(tuple(values))
            return values[-1]
    stream = Last([])
    selected = bp.choose_pair(free,stream)
    expected = [(a,b,abs(a[0]-b[0])) for a in sorted(free,key=lambda c:(c[1],c[0]))
                for b in sorted(free,key=lambda c:(c[1],c[0])) if 12<=abs(a[0]-b[0])<=40]
    assert stream.choices[0]==tuple(expected) and selected==expected[-1]
    assert {p[2] for p in expected}==set(range(12,41))
    with pytest.raises(old.Rejected):bp.choose_pair({(0,0),(1,0)},zeros())


@pytest.mark.parametrize('category',range(5))
def test_dynamics_exact_baseline_body_on_hand_constructed_fixture(monkeypatch,category):
    free = frozenset((x,y) for y in range(1,10) for x in range(1,10))
    geo = old.Geometry('synthetic-fit','BP',7,free,{})
    args = (geo,(1,1),(9,9))
    tape = Tape([category]+[0]*3000)
    baseline = Tape([category]+[0]*3000)
    monkeypatch.setattr(old,'Stream',lambda *args:baseline)
    expected = old.dynamic_schedule(*args,0,retry_rule='fixed')
    actual = bp.build_schedule(*args,tape)
    assert actual==expected and tape.bounds==baseline.bounds and tape.choices==baseline.choices
    assert not set(map(tuple,actual['initial'])) & {(1,1),(9,9)}
    assert not {tuple(e['cell']) for e in actual['events']} & {(1,1),(9,9)}
    if category==0:assert tape.bounds==[5]
    elif category==4:
        assert len(actual['positions'])==81
        assert sum(actual['dwells'])>=81
    else:
        assert actual['onset']==2 and actual['length']==2
        blocked = set(map(tuple,actual['initial']))
        assert (9,9) in flood(free-blocked,(1,1))


def test_dynamics_exhaustion_fixed_draws_no_category_redraw():
    free = frozenset(((0,0),(1,0),(2,0)))
    geo = old.Geometry('synthetic-fit','BP',7,free,{})
    # Protect both endpoints: every footprint starts at the isolated middle.
    tape = Tape([1,0,0]+[0]*128)
    with pytest.raises(old.DynamicLimit):bp.build_schedule(geo,(0,0),(2,0),tape)
    assert tape.bounds==[5,11,3]+[1]*128


def lock():
    return dict(version=bp.VERSION,profile='synthetic',source_sha256='1'*64,
        configuration_sha256='2'*64,dependencies_sha256='3'*64,references_sha256='4'*64)


def test_checkpoint_integrity_exact_resume_and_lock_conflict(tmp_path):
    store = toy_store(tmp_path)
    with store.writer():
        entry = store.write('synthetic:one',fixture(dict(complete=True,trace=[1,2],failure=None)))
        packed = (tmp_path/entry['path']).read_bytes()
        assert not store.inventory([entry],['synthetic:one'])
        with pytest.raises(bp.IntegrityError):store.write('synthetic:two',fixture(dict(nonfinite=float('nan'))))
        with pytest.raises(bp.IntegrityError):
            with toy_store(tmp_path).writer():pass
    with store.writer():
        assert not store.inventory([entry],['synthetic:one'])
        assert (tmp_path/entry['path']).read_bytes()==packed
        with pytest.raises(bp.IntegrityError):store.inventory([entry,entry],['synthetic:one'])
        with pytest.raises(bp.IntegrityError):store.inventory([entry],['synthetic:one','synthetic:missing'])
    changed = lock();changed['source_sha256']='9'*64
    with pytest.raises(bp.IntegrityError):
        with toy_store(tmp_path,override=changed).writer():pass
    (tmp_path/entry['path']).write_bytes(b'corruption')
    with pytest.raises(bp.IntegrityError):store.inventory([entry],['synthetic:one'])


def test_checkpoint_duplicate_torn_and_complete_recovery(tmp_path):
    store = toy_store(tmp_path)
    with store.writer():
        entry = store.write('synthetic:one',fixture({'trace':[]}))
        packed = (tmp_path/entry['path']).read_bytes()
        (tmp_path/entry['path']).unlink()
        part = tmp_path/'staging'/'manual.part';part.write_bytes(packed)
        recovered = store.recover(['synthetic:one'])
        assert recovered==[entry] and not part.exists()
        with pytest.raises(bp.IntegrityError):store.write('synthetic:one',fixture({'trace':[]}))
        assert list((tmp_path/'staging').glob('*.part'))  # preserved duplicate
    other = toy_store(tmp_path/'other')
    with other.writer():
        part = tmp_path/'other'/'staging'/'torn.part';part.write_bytes(b'partial')
        with pytest.raises(bp.IntegrityError):other.recover(['synthetic:one'])
        with pytest.raises(bp.IntegrityError):other.write('synthetic:one',{})
        assert part.read_bytes()==b'partial'


def test_checkpoint_reserved_stage_denied_without_files(tmp_path):
    path = tmp_path/'never-created'
    for part in ('assessment','final','held_out'):
        with pytest.raises(bp.IntegrityError):storage.Checkpoints(path,lock(),partition=part)
    assert not path.exists()


def test_order_requires_checkpoint_and_stops_at_frozen_allowance():
    index = protocol.AdmissionIndex()
    order = protocol.DevelopmentOrder()
    # Identity accounting only: no geometry function or Stream is called.
    identity = order.next_identity(index)
    assert identity==('fit','R',80_000_000)
    with pytest.raises(bp.IntegrityError):order.next_identity(index)
    order.checkpointed(identity)
    order.cursors['fit','BP']=10_000
    with pytest.raises(bp.IntegrityError):order.next_identity(index)
    with pytest.raises(bp.IntegrityError):index.freeze('fit')


def test_backend_failure_propagates_without_fallback():
    class Failed(bp.Backend):
        def near_certificates(self,*args,**kwargs):raise bp.IntegrityError('native failure')
    with pytest.raises(bp.IntegrityError,match='native failure'):
        bp.describe({(0,0),(1,0)},Failed())


def test_public_projection_and_no_navigation_imports():
    geo = old.Geometry('synthetic-fit','BP',7,frozenset(((1,1),(2,1))),{})
    assert set(geo.public_domain((1,1),(2,1)))=={
        'width','height','start','goal','occupied_outer_ring','start_goal_always_free'}
    import ast
    for name in ('phase15_bprime.py','phase15_bprime_protocol.py','phase15_bprime_store.py'):
        source = Path(bp.__file__).with_name(name).read_text()
        imports = [n.module or '' for n in ast.walk(ast.parse(source)) if isinstance(n,ast.ImportFrom)]
        assert not any(any(word in module for word in ('simulation','evaluation','policies')) for module in imports)


@pytest.mark.parametrize('category',[1,2,3])
def test_static_schedule_upper_boundaries_and_protected_endpoints(category):
    free = frozenset((x,y) for x in range(1,10) for y in range(1,10))
    geo = old.Geometry('synthetic-fit','BP',7,free,{})
    tape = Tape([category,10,2]+[0]*3000)
    result = bp.build_schedule(geo,(1,1),(9,9),tape)
    assert result['onset']==12 and result['length']==4
    assert tape.bounds[:3]==[5,11,3]
    assert all(e['step']==12 for e in result['events'])
    if category==3:
        assert not set(result['footprint']) & set(result['other_footprint'])
    blocked = set(result['initial'])
    assert (9,9) in flood(free-blocked,(1,1))
    for event in result['events']:
        if event['action']=='remove':blocked.remove(tuple(event['cell']))
        else:blocked.add(tuple(event['cell']))
    assert (9,9) in flood(free-blocked,(1,1))


def test_moving_length_reversal_and_complete_final_dwell():
    free = frozenset((x,y) for x in range(1,10) for y in range(1,10))
    geo = old.Geometry('synthetic-fit','BP',7,free,{})
    # Eight path cells: first and seven growth choices, then reversal coin 1.
    tape = Tape([4,2]+[0]*8+[1]+[0]*100)
    result = bp.build_schedule(geo,(1,1),(9,9),tape)
    assert result['length']==8 and len(result['positions'])==81
    assert len(result['footprint'])==8
    assert result['positions'][0]==result['footprint'][0]
    assert sum(result['dwells'][:-1])<81<=sum(result['dwells'])
    assert all(abs(a[0]-b[0])+abs(a[1]-b[1])<=1
               for a,b in zip(result['positions'],result['positions'][1:]))


def test_rejected_prior_ancestry_preserved_without_key_promotion(tmp_path):
    payload,ledger = make_inventory(tmp_path)
    validated = validate(payload,ledger,tmp_path)
    index = MathIndex()
    validated.load(index)
    rejected = validated.rejected_ledger[0]
    derivative = replace(rejected,identity='synthetic:derivative',partition='synthetic-fit',
                         mechanism='BP',category='')
    outcome = index.admit(derivative,complete=True)
    assert not outcome['inserted'] and not outcome['matches']
    assert outcome['lineage_exclusions']==sorted(rejected.lineage.roots)
    assert len(index.records)==2


def test_independent_relation_component_reconstruction():
    graphs = [top.graph_from_edges(1,[(0,0)]*k) for k in (0,1,2)]
    records = [record(f'synthetic:{k}',g,mechanism=m) for k,(g,m) in
               enumerate(zip(graphs,('R','BP','V')))]
    records += [replace(record('synthetic:ab',graphs[1]),lineage=protocol.Lineage.derived(
        records[0].lineage,records[1].lineage))]
    records += [replace(record('synthetic:bc',graphs[2]),lineage=protocol.Lineage.derived(
        records[1].lineage,records[2].lineage))]
    index = MathIndex()
    neighbors = {r.identity:set() for r in records}
    for i,r in enumerate(records):
        index.admit(r,complete=i<3)
        for before in records[:i]:
            if (r.keys & before.keys or r.raster==before.raster or
                r.lineage.roots & before.lineage.roots):
                neighbors[r.identity].add(before.identity)
                neighbors[before.identity].add(r.identity)
    remaining = set(neighbors)
    expected = []
    while remaining:
        seen = {min(remaining)}
        while True:
            expanded = seen | set().union(*(neighbors[x] for x in seen))
            if expanded==seen:break
            seen = expanded
        expected.append(frozenset(seen));remaining-=seen
    actual = [frozenset(index.records[i].identity for i in group)
              for group in index.components('synthetic-fit')]
    assert set(actual)==set(expected)=={frozenset(neighbors)}
    assert dict(index.credits('synthetic-fit'))=={'R':1}


def test_ancestry_key_and_stage_validation_cannot_launder_profiles():
    with pytest.raises(bp.IntegrityError):protocol.Lineage('not-a-root-set')
    with pytest.raises(bp.IntegrityError):protocol.Lineage.derived()
    r = record('synthetic:one',top.graph_from_edges(1,[]))
    with pytest.raises(bp.IntegrityError):protocol.AdmissionIndex().admit(replace(r,partition='fit'),complete=True)
    with pytest.raises(bp.IntegrityError):protocol.AdmissionIndex().admit(
        replace(r,partition='calibration'),complete=True)
    with pytest.raises(bp.IntegrityError):replace(r,exact=('bad',),keys=frozenset({('bad',)}))
    with pytest.raises(bp.IntegrityError):replace(r,raster=['mutable'])


def test_checkpoint_atomic_failure_preserves_complete_stage_for_recovery(tmp_path,monkeypatch):
    store = toy_store(tmp_path)
    with store.writer():
        real_link = storage.os.link
        def fail(*args,**kwargs):raise OSError('simulated publication interruption')
        monkeypatch.setattr(storage.os,'link',fail)
        with pytest.raises(OSError):store.write('synthetic:one',fixture({'retained':[1,2,3]}))
        assert len(list((tmp_path/'staging').glob('*.part')))==1
        monkeypatch.setattr(storage.os,'link',real_link)
        recovered = store.recover(['synthetic:one'])
        assert not store.inventory(recovered,['synthetic:one'])


def test_checkpoint_extra_symlink_and_nonlease_writes_denied(tmp_path):
    store = toy_store(tmp_path)
    with pytest.raises(bp.IntegrityError):store.write('synthetic:one',{})
    with store.writer():
        (tmp_path/'records'/'unexpected').write_bytes(b'preserved')
        with pytest.raises(bp.IntegrityError):store.inventory([],[])
    other = tmp_path/'other';other.mkdir()
    (other/'records').symlink_to(tmp_path/'records')
    with pytest.raises(bp.IntegrityError):
        with toy_store(other).writer():pass


def test_order_exhaustion_is_terminal_without_new_draw():
    order = protocol.DevelopmentOrder()
    order.cursors['fit','R']=10_000
    with pytest.raises(bp.IntegrityError):order.next_identity(protocol.AdmissionIndex())
    assert order.stopped
    for _ in range(2):
        with pytest.raises(bp.IntegrityError,match='stopped'):
            order.next_identity(protocol.AdmissionIndex())


def test_marginal_cycle_law_is_nonuniform_exact_rational_fixture():
    # Analytical toy mixture only, not enumeration of any 6×6 partitions.
    p = {1:Fraction(1,2),3:Fraction(1,2)}
    q = [sum((mass/(r+1) for r,mass in p.items() if r>=k),Fraction(0)) for k in range(4)]
    assert q==[Fraction(3,8),Fraction(3,8),Fraction(1,8),Fraction(1,8)]
    assert sum(q)==1
    for k in range(3):assert q[k]-q[k+1]==p.get(k,0)/(k+1)



def test_zero_available_edges_still_consumes_uniform_singleton():
    tree,chord = Tape([]),Tape([0])
    selected,detail = bp.connections([(0,0,5,5)],tree,chord)
    assert selected==[] and detail['K']==detail['available_rank']==0
    assert tree.bounds==[] and chord.bounds==[1]


def test_reference_reserved_archive_path_denied_before_open(tmp_path,monkeypatch):
    payload,ledger = make_inventory(tmp_path)
    payload['entries'][0]['path']='assessment/fixture.json.gz'
    def deny(*args):pytest.fail('Reserved path was opened')
    monkeypatch.setattr(Path,'read_bytes',deny)
    with pytest.raises(bp.IntegrityError,match='Reserved|binding|authority'):
        validate(payload,ledger,tmp_path)


def test_complete_world_credit_cannot_be_given_to_related_record():
    index = MathIndex()
    graph = top.graph_from_edges(2,[(0,1)])
    a,b = record('synthetic:a',graph),record('synthetic:b',graph)
    with pytest.raises(bp.IntegrityError):index.admit(a)
    index.admit(a,complete=True)
    with pytest.raises(bp.IntegrityError):index.admit(b,complete=True)
    assert len(index.records)==1


def test_order_reactivates_mechanism_and_requires_prior_partition_freeze():
    class Counts:
        def __init__(self):
            self.values = Counter(R=12,BP=11,V=12,M=12)
            self.frozen = []
        def credits(self,part):return self.values if part=='fit' else Counter()
        def freeze(self,part):self.frozen.append(part)
    index = Counts();order = protocol.DevelopmentOrder()
    first = order.next_identity(index)
    assert first[:2]==('fit','BP')
    order.checkpointed(first)
    # An abstract saved bridge reduces R: this is counter accounting, no world.
    index.values['R']=11
    second = order.next_identity(index)
    assert second[:2]==('fit','R')
    order.checkpointed(second)
    index.values.update(R=1,BP=1)
    third = order.next_identity(index)
    assert index.frozen==['fit'] and third[:2]==('calibration','R')
    empty = protocol.DevelopmentOrder()
    with pytest.raises(bp.IntegrityError):empty.checkpointed(None)


def test_checkpoint_reproduction_same_pinned_lock_and_payload(tmp_path):
    data = []
    common=binding_for(tmp_path/'first',stores=[tmp_path/'first',tmp_path/'second'])
    for name in ('first','second'):
        store = toy_store(tmp_path/name,binding=common)
        with store.writer():
            entry = store.write('synthetic:fixed',fixture({'failure':'explicit synthetic failure','trace':[]}))
        data.append((tmp_path/name/entry['path']).read_bytes())
    assert data[0]==data[1]


def test_full_c3_backend_is_required_in_production_reference_validation(tmp_path):
    payload,ledger = make_inventory(tmp_path)
    with pytest.raises(bp.IntegrityError,match='binding'):
        protocol.validate_inventory(payload,ledger,tmp_path,expected_digest=protocol.digest(payload),
            expected_ledger_digest=protocol.digest(ledger),backend=Oracle())


def test_non_linux_backend_refuses_without_starting_worker(monkeypatch):
    # Existing production guard, on one explicit toy graph. Never install or
    # emulate nauty, alter limits, or create a registered candidate.
    import spatial_memory.phase15_nauty as native
    monkeypatch.setattr(native.sys,'platform','darwin')
    backend = native.Backend()
    with pytest.raises(native.BackendFailure,match='Linux enforcement required'):
        backend.exact_certificate(top.graph_from_edges(1,[]))
    assert backend.process is None



def test_geometry_serialization_preserves_single_and_multiple_actual_roots():
    geo = old.Geometry('synthetic-fit','BP',7,frozenset(((1,1),(2,1))),
                       {'ancestral_roots':['old-version:root']})
    parent = protocol.Lineage(frozenset(('old-version:root',)))
    single = bp.geometry_payload(geo,None,None,None,[],parent)
    assert single['lineage']=='old-version:root'
    assert single['ancestral_roots']==['old-version:root']
    assert single['public_domain'] is None
    with pytest.raises(bp.IntegrityError):
        bp.geometry_payload(geo,None,None,None,[],protocol.Lineage(frozenset(('new-seed',))))
    ancestry = protocol.Lineage.derived(parent,protocol.Lineage(frozenset(('second-root',))))
    multi = bp.geometry_payload(geo,None,None,None,[],ancestry)
    assert multi['lineage'] is None and set(multi['ancestral_roots'])==ancestry.roots
