#!/usr/bin/env python3
"""Controlled, resumable timing rerun of the 54 admitted H2 high-frequency arms.

The runner delegates all episode and model behavior to the frozen H2 engines.
Only timing records and semantic parity hashes are written to this new output.
"""
from __future__ import annotations

import argparse
import copy
import csv
import gzip
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import random
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'src')]
import h2_high_frequency_dynamics as engine
import h2_final_common as frozen
import h2_comprehensive_adapters as adapters
from run_h2_comprehensive_benchmark import (  # type: ignore
    HISTORICAL as COMPREHENSIVE_HISTORICAL, load_registry,
    verify_manifests as verify_comprehensive_manifests,
)
from verify_dao_integrity import verify as verify_preservation

OUT = ROOT / 'results/phase2_mujoco/h2_controlled_compute_benchmark_v1'
PRIOR_COMPREHENSIVE = COMPREHENSIVE_HISTORICAL[0]
PRIOR_HF = engine.OUT
PRIOR_INDEX = COMPREHENSIVE_HISTORICAL[0] / 'combined_dataset/replay_index.json'
PROTOCOL = ROOT / 'docs/h2_controlled_compute_benchmark_protocol_v1.md'
SCRIPT = Path(__file__)
REPETITIONS = 5
ORDER_SEED = 2026111501
MICRO_SEED = 2026111502
MATRIX_CASES = 72
MODEL_IDS: tuple[str, ...] = ()


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False)


def write_exclusive(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as f:
        f.write(json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False,
                           allow_nan=False) + '\n')
        f.flush()
        os.fsync(f.fileno())


def _load_gz(path: Path):
    with gzip.open(path, 'rt', encoding='utf-8') as f:
        return json.load(f)


def model_ids() -> tuple[str, ...]:
    engine._extend_frozen_arms()
    values = tuple(engine.ARM_IDS) + tuple(adapters.ADDITIONAL)
    if len(values) != 54 or len(set(values)) != 54:
        raise RuntimeError(f'Expected 54 unique admitted models, got {len(values)}')
    return values


def maps_and_cases():
    maps = engine.source_maps()
    cases = engine._case_order(maps)
    if len(maps) != 36 or len(cases) != 72:
        raise RuntimeError('Saved H2 map/schedule matrix does not match 36 × 2')
    return maps, cases


def historical_index():
    data = json.loads(PRIOR_INDEX.read_text(encoding='utf-8'))
    entries = [e for e in data['entries'] if e['condition'] == 'high_frequency']
    expected = 54 * MATRIX_CASES
    if len(entries) != expected:
        raise RuntimeError(f'Expected {expected} historical high-frequency entries, found {len(entries)}')
    index = {}
    for entry in entries:
        key = (entry['model_id'], entry['world_identity'], int(entry['schedule']))
        if key in index:
            raise RuntimeError(f'Duplicate historical index key: {key}')
        path = ROOT / entry['path']
        if not path.is_file() or sha(path) != entry['sha256']:
            raise RuntimeError(f'Historical replay missing or hash mismatch: {path}')
        index[key] = (path, entry['sha256'])
    if set(x[0] for x in index) != set(model_ids()):
        raise RuntimeError('Historical replay model set differs from admitted model set')
    return index


def _resource_snapshot():
    snapshot = {'at_utc': datetime.now(timezone.utc).isoformat(), 'vm_stat': None,
                'top_processes': None}
    try:
        snapshot['vm_stat'] = subprocess.run(['vm_stat'], text=True, capture_output=True,
            timeout=5, check=True).stdout.strip()
    except Exception as exc:
        snapshot['vm_stat_error'] = repr(exc)
    try:
        lines = subprocess.run(['ps', '-A', '-o', '%cpu=,comm='], text=True,
            capture_output=True, timeout=10, check=True).stdout.splitlines()
        parsed = []
        for line in lines:
            try:
                cpu, command = line.strip().split(None, 1)
                parsed.append((float(cpu), command))
            except (ValueError, TypeError):
                continue
        snapshot['top_processes'] = [
            {'cpu_percent': cpu, 'command': cmd} for cpu, cmd in
            sorted(parsed, reverse=True)[:8]]
    except Exception as exc:
        snapshot['process_snapshot_error'] = repr(exc)
    return snapshot


def _runtime_info():
    packages = {}
    for name in ('numpy', 'mujoco', 'pytest', 'matplotlib', 'pynauty'):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    hardware = None
    try:
        output = subprocess.run(['system_profiler', 'SPHardwareDataType', '-detailLevel', 'mini'],
            text=True, capture_output=True, timeout=30, check=True).stdout
        wanted = ('Model Name:', 'Model Identifier:', 'Chip:', 'Memory:')
        hardware = [line.strip() for line in output.splitlines() if line.strip().startswith(wanted)]
    except Exception as exc:
        hardware = {'error': repr(exc)}
    return {
        'python': sys.version,
        'python_executable': str(Path(sys.executable).resolve()),
        'python_version': platform.python_version(),
        'platform': platform.platform(), 'machine': platform.machine(),
        'hostname': platform.node(), 'logical_cpu_count': os.cpu_count(),
        'hardware_summary': hardware, 'packages': packages,
        'sysctl_hw_memsize_access': 'denied by local execution policy; system_profiler used',
        'cpu_thermal_pressure': 'not directly measurable without privileged macOS tooling',
        'resource_snapshot_start': _resource_snapshot(),
    }


def _timer_pair_overhead(samples: int = 20000) -> dict:
    # Measure the instrumentation primitive itself; no model work is included.
    durations = []
    t0 = time.perf_counter_ns()
    for _ in range(samples):
        a = time.perf_counter_ns()
        b = time.perf_counter_ns()
        durations.append(b - a)
    total = time.perf_counter_ns() - t0
    return {'samples': samples, 'mean_pair_ns': statistics.mean(durations),
            'median_pair_ns': statistics.median(durations),
            'p95_pair_ns': _quantile(durations, .95),
            'p99_pair_ns': _quantile(durations, .99),
            'amortized_loop_ns_per_pair': total / samples}


def prepare():
    if OUT.exists() and any(OUT.iterdir()):
        raise FileExistsError(f'Output already exists; use its bound runner/resume path: {OUT}')
    current = subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT,
                                      text=True).strip()
    if current != 'phase2/mujoco-proxy-pilot':
        raise RuntimeError(f'Unexpected branch: {current}')
    maps, cases = maps_and_cases()
    models = model_ids()
    prior = historical_index()
    registry = load_registry()
    eligible = {r['model_id'] for r in registry if r['authorization_status'] == 'eligible'}
    if set(models) != eligible:
        raise RuntimeError('54 model set does not equal the eligible registry')
    preservation = verify_preservation()
    if preservation.get('status') != 'PASS':
        raise RuntimeError(f'Protected-file integrity check failed: {preservation}')
    manifest_entries = verify_comprehensive_manifests()
    runtime = _runtime_info()
    timer = _timer_pair_overhead()
    source_files = [SCRIPT, PROTOCOL, ROOT/'scripts/h2_final_common.py',
        ROOT/'scripts/h2_high_frequency_dynamics.py', ROOT/'scripts/h2_comprehensive_adapters.py',
        ROOT/'scripts/run_h2_comprehensive_benchmark.py', ROOT/'scripts/evaluate_phase2_61ray_emergency_safety_full_288.py',
        ROOT/'scripts/verify_dao_integrity.py', ROOT/'src/spatial_memory/cadence_age.py',
        ROOT/'src/spatial_memory/evi.py', ROOT/'src/spatial_memory/scheduling.py',
        ROOT/'results/phase2_mujoco/h2_comprehensive_benchmark_v1/protocol/model_registry.json',
        PRIOR_INDEX]
    source_files.extend((ROOT/'src/spatial_memory').rglob('*.py'))
    source_files.extend(ROOT/r['historical_evaluation_script'] for r in registry
                         if r['model_id'] in models)
    source_files.extend(ROOT/r['source_file'] for r in registry if r['model_id'] in models)
    source_files = sorted(set(source_files))
    source_hashes = {p.relative_to(ROOT).as_posix(): sha(p) for p in source_files}
    for r in registry:
        if r['model_id'] in models and source_hashes[r['source_file']] != r['source_sha256']:
            raise RuntimeError(f"Model source hash differs from registry for {r['model_id']}")
    source_commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT,
                                             text=True).strip()
    binding = {
        'protocol': 'h2_controlled_compute_benchmark_v1',
        'status': 'PREREGISTERED_READY_FOR_SMOKE', 'source_commit': source_commit,
        'branch': current, 'source_sha256': source_hashes,
        'protocol_sha256': sha(PROTOCOL),
        'original_h2_binding_sha256': sha(PRIOR_HF/'binding_amendment_3.json'),
        'comprehensive_binding_sha256': sha(COMPREHENSIVE_HISTORICAL[0]/'binding.json'),
        'matrix': {'models': list(models), 'model_count': 54, 'maps': 36,
            'schedules': [0, 1], 'cases_per_repetition': 3888,
            'repetitions': REPETITIONS, 'measured_episodes': 19440,
            'condition': 'existing H2 high-frequency transition engine', 'seed': 42,
            'max_steps': 80, 'observation_budget': 20, 'cell_size_m': .75,
            'workers': 1},
        'randomized_order_seed': ORDER_SEED,
        'microbenchmark_seed': MICRO_SEED,
        'model_timing_scope': 'existing shared H2 wrapper: initialization + core.decide + core.refresh; total is their sum',
        'timing_exclusions': ['sensor acquisition/raycasting', 'emergency safety',
            'navigation planning outside the observation model', 'selected-action collision shield',
            'dynamic transition generation', 'MuJoCo scene updates', 'replay capture and file I/O'],
        'maps': [{'identity': p['identity'], 'sha256': digest} for p, digest in maps],
        'historical_index_entries': len(prior),
        'historical_manifest_entries_verified': manifest_entries,
        'preservation_check': preservation,
        'runtime': runtime, 'timer_probe': timer,
        'disk_available_at_bind_bytes': shutil_disk_free(),
        'historical_timing_machine': json.loads((PRIOR_HF/'binding_amendment_3.json').read_text())['runtime'],
        'interpretation': 'Descriptive development timing benchmark; repeats are paired reruns, not new environments.',
        'created_at_utc': datetime.now(timezone.utc).isoformat(),
    }
    OUT.mkdir(parents=True, exist_ok=False)
    write_exclusive(OUT/'binding.json', binding)
    write_exclusive(OUT/'environment_info.json', runtime)
    write_exclusive(OUT/'historical_index_audit.json', {
        'high_frequency_entries': len(prior), 'verified_hashes': True,
        'source_index_sha256': sha(PRIOR_INDEX), 'models': len(models),
        'maps': len(maps), 'schedules': 2})
    print(f'Prepared immutable binding for {len(models)} models; no episode run.', flush=True)


def shutil_disk_free():
    import shutil
    return shutil.disk_usage(ROOT).free


def validate_binding():
    binding = json.loads((OUT/'binding.json').read_text())
    current = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if binding['source_commit'] != current:
        raise RuntimeError('Committed source differs from benchmark binding')
    for name, expected in binding['source_sha256'].items():
        if sha(ROOT/name) != expected:
            raise RuntimeError(f'Source commitment changed after bind: {name}')
    if sha(PROTOCOL) != binding['protocol_sha256']:
        raise RuntimeError('Protocol hash mismatch')
    maps, _ = maps_and_cases()
    if binding['maps'] != [{'identity': p['identity'], 'sha256': h} for p, h in maps]:
        raise RuntimeError('Saved map identity/hash mismatch')
    verify_preservation()
    return binding


def semantic_projection(row: dict, replay: dict) -> dict:
    ignored_fragments = ('timing', '_ns', '_ms', 'wall', 'duration', 'computation',
                         'runtime', 'elapsed_time', 'cpu_time')
    def strip_timing(value):
        if isinstance(value, dict):
            return {k: strip_timing(v) for k, v in value.items()
                    if not any(fragment in k.lower() for fragment in ignored_fragments)}
        if isinstance(value, list):
            return [strip_timing(v) for v in value]
        return value
    semantic_row = {k: v for k, v in row.items()
        if not any(fragment in k.lower() for fragment in ignored_fragments)}
    # The full per-step trace is committed, including observations, maps, robot
    # pose/actions, pedestrian/object events, shield decisions and contacts.
    semantic_replay = strip_timing({k: v for k, v in replay.items() if k != 'metrics'})
    return {'row': semantic_row, 'replay': semantic_replay}


def semantic_sha(row: dict, replay: dict) -> str:
    return sha_bytes(canonical(semantic_projection(row, replay)).encode('utf-8'))


def historical_path(model: str, identity: str, schedule: int, index: dict):
    try:
        return index[(model, identity, schedule)][0]
    except KeyError as exc:
        raise RuntimeError(f'No historical baseline for {model} {identity} s{schedule}') from exc


def historical_semantic(model: str, identity: str, schedule: int, index: dict) -> tuple[str, dict]:
    path = historical_path(model, identity, schedule, index)
    item = _load_gz(path)
    replay = item['replay']
    row = item.get('row', replay.get('metrics', {}))
    digest = semantic_sha(row, replay)
    return digest, item


def run_one(payload: dict, schedule: int, model: str):
    if model in engine.ARM_IDS:
        return engine.run_dynamic_case(payload, schedule, model)
    return adapters.run_case(payload, schedule, model, 'high_frequency')


def _timing_row(rep: int, order: int, case_index: int, payload: dict,
                schedule: int, model: str, row: dict, diag: dict,
                parity_digest: str, baseline_digest: str, case_wall_ns: int):
    values = diag.get('timing_ns', {})
    required = ('initialization', 'decision', 'update')
    if any(not isinstance(values.get(k), list) for k in required):
        raise RuntimeError(f'Missing common timing arrays for {model}: {values.keys()}')
    init_ns = sum(values['initialization'])
    decision_ns = sum(values['decision'])
    update_ns = sum(values['update'])
    if not values['initialization']:
        raise RuntimeError(f'Missing model initialization timing: {model}')
    total_ns = init_ns + decision_ns + update_ns
    decisions = values['decision']
    return {
        'repetition': rep, 'order_index': order, 'case_index': case_index,
        'map_identity': payload['identity'], 'map_family': payload['mechanism'],
        'schedule': schedule, 'seed': 42, 'model_id': model,
        'success': bool(row['success']), 'goal_step': row.get('goal_step'),
        'paid_observations': int(row['observation_count']),
        'elapsed_steps': int(row['elapsed_steps']),
        'travel_distance_m': float(row.get('travel_distance_m', 0.0)),
        'unwanted_contact_pairs': int(row.get('g1_unwanted_contact_pairs', 0)),
        'emergency_interventions': int(row.get('emergency_interventions', 0)),
        'failure_reason': row.get('failure_reason'),
        'initialization_ns': init_ns, 'decision_ns': decision_ns,
        'memory_update_ns': update_ns, 'total_model_computation_ns': total_ns,
        'decision_calls': len(decisions),
        'decision_mean_ns_per_call': statistics.mean(decisions) if decisions else 0,
        'decision_median_ns_per_call': statistics.median(decisions) if decisions else 0,
        'decision_p95_ns_per_call': _quantile(decisions, .95) if decisions else 0,
        'decision_p99_ns_per_call': _quantile(decisions, .99) if decisions else 0,
        'case_wall_ns': case_wall_ns,
        'parity_sha256': parity_digest, 'baseline_semantic_sha256': baseline_digest,
        'parity_match': parity_digest == baseline_digest,
        '_init_calls_ns': values['initialization'],
        '_decision_calls_ns': decisions,
        '_update_calls_ns': values['update'],
    }


def _load_journal(path: Path, unique_key):
    rows = {}; seen_digests = set()
    if not path.exists():
        return rows
    for line_no, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        envelope = json.loads(line)
        item = envelope['record']
        digest = sha_bytes(canonical(item).encode('utf-8'))
        if digest != envelope['sha256']:
            raise RuntimeError(f'Journal record hash mismatch at {path}:{line_no}')
        key = unique_key(item)
        if key in rows:
            raise RuntimeError(f'Duplicate journal key {key} at line {line_no}')
        rows[key] = item
        seen_digests.add(digest)
    return rows


def _append_journal(path: Path, item: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    envelope = {'record': item, 'sha256': sha_bytes(canonical(item).encode('utf-8'))}
    with path.open('a', encoding='utf-8') as f:
        f.write(canonical(envelope) + '\n')
        f.flush(); os.fsync(f.fileno())


def _save_progress(path: Path, info: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as f:
        f.write(canonical(info) + '\n'); f.flush(); os.fsync(f.fileno())


def _smoke_cases(cases):
    # Prespecified spread: first R, BP and M map, both schedules.
    selected = []
    for family in ('R', 'BP', 'M'):
        found = next((case for case in cases if case[1]['mechanism'] == family), None)
        if found is None:
            raise RuntimeError(f'Missing saved map family {family}')
        idx, payload, _schedule = found
        selected.extend((idx, payload, s) for s in (0, 1))
    return selected


def _warm_up(cases, models, prior):
    path = OUT/'warmup/journal.jsonl'
    completed = _load_journal(path, lambda r: r['model_id'])
    payload = cases[0][1]
    schedule = 0
    for n, model in enumerate(models, 1):
        if model in completed:
            continue
        row, replay, diag = run_one(payload, schedule, model)
        digest = semantic_sha(row, replay)
        baseline, _ = historical_semantic(model, payload['identity'], schedule, prior)
        record = {'model_id': model, 'map_identity': payload['identity'],
                  'schedule': schedule, 'semantic_sha256': digest,
                  'baseline_semantic_sha256': baseline, 'parity_match': digest == baseline,
                  'timing_ns': {k: diag.get('timing_ns', {}).get(k, [])
                                for k in ('initialization', 'decision', 'update')}}
        _append_journal(path, record)
        if n % 6 == 0 or n == len(models):
            print(f'warm-up: {n}/{len(models)} models', flush=True)
    results = _load_journal(path, lambda r: r['model_id'])
    if len(results) != len(models) or not all(r['parity_match'] for r in results.values()):
        raise RuntimeError('Warm-up parity gate failed')


def run_smoke():
    binding = validate_binding()
    maps, all_cases = maps_and_cases()
    cases = _smoke_cases(all_cases)
    models = model_ids(); prior = historical_index()
    root = OUT/'smoke'; root.mkdir(parents=True, exist_ok=True)
    journal = root/'journal.jsonl'
    completed = _load_journal(journal,
        lambda r: (r['case_index'], r['model_id']))
    tasks = [(ci, payload, schedule, model) for ci, payload, schedule in cases
             for model in models]
    random.Random(ORDER_SEED).shuffle(tasks)
    started = time.monotonic()
    _warm_up(all_cases, models, prior)
    for order, (case_index, payload, schedule, model) in enumerate(tasks, 1):
        key = (case_index, model)
        if key in completed:
            continue
        baseline, _ = historical_semantic(model, payload['identity'], schedule, prior)
        t0 = time.perf_counter_ns()
        row, replay, diag = run_one(payload, schedule, model)
        wall = time.perf_counter_ns()-t0
        digest = semantic_sha(row, replay)
        item = _timing_row(0, order, case_index, payload, schedule, model, row,
                           diag, digest, baseline, wall)
        _append_journal(journal, item); completed[key] = item
        if len(completed) % 27 == 0 or len(completed) == len(tasks):
            elapsed = time.monotonic()-started
            eta = elapsed/max(len(completed), 1)*(len(tasks)-len(completed))
            print(f'smoke {len(completed)}/{len(tasks)} ({100*len(completed)/len(tasks):.1f}%); '
                  f'elapsed {elapsed/60:.1f} min; ETA {eta/60:.1f} min', flush=True)
    # Duplicate a fixed eight task subset to check same-process repeatability.
    repeat_path = root/'repeatability.jsonl'
    repeated = _load_journal(repeat_path, lambda r: (r['case_index'], r['model_id']))
    repeat_tasks = tasks[:8]
    for order, (case_index, payload, schedule, model) in enumerate(repeat_tasks, 1):
        key = (case_index, model)
        if key in repeated:
            continue
        row, replay, diag = run_one(payload, schedule, model)
        digest = semantic_sha(row, replay)
        reference = completed[key]['parity_sha256']
        record = {'case_index': case_index, 'model_id': model,
            'first_semantic_sha256': reference, 'repeat_semantic_sha256': digest,
            'repeat_matches': digest == reference}
        _append_journal(repeat_path, record); repeated[key] = record
    if len(completed) != len(tasks) or any(not r['parity_match'] for r in completed.values()):
        raise RuntimeError('Smoke episode semantic parity failed')
    if len(repeated) != len(repeat_tasks) or any(not r['repeat_matches'] for r in repeated.values()):
        raise RuntimeError('Smoke duplicate execution was not reproducible')
    gate = {'status': 'PASS_SMOKE', 'model_count': len(models),
        'selected_map_schedules': len(cases), 'episodes': len(completed),
        'duplicate_replay_checks': len(repeated), 'parity': 'all semantic traces match historical',
        'timer_probe': binding['timer_probe'],
        'wall_seconds': time.monotonic()-started,
        'estimated_full_matrix_seconds': ((time.monotonic()-started) / len(tasks)
            * (54*72*REPETITIONS)),
        'estimated_disk_for_timing_outputs_bytes': int(54*72*REPETITIONS*2200),
        'created_at_utc': datetime.now(timezone.utc).isoformat()}
    write_exclusive(OUT/'smoke_gate.json', gate)
    _emit_csv(root/'episode_timings.csv', completed.values())
    print(json.dumps(gate, indent=2), flush=True)


def _emit_csv(path: Path, records):
    records = list(records)
    fields = [k for k in records[0] if not k.startswith('_')] if records else []
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix+'.tmp')
    with tmp.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fields, lineterminator='\n', extrasaction='ignore')
        w.writeheader()
        for row in records:
            w.writerow({k: row.get(k) for k in fields})
        f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)


def run_repetitions(resume: bool):
    binding = validate_binding()
    gate_path = OUT/'smoke_gate.json'
    if not gate_path.is_file() or json.loads(gate_path.read_text())['status'] != 'PASS_SMOKE':
        raise RuntimeError('Passing smoke gate is required before full benchmark')
    maps, cases = maps_and_cases(); models = model_ids(); prior = historical_index()
    expected = REPETITIONS * len(cases) * len(models)
    journal = OUT/'episode_journal.jsonl'
    if journal.exists() and not resume:
        raise RuntimeError('Timing journal already exists; pass --resume')
    completed = _load_journal(journal,
        lambda r: (r['repetition'], r['case_index'], r['model_id']))
    if len(completed) > expected:
        raise RuntimeError('Timing journal exceeds frozen matrix')
    all_tasks = [(case_index, payload, schedule, model)
                 for case_index, (_mi, payload, schedule) in enumerate(cases, 1)
                 for model in models]
    progress_path = OUT/'runtime_observations.jsonl'
    started = time.monotonic(); start_count = len(completed)
    _save_progress(progress_path, {'event': 'run_start', 'already_committed': start_count,
        'expected_total': expected, 'resource_snapshot': _resource_snapshot(),
        'at_utc': datetime.now(timezone.utc).isoformat()})
    last_emit = started
    for rep in range(1, REPETITIONS+1):
        tasks = all_tasks.copy()
        random.Random(ORDER_SEED+rep).shuffle(tasks)
        for order, (case_index, payload, schedule, model) in enumerate(tasks, 1):
            key = (rep, case_index, model)
            if key in completed:
                continue
            if len(completed) % 108 == 0:
                validate_binding()
            baseline_digest, _ = historical_semantic(model, payload['identity'], schedule, prior)
            t0 = time.perf_counter_ns()
            row, replay, diag = run_one(payload, schedule, model)
            case_wall_ns = time.perf_counter_ns()-t0
            digest = semantic_sha(row, replay)
            item = _timing_row(rep, order, case_index, payload, schedule,
                model, row, diag, digest, baseline_digest, case_wall_ns)
            _append_journal(journal, item)
            completed[key] = item
            if digest != baseline_digest:
                mismatch = {'repetition': rep, 'case_index': case_index,
                    'model_id': model, 'identity': payload['identity'], 'schedule': schedule,
                    'baseline_semantic_sha256': baseline_digest,
                    'new_semantic_sha256': digest,
                    'status': 'FAIL_SEMANTIC_PARITY'}
                _save_progress(OUT/'parity_mismatches.jsonl', mismatch)
                raise RuntimeError(f'Semantic parity mismatch: {mismatch}')
            now = time.monotonic()
            if len(completed) % 54 == 0 or now-last_emit >= 60 or len(completed) == expected:
                elapsed = now-started
                local_done = len(completed)-start_count
                rate = local_done/max(elapsed, 1e-9)
                eta = (expected-len(completed))/max(rate, 1e-9)
                print(f'controlled compute: {len(completed)}/{expected} '
                      f'({100*len(completed)/expected:.1f}%); rep {rep}/{REPETITIONS}; '
                      f'elapsed {elapsed/3600:.2f} h; ETA {eta/3600:.2f} h; '
                      f'repetition parity so far PASS', flush=True)
                if now-last_emit >= 15*60:
                    _save_progress(progress_path, {'event': '15_minute_snapshot',
                        'committed': len(completed), 'expected': expected,
                        'elapsed_seconds': elapsed, 'eta_seconds': eta,
                        'resource_snapshot': _resource_snapshot(),
                        'at_utc': datetime.now(timezone.utc).isoformat()})
                last_emit = now
        _emit_csv(OUT/'episode_timings.csv', completed.values())
        print(f'Completed repetition {rep}/{REPETITIONS}; '
              f'{len(completed)} timing records committed.', flush=True)
    _save_progress(progress_path, {'event': 'run_complete', 'committed': len(completed),
        'expected': expected, 'elapsed_seconds': time.monotonic()-started,
        'resource_snapshot': _resource_snapshot(),
        'at_utc': datetime.now(timezone.utc).isoformat()})
    if len(completed) != expected:
        raise RuntimeError(f'Expected {expected} timing records, got {len(completed)}')
    print('All five repetitions complete; semantic parity passed for every episode.', flush=True)


def _quantile(values, q):
    if not values:
        return 0.0
    ordered = sorted(float(x) for x in values)
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered)-1)*q
    lo = math.floor(pos); hi = math.ceil(pos)
    return ordered[lo] + (ordered[hi]-ordered[lo])*(pos-lo)


def _stats(values):
    vals = [float(v) for v in values]
    if not vals:
        return {'n': 0, 'mean': None, 'median': None, 'std': None,
                'p95': None, 'p99': None}
    return {'n': len(vals), 'mean': statistics.mean(vals),
        'median': statistics.median(vals),
        'std': statistics.stdev(vals) if len(vals) > 1 else 0.0,
        'p95': _quantile(vals, .95), 'p99': _quantile(vals, .99)}


def _read_complete_rows():
    raw = _load_journal(OUT/'episode_journal.jsonl',
        lambda r: (r['repetition'], r['case_index'], r['model_id']))
    return list(raw.values())


def _state_snapshot_interceptor(controller, target_steps, collected, model, identity):
    original = controller.decide
    def capture(step, position):
        if int(step) in target_steps:
            patched = controller.__dict__.pop('decide', None)
            try:
                clone = copy.deepcopy(controller)
            finally:
                if patched is not None:
                    controller.__dict__['decide'] = patched
            # The measured state contains model-owned memory and public context
            # only; controller APIs never receive evaluator occupancy or future events.
            grid = getattr(getattr(controller, 'memory', None), 'grid', None)
            memory_hash = None if grid is None else sha_bytes(grid.tobytes())
            collected[int(step)] = {'model': model, 'map_identity': identity,
                'step': int(step), 'position': tuple(position), 'controller': clone,
                'memory_sha256': memory_hash,
                'paid_observations_used': int(getattr(controller, 'used', 0))}
        return original(step, position)
    controller.decide = capture
    return controller


def _capture_valid_states(model, payload, schedule, target_steps):
    collected = {}
    if model in engine.ARM_IDS:
        old_factory = frozen.factory
        def capturing_factory(initial, arm, cfg, options, goal):
            c = old_factory(initial, arm, cfg, options, goal)
            return _state_snapshot_interceptor(c, target_steps, collected, model, payload['identity'])
        frozen.factory = capturing_factory
        try:
            row, replay, diag = engine.run_dynamic_case(payload, schedule, model)
        finally:
            frozen.factory = old_factory
    else:
        old_adapter_factory = adapters._factory
        def capturing_adapter_factory(arm, config, state):
            create = old_adapter_factory(arm, config, state)
            def create_and_capture(initial, mode, **options):
                c = create(initial, mode, **options)
                return _state_snapshot_interceptor(c, target_steps, collected, model,
                                                   payload['identity'])
            return create_and_capture
        adapters._factory = capturing_adapter_factory
        try:
            row, replay, diag = adapters.run_case(payload, schedule, model, 'high_frequency')
        finally:
            adapters._factory = old_adapter_factory
    if not collected:
        raise RuntimeError(f'No historical replay state was captured for {model} at {target_steps}')
    return collected, row, replay


def _microbench():
    maps, cases = maps_and_cases(); models = model_ids(); prior = historical_index()
    case_by_family = {}
    for family in ('R', 'BP', 'M'):
        candidates = [(idx, payload, schedule) for idx, payload, schedule in cases
                      if payload['mechanism'] == family and schedule == 0]
        case_by_family[family] = candidates
    # Choose each model's longest saved baseline trace per family. Snapshots
    # are early, mid-episode, and late; states follow each model's actual policy.
    candidate_records = []
    for model in models:
        for family in ('R', 'BP', 'M'):
            best = None
            for case_index, payload, schedule in case_by_family[family]:
                baseline_path = historical_path(model, payload['identity'], schedule, prior)
                item = _load_gz(baseline_path)
                length = int(item['row']['elapsed_steps'])
                if best is None or length > best[0]:
                    best = (length, case_index, payload, schedule)
            length, case_index, payload, schedule = best
            targets = [1, max(1, length//2), max(1, length-1)]
            target = targets[('R', 'BP', 'M').index(family)]
            # If a case ended at step 1, the same legitimate state may recur;
            # de-duplicate target step within the episode.
            target = min(target, max(1, length))
            candidate_records.append((model, family, case_index, payload, schedule, target, length))
    path = OUT/'microbenchmark_state_runs.jsonl'
    existing = _load_journal(path, lambda r: (r['model_id'], r['map_family']))
    snapshots = []
    historic_csv = PRIOR_COMPREHENSIVE/'analysis/high_frequency_environment_summary.csv'
    with historic_csv.open(encoding='utf-8') as f:
        historical_summary = {r['model_id']: r for r in csv.DictReader(f)
                              if r['condition'] == 'high_frequency'}
    for i, (model, family, case_index, payload, schedule, target, length) in enumerate(candidate_records, 1):
        key = (model, family)
        saved = existing.get(key)
        if saved is None:
            captured, row, replay = _capture_valid_states(model, payload, schedule, {target})
            if target not in captured:
                # A terminal outcome may stop before a target on an inconsistent
                # replay. Use the last pre-action step actually recorded instead.
                target = max((int(s['step']) for s in replay['steps'] if int(s['step']) > 0), default=1)
                captured, row, replay = _capture_valid_states(model, payload, schedule, {target})
            state = captured[target]
            body = {'model_id': model, 'map_family': family,
                'case_index': case_index, 'map_identity': payload['identity'],
                'schedule': schedule, 'historical_elapsed_steps': length,
                'state_step': state['step'], 'position': list(state['position']),
                'memory_sha256': state['memory_sha256'],
                'paid_observations_used': state['paid_observations_used'],
                'state_source_semantic_sha256': semantic_sha(row, replay),
                'target_stage': {'R': 'early', 'BP': 'middle', 'M': 'late'}[family],
                'provenance': 'replayed from a saved admitted high-frequency map/schedule and model; capture is pre-decision; hidden simulator truth is not passed to controller'}
            _append_journal(path, body)
            saved = body
            saved['_controller'] = state['controller']
        else:
            # Resume is only valid when deterministic state capture is repeated;
            # capture again because Python object state is intentionally not serialized.
            captured, row, replay = _capture_valid_states(model, payload, schedule, {int(saved['state_step'])})
            state = captured[int(saved['state_step'])]
            saved = dict(saved); saved['_controller'] = state['controller']
        snapshots.append((model, family, saved, saved['_controller']))
        if i % 27 == 0 or i == len(candidate_records):
            print(f'microbenchmark states {i}/{len(candidate_records)}', flush=True)
    results = []
    rng = random.Random(MICRO_SEED)
    for idx, (model, family, state_meta, snapshot) in enumerate(snapshots, 1):
        baseline_us = float(historical_summary[model]['mean_decision_call_ms']) * 1000
        if baseline_us <= 10:
            n = 300
        elif baseline_us <= 100:
            n = 150
        elif baseline_us <= 1000:
            n = 80
        elif baseline_us <= 10000:
            n = 30
        else:
            n = 20
        samples = []
        step = int(state_meta['state_step']); position = tuple(state_meta['position'])
        for trial in range(n):
            clone = copy.deepcopy(snapshot)  # State restoration is outside timer.
            t0 = time.perf_counter_ns()
            clone.decide(step, position)
            samples.append(time.perf_counter_ns()-t0)
        stats = _stats(samples)
        results.append({'model_id': model, 'map_family': family,
            'target_stage': state_meta['target_stage'], 'map_identity': state_meta['map_identity'],
            'state_step': step, 'position': canonical(position),
            'paid_observations_used': state_meta['paid_observations_used'],
            'memory_sha256': state_meta['memory_sha256'], 'samples': n,
            'mean_ns_per_call': stats['mean'], 'median_ns_per_call': stats['median'],
            'std_ns_per_call': stats['std'], 'p95_ns_per_call': stats['p95'],
            'p99_ns_per_call': stats['p99'],
            'mean_us_per_call': stats['mean']/1000,
            'median_us_per_call': stats['median']/1000,
            'std_us_per_call': stats['std']/1000,
            'p95_us_per_call': stats['p95']/1000,
            'p99_us_per_call': stats['p99']/1000,
            'state_source_semantic_sha256': state_meta['state_source_semantic_sha256'],
            'state_restoration_in_timed_region': False,
            'within_model_history_is_valid': True,
        })
        if idx % 27 == 0 or idx == len(snapshots):
            print(f'microbenchmark measurements {idx}/{len(snapshots)}', flush=True)
    _emit_csv(OUT/'decision_microbenchmark.csv', results)
    by_model = {}
    for model in models:
        vals = [x for x in results if x['model_id'] == model]
        calls = [x['mean_ns_per_call'] for x in vals]
        by_model[model] = {'state_count': len(vals), 'state_means_ns': calls,
            'mean_of_state_means_ns': statistics.mean(calls),
            'mean_us_per_call': statistics.mean(calls)/1000,
            'median_us_per_call': statistics.median(calls)/1000,
            'min_samples_per_state': min(x['samples'] for x in vals),
            'max_samples_per_state': max(x['samples'] for x in vals)}
    _emit_csv(OUT/'decision_microbenchmark_model_summary.csv', [
        {'model_id': m, **v} for m, v in by_model.items()])
    return results


def analyze():
    binding = validate_binding()
    rows = _read_complete_rows()
    expected = 54*72*REPETITIONS
    if len(rows) != expected:
        raise RuntimeError(f'Cannot analyze incomplete matrix: {len(rows)}/{expected}')
    if not all(x['parity_match'] for x in rows):
        raise RuntimeError('Cannot analyze failed semantic parity')
    model_list = model_ids()
    all_timing_arrays = _load_journal(OUT/'episode_journal.jsonl',
        lambda r: (r['repetition'], r['case_index'], r['model_id']))
    call_records = list(all_timing_arrays.values())
    _emit_csv(OUT/'episode_timings.csv', call_records)
    parity = [{k: r[k] for k in ('repetition','case_index','map_identity','schedule',
        'model_id','parity_sha256','baseline_semantic_sha256','parity_match')}
        for r in call_records]
    _emit_csv(OUT/'parity_validation.csv', parity)
    summaries = []
    breakdown = []
    for model in model_list:
        group = [r for r in rows if r['model_id'] == model]
        baseline = historical_summary_row(model)
        all_total_ms = [r['total_model_computation_ns']/1e6 for r in group]
        success_rate = statistics.mean(bool(r['success']) for r in group)
        paid_mean = statistics.mean(r['paid_observations'] for r in group)
        contact_episodes = sum(int(r['unwanted_contact_pairs']) > 0 for r in group)
        all_decision_calls = [v for r in group for v in r['_decision_calls_ns']]
        summary = {'model_id': model, 'episodes': len(group), 'repetitions': REPETITIONS,
            'goal_completions': sum(bool(r['success']) for r in group),
            'goal_rate': success_rate, 'mean_paid_observations': paid_mean,
            'mean_elapsed_steps': statistics.mean(r['elapsed_steps'] for r in group),
            'mean_distance_m': statistics.mean(r['travel_distance_m'] for r in group),
            'unwanted_contact_episodes': contact_episodes,
            'mean_initialization_ms': statistics.mean(r['initialization_ns'] for r in group)/1e6,
            'mean_observation_decision_ms': statistics.mean(r['decision_ns'] for r in group)/1e6,
            'mean_memory_update_ms': statistics.mean(r['memory_update_ns'] for r in group)/1e6,
            'mean_total_model_computation_ms': statistics.mean(all_total_ms),
            'median_total_model_computation_ms': statistics.median(all_total_ms),
            'std_total_model_computation_ms': statistics.stdev(all_total_ms),
            'p95_total_model_computation_ms': _quantile(all_total_ms,.95),
            'p99_total_model_computation_ms': _quantile(all_total_ms,.99),
            'mean_decision_ns_per_call': statistics.mean(all_decision_calls),
            'historical_mean_compute_ms': float(baseline['mean_compute_ms']),
            'historical_mean_decision_call_ms': float(baseline['mean_decision_call_ms']),
            'semantic_parity_failures': sum(not r['parity_match'] for r in group)}
        summaries.append(summary)
        for rep in range(1, REPETITIONS+1):
            subset = [r for r in group if r['repetition'] == rep]
            for key, field in (('initialization','initialization_ns'),
                               ('observation_decision','decision_ns'),
                               ('memory_update','memory_update_ns'),
                               ('total_model_computation','total_model_computation_ns')):
                vals = [r[field]/1e6 for r in subset]
                breakdown.append({'model_id': model, 'repetition': rep,
                    'component': key, 'episodes': len(vals), 'mean_ms': statistics.mean(vals),
                    'median_ms': statistics.median(vals), 'std_ms': statistics.stdev(vals),
                    'p95_ms': _quantile(vals,.95), 'p99_ms': _quantile(vals,.99),
                    'within_case_repetition_unit': 'same 72 map×schedule cases; not independent maps'})
    _emit_csv(OUT/'model_summary.csv', summaries)
    _emit_csv(OUT/'timing_breakdown.csv', breakdown)
    prior_cmp = []
    for s in summaries:
        old = s['historical_mean_compute_ms']; new = s['mean_total_model_computation_ms']
        prior_cmp.append({'model_id': s['model_id'], 'historical_mean_compute_ms': old,
            'new_mean_compute_ms': new, 'difference_ms': new-old,
            'ratio_new_over_historical': new/old if old else None,
            'historical_decision_call_ms': s['historical_mean_decision_call_ms'],
            'new_decision_call_ms': s['mean_decision_ns_per_call']/1e6,
            'paired_case_repetitions': 360, 'same_machine_python_dependencies': True,
            'parity_failures': s['semantic_parity_failures']})
    _emit_csv(OUT/'historical_vs_new_comparison.csv', prior_cmp)
    # Pareto axes are explicitly goal rate (maximize), paid reads (minimize),
    # and new total model computation (minimize), with no weighted score.
    pareto = []
    for candidate in summaries:
        dominated = any(other['model_id'] != candidate['model_id'] and
            other['goal_rate'] >= candidate['goal_rate'] and
            other['mean_paid_observations'] <= candidate['mean_paid_observations'] and
            other['mean_total_model_computation_ms'] <= candidate['mean_total_model_computation_ms'] and
            (other['goal_rate'] > candidate['goal_rate'] or
             other['mean_paid_observations'] < candidate['mean_paid_observations'] or
             other['mean_total_model_computation_ms'] < candidate['mean_total_model_computation_ms'])
            for other in summaries)
        pareto.append({'model_id': candidate['model_id'], 'pareto_optimal': not dominated,
            'goal_rate': candidate['goal_rate'],
            'mean_paid_observations': candidate['mean_paid_observations'],
            'mean_total_model_computation_ms': candidate['mean_total_model_computation_ms']})
    _emit_csv(OUT/'pareto_frontier.csv', pareto)
    ref = next(x for x in summaries if x['model_id'] == 'periodic5')
    break_even = []
    for s in summaries:
        saved = ref['mean_paid_observations'] - s['mean_paid_observations']
        extra = s['mean_total_model_computation_ms'] - ref['mean_total_model_computation_ms']
        crossover = extra/saved if saved > 0 and extra > 0 else None
        break_even.append({'model_id': s['model_id'], 'reference': 'periodic5',
            'reference_historical_policy': 'Periodic-5',
            'saved_observations_vs_reference': saved,
            'extra_fixed_computation_ms': extra,
            'break_even_observation_cost_ms': crossover,
            'nonnegative_break_even_exists': crossover is not None,
            'formula': 'extra fixed compute / paid observations saved; compute is init+decision+update',
            'limitation': 'hypothetical scan-price threshold, not energy or end-to-end runtime'})
    _emit_csv(OUT/'break_even_analysis.csv', break_even)
    poster_ids = ('static','periodic4','periodic5','age4','b_age','c_ternary','c_k',
                  'rdao_v1','rdao_v1_footprint','rdao_v1_gate_every')
    poster = [x for x in summaries if x['model_id'] in poster_ids]
    if len(poster) != len(poster_ids):
        raise RuntimeError('Poster model list is incomplete')
    _emit_csv(OUT/'poster_10_model_costs.csv', poster)
    _make_figures(summaries, breakdown, prior_cmp, poster, pareto)
    micro_path = OUT/'decision_microbenchmark.csv'
    if not micro_path.exists():
        print('Running separately scoped decision microbenchmark from valid saved episode histories.',flush=True)
        _microbench()
    _write_report(summaries, prior_cmp, pareto, break_even, binding)
    validate_preservation_post()
    write_exclusive(OUT/'validation_status.json', {'status':'PASS_COMPLETE',
        'episodes': len(rows), 'semantic_parity_records': len(parity),
        'parity_failures': sum(not r['parity_match'] for r in parity),
        'models': len(model_list), 'repetitions': REPETITIONS,
        'source_binding_sha256': sha(OUT/'binding.json'),
        'post_run_preservation': verify_preservation(),
        'validated_at_utc': datetime.now(timezone.utc).isoformat()})
    print('Analysis, figures, microbenchmark, parity, and preservation checks complete.',flush=True)


def historical_summary_row(model):
    with (PRIOR_COMPREHENSIVE/'analysis/high_frequency_environment_summary.csv').open(encoding='utf-8') as f:
        for row in csv.DictReader(f):
            if row['condition'] == 'high_frequency' and row['model_id'] == model:
                return row
    raise RuntimeError(f'No historical timing summary for {model}')


def validate_preservation_post():
    result = verify_preservation()
    if result.get('status') != 'PASS':
        raise RuntimeError(f'Post-run protected integrity check failed: {result}')


def _make_figures(summaries, breakdown, comparison, poster, pareto):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    figdir = OUT/'figures'; figdir.mkdir(exist_ok=True)
    def save(fig, name):
        fig.tight_layout(); fig.savefig(figdir/(name+'.png'), dpi=180)
        fig.savefig(figdir/(name+'.svg')); plt.close(fig)
    ordered = sorted(summaries, key=lambda x: x['mean_total_model_computation_ms'])
    fig, ax = plt.subplots(figsize=(16,6))
    ax.bar([x['model_id'] for x in ordered],
           [max(1e-6,x['mean_total_model_computation_ms']) for x in ordered], color='#3e7798')
    ax.set_yscale('log'); ax.set_ylabel('Model computation (ms / episode; log scale)')
    ax.set_title('H2 controlled compute benchmark · 54 models')
    ax.tick_params(axis='x', rotation=80, labelsize=7); save(fig,'total_model_computation_54')
    fig, ax = plt.subplots(figsize=(15,6))
    ids=[x['model_id'] for x in summaries]; width=.72
    bottoms=[0.]*len(ids)
    for key,label,color in (('mean_initialization_ms','Initialization','#74a9cf'),
        ('mean_observation_decision_ms','Observation decision','#f28e2b'),
        ('mean_memory_update_ms','Memory update','#59a14f')):
        vals=[x[key] for x in summaries];ax.bar(ids,vals,bottom=bottoms,width=width,label=label,color=color)
        bottoms=[a+b for a,b in zip(bottoms,vals)]
    ax.set_ylabel('Mean computation (ms / episode)');ax.set_title('Model computation components');ax.legend()
    ax.tick_params(axis='x',rotation=80,labelsize=7);save(fig,'computational_cost_breakdown')
    fig, ax=plt.subplots(figsize=(16,6))
    decision=sorted(summaries,key=lambda x:x['mean_decision_ns_per_call'])
    ax.bar([x['model_id'] for x in decision],
        [max(1e-3,x['mean_decision_ns_per_call']/1000) for x in decision],color='#8b78a6')
    ax.set_yscale('log');ax.set_ylabel('Observation decision (μs / call; log scale)')
    ax.set_title('Mean per-call decision latency, aggregated from episode calls')
    ax.tick_params(axis='x',rotation=80,labelsize=7);save(fig,'decision_latency_per_call')
    fig, ax=plt.subplots(figsize=(14,6))
    comp=sorted(comparison,key=lambda x:x['historical_mean_compute_ms'])
    x=list(range(len(comp)));w=.42
    ax.bar([v-w/2 for v in x],[max(1e-6,r['historical_mean_compute_ms']) for r in comp],w,label='Historical')
    ax.bar([v+w/2 for v in x],[max(1e-6,r['new_mean_compute_ms']) for r in comp],w,label='Controlled rerun')
    ax.set_yscale('log');ax.set_xticks(x,[r['model_id'] for r in comp],rotation=80,fontsize=7)
    ax.set_ylabel('Total model computation (ms / episode, log)');ax.legend()
    ax.set_title('Historical vs controlled timing');save(fig,'historical_vs_new_computation')
    fig, ax=plt.subplots(figsize=(9,7))
    sc=ax.scatter([x['mean_paid_observations'] for x in summaries],
        [x['mean_total_model_computation_ms'] for x in summaries],
        c=[x['goal_rate'] for x in summaries],cmap='viridis',s=35)
    ax.set_yscale('log');ax.set_xlabel('Paid observations / episode');ax.set_ylabel('Total model computation (ms; log)')
    fig.colorbar(sc,ax=ax,label='Goal success rate');ax.set_title('Goal success · observations · computation')
    save(fig,'success_observations_computation_3d_projection')
    fig,ax=plt.subplots(figsize=(12,5))
    ax.bar([x['model_id'] for x in poster],[x['mean_total_model_computation_ms'] for x in poster],color='#427da1')
    ax.set_ylabel('Mean model computation (ms / episode)');ax.tick_params(axis='x',rotation=35)
    ax.set_title('Poster subset: 10 admitted models');save(fig,'poster_10_model_costs')


def _write_report(summaries, comparison, pareto, break_even, binding):
    lookup={r['model_id']:r for r in summaries}
    pairs=(('periodic4','periodic5'),('age4','age5'),('periodic5','age4'),
           ('periodic5','rdao_v1_footprint'),('rdao_v1','rdao_v1_footprint'),
           ('rdao_v1_footprint','rdao_v1_gate_every'))
    lines=['# H2 Controlled Computational Cost Benchmark','',
        '**Status:** Complete only if `validation_status.json` reports `PASS_COMPLETE`.','',
        'Descriptive development timing rerun on the same 36 saved maps and two saved high-frequency schedules. Each of five repetitions contains the same 3,888 model×map×schedule episodes; repeats are not additional independent environments. No experiment policy, parameter, observation budget, safety, map, or schedule was changed.','',
        '## Existing anomaly diagnosis','',
        'Periodic-4 calls the frozen baseline `ObservationController` periodic interval test. Periodic-5 calls `CadenceController` through `PersistenceEVIController`; its `_score` runs `cadence_decision`, which allocates a full grid index and computes known-cell age fractions before checking the periodic5 mode. The score is not used by the fixed-period grant decision. This unnecessary per-call scoring is confirmed in source at `src/spatial_memory/cadence_age.py`; it explains the larger decision workload. Age-4 uses the age observer and is a separate code path. The timing gap is therefore not explained by observation interval alone. No controller was edited for this benchmark.','',
        'Existing measurements used `time.perf_counter_ns()` in the shared `h2_final_common.run_case` wrapper for model initialization, `core.decide`, and `core.refresh`. The 13 historical arms and 41 additional admitted arms both pass through that wrapper. Sensor acquisition, emergency sensing, navigation planning, selected-action shielding, scene updates, event generation, replay capture and I/O are separately timed or outside that scope. Historical bindings show Python 3.12.10, arm64 macOS 26.6.2, MuJoCo 3.17.0, NumPy 2.2.6, and the same hostname as this rerun. Historical CPU contention/thermal state was not logged, so it cannot be ruled out retrospectively.','',
        '## Controlled protocol and integrity','',
        f"- Bound source commit: `{binding['source_commit']}`; one sequential process, 8 logical CPUs available.",
        '- One fixed warm-up episode per model; measured model×case tasks shuffled with a seeded PRNG independently for each repetition.',
        '- Timer: `time.perf_counter_ns()`; timer-pair overhead probe is in `binding.json`. Raw measured time is retained, not corrected.',
        '- Per-model compute = initialization + observation decision + spatial-memory update. The three components are reported separately.',
        '- Every measured run is compared by semantic SHA-256 against its existing episode trace, excluding only timing/runtime fields. All five repetitions must pass.',
        '- Full hidden occupancy is evaluator/replay data only. Controller inputs are supplied by the frozen runner; the separate microbenchmark captures controller-owned state before a legitimate decision and never passes ground truth.',
        '- Checkpoint journal records are fsynced per episode and hash-checked for safe `--resume`.','',
        '## Timing comparisons','',
        '| Contrast | Controlled A (ms/episode) | Controlled B (ms/episode) | Ratio B/A |',
        '|---|---:|---:|---:|']
    for a,b in pairs:
        va=lookup[a]['mean_total_model_computation_ms'];vb=lookup[b]['mean_total_model_computation_ms']
        lines.append(f'| {a} vs {b} | {va:.6f} | {vb:.6f} | {vb/va:.3f} |')
    lines += ['', '## Computational cost definition and variability','',
        'Episode-level repeated measurements are grouped by model and repetition in `timing_breakdown.csv`. Within-case repetition variation is retained separately from across-case variation; maps are not treated as independent repeated observations. The decision microbenchmark uses three model-specific states reconstructed by executing the saved legitimate history: early (R), middle (BP), late (M). These are not identical cross-model inputs because controller histories diverge. Controller state copying is outside each timed decision. Per-model/state mean, median, standard deviation, P95, P99, and sample count are in `decision_microbenchmark.csv`; tail estimates are descriptive and less stable when the model required fewer samples.','',
        '## Pareto and observation break-even','',
        '`pareto_frontier.csv` keeps the three axes separate: maximize goal rate, minimize paid observations, minimize model compute. `break_even_analysis.csv` uses Periodic-5 as reference and divides extra fixed model computation by paid observations saved. It is a hypothetical scan-cost crossover, not measured sensor energy, battery use, or end-to-end runtime.','',
        '## Results summary','',
        f"- Repeated episodes: {54*72*REPETITIONS:,}; semantic parity records: {54*72*REPETITIONS:,}.",
        '- Detailed model/episode/repetition values and plots are in this directory; poster subset is `poster_10_model_costs.csv` plus its PNG/SVG chart.',
        '- Smoke: six saved map×schedule cases across 54 models, plus eight duplicate executions; see `smoke_gate.json`.',
        '- No new maps or schedules were generated. Existing evidence remains unchanged.','',
        '## Machine-readable files','',
        '- `episode_timings.csv`, `decision_microbenchmark.csv`, `model_summary.csv`, `timing_breakdown.csv`',
        '- `historical_vs_new_comparison.csv`, `parity_validation.csv`, `pareto_frontier.csv`, `break_even_analysis.csv`',
        '- `environment_info.json`, `binding.json`, `runtime_observations.jsonl`, `validation_status.json`',
        '- Figures are supplied in PNG and SVG under `figures/`.','']
    (OUT/'final_report.md').write_text('\n'.join(lines),encoding='utf-8')


def verify():
    binding=validate_binding();models=model_ids()
    journal=OUT/'episode_journal.jsonl'
    rows=_load_journal(journal,lambda r:(r['repetition'],r['case_index'],r['model_id']))
    expected=54*72*REPETITIONS
    mismatches=[r for r in rows.values() if not r['parity_match']]
    result={'episodes_committed':len(rows),'expected':expected,'models':len(models),
        'repetitions':REPETITIONS,'semantic_parity_failures':len(mismatches),
        'binding_sha256':sha(OUT/'binding.json'),
        'status':'PASS' if len(rows)==expected and not mismatches else 'INCOMPLETE_OR_FAIL'}
    print(json.dumps(result,indent=2))
    if result['status']!='PASS':raise SystemExit(1)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('prepare')
    sub.add_parser('smoke')
    run=sub.add_parser('run');run.add_argument('--resume',action='store_true')
    sub.add_parser('analyze')
    sub.add_parser('verify')
    args=parser.parse_args()
    if args.command=='prepare': prepare()
    elif args.command=='smoke': run_smoke()
    elif args.command=='run': run_repetitions(args.resume)
    elif args.command=='analyze': analyze()
    elif args.command=='verify': verify()


if __name__ == '__main__':
    main()
