"""Synthetic injection and shared-loop checks; no population generation."""
from pathlib import Path
import sys
import numpy as np
import pytest
sys.path.insert(0, str(Path(__file__).parents[1]/'scripts'))
import evaluate_persistence_evi_fit72 as screen


@pytest.mark.parametrize('arm', ['b_age', 'c_ternary', 'bc'])
def test_injection_keeps_sensor_shield_and_planner_callbacks(monkeypatch, arm):
    shield = object()
    planner = object()
    sensor = object()
    def episode(scenario, config, method, **kwargs):
        assert kwargs['_action_checker'] is shield
        assert kwargs['_g1_planner'] is planner
        assert kwargs['_observation_provider'] is sensor
        initial = np.zeros((5, 7), dtype=np.int8)
        agent = kwargs['_controller_factory'](initial, method, interval=4, radius=3,
            parameters=None, max_observations=20)
        for step in range(1, 6):
            agent.set_navigation_context(goal=(5, 2), yaw=0., unknown='optimistic')
            decision = agent.decide(step, (1, 2))
            if decision['observation_granted']:
                kwargs['_observation_callback'](initial, step, (1, 2))
                agent.refresh(initial, step)
        frames = [{'step': 0, 'observation_granted': True, 'action': None}]
        frames += [{'step': step, 'action': ['move', [2, 2]],
                    'observation_granted': any(e['step'] == step for e in agent.observation_log)}
                   for step in range(1, 6)]
        return {'observation_count': agent.used, 'g1_shield_query_count_valid': True,
                'g1_unselected_action_shield_queries': 0}, {'steps': frames}
    monkeypatch.setattr(screen.reference.base, 'run_episode', episode)
    def run_case(*args, **kwargs):
        return screen.reference.base.run_episode(None, {}, 'age', _action_checker=shield,
            _g1_planner=planner, _observation_provider=sensor)
    monkeypatch.setattr(screen.reference.base, 'run_case', run_case)
    row, trace, diagnostic = screen.run_arm({}, 0, arm, {
        'mujoco_ray_sensor': {'range_m': 6., 'horizontal_fov_deg': 120., 'ray_count': 61},
        'mujoco_cell_size_m': .75})
    assert row['observation_count'] <= 20
    assert screen.reference.base.run_episode is episode
    assert len(trace['steps']) == 6
    assert diagnostic['scheduler_total_ms'] >= 0


def test_injected_factory_restored_on_error(monkeypatch):
    original = screen.reference.base.run_episode
    def fail(*a, **k):
        raise RuntimeError('test failure')
    monkeypatch.setattr(screen.reference.base, 'run_case', fail)
    with pytest.raises(RuntimeError, match='test failure'):
        screen.run_arm({}, 0, 'bc', {})
    assert screen.reference.base.run_episode is original


@pytest.mark.parametrize('arm', ['b_age', 'c_ternary', 'bc'])
def test_actual_g1_61ray_emergency_and_selected_only_shield(arm):
    import json
    import smoke_persistence_evi_mujoco as smoke
    _, _, provenance, _ = screen.reference.base.load_baseline()
    config = screen.reference.base.frozen_config(provenance)
    result = smoke.run_smoke(arm, config)
    # Serialization is part of the reproducibility contract.
    json.dumps(result, allow_nan=False)
    metrics = result['metrics']
    assert 1 <= metrics['observation_count'] <= 20
    assert metrics['paid_memory_rays'] == metrics['observation_count']*61
    assert metrics['emergency_safety_scans'] == metrics['elapsed_steps']
    assert metrics['emergency_safety_raycasts'] == metrics['elapsed_steps']*61
    assert metrics['unselected_shield_queries'] == 0
    assert metrics['g1_unwanted_contact_pairs'] == 0
    assert len(result['diagnostics']['observation_log'])+1 == metrics['observation_count']


def test_paired_summary_clusters_schedules_and_censors_failures():
    rows = []
    for schedule, success in [(0, True), (1, False)]:
        row = dict(world_identity='synthetic-maze', schedule=schedule,
            reference_success=True, candidate_success=success,
            candidate_scheduler_total_ms=1., candidate_triggered_scans=0,
            candidate_blocked_feedback_count=0, candidate_no_route_feedback_count=0,
            candidate_blocked_attempts=0, reference_blocked_attempts=0)
        for side in ('reference', 'candidate'):
            row.update({side+'_observations': 3, side+'_memory_rays': 183,
                side+'_steps_h80': 8 if side == 'reference' or success else 80,
                side+'_distance_m': 6., side+'_emergency_scans': 8,
                side+'_emergency_rays': 488, side+'_episode_wall_seconds': .1,
                side+'_unwanted_contacts': 0})
            row[side+'_false_persistent_occupancy_updates'] = 0
            row[side+'_missed_persistent_changes'] = 0
        rows.append(row)
    summary = screen.summarize_pairs(rows)
    assert summary['independent_maze_layouts'] == 1
    assert summary['harmed_successes'] == 1
    assert summary['paired_common_success']['episodes'] == 1
    assert summary['paired_common_success_means']['candidate_steps_h80'] == 8
    assert summary['maze_level_deltas'][0]['correlated_schedules'] == 2
    assert summary['maze_level_deltas'][0]['steps_h80'] == 36
