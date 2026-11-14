import copy,json,math,sys
from pathlib import Path
import numpy as np
import pytest
from spatial_memory.dao_generator_v1 import generate_test,generate_population,validate,FAMILIES
from spatial_memory.dao_admission_v1 import (occupancy_hash,endpoint_hash,corridor_graph,exact_isomorphic,
    graph_edit,near_occupancy,admission,ImmutableLog,inventory_commitment,stream_seed,graph_signature)
from spatial_memory.dao_statistics_v1 import (compare,contact_upper,holm,select_candidate,simulate_completion,paired_arrays)
from spatial_memory.dao_navigation_v1 import DAONavigationV1
from spatial_memory.discovery_observation import DiscoveryController


@pytest.mark.parametrize('family',FAMILIES)
@pytest.mark.parametrize('size',(25,33,41))
def test_test_generator_schema_clearance_determinism(family,size):
    a=generate_test(101,family=family,width=size,height=size,category='moving',persistent='relocate')
    b=generate_test(101,family=family,width=size,height=size,category='moving',persistent='relocate')
    assert json.dumps(a,sort_keys=True)==json.dumps(b,sort_keys=True)
    assert validate(a) and a['partition']=='TEST' and not a['production_ready']
    assert a['schedules'][0] is not a['schedules'][1] and a['events']


@pytest.mark.parametrize('condition',('unchanged','add','remove','relocate'))
@pytest.mark.parametrize('category',('none','static','moving'))
def test_generator_event_category_and_real_strata(condition,category):
    a=generate_test(21,family='mixed',width=25,height=33,persistent=condition,category=category,discovery='occluded',revisit='rare')
    assert validate(a) and a['persistent_condition']==condition
    assert bool(a['events'])==(condition!='unchanged')
    assert bool(a['schedules'][0])==(category!='none')
    if category=='static':assert all(len(p)==1 for p in a['schedules'][0])
    bad=copy.deepcopy(a);bad['certificate'][1]=bad['certificate'][-1]
    with pytest.raises(ValueError):validate(bad)


def test_namespace_and_production_disabled():
    for p in ('pilot','development','sealed','evaluation'):
        with pytest.raises(PermissionError):generate_test(1,namespace=p)
        with pytest.raises(PermissionError):generate_population(partition=p)
        with pytest.raises(PermissionError):stream_seed(b'x'*32,p,0,'layout')
    streams={stream_seed(b'x'*32,'TEST',0,k) for k in ('layout','objects','persistent','phase0','phase1')}
    assert len(streams)==5 and streams!={stream_seed(b'x'*32,'TEST',1,'layout')}


def test_canonical_transform_padding_and_endpoint_independence():
    g=np.zeros((7,9),int);g[1:6,1]=1;g[5,1:8]=1;g[2,5]=1
    assert occupancy_hash(g)==occupancy_hash(np.pad(np.rot90(g),((2,3),(4,1))))
    assert occupancy_hash(g)==occupancy_hash(np.fliplr(g))
    assert endpoint_hash(g,(3,3),(6,3))!=endpoint_hash(g,(4,3),(6,3))
    candidate={'occupancy':g.tolist(),'family':'tree'}
    rotated={'occupancy':np.rot90(g).tolist(),'family':'loop'}
    assert admission(candidate,[rotated])['status']=='STRUCTURAL_DUPLICATE'
    assert admission(candidate,[])['status']=='INCOMPLETE'
    assert admission(candidate,[],prior_opaque_signatures=[])['status']=='TEST_UNIQUE'


def test_exact_graph_permutation_and_budget_quarantine():
    a={'nodes':[[1],[2],[1]],'edges':[[0,1,[2]],[1,2,[3]]]}
    b={'nodes':[[1],[1],[2]],'edges':[[1,2,[2]],[2,0,[3]]]}
    assert exact_isomorphic(a,b)['match'] is True
    assert graph_signature(a)==graph_signature(b)
    assert exact_isomorphic(a,b,budget=0)['match'] is None
    c=copy.deepcopy(b);c['edges'][0][2]=[9]
    assert exact_isomorphic(a,c)['match'] is False
    assert graph_edit(a,b)['distance']==0 and graph_edit(a,c)['distance']>0
    assert graph_edit(a,c,budget=0)['distance'] is None
    cycle={'nodes':[[2]]*6,'edges':[[i,(i+1)%6,[]] for i in range(6)]}
    triangles={'nodes':[[2]]*6,'edges':[[0,1,[]],[1,2,[]],[2,0,[]],[3,4,[]],[4,5,[]],[5,3,[]]]}
    assert graph_signature(cycle)==graph_signature(triangles)
    assert exact_isomorphic(cycle,triangles)['match'] is False


def test_corridor_graph_cycle_and_near_geometry():
    g=np.ones((7,7),int);g[1,1:6]=0;g[5,1:6]=0;g[1:6,1]=0;g[1:6,5]=0
    graph=corridor_graph(g);assert len(graph['nodes'])==1 and graph['edges'][0][0]==graph['edges'][0][1]
    assert exact_isomorphic(graph,corridor_graph(np.rot90(g)))['match'] is True
    assert near_occupancy(g,np.rot90(g))==0
    modified=g.copy();modified[3,3]=0
    assert 0<near_occupancy(g,modified)<.05


def test_immutable_logs_and_inventory(tmp_path):
    log=ImmutableLog(tmp_path/'events');log.append({'namespace':'TEST','event':'generated'});log.append({'event':'quarantined'})
    assert len(log.read())==2
    entries=[{'lineage_id':'TEST:0','x':1},{'lineage_id':'TEST:1','x':2}]
    assert inventory_commitment(entries,b's'*16)==inventory_commitment(entries[::-1],b's'*16)
    assert inventory_commitment(entries,b's'*16)!=inventory_commitment(entries,b't'*16)
    (tmp_path/'events/000000.json').write_text('{}')
    with pytest.raises((AssertionError,KeyError)):log.read()
    with pytest.raises(ValueError):inventory_commitment(entries+entries,b's'*16)


def outcomes(n=20,goal_a=1,goal_b=1):
    rows=[]
    for i in range(n):
        for s in (0,1):
            for arm,g in [('age5',goal_b),('dao_veto',goal_a)]:
                rows.append(dict(lineage=f'SYNTHETIC:{i}',partition='SYNTHETIC',schedule=s,arm=arm,goal=g,
                    contacts=0,paid=8 if arm=='dao_veto' else 10,emergency_rays=61*20,
                    steps=20 if arm=='dao_veto' else 24,distance=12 if arm=='dao_veto' else 15,
                    wall=.2,scheduler_ms=2.))
    return rows


def test_paired_bootstrap_denominators_and_owner_vs_scientific():
    rows=outcomes();r=compare(rows,'dao_veto','age5',replicates=200)
    assert r['lineages']==20 and r['schedules']==40 and r['completion']['mean']==0
    assert r['original_owner_descriptive_target'] and not r['completion_noninferiority_proposed']
    assert r['movement']['steps']['difference']==-4
    assert r==compare(rows,'dao_veto','age5',replicates=200)
    missing=outcomes(goal_a=0);r=compare(missing,'dao_veto','age5',replicates=200)
    assert r['movement']['steps']['benefit_contrast'] is None and r['movement']['steps']['bootstrap_missing_fraction']==1
    assert not r['joint_proposed_pass'] and not r['original_owner_descriptive_target']
    assert r['movement']['steps']['failure_penalized_difference']['mean']==56


def test_pairing_validation_and_rare_contacts():
    rows=outcomes()
    with pytest.raises(ValueError):paired_arrays(rows[:-1],'dao_veto','age5')
    with pytest.raises(ValueError):paired_arrays(rows+[rows[0]],'dao_veto','age5')
    assert math.isclose(contact_upper(0,200),1-.05**(1/200))
    assert contact_upper(1,200)>contact_upper(0,200)
    assert contact_upper(200,200)==1
    assert abs(contact_upper(1,2)-math.sqrt(.95))<1e-12


def test_holm_fixed_sequence_and_no_sealed_selection():
    adjusted=holm({'a':.01,'b':.04,'c':.2});assert adjusted['a']['reject'] and not adjusted['b']['reject']
    rows=outcomes();assert select_candidate(rows)['candidate']=='dao_veto'
    assert select_candidate(rows,stage='confirmation',confirmed_candidate='dao_veto')['candidate']=='dao_veto'
    rows[0]['partition']='sealed'
    with pytest.raises(PermissionError):select_candidate(rows)
    for row in rows:row['partition']='SYNTHETIC'
    for row in rows:
        if row['arm']=='dao_veto':row['contacts']=1
    r=compare(rows,'dao_veto','age5',replicates=100)
    assert not r['fixed_sequence'][0]['criterion_passed'] and not r['fixed_sequence'][1]['eligible']


def test_simulation_variance_correlation_and_null_direction():
    low=simulate_completion(n=100,repetitions=150,correlation=0.,discordance=.2)
    high=simulate_completion(n=100,repetitions=150,correlation=1.,discordance=.2)
    assert high['mean_lineage_sd']>low['mean_lineage_sd']
    assert low['coverage']>.85 and high['coverage']>.85
    assert simulate_completion(n=100,repetitions=150,loss=.05)['proposed_NI_probability']<.2


@pytest.mark.parametrize('mode',('dao_veto','dao_trigger','dao_route','dao_combined'))
def test_adapter_exact_frozen_request_parity_and_route_cost(mode):
    from spatial_memory.navigation import plan
    grid=np.zeros((15,15),np.int8);grid[:,7:]=-1
    adapter=DAONavigationV1(grid,mode=mode);frozen=DiscoveryController(grid,mode=mode)
    for step in range(1,16):
        route=plan(frozen.memory.grid,(3,7),(12,7),'optimistic') if mode=='dao_route' else None
        adapter.set_navigation_context(goal=(12,7),yaw=0.,unknown='optimistic')
        frozen.set_navigation_context(goal=(12,7),yaw=0.,route=route)
        assert adapter.decide(step,(3,7))==frozen.decide(step,(3,7))
        if adapter._pending is not None:
            reading=np.full(grid.shape,-1,np.int8);adapter.refresh(reading,step);frozen.refresh(reading,step)
    assert adapter.route_plan_calls==(15 if mode=='dao_route' else 0)


def test_actual_navigation_wrapper_accounting_small_engineering_scene():
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
    import run_dao_integration_v1 as run
    from dao_engineering_scenes_v1 import scenes
    d=scenes()[0];d['horizon']=6
    e=run.run_navigation(d,'dao_route')
    assert e['actual_calls']['memory']==len(e['scans'])==e['metrics']['observation_count']
    assert e['actual_calls']['emergency']==6 and e['route_plan_calls']==6
    assert e['actual_calls']['memory']>=2
    assert e['scans'][0]['computed_before_actual_reading']


def test_generation_admission_logging_are_immutable_and_test_only(tmp_path):
    from spatial_memory.dao_generator_v1 import generate_test_logged
    from spatial_memory.dao_admission_v1 import admit_test_logged
    payload=generate_test_logged(101,tmp_path,family='tree')
    decision=admit_test_logged(payload,[],tmp_path)
    assert decision['status']=='INCOMPLETE'
    assert len(ImmutableLog(tmp_path/'generation').read())==2
    assert len(ImmutableLog(tmp_path/'admission').read())==1
    with pytest.raises(FileExistsError):generate_test_logged(101,tmp_path,family='tree')
    altered=copy.deepcopy(payload);altered['partition']='pilot'
    with pytest.raises(PermissionError):admit_test_logged(altered,[],tmp_path)
