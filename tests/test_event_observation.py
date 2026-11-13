"""Unit contracts for Periodic+Event and Age+Event; no MuJoCo required."""
import sys
from pathlib import Path
import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"src"),str(ROOT/"scripts")]

from spatial_memory.event_observation import (
    EventObservationParameters, EventTriggeredObservationController as Event,
)
from spatial_memory.scheduling import ObservationController, AdaptiveParameters


def initial():
    arr=np.zeros((7,7),dtype=np.int8)
    arr[2,4]=-1
    return arr


def run(observer,steps=14):
    requested=[]
    for t in range(1,steps+1):
        decision=observer.decide(t,(3,3))
        if decision["observation_granted"]:
            requested.append(t)
            observer.refresh(initial(),t)
    return requested


def test_periodic_without_events_exactly_matches_legacy_periodic():
    o=Event(initial(),"periodic",interval=4,max_observations=20)
    b=ObservationController(initial(),"periodic",interval=4,max_observations=20)
    observed_events=run(o)
    observed_baseline=run(b)
    assert observed_events==observed_baseline==[4,8,12]


def test_age_without_events_exactly_matches_legacy_age():
    o=Event(initial(),"age",radius=3,
            parameters=AdaptiveParameters(),max_observations=20)
    b=ObservationController(initial(),"age",radius=3,
            parameters=AdaptiveParameters(),max_observations=20)
    assert run(o)==run(b)


def test_rejected_selected_action_triggers_next_eligible_scan():
    o=Event(initial(),"periodic",interval=5,max_observations=20)
    o.note_selected_action_rejected(1)
    assert not o.decide(1,(3,3))["observation_granted"]
    due=o.decide(2,(3,3))
    assert due["event_reason"]=="event"
    assert due["observation_granted"]
    o.refresh(initial(),2)
    assert o.event_observation_count==1
    # Event scan RESETs periodic clock: step5 is no longer due.
    assert not o.decide(5,(3,3))["observation_granted"]
    assert o.decide(7,(3,3))["observation_granted"]


def test_public_no_route_feedback_triggers_without_sensor_or_truth():
    o=Event(initial(),"age",radius=3,max_observations=20)
    o.note_no_route(1)
    assert not o.decide(1,(3,3))["observation_granted"]
    assert o.decide(2,(3,3))["observation_granted"]
    o.refresh(initial(),2)
    assert o.event_observation_count==1


def test_recent_observation_suppresses_repeated_emergency_like_event():
    o=Event(initial(),"periodic",interval=10,max_observations=20)
    o.note_no_route(1)
    assert o.decide(2,(3,3))["observation_granted"]
    o.refresh(initial(),2)
    o.note_no_route(2)
    assert not o.decide(3,(3,3))["observation_granted"]
    assert o.decide(5,(3,3))["observation_granted"]


def test_budget_denial_never_calls_memory_update():
    o=Event(initial(),"periodic",interval=2,max_observations=1)
    before=o.memory.grid.copy()
    decision=o.decide(2,(3,3))
    assert decision["observation_requested"]
    assert not decision["observation_granted"]
    assert o.used==1
    assert np.array_equal(o.memory.grid,before)


def test_only_authorized_refresh_and_memory_changes():
    o=Event(initial(),"periodic",interval=4,max_observations=20)
    with pytest.raises(RuntimeError,match="Unauthorized"):
        o.refresh(initial(),1)
    assert o.decide(4,(3,3))["observation_granted"]
    updated=initial()
    updated[2,4]=1
    o.refresh(updated,4)
    assert o.memory.grid[2,4]==1
    assert o.observation_log[0]["changed_cells"]==1
    assert o.observation_log[0]["newly_known_cells"]==1


def test_event_not_available_at_initial_step_and_parameters_validated():
    o=Event(initial(),"periodic",interval=4)
    assert not o.decide(0,(3,3))["observation_granted"]
    with pytest.raises(ValueError):
        EventObservationParameters(min_steps_since_any_observation=0)
    with pytest.raises(ValueError):
        Event(initial(),"uncertainty")


def test_baseline_due_event_overlap_single_scan():
    o=Event(initial(),"periodic",interval=4,max_observations=20)
    o.note_selected_action_rejected(2)
    d=o.decide(4,(3,3))
    assert d["observation_granted"]
    assert d["event_reason"]=="baseline_and_event"
    o.refresh(initial(),4)
    assert o.used==2
    assert o.event_observation_count==1
