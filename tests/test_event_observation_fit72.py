"""Synthetic evaluator-hook and paired-summary tests for candidate A."""
from pathlib import Path
import sys
import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"src"),str(ROOT/"scripts")]

import evaluate_event_observation_fit72 as screen


def pair(world, *, prev, next_, obs0, obs1, steps0, steps1,
         dist0, dist1):
    return {
        "world_identity":world,"schedule":0,"seed":42,
        "reference_method":"periodic",
        "candidate_method":"event_periodic",
        "reference_success":prev,"candidate_success":next_,
        "reference_observations":obs0,"candidate_observations":obs1,
        "reference_memory_rays":obs0*61,"candidate_memory_rays":obs1*61,
        "reference_steps_h80":steps0,"candidate_steps_h80":steps1,
        "reference_distance_m":dist0,"candidate_distance_m":dist1,
        "reference_emergency_scans":steps0,
        "candidate_emergency_scans":steps1,
        "reference_emergency_rays":steps0*61,
        "candidate_emergency_rays":steps1*61,
        "candidate_scheduler_total_ms":.14,
        "reference_unwanted_contacts":0,
        "candidate_unwanted_contacts":0,
        "candidate_triggered_scans":1,
        "candidate_blocked_feedback_count":2,
        "candidate_no_route_feedback_count":0,
        "reference_episode_wall_seconds":.5,
        "candidate_episode_wall_seconds":.5,
    }


def test_pair_aggregates_distinguish_censored_and_common_success():
    rows=[
        pair("A",prev=True,next_=True,obs0=11,obs1=9,
             steps0=42,steps1=36,dist0=22,dist1=20),
        pair("B",prev=False,next_=True,obs0=17,obs1=12,
             steps0=80,steps1=52,dist0=40,dist1=26),
        pair("C",prev=True,next_=False,obs0=10,obs1=7,
             steps0=30,steps1=80,dist0=18,dist1=40),
    ]
    s=screen.aggregate_pairs(rows)
    assert s["baseline_successes"]==2
    assert s["candidate_successes"]==2
    assert s["rescued_failures"]==1 and s["harmed_successes"]==1
    assert s["paired_common_success"]["episodes"]==1
    assert s["paired_common_success"]["total_delta_steps"]==-6
    assert s["total_delta_observations"]==-10
    assert s["independent_maze_layouts"]==3


def test_run_candidate_restores_global_evaluator_after_failure(monkeypatch):
    original=screen.base.run_episode
    def broken(*args,**kwargs):
        raise RuntimeError("synthetic MuJoCo error")
    monkeypatch.setattr(screen.base,"run_case",
                        lambda *args,**kwargs: screen.base.run_episode(
                            None,{},args[2],
                            _action_checker=lambda *a: (False,None,0.,None),
                            _g1_planner=lambda *a: []))
    monkeypatch.setattr(screen.base,"run_episode",broken)
    with pytest.raises(RuntimeError,match="synthetic MuJoCo error"):
        screen.run_candidate({},0,"periodic",{})
    assert screen.base.run_episode is broken


def test_candidate_injection_receives_only_past_selected_action_feedback(monkeypatch):
    def original_episode(scenario,config,method,**kwargs):
        arr=np.zeros((8,8),dtype=np.int8)
        agent=kwargs["_controller_factory"](
            arr,method,interval=6,radius=3,
            parameters=None,max_observations=20)
        assert agent.used==1
        d1=agent.decide(1,(2,2))
        assert not d1["observation_granted"]
        class World:
            step=1
        checker=kwargs["_action_checker"]
        result=checker(World(),(2,2),("move",(3,2)),0.)
        assert result[0]
        d2=agent.decide(2,(2,2))
        assert d2["observation_granted"]
        agent.refresh(arr,2)
        return {"event_observation_test":True}, {"steps":[]}

    def runner(payload,schedule,method,config,**kwargs):
        return screen.base.run_episode(
            None,{},method,
            _action_checker=lambda *a:(True,None,None,"translation_collision"),
            _g1_planner=lambda *a:[("move",(3,2))])
    monkeypatch.setattr(screen.base,"run_episode",original_episode)
    monkeypatch.setattr(screen.base,"run_case",runner)
    row,trace=screen.run_candidate({},0,"periodic",{})
    assert row["event_observation_count"]==1
    assert row["feedback_blocked_count"]==1
    assert row["event_observation_log"][0]["step"]==2
    assert row["event_policy"]=="event_periodic"
    assert trace["steps"]==[]
    assert screen.base.run_episode is original_episode


def test_g1_no_route_callback_is_next_step_feedback(monkeypatch):
    def original_episode(scenario,config,method,**kwargs):
        arr=np.zeros((8,8),dtype=np.int8)
        agent=kwargs["_controller_factory"](
            arr,method,interval=6,radius=3,
            parameters=None,max_observations=20)
        assert not agent.decide(1,(2,2))["observation_granted"]
        assert kwargs["_g1_planner"](
            arr,(2,2),(7,7),"optimistic",0.,frozenset())==[]
        assert not agent.decide(1,(2,2))["observation_granted"]
        assert agent.decide(2,(2,2))["observation_granted"]
        agent.refresh(arr,2)
        return {}, {"steps":[]}

    monkeypatch.setattr(screen.base,"run_episode",original_episode)
    monkeypatch.setattr(screen.base,"run_case",
                        lambda *a,**k: screen.base.run_episode(
                          None,{},a[2],
                          _action_checker=lambda *z:(False,None,0.,None),
                          _g1_planner=lambda *z:[]))
    row,_=screen.run_candidate({},0,"age",{})
    assert row["feedback_no_route_count"]==1
    assert row["event_observation_count"]==1



def test_frozen_evidence_paths_and_correct_h80_reference_matrix():
    """Regression: provenance is PREDECESSOR, comparator is safety H80.

    Prior bug tried to read nonexistent H80/provenance.json; a second
    bug compared the candidates with pre-safety predecessor episodes.
    """
    assert screen.base.BASELINE != screen.BASE
    assert screen.base.BASELINE / "provenance.json" in screen.PROTECTED
    assert screen.BASE / "provenance.json" not in screen.PROTECTED
    assert all(path.is_file() for path in screen.PROTECTED)
    h80 = screen._load_csv(screen.BASE / "episodes.csv")
    predecessor, _, provenance, _ = screen.base.load_baseline()
    config = screen.base.frozen_config(provenance)
    assert len(h80) == len(predecessor) == 288
    assert config["max_steps"] == 80
    assert config["mujoco_ray_sensor"]["ray_count"] == 61
    assert {row["method"] for row in h80} == {
        "periodic", "age", "static", "uncertainty"}
    assert sum(row["success"] == "True" and row["method"] == "periodic"
               for row in h80) == 66
    assert sum(row["success"] == "True" and row["method"] == "age"
               for row in h80) == 66



def test_noninitial_scan_accounting_excludes_step_zero():
    """The real first frame already includes the initial memory scan.

    Event controller does not call refresh() for the initial scan, so
    compare only subsequent authorized observation steps to its log.
    """
    trace = {"steps": [
        {"step": 0, "observation_granted": True},
        {"step": 1, "observation_granted": False},
        {"step": 2, "observation_granted": True},
        {"step": 3, "observation_granted": False},
        {"step": 4, "observation_granted": True},
    ]}
    assert screen._noninitial_granted_scan_steps(trace) == [2, 4]
    assert 1 + len(screen._noninitial_granted_scan_steps(trace)) == 3


def test_only_initial_memory_observation_has_empty_event_log():
    trace = {"steps": [
        {"step": 0, "observation_granted": True},
        {"step": 1, "observation_granted": False},
        {"step": 2, "observation_granted": False},
    ]}
    assert screen._noninitial_granted_scan_steps(trace) == []


@pytest.mark.parametrize("trace", [
    {"steps": []},
    {"steps": [{"step": 0, "observation_granted": False}]},
    {"steps": [{"step": 1, "observation_granted": True}]},
])
def test_scan_accounting_rejects_malformed_missing_initial_frame(trace):
    with pytest.raises(RuntimeError, match="Step 0 initial"):
        screen._noninitial_granted_scan_steps(trace)
