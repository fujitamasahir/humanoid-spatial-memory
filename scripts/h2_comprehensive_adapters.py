"""Scoped adapters for the already implemented H2 comprehensive arms.

No policy implementation is changed here. The adapter routes the frozen H2
episode API to existing controllers and adds only feedback already required by
the original Event and online RDAO Gate implementations.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'scripts')]

import h2_final_common as frozen
import h2_high_frequency_dynamics as engine
import evaluate_phase2_61ray_emergency_safety_full_288 as evaluator

ELIGIBLE = tuple(x['model_id'] for x in __import__(
    'json').loads((ROOT/'results/phase2_mujoco/h2_comprehensive_benchmark_v1/protocol/model_registry.json').read_text())
    if x['authorization_status'] == 'eligible')
ADDITIONAL = tuple(x for x in ELIGIBLE if x not in frozen.ARMS and x != 'uncertainty')


def _sensor(config):
    result = {k: config['mujoco_ray_sensor'][k]
              for k in ('range_m', 'horizontal_fov_deg', 'ray_count')}
    result['cell_size'] = config['mujoco_cell_size_m']
    return result


def _factory(arm, config, gate_state):
    from dataclasses import replace
    from spatial_memory.cadence_age import CadenceController
    from spatial_memory.view_age import ViewAgeController
    from spatial_memory.event_observation import EventObservationParameters, EventTriggeredObservationController
    from spatial_memory.rdao import RDAOController
    from spatial_memory.rdao_v22_decision_protected import RDAOv22DecisionProtectedController
    from spatial_memory.evi import PersistenceEVIController, EVIParameters
    from spatial_memory.persistence import PersistenceParameters
    from spatial_memory.candidate_coverage import (ExpandedEVIParameters,
        information_value_uncertainty_k, information_value_original_audit)
    from spatial_memory.topology_evi_d import information_value_topology_d
    from spatial_memory.multistep_evi import ARMS as MS_ARMS, MultiStepParameters as MSParams
    from spatial_memory.multistep_depth_ablation import ARMS as DEPTH_ARMS, MultiStepParameters as DepthParams
    from spatial_memory.change_aware_age import ChangeAwareAgeController
    from spatial_memory.dao_navigation_compat_v1_1 import DAONavigationCompatV1_1
    from spatial_memory.attenuated_dao_veto_v1 import AttenuatedDAOVeto, ARMS as ATTENUATED
    from spatial_memory.route_gated_dao_veto_v1 import RouteGatedDAOVeto, ARMS as ROUTE_GATED
    from spatial_memory.history_gated_deadline_v1 import HistoryGatedDeadline, MODES as HISTORY_MODES
    from spatial_memory.route_adaptive_age_v1 import RouteAdaptiveAgeV1

    sensor = _sensor(config)
    base_sensor = dict(sensor)
    base_sensor.pop('cell_size')
    maxobs = 20

    def create(initial, mode, **options):
        options['max_observations'] = maxobs
        if arm == 'static':
            from spatial_memory.scheduling import ObservationController
            return ObservationController(initial, 'static', **options)
        if arm in ('age_gap4', 'age_motion'):
            return CadenceController(initial, 'age', cadence_mode=arm, sensor=sensor,
                persistence=False, **options)
        if arm in ('age_view_veto', 'age_view_clock'):
            return ViewAgeController(initial, 'age', view_mode=arm, sensor=sensor,
                persistence=False, **options)
        if arm in ('periodic_event', 'age_event'):
            base_mode = 'periodic' if arm == 'periodic_event' else 'age'
            return EventTriggeredObservationController(initial, base_mode,
                event_parameters=EventObservationParameters(), **options)
        if arm in ('rdao_v1','rdao_v1_footprint') or arm in ('rdao_v1_gate_first', 'rdao_v1_gate_every'):
            cls = RDAOController
            if arm.startswith('rdao_v1_gate_'):
                helper = __import__('evaluate_rdao_online_safe_gate_screen')
                parent = helper.CandidateOnlineGateRDAO
                policy = 'first' if arm.endswith('first') else 'every'
                class Gated(parent):
                    def decide(self, step, position):
                        out = super().decide(step, position)
                        if out['observation_granted']:
                            self.gate_pre_map = self.memory.grid.copy()
                            self.gate_pre_step = int(step)
                            self.gate_pre_position = tuple(position)
                        else:
                            self.gate_pre_step = None
                        return out
                cls = Gated
                gate_state.update(policy=policy, overrides=0, events=[])
            return cls(initial, goal=tuple(gate_state['goal']), max_observations=maxobs,
                unknown=config['unknown'], local_extents=config['g1_navigation']['local_half_extents_m'],
                cell_size_m=config['mujoco_cell_size_m'], **base_sensor)
        if arm == 'rdao_v22':
            return RDAOv22DecisionProtectedController(initial, goal=tuple(gate_state['goal']),
                max_observations=maxobs, unknown=config['unknown'],
                local_extents=config['g1_navigation']['local_half_extents_m'],
                cell_size_m=config['mujoco_cell_size_m'], **base_sensor)
        if arm in ('b_age', 'c_ternary', 'bc', 'c0_audit', 'c_k', 'c_topology3d') or arm.startswith('ms_') or arm.startswith('h1_') or arm.startswith('h3_'):
            evi_function = None; evi_params = None; persistence = arm in ('b_age','bc')
            if arm == 'c0_audit':
                evi_function = information_value_original_audit
            elif arm == 'c_k':
                evi_function = information_value_uncertainty_k
                evi_params = ExpandedEVIParameters(max_candidates=5)
            elif arm == 'c_topology3d':
                evi_function = information_value_topology_d
                evi_params = EVIParameters(max_candidates=3)
            elif arm.startswith('ms_'):
                evi_function = MS_ARMS[arm]
                selector = 'topology' if 'topology' in arm else 'k'
                evi_params = MSParams(3 if selector == 'topology' else 5)
                persistence = False
            elif arm.startswith(('h1_', 'h3_')):
                evi_function = DEPTH_ARMS[arm]
                selector = 'topology' if 'topology' in arm else 'k'
                evi_params = DepthParams(3 if selector == 'topology' else 5)
                persistence = False
            return PersistenceEVIController(initial, mode, **options,
                persistence=persistence, evi=arm != 'b_age', sensor=sensor,
                persistence_parameters=PersistenceParameters(),
                evi_parameters=evi_params, evi_function=evi_function)
        if arm == 'caa_slow':
            return ChangeAwareAgeController(initial, mode='caa_slow', **options)
        if arm.startswith('dao_') or arm in ('deadline_stable','deadline_stable_quiet'):
            dao_options = dict(options, sensor=sensor)
            if arm in ('dao_veto','dao_trigger','dao_route','dao_combined'):
                return DAONavigationCompatV1_1(initial, mode=arm, **dao_options)
            if arm in ATTENUATED:
                return AttenuatedDAOVeto(initial, factor=ATTENUATED[arm], **dao_options)
            if arm in ROUTE_GATED:
                return RouteGatedDAOVeto(initial, gate_mode=ROUTE_GATED[arm], **dao_options)
            if arm in HISTORY_MODES:
                return HistoryGatedDeadline(initial, history_mode=arm, **dao_options)
        if arm in ('raa_advance','raa_joint'):
            return RouteAdaptiveAgeV1(initial, mode=arm, sensor=sensor, **options)
        raise ValueError(f'No frozen adapter for {arm!r}')
    return create


def _install_feedback(arm, original, context):
    if arm not in ('periodic_event','age_event'):
        return original
    def with_public_feedback(scenario, config, method, **kwargs):
        check = kwargs['_action_checker']
        planner = kwargs['_g1_planner']
        def checked(world, position, action, yaw):
            result = check(world, position, action, yaw)
            if result[0]:
                context['controller'].note_selected_action_rejected(world.step)
            return result
        def planned(grid, position, goal, unknown, yaw, blocked):
            result = planner(grid, position, goal, unknown, yaw, blocked)
            if not result:
                core = context['controller']
                step = int(getattr(core, 'last_decision_step', 0))
                if step > 0: core.note_no_route(step)
            return result
        kwargs['_action_checker'] = checked
        kwargs['_g1_planner'] = planned
        return original(scenario, config, method, **kwargs)
    return with_public_feedback


def _install_gate_planner(arm, old_planner, state, config):
    if arm not in ('rdao_v1_gate_first','rdao_v1_gate_every'):
        return old_planner
    from evaluate_rdao_online_safe_gate_screen import online_gate_decision
    policy = 'first' if arm.endswith('first') else 'every'
    def gate_planner(grid, start, goal, **kwargs):
        agent = state.get('controller')
        if (agent is None or getattr(agent,'gate_pre_step',None) !=
                getattr(agent,'current_step',-1) or
                agent.last_observation_step != agent.current_step):
            return old_planner(grid,start,goal,**kwargs)
        if tuple(start) != tuple(agent.gate_pre_position):
            raise RuntimeError('RDAO gate pose drift')
        route, event = online_gate_decision(agent.gate_pre_map,grid,start,goal,
            kwargs,old_planner,prior_overrides=state['overrides'],policy=policy)
        event['step']=int(agent.current_step);state['events'].append(event)
        state['overrides'] += int(event['override_applied'])
        return route
    return gate_planner


def run_case(payload, schedule, arm, condition):
    """Execute one source-faithful episode through the committed H2 runner."""
    if arm not in ADDITIONAL:
        raise ValueError(f'Arm not registered as eligible additional model: {arm}')
    old_factory = frozen.factory
    base = frozen.ref.base
    old_episode = base.run_episode
    old_planner = evaluator.plan_g1_default_policy
    state = {'goal': tuple(payload['world']['goal']), 'controller':None,
             'overrides':0,'events':[]}
    create = _factory(arm, frozen.config(), state)
    def capture_factory(initial, mode, **options):
        c = create(initial,mode,**options);state['controller']=c;return c
    def routed_factory(initial, model_id, cfg, options, goal):
        state['goal']=tuple(goal)
        return capture_factory(initial, 'periodic' if arm=='periodic_event' else 'age', **options)
    frozen.factory = routed_factory
    base.run_episode = _install_feedback(arm,old_episode,state)
    evaluator.plan_g1_default_policy = _install_gate_planner(arm,old_planner,state,frozen.config())
    # RDAO footprint is the exact historical single-hook ablation.
    legacy_visibility = None
    if arm == 'rdao_v1_footprint':
        import spatial_memory.rdao as rdao_module
        from evaluate_rdao_footprint_visibility_online import footprint_predictor
        legacy_visibility = rdao_module.predicted_cell_visibility
        rdao_module.predicted_cell_visibility = footprint_predictor
    try:
        if condition == 'original':
            result = engine.run_original_case(payload,schedule,arm)
        elif condition == 'high_frequency':
            result = engine.run_dynamic_case(payload,schedule,arm)
        else:
            raise ValueError(f'Unknown environment condition: {condition}')
    finally:
        if legacy_visibility is not None:
            import spatial_memory.rdao as rdao_module
            rdao_module.predicted_cell_visibility = legacy_visibility
        evaluator.plan_g1_default_policy = old_planner
        base.run_episode = old_episode
        frozen.factory = old_factory
    row, replay, diagnostics = result
    row['method'] = arm
    row['comprehensive_arm'] = arm
    row['environment_condition'] = condition
    diagnostics['comprehensive_arm'] = arm
    if arm in ('rdao_v1_gate_first','rdao_v1_gate_every'):
        diagnostics['online_gate_events'] = state['events']
        diagnostics['online_gate_overrides'] = state['overrides']
    controller=state['controller']
    if controller is None or controller.used != row['observation_count'] or controller.used > 20:
        raise RuntimeError('Controller and paid-observation accounting mismatch')
    if row['g1_unselected_action_shield_queries'] != 0 or not row['g1_shield_query_count_valid']:
        raise RuntimeError('Selected-action shield accounting invariant failed')
    return row,replay,diagnostics
