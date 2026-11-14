"""Shared factory restoration and gating tests; no FIT outcomes used."""
import sys
from pathlib import Path
from unittest.mock import Mock
import numpy as np
import pytest
sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
import caa_common as common
from spatial_memory.scheduling import AdaptiveParameters


def test_adapter_restores_evaluator_and_sensor_after_error(monkeypatch):
    original=common.ref.base.run_episode;observe=common.fit.MujocoRayPerception.observe
    def broken(*a,**kw):raise RuntimeError('synthetic failure')
    monkeypatch.setattr(common.ref.base,'run_case',broken)
    with pytest.raises(RuntimeError):common.run_case({},0,'age4',{})
    assert common.ref.base.run_episode is original
    assert common.fit.MujocoRayPerception.observe is observe


@pytest.mark.parametrize('arm',['caa_fast','caa_slow','caa_full','age6','age5'])
def test_factory_uses_only_last_write_memory_and_finite_cap(arm):
    import run_caa_fit72 as matrix
    initial=np.zeros((4,5),dtype=np.int8)
    options=dict(interval=4,radius=3,parameters=AdaptiveParameters(),max_observations=20)
    config={'mujoco_ray_sensor':dict(range_m=6.,horizontal_fov_deg=120.,ray_count=61),'mujoco_cell_size_m':.75}
    controller=matrix.factory(initial,arm,config,options)
    assert controller.used==1 and controller.cap==20
    np.testing.assert_array_equal(controller.memory.grid,initial)
    if arm.startswith('caa_'):
        assert not hasattr(controller,'belief')
        assert not hasattr(controller,'evi_function')
    if arm=='age6':assert controller.agent.parameters.age_steps==6
    if arm=='age5':assert controller.belief is None


def test_gate_failure_precedes_world_access(tmp_path,monkeypatch):
    import run_caa_fit72 as matrix
    monkeypatch.setattr(matrix,'OUT',tmp_path)
    forbidden=Mock(side_effect=AssertionError('Unapproved FIT read'))
    monkeypatch.setattr(matrix.fit,'verify_original_data_integrity',forbidden)
    with pytest.raises(FileNotFoundError):matrix.run(True)
    forbidden.assert_not_called()


@pytest.mark.parametrize('arm',['age4','age5','caa_full'])
def test_instrumented_adapter_executes_history_and_real_call_ledger(monkeypatch,arm):
    import run_caa_fit72 as matrix
    from spatial_memory.change_aware_age import CellHistory
    initial=np.zeros((4,5),dtype=np.int8)
    class Sensor:
        ray_count=61;horizontal_fov_deg=120.;range_m=6.
    class World:
        step=0
    world=World();sensor=Sensor()
    monkeypatch.setattr(common.fit.MujocoRayPerception,'observe',lambda *a:initial.copy())
    def original_episode(scenario,config,method,**kw):
        observed=common.fit.MujocoRayPerception.observe(sensor,world,(1,1),0.)
        agent=kw['_controller_factory'](observed,method,interval=4,radius=3,
            parameters=AdaptiveParameters(),max_observations=20)
        frames=[{'step':0,'observation_granted':True}]
        for t in range(1,13):
            world.step=t;agent.set_navigation_context(goal=(4,2),yaw=0.,unknown='optimistic')
            result=agent.decide(t,(1,1))
            if result['observation_granted']:
                observed=common.fit.MujocoRayPerception.observe(sensor,world,(1,1),0.)
                agent.refresh(observed,t)
            frames.append({'step':t,'observation_granted':result['observation_granted']})
        return {'observation_count':agent.used,'g1_unselected_action_shield_queries':0,
                'g1_shield_query_count_valid':True},{'steps':frames}
    monkeypatch.setattr(common.ref.base,'run_episode',original_episode)
    monkeypatch.setattr(common.ref.base,'run_case',lambda *a,**kw:common.ref.base.run_episode(None,{},'age'))
    config={'mujoco_ray_sensor':dict(range_m=6.,horizontal_fov_deg=120.,ray_count=61),'mujoco_cell_size_m':.75}
    row,trace,diag=common.run_case({},0,arm,config,factory=matrix.factory,history_factory=CellHistory)
    assert row['observation_count']==len(diag['actual_memory_call_steps'])
    assert diag['decisions'][0]['global_history']['classes']['intermediate']==20
    assert common.ref.base.run_episode is original_episode
