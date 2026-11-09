"""Paired timing comparison for the one saved R/static safety episode.

No worlds are generated. The saved R/80000001, schedule 1, Static episode is
replayed repeatedly to estimate timing variability; no other episode runs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import statistics
import subprocess
import sys
from pathlib import Path
from time import perf_counter_ns

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))

import evaluate_g1_static_independent_safety as episode_eval
from spatial_memory.emergency_safety import (EmergencySafetyController,
    IndependentEmergencySafetySensor)
from spatial_memory.mujoco_navigation import MujocoNavigationScene
from spatial_memory.mujoco_perception import MujocoRayPerception


DEFAULT_OUTPUT = ROOT / 'results/phase2_mujoco/g1_static_safety_timing_R80000001_s1_v1'
REFERENCE = ROOT / 'results/phase2_mujoco/g1_static_independent_safety_R80000001_s1_v5'


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      allow_nan=False).encode()


def _summary(values_ns):
    values_ms = [v / 1_000_000 for v in values_ns]
    if not values_ms:
        return {'count': 0, 'total_ms': 0.0, 'mean_ms': 0.0, 'median_ms': 0.0,
                'p95_ms': 0.0, 'min_ms': 0.0, 'max_ms': 0.0}
    ordered = sorted(values_ms)
    p95 = ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)]
    return {'count': len(values_ms), 'total_ms': sum(values_ms),
            'mean_ms': statistics.mean(values_ms),
            'median_ms': statistics.median(values_ms), 'p95_ms': p95,
            'min_ms': min(values_ms), 'max_ms': max(values_ms)}


def _trace_digest(frames):
    fields = ('step', 'position', 'heading_yaw', 'navigation_action',
        'navigation_action_reason', 'moved', 'blocked', 'blocked_reason',
        'g1_pedestrians', 'g1_pedestrian_contact_pairs',
        'g1_unwanted_contact_pairs', 'emergency_safety_scan',
        'emergency_safety_intervention')
    trace = [{key: frame[key] for key in fields if key in frame} for frame in frames]
    return _sha(_canonical(trace))


def _measure_one(condition, payload, config, wrappers):
    wrappers['current']['samples'] = {}
    start = perf_counter_ns()
    metrics, frames, _scene = episode_eval._run_episode(
        payload, json.loads(json.dumps(config)), with_safety=(condition == 'safety'))
    total_ns = perf_counter_ns() - start
    samples = wrappers['current']['samples']
    core_ns = samples.get('run_episode_ns', [0])[0]
    compact = json.loads(json.dumps(episode_eval._compact_metric(metrics)))
    return {
        'condition': condition,
        'setup_plus_episode_wall_ns': total_ns,
        'run_episode_core_ns': core_ns,
        'steps': int(metrics['elapsed_steps']),
        'wall_ms_per_step': total_ns / max(1, metrics['elapsed_steps']) / 1_000_000,
        'core_ms_per_step': core_ns / max(1, metrics['elapsed_steps']) / 1_000_000,
        'metrics': compact,
        'trajectory_sha256': _trace_digest(frames),
        'timing_samples_ns': {key: list(values) for key, values in samples.items()
                              if key != 'run_episode_ns'},
    }


def _install_timers():
    current = {'samples': {}}
    originals = []

    def wrap(owner, name, category):
        original = getattr(owner, name)

        def timed(*args, **kwargs):
            started = perf_counter_ns()
            try:
                return original(*args, **kwargs)
            finally:
                current['samples'].setdefault(category, []).append(
                    perf_counter_ns() - started)
        setattr(owner, name, timed)
        originals.append((owner, name, original))

    wrap(IndependentEmergencySafetySensor, 'scan', 'emergency_sensor_scan_ns')
    wrap(EmergencySafetyController, 'choose', 'emergency_controller_ns')

    original_observe = MujocoRayPerception.observe

    def timed_observe(self, *args, **kwargs):
        category = ('emergency_ray_pipeline_ns' if self.horizontal_fov_deg == 360.0
                    else 'spatial_memory_ray_pipeline_ns')
        started = perf_counter_ns()
        try:
            return original_observe(self, *args, **kwargs)
        finally:
            current['samples'].setdefault(category, []).append(perf_counter_ns() - started)
    MujocoRayPerception.observe = timed_observe
    originals.append((MujocoRayPerception, 'observe', original_observe))

    for name in ('check_move', 'check_turn'):
        wrap(MujocoNavigationScene, name, 'selected_action_shield_ns')

    original_run = episode_eval.run_episode

    def timed_run(*args, **kwargs):
        started = perf_counter_ns()
        try:
            return original_run(*args, **kwargs)
        finally:
            current['samples'].setdefault('run_episode_ns', []).append(
                perf_counter_ns() - started)
    episode_eval.run_episode = timed_run
    originals.append((episode_eval, 'run_episode', original_run))
    return {'current': current, 'originals': originals}


def _restore_timers(wrappers):
    for owner, name, original in reversed(wrappers['originals']):
        setattr(owner, name, original)


def run(output: Path, repetitions=5):
    if output.exists():
        raise FileExistsError(f'Refusing to overwrite {output}')
    if repetitions < 3 or repetitions > 15:
        raise ValueError('Use 3..15 measured pairs for bounded timing')
    reference = json.loads((REFERENCE / 'episode_comparison.json').read_text())
    reference_manifest = json.loads((REFERENCE / 'artifact_manifest.json').read_text())
    if any(_sha((REFERENCE / item['path']).read_bytes()) != item['sha256']
           for item in reference_manifest):
        raise RuntimeError('Prior safety result artifact hash mismatch')
    preserved = episode_eval.runner.verify_preserved_prefix()
    if preserved['files_checked'] != 836:
        raise RuntimeError('Protected Phase 1.5 evidence count changed')
    current_source_hashes = {
        name: _sha((episode_eval.SOURCE / name).read_bytes())
        for name in ('episodes.csv', 'action_events.json', 'provenance.json', 'run.lock')}
    if current_source_hashes != reference['source_file_sha256']:
        raise RuntimeError('Saved baseline source files changed since the safety evaluation')
    baseline_expected = reference['baseline']
    safety_expected = reference['with_independent_safety_sensor']
    _row, _events, payload = episode_eval._load_source_episode()
    config = episode_eval._config()
    wrappers = _install_timers()
    warmups = []
    trials = []
    try:
        # Warm both paths once to reduce one-time import/model-load effects.
        for condition, expected in (('baseline', baseline_expected),
                                    ('safety', safety_expected)):
            trial = _measure_one(condition, payload, config, wrappers)
            if trial['metrics'] != expected:
                raise RuntimeError(f'{condition} warmup did not reproduce the committed episode metrics')
            warmups.append({key: trial[key] for key in (
                'condition', 'setup_plus_episode_wall_ns', 'run_episode_core_ns',
                'steps', 'metrics', 'trajectory_sha256')})

        for index in range(repetitions):
            order = ('baseline', 'safety') if index % 2 == 0 else ('safety', 'baseline')
            pair = {'pair': index + 1, 'runs': {}}
            for condition in order:
                trial = _measure_one(condition, payload, config, wrappers)
                expected = baseline_expected if condition == 'baseline' else safety_expected
                if trial['metrics'] != expected:
                    raise RuntimeError(f'{condition} timing trial changed episode outcome')
                samples = trial['timing_samples_ns']
                if len(samples.get('spatial_memory_ray_pipeline_ns', ())) != 1:
                    raise RuntimeError('Expected one spatial-memory sensor observation')
                expected_safety_scans = (0 if condition == 'baseline'
                    else int(expected['emergency_safety_scans']))
                if len(samples.get('emergency_sensor_scan_ns', ())) != expected_safety_scans:
                    raise RuntimeError('Emergency sensor timing count does not match episode scans')
                if len(samples.get('selected_action_shield_ns', ())) != int(
                        expected['g1_actual_collision_shield_queries']):
                    raise RuntimeError('Shield timing count does not match selected action checks')
                if condition == 'safety':
                    expected_trace = json.loads((REFERENCE / 'safety_episode_trace.json').read_text())
                    if trial['trajectory_sha256'] != _sha(_canonical(expected_trace)):
                        raise RuntimeError('Safety timing trial changed the saved deterministic trajectory')
                pair['runs'][condition] = trial
            pair['delta_safety_minus_baseline_ms'] = {
                'setup_plus_episode_wall': (
                    pair['runs']['safety']['setup_plus_episode_wall_ns']
                    - pair['runs']['baseline']['setup_plus_episode_wall_ns']) / 1_000_000,
                'run_episode_core': (
                    pair['runs']['safety']['run_episode_core_ns']
                    - pair['runs']['baseline']['run_episode_core_ns']) / 1_000_000,
                'wall_ms_per_step': (
                    pair['runs']['safety']['wall_ms_per_step']
                    - pair['runs']['baseline']['wall_ms_per_step']),
                'core_ms_per_step': (
                    pair['runs']['safety']['core_ms_per_step']
                    - pair['runs']['baseline']['core_ms_per_step']),
            }
            trials.append(pair)
    finally:
        _restore_timers(wrappers)

    condition_summaries = {}
    for condition in ('baseline', 'safety'):
        runs = [pair['runs'][condition] for pair in trials]
        all_samples = {}
        for run_item in runs:
            for key, values in run_item['timing_samples_ns'].items():
                all_samples.setdefault(key, []).extend(values)
        condition_summaries[condition] = {
            'episode_setup_plus_run': _summary([r['setup_plus_episode_wall_ns'] for r in runs]),
            'run_episode_core': _summary([r['run_episode_core_ns'] for r in runs]),
            'wall_ms_per_step': _summary([int(r['wall_ms_per_step']*1_000_000) for r in runs]),
            'core_ms_per_step': _summary([int(r['core_ms_per_step']*1_000_000) for r in runs]),
            'step_counts': sorted({r['steps'] for r in runs}),
            'instrumented_sections': {key: _summary(values) for key, values in all_samples.items()},
        }
    paired = {}
    for key in ('setup_plus_episode_wall', 'run_episode_core',
                'wall_ms_per_step', 'core_ms_per_step'):
        paired[key] = _summary([
            int(pair['delta_safety_minus_baseline_ms'][key] * 1_000_000)
            for pair in trials])
    base_median_ms = condition_summaries['baseline']['episode_setup_plus_run']['median_ms']
    paired['median_episode_wall_percent_of_baseline'] = (
        100 * paired['setup_plus_episode_wall']['median_ms'] / base_median_ms
        if base_median_ms else None)

    output.mkdir(parents=True)
    source_paths = (
        'scripts/benchmark_g1_static_safety_timing.py',
        'scripts/evaluate_g1_static_independent_safety.py',
        'src/spatial_memory/emergency_safety.py',
        'src/spatial_memory/evaluation.py')
    report = {
        'status': 'PASS_PAIRED_SINGLE_EPISODE_TIMING_COMPARISON',
        'episode': reference['experiment_identity'],
        'source_result_directory': reference['source_full_run'],
        'prior_safety_result_directory': REFERENCE.relative_to(ROOT).as_posix(),
        'protected_phase15_files_rehashed': preserved['files_checked'],
        'measurement_method': {
            'clock': 'time.perf_counter_ns, monotonic high-resolution wall clock',
            'warmup_pairs': 1,
            'measured_paired_repetitions': repetitions,
            'pair_order': 'alternates baseline-first and safety-first to reduce order bias',
            'episode_total': 'wall time around scenario/scene/sensor construction plus run_episode; excludes artifact writing and source file loading',
            'run_episode_core': 'wall time inside the evaluator call, including initial observation, simulated steps, collision checks, contact accounting, and metric calculation',
            'emergency_sensor_scan': 'wall time around one full IndependentEmergencySafetySensor.scan call; includes MuJoCo pose synchronization, forward kinematics, ray traversal, grid rasterization, tracking, and record creation',
            'nested_timing_note': 'ray-pipeline and controller timings are subsets of episode core and are not additive to episode time',
            'instrumentation': 'same wrappers are present for both conditions; all measurements are observational and do not alter actions or observation schedules',
        },
        'condition_summaries': condition_summaries,
        'paired_safety_minus_baseline': paired,
        'warmup_runs': warmups,
        'measured_pairs': trials,
        'trajectory_reproduction': {
            'baseline_metrics_match_prior_report_every_trial': True,
            'safety_metrics_and_trace_match_prior_report_every_trial': True,
        },
        'interpretation_limits': [
            'This is timing for one saved episode on this machine and software state; it is not a general benchmark.',
            'Baseline and safety policies take different actions and have different episode lengths; total wall-time differences combine added sensing with the changed action/step count.',
            'Emergency sensor scan time is the direct added sensor cost; the per-step and end-to-end comparisons are descriptive.',
            'One warmup and alternating five paired measurements reduce but do not eliminate OS scheduling and thermal variability.',
        ],
    }
    (output / 'timing_comparison.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    provenance = {
        'commit': subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT,
            capture_output=True, text=True, check=True).stdout.strip(),
        'platform': platform.platform(),
        'python': sys.version,
        'source_hashes': {path: _sha((ROOT / path).read_bytes()) for path in source_paths},
        'prior_result_hashes': {
            'episode_comparison.json': _sha((REFERENCE / 'episode_comparison.json').read_bytes()),
            'safety_episode_trace.json': _sha((REFERENCE / 'safety_episode_trace.json').read_bytes()),
            'artifact_manifest.json': _sha((REFERENCE / 'artifact_manifest.json').read_bytes()),
        },
    }
    (output / 'provenance.json').write_text(json.dumps(provenance, indent=2, sort_keys=True) + '\n')
    manifest = []
    for path in sorted(item for item in output.rglob('*') if item.is_file()):
        raw = path.read_bytes()
        manifest.append({'path': path.relative_to(output).as_posix(),
                         'bytes': len(raw), 'sha256': _sha(raw)})
    (output / 'artifact_manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--repetitions', type=int, default=5)
    args = parser.parse_args()
    report = run(args.output.resolve(), repetitions=args.repetitions)
    print(json.dumps({'status': report['status'],
        'output': args.output.as_posix(),
        'summaries': report['condition_summaries'],
        'paired_safety_minus_baseline': report['paired_safety_minus_baseline']}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
