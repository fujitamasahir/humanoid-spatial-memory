import ast,inspect,math
import numpy as np
import pytest
from spatial_memory.route_adaptive_age_v1 import RouteAdaptiveAgeV1,mechanism_rule,swept_prefix,MODES
from spatial_memory.cadence_age import CadenceController
from spatial_memory.scheduling import AdaptiveParameters
SENSOR={'range_m':6.,'cell_size':.75,'horizontal_fov_deg':120.,'ray_count':61}


def set_context(c,yaw=0.):c.set_navigation_context(goal=(12,7),yaw=yaw,unknown='optimistic')


def test_exact_original_age5_disabled_random_authorized_history_and_cap():
    rng=np.random.default_rng(2026111601)
    for cap in (1,2,20):
        initial=rng.choice([-1,0,1],(15,15)).astype(np.int8);a=RouteAdaptiveAgeV1(initial,mode='raa_off',max_observations=cap)
        b=CadenceController(initial,'age',cadence_mode='age5',persistence=False,evi=True,sensor=SENSOR,
            radius=3,interval=4,parameters=AdaptiveParameters(),max_observations=cap)
        for t in range(1,81):
            position=(int(rng.integers(1,14)),int(rng.integers(1,14)));yaw=float(rng.integers(4)*math.pi/2)
            set_context(a,yaw);set_context(b,yaw);x=a.decide(t,position);y=b.decide(t,position)
            assert x==y
            if x['observation_granted']:
                reading=rng.choice([-1,0,1],(15,15)).astype(np.int8);a.refresh(reading,t);b.refresh(reading,t)
            assert a.used==b.used and a.requests==b.requests and a.denied==b.denied
            assert np.array_equal(a.memory.grid,b.memory.grid) and np.array_equal(a.last_observed,b.base.agent.last_observed)


def feature(**kw):
    return {'route_available':True,'age4_request':True,'age5_request':False,
      'observable_near_route_uncertainty':True,'prefix_free_fresh5':True,
      'predicted_view_known_fresh5':True,'prefix_recent_change':False,**kw}


def test_early_request_requires_all_prospective_guards():
    f=feature();assert mechanism_rule(f,used=2,gap=4,enable_advance=True,enable_defer=False)==(True,False)
    for change in ({'route_available':False},{'age4_request':False},{'age5_request':True},{'observable_near_route_uncertainty':False}):
        assert not mechanism_rule(feature(**change),used=2,gap=4,enable_advance=True,enable_defer=False)[0]
    for used,gap in ((1,4),(2,3)):
        assert not mechanism_rule(f,used=used,gap=gap,enable_advance=True,enable_defer=False)[0]


@pytest.mark.parametrize('mode',('raa_advance','raa_defer','raa_joint'))
def test_first_noninitial_is_exact_age5_and_cap_is_initial_inclusive(mode):
    g=np.zeros((15,15),np.int8);c=RouteAdaptiveAgeV1(g,mode=mode,max_observations=2);grants=[]
    for t in range(1,30):
        set_context(c);ans=c.decide(t,(7,7))
        if ans['observation_granted']:grants.append(t);c.refresh(g,t)
    assert grants==[5] and c.used==2
    assert all(not d['deferred'] for d in c.decisions)
    with pytest.raises(RuntimeError):c.refresh(g,30)


def test_one_step_deferral_forces_next_even_if_parent_or_route_changes():
    g=np.zeros((15,15),np.int8);c=RouteAdaptiveAgeV1(g,mode='raa_defer')
    set_context(c);assert c.decide(5,(7,7))['observation_granted'];c.refresh(g,5)
    # Controlled public-feature certificate isolates the state-machine guarantee.
    c.features=lambda *args:feature(age5_request=True)
    set_context(c);assert not c.decide(10,(7,7))['observation_granted']
    assert c.forced_step==11 and c.decisions[-1]['deferred']
    # New local pose with no known cells can make A5 false; promise still holds.
    c.last_observed[:]=-1;c.memory.grid[:]=-1
    set_context(c);ans=c.decide(11,(1,1));assert ans['observation_granted']
    assert c.decisions[-1]['forced_next'] and not c.decisions[-1]['deferred']
    c.refresh(np.full(g.shape,-1),11);assert c.last_scan_step==11


def test_cannot_skip_forced_decision_and_no_unauthorized_update():
    g=np.zeros((15,15),np.int8);c=RouteAdaptiveAgeV1(g,mode='raa_defer')
    with pytest.raises(RuntimeError):c.refresh(g,1)
    set_context(c);c.decide(5,(7,7));c.refresh(g,5)
    c.features=lambda *args:feature(age5_request=True);set_context(c);c.decide(10,(7,7))
    set_context(c)
    with pytest.raises(RuntimeError):c.decide(12,(7,7))
    set_context(c);assert c.decide(11,(7,7))['observation_granted']
    before=c.memory.grid.copy()
    with pytest.raises(ValueError):c.refresh(np.full(g.shape,9),11)
    assert np.array_equal(c.memory.grid,before)
    c.refresh(np.full(g.shape,-1),11)
    assert np.array_equal(c.memory.grid,before) and c.used==3


def test_defer_protection_and_age6_bound():
    f=feature(age5_request=True)
    assert mechanism_rule(f,used=2,gap=5,enable_advance=False,enable_defer=True)==(False,True)
    for change in ({'route_available':False},{'prefix_free_fresh5':False},{'predicted_view_known_fresh5':False},{'prefix_recent_change':True}):
        assert not mechanism_rule(feature(age5_request=True,**change),used=2,gap=5,enable_advance=False,enable_defer=True)[1]
    assert not mechanism_rule(f,used=2,gap=6,enable_advance=False,enable_defer=True)[1]


def test_public_features_unknown_change_and_swept_rotation_bounded():
    g=np.zeros((15,15),np.int8);g[:,9:]=-1;c=RouteAdaptiveAgeV1(g)
    scores=c.age_scores(4,(7,7));f=c.features(4,(7,7),0.,(12,7),'optimistic',scores)
    assert f['observable_near_route_uncertainty'] and not f['prefix_free_fresh5']
    assert f['point_plan_calls']==f['predicted_footprints']==1 and f['actual_sensor_calls']==0
    assert f['sweep_cell_visits']<=200
    cells,visits=swept_prefix([(7,7),(8,7),(8,8)],0.,5,g.shape)
    assert (9,7) in cells and visits<=40


def test_determinism_and_unknown_does_not_change_transition_history():
    logs=[]
    for _ in range(2):
        g=np.zeros((15,15),np.int8);c=RouteAdaptiveAgeV1(g)
        for t in range(1,26):
            set_context(c);d=c.decide(t,(7,7))
            if d['observation_granted']:c.refresh(np.full(g.shape,-1),t)
        logs.append(c.decisions)
        assert (c.changed==-1).all() and not c.reobserved.any()
    assert logs[0]==logs[1]


def test_no_world_emergency_sensor_shield_or_true_state_dependency():
    import spatial_memory.route_adaptive_age_v1 as m
    tree=ast.parse(inspect.getsource(m));allowed={'dataclasses','time','memory','navigation','evi'}
    assert all((n.module or '') in allowed for n in ast.walk(tree) if isinstance(n,ast.ImportFrom))
    assert not any(isinstance(n,ast.Attribute) and n.attr in ('observe','scan','occupancy','geometry','people','check_move','check_turn') for n in ast.walk(tree))
