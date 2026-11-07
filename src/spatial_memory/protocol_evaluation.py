"""Evaluator-only instrumentation around the unchanged episode mechanics.

Phase 1.4A exposes smoke/synthetic validation only, not tuning or assessment runs.
"""
from dataclasses import asdict
from time import perf_counter
import numpy as np
from .evaluation import run_episode
from .policy_planning import PlanningMeter
from .scheduling import AdaptiveParameters
from .task_policies import PolicyController, PolicyParameters, precommit_schedule


def feasibility_summary(samples):
    if not samples:
        return dict(samples=0,brier=None,mae=None,bins=[],by_blocker={})
    def stats(items):
        return dict(samples=len(items),brier=float(np.mean([(r['probability']-r['visible'])**2 for r in items])),
                    mae=float(np.mean([abs(r['probability']-r['visible']) for r in items])))
    bins=[]
    for index in range(5):
        items=[r for r in samples if min(4,int(r['probability']*5))==index]
        if items:
            bins.append(dict(bin=index,lower=index/5,upper=(index+1)/5,
                             count=len(items),mean_prediction=float(np.mean([r['probability'] for r in items])),
                             fraction_visible=float(np.mean([r['visible'] for r in items]))))
    return dict(**stats(samples),bins=bins,by_blocker={
        key:stats(items) for key,items in (
            ('unknown',[r for r in samples if r['unknown_blocker']]),
            ('all_known',[r for r in samples if not r['unknown_blocker']])) if items})


def run_protocol_episode(scenario, config, method, seed, *, parameters=None,
                         ablation=None, replicate=0, purpose='smoke'):
    if purpose not in {'smoke','synthetic-regression'} or scenario.split != 'development':
        raise ValueError('Only smoke/synthetic validation authorized; no tuning, assessment or held-out execution')
    if 10000 <= seed < 30000:
        raise ValueError('Reserved tuning/assessment seed namespace')
    return _run_instrumented_episode(scenario,config,method,seed,parameters=parameters,
        ablation=ablation,replicate=replicate,purpose=purpose)


def _run_instrumented_episode(scenario, config, method, seed, *, parameters=None,
                              ablation=None, replicate=0, purpose='smoke'):
    """Shared mechanics; authorized tuning adapter validates its pinned record first."""
    if scenario.split != 'development' or purpose not in {'smoke','synthetic-regression','tuning'}:
        raise ValueError('Assessment and held-out execution remain reserved')
    if config['unknown'] != 'optimistic':
        raise ValueError('Frozen Phase 1.4 uses optimistic unknown handling')
    if any(value != getattr(AdaptiveParameters(),key) for key,value in config.get('adaptive',{}).items()):
        raise ValueError('Historical model parameters are frozen')
    if type(replicate) is not int or not 0 <= replicate < 5:
        raise ValueError('Random replicate must be 0..4')
    cap, horizon = config.get('max_observations'),config['max_steps']
    rng = np.random.default_rng(np.random.SeedSequence([seed,1404,replicate]))
    schedule = precommit_schedule(method,cap,horizon,rng) if method in {'random-quota','quota-periodic'} else ()
    parameters = PolicyParameters(**parameters) if isinstance(parameters,dict) else parameters
    common = PlanningMeter()
    controller = None
    decisions = []
    samples = []
    observations = {}
    def factory(initial, name, *, interval, radius, parameters, max_observations):
        nonlocal controller
        # All arguments below are explicit public inputs. No Scenario/config is stored.
        controller = PolicyController(initial,name,goal=tuple(scenario.goal),radius=radius,
            parameters=policy_parameters,ablation=ablation,schedule=schedule,
            observation_cost=config['observation_cost'],max_observations=max_observations)
        original = controller.decide
        def timed(step,position):
            decision = original(step,position)
            decisions.append(decision)
            return decision
        controller.decide = timed
        return controller
    policy_parameters = parameters
    def observe_callback(observation,step,position):
        observations[step]=observation.tolist()
        # Labels never flow back to a policy. Only actually granted calls are scored.
        for prediction in decisions[-1]['policy_details']['visibility']:
            x,y = prediction['cell']
            samples.append(dict(step=step,**prediction,visible=int(observation[y,x]>=0)))
    begin=perf_counter()
    metrics,frames=run_episode(scenario,config,method,seed,_controller_factory=factory,
                               _planner=common,_observation_callback=observe_callback)
    elapsed=perf_counter()-begin
    for frame,duration in zip(frames,common.durations):
        frame.update(common_planner_calls=1,common_planner_seconds=duration,
                     received_observation=frame['memory'].tolist() if frame['step']==0 else observations.get(frame['step']))
    # Common planner is invoked once at initialization and after each decision.
    # Per-call timing is collected by a dedicated wrapper below, not inferred.
    metrics.update(purpose=purpose,replicate=replicate,ablation=ablation,
        scheduler_seconds=sum(d['scheduler_seconds'] for d in decisions),
        diagnostic_seconds=sum(d['diagnostic_seconds'] for d in decisions),
        scheduler_astar_calls=sum(d['scheduler_astar_calls'] for d in decisions),
        scheduler_astar_seconds=sum(d['scheduler_astar_seconds'] for d in decisions),
        common_planner_calls=common.calls,common_planner_seconds=common.seconds,
        total_astar_calls=common.calls+sum(d['scheduler_astar_calls'] for d in decisions),
        episode_runtime_seconds=elapsed,
        scheduler_latency_median=float(np.median([d['scheduler_seconds'] for d in decisions])) if decisions else None,
        scheduler_latency_p95=float(np.percentile([d['scheduler_seconds'] for d in decisions],95)) if decisions else None,
        feasibility=feasibility_summary(samples),schedule=schedule,
        policy_parameters=asdict(parameters or PolicyParameters()))
    return metrics,frames,samples
