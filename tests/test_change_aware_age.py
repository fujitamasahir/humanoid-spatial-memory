"""History semantics/reference checks; no FIT or hidden-state inputs."""
from copy import deepcopy
from dataclasses import replace
import ast
from pathlib import Path
import numpy as np
import pytest
from spatial_memory.change_aware_age import (CellHistory,ChangeAwareAgeController,
    HistoryParameters,UNKNOWN,CHANGING,INTERMEDIATE,STABLE)
from spatial_memory.scheduling import ObservationController,AdaptiveParameters


def one(value):return np.array([[value]],dtype=np.int8)


def test_constant_free_and_occupied_require_actual_span_and_repeats():
    for value in (0,1):
        h=CellHistory(one(value))
        for t in (1,2,3):h.observe(one(value),t)
        assert h.unchanged[0,0]==3 and h.classify(3)[0,0]==INTERMEDIATE
        h.observe(one(value),7);h.observe(one(value),12)
        assert h.classify(12)[0,0]==STABLE
        assert h.deadlines(12,'caa_full')[0][0,0]==6
        assert h.memory.grid[0,0]==value


def test_alternating_and_recent_change_override_stable():
    h=CellHistory(one(0))
    for t in (4,8,12):h.observe(one(0),t)
    assert h.classify(12)[0,0]==STABLE
    h.observe(one(1),16)
    assert h.classify(16)[0,0]==CHANGING
    assert h.unchanged[0,0]==0 and h.run_start[0,0]==16
    assert h.deadlines(16,'caa_full')[0][0,0]==4
    for t,v in ((20,0),(24,1),(28,0)):h.observe(one(v),t)
    assert h.transitions[0,0]==4 and h.repeated[0,0]==7
    assert h.last_transition[0,0]==28


def test_changing_to_stable_requires_new_observed_run():
    h=CellHistory(one(0));h.observe(one(1),4)
    for t in (8,12):h.observe(one(1),t)
    assert h.classify(14)[0,0]==CHANGING # inclusive detection-age10
    assert h.classify(15)[0,0]==INTERMEDIATE
    h.observe(one(1),16)
    assert h.classify(16)[0,0]==STABLE


def test_unknown_cells_and_empty_observations_never_add_stability():
    h=CellHistory(np.array([[0,-1]],dtype=np.int8))
    before=[a.copy() for a in (h.last_observed,h.repeated,h.transitions,h.last_transition,h.unchanged,h.run_start,h.memory.grid)]
    for t in (4,8,12):h.observe(np.array([[-1,-1]],dtype=np.int8),t)
    for a,b in zip(before,(h.last_observed,h.repeated,h.transitions,h.last_transition,h.unchanged,h.run_start,h.memory.grid)):np.testing.assert_array_equal(a,b)
    assert h.classify(12).tolist()==[[INTERMEDIATE,UNKNOWN]]
    assert h.score(12,(1,0),0,'caa_full')[0]==0


def test_unobserved_time_and_long_gap_are_not_stability_evidence():
    h=CellHistory(one(0))
    for t in (4,8,12):h.observe(one(0),t)
    assert h.classify(18)[0,0]==STABLE
    before=h.memory.grid.copy()
    assert h.classify(19)[0,0]==INTERMEDIATE
    h.observe(one(0),30)
    assert h.run_start[0,0]==30 and h.unchanged[0,0]==0
    assert h.classify(30)[0,0]==INTERMEDIATE
    np.testing.assert_array_equal(before,h.memory.grid)


def test_invalid_observation_and_timestamp_are_atomic():
    h=CellHistory(one(0))
    for observation,time in [(one(2),1),(one(1),0),(one(1),-1),(one(1),1.5),(np.zeros((2,2)),1)]:
        with pytest.raises(ValueError):h.observe(observation,time)
        assert h.latest_scan==0 and h.repeated[0,0]==0 and h.memory.grid[0,0]==0
    with pytest.raises(ValueError):h.classify(-1)
    with pytest.raises(ValueError):HistoryParameters(recent_steps=0)


@pytest.mark.parametrize('mode,changing,stable',[('caa_fast',4,5),('caa_slow',5,6),('caa_full',4,6)])
def test_ablation_deadlines(mode,changing,stable):
    h=CellHistory(np.zeros((1,3),dtype=np.int8))
    for t in (4,8,12):h.observe(np.array([[0,0,-1]],dtype=np.int8),t)
    h.observe(np.array([[1,-1,-1]],dtype=np.int8),13)
    assert h.deadlines(13,mode)[0].tolist()==[[changing,stable,5]]


def test_uniform5_exact_original_age_equivalence_random_authorized_histories():
    rng=np.random.default_rng(2026111404)
    initial=rng.choice([-1,0,1],size=(8,9)).astype(np.int8)
    a=ObservationController(initial,'age',parameters=replace(AdaptiveParameters(),age_steps=5),max_observations=20)
    b=ChangeAwareAgeController(initial,mode='age5',max_observations=20)
    for t in range(1,161):
        pos=(int(rng.integers(9)),int(rng.integers(8)))
        da,db=a.decide(t,pos),b.decide(t,pos)
        assert da==db
        if da['observation_granted']:
            observed=rng.choice([-1,0,1],size=(8,9)).astype(np.int8)
            a.refresh(observed,t);b.refresh(observed,t)
        np.testing.assert_array_equal(a.memory.grid,b.memory.grid)
        assert a.used==b.used<=20


def test_authorization_budget_and_empty_paid_scan():
    a=ChangeAwareAgeController(one(0),max_observations=2)
    with pytest.raises(RuntimeError):a.refresh(one(1),1)
    assert a.history.transitions[0,0]==0
    assert a.decide(5,(0,0))['observation_granted']
    with pytest.raises(RuntimeError):a.decide(6,(0,0))
    a.refresh(one(-1),5)
    assert a.used==2 and a.history.latest_scan==5 and a.history.last_observed[0,0]==0
    assert not a.decide(6,(0,0))['observation_granted']
    with pytest.raises(RuntimeError):a.refresh(one(1),6)
    with pytest.raises(ValueError):a.decide(4,(0,0))


def test_independent_scalar_history_reference_seeded_sequences():
    rng=np.random.default_rng(2026111405)
    h=CellHistory(one(-1));last=-1;state=-1;repeated=0;changes=0;change=-1;run=-1;unchanged=0;t=0
    for _ in range(300):
        t+=int(rng.integers(1,10));value=int(rng.choice([-1,0,1]))
        if value>=0:
            if last<0:run=t;unchanged=0
            else:
                repeated+=1
                if value!=state:changes+=1;change=t;run=t;unchanged=0
                elif t-last>6:run=t;unchanged=0
                else:unchanged+=1
            state=value;last=t
        h.observe(one(value),t)
        assert (h.last_observed[0,0],h.memory.grid[0,0],h.repeated[0,0],h.transitions[0,0],h.last_transition[0,0],h.run_start[0,0],h.unchanged[0,0])==(last,state,repeated,changes,change,run,unchanged)
        for clock in (t,t+6,t+11):
            expected=UNKNOWN if last<0 else CHANGING if change>=0 and clock-change<=10 else STABLE if unchanged>=3 and last-run>=12 and clock-last<=6 else INTERMEDIATE
            assert h.classify(clock)[0,0]==expected


def test_cropped_local_score_matches_full_original_known_mask():
    rng=np.random.default_rng(2026111406);h=CellHistory(rng.choice([-1,0,1],size=(7,8)).astype(np.int8))
    for t in (3,7,12,18):h.observe(rng.choice([-1,0,1],size=(7,8)).astype(np.int8),t)
    for pos in ((0,0),(7,6),(3,3)):
      for radius in (0,1.5,3,20):
       for mode in ('caa_fast','caa_slow','caa_full','age5'):
        tau,_=h.deadlines(20,mode);yy,xx=np.indices(h.memory.grid.shape)
        known=((xx-pos[0])**2+(yy-pos[1])**2<=radius**2)&(h.last_observed>=0)
        expected=float(np.mean(20-h.last_observed[known]>=tau[known])) if known.any() else 0.
        assert h.score(20,pos,radius,mode)[0]==expected


def test_algorithm_has_no_planning_truth_or_sensor_dependency():
    text=(Path(__file__).parents[1]/'src/spatial_memory/change_aware_age.py').read_text();tree=ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node,ast.ImportFrom):assert node.module in ('__future__','dataclasses','memory','scheduling')
        if isinstance(node,ast.Attribute):assert node.attr not in ('occupancy','geometry','people','plan','observe_current','scan','check_move','check_turn')


def test_changing_priority_if_stability_and_change_window_overlap():
    h=CellHistory(one(0),HistoryParameters(recent_steps=100))
    h.observe(one(1),4)
    for t in (8,12,16):h.observe(one(1),t)
    assert h.unchanged[0,0]>=3 and h.last_observed[0,0]-h.run_start[0,0]>=12
    assert h.classify(16)[0,0]==CHANGING


def test_deterministic_public_stream_replay():
    def replay():
        a=ChangeAwareAgeController(one(0),mode='caa_full',max_observations=5)
        for t in range(1,45):
            d=a.decide(t,(0,0))
            if d['observation_granted']:a.refresh(one((t//10)%2),t)
        return a.decisions,a.memory.grid.tolist(),a.used
    assert replay()==replay()
