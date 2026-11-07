"""Artifact-only tests: no navigation, policy, filter or controller execution."""
import ast
from dataclasses import asdict
from itertools import combinations, permutations
import random
from pathlib import Path
import pytest
from spatial_memory import phase15_generators as gen
from spatial_memory import phase15_topology as top


def test_development_namespaces_only():
    for part in gen.PARTITIONS:
        for mechanism in gen.MECHANISMS:
            assert gen.seed_for(part,mechanism,9999)-gen.seed_for(part,mechanism,0)==9999
    for part in ('assessment','held_out','final','tuning'):
        with pytest.raises(ValueError): gen.seed_for(part,'R',0)
    for index in (-1,10000,True):
        with pytest.raises(ValueError): gen.seed_for('fit','R',index)
    with pytest.raises(ValueError): gen.geometry('fit','R',60_000_000)


def test_raw_stream_identity_replay_and_separation():
    a=gen.Stream(50_000_000,'geometry'); b=gen.Stream(50_000_000,'geometry')
    assert a.identity==b.identity
    assert [a.integer(100000) for _ in range(30)]==[b.integer(100000) for _ in range(30)]
    assert gen.Stream(50_000_000,'start-goal').identity!=a.identity
    assert gen.Stream(50_000_001,'geometry').identity!=a.identity


def test_exact_integer_rejection_and_rational_bernoulli():
    class Raw:
        def __init__(self,values): self.values=iter(values)
        def random_raw(self): return next(self.values)
    stream=gen.Stream(50_000_000,'test')
    stream.raw=Raw([2**64-1,5])
    assert stream.integer(3)==2 # rejects the upper biased word
    stream.raw=Raw(range(20))
    assert sum(stream.bernoulli(3,10) for _ in range(20))==6
    stream.raw=Raw(range(5))
    assert [stream.choose(gen.CATEGORIES) for _ in range(5)]==list(gen.CATEGORIES)


def test_geometry_r_exact_rooms_doors():
    g=gen.geometry('fit','R',50_000_000)
    assert 415<=len(g.free)<=424
    assert len(g.construction['room_edges'])==len(g.construction['doors'])
    assert all((6*i+x,6*j+y) in g.free for i in range(4) for j in range(4)
               for x in range(1,6) for y in range(1,6))
    assert all((x%6==0)!=(y%6==0) for x,y in g.construction['doors'])
    assert len(gen.components(g.free))==1


def test_geometry_m_exact_lattice_and_probability_inputs():
    stream=gen.Stream(50_030_000,'geometry')
    free,detail=gen.generate_m(stream)
    assert 120<=len(detail['coarse_edges'])<=220
    assert len(free)==121+len(detail['coarse_edges'])
    assert all((2+2*x,2+2*y) in free for x in range(11) for y in range(11))
    assert len(gen.components(free))==1
    assert len(gen.lattice(11))==220


def test_prescribed_chord_probabilities():
    class Spy(gen.Stream):
        def __init__(self): super().__init__(50_000_000,'spy'); self.probabilities=[]
        def bernoulli(self,n,d): self.probabilities.append((n,d)); return False
    a=Spy(); gen.generate_r(a)
    assert a.probabilities==[(3,10)]*9
    b=Spy(); gen.generate_m(b)
    assert b.probabilities==[(3,20)]*100


def test_bsp_split_geometry_and_exact_ranges():
    free,detail=gen.generate_b(gen.Stream(50_010_000,'geometry'))
    assert detail['desired'] in (12,16,20)
    assert len(detail['leaves'])==detail['desired']
    for row in detail['splits']:
        x0,y0,x1,y1=row['rect']; c=row['wall']
        assert (x0+3<=c<=x1-3) if row['axis']==0 else (y0+3<=c<=y1-3)
    assert all(1<=x<=23 and 1<=y<=23 for x,y in free)


def test_v_requires_resolved_tie_and_exact_prefix_rejections():
    with pytest.raises(gen.SpecificationAmbiguity):
        gen.generate_v(gen.Stream(50_020_000,'geometry'))
    # This seed may reject before carving; rejection is preserved, never repaired.
    try:
        free,detail=gen.generate_v(gen.Stream(50_020_000,'geometry'),'lex_yx')
    except gen.Rejected as error:
        assert str(error).startswith('voronoi_')
    else:
        assert len(detail['seeds']) in (12,16,20)
        assert len(gen.components(free))==1


def test_v_tie_conflict_and_user_selected_lexicographic_rule():
    cells={(1,2),(2,2),(1,3),(2,3)}
    lex=gen.shortest_core_path({(2,2)},{(1,3)},cells,'lex_yx')
    bfs=gen.shortest_core_path({(2,2)},{(1,3)},cells,'bfs_nesw')
    assert lex==[(2,2),(1,2),(1,3)]
    assert bfs==[(2,2),(2,3),(1,3)]
    assert tuple(map(gen.row_key,lex))<tuple(map(gen.row_key,bfs))


def test_v_complete_geometry_on_an_admissible_golden_draw():
    class GoldenStream:
        def __init__(self): self.probabilities=[]
        def choose(self,values): return values[0]
        def permutation(self,values):
            values=list(values)
            if len(values)==529:
                seeds=[(x,y) for y in (4,12,20) for x in (3,9,15,21)]
                return seeds+[v for v in values if v not in seeds]
            return values
        def bernoulli(self,n,d): self.probabilities.append((n,d)); return False
    stream=GoldenStream(); free,detail=gen.generate_v(stream,'lex_yx')
    assert len(detail['seeds'])==12 and len(gen.components(free))==1
    assert stream.probabilities and set(stream.probabilities)=={(1,4)}
    assert all(1<=x<=23 and 1<=y<=23 for x,y in free)


def test_geometry_replay_all_implemented_mechanisms():
    for mechanism in gen.MECHANISMS:
        seed=gen.seed_for('fit',mechanism,0)
        outcomes=[]
        for _ in range(2):
            try: outcomes.append(asdict(gen.geometry('fit',mechanism,seed,v_tie_rule='lex_yx')))
            except gen.Rejected as error: outcomes.append(str(error))
        assert outcomes[0]==outcomes[1]


def test_pair_uniform_selection_and_constraints():
    geo=gen.geometry('fit','R',50_000_000)
    a=gen.choose_pair(geo); b=gen.choose_pair(geo)
    assert a==b
    start,goal,d=a
    assert 12<=d<=40 and abs(start[0]-goal[0])+abs(start[1]-goal[1])>=5
    assert d==gen.distances(geo.free,start)[goal]


def test_public_projection_excludes_evaluator_information():
    geo=gen.geometry('fit','R',50_000_000); start,goal,_=gen.choose_pair(geo)
    public=geo.public_domain(start,goal)
    assert set(public)=={'width','height','start','goal','occupied_outer_ring','start_goal_always_free'}
    assert not {'seed','partition','mechanism','free','construction','events'}&public.keys()


def test_partial_artifact_before_start_goal_has_no_public_projection():
    geo=gen.geometry('fit','R',50_000_000)
    payload=gen.artifact(geo,None,None,None,[])
    assert payload['public_domain'] is None and payload['start'] is None
    start,goal,d=gen.choose_pair(geo)
    assert gen.artifact(geo,start,goal,d,[])['public_domain']['start']==list(start)


def test_dynamic_categories_and_replay():
    # Artifact fixtures use new development seeds only; no robot trajectory.
    categories=set()
    for index in range(30):
        geo=gen.geometry('fit','R',50_000_000+index)
        # Valid fixed free endpoints; pair sampling has an independent stream.
        start,goal=(1,1),(23,23)
        for schedule in (0,1):
            d=gen.dynamic_schedule(geo,start,goal,schedule,retry_rule='fixed')
            assert d==gen.dynamic_schedule(geo,start,goal,schedule,retry_rule='fixed')
            categories.add(d['category'])
            protected={start,goal}
            assert not set(map(tuple,d['initial']))&protected
            assert not {tuple(e['cell']) for e in d['events']}&protected
            if d['category']=='none': assert not d['events'] and not d['positions']
            elif d['category']=='moving':
                assert len(d['positions'])==81 and set(map(tuple,d['positions']))<=geo.free-protected
                assert d['dwells'][0] in (2,3,4)
                assert all(2<=v<=6 for v in d['dwells'][1:])
                assert all(abs(a[0]-b[0])+abs(a[1]-b[1])<=1
                           for a,b in zip(d['positions'],d['positions'][1:]))
            else:
                assert 2<=d['onset']<=12 and d['length'] in (2,3,4)
                assert all(e['step']==d['onset'] for e in d['events'])
                blocked=set(map(tuple,d['initial']))
                assert goal in gen.distances(geo.free-blocked,start)
                for e in d['events']:
                    if e['action']=='remove': blocked.remove(tuple(e['cell']))
                    else: blocked.add(tuple(e['cell']))
                assert goal in gen.distances(geo.free-blocked,start)
                if d['category']=='swap': assert not set(d['footprint'])&set(d['other_footprint'])
    assert categories==set(gen.CATEGORIES)


def test_dynamic_rejection_limit_no_category_substitution(monkeypatch):
    class FakeStream:
        def __init__(self,*args): pass
        def choose(self,values):
            if values==gen.CATEGORIES: return 'addition'
            return values[0]
        def integer(self,n): return 0
    attempts=[]
    def reject(*args): attempts.append(1); raise gen.Rejected('forced_dead_end')
    monkeypatch.setattr(gen,'Stream',FakeStream); monkeypatch.setattr(gen,'grow_path',reject)
    geo=gen.Geometry('fit','R',50_000_000,frozenset({(1,1),(2,1)}),{})
    with pytest.raises(gen.DynamicLimit,match='128'): gen.dynamic_schedule(geo,(1,1),(2,1),0,retry_rule='fixed')
    assert len(attempts)==128


def test_raster_corridor_room_cycle_golden():
    corridor={(x,1) for x in range(1,8)}
    g,_=top.raster_quotient(corridor)
    assert top.exact_certificate(g)==(2,0,0,1)
    room={(x,y) for x in range(1,4) for y in range(1,4)}
    g,info=top.raster_quotient(room)
    assert top.exact_certificate(g)==(1,0) and info['room_regions']==1
    ring={(x,y) for x in range(3) for y in range(3)}-{(1,1)}
    g,_=top.raster_quotient(ring)
    assert top.exact_certificate(g)==(1,1)


def test_one_cell_door_separates_rooms_two_cell_can_merge():
    rooms={(x,y) for x in (0,1,3,4) for y in (0,1)}
    narrow=rooms|{(2,0)}; wide=narrow|{(2,1)}
    _,a=top.raster_quotient(narrow); _,b=top.raster_quotient(wide)
    assert a['room_regions']==2 and b['room_regions']==1


def test_multiedge_loop_and_contraction():
    g=top.graph_from_edges(3,[(0,1),(0,1),(1,2)])
    reduced=top.suppress(g)
    assert sorted(reduced.degree(i) for i in range(reduced.n))==[1,3]
    assert sum(reduced.matrix[i][i] for i in range(reduced.n))==1
    contracted=top.contract_edge(top.graph_from_edges(2,[(0,1),(0,1),(0,1)]),0,1)
    assert contracted.matrix==((2,),) # two noncontracted parallel edges become loops


def test_pure_cycles_and_subdivision_share_certificate():
    for n in (3,4,8):
        g=top.graph_from_edges(n,[(i,(i+1)%n) for i in range(n)])
        assert top.exact_certificate(top.suppress(g))==(1,1)


def test_exact_canonicalization_against_independent_permutation_reference():
    rng=random.Random(150150)
    for n in range(1,7):
        for _ in range(15):
            matrix=[[0]*n for _ in range(n)]
            for i in range(n):
                for j in range(i,n):
                    matrix[i][j]=matrix[j][i]=rng.randrange(3)
            g=top.Graph(tuple(map(tuple,matrix)))
            assert top.exact_certificate(g)==top.brute_certificate(g)
            order=list(range(n)); rng.shuffle(order)
            assert top.exact_certificate(top.induced(g,order))==top.exact_certificate(g)


def test_exact_wl_collision_fixture_not_hash_equivalence():
    # A six-cycle and two triangles share degree2 everywhere; raw graphs differ.
    cycle=top.graph_from_edges(6,[(i,(i+1)%6) for i in range(6)])
    triangles=top.graph_from_edges(6,[(0,1),(1,2),(2,0),(3,4),(4,5),(5,3)])
    assert top.exact_certificate(cycle)!=top.exact_certificate(triangles)


def test_canonicalization_budget_never_returns_approximate_key():
    g=top.graph_from_edges(5,[(0,1),(1,2),(2,3),(3,4)])
    with pytest.raises(top.CanonicalizationLimit): top.exact_certificate(g,max_nodes=0)
    with pytest.raises(top.CanonicalizationLimit): top.exact_certificate(g,max_seconds=-1)


def test_near_equivalence_and_lineage_transitive_cross_partition():
    index=top.IndependenceIndex()
    def add(identity,keys,partition='fit',mechanism='R',lineage=None):
        return index.admit(partition=partition,mechanism=mechanism,keys=frozenset(keys),
                           exact=(identity,),raster=(identity,),lineage=lineage or identity,identity=identity)
    assert add(1,{(1,)})['accepted']
    assert add(2,{(2,)},mechanism='B')['accepted']
    merged=add(3,{(1,),(2,)},mechanism='M')
    assert not merged['accepted'] and merged['merged_components']==2
    assert len(index.clusters('fit'))==1
    assert not add(4,{(2,)},partition='calibration')['accepted']
    assert len(index.records)==3 # rejected cross-split bridge not inserted
    assert not add(5,{(9,)},lineage=1)['accepted']


def test_near_graph_keys_include_allowed_operations_only():
    star=top.graph_from_edges(4,[(0,1),(0,2),(0,3)])
    assert top.exact_certificate(top.suppress(star)) in top.near_certificates(star)
    assert top.exact_certificate(top.delete_leaf(star,1)) in top.near_certificates(star)
    with pytest.raises(ValueError): top.contract_edge(top.graph_from_edges(1,[(0,0)]),0,0)


def test_raster_dihedral_invariance_and_metric_information():
    cells={(1,1),(2,1),(3,1),(3,2)}
    transformed={(24-y,x) for x,y in cells}
    assert top.raster_certificate(cells)==top.raster_certificate(transformed)
    assert top.raster_certificate(cells)!=top.raster_certificate(cells|{(3,3)})


def test_modules_do_not_import_policy_simulation_or_filter():
    for module in (gen,top):
        tree=ast.parse(Path(module.__file__).read_text())
        forbidden={'simulation','evaluation','scheduling','task_policies','protocol_evaluation'}
        assert not any(isinstance(node,ast.ImportFrom) and (node.module or '').split('.')[-1] in forbidden
                       for node in ast.walk(tree))
