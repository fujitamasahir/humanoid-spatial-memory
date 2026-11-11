"""Repeat the matched 288-episode 61-ray evaluation with an 800-step horizon.

The evaluator's policy callbacks are reused unchanged. This script adds local
perf_counter_ns wrappers around observation decisions, Memory.update, and the
forward-facing A* search, then compares the resulting trajectories against the
saved 80-step matrix and the previously rerun 400-step failure cohort.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'scripts')]

import evaluate_phase2_61ray_emergency_safety_full_288 as base
import phase2_mujoco_navigation as nav
import spatial_memory.navigation as navigation
from spatial_memory.memory import Memory
from spatial_memory.scheduling import ObservationController

HORIZON = 800
DEFAULT_OUTPUT = ROOT / 'results/phase2_mujoco/g1_forward_first_61ray_emergency_safety_full_288_h800_timed_v1'
H80 = base.DEFAULT_OUTPUT
H400 = ROOT / 'results/phase2_mujoco/g1_forward_first_61ray_emergency_safety_failed_episodes_h400_v1'
H800_PRIOR = ROOT / 'results/phase2_mujoco/g1_forward_first_61ray_emergency_safety_unreached_h400_h800_v1'
PROFILE: dict[str, list[int]] | None = None


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n')


def _jsonl_gz(path: Path, records) -> None:
    with gzip.open(path, 'wt', encoding='utf-8', newline='\n', compresslevel=6) as stream:
        for item in records:
            stream.write(json.dumps(item, sort_keys=True, allow_nan=False) + '\n')


def _read_gz_jsonl(path: Path) -> dict[tuple, dict]:
    indexed = {}
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        for line_no, line in enumerate(stream, 1):
            record = json.loads(line)
            key = tuple(record['key'])
            if key in indexed:
                raise ValueError(f'Duplicate trace key in {path}:{line_no}: {key}')
            indexed[key] = record
    return indexed


def _artifact_hashes(directory: Path) -> dict[str, str]:
    entries = json.loads((directory / 'artifact_manifest.json').read_text())
    hashes = {}
    for item in entries:
        path = directory / item['path']
        raw = path.read_bytes()
        if len(raw) != item['bytes'] or _sha(raw) != item['sha256']:
            raise ValueError(f'Existing result artifact hash mismatch: {path}')
        hashes[item['path']] = item['sha256']
    return hashes


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding='utf-8') as stream:
        return [json.loads(line) for line in stream if line.strip()]


def _append_fsync(path: Path, value: dict) -> None:
    with path.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(value, sort_keys=True, allow_nan=False) + '\n')
        stream.flush()
        os.fsync(stream.fileno())


def _install_timers():
    """Wrap only the exact methods whose execution time is requested."""
    originals = (ObservationController.decide, Memory.update,
                 navigation.plan_g1_forward_facing)

    def timed(original, field):
        def wrapper(*args, **kwargs):
            start = time.perf_counter_ns()
            try:
                return original(*args, **kwargs)
            finally:
                elapsed = time.perf_counter_ns() - start
                if PROFILE is not None:
                    PROFILE[field].append(elapsed)
        wrapper.__name__ = original.__name__
        wrapper.__doc__ = original.__doc__
        return wrapper

    ObservationController.decide = timed(originals[0], 'observation_decision_ns')
    Memory.update = timed(originals[1], 'map_update_ns')
    navigation.plan_g1_forward_facing = timed(originals[2], 'ordinary_astar_ns')
    return originals


def _restore_timers(originals):
    ObservationController.decide, Memory.update, navigation.plan_g1_forward_facing = originals


def _summary(values_ns: list[int]) -> dict:
    vals = sorted(int(v) for v in values_ns)
    if not vals:
        return {'calls': 0, 'total_ms': 0.0, 'mean_ms': None, 'median_ms': None, 'p95_ms': None}
    def ms(v): return v / 1e6
    return {
        'calls': len(vals), 'total_ms': ms(sum(vals)),
        'mean_ms': ms(statistics.mean(vals)), 'median_ms': ms(statistics.median(vals)),
        'p95_ms': ms(vals[max(0, math.ceil(.95 * len(vals)) - 1)]),
    }


def _prefix_comparison(new_traces: dict, old_traces: dict) -> dict:
    details = []
    mismatches = []
    for key, old in old_traces.items():
        new = new_traces.get(key)
        if new is None:
            mismatches.append({'key': list(key), 'reason': 'missing in 800-step run'})
            continue
        old_steps, new_steps = old['steps'], new['steps']
        match = len(new_steps) >= len(old_steps) and new_steps[:len(old_steps)] == old_steps
        details.append({'key': list(key), 'compared_frames': len(old_steps), 'exact_match': match})
        if not match:
            first = next((i for i, pair in enumerate(zip(old_steps, new_steps)) if pair[0] != pair[1]), None)
            mismatches.append({'key': list(key), 'reason': 'trajectory prefix differs',
                               'first_different_frame_index': first,
                               'old_frame_count': len(old_steps), 'new_frame_count': len(new_steps)})
    return {'source_episode_count': len(old_traces), 'matched_episode_count': sum(x['exact_match'] for x in details),
            'all_exact': len(old_traces) == len(details) and not mismatches,
            'frames_compared': sum(x['compared_frames'] for x in details),
            'episode_details': details, 'mismatches': mismatches}


def _load_rows(path: Path) -> list[dict]:
    with path.open(newline='', encoding='utf-8') as stream:
        return list(csv.DictReader(stream))


def _write_csv(path: Path, rows: list[dict]):
    fields = sorted({key for row in rows for key in row})
    with path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def _run(output: Path, *, resume: bool):
    global PROFILE
    if output.exists() and not resume:
        raise FileExistsError(f'Refusing to overwrite existing output: {output}')
    baseline_hashes = base.file_hashes(H80)
    h400_hashes = _artifact_hashes(H400)
    h800prior_hashes = _artifact_hashes(H800_PRIOR)
    baseline_rows, baseline_index, provenance, _ = base.load_baseline()
    config = base.frozen_config(provenance)
    config['max_steps'] = HORIZON
    worlds = nav.admitted_worlds()
    if len(worlds) != 36:
        raise ValueError('Expected 36 saved admitted worlds; generation is forbidden')
    preserved = nav.verify_preserved_prefix()
    output.mkdir(parents=True, exist_ok=True)
    lock = output / 'run.lock'
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.write(fd, json.dumps({'pid': os.getpid(), 'started': time.time()}).encode())
    os.close(fd)
    records_path = output / 'episode_records.jsonl'
    try:
        if not records_path.exists():
            records_path.touch()
        records = _load_jsonl(records_path)
        indexed = {tuple(r['row']['episode_key']): r for r in records}
        if len(indexed) != len(records):
            raise ValueError('Duplicate episode keys in this run checkpoint')
        expected = [(p, s, m) for p in worlds for s in (0, 1) for m in base.POLICIES]
        expected_keys = {(p['identity'], s, m, base.SEED) for p, s, m in expected}
        if set(indexed) - expected_keys:
            raise ValueError('Unexpected episode key in checkpoint')
        started = time.monotonic()
        timers = _install_timers()
        try:
            print(f'Progress: {len(indexed)}/288 (800-step matched evaluation)', flush=True)
            for number, (payload, schedule, method) in enumerate(expected, 1):
                key = (payload['identity'], schedule, method, base.SEED)
                if key in indexed:
                    continue
                PROFILE = {'observation_decision_ns': [], 'ordinary_astar_ns': [], 'map_update_ns': []}
                row, trace = base.run_case(payload, schedule, method,
                    json.loads(json.dumps(config)), with_safety=True)
                profile = PROFILE
                PROFILE = None
                # Normalize tuples and NumPy scalar values to their on-disk JSON
                # representation before exact comparison with historical traces.
                trace = base._jsonable_row(trace)
                if len(profile['observation_decision_ns']) != int(row['elapsed_steps']):
                    raise RuntimeError(f'Observation decision timer count mismatch for {key}')
                if not profile['ordinary_astar_ns']:
                    raise RuntimeError(f'No ordinary A* search was timed for {key}')
                expected_updates = int(row['observation_count'])
                if len(profile['map_update_ns']) != expected_updates:
                    raise RuntimeError(f'Map update timer count mismatch for {key}: {len(profile["map_update_ns"])} != {expected_updates}')
                # The timed observation closure does not expose the bound ray
                # scanner's last_stats to generic evaluator bookkeeping. The
                # ray count is exact from granted observations x pinned 61 rays.
                memory_rays = int(row['observation_count']) * int(config['mujoco_ray_sensor']['ray_count'])
                row['mujoco_sensor_rays'] = memory_rays
                row['spatial_memory_rays'] = memory_rays
                row.update(
                    observation_decision_total_ms=sum(profile['observation_decision_ns']) / 1e6,
                    observation_decision_calls=len(profile['observation_decision_ns']),
                    ordinary_astar_total_ms=sum(profile['ordinary_astar_ns']) / 1e6,
                    ordinary_astar_calls=len(profile['ordinary_astar_ns']),
                    map_update_total_ms=sum(profile['map_update_ns']) / 1e6,
                    map_update_calls=len(profile['map_update_ns']),
                    map_update_mean_ms=(statistics.mean(profile['map_update_ns']) / 1e6
                                        if profile['map_update_ns'] else 0.0),
                )
                row['episode_key'] = list(key)
                record = {'row': base._jsonable_row(row), 'trace': trace,
                          'timings_ns': profile}
                _append_fsync(records_path, record)
                indexed[key] = record
                if number % 12 == 0 or number == len(expected):
                    elapsed = time.monotonic() - started
                    done = len(indexed)
                    eta = elapsed / done * (288 - done) if done else None
                    print(f'Progress: {done}/288 ({100*done/288:.1f}%) | elapsed {elapsed/60:.1f} min | ETA {eta/60:.1f} min', flush=True)
        finally:
            PROFILE = None
            _restore_timers(timers)

        if set(indexed) != expected_keys:
            raise ValueError('Evaluation did not produce the complete 288-key matrix')
        ordered = [indexed[k] for k in sorted(indexed)]
        rows = [dict(record['row']) for record in ordered]
        traces = [record['trace'] for record in ordered]
        for row in rows:
            if row['emergency_safety_scans'] != row['elapsed_steps']:
                raise RuntimeError(f'Expected one independent safety scan per executed step: {row["episode_key"]}')
            if row['emergency_safety_raycasts'] != 61 * row['emergency_safety_scans']:
                raise RuntimeError(f'Expected 61 safety rays per scan: {row["episode_key"]}')
            if row['spatial_memory_rays'] != 61 * row['observation_count']:
                raise RuntimeError(f'Spatial memory ray accounting mismatch: {row["episode_key"]}')
            if row['g1_unselected_action_shield_queries'] != 0 or not row['g1_shield_query_count_valid']:
                raise RuntimeError(f'Selected-action-only shield check failed: {row["episode_key"]}')
        timing_records = [{'key': record['row']['episode_key'], **record['timings_ns']}
                          for record in ordered]
        old80 = _read_gz_jsonl(H80 / 'episode_traces.jsonl.gz')
        prior400 = _read_gz_jsonl(H400 / 'failed_episode_traces.jsonl.gz')
        compare80 = _prefix_comparison({tuple(t['key']): t for t in traces}, old80)
        compare400 = _prefix_comparison({tuple(t['key']): t for t in traces}, prior400)
        if len(old80) != 288 or not compare80['all_exact']:
            raise RuntimeError('The 800-step run does not exactly reproduce every saved 80-step trace prefix')
        if not compare400['all_exact']:
            raise RuntimeError('The 800-step run does not exactly reproduce the saved 400-step cohort prefixes')

        _write_csv(output / 'episodes.csv', rows)
        _jsonl_gz(output / 'episode_traces.jsonl.gz', traces)
        _jsonl_gz(output / 'phase_timings.jsonl.gz', timing_records)
        _write_json(output / 'trajectory_prefix_comparison.json', {
            'horizon_80': compare80,
            'horizon_400': compare400,
            'interpretation': ('Every one of the 288 episodes exactly matches its saved 80-step trajectory prefix. '
                'The prior 400-step experiment covered only its saved failure cohort; all those saved traces '
                'exactly match the corresponding 800-step prefixes. No previous 400-step trace exists for '
                'the other episodes, so no 288/288 claim is made for horizon 400.')})

        timing_fields = {
            'observation_decision': [v for rec in ordered for v in rec['timings_ns']['observation_decision_ns']],
            'ordinary_astar': [v for rec in ordered for v in rec['timings_ns']['ordinary_astar_ns']],
            'map_update': [v for rec in ordered for v in rec['timings_ns']['map_update_ns']],
            'spatial_memory_sensor': [int(float(r['spatial_memory_total_processing_ms']) * 1e6) for r in rows],
            'independent_safety_sensor': [int(float(r['emergency_safety_total_processing_ms']) * 1e6) for r in rows],
            'selected_action_collision_check': [int(float(r['selected_shield_time_ms']) * 1e6) for r in rows],
            'episode_wall': [int(float(r['episode_wall_time_seconds']) * 1e9) for r in rows],
        }
        old80_summary = json.loads((H80 / 'summary.json').read_text())['overall']
        still_unreached = [{'world_identity': r['world_identity'], 'schedule': r['schedule'],
                            'method': r['method'], 'seed': r['seed'], 'steps': r['elapsed_steps'],
                            'final_position': r['final_position']}
                           for r in rows if not bool(r['success'])]
        summary = {
            'status': 'PASS_COMPLETE_288_EPISODE_MATRIX_H800_TIMED',
            'design': {'worlds': 36, 'schedules': [0, 1], 'policies': list(base.POLICIES),
                       'episodes': 288, 'seed': base.SEED, 'horizon': HORIZON,
                       'grid_scale_m_per_cell': .75, 'world_regeneration': False},
            'outcomes': base._aggregate(rows),
            'comparison_to_horizon_80': {
                'h80_goal_completions': old80_summary['goal_completions'],
                'h800_goal_completions': base._aggregate(rows)['goal_completions'],
                'additional_goal_completions_by_h800': base._aggregate(rows)['goal_completions'] - old80_summary['goal_completions'],
                'h80_unwanted_contact_episodes': old80_summary['episodes_with_unwanted_contact'],
                'h800_unwanted_contact_episodes': base._aggregate(rows)['episodes_with_unwanted_contact']},
            'still_unreached_at_horizon_800': still_unreached,
            'per_policy': {policy: base._aggregate([r for r in rows if r['method'] == policy])
                           for policy in base.POLICIES},
            'timing_phase_totals_and_call_distributions': {name: _summary(vals)
                for name, vals in timing_fields.items()},
            'new_phase_timing_definitions': {
                'observation_decision': 'ObservationController.decide only, including policy scoring/request and budget grant decision.',
                'ordinary_astar': 'plan_g1_forward_facing only; excludes policy wrappers, sensors, and collision shield.',
                'map_update': 'Memory.update only; includes initial observed-map population and each granted observation refresh.'},
            'movement_comparison': {'horizon_80_all_288_exact': compare80['all_exact'],
                'horizon_400_prior_cohort_exact': compare400['all_exact'],
                'horizon_400_cohort_size': compare400['source_episode_count'],
                'horizon_400_full_matrix_comparison_available': compare400['source_episode_count'] == 288},
            'integrity': {'baseline_result_hashes_verified': len(baseline_hashes),
                'h400_result_hashes_verified': len(h400_hashes),
                'prior_h800_result_hashes_verified': len(h800prior_hashes),
                'phase15_preserved_files_verified': preserved,
                'controller_or_policy_code_modified': False,
                'hidden_state_used_for_decision': False,
                'only_selected_action_collision_check': True},
        }
        _write_json(output / 'summary.json', summary)
        report = [
            '# 800-step matched Phase 2 evaluation', '',
            f"- Episodes: **{summary['outcomes']['episodes']}**; goals: **{summary['outcomes']['goal_completions']}**; contact-free goals: **{summary['outcomes']['contact_free_goal_completions']}**.",
            f"- Unwanted-contact episodes: **{summary['outcomes']['episodes_with_unwanted_contact']}**.",
            f"- Compared with the 80-step matrix: **{summary['comparison_to_horizon_80']['additional_goal_completions_by_h800']}** additional goals by step 800.",
            f"- Still unreached at 800: **{len(still_unreached)}** episode(s).",
            f"- Exact 80-step prefix match: **{compare80['matched_episode_count']}/{compare80['source_episode_count']}**.",
            f"- Exact prior 400-step cohort prefix match: **{compare400['matched_episode_count']}/{compare400['source_episode_count']}**.",
            '- The 400-step run covered only its saved failure cohort; the remaining episodes have no prior 400-step trace for direct comparison.',
            '- Added timers measure the observation decision, `plan_g1_forward_facing` A* body, and `Memory.update` separately. Per-call nanoseconds are in `phase_timings.jsonl.gz`.',
            '- Existing sensor, selected-action collision-check, and episode wall-time measurements are retained in `episodes.csv` and summarized in `summary.json`.',
            '- No environment, source trace, experiment condition, controller, policy, or protected Phase 1.5 file was changed.', '',
        ]
        (output / 'report.md').write_text('\n'.join(report), encoding='utf-8')
        (output / 'run_state.json').write_text(json.dumps({'status': 'COMPLETE', 'episodes': 288}) + '\n')
        source_files = [*base.SOURCE_FILES, 'scripts/evaluate_phase2_61ray_emergency_safety_full_288_h800_timed.py']
        _write_json(output / 'provenance.json', {
            'git_commit': os.popen('git rev-parse HEAD').read().strip(),
            'source_hashes': {p: _sha((ROOT / p).read_bytes()) for p in source_files},
            'original_80_result_sha256': _sha((H80/'artifact_manifest.json').read_bytes()),
            'prior_400_result_manifest_sha256': _sha((H400/'artifact_manifest.json').read_bytes()),
            'prior_800_result_manifest_sha256': _sha((H800_PRIOR/'artifact_manifest.json').read_bytes()),
            'python': sys.version, 'platform': platform.platform(), 'architecture': platform.machine(),
            'mujoco_version': __import__('mujoco').__version__,
            'conditions': {'changed_only': 'max_steps: 80 -> 800',
                'sensor_and_navigation_callbacks': 'reused unchanged from the existing 61-ray evaluator',
                'timing_instrumentation': 'three perf_counter_ns wrappers; returns/exceptions forwarded unchanged'},
        })
        _write_json(output / 'experiment_manifest.json', {
            'experiment_name': 'Phase 2 matched 61-ray emergency safety evaluation, 800-step horizon with phase timings',
            'status': summary['status'], 'commit': os.popen('git rev-parse HEAD').read().strip(),
            'baseline_result_dir': H80.relative_to(ROOT).as_posix(),
            'baseline_experiment_manifest_sha256': _sha((H80/'experiment_manifest.json').read_bytes()),
            'baseline_artifacts': baseline_hashes,
            'previous_h400_result_dir': H400.relative_to(ROOT).as_posix(),
            'previous_h400_artifacts': h400_hashes,
            'previous_h800_result_dir': H800_PRIOR.relative_to(ROOT).as_posix(),
            'previous_h800_artifacts': h800prior_hashes,
            'world_identities': [p['identity'] for p in worlds],
            'world_count': 36, 'schedules': [0, 1], 'policies': list(base.POLICIES),
            'seed': base.SEED, 'episode_count': 288, 'max_steps': HORIZON,
            'policy_config': config, 'grid_scale_m_per_cell': .75,
            'world_regeneration': False, 'phase15_fit_files_modified': False,
            'decision_information': 'Only the existing observation memory, permitted ray observations and feedback are passed to decision callbacks; no future proxy trajectory or hidden occupancy is provided.',
            'collision_queries': 'Only the selected non-wait action is checked; unselected action shield query count remains zero.',
            'added_timing_scope': summary['new_phase_timing_definitions'],
            'trace_prefix_validation': {'h80': compare80, 'prior_h400_cohort': compare400},
        })
        # Hash every final output except the manifest itself, after all files are
        # complete, so the manifest can be verified independently.
        manifest = []
        for path in sorted(p for p in output.rglob('*') if p.is_file() and p.name not in {'artifact_manifest.json', 'run.lock'}):
            raw = path.read_bytes()
            manifest.append({'path': path.relative_to(output).as_posix(), 'bytes': len(raw), 'sha256': _sha(raw)})
        _write_json(output / 'artifact_manifest.json', manifest)
        preserved_after = nav.verify_preserved_prefix()
        if preserved_after != preserved:
            raise RuntimeError('Phase 1.5 preserved-file count changed during evaluation')
        # Recheck all previously committed experiment data after running.
        if base.file_hashes(H80) != baseline_hashes or _artifact_hashes(H400) != h400_hashes or _artifact_hashes(H800_PRIOR) != h800prior_hashes:
            raise RuntimeError('A previously saved experiment artifact changed during this task')
        print(json.dumps({'status': summary['status'], 'output': output.relative_to(ROOT).as_posix(),
            'goal_completions': summary['outcomes']['goal_completions'],
            'contact_free_goal_completions': summary['outcomes']['contact_free_goal_completions'],
            'unwanted_contact_episodes': summary['outcomes']['episodes_with_unwanted_contact'],
            'h80_prefix_exact': compare80['matched_episode_count'],
            'h400_prefix_exact': compare400['matched_episode_count'],
            'h400_comparison_count': compare400['source_episode_count']}, indent=2), flush=True)
    finally:
        PROFILE = None
        lock.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    _run(args.output, resume=args.resume)


if __name__ == '__main__':
    main()
