"""Robustness evaluation contracts; no reserved held-out suite execution."""
from copy import deepcopy
import inspect
import json
from pathlib import Path
import sys
import numpy as np
import pytest
from spatial_memory.robustness import FAMILIES, generate_robustness, truth_audit, episode_config
from spatial_memory.scenarios import scenario_hash
from spatial_memory.simulation import Scenario, World
from spatial_memory.evaluation import run_episode
from spatial_memory.scheduling import ObservationController

ROOT = Path(__file__).resolve().parents[1]
CFG = json.loads((ROOT/'configs/development_phase1_3.json').read_text())
sys.path.insert(0, str(ROOT/'scripts'))
from run_robustness_experiment import protect_output, validate


@pytest.mark.parametrize('family', FAMILIES)
def test_seed_reproducibility_diversity_and_topology(family):
    hashes = []
    for seed in CFG['seeds']:
        a, b = generate_robustness(family, seed), generate_robustness(family, seed)
        assert a == b
        hashes.append(scenario_hash(a))
        records = truth_audit(a, CFG['max_steps'])
        assert records[-1]['reachable']
        assert records[0]['step'] == 0 and records[-1]['step'] == CFG['max_steps']
    assert len(set(hashes)) == len(hashes)


@pytest.mark.parametrize('family', FAMILIES)
def test_paired_truth_and_noise_initial_views(family):
    scenario = generate_robustness(family, 101)
    cfg = episode_config(CFG, {'sensor': {'noise': 0.05}})
    runs = [run_episode(scenario,cfg,m,101) for m in CFG['methods']]
    for _, frames in runs[1:]:
        np.testing.assert_array_equal(frames[0]['memory'], runs[0][1][0]['memory'])
        for f, reference in zip(frames, runs[0][1]):
            np.testing.assert_array_equal(f['geometry'], reference['geometry'])
            np.testing.assert_array_equal(f['people'], reference['people'])
    assert runs[0][0] == run_episode(scenario,cfg,'static',101)[0]


@pytest.mark.parametrize('method', CFG['methods'])
def test_new_metrics_common_horizon_and_caps(method):
    scenario = generate_robustness('budget', 211)
    cfg = episode_config(CFG, {'max_observations': 2})
    metrics, frames = run_episode(scenario, cfg, method, 211)
    assert metrics['observation_count'] <= 2
    assert metrics['budget_exhausted'] == (metrics['observation_count']==2)
    assert metrics['contact_free_success'] == (metrics['success'] and metrics['dynamic_contacts']==0)
    assert metrics['dynamic_contact_rate'] == metrics['dynamic_contacts']/max(1,metrics['elapsed_steps'])
    assert metrics['common_horizon_steps'] == CFG['max_steps']
    assert metrics['observation_requests_denied'] == sum(f['observation_requested'] and not f['observation_granted'] for f in frames[1:])
    # Direct independent truth reconstruction, frozen final map, departed attribution
    # not needed for stale errors. Historical per-frame prefix plus padded tail.
    expected = sum(f['errors']['stale_map_errors'] for f in frames)
    world = World(scenario)
    while world.step < metrics['elapsed_steps']:
        world.advance()
    memory = frames[-1]['memory']
    while world.step < CFG['max_steps']:
        world.advance()
        expected += np.count_nonzero((memory >= 0) & (memory != world.geometry().astype(np.int8)))
    assert metrics['common_horizon_stale_map_errors'] == expected


def test_truth_isolation_and_metrics_do_not_change_agent_behavior():
    assert set(inspect.signature(ObservationController).parameters) == {'initial','method','interval','radius','parameters','max_observations'}
    import spatial_memory.scheduling as scheduling
    assert 'robustness' not in inspect.getsource(scheduling)
    s = generate_robustness('reopen',101)
    for method in CFG['methods']:
        a, af = run_episode(s,CFG,method,101)
        b, bf = run_episode(s,{**CFG,'common_horizon_metrics':False},method,101)
        assert len(af)==len(bf)
        for key in b:
            assert a[key]==b[key]
        assert [(f['position'],f['observation_granted']) for f in af] == [(f['position'],f['observation_granted']) for f in bf]


def test_held_out_and_historical_output_guards(tmp_path):
    with pytest.raises(ValueError,match='reserved'):
        validate({**CFG,'split':'held_out'})
    for p in ('results/phase1_2','results/phase1_2/development','results','results/phase1_1'):
        with pytest.raises(ValueError,match='protected'):
            protect_output((ROOT/p).resolve())
    protect_output(tmp_path.resolve())
    duplicate = deepcopy(CFG); duplicate['seeds'] = [101,101]
    with pytest.raises(ValueError):
        validate(duplicate)


def test_timing_and_dwell_interventions_and_setting_isolation():
    a = generate_robustness('budget', 101)
    b = generate_robustness('budget', 101, timing=3, dwell_shift=4)
    assert a.walls == b.walls and a.start == b.start and a.goal == b.goal
    assert b.changes[0]['step'] == a.changes[0]['step']+3
    assert len(b.pedestrians[0]) > len(a.pedestrians[0])
    before = deepcopy(CFG)
    episode_config(CFG, {'sensor': {'noise': 0.1}, 'adaptive': {'prior_flips': 0.1}})
    assert CFG == before


def test_contact_is_distinct_from_blocked_movement_and_safe_completion():
    s = Scenario.from_dict(dict(name='contact',split='development',width=5,height=3,
        start=[1,1],goal=[3,1],pedestrians=[[[2,1],[1,1]]]))
    cfg = {**CFG,'sensor':dict(radius=4,occlusion=False,noise=0),'max_steps':4}
    m,_ = run_episode(s,cfg,'static',101)
    assert m['dynamic_contacts'] >= 1
    assert not m['contact_free_success']
    assert m['collision_count'] == m['dynamic_contacts']+m['blocked_movement_attempts']


def test_all_phase1_2_historical_episode_metrics_preserved():
    from spatial_memory.scenarios import generate_scenario
    old = json.loads((ROOT/'results/phase1_2/development/results.json').read_text(encoding='utf-8-sig'))
    cfg = old['config']
    for expected in old['episodes']:
        template = next(t for t in cfg['scenarios'] if t['name']==expected['scenario'])
        setting = next(s for s in cfg['settings'] if s['name']==expected['setting'])
        scenario = generate_scenario(template,expected['seed'])
        actual,_ = run_episode(scenario,{**cfg,'max_observations':setting['max_observations']},expected['method'],expected['seed'])
        for key, value in expected.items():
            if key in {'setting','scenario_sha256'}:
                continue
            assert (list(actual[key]) if key=='final_position' else actual[key]) == value


def test_offroute_entropy_and_route_disruption_are_distinct_information():
    from spatial_memory.scheduling import AdaptiveObserver
    from spatial_memory.navigation import plan
    # Matched histories have identical generic uncertainty. Route location gives
    # different consequences of the SAME hypothetical occupancy change. This is
    # a constructive identifiability check, not a proposed policy implementation.
    grid = np.zeros((5,9),dtype=np.int8)
    a = AdaptiveObserver(grid,'uncertainty',20)
    b = AdaptiveObserver(grid,'uncertainty',20)
    np.testing.assert_array_equal(a.uncertainty(5),b.uncertainty(5))
    assert a.score(5,(1,2)) == b.score(5,(1,2))
    base = len(plan(grid,(1,2),(7,2)))
    onroute, offroute = grid.copy(),grid.copy()
    onroute[2,4]=1; offroute[0,4]=1
    assert len(plan(onroute,(1,2),(7,2))) > base
    assert len(plan(offroute,(1,2),(7,2))) == base


def test_occluded_family_really_hides_downstream_change():
    from spatial_memory.observation import Sensor
    s = generate_robustness('occluded',101)
    foreground = s.obstacles[0]
    important = tuple(s.changes[0]['cell'])
    pose = (foreground[0]-1,foreground[1])
    obs = Sensor(radius=5).observe(World(s).occupancy(),pose,np.random.default_rng(0))
    assert obs[important[1],important[0]] == -1
    assert obs[foreground[1],foreground[0]] == 1


def test_distinct_environment_realizations_ignore_family_labels():
    from dataclasses import asdict
    worlds = []
    for family in FAMILIES:
        for seed in CFG['seeds']:
            data = asdict(generate_robustness(family,seed))
            data.pop('name')
            worlds.append(json.dumps(data,sort_keys=True))
    assert len(set(worlds)) == len(worlds)


@pytest.mark.parametrize('family',['irrelevant','outdated'])
def test_intended_belief_stressors_occur_in_generated_episodes(family):
    from spatial_memory.scheduling import AdaptiveObserver
    from spatial_memory.observation import Sensor
    from spatial_memory.navigation import plan
    witnessed = False
    for seed in CFG['seeds']:
        scenario = generate_robustness(family,seed)
        _, frames = run_episode(scenario,CFG,'uncertainty',seed)
        observer = AdaptiveObserver(frames[0]['memory'],'uncertainty',CFG['sensor']['radius'])
        world = World(scenario)
        sensor = Sensor(**CFG['sensor'])
        for frame in frames[1:]:
            world.advance()
            entropy = observer.uncertainty(world.step)
            pose = frame['observation_position']
            route = plan(observer.memory.grid,pose,scenario.goal)
            if family == 'irrelevant' and route:
                route_mask = np.zeros(entropy.shape,bool)
                for x,y in route:
                    route_mask[y,x]=True
                yy,xx=np.indices(entropy.shape)
                footprint=(xx-pose[0])**2+(yy-pose[1])**2 <= CFG['sensor']['radius']**2
                high=(entropy >= CFG['adaptive']['entropy_threshold']) & (observer.last_observed>=0) & footprint
                witnessed |= bool(np.count_nonzero(high & ~route_mask)>np.count_nonzero(high & route_mask) and high.any())
            if family == 'outdated':
                for event in scenario.changes:
                    x,y=event['cell']
                    if event['step']==world.step:
                        witnessed |= bool(observer.memory.grid[y,x]==0 and (x,y) in route and entropy[y,x]<CFG['adaptive']['entropy_threshold'])
            if frame['observation_granted']:
                rng=np.random.default_rng(np.random.SeedSequence([seed,world.step]))
                observer.refresh(sensor.observe(world.occupancy(),pose,rng),world.step)
    assert witnessed, f'No intended belief stressor witnessed for {family}'
