"""Paired descriptive B/C engineering screen. Never opens reserved cohorts.

Reproduce Periodic/Age metrics AND traces first for every admitted FIT key.
Then run B+Age, C+ternary, B+C through unchanged G1 sensing/safety callbacks.
No parameter search. Exclusive output directory; per-episode checkpoints.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict
import gzip
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'scripts')]
import numpy as np
import evaluate_event_observation_fit72 as reference
from spatial_memory.evi import PersistenceEVIController, EVIParameters
from spatial_memory.persistence import calibration_summary, PersistenceParameters
from spatial_memory.scheduling import ObservationController

ARMS = {'b_age': (True, False), 'c_ternary': (False, True), 'bc': (True, True)}


def source_metadata():
    names = sorted(set(reference.base.SOURCE_FILES) | {
        'scripts/evaluate_persistence_evi_fit72.py',
        'src/spatial_memory/evi.py', 'src/spatial_memory/persistence.py',
        'src/spatial_memory/scheduling.py', 'src/spatial_memory/memory.py',
        'docs/phase2_persistence_evi_protocol.md'})
    return {
        'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'branch': subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT, text=True).strip(),
        'dirty_status': subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True),
        'tracked_diff_sha256': hashlib.sha256(subprocess.check_output(['git', 'diff', 'HEAD'], cwd=ROOT)).hexdigest(),
        'source_sha256': {n: reference._sha(ROOT/n) for n in names},
        'python': platform.python_version(),
        'dependencies': {n: importlib.metadata.version(n) for n in ('numpy', 'mujoco', 'pytest')},
        'persistence_parameters': asdict(PersistenceParameters()),
        'evi_parameters': asdict(EVIParameters()),
    }


def run_arm(payload, schedule, arm, config):
    """Scoped factory replacement only; actual sensor/planner/shield unchanged."""
    base = reference.base
    original = base.run_episode
    context = {}
    records = {'last_write': [], 'age_rate': []}

    def injected(scenario, run_config, method, **kwargs):
        def factory(initial, mode, **options):
            if arm in ARMS:
                b, c = ARMS[arm]
                sensor = {k: config['mujoco_ray_sensor'][k] for k in
                          ('range_m', 'horizontal_fov_deg', 'ray_count')}
                sensor['cell_size'] = config['mujoco_cell_size_m']
                agent = PersistenceEVIController(initial, mode, **options,
                    persistence=b, evi=c, sensor=sensor)
            else:
                agent = ObservationController(initial, mode, **options)
            context['controller'] = agent
            return agent
        previous_callback = kwargs.get('_observation_callback')
        def record(observation, step, position):
            agent = context['controller']
            history = agent.base.agent if arm in ARMS else agent.agent
            grid = history.memory.grid
            known = grid >= 0
            visible = observation >= 0
            last = np.where(known, np.where(grid == 1, .95, .05), .5)
            if hasattr(history, 'last_observed'):
                a, b = history.rates(), np.maximum(0, step-history.last_observed)
                age = .5+np.where(grid == 1, .45, -.45)*np.exp(-2*a*b)
                age[~known] = .5
            else:
                age = last
            for name, probability in [('last_write', last), ('age_rate', age)]:
                records[name].append({'step': step, 'probability': probability[visible].tolist(),
                    'outcome': observation[visible].astype(int).tolist()})
            if previous_callback is not None:
                previous_callback(observation, step, position)
        kwargs['_controller_factory'] = factory
        kwargs['_observation_callback'] = record
        return original(scenario, run_config, method, **kwargs)
    base.run_episode = injected
    try:
        method = arm if arm in ('periodic', 'age') else 'age'
        row, trace = base.run_case(payload, schedule, method,
            json.loads(json.dumps(config)), with_safety=True)
    finally:
        base.run_episode = original
    agent = context['controller']
    diagnostics = {'calibration_comparators_same_scan_cells': {
        k: calibration_summary(v) for k, v in records.items()}}
    if arm in ARMS:
        diagnostics.update(decisions=agent.decisions, observation_log=agent.observation_log,
            scheduler_total_ms=agent.scheduler_decision_total_ns/1e6,
            inference_log=agent.belief.inference_log if agent.belief is not None else [],
            calibration_belief=(calibration_summary(agent.belief.calibration)
                                if agent.belief is not None else None))
        for event in diagnostics['observation_log']:
            step = event['step']
            frames = trace['steps']
            current = next(f for f in frames if f['step'] == step)
            previous = next(f for f in frames if f['step'] == step-1)
            event['executed_action_after_scan'] = current['action']
            event['previous_executed_action'] = previous['action']
            event['temporal_executed_action_changed'] = current['action'] != previous['action']
            event['causal_utility_observed'] = False
        if reference._noninitial_granted_scan_steps(trace) != [r['step'] for r in agent.observation_log]:
            raise RuntimeError('Realized scans differ from controller authorizations')
        if int(row['observation_count']) != 1+len(agent.observation_log):
            raise RuntimeError('Paid cap/initial-scan accounting differs')
    if (not reference._bool(row['g1_shield_query_count_valid']) or
        int(row['g1_unselected_action_shield_queries']) != 0 or
        int(row['observation_count']) > 20):
        raise RuntimeError('Safety or paid sensor budget invariant violated')
    return row, trace, diagnostics


def pair_row(key, method, arm, baseline, candidate, diagnostics):
    # Reuse the established paired primary-metric schema, without changing A.
    temporary = dict(candidate, event_scheduler_total_ms=diagnostics['scheduler_total_ms'],
        event_observation_count=0, ordinary_observation_count=int(candidate['observation_count'])-1,
        feedback_blocked_count=int(candidate['g1_footprint_blocked_attempts']),
        feedback_no_route_count=0)
    result = reference.make_pair_row(key, method, baseline, temporary)
    result['candidate_method'] = arm
    result['candidate_blocked_attempts'] = int(candidate['g1_footprint_blocked_attempts'])
    result['reference_blocked_attempts'] = int(baseline['g1_footprint_blocked_attempts'])
    return result


def summarize_pairs(rows):
    result = reference.aggregate_pairs(rows)
    common = [r for r in rows if r['reference_success'] and r['candidate_success']]
    result['paired_common_success_means'] = {
        side+'_'+metric: (sum(float(r[side+'_'+metric]) for r in common)/len(common)
                         if common else None)
        for side in ('reference', 'candidate') for metric in ('steps_h80', 'distance_m')}
    # Keep both schedules together. Descriptive cluster means, no iid-schedule CI.
    result['maze_level_deltas'] = []
    for world in sorted({r['world_identity'] for r in rows}):
        cluster = [r for r in rows if r['world_identity'] == world]
        result['maze_level_deltas'].append({'world_identity': world,
            'correlated_schedules': len(cluster),
            **{metric: sum(float(r['candidate_'+metric])-float(r['reference_'+metric])
                           for r in cluster)/len(cluster)
               for metric in ('success', 'observations', 'steps_h80', 'distance_m')}})
    result['candidate_blocked_attempts'] = sum(r['candidate_blocked_attempts'] for r in rows)
    result['reference_blocked_attempts'] = sum(r['reference_blocked_attempts'] for r in rows)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--max-cases', type=int)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.max_cases is not None and args.max_cases < 1:
        parser.error('--max-cases must be positive')
    metadata = source_metadata()
    if metadata['branch'] != 'phase2/mujoco-proxy-pilot':
        raise RuntimeError('Wrong research branch')
    _, _, provenance, _ = reference.base.load_baseline()
    config = reference.base.frozen_config(provenance)
    baseline_rows = reference._load_csv(reference.BASE/'episodes.csv')
    index = {(r['world_identity'], int(r['schedule']), r['method'], int(r['seed'])): r
             for r in baseline_rows}
    with gzip.open(reference.BASE/'episode_traces.jsonl.gz', 'rt') as stream:
        saved = {tuple(r['key']): r for r in map(json.loads, stream)}
    worlds = {w['identity']: w for w in reference.navigation.admitted_worlds()}
    keys = sorted({(r['world_identity'], int(r['schedule']), int(r['seed']))
                   for r in baseline_rows if r['method'] == 'age'})
    if len(worlds) != 36 or len(keys) != 72 or len(index) != 288 or len(saved) != 288:
        raise RuntimeError('Incomplete frozen FIT population/evidence')
    protected = {str(p.relative_to(ROOT)): reference._sha(p) for p in reference.PROTECTED}
    prefix = reference.navigation.verify_preserved_prefix()
    args.output.mkdir(parents=True, exist_ok=False)
    metadata.update(config=config, protected_sha256=protected, preserved_prefix=prefix,
                    status='DESCRIPTIVE_FIT_ONLY', independent_validation=False)
    reference.base.write_json(args.output/'provenance.json', metadata)
    pairs = []
    if args.max_cases is not None:
        keys = keys[:args.max_cases]
    for number, key in enumerate(keys, 1):
        payload = worlds[key[0]]
        references = {}
        for method in ('periodic', 'age'):
            row, trace, diagnostic = run_arm(payload, key[1], method, config)
            refkey = (key[0], key[1], method, key[2])
            if reference.rdao_evaluator._signature(row) != reference.rdao_evaluator._signature(index[refkey]):
                raise RuntimeError(f'Frozen {method} baseline metrics failed: {key}')
            reference._compare_trace(saved[refkey], reference.base._jsonable_row(trace))
            references[method] = row
            save_episode(args.output, number, method, row, trace, diagnostic)
        for arm in ARMS:
            row, trace, diagnostic = run_arm(payload, key[1], arm, config)
            save_episode(args.output, number, arm, row, trace, diagnostic)
            for method in ('periodic', 'age'):
                pairs.append(pair_row(key, method, arm, references[method], row, diagnostic))
        reference._write_csv(args.output/'pairs.csv', pairs)
        print(f'Completed {number}/{len(keys)}: {key[:2]} (5 arms)', flush=True)
    if (reference.navigation.verify_preserved_prefix() != prefix or
        protected != {str(p.relative_to(ROOT)): reference._sha(p) for p in reference.PROTECTED}):
        raise RuntimeError('Protected historical evidence changed')
    summary = {'status': 'COMPLETED_DESCRIPTIVE_FIT_NOT_VALIDATION',
        'episodes_per_arm': len(keys), 'maze_layouts': len({k[0] for k in keys}),
        'baseline_metrics_and_traces_reproduced': True,
        'paired_comparisons': {arm+'_vs_'+method: summarize_pairs(
            [r for r in pairs if r['candidate_method'] == arm and r['reference_method'] == method])
            for arm in ARMS for method in ('periodic', 'age')},
        'unavailable_metrics': ['evaluator-labelled false persistent occupancy',
            'missed persistent geometry changes', 'causal realized EVI'],
        'correlation': 'Two schedules of each maze are correlated; no independent-test inference.',
        'protected_evidence_unchanged': True}
    reference.base.write_json(args.output/'summary.json', summary)
    files = sorted(p for p in args.output.iterdir() if p.is_file())
    reference.base.write_json(args.output/'artifact_manifest.json', [
        {'path': p.name, 'bytes': p.stat().st_size, 'sha256': reference._sha(p)} for p in files])
    print(json.dumps(summary, indent=2))


def save_episode(output, number, arm, row, trace, diagnostic):
    with gzip.open(output/f'episode_{number:03}_{arm}.json.gz', 'xt') as stream:
        json.dump(reference.base._jsonable_row({'row': row, 'trace': trace, 'diagnostics': diagnostic}),
                  stream, sort_keys=True, allow_nan=False)


if __name__ == '__main__':
    main()
