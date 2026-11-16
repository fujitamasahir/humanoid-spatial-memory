"""Cadence decision and authorized scan-clock checks on public fixtures."""
import numpy as np
import pytest
from spatial_memory.cadence_age import ARMS
from spatial_memory.cadence_age_optimized_v1 import cadence_decision,CadenceController
from spatial_memory.scheduling import AdaptiveParameters,AdaptiveObserver
P=AdaptiveParameters(age_steps=4,stale_fraction=.5)
GRID=np.zeros((7,7),dtype=np.int8)
POS=(3,3)

def decision(mode,t,last=None,scan=0,travel=0,turn=False):
    return cadence_decision(GRID,np.zeros(GRID.shape,dtype=int) if last is None else last,
        t,POS,3,P,mode,last_scan_step=scan,travel_since_scan=travel,heading_changed=turn)

def test_periodic_and_older_age_controls():
    assert [t for t in range(1,17) if decision('periodic5',t)['net_value']>0]==[5,10,15]
    assert decision('age5',4)['net_value']<0
    assert decision('age5',5)['net_value']>0
    assert decision('periodic5',5)['age_score'] is None
    assert decision('periodic5',5)['effective_age_score'] is None
    assert decision('age5',5)['age_score'] is None
    assert decision('age5',5)['age_request'] is None

def test_periodic5_skips_grid_allocation(monkeypatch):
    import spatial_memory.cadence_age_optimized_v1 as cadence
    def fail(*args,**kwargs):
        raise AssertionError('Periodic-5 must not create age-score arrays')
    monkeypatch.setattr(cadence.np,'indices',fail)
    out=decision('periodic5',5)
    assert out['net_value']==1 and out['reason']=='fixed_longer_interval'
    assert out['age_score'] is None and out['age_request'] is None

def test_age5_computes_only_the_effective_age_fraction(monkeypatch):
    import spatial_memory.cadence_age_optimized_v1 as cadence
    calls=[]; original=np.mean
    def counted(*args,**kwargs):
        calls.append(1)
        return original(*args,**kwargs)
    monkeypatch.setattr(cadence.np,'mean',counted)
    last=np.zeros(GRID.shape,dtype=np.int64)
    out=decision('age5',5,last=last)
    assert len(calls)==1
    assert out['effective_age_score']==1.0
    assert out['net_value']==1 and out['age_score'] is None

def test_gap_and_motion_preserve_first_age_request():
    assert decision('age_gap4',4)['net_value']>0
    assert decision('age_motion',4)['net_value']>0
    assert decision('age_gap4',5,scan=3)['net_value']<0
    assert decision('age_gap4',7,scan=3)['net_value']>0

def test_motion_and_deadline():
    assert decision('age_motion',7,scan=4,travel=2)['net_value']<0
    assert decision('age_motion',7,scan=4,travel=3)['net_value']>0
    assert decision('age_motion',7,scan=4,turn=True)['net_value']>0
    assert decision('age_motion',6,scan=4,travel=3,turn=True)['net_value']<0
    assert decision('age_motion',9,scan=4)['net_value']>0
    fresh=np.full(GRID.shape,8,dtype=int)
    assert decision('age_motion',9,last=fresh,scan=4)['net_value']<0

def test_randomized_original_age_score_and_subset():
    rng=np.random.default_rng(2026111420)
    history=AdaptiveObserver(GRID,'age',3,P)
    for _ in range(80):
        last=rng.integers(-1,10,size=GRID.shape)
        history.last_observed=last
        history.latest_step=0
        old=history.score(10,POS)
        for mode in ARMS:
            d=decision(mode,10,last=last,scan=7,travel=3)
            if mode in ('periodic5','age5'):
                assert d['age_score'] is None and d['age_request'] is None
            else:
                assert d['age_score']==old
            if mode not in ('periodic5','age5'):
                assert d['net_value']<=0 or d['age_request']

@pytest.mark.parametrize('mode',ARMS)
def test_actual_clock_resets_empty_scan_and_cap(mode):
    c=CadenceController(GRID,'age',cadence_mode=mode,radius=3,parameters=P,
                       max_observations=2,persistence=False)
    c.set_navigation_context(goal=(6,3),yaw=0.,unknown='optimistic')
    t=5 if mode in ('periodic5','age5') else 4
    assert c.decide(t,POS)['observation_granted']
    c.refresh(np.full(GRID.shape,-1,dtype=np.int8),t)
    assert c.last_scan_step==t and c.used==2 and c.travel_since_scan==0
    assert not c.decide(t+5,(4,3))['observation_granted']
    with pytest.raises(RuntimeError):c.refresh(GRID,t+5)
