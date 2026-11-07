"""Scheduling validity, budget fairness and preservation of historical baselines."""
import inspect
import json
from pathlib import Path
import subprocess
import sys
import numpy as np
import pytest
from spatial_memory import scheduling
from spatial_memory.scheduling import AdaptiveObserver, AdaptiveParameters, ObservationController
from spatial_memory.scenarios import generate_scenario
from spatial_memory.evaluation import run_episode
from spatial_memory.observation import Sensor

ROOT = Path(__file__).resolve().parents[1]
CFG = json.loads((ROOT/'configs/development_phase1_2.json').read_text(encoding='utf-8'))
METHODS = CFG['methods']


def test_local_age_not_global_interval_and_unknown_handling():
    a = AdaptiveObserver(np.zeros((1,7),dtype=np.int8),'age',1)
    partial = np.full((1,7),-1,dtype=np.int8)
    partial[0,:2] = 0
    a.refresh(partial,3)
    np.testing.assert_array_equal(a.last_observed,[[3,3,0,0,0,0,0]])
    assert a.score(4,(0,0)) == 0
    assert a.score(4,(6,0)) == 1  # same global time, different cell ages
    unknown = AdaptiveObserver(np.full((1,3),-1),'age',1)
    assert unknown.score(100,(1,0)) == 0
    assert np.all(unknown.last_observed == -1)
    assert np.all(unknown.uncertainty(100) == 1)


def test_age_threshold_boundary_and_fraction():
    a = AdaptiveObserver(np.array([[0,0]]),'age',2)
    assert a.score(3,(0,0)) == 0
    assert a.score(4,(0,0)) == 1
    a.refresh(np.array([[0,-1]]),4)
    assert a.score(4,(0,0)) == 0.5 == a.threshold()


def test_timestamp_visibility_and_invalid_refresh_atomicity():
    a = AdaptiveObserver(np.array([[0,-1]]),'uncertainty',2)
    assert a.last_observed.tolist() == [[0,-1]]
    a.refresh(np.array([[-1,1]]),5)
    assert a.last_observed.tolist() == [[0,5]]
    assert a.memory.grid.tolist() == [[0,1]]
    before = [x.copy() for x in (a.last_observed,a.flips,a.exposure,a.memory.grid)]
    for obs, step in [(np.array([[2,0]]),6),(np.array([[0,1]]),4)]:
        with pytest.raises(ValueError):
            a.refresh(obs,step)
    for old,new in zip(before,(a.last_observed,a.flips,a.exposure,a.memory.grid)):
        np.testing.assert_array_equal(old,new)


def test_uncertainty_evolves_without_sensing_and_does_not_erase_memory():
    a = AdaptiveObserver(np.array([[0,1,-1]]),'uncertainty',3)
    assert 0 < a.uncertainty(0)[0,0] < a.uncertainty(2)[0,0] < a.uncertainty(20)[0,0] <= 1
    assert a.uncertainty(0)[0,0] == pytest.approx(a.uncertainty(0)[0,1])
    assert a.score(4,(0,0)) < a.threshold() <= a.score(5,(0,0))
    np.testing.assert_array_equal(a.memory.grid,[[0,1,-1]])
    assert a.latest_step == 0


def test_same_age_distinct_histories_yield_distinct_uncertainty_decisions():
    stable = AdaptiveObserver(np.array([[0]]),'uncertainty',1)
    flipping = AdaptiveObserver(np.array([[0]]),'uncertainty',1)
    for step in (2,4):
        stable.refresh(np.array([[0]]),step)
        flipping.refresh(np.array([[1 if step==2 else 0]]),step)
    np.testing.assert_array_equal(stable.last_observed,flipping.last_observed)
    np.testing.assert_array_equal(stable.memory.grid,flipping.memory.grid)
    assert stable.score(6,(0,0)) < stable.threshold()
    assert flipping.score(6,(0,0)) >= flipping.threshold()
    assert flipping.flips[0,0] == 2
    assert flipping.exposure[0,0] == stable.exposure[0,0] == 4
    assert stable.rates()[0,0] < flipping.rates()[0,0]


@pytest.mark.parametrize('method',METHODS)
@pytest.mark.parametrize('cap',[1,3,None])
def test_budget_enforced_with_actual_sensor_call_count(monkeypatch,method,cap):
    calls = []
    original = Sensor.observe
    def counted(self,occupancy,position,rng):
        calls.append(position)
        return original(self,occupancy,position,rng)
    monkeypatch.setattr(Sensor,'observe',counted)
    scenario = generate_scenario(CFG['scenarios'][-1],7)
    metrics, frames = run_episode(scenario,{**CFG,'max_observations':cap},method,7)
    assert len(calls) == metrics['observation_count']
    assert cap is None or metrics['observation_count'] <= cap
    assert metrics['observation_count'] == 1 + sum(f['observation_granted'] for f in frames[1:])
    assert metrics['observation_requests_denied'] == sum(
        f['observation_requested'] and not f['observation_granted'] for f in frames[1:])
    assert metrics['observation_cost'] == len(calls)*CFG['observation_cost']
    if method == 'static':
        assert len(calls) == 1
    elif cap == 1:
        assert len(calls) == 1 and metrics['observation_requests_denied'] > 0


def test_denied_request_leaves_model_untouched_but_uncertainty_grows():
    c = ObservationController(np.array([[0]]),'uncertainty',max_observations=1)
    before = c.agent.last_observed.copy()
    score5 = c.decide(5,(0,0))
    score8 = c.decide(8,(0,0))
    assert score5['observation_requested'] and not score5['observation_granted']
    assert score8['observation_score'] > score5['observation_score']
    assert c.used == 1 and c.denied == 2
    np.testing.assert_array_equal(c.agent.last_observed,before)
    with pytest.raises(ValueError,match='exhausted'):
        c.refresh(np.array([[0]]),8)


@pytest.mark.parametrize('cap',[0,-1,1.5,True])
def test_invalid_budget(cap):
    with pytest.raises(ValueError):
        ObservationController(np.array([[0]]),'age',max_observations=cap)


@pytest.mark.parametrize('parameters',[dict(age_steps=0),dict(stale_fraction=0),
    dict(entropy_threshold=2),dict(prior_exposure=0),dict(confidence=1),dict(min_rate=0),
    dict(max_rate=float('nan'))])
def test_invalid_parameters(parameters):
    with pytest.raises(ValueError):
        AdaptiveParameters(**parameters)


@pytest.mark.parametrize('method',METHODS)
def test_paired_truth_initial_observation_and_reproducibility(method):
    scenario = generate_scenario(CFG['scenarios'][3],19)
    cfg = {**CFG,'max_observations':5}
    m,f = run_episode(scenario,cfg,method,19)
    repeated,rf = run_episode(scenario,cfg,method,19)
    assert m == repeated
    _, reference = run_episode(scenario,cfg,'periodic',19)
    np.testing.assert_array_equal(f[0]['memory'],reference[0]['memory'])
    for a,b in zip(f,reference):
        np.testing.assert_array_equal(a['geometry'],b['geometry'])
        np.testing.assert_array_equal(a['people'],b['people'])
    for a,b in zip(f,rf):
        assert a['position'] == b['position']
        assert a['observation_score'] == b['observation_score']
        np.testing.assert_array_equal(a['memory'],b['memory'])


def test_schedulers_cannot_receive_hidden_world_or_task_inputs():
    assert set(inspect.signature(AdaptiveObserver.score).parameters) == {'self','step','position'}
    assert set(inspect.signature(AdaptiveObserver.refresh).parameters) == {'self','observation','step'}
    assert set(inspect.signature(ObservationController).parameters) == {
        'initial','method','interval','radius','parameters','max_observations'}
    assert 'simulation' not in inspect.getsource(scheduling)
    assert 'navigation' not in inspect.getsource(scheduling)
    # Different hidden states outside range produce identical histories/decisions.
    a = np.zeros((3,10),bool)
    b = a.copy(); b[1,9] = True
    sensor = Sensor(radius=1)
    for method in ('age','uncertainty'):
        models = [AdaptiveObserver(sensor.observe(g,(0,1),np.random.default_rng(0)),method,1)
                  for g in (a,b)]
        for step in range(1,10):
            assert models[0].score(step,(0,1)) == models[1].score(step,(0,1))


def test_historical_unconstrained_baseline_results_preserved():
    for directory, config_name in [('development','development_phase1_1.json'),
                                   ('diagnostic','development.json')]:
        old = json.loads((ROOT/f'results/phase1_1/{directory}/results.json').read_text(encoding='utf-8'))
        cfg = json.loads((ROOT/'configs'/config_name).read_text(encoding='utf-8'))
        for expected in old['episodes']:
            template = next(t for t in cfg['scenarios'] if t['name']==expected['scenario'])
            scenario = generate_scenario(template,expected['seed'])
            metrics,_ = run_episode(scenario,{**cfg,'max_steps':expected['max_steps']},
                                    expected['method'],expected['seed'])
            for key,value in expected.items():
                if key == 'scenario_sha256':
                    continue
                actual = list(metrics[key]) if key=='final_position' else metrics[key]
                assert actual == value, (directory,key,actual,value)


def test_runner_guards_and_summary_success_only(tmp_path):
    sys.path.insert(0,str(ROOT/'scripts'))
    from run_adaptive_experiment import summarize, validate_config
    with pytest.raises(ValueError,match='reserved'):
        validate_config({**CFG,'split':'held_out'})  # synthetic only
    runner = [sys.executable,str(ROOT/'scripts/run_adaptive_experiment.py')]
    completed = subprocess.run(runner+['--output',str(ROOT/'results/phase1_1')],
                               capture_output=True,text=True)
    assert completed.returncode != 0 and 'protected' in completed.stderr
    s = generate_scenario(CFG['scenarios'][2],7)
    m,_ = run_episode(s,CFG,'static',7)
    summary = summarize([m],('method',))[0]
    assert not m['success']
    assert summary['successful_observation_count_mean'] is None
    assert summary['failure_reasons'] == {'deadline_repeated_blocked_attempts':1}

def test_confidence_rate_bounds_and_stable_evidence_reduces_rate():
    params = AdaptiveParameters(prior_flips=0.3,prior_exposure=6,min_rate=0.01,max_rate=0.35)
    a = AdaptiveObserver(np.array([[0]]),'uncertainty',1,params)
    a.refresh(np.array([[0]]),100)
    assert a.rates()[0,0] == params.min_rate
    assert a.uncertainty(100)[0,0] < a.uncertainty(99+100)[0,0]
    a.flips[0,0] = 1000  # explicit upper-bound stress of the configured estimator
    assert a.rates()[0,0] == params.max_rate


def test_occluded_cells_stay_old_despite_granted_age_refreshes():
    a = AdaptiveObserver(np.array([[0,0]]),'age',2)
    a.refresh(np.array([[0,-1]]),4)
    assert a.score(5,(0,0)) >= a.threshold()
    a.refresh(np.array([[0,-1]]),5)
    assert a.score(6,(0,0)) >= a.threshold()
    assert a.last_observed[0,1] == 0


def test_trace_records_pre_move_sensing_pose():
    s = generate_scenario(CFG['scenarios'][0],7)
    _,f = run_episode(s,CFG,'age',7)
    assert f[4]['observation_granted']
    assert f[4]['observation_position'] == f[3]['position'] == (4,3)
    assert f[4]['position'] == (5,3)


def test_successful_only_summary_uses_matching_successes():
    sys.path.insert(0,str(ROOT/'scripts'))
    from run_adaptive_experiment import summarize
    s = generate_scenario(CFG['scenarios'][2],7)
    failure,_ = run_episode(s,CFG,'static',7)
    success,_ = run_episode(s,CFG,'periodic',7)
    summary = summarize([failure,success],('scenario',))[0]
    assert summary['success_rate'] == 0.5
    assert summary['successful_observation_count_mean'] == success['observation_count']
    assert summary['observation_count_mean'] == (success['observation_count']+failure['observation_count'])/2


def test_json_report_roundtrip_preserves_all_records(tmp_path):
    sys.path.insert(0,str(ROOT/'scripts'))
    from run_adaptive_experiment import write_json_report
    payload = dict(config=CFG,episodes=[dict(success=True,score=0.75)],
                   traces=[dict(frames=[dict(step=0,granted=True),dict(step=1,granted=False)])],
                   empty=[],provenance=dict(commit_sha='test',dirty=True))
    path = tmp_path/'results.json'
    write_json_report(path,payload)
    assert json.loads(path.read_text(encoding='utf-8')) == payload
