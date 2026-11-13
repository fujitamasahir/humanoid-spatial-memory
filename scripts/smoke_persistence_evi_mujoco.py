"""Isolated synthetic G1 integration smoke, NOT an admitted Phase1.5 cohort.

Does not load/generate Phase1.5 records, bypass admission, or estimate efficacy.
Actual G1, 61-ray memory sensor, independent emergency sensor, selected-only
shield and original G1 planner are exercised for all five configurations.
"""
from __future__ import annotations
import argparse
import gzip
import json
from pathlib import Path
import sys
sys.path[:0] = [str(Path(__file__).resolve().parents[1]/'src'),
               str(Path(__file__).resolve().parent)]
import evaluate_persistence_evi_fit72 as study
from spatial_memory.emergency_safety import EmergencySafetyController, IndependentEmergencySafetySensor
from spatial_memory.evaluation import run_episode
from spatial_memory.mujoco_navigation import MujocoNavigationScene
from spatial_memory.mujoco_perception import MujocoRayPerception
from spatial_memory.navigation import (HEADINGS, heading_index, plan_g1_default_policy,
                                       assess_observed_pedestrian_risk)
from spatial_memory.pedestrian_tracking import ObservedPedestrianTracker
from spatial_memory.simulation import Scenario
from spatial_memory.evi import PersistenceEVIController
from spatial_memory.persistence import calibration_summary


def smoke_scenario():
    width, height = 11, 9
    walls = {(x, y) for x in range(width) for y in range(height)
             if x in (0, width-1) or y in (0, height-1)}
    return Scenario.from_dict(dict(name='bc-synthetic-integration-only', split='development',
        width=width, height=height, start=(1, 4), goal=(9, 4), walls=sorted(walls),
        obstacles=((5, 6),), changes=(),
        pedestrians=(((5, 2), (5, 3), (5, 4), (5, 5), (5, 6), (5, 5), (5, 4), (5, 3)),)))


def run_smoke(arm, config):
    scenario = smoke_scenario()
    scene = MujocoNavigationScene(scenario, cell_size=config['mujoco_cell_size_m'],
                                  timestep=config['mujoco_timestep_seconds'])
    memory_sensor = MujocoRayPerception(scene, **config['mujoco_ray_sensor'])
    emergency_config = {k: v for k, v in study.reference.base.SAFETY_CONFIG.items()
                        if k != 'horizontal_fov_deg'}  # safety FOV is fixed at 360
    emergency_sensor = IndependentEmergencySafetySensor(scene, **emergency_config)
    emergency_controller = EmergencySafetyController(scene)
    tracker = ObservedPedestrianTracker(max_age_steps=8)
    state = {'planner_step': 0, 'static_step': -1, 'static_cells': set(),
             'shield_queries': 0, 'last_reason': 'no_feasible_forward_route'}
    captured = {}

    def factory(initial, method, **options):
        b, c = study.ARMS[arm]
        sensor = {k: config['mujoco_ray_sensor'][k]
                  for k in ('range_m', 'horizontal_fov_deg', 'ray_count')}
        sensor['cell_size'] = config['mujoco_cell_size_m']
        captured['agent'] = PersistenceEVIController(initial, method, **options,
            persistence=b, evi=c, sensor=sensor)
        return captured['agent']

    def record(_observation, step, _position):
        stats = memory_sensor.last_stats
        tracker.observe(step, stats.get('visible_pedestrian_cells', ()))
        state['static_cells'] = {tuple(cell) for cell in
                                 stats.get('visible_persistent_obstacle_cells', ())}
        state['static_step'] = int(step)

    def planner(grid, position, goal, unknown, yaw, blocked):
        state['planner_step'] += 1
        context = tracker.context()
        recent = state['static_cells'] if 0 <= state['planner_step']-state['static_step'] <= 8 else set()
        route = plan_g1_default_policy(grid, position, goal,
            heading=heading_index(yaw), unknown=unknown,
            local_extents=scene.footprint_half_extents_local, cell_size=scene.cell_size,
            blocked_actions=blocked, static_obstacle_cells=recent,
            pedestrian_context=context, step=state['planner_step'])
        if route:
            kind, value = route[0]
            reasons = {'turn': 'route_direction_change',
                       'sidestep': 'observed_static_obstacle_blocks_forward_path'}
            state['last_reason'] = reasons.get(kind, 'forward_route_segment')
            if kind == 'retreat':
                state['last_reason'] = assess_observed_pedestrian_risk(position,
                    heading_index(yaw), context, step=state['planner_step']) or 'observed_oncoming_pedestrian_imminent'
            if kind == 'wait':
                state['last_reason'] = str(value)
        else:
            state['last_reason'] = 'no_feasible_forward_route'
        return route

    def selected_check(world, position, action, yaw):
        state['shield_queries'] += 1
        kind, value = action
        if kind in {'move', 'sidestep', 'retreat'}:
            return scene.check_move(world, position, tuple(value), yaw, target_yaw=yaw)
        return scene.check_turn(world, position, yaw, HEADINGS[int(value)])

    method = arm if arm in ('periodic', 'age') else 'age'
    kwargs = {'_controller_factory': factory} if arm in study.ARMS else {}
    metrics, frames = run_episode(scenario, config, method, 42,
        _frame_callback=scene.update, _observation_provider=memory_sensor.observe,
        _g1_planner=planner, _action_checker=selected_check,
        _initial_observation_callback=record, _observation_callback=record,
        _g1_action_reason=lambda *_: state['last_reason'],
        _emergency_safety_sensor=emergency_sensor.scan,
        _emergency_safety_controller=emergency_controller.choose, **kwargs)
    selected = sum(f.get('navigation_action') is not None and
                   f['navigation_action'][0] != 'wait' for f in frames)
    if state['shield_queries'] != selected:
        raise RuntimeError('Extra/missing selected-action shield calls')
    if metrics['observation_count'] > 20 or metrics['emergency_safety_scans'] != metrics['elapsed_steps']:
        raise RuntimeError('Sensor count invariant failed')
    metrics.update(shield_queries=selected, unselected_shield_queries=0,
        paid_memory_rays=61*metrics['observation_count'],
        distance_m=scene.cell_size*metrics['travel_distance'])
    diagnostics = {}
    if captured:
        agent = captured['agent']
        diagnostics = {'decisions': agent.decisions, 'observation_log': agent.observation_log,
            'scheduler_ms': agent.scheduler_decision_total_ns/1e6,
            'calibration_belief': calibration_summary(agent.belief.calibration) if agent.belief is not None else None,
            'inference_log': agent.belief.inference_log if agent.belief is not None else []}
        if agent.used != metrics['observation_count']:
            raise RuntimeError('Controller/evaluator scan counts differ')
    trace = [{'step': f['step'], 'position': f['position'], 'yaw': f['heading_yaw'],
              'action': f.get('navigation_action'), 'scan': f.get('observation_granted'),
              'memory': f['memory']} for f in frames]
    return study.reference.base._jsonable_row({'arm': arm, 'metrics': metrics,
                                      'diagnostics': diagnostics, 'trace': trace})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    _, _, provenance, _ = study.reference.base.load_baseline()
    config = study.reference.base.frozen_config(provenance)
    args.output.mkdir(parents=True, exist_ok=False)
    study.reference.base.write_json(args.output/'provenance.json', {
        **study.source_metadata(), 'config': config, 'status': 'SYNTHETIC_INTEGRATION_ONLY',
        'not_phase15_population': True, 'scenario': 'smoke_scenario() in source',
        'synthetic_source_sha256': study.reference._sha(Path(__file__))})
    rows = []
    for arm in ('periodic', 'age', *study.ARMS):
        episode = run_smoke(arm, config)
        with gzip.open(args.output/f'{arm}.json.gz', 'xt') as stream:
            json.dump(episode, stream, sort_keys=True, allow_nan=False)
        m = episode['metrics']
        row = {'arm': arm, 'success': m['success'], 'steps': m['elapsed_steps'],
               'paid_scans': m['observation_count'], 'memory_rays': m['paid_memory_rays'],
               'emergency_scans': m['emergency_safety_scans'],
               'emergency_rays': m['emergency_safety_raycasts'],
               'contacts': m['g1_unwanted_contact_pairs'], 'distance_m': m['distance_m'],
               'blocked_attempts': m['g1_footprint_blocked_attempts'],
               'emergency_interventions': m['emergency_safety_interventions'],
               'false_persistent_cell_times': m['false_persistent_occupancy_updates'],
               'missed_persistent_change_cell_times': m['missed_persistent_changes'],
               'scheduler_ms': episode['diagnostics'].get('scheduler_ms'),
               'unselected_shield_queries': 0}
        rows.append(row)
        print(json.dumps(row), flush=True)
    study.reference.base.write_json(args.output/'summary.json', {
        'status': 'COMPLETED_SYNTHETIC_INTEGRATION_ONLY', 'rows': rows,
        'efficacy_or_baseline_reproduction_claim': False})


if __name__ == '__main__':
    main()
