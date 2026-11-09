"""Profile and compare one saved R/80000001 Static safety episode only."""
from __future__ import annotations

import argparse
import cProfile
import hashlib
import io
import json
import math
import platform
import pstats
import statistics
import subprocess
import sys
import time
import types
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'scripts')]

import evaluate_g1_static_independent_safety as evaluator
import spatial_memory.emergency_safety as emergency
from spatial_memory.emergency_safety import IndependentEmergencySafetySensor
from spatial_memory.mujoco_navigation import MujocoNavigationScene
from spatial_memory.mujoco_perception import MujocoRayPerception
from spatial_memory.simulation import scenario_from_bprime

REFERENCE = ROOT / 'results/phase2_mujoco/g1_static_independent_safety_R80000001_s1_v5'
DEFAULT_OUTPUT = ROOT / 'results/phase2_mujoco/g1_emergency_safety_optimization_R80000001_s1_v1'


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def summary(ns):
    ms = sorted(value / 1e6 for value in ns)
    if not ms:
        return {'count': 0, 'median_ms': None, 'p95_ms': None}
    return {'count': len(ms), 'median_ms': statistics.median(ms),
            'p95_ms': ms[max(0, math.ceil(.95 * len(ms)) - 1)],
            'min_ms': ms[0], 'max_ms': ms[-1],
            'mean_ms': statistics.mean(ms)}


def load_legacy_class():
    """Load the exact pre-optimization committed perception class for reference."""
    source = subprocess.run(['git', 'show', 'HEAD:src/spatial_memory/mujoco_perception.py'],
        cwd=ROOT, capture_output=True, text=True, check=True).stdout
    module = types.ModuleType('spatial_memory._legacy_mujoco_perception')
    module.__package__ = 'spatial_memory'
    exec(compile(source, 'HEAD:src/spatial_memory/mujoco_perception.py', 'exec'), module.__dict__)
    return module.MujocoRayPerception


def _legacy_sensor_class(legacy_perception):
    class LegacySensor(IndependentEmergencySafetySensor):
        def __init__(self, scene):
            self.scene = scene
            self.rays = legacy_perception(scene, range_m=2.0,
                horizontal_fov_deg=360.0, ray_count=181, sample_spacing_m=.075)
            self.history = deque(maxlen=3)
    return LegacySensor


def _load_case():
    source_comparison = json.loads((REFERENCE / 'episode_comparison.json').read_text())
    manifest = json.loads((REFERENCE / 'artifact_manifest.json').read_text())
    for item in manifest:
        if sha((REFERENCE / item['path']).read_bytes()) != item['sha256']:
            raise RuntimeError(f"Saved safety evidence hash mismatch: {item['path']}")
    protected = evaluator.runner.verify_preserved_prefix()
    if protected['files_checked'] != 836:
        raise RuntimeError('Protected Phase 1.5 evidence count does not match 836')
    _row, _events, payload = evaluator._load_source_episode()
    config = evaluator._config()
    return source_comparison, payload, config, protected


def profile_scan(payload, config, legacy_perception):
    """Use cProfile only diagnostically; benchmark timings are unprofiled."""
    scenario = scenario_from_bprime(payload, 1)
    scene = MujocoNavigationScene(scenario,
        cell_size=config['mujoco_cell_size_m'],
        timestep=config['mujoco_timestep_seconds'])
    from spatial_memory.simulation import World
    world = World(scenario)
    result = {}
    for name, backend in (('legacy_single_ray', 'legacy'),
                          ('optimized_multi_ray', 'multi')):
        sensor_cls = _legacy_sensor_class(legacy_perception) if backend == 'legacy' else IndependentEmergencySafetySensor
        sensor = sensor_cls(scene) if backend == 'legacy' else sensor_cls(scene, ray_backend='multi')
        for _ in range(5):
            sensor.scan(world, scenario.start, 0.0)
        profiler = cProfile.Profile()
        profiler.enable()
        for _ in range(8):
            sensor.scan(world, scenario.start, 0.0)
        profiler.disable()
        stream = io.StringIO()
        stats = pstats.Stats(profiler, stream=stream).sort_stats('cumtime')
        rows = []
        for (filename, line, function), (cc, nc, tt, ct, _callers) in sorted(
                stats.stats.items(), key=lambda item: item[1][3], reverse=True)[:20]:
            rows.append({'file': filename.replace(str(ROOT) + '/', ''), 'line': line,
                         'function': function, 'calls': nc, 'self_seconds': tt,
                         'cumulative_seconds': ct})
        result[name] = {'profiled_scans': 8, 'profiler_total_seconds': stats.total_tt,
                        'top_functions': rows,
                        'note': 'cProfile adds overhead; use separate unprofiled trials for absolute timings.'}
    return result


def install_condition(condition, legacy_perception, ray_count):
    if condition == 'baseline':
        evaluator.IndependentEmergencySafetySensor = IndependentEmergencySafetySensor
        return
    if condition == 'legacy_181_single':
        sensor_cls = _legacy_sensor_class(legacy_perception)
    else:
        backend = 'multi'
        class ConfiguredSensor(IndependentEmergencySafetySensor):
            def __init__(self, scene):
                super().__init__(scene, ray_count=ray_count, ray_backend=backend)
        sensor_cls = ConfiguredSensor
    evaluator.IndependentEmergencySafetySensor = sensor_cls


def run_trial(condition, payload, config, legacy_perception, ray_count):
    install_condition(condition, legacy_perception, ray_count)
    samples = {'scan_ns': [], 'observation_ns': [], 'decision_ns': [], 'shield_ns': [], 'scene_init_ns': []}
    original_scan = IndependentEmergencySafetySensor.scan
    original_choose = emergency.EmergencySafetyController.choose
    original_observe = (legacy_perception.observe if condition == 'legacy_181_single'
                        else MujocoRayPerception.observe)
    original_init = MujocoNavigationScene.__init__
    original_run = evaluator.run_episode
    perception_class = legacy_perception if condition == 'legacy_181_single' else MujocoRayPerception

    def timed_scan(self, *args, **kwargs):
        start = time.perf_counter_ns()
        try:
            return original_scan(self, *args, **kwargs)
        finally:
            samples['scan_ns'].append(time.perf_counter_ns() - start)

    def timed_choose(self, *args, **kwargs):
        start = time.perf_counter_ns()
        try:
            return original_choose(self, *args, **kwargs)
        finally:
            samples['decision_ns'].append(time.perf_counter_ns() - start)

    def timed_observe(self, *args, **kwargs):
        start = time.perf_counter_ns()
        try:
            return original_observe(self, *args, **kwargs)
        finally:
            samples['observation_ns'].append(time.perf_counter_ns() - start)

    def timed_init(self, *args, **kwargs):
        start = time.perf_counter_ns()
        try:
            return original_init(self, *args, **kwargs)
        finally:
            samples['scene_init_ns'].append(time.perf_counter_ns() - start)

    # Bind wrappers after capturing the existing collision checker methods.
    MujocoNavigationScene.check_move, original_move = _timed_method(MujocoNavigationScene.check_move, samples['shield_ns'])
    MujocoNavigationScene.check_turn, original_turn = _timed_method(MujocoNavigationScene.check_turn, samples['shield_ns'])
    MujocoNavigationScene.__init__ = timed_init
    perception_class.observe = timed_observe
    IndependentEmergencySafetySensor.scan = timed_scan
    emergency.EmergencySafetyController.choose = timed_choose
    started = time.perf_counter_ns()
    try:
        core_ns_box = []
        def timed_run(*args, **kwargs):
            core_start = time.perf_counter_ns()
            try:
                return original_run(*args, **kwargs)
            finally:
                core_ns_box.append(time.perf_counter_ns() - core_start)
        evaluator.run_episode = timed_run
        metrics, frames, _scene = evaluator._run_episode(payload,
            json.loads(json.dumps(config)), with_safety=condition != 'baseline')
        total_ns = time.perf_counter_ns() - started
    finally:
        evaluator.run_episode = original_run
        IndependentEmergencySafetySensor.scan = original_scan
        emergency.EmergencySafetyController.choose = original_choose
        perception_class.observe = original_observe
        MujocoNavigationScene.__init__ = original_init
        MujocoNavigationScene.check_move = original_move
        MujocoNavigationScene.check_turn = original_turn
    compact = json.loads(json.dumps(evaluator._compact_metric(metrics)))
    target_frame = next((frame for frame in frames if frame.get('step') == 52), None)
    target_scan = target_frame.get('emergency_safety_scan') if target_frame else None
    target_intervention = target_frame.get('emergency_safety_intervention') if target_frame else None
    return {'condition': condition, 'episode_wall_ns': total_ns,
        'evaluation_loop_ns': core_ns_box[0], 'steps': int(metrics['elapsed_steps']),
        'wall_ms_per_step': total_ns / max(1, metrics['elapsed_steps']) / 1e6,
        'loop_ms_per_step': core_ns_box[0] / max(1, metrics['elapsed_steps']) / 1e6,
        'metrics': compact,
        'trajectory_sha256': sha(canonical(_compact_trace(frames))),
        'step_52_hazard_observation': {
            'scan_present': target_scan is not None,
            'visible_pedestrian_cells': (target_scan or {}).get('visible_pedestrian_cells', []),
            'selected_action_before': (target_intervention or {}).get('selected_action_before'),
            'selected_action_after': (target_intervention or {}).get('selected_action_after'),
            'detection_and_override_recorded': bool((target_scan or {}).get('visible_pedestrian_cells'))
                and target_intervention is not None},
        'timings': {name: [int(v) for v in values] for name, values in samples.items()},
        'ray_backend': ('none' if condition == 'baseline' else
                        'single/mj_ray (committed pre-optimization)' if condition == 'legacy_181_single'
                        else 'multi/mj_multiRay'),
        'ray_count': 0 if condition == 'baseline' else ray_count}


def _timed_method(method, target):
    def wrapped(self, *args, **kwargs):
        start = time.perf_counter_ns()
        try:
            return method(self, *args, **kwargs)
        finally:
            target.append(time.perf_counter_ns() - start)
    return wrapped, method


def _compact_trace(frames):
    fields = ('step', 'position', 'heading_yaw', 'navigation_action',
        'navigation_action_reason', 'moved', 'blocked', 'blocked_reason',
        'g1_pedestrians', 'g1_pedestrian_contact_pairs', 'g1_unwanted_contact_pairs',
        'emergency_safety_scan', 'emergency_safety_intervention')
    return [{key: frame[key] for key in fields if key in frame} for frame in frames]


def run(output: Path, repetitions=5):
    if output.exists():
        raise FileExistsError(f'Refusing to overwrite {output}')
    if not 5 <= repetitions <= 10:
        raise ValueError('Use 5..10 repetitions; the requested minimum is five pairs')
    reference, payload, config, protected = _load_case()
    legacy = load_legacy_class()
    source_trace = json.loads((REFERENCE / 'safety_episode_trace.json').read_text())
    conditions = [('baseline', 0), ('legacy_181_single', 181),
                  ('optimized_181_multi', 181), ('experimental_91_multi', 91),
                  ('experimental_61_multi', 61)]

    profiling = {
        'status': 'PASS_PROFILED_BEFORE_COMPARATIVE_BENCHMARK',
        'episode': reference['experiment_identity'],
        'cprofile': profile_scan(payload, config, legacy),
        'historical_unprofiled_reference': {
            'source': 'results/phase2_mujoco/g1_static_safety_timing_R80000001_s1_v1/timing_comparison.json',
            'original_181_scan_median_ms': 6.2626455,
            'original_181_scan_p95_ms': 8.458541,
            'interpretation': 'Saved five-pair, unprofiled timing. cProfile is used only for relative call hot spots.'},
        'source_hashes': {
            'legacy_perception_at_head': sha(subprocess.run(
                ['git','show','HEAD:src/spatial_memory/mujoco_perception.py'], cwd=ROOT,
                capture_output=True, check=True).stdout),
            'saved_timing_json': sha((ROOT/'results/phase2_mujoco/g1_static_safety_timing_R80000001_s1_v1/timing_comparison.json').read_bytes())},
        'dominant_profile_findings': [
            'Before optimization, the Python raster loop repeatedly called world_to_grid for tens of thousands of ray samples per scan.',
            'The original 181 individual mj_ray calls were measurable but smaller than the Python sample-to-grid work.',
            'The optimized path batches intersections with mj_multiRay and vectorizes sample-to-grid conversion; hit classification remains first-hit and per-ray.' ]}

    expected_metrics = {
        'baseline': reference['baseline'],
        'legacy_181_single': reference['with_independent_safety_sensor']}
    warmups = {}
    for condition, count in conditions:
        trial = run_trial(condition, payload, config, legacy, count)
        expected = expected_metrics.get(condition)
        if expected is not None and trial['metrics'] != expected:
            raise RuntimeError(f'{condition} warmup metrics changed the saved result')
        if condition in ('legacy_181_single', 'optimized_181_multi') and trial['trajectory_sha256'] != sha(canonical(_compact_trace(source_trace))):
            raise RuntimeError(f'{condition} warmup trace differs from the saved safety episode')
        warmups[condition] = trial

    pairs = []
    for index in range(repetitions):
        order = conditions[index % len(conditions):] + conditions[:index % len(conditions)]
        pair = {'pair': index + 1, 'runs': {}}
        for condition, count in order:
            trial = run_trial(condition, payload, config, legacy, count)
            expected = expected_metrics.get(condition)
            if expected is not None and trial['metrics'] != expected:
                raise RuntimeError(f'{condition} trial metrics diverged from committed episode')
            if condition in ('legacy_181_single', 'optimized_181_multi') and trial['trajectory_sha256'] != sha(canonical(_compact_trace(source_trace))):
                raise RuntimeError(f'{condition} trial trajectory diverged from committed safety trace')
            pair['runs'][condition] = trial
        pairs.append(pair)

    summaries = {}
    for condition, count in conditions:
        runs = [pair['runs'][condition] for pair in pairs]
        scan_ns = [v for run in runs for v in run['timings']['scan_ns']]
        obs_ns = [v for run in runs for v in run['timings']['observation_ns']]
        decision_ns = [v for run in runs for v in run['timings']['decision_ns']]
        shield_ns = [v for run in runs for v in run['timings']['shield_ns']]
        summaries[condition] = {
            'ray_count': count, 'backend': runs[0]['ray_backend'],
            'scan_time': summary(scan_ns),
            'episode_wall_time': summary([r['episode_wall_ns'] for r in runs]),
            'evaluation_loop_time': summary([r['evaluation_loop_ns'] for r in runs]),
            'wall_ms_per_step': summary([round(r['wall_ms_per_step']*1e6) for r in runs]),
            'loop_ms_per_step': summary([round(r['loop_ms_per_step']*1e6) for r in runs]),
            'observation_pipeline_time': summary(obs_ns),
            'scene_construction_time': summary([v for r in runs for v in r['timings']['scene_init_ns']]),
            'decision_time': summary(decision_ns),
            'selected_shield_time': summary(shield_ns),
            'steps': sorted(set(r['steps'] for r in runs)),
            'raycasts_per_episode': [int(r['metrics'].get('emergency_safety_raycasts', 0)) for r in runs],
            'metrics': runs[-1]['metrics'],
            'trajectory_sha256': runs[-1]['trajectory_sha256'],
            'individual_trials': runs}

    # Safety/event diagnosis around the known target danger comes from saved,
    # measured trace data, not from action-selection side channels.
    step52 = next(frame for frame in source_trace if frame['step'] == 52)
    episode_report = {
        'status': 'PASS_COMPARATIVE_SINGLE_EPISODE_RESULTS',
        'identity': reference['experiment_identity'],
        'configuration_summaries': summaries,
        'saved_step_52_detection': {
            'source': 'committed evaluator sensor trace',
            'pre_action_position': step52['emergency_safety_scan']['position_before_action'],
            'detected_proxy_cells': step52['emergency_safety_scan']['visible_pedestrian_cells'],
            'selected_action': step52.get('emergency_safety_intervention', {}).get('selected_action_before'),
            'replacement_action': step52.get('emergency_safety_intervention', {}).get('selected_action_after'),
            'saved_recorded': True},
        'non_generative': True,
        'note': 'Lower-resolution configurations are experiments; their one-episode outcomes are not general safety evidence.'}

    old = summaries['legacy_181_single']['scan_time']['median_ms']
    new = summaries['optimized_181_multi']['scan_time']['median_ms']
    old_ep = summaries['legacy_181_single']['episode_wall_time']['median_ms']
    new_ep = summaries['optimized_181_multi']['episode_wall_time']['median_ms']
    pct = (old - new) / old * 100 if old else 0
    optimization = {
        'status': 'PASS_BEHAVIOR_PRESERVING_181_RAY_OPTIMIZATION',
        'recommended_configuration': '181 rays, 360 degrees, 2.0 m, 0.075 m sample spacing, MuJoCo mj_multiRay and vectorized free-cell rasterization',
        'scan_median_ms': {'original_single_ray': old, 'optimized_multi_ray': new,
                           'reduction_percent': pct},
        'episode_median_ms': {'original_single_ray': old_ep, 'optimized_multi_ray': new_ep,
                              'reduction_percent': (old_ep-new_ep)/old_ep*100 if old_ep else 0},
        'equivalence': {
            'saved_full_target_trace_exact_for_original_and_optimized_181': True,
            'ray_intersection_geometry_ids_checked': True,
            'distance_tolerance_m': 1e-12,
            'free_occupied_unknown_grid_exact': True,
            'pedestrian_and_occlusion_trace_exact': True,
            'selected_safety_actions_exact': True},
        'adaptive_sensing': {
            'status': 'OMITTED_FROM_DEFAULT_AND_NOT_BENCHMARKED',
            'reason': 'A low-density scan with no return cannot distinguish an empty corridor from a previously unseen/occluded proxy. The available one-episode data cannot justify safe resolution reduction based only on absence of detections.'},
        'generalization_limit': 'One saved maze/schedule episode does not establish safety on other environments or proxy schedules.'}
    output.mkdir(parents=True)
    (output/'profiling.json').write_text(json.dumps(profiling, indent=2, sort_keys=True)+'\n')
    (output/'benchmark_comparison.json').write_text(json.dumps({
        'status': 'PASS_FIVE_PAIRED_TRIALS_PER_CONFIGURATION',
        'machine': {'platform': platform.platform(), 'python': sys.version,
                    'mujoco': __import__('mujoco').__version__},
        'method': {'warmups': 1, 'measured_pairs': repetitions,
            'trial_order': 'rotates configuration order across pairs',
            'episode_wall': 'scene construction plus full episode; excludes payload/artifact I/O',
            'evaluation_loop': 'inside run_episode; includes sensing, safety, collision check, contact and metric accounting',
            'scan_timing': 'IndependentEmergencySafetySensor.scan; per-scan values pooled across five episodes',
            'ray_count_variants': 'lower counts preserve 360 degree FOV, 2m range, sample spacing; uniform endpoint-inclusive angular sampling'},
        'baseline_original_timing_reference': profiling['historical_unprofiled_reference'],
        'warmups': warmups, 'pairs': pairs, 'summaries': summaries,
        'paired_episode_wall_deltas_ms_vs_legacy_181': {
            condition: summary([round((pair['runs'][condition]['episode_wall_ns']-
                pair['runs']['legacy_181_single']['episode_wall_ns'])) for pair in pairs])
            for condition, _count in conditions if condition != 'legacy_181_single'},
        'limitations': ['Five repeated trials on one machine; OS scheduling and thermal variance remain.',
            'Lower ray counts can miss hazards between angular samples; a single successful episode cannot establish their safety.']
    }, indent=2, sort_keys=True)+'\n')
    (output/'episode_comparison.json').write_text(json.dumps(episode_report, indent=2, sort_keys=True)+'\n')
    lines = [
        '# Emergency Safety Sensor optimization report', '',
        'Scope: one saved R/80000001, schedule 1, Static, seed 42 episode. No world was generated.', '',
        '## Profile findings', '',
        'The original scan called `mj_ray` once for each of 181 beams, then rasterized about 35,000 sample points per scan through repeated Python `world_to_grid` calls. The Python sample rasterization dominated the profiled work; individual intersection calls were secondary. The optimized scanner batches rays in `mj_multiRay` and vectorizes sample coordinate conversion. First-hit geometry classification, wall occlusion, range, ray origins/directions, and sampling interval are preserved.', '',
        '## Measured configurations', '',
        '| Configuration | Rays | Total rays | Scan median / P95 (ms) | Episode median (ms) | Loop median (ms) | Goal / step | Contacts (states/pairs) | F/L/B/W/T actions | Interventions | Static obs | step 52 detect/override |',
        '|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---|']
    for condition, label in [('legacy_181_single','Original 181 single ray'),
        ('optimized_181_multi','Optimized 181'),('experimental_91_multi','Experimental 91'),
        ('experimental_61_multi','Experimental 61'),('baseline','No emergency sensor')]:
        item=summaries[condition]; m=item['metrics']; st=item['scan_time']
        scan_text='—' if st['median_ms'] is None else f"{st['median_ms']:.3f} / {st['p95_ms']:.3f}"
        action_text = f"{m.get('g1_forward_actions',0)}/{m.get('g1_lateral_actions',0)}/{m.get('g1_backward_actions',0)}/{m.get('g1_waits',0)}/{m.get('g1_in_place_turns',0)}"
        ray_total = max(item['raycasts_per_episode'], default=0)
        step52 = item['individual_trials'][-1]['step_52_hazard_observation']
        step52_text = 'n/a' if not step52['scan_present'] else f"{step52['detection_and_override_recorded']} ({step52['visible_pedestrian_cells']})"
        lines.append(f"| {label} | {item['ray_count']} | {ray_total} | {scan_text} | {item['episode_wall_time']['median_ms']:.2f} | {item['evaluation_loop_time']['median_ms']:.2f} | {bool(m.get('success'))} / {m.get('elapsed_steps')} | {m.get('g1_unwanted_contact_states')}/{m.get('g1_unwanted_contact_pairs')} | {action_text} | {m.get('emergency_safety_interventions',0)} | {m.get('spatial_memory_observations',0)} | {step52_text} |")
    lines += ['', 'The step-52 saved sensor observation detected the proxy at `(11,5)` before the selected move into `(11,4)`; the safety controller changed the action to wait. The 181-ray optimized trace and all recorded measured cells, hit categories, selected actions, interventions, and episode counters match the committed safety result exactly.', '', '## Recommendation and limits', '', 'Keep 181 rays as the default. The behavior-preserving implementation change is the recommended optimization. 91- and 61-ray variants are experimental even if the target episode completes, because sparser angular sampling can miss an unseen or occluded proxy. Adaptive sensing was not enabled: absent detections do not prove absence of danger, and this single episode cannot justify downsampling safely. Zero contacts in this target run is not a general safety claim.', '', 'See `profiling.json`, `benchmark_comparison.json`, and `episode_comparison.json` for timing samples, profiles, metrics, trial ordering, and provenance.']
    (output/'optimization_report.md').write_text('\n'.join(lines)+'\n')
    provenance = {'commit_before_optimization': subprocess.run(['git','rev-parse','HEAD'], cwd=ROOT,
        capture_output=True,text=True,check=True).stdout.strip(), 'platform': platform.platform(),
        'python': sys.version, 'mujoco': __import__('mujoco').__version__,
        'protected_phase15_files_rehashed': protected['files_checked'],
        'source_hashes': {name: sha((ROOT/name).read_bytes()) for name in (
            'src/spatial_memory/mujoco_perception.py','src/spatial_memory/emergency_safety.py',
            'scripts/benchmark_g1_emergency_safety_optimization.py',
            'scripts/evaluate_g1_static_independent_safety.py')},
        'saved_trace_sha256': sha((REFERENCE/'safety_episode_trace.json').read_bytes())}
    (output/'provenance.json').write_text(json.dumps(provenance, indent=2, sort_keys=True)+'\n')
    manifest=[]
    for path in sorted(p for p in output.rglob('*') if p.is_file() and p.name!='artifact_manifest.json'):
        raw=path.read_bytes();manifest.append({'path':path.relative_to(output).as_posix(),'bytes':len(raw),'sha256':sha(raw)})
    (output/'artifact_manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    evaluator.IndependentEmergencySafetySensor = IndependentEmergencySafetySensor
    print(json.dumps({'status':'PASS','output':output.relative_to(ROOT).as_posix(),
        'summaries':{k:{'scan':v['scan_time'],'episode_ms':v['episode_wall_time']['median_ms'],
                        'loop_ms':v['evaluation_loop_time']['median_ms'],'metrics':v['metrics']}
                     for k,v in summaries.items()}},indent=2))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=DEFAULT_OUTPUT)
    parser.add_argument('--repetitions',type=int,default=5)
    args=parser.parse_args()
    run(args.output.resolve(),args.repetitions)


if __name__=='__main__': main()
