"""Independent formula and boundary checks for frozen public-input policies."""
from dataclasses import replace
import inspect
import math
import numpy as np
import pytest
from spatial_memory.scheduling import AdaptiveObserver, ObservationController
from spatial_memory.navigation import plan
from spatial_memory.task_policies import (METHODS, ABLATIONS, PolicyParameters, TaskObserver,
    PolicyController, belief, precommit_schedule, ray_prediction, disk_cells)


def observer(method='disruption-visible',grid=None,**kw):
    if grid is None:
        grid=np.zeros((3,5),dtype=np.int8)
    return TaskObserver(grid,method,goal=(4,1),radius=3,**kw)


def test_exact_belief_formula_unknown_and_fixed_rate():
    a=AdaptiveObserver(np.array([[0,1,-1]]),'uncertainty',3)
    p,h=belief(a,5)
    expected=.5-.45*math.exp(-.5)
    assert p.tolist()[0]==pytest.approx([expected,1-expected,.5])
    np.testing.assert_allclose(h,a.uncertainty(5))
    a.refresh(np.array([[1,1,-1]]),5)
    p,_=belief(a,8,.05)
    assert p[0,0]==pytest.approx(.5+.45*math.exp(-.3))
    assert p[0,0]==p[0,1]
    adapted,_=belief(a,8)
    assert adapted[0,0]!=adapted[0,1]
    assert p[0,2]==.5


def test_visibility_unique_supercover_and_endpoint_exclusion():
    p=np.full((3,3),.5)
    known=np.ones((3,3),bool)
    # diagonal supercover includes both corner-adjacent cells, excludes endpoints
    value,unknown=ray_prediction(p,(0,0),(1,1),known)
    assert value==.25 and not unknown
    known[0,1]=False
    assert ray_prediction(p,(0,0),(1,1),known)==(.25,True)
    assert ray_prediction(p,(0,0),(0,0),known)==(1.,False)
    assert ray_prediction(p,(0,0),(1,0),known)==(1.,False)
    p[0,1]=.95
    assert ray_prediction(p,(0,0),(2,0),known)[0]==pytest.approx(.05)


def test_candidates_lexicographic_and_counterfactual_costs_do_not_mutate():
    a=observer()
    before=a.memory.grid.copy()
    result=a.decide(5,(1,1),3)
    candidates=result['details']['candidates']
    assert [r['cell'] for r in candidates]==sorted(r['cell'] for r in candidates)
    assert (1,1) not in [r['cell'] for r in candidates]
    for r in candidates:
        x,y=r['cell']
        costs=[]
        for z in (0,1):
            g=before.copy();g[y,x]=z
            path=plan(g,(1,1),(4,1))
            costs.append(len(path)-1 if path else before.size+1)
        assert r['costs']==costs
        assert r['disruption']==min(before.size,abs(costs[1]-costs[0]))/before.size
    expected=np.float64(0.)
    for r in candidates:
        expected+=np.float64(r['visibility'])*r['risk']*r['disruption']
    assert result['score']==expected
    np.testing.assert_array_equal(a.memory.grid,before)


def test_disruption_strict_threshold_and_visible_mass_boundary():
    a=observer(parameters=PolicyParameters(budget_price=0))
    result=a.decide(5,(1,1),None)
    score=result['score']
    a.observation_cost=1.
    a.parameters=replace(a.parameters,disruption_threshold=score)
    assert not a.decide(5,(1,1),None)['requested']
    a.parameters=replace(a.parameters,disruption_threshold=np.nextafter(score,0.))
    assert a.decide(5,(1,1),None)['requested']
    assert result['details']['visible_mass']>=.25


def test_route_weighted_formula_and_strict_tie():
    grid=np.zeros((3,5),np.int8);grid[0,0]=-1
    a=observer('route-weighted',grid=grid)
    r=a.decide(5,(1,1),3)
    route=set(r['details']['route'])
    entropy=np.array(r['details']['entropy'])
    cells=disk_cells(grid.shape,(1,1),3)
    expected=sum((4 if c in route else 1)*entropy[c[1],c[0]] for c in cells)/sum(4 if c in route else 1 for c in cells)
    assert r['score']==expected
    a.parameters=replace(a.parameters,route_threshold=expected)
    assert not a.decide(5,(1,1),3)['requested']


def test_fixed_rate_exact_tie_and_empty_known_footprint():
    a=observer('fixed-rate')
    r=a.decide(5,(1,1),3)
    a.parameters=replace(a.parameters,entropy_threshold=r['score'])
    assert not a.decide(5,(1,1),3)['requested']
    b=observer('fixed-rate',grid=np.full((3,5),-1,np.int8))
    assert not b.decide(5,(1,1),3)['requested']


@pytest.mark.parametrize('method',METHODS)
def test_total_cap_denial_no_sensor_and_no_history_reset(method):
    grid=np.zeros((3,5),np.int8)
    schedule=(1,2) if method in {'random-quota','quota-periodic'} else ()
    c=PolicyController(grid,method,goal=(4,1),max_observations=1,schedule=schedule)
    before=c.memory.grid.copy()
    for t in range(1,11):
        d=c.decide(t,(1,1))
        assert not d['observation_granted']
        assert d['scheduler_seconds']>=0 and d['scheduler_astar_calls']>=0
    assert c.used==1
    np.testing.assert_array_equal(before,c.memory.grid)
    with pytest.raises(ValueError,match='exhausted'):
        c.refresh(grid,10)
    assert c.denied==c.requests


@pytest.mark.parametrize('method',['static','age','uncertainty','periodic1','periodic2','periodic5'])
def test_legacy_delegation_exact_decisions_and_refresh(method):
    grid=np.zeros((3,5),np.int8)
    c=PolicyController(grid,method,goal=(4,1),max_observations=4)
    old=ObservationController(grid,'periodic' if method.startswith('periodic') else method,
        interval=int(method[-1]) if method.startswith('periodic') else 2,max_observations=4)
    for t in range(1,15):
        a,b=c.decide(t,(1,1)),old.decide(t,(1,1))
        for key in b:
            assert a[key]==b[key]
        if b['observation_granted']:
            partial=grid.copy();partial[0,0]=-1
            c.refresh(partial,t);old.refresh(partial,t)
        np.testing.assert_array_equal(c.memory.grid,old.memory.grid)
    assert (c.used,c.requests,c.denied)==(old.used,old.requests,old.denied)


@pytest.mark.parametrize('cap',[1,2,4,8,16,None])
def test_precommitted_rng_and_quota_schedule(cap):
    rng=lambda rep:np.random.default_rng(np.random.SeedSequence([101,1404,rep]))
    a=precommit_schedule('random-quota',cap,40,rng(0))
    assert a==precommit_schedule('random-quota',cap,40,rng(0))
    q=8 if cap is None else cap-1
    assert len(a)==len(set(a))==q
    assert all(1<=t<=40 for t in a)
    even=precommit_schedule('quota-periodic',cap,40)
    assert even==tuple(j*40//q for j in range(1,q+1))
    if q:
        assert a!=precommit_schedule('random-quota',cap,40,rng(1))


def test_no_route_and_unknown_handling_query_and_route_weighted():
    grid=np.ones((3,5),np.int8);grid[1,1]=0
    q=observer('query-gate-conceptual',grid=grid)
    r=q.decide(5,(1,1),0)
    assert not r['requested'] and not r['details']['route']
    a=observer('route-weighted',grid=grid)
    r=a.decide(5,(1,1),3)
    assert all(w==1 for w in r['details']['weights'])
    d=observer(grid=grid).decide(5,(1,1),0)
    assert d['details']['remaining_path_estimate']==grid.size+1
    assert math.isfinite(d['threshold'])


def test_query_gate_inclusive_visibility_tie_next_action_and_cost():
    grid=np.zeros((3,5),np.int8)
    a=observer('query-gate-conceptual',grid=grid)
    r=a.decide(5,(1,1),3)
    assert r['details']['low_confidence_cells']
    assert r['details']['masked_route']==[]
    assert r['details']['cost_increase']>=1
    a.parameters=replace(a.parameters,visibility_fraction=r['score'])
    assert a.decide(5,(1,1),3)['requested']
    a.parameters=replace(a.parameters,visibility_fraction=np.nextafter(r['score'],1.))
    assert not a.decide(5,(1,1),3)['requested']


@pytest.mark.parametrize('ablation',ABLATIONS)
def test_ablation_only_intended_component(ablation):
    grid=np.zeros((3,5),np.int8);grid[0,1]=-1;grid[0,3]=1
    a=observer(grid=grid)
    b=observer(grid=grid,ablation=ablation)
    # Nonuniform history makes fixed-rate ablation observable.
    update=grid.copy();update[1,2]=1
    a.refresh(update,4);b.refresh(update,4)
    old,new=a.decide(9,(1,1),2),b.decide(9,(1,1),2)
    before={r['cell']:r for r in old['details']['candidates']}
    after={r['cell']:r for r in new['details']['candidates']}
    if ablation=='exclude-unknown':
        assert set(after)=={c for c in before if grid[c[1],c[0]]!=-1}
    elif ablation=='no-alternative-candidates':
        assert set(after)==set(before)&set(old['details']['route'])
    else:
        assert before.keys()==after.keys()
    for cell,row in after.items():
        reference=before[cell]
        assert row['costs']==reference['costs']
        if ablation=='no-route-disruption':
            assert row['disruption']==1
        else:
            assert row['disruption']==reference['disruption']
        if ablation=='no-visibility':
            assert row['visibility']==1
        elif ablation!='fixed-rate':
            assert row['visibility']==reference['visibility']
        if ablation!='fixed-rate':
            assert row['risk']==reference['risk']
    if ablation=='no-budget-threshold':
        assert new['threshold']==.1*1.5
        assert new['score']==old['score']
    else:
        assert new['threshold']==old['threshold']
    if ablation=='fixed-rate':
        assert new['details']['probabilities']!=old['details']['probabilities']
    np.testing.assert_array_equal(a.memory.grid,b.memory.grid)
    np.testing.assert_array_equal(a.history.last_observed,b.history.last_observed)


def test_public_interface_does_not_accept_world_labels_or_event_schedule():
    import spatial_memory.task_policies as module
    source=inspect.getsource(module)
    for forbidden in ('from .simulation','from .robustness','from .manifests','from .evaluation'):
        assert forbidden not in source
    assert set(inspect.signature(TaskObserver.decide).parameters)=={'self','step','position','remaining'}
    with pytest.raises(TypeError):
        TaskObserver(np.zeros((3,5)),'route-weighted',goal=(4,1),world=object())
    for method in ('route-weighted','disruption-visible','query-gate-conceptual'):
        a,b=observer(method),observer(method)
        assert a.decide(5,(1,1),3)==b.decide(5,(1,1),3)


def test_invalid_and_nonmonotone_inputs():
    with pytest.raises(ValueError):
        observer(ablation='repair-route')
    with pytest.raises(ValueError):
        PolicyParameters(budget_price=float('nan'))
    c=PolicyController(np.zeros((3,5),np.int8),'route-weighted',goal=(4,1))
    c.decide(1,(1,1))
    with pytest.raises(ValueError):
        c.decide(1,(1,1))


def test_disruption_visible_mass_exact_quarter_inclusive(monkeypatch):
    import spatial_memory.task_policies as module
    a=TaskObserver(np.zeros((3,5),np.int8),'disruption-visible',goal=(1,0),radius=1,
        parameters=PolicyParameters(disruption_threshold=0,budget_price=0))
    monkeypatch.setattr(module,'ray_prediction',lambda *args:(.125,False))
    r=a.decide(1,(0,0),None)
    assert r['details']['visible_mass']==.25 and r['score']>0 and r['requested']
    monkeypatch.setattr(module,'ray_prediction',lambda *args:(float(np.nextafter(.125,0.)),False))
    r=a.decide(1,(0,0),None)
    assert r['details']['visible_mass']<.25 and not r['requested']


def test_query_reliability_equality_does_not_mask_known_cells():
    a=observer('query-gate-conceptual',parameters=PolicyParameters(reliability_threshold=.95))
    r=a.decide(0,(1,1),3)
    assert r['details']['route']==r['details']['masked_route']
    assert r['details']['low_confidence_cells']==[]
