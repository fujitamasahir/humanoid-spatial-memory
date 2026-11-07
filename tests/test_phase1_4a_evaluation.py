"""Evaluator instrumentation, manifest isolation, and historical compatibility."""
from copy import deepcopy
from dataclasses import asdict
import inspect
import json
from pathlib import Path
import sys
import numpy as np
import pytest
from spatial_memory.task_policies import METHODS
from spatial_memory.robustness import generate_robustness
from spatial_memory.evaluation import run_episode
from spatial_memory.protocol_evaluation import run_protocol_episode,feasibility_summary
from spatial_memory.manifests import (build_manifests,canonical_environment,environment_hash,
    layout_hash,validate_manifest,require_smoke_record)
from spatial_memory.simulation import Scenario
ROOT=Path(__file__).resolve().parents[1]
CFG=json.loads((ROOT/'configs/development_phase1_4a_smoke.json').read_text())


@pytest.mark.parametrize('method',METHODS)
def test_episode_runtime_accounting_traces_and_paired_initial_views(method):
    s=generate_robustness('occluded',6101)
    m,f,samples=run_protocol_episode(s,CFG,method,6101)
    assert m['common_planner_calls']==len(f)==m['elapsed_steps']+1
    assert m['scheduler_astar_calls']==sum(d['scheduler_astar_calls'] for d in f[1:])
    assert m['scheduler_seconds']==sum(d['scheduler_seconds'] for d in f[1:])
    assert m['common_planner_seconds']==sum(d['common_planner_seconds'] for d in f)
    assert m['observation_count']==sum(d['observation_granted'] for d in f)
    assert all(d['scheduler_seconds']>=d['scheduler_astar_seconds']>=0 for d in f[1:])
    assert all('policy_details' in d and 'reason' in d for d in f[1:])
    assert m['episode_runtime_seconds']>=m['scheduler_seconds']+m['common_planner_seconds']
    for frame in f[1:]:
        assert (frame['received_observation'] is not None)==frame['observation_granted']
    assert {r['step'] for r in samples}=={d['step'] for d in f[1:] if d['observation_granted']}
    assert m['feasibility']['samples']==len(samples)
    reference=run_episode(s,CFG,'static',6101)[1]
    np.testing.assert_array_equal(f[0]['memory'],reference[0]['memory'])
    for a,b in zip(f,reference):
        np.testing.assert_array_equal(a['geometry'],b['geometry'])
        np.testing.assert_array_equal(a['people'],b['people'])
    if method=='disruption-visible':
        for d in f[1:]:
            assert d['scheduler_astar_calls']==1+2*len(d['policy_details']['candidates'])
    elif method=='route-weighted':
        assert all(d['scheduler_astar_calls']==1 for d in f[1:])
    elif method=='query-gate-conceptual':
        assert all(d['scheduler_astar_calls']==2 for d in f[1:])


def deterministic(value):
    if isinstance(value,np.ndarray):
        return value.tolist()
    if isinstance(value,dict):
        return {k:deterministic(v) for k,v in value.items()
                if 'seconds' not in k and k not in {'scheduler_latency_median','scheduler_latency_p95'}}
    if isinstance(value,(tuple,list)):
        return [deterministic(v) for v in value]
    return value


@pytest.mark.parametrize('method',['random-quota','disruption-visible','query-gate-conceptual'])
def test_repeated_metrics_and_decision_traces_without_wallclock(method):
    s=generate_robustness('detour',6102)
    a=run_protocol_episode(s,CFG,method,6102)
    b=run_protocol_episode(s,CFG,method,6102)
    assert deterministic(a)==deterministic(b)


def test_feasibility_brier_bins_and_groups():
    rows=[dict(probability=0.,visible=1,unknown_blocker=False),
          dict(probability=.2,visible=0,unknown_blocker=True),
          dict(probability=1.,visible=1,unknown_blocker=True)]
    s=feasibility_summary(rows)
    assert s['brier']==pytest.approx(1.04/3)
    assert s['mae']==pytest.approx(1.2/3)
    assert [b['bin'] for b in s['bins']]==[0,1,4]
    assert s['by_blocker']['unknown']['samples']==2
    assert feasibility_summary([])['brier'] is None


def test_canonical_hashes_remove_labels_and_static_order_but_keep_events():
    s=generate_robustness('detour',6102)
    data=asdict(s);data['name']='other';data['split']='held_out';data['walls']=tuple(reversed(data['walls']))
    renamed=Scenario.from_dict(data)
    assert environment_hash(s)==environment_hash(renamed)
    assert layout_hash(s)==layout_hash(renamed)
    data['changes'][0]['step']+=1
    modified=Scenario.from_dict(data)
    assert environment_hash(s)!=environment_hash(modified)
    assert layout_hash(s)==layout_hash(modified)


def test_manifests_repeat_disjoint_audited_no_policy_execution(monkeypatch):
    import spatial_memory.task_policies as policies
    def forbidden(*a,**k):
        raise AssertionError('Manifest generation must never execute policies')
    monkeypatch.setattr(policies.PolicyController,'decide',forbidden)
    excluded=environment_hash(generate_robustness('detour',10000))
    a=build_manifests([excluded],[10001],families=('detour',))
    b=build_manifests([excluded],[10001],families=('detour',))
    assert a==b
    assert len(a['tuning']['records'])==5 and len(a['assessment']['records'])==10
    assert validate_manifest(a['tuning']).isdisjoint(validate_manifest(a['assessment']))
    assert not a['assessment']['outcomes_generated']
    assert a['tuning']['rejections'][0]['reason']=='duplicate_environment'
    assert a['tuning']['rejections'][1]['reason']=='historical_seed'
    corrupted=deepcopy(a['tuning']);corrupted['records'][0]['layout_sha256']='bad'
    with pytest.raises(ValueError):
        validate_manifest(corrupted)
    for part in a.values():
        with pytest.raises(ValueError,match='not authorized'):
            require_smoke_record(part['records'][0])


def test_evaluator_gates_and_truth_never_reaches_policy(monkeypatch):
    from spatial_memory.task_policies import PolicyController
    captured=[]
    original=PolicyController.__init__
    def check(self,*args,**kwargs):
        captured.append(kwargs)
        assert set(kwargs)=={'goal','radius','parameters','ablation','schedule','observation_cost','max_observations'}
        assert all(not isinstance(v,Scenario) for v in (*args,*kwargs.values()))
        original(self,*args,**kwargs)
    monkeypatch.setattr(PolicyController,'__init__',check)
    s=generate_robustness('detour',6102)
    run_protocol_episode(s,CFG,'route-weighted',6102)
    assert captured
    for purpose in ('assessment','tuning','held_out'):
        with pytest.raises(ValueError,match='authorized'):
            run_protocol_episode(s,CFG,'route-weighted',6102,purpose=purpose)
    with pytest.raises(ValueError,match='namespace'):
        run_protocol_episode(s,CFG,'route-weighted',20000)
    held=asdict(s);held['split']='held_out'
    with pytest.raises(ValueError):
        run_protocol_episode(Scenario.from_dict(held),CFG,'route-weighted',6102)


def test_smoke_size_and_history_output_guards(tmp_path):
    sys.path.insert(0,str(ROOT/'scripts'))
    from run_phase1_4a_validation import smoke,protect_output
    for path in ('results','results/phase1_3','results/phase1_3/development','results/representative'):
        with pytest.raises(ValueError):
            protect_output(ROOT/path)
    invalid=deepcopy(CFG);invalid['realizations'][0]['seed']=20000
    with pytest.raises(ValueError):
        smoke(invalid,tmp_path)
    invalid=deepcopy(CFG);invalid['realizations']*=2
    with pytest.raises(ValueError):
        smoke(invalid,tmp_path)


def test_full_plan_runtime_counts_and_synthetic_workload_diversity():
    sys.path.insert(0,str(ROOT/'scripts'))
    from benchmark_phase1_4a import counts,workloads
    assert sum(counts().values())==18900
    cases=workloads()
    assert len(cases)>=5 and len({tuple(c['grid'].shape) for c in cases})>=3
    assert any(np.any(c['grid']==-1) for c in cases)
    assert any(c['name']=='no-route' for c in cases)


@pytest.mark.parametrize('method',['static','age','uncertainty','periodic1','periodic2','periodic5'])
def test_protocol_wrapper_matches_historical_episode_mechanics(method):
    s=generate_robustness('detour',6102)
    interval=int(method[-1]) if method.startswith('periodic') else 2
    old_name='periodic' if method.startswith('periodic') else method
    expected,old_frames=run_episode(s,{**CFG,'update_interval':interval},old_name,6102)
    actual,frames,_=run_protocol_episode(s,CFG,method,6102)
    for key,value in expected.items():
        if key!='method':
            assert actual[key]==value,key
    assert [f['position'] for f in frames]==[f['position'] for f in old_frames]


@pytest.mark.parametrize('method',['route-weighted','disruption-visible','query-gate-conceptual','fixed-rate','random-quota'])
def test_hidden_distant_changes_do_not_change_public_decisions(method):
    base=dict(name='isolation',split='development',width=13,height=7,start=[1,3],goal=[11,3])
    a=Scenario.from_dict(base)
    b=Scenario.from_dict({**base,'changes':[dict(step=1,action='add',cell=[11,5])]})
    cfg={**CFG,'max_steps':2,'max_observations':2,'sensor':dict(radius=3,occlusion=True,noise=0)}
    _,af,_=run_protocol_episode(a,cfg,method,6104)
    _,bf,_=run_protocol_episode(b,cfg,method,6104)
    for x,y in zip(af[1:],bf[1:]):
        assert deterministic(x['policy_details'])==deterministic(y['policy_details'])
        assert x['observation_requested']==y['observation_requested']
        assert x['position']==y['position']
