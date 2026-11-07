"""Hardening tests: hand-authored fixtures, no registered RNG or population calls."""
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import gzip
import hashlib
import json
import os
import pytest
from spatial_memory import phase15_bprime as bp, phase15_generators as old, phase15_topology as top
from spatial_memory import phase15_bprime_protocol as protocol
from spatial_memory.phase15_bprime_access import StageBinding, checked_path, safe_read, packed, sha
from spatial_memory.phase15_bprime_records import validate_candidate, graph_fixture_evidence
from spatial_memory.phase15_bprime_coordinator import Coordinator, visual_selection
from spatial_memory.phase15_bprime_store import Checkpoints
from test_phase1_5_bprime import Tape, Oracle, make_inventory, record
from bprime_test_support import binding_for, toy_store, fixture


@pytest.fixture(autouse=True)
def forbid_registered_execution(monkeypatch):
    def deny(*a,**k):pytest.fail('Registered RNG/geometry execution is forbidden')
    monkeypatch.setattr(bp.Stream,'__init__',deny)
    monkeypatch.setattr(old.Stream,'__init__',deny)
    monkeypatch.setattr(bp,'geometry',deny)
    monkeypatch.setattr(old,'geometry',deny)


def permutation_indices(initial,target):
    values=list(initial);indices=[]
    assert set(values)==set(target) and len(values)==len(target)
    for i in range(len(values)-1,0,-1):
        j=values.index(target[i]);assert j<=i
        indices.append(j);values[i],values[j]=values[j],values[i]
    assert values==list(target)
    return indices


class Choices(Tape):
    def __init__(self,values):self.items=iter(values);super().__init__([])
    def choose(self,values):
        item=next(self.items);assert item in values
        self.bounds.append(len(values));self.choices.append(tuple(values));return item


def counter(stream,purpose):
    return dict(identity=sha(('explicit-fixture:'+purpose).encode()),words=len(stream.bounds),bounds=list(stream.bounds))


def bp_geometry_fixture(job):
    # Hand-authored partition: two width-three columns, six one-unit rows.
    choices=[12,(0,0,5,5),0,3]
    for x0,x1 in ((0,2),(3,5)):
        for y in range(5):choices += [(x0,y,x1,5),1,y+1]
    stream=Choices(choices);rooms,detail=bp.partition(stream)
    owner={(a,b):i for i,(a,b,c,d) in enumerate(rooms)}
    path=[owner[0,y] for y in range(6)]+[owner[3,y] for y in reversed(range(6))]
    tree=[tuple(sorted(e)) for e in zip(path,path[1:])]
    edges=bp.adjacency(rooms);target=tree+[e for e in edges if e not in tree]
    tree_stream=Tape(permutation_indices(edges,target))
    unused=sorted(set(edges)-set(tree))
    chords=Tape([0]+permutation_indices(unused,list(reversed(unused))))
    selected,graph=bp.connections(rooms,tree_stream,chords)
    doors=Choices([bp.door_options(rooms[a],rooms[b])[-1] for a,b in selected])
    free,raster=bp.rasterize(rooms,selected,doors)
    construction=dict(rooms=rooms,selected=selected,**detail,**graph,**raster,ancestral_roots=[job['identity']])
    streams={p:counter(s,p) for p,s in [('partition',stream),('tree',tree_stream),('chords',chords),('doors',doors)]}
    return free,construction,streams


def r_geometry_fixture(job):
    nodes=[(x,y) for y in range(4) for x in (range(4) if y%2==0 else reversed(range(4)))]
    tree=[tuple(sorted(e,key=old.row_key)) for e in zip(nodes,nodes[1:])]
    edges=old.lattice(4)
    target=tree+[e for e in edges if e not in tree]
    stream=Tape(permutation_indices(edges,target)+[3]*9+[4]*15)
    free,construction=old.generate_r(stream)
    construction['ancestral_roots']=[job['identity']]
    return free,construction,{'geometry':counter(stream,'geometry')}


def geometry_payload(job):
    free,construction,streams=(bp_geometry_fixture(job) if job['mechanism']=='BP' else r_geometry_fixture(job))
    graph,detail=top.raster_quotient(free);oracle=Oracle()
    topology=dict(matrix=list(map(list,graph.matrix)),exact=list(oracle.exact_certificate(graph)),
                  keys=list(map(list,sorted(oracle.near_certificates(graph)))),
                  cycle_rank=bp.cycle_rank(graph),normalized_vertices=graph.n,measurements=[])
    return dict(job,kind='candidate',version=bp.VERSION,profile='synthetic',outcome='same_partition_related',
        reasons=['same_partition_related'],geometry=dict(width=25,height=25,free=sorted(map(list,free),key=lambda c:(c[1],c[0])),construction=construction),
        topology=topology,roots=[job['identity']],streams=streams,world=None)


def complete_payload(payload):
    free=frozenset(map(tuple,payload['geometry']['free']));pair=Tape([0])
    start,goal,d=bp.choose_pair(free,pair)
    geo=old.Geometry('synthetic-fit',payload['mechanism'],7,free,{})
    streams=[Tape([0]),Tape([0])]
    schedules=[bp.build_schedule(geo,start,goal,s) for s in streams]
    payload=deepcopy(payload)
    payload.update(outcome='independent',reasons=['independent'],world=dict(start=start,goal=goal,distance=d,schedules=schedules))
    payload['streams'].update({'start-goal':counter(pair,'start-goal'),**{f'dynamics-{i}':counter(s,f'dynamics-{i}') for i,s in enumerate(streams)}})
    return payload


def job(mechanism='BP',index=0,sequence=0):
    return dict(identity=f'synthetic:fit:{mechanism}:{index}',partition='fit',mechanism=mechanism,index=index,sequence=sequence)


def loop_inventory(root):
    payload,ledger=make_inventory(root)
    # Replace all three explicit reference rasters with 1/2/3 thin cycles.
    for i,row in enumerate(payload['entries']):
        rank=protocol.CATEGORIES.index(row['category'])+1
        free={(x,y) for x in range(2*rank+1) for y in range(3) if x%2==0 or y in (0,2)}
        graph,_=top.raster_quotient(free);oracle=Oracle()
        exact=oracle.exact_certificate(graph);keys=oracle.near_certificates(graph)
        body=dict(geometry=dict(width=9,height=5,free=sorted(map(list,free))),matrix=list(map(list,graph.matrix)),exact=exact,near_certificates=sorted(keys))
        data=gzip.compress(packed(body),mtime=0);(root/row['path']).write_bytes(data)
        row.update(width=9,height=5,matrix=body['matrix'],exact=list(exact),near_keys=list(map(list,sorted(keys))),bytes=len(data),sha256=sha(data))
        ledger[row['identity']]['bytes']=len(data);ledger[row['identity']]['sha256']=sha(data)
    payload['ledger_sha256']=protocol.digest(ledger)
    return payload,ledger


def setup_coordinator(tmp_path,*,fault=None):
    archives=tmp_path/'archives';archives.mkdir()
    payload,ledger=loop_inventory(archives)
    root=tmp_path/'store';binding=binding_for(root,inventory=payload,ledger=ledger)
    refs=protocol.validate_inventory(payload,ledger,archives,expected_digest=protocol.digest(payload),
        expected_ledger_digest=protocol.digest(ledger),backend=Oracle(),synthetic=True,binding=binding)
    store=toy_store(root,binding=binding,backend=Oracle(),fault=fault)
    return store,refs,Coordinator(store,refs,backend=Oracle(),synthetic=True)


@pytest.mark.parametrize('shape',['ancestor','escape','alias','alternate','stage','unapproved'])
def test_access_negative_forms_before_open(tmp_path,shape):
    store=tmp_path/'store';binding=binding_for(store)
    if shape=='ancestor':target=tmp_path/'synthetic-final-held-out'/'input'
    elif shape=='escape':target=tmp_path/'..'/'outside'
    elif shape=='alias':
        (tmp_path/'alias').symlink_to(tmp_path,target_is_directory=True);target=tmp_path/'alias'/'file'
    elif shape=='alternate':target=tmp_path.parent/'another-root'/'file'
    elif shape=='stage':
        with pytest.raises(bp.IntegrityError):protocol.development_path(store,'assessment',binding)
        return
    else:
        with pytest.raises(bp.IntegrityError):StageBinding.load(binding.manifest_path,approved_sha256=binding.approved_sha256)
        return
    opened=[]
    def guarded(path):
        opened.append(Path(path))
        assert Path(path)==binding.manifest_path, 'Unauthorized target was opened'
        return safe_read(path)
    with patch('spatial_memory.phase15_bprime_access.safe_read',side_effect=guarded):
        with pytest.raises(bp.IntegrityError):binding.read(target)
    assert opened==[binding.manifest_path]



@pytest.mark.parametrize('group',['source','configuration','dependencies','references'])
def test_actual_commitments_rechecked_not_caller_hashes(tmp_path,group):
    binding=binding_for(tmp_path/'store');store=toy_store(tmp_path/'store',binding=binding)
    with store.writer():entry=store.write('synthetic:one',fixture({'test':1}))
    relative=next(iter(json.loads(binding.manifest_bytes)['files'][group]))
    (binding.root/relative).write_bytes(b'changed actual input')
    with pytest.raises(bp.IntegrityError):store.inventory([entry],['synthetic:one'])
    with pytest.raises(bp.IntegrityError):
        with store.writer():pass


@pytest.mark.parametrize('state',['changed','missing','stale','mixed'])
def test_lock_negative_states(tmp_path,state):
    store=toy_store(tmp_path/'store')
    with store.writer():entry=store.write('synthetic:one',fixture({'test':1}))
    lock=store.root/'run.json'
    if state=='missing':lock.unlink()
    elif state=='changed':lock.write_bytes(b'changed-lock')
    elif state=='stale':
        stale=store.lock;stale['source_sha256']='9'*64;lock.write_bytes(packed(stale))
    else:
        other=toy_store(tmp_path/'other')
        with other.writer():pass
        lock.write_bytes((other.root/'run.json').read_bytes())
    with pytest.raises(bp.IntegrityError):store.inventory([entry],['synthetic:one'])
    with pytest.raises(bp.IntegrityError):
        with store.writer():pass


BOUNDARIES=['after_stage_create','after_stage_fsync','after_link','after_destination_fsync','after_stage_unlink','after_stage_dir_fsync']
@pytest.mark.parametrize('boundary',BOUNDARIES)
@pytest.mark.parametrize('initial',[False,True])
def test_every_publication_crash_boundary(tmp_path,boundary,initial):
    root=tmp_path/'store';fired=[]
    def crash(point,path):
        if point==boundary and (path.name=='run.json')==initial and not fired:
            fired.append(point);raise OSError('deterministic crash')
    store=toy_store(root,fault=crash)
    with pytest.raises(OSError):
        with store.writer():store.write('synthetic:one',fixture({'value':1}))
    assert fired
    restored=toy_store(root)
    if boundary=='after_stage_create':
        with pytest.raises(bp.IntegrityError):
            with restored.writer():restored.recover(['synthetic:one'])
        assert list((root/'staging').glob('*.part'))
    else:
        with restored.writer():
            if not initial:restored.recover(['synthetic:one'])
            if initial:assert not restored.scan()
            else:assert len(restored.scan())==1


def test_duplicate_copy_is_not_same_publication_alias(tmp_path):
    store=toy_store(tmp_path/'store')
    with store.writer():
        entry=store.write('synthetic:one',fixture({'value':1}))
        (store.root/'staging'/'copy.part').write_bytes((store.root/entry['path']).read_bytes())
        with pytest.raises(bp.IntegrityError):store.recover(['synthetic:one'])
        assert (store.root/'staging'/'copy.part').exists()


def test_nonfirst_partition_and_doors_independent_raster_reconstruction():
    payload=geometry_payload(job());geometry=payload['geometry'];free=set(map(tuple,geometry['free']))
    construction=geometry['construction'];rooms=construction['rooms'];owner={}
    for i,(a,b,c,d) in enumerate(rooms):
        for x in range(4*a+1,4*c+4):
            for y in range(4*b+1,4*d+4):owner[x,y]=i
    edges=set()
    for door in free-owner.keys():
        x,y=door;adjacent={(x-1,y),(x+1,y),(x,y-1),(x,y+1)}&owner.keys()
        assert len(adjacent)==2;edges.add(tuple(sorted(owner[c] for c in adjacent)))
    assert edges==set(map(tuple,construction['selected']))
    assert construction['splits'][0]['cut']==3 and construction['splits'][1]['axis']==1
    assert any(len(bp.door_options(rooms[a],rooms[b]))>1 for a,b in construction['selected'])
    validate_candidate(payload,synthetic=True,backend=Oracle())


@pytest.mark.parametrize('target',list(__import__('itertools').permutations([(0,1),(1,2),(0,2)])))
def test_actual_fisher_yates_subset_pipeline(target):
    initial=[(0,1),(1,2),(0,2)]
    for k in range(4):
        tape=Tape([k]+permutation_indices(initial,target))
        drawn=tape.integer(4);subset=tape.permutation(initial)[:drawn]
        assert subset==list(target[:k]) and tape.bounds==[4,3,2]


@pytest.mark.parametrize('mutation',['empty','trace','counter','raster','matrix','key','world','pair','schedule','roots','identity','extra-purpose'])
def test_outcome_specific_schema_rejects_bad_evidence(mutation):
    payload=complete_payload(geometry_payload(job()))
    if mutation=='empty':payload={}
    elif mutation=='trace':payload['geometry']['construction']['splits'].pop()
    elif mutation=='counter':payload['streams']['chords']['bounds']=[]
    elif mutation=='raster':payload['geometry']['free'].pop()
    elif mutation=='matrix':payload['topology']['matrix']=[[8]]
    elif mutation=='key':payload['topology']['keys']=[]
    elif mutation=='world':payload['world']=None
    elif mutation=='pair':payload['world']['distance']=11
    elif mutation=='schedule':payload['world']['schedules'][0]['initial']=[[1,1]]
    elif mutation=='roots':payload['roots']=['laundered']
    elif mutation=='identity':payload['identity']='synthetic:wrong'
    else:payload['streams']['geometry']=payload['streams']['partition']
    with pytest.raises(bp.IntegrityError):validate_candidate(payload,synthetic=True,backend=Oracle())


def test_credit_requires_bound_validated_world_and_detects_mutation():
    payload=complete_payload(geometry_payload(job()));evidence=validate_candidate(payload,synthetic=True,backend=Oracle())
    index=protocol.AdmissionIndex(synthetic=True)
    with pytest.raises(bp.IntegrityError):index.admit(evidence.record,complete=True)
    payload['world']['distance']=999
    with pytest.raises(bp.IntegrityError):index.admit(evidence.record,evidence=evidence)


class Builder:
    def __init__(self):self.geometry_calls=0;self.world_calls=0
    def geometry(self,job):self.geometry_calls+=1;return geometry_payload(job)
    def complete(self,payload):self.world_calls+=1;return complete_payload(payload)


def test_coordinator_commit_rebuild_and_no_repeat_of_related_world(tmp_path):
    store,refs,coordinator=setup_coordinator(tmp_path);builder=Builder()
    with store.writer():
        coordinator.execute_one(builder)
        coordinator.execute_one(builder)
        rows=store.scan()
        assert [p['mechanism'] for _,p in sorted(rows,key=lambda r:r[1]['sequence'])]==['R','BP']
        assert builder.geometry_calls==2 and builder.world_calls==1
        assert coordinator.index.credits('synthetic-fit')=={'R':1}
        restart=Coordinator(store,refs,backend=Oracle(),synthetic=True);restart.restore()
        assert restart.sequence==2 and restart.index.credits('synthetic-fit')=={'R':1}
        assert builder.geometry_calls==2


def test_coordinator_uncheckpointed_crash_never_reexecutes(tmp_path):
    store,refs,coordinator=setup_coordinator(tmp_path)
    class Crash(Builder):
        def geometry(self,job):raise KeyboardInterrupt('explicit interruption')
    with store.writer():
        with pytest.raises(KeyboardInterrupt):coordinator.execute_one(Crash())
        builder=Builder()
        with pytest.raises(bp.IntegrityError):coordinator.execute_one(builder)
        assert builder.geometry_calls==0 and (store.root/'pending.json').exists()


def test_coordinator_terminal_error_persisted_and_stops(tmp_path):
    store,refs,coordinator=setup_coordinator(tmp_path)
    class Bad(Builder):
        def geometry(self,job):raise ValueError('explicit malformed fixture')
    with store.writer():
        coordinator.execute_one(Bad());assert coordinator.stopped
        with pytest.raises(bp.IntegrityError):coordinator.execute_one(Builder())
        assert store.scan()[0][1]['outcome']=='implementation_error'


def test_production_coordinator_disabled_before_access():
    with pytest.raises(bp.IntegrityError,match='disabled'):
        Coordinator(None,None,backend=None)


def test_visual_selection_exact_hash_order_ceiling_and_no_rng():
    identities=['synthetic:representative:'+str(i) for i in range(12)]
    def independent(identity):
        data=b''
        for value in (bp.VERSION,'visual-audit',identity):
            encoded=value.encode();data+=len(encoded).to_bytes(4,'little')+encoded
        return hashlib.sha256(data).hexdigest(),identity
    expected=sorted(identities,key=independent)[:3]
    assert visual_selection(list(reversed(identities)))==expected
    assert visual_selection([])==[]
    assert len(visual_selection(identities[:6]))==2
    with pytest.raises(bp.IntegrityError):visual_selection(['same','same'])


def test_bound_objects_and_credit_attestations_cannot_be_relabelled(tmp_path):
    from dataclasses import replace
    binding=binding_for(tmp_path/'store')
    with pytest.raises(bp.IntegrityError):replace(binding,root=tmp_path/'different').verify()
    payload=complete_payload(geometry_payload(job()))
    evidence=validate_candidate(payload,synthetic=True,backend=Oracle())
    index=protocol.AdmissionIndex(synthetic=True)
    with pytest.raises(bp.IntegrityError):index.admit(evidence.record,evidence=replace(evidence,complete=False))
    archives=tmp_path/'archives';archives.mkdir();inventory,ledger=loop_inventory(archives)
    committed=binding_for(tmp_path/'second',inventory=inventory,ledger=ledger)
    references=protocol.validate_inventory(inventory,ledger,archives,expected_digest=protocol.digest(inventory),
        expected_ledger_digest=protocol.digest(ledger),backend=Oracle(),synthetic=True,binding=committed)
    with pytest.raises(bp.IntegrityError):replace(references,included=()).load(protocol.AdmissionIndex(synthetic=True))


@pytest.mark.parametrize('foreign',['unknown','recovered'])
def test_missing_original_lock_with_other_evidence_cannot_reinitialize(tmp_path,foreign):
    store=toy_store(tmp_path/'store')
    with store.writer():pass
    (store.root/'run.json').unlink()
    target=store.root/'unknown' if foreign=='unknown' else store.root/'recovered'/'old-evidence'
    target.write_bytes(b'preserved')
    with pytest.raises(bp.IntegrityError):
        with store.writer():pass
    assert target.read_bytes()==b'preserved'


@pytest.mark.parametrize('boundary',BOUNDARIES[1:])
def test_coordinator_publication_crash_recovers_without_calling_builder(tmp_path,boundary):
    fired=[]
    def crash(point,path):
        if path.name.endswith('.json.gz') and point==boundary and not fired:
            fired.append(point);raise OSError('explicit checkpoint interruption')
    store,refs,coordinator=setup_coordinator(tmp_path,fault=crash);builder=Builder()
    with pytest.raises(OSError):
        with store.writer():coordinator.execute_one(builder)
    assert builder.geometry_calls==1
    restored=toy_store(store.root,binding=store.binding,backend=Oracle())
    restarted=Coordinator(restored,refs,backend=Oracle(),synthetic=True)
    with restored.writer():
        restarted.restore()
        assert restarted.sequence==1 and not (restored.root/'pending.json').exists()
        assert not list((restored.root/'staging').glob('*.part'))
    assert builder.geometry_calls==1


def test_missing_committed_checkpoint_does_not_trigger_regeneration(tmp_path):
    store,refs,coordinator=setup_coordinator(tmp_path);builder=Builder()
    with store.writer():
        entry=coordinator.execute_one(builder)
        (store.root/entry['path']).unlink()
        with pytest.raises(bp.IntegrityError,match='Missing/conflicting completed'):
            coordinator.execute_one(builder)
        assert builder.geometry_calls==1


def test_full_connections_pipeline_all_small_unused_permutations():
    from itertools import permutations
    rooms=sorted((x,y,x+2,z) for x in (0,3) for y,z in ((0,0),(1,1),(2,3),(4,5)))
    edges=bp.adjacency(rooms)
    ids={(a,b):i for i,(a,b,c,d) in enumerate(rooms)}
    path=[ids[0,y] for y in (0,1,2,4)]+[ids[3,y] for y in (4,2,1,0)]
    tree=[tuple(sorted(e)) for e in zip(path,path[1:])]
    unused=sorted(set(edges)-set(tree));assert len(unused)==3
    tree_order=tree+[e for e in edges if e not in tree]
    for order in permutations(unused):
        for k in range(4):
            chord=Tape([k]+permutation_indices(unused,order))
            selected,detail=bp.connections(rooms,Tape(permutation_indices(edges,tree_order)),chord)
            assert detail['extra']==list(order[:k]) and chord.bounds==[4,3,2]
            assert set(selected)==set(tree)|set(order[:k])


def test_terminal_dynamic_failure_and_scientific_rejection_classification(tmp_path):
    store,refs,coordinator=setup_coordinator(tmp_path)
    class Exhaust(Builder):
        def complete(self,payload):raise old.DynamicLimit('128 explicit fixture failures')
    with store.writer():
        coordinator.execute_one(Exhaust())
        assert store.scan()[0][1]['outcome']=='DynamicLimit' and coordinator.stopped
    # Scientific geometry rejection is a saved rejection, never a new credit.
    payload=dict(job('V'),kind='candidate',version=bp.VERSION,profile='synthetic',
        outcome='voronoi_seed_separation',reasons=['voronoi_seed_separation'],phase='geometry',
        rejection_evidence={'seeds':[[1,1],[1,2]]+[[x,8] for x in range(1,11)],'reason':'explicit separation witness'},
        streams={'geometry':{'identity':'a'*64,'words':529,'bounds':[3]+list(range(529,1,-1))}})
    evidence=validate_candidate(payload,synthetic=True,backend=Oracle())
    assert not evidence.complete and evidence.record is None
    payload['mechanism']='BP';payload['identity']='synthetic:fit:BP:0'
    with pytest.raises(bp.IntegrityError):validate_candidate(payload,synthetic=True,backend=Oracle())


def test_visual_population_selection_requires_completed_sealed_partition(tmp_path):
    store,refs,coordinator=setup_coordinator(tmp_path)
    with store.writer():
        coordinator.execute_one(Builder())
        with pytest.raises(bp.IntegrityError,match='quota'):
            coordinator.visual_representatives()


def test_no_automatic_next_stage_without_approved_prior_seals(tmp_path):
    store,refs,coordinator=setup_coordinator(tmp_path)
    # Altering an in-memory object cannot grant a new stage: manifest remains fit.
    with pytest.raises(bp.IntegrityError):
        Checkpoints(store.root,partition='calibration',synthetic=True,binding=store.binding,backend=Oracle())


def test_pending_shape_and_changed_reference_commitment_stop_before_builder(tmp_path):
    store,refs,coordinator=setup_coordinator(tmp_path)
    with store.writer():
        (store.root/'pending.json').write_bytes(packed({'run_id':store.run_id,'job':{}}))
        builder=Builder()
        with pytest.raises(bp.IntegrityError):coordinator.execute_one(builder)
        assert builder.geometry_calls==0
    bad=deepcopy(json.loads(store.binding.manifest_bytes))
    assert bad['reference_inventory_sha256']==refs.sha256


def test_counter_and_descriptor_conflicts_are_not_accepted():
    payload=complete_payload(geometry_payload(job()))
    payload['streams']['start-goal']['bounds']=[1]
    with pytest.raises(bp.IntegrityError):validate_candidate(payload,synthetic=True,backend=Oracle())
    payload=geometry_payload(job());payload['geometry']['construction']['room_count']=999
    with pytest.raises(bp.IntegrityError):validate_candidate(payload,synthetic=True,backend=Oracle())


@pytest.mark.parametrize('outcome,witness',[
    ('outer_ring',{'free':[[0,1]]}),
    ('free_count',{'free':[[1,1]]}),
    ('density',{'free':[[x,y] for x in range(1,21) for y in range(1,5)]}),
    ('connectivity',{'free':[[x,y] for x in (*range(1,6),*range(10,15)) for y in range(1,11)]}),
    ('voronoi_region_connectivity',{'region':[[1,1],[3,1]]}),
    ('voronoi_core',{'region':[[1,1]],'core':[]}),
    ('voronoi_no_corridor',{'allowed':[[1,1],[3,1]],'core_a':[[1,1]],'core_b':[[3,1]]}),
    ('voronoi_unintended_adjacency',{'free':[[1,1],[2,1],[3,1]],'cores':[[[1,1]],[[3,1]]],'chosen_edges':[]}),
])
def test_independent_local_rejection_witnesses(outcome,witness):
    from spatial_memory.phase15_bprime_records import validate_rejection
    validate_rejection(outcome,witness,{})
    if outcome=='outer_ring':
        with pytest.raises(bp.IntegrityError):validate_rejection(outcome,{'free':[[1,1]]},{})


def test_corrupt_seed_failure_witness_is_not_a_scientific_rejection():
    from spatial_memory.phase15_bprime_records import validate_rejection
    witness={'seeds':[[x,y] for y in (2,10,18) for x in (2,8,14,20)]}
    counters={'geometry':{'identity':'a'*64,'words':529,'bounds':[3]+list(range(529,1,-1))}}
    with pytest.raises(bp.IntegrityError):validate_rejection('voronoi_seed_separation',witness,counters)


@pytest.mark.parametrize('operation',['publication','inventory','recovery'])
def test_lock_rechecked_inside_active_lease(tmp_path,operation):
    store=toy_store(tmp_path/'store')
    with store.writer():
        entry=store.write('synthetic:one',fixture({'value':1}))
        (store.root/'run.json').write_bytes(b'changed during active lease')
        with pytest.raises(bp.IntegrityError):
            if operation=='publication':store.write('synthetic:two',fixture({'value':2}))
            elif operation=='inventory':store.inventory([entry],['synthetic:one'])
            else:store.recover(['synthetic:one'])
        assert len(list((store.root/'records').iterdir()))==1
