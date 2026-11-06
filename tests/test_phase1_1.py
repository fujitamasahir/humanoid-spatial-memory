"""Phase 1.1 validity checks without accessing the held-out configuration."""
import json
from pathlib import Path
import numpy as np
import pytest
from spatial_memory.scenarios import generate_scenario, scenario_hash
from spatial_memory.simulation import Scenario, World
from spatial_memory.evaluation import run_episode, map_errors
from spatial_memory.navigation import plan

ROOT = Path(__file__).resolve().parents[1]
CFG = json.loads((ROOT/'configs/development_phase1_1.json').read_text())


@pytest.mark.parametrize('template', CFG['scenarios'], ids=lambda t: t['name'])
def test_generated_reproducibility_and_pairing(template):
    fingerprints = []
    for seed in CFG['seeds']:
        a = generate_scenario(template, seed)
        b = generate_scenario(template, seed)
        assert scenario_hash(a) == scenario_hash(b)
        fingerprints.append(scenario_hash(a))
        wa, wb = World(a), World(b)
        for _ in range(60):
            np.testing.assert_array_equal(wa.occupancy(), wb.occupancy())
            wa.advance(); wb.advance()
        sm, sf = run_episode(a, CFG, 'static', seed)
        pm, pf = run_episode(b, CFG, 'periodic', seed)
        np.testing.assert_array_equal(sf[0]['memory'], pf[0]['memory'])
        for x, y in zip(sf, pf):
            np.testing.assert_array_equal(x['geometry'], y['geometry'])
            np.testing.assert_array_equal(x['people'], y['people'])
        if template['name'] == 'empty':
            assert sm['success'] and pm['success']
            assert sm['travel_distance'] == pm['travel_distance'] == 8
    if template['name'] != 'empty':
        assert len(set(fingerprints)) == len(CFG['seeds'])


def test_variation_dimensions_and_no_hidden_input_mutation():
    template = next(t for t in CFG['scenarios'] if t['name']=='mixed')
    original = json.dumps(template, sort_keys=True)
    scenarios = [generate_scenario(template, s) for s in range(20)]
    assert len({s.pedestrians for s in scenarios}) > 5
    assert len({sum(c == s.pedestrians[0][0] for c in s.pedestrians[0]) for s in scenarios}) > 1
    assert len({tuple(s.changes[0]['cell']) for s in scenarios}) > 1
    assert json.dumps(template, sort_keys=True) == original


def test_persistent_change_invalidates_previously_usable_route():
    for kind in ('persistent','alternative'):
        t = next(t for t in CFG['scenarios'] if t['name']==kind)
        for seed in CFG['seeds']:
            s = generate_scenario(t, seed)
            w = World(s)
            initial = plan(w.geometry().astype(np.int8), s.start, s.goal)
            cell = tuple(s.changes[0]['cell'])
            assert cell in initial
            for _ in range(5):
                w.advance()
            alternate = plan(w.geometry().astype(np.int8), s.start, s.goal)
            assert alternate and cell not in alternate
            assert len(alternate) > len(initial)


def test_contact_entry_not_continuing_overlap_and_blocked_separation():
    # Robot cannot move; persistent object enters its cell and remains for 3 steps.
    s = Scenario.from_dict(dict(name='entry',split='development',width=4,height=3,
        start=[0,1],goal=[3,1], walls=[[1,1],[0,0],[0,2]],
        changes=[dict(step=1,action='add',cell=[0,1])]))
    cfg = {**CFG,'max_steps':3,'sensor':dict(radius=10,occlusion=False,noise=0)}
    m, f = run_episode(s,cfg,'static',0)
    assert m['dynamic_contacts'] == 1
    assert m['blocked_movement_attempts'] == m['travel_distance'] == 0
    assert m['elapsed_steps'] == 3
    # A hidden obstacle blocks repeated attempts, without entering the robot cell.
    s = Scenario.from_dict(dict(name='blocked',split='development',width=4,height=3,
        start=[0,1],goal=[3,1],obstacles=[[1,1]]))
    cfg['sensor']['radius'] = 0
    m, f = run_episode(s,cfg,'static',0)
    assert m['blocked_movement_attempts'] == 3
    assert m['dynamic_contacts'] == m['travel_distance'] == 0
    assert m['collision_count'] == 3  # deprecated aggregate only


def test_pedestrian_entry_contact():
    s = Scenario.from_dict(dict(name='person',split='development',width=4,height=3,
        start=[0,1],goal=[3,1],pedestrians=[[[0,2],[0,1],[0,1],[0,2]]]))
    m, _ = run_episode(s,{**CFG,'max_steps':1},'static',0)
    assert m['dynamic_contacts'] == 1
    assert m['travel_distance'] == 1
    assert m['blocked_movement_attempts'] == 0


def test_cumulative_and_final_metrics_from_snapshots():
    s = generate_scenario(CFG['scenarios'][3],7)
    for method in ('static','periodic'):
        m, frames = run_episode(s, CFG, method,7)
        for key in frames[0]['errors']:
            assert m[key] == sum(f['errors'][key] for f in frames)
            assert m['final_'+key] == frames[-1]['errors'][key]
        distance = sum(a['position'] != b['position'] for a,b in zip(frames,frames[1:]))
        assert m['travel_distance'] == distance
        assert m['elapsed_steps'] == len(frames)-1
        assert m['observation_cost'] == m['observation_count'] * CFG['observation_cost']


def test_generation_rejects_held_out():
    t = {**CFG['scenarios'][1], 'split':'held_out'}
    with pytest.raises(ValueError):
        generate_scenario(t,0)


def test_runner_protects_original_artifacts_and_rejects_reserved_split(tmp_path):
    import subprocess
    import sys
    runner = [sys.executable, str(ROOT/'scripts/run_experiment.py')]
    protected = subprocess.run(runner + ['--output', str(ROOT/'results/representative')],
                               capture_output=True, text=True)
    assert protected.returncode != 0 and 'protected' in protected.stderr
    # Synthetic config: never read or execute the actual held-out suite.
    config = {**CFG, 'split':'held_out'}
    file = tmp_path/'synthetic.json'
    file.write_text(json.dumps(config), encoding='utf-8')
    reserved = subprocess.run(runner + ['--config', str(file), '--output',str(tmp_path/'out')],
                              capture_output=True, text=True)
    assert reserved.returncode != 0 and 'reserved' in reserved.stderr
    assert not (tmp_path/'out').exists()
