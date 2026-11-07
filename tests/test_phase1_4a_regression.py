"""Replay stored Phase 1.3 metrics; these are regression checks, not new research."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from spatial_memory.evaluation import run_episode
from spatial_memory.scenarios import generate_scenario
from spatial_memory.simulation import Scenario
from spatial_memory.robustness import episode_config
ROOT=Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('artifact',['development','corridor_diagnostic'])
def test_all_phase1_3_historical_metrics(artifact):
    payload=json.loads((ROOT/'results/phase1_3'/artifact/'results.json').read_text())
    scenarios={r['scenario_sha256']:Scenario.from_dict(r['scenario']) for r in payload['realized_scenarios']}
    for expected in payload['episodes']:
        if artifact=='development':
            base=payload['config']
            setting=next(s for s in base['settings'] if s['name']==expected['setting'])
            cfg=episode_config(base,setting)
        else:
            cfg=deepcopy(payload['specification']['config'])
            cfg['common_horizon_metrics']=True
            cfg['adaptive']['prior_flips']=expected['prior_flips']
        scenario=scenarios[expected['scenario_sha256']]
        actual,frames=run_episode(scenario,cfg,expected['method'],expected['seed'])
        grants=[f['step'] for f in frames if f['observation_granted']]
        for key,value in expected.items():
            if key in {'setting','scenario_sha256','removal_step','prior','prior_flips'}:
                continue
            if key=='observation_steps':
                assert value==grants
            elif key=='persistent_observation_timing':
                timing=[dict(event_step=e['step'],action=e['action'],first_observation_delay=
                        next((t-e['step'] for t in grants if t>=e['step']),None)) for e in scenario.changes]
                assert value==timing
            else:
                assert (list(actual[key]) if key=='final_position' else actual[key])==value,(artifact,key)


def test_all_phase1_0_representative_metrics():
    payload=json.loads((ROOT/'results/representative/results.json').read_text(encoding='utf-8-sig'))
    cfg=payload['config']
    for expected in payload['episodes']:
        template=next(t for t in cfg['scenarios'] if t['name']==expected['scenario'])
        scenario=Scenario.from_dict(template)
        actual,_=run_episode(scenario,cfg,expected['method'],expected['seed'])
        for key,value in expected.items():
            assert actual[key]==value
