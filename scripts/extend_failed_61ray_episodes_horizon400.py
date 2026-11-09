#!/usr/bin/env python3
"""Replay only failed saved 61-ray episodes with a 400-step horizon.

This is a separate diagnostic cohort. It consumes admitted saved worlds and
the frozen 61-ray evaluator, changing only policy_config.max_steps from 80 to
400. It never edits either source evaluation directory.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'scripts')]
SOURCE = ROOT / 'results/phase2_mujoco/g1_forward_first_61ray_emergency_safety_full_288_v1'
OUTPUT = ROOT / 'results/phase2_mujoco/g1_forward_first_61ray_emergency_safety_failed_episodes_h400_v1'
NEW_HORIZON = 400


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def file_sha(path: Path) -> str:
    return sha(path.read_bytes())


def load_module():
    spec = importlib.util.spec_from_file_location(
        'phase2_61ray_eval_horizon400',
        ROOT / 'scripts/evaluate_phase2_61ray_emergency_safety_full_288.py')
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def read_trace_index(path: Path):
    result = {}
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        for line in stream:
            record = json.loads(line)
            key = tuple(record['key'])
            if key in result:
                raise ValueError(f'Duplicate saved trace key: {key}')
            result[key] = record
    return result


def row_key(row):
    return (row['world_identity'], int(row['schedule']), row['method'], int(row['seed']))


def trace_core(record):
    fields = ('step', 'position', 'heading_yaw', 'action', 'action_reason', 'moved',
              'blocked', 'contacts', 'observation_granted', 'observation_count',
              'emergency_scan', 'emergency_intervention', 'evaluator_only_proxy_cells')
    return {key: record.get(key) for key in fields}


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode('utf-8')


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n',
                    encoding='utf-8')


def main(output: Path = OUTPUT):
    if output.exists():
        raise FileExistsError(f'Refusing to overwrite {output}')
    evaluator = load_module()
    evaluator._verify_output(SOURCE)
    phase15_before = evaluator.nav.verify_preserved_prefix()
    baseline_rows, _baseline_index, provenance, baseline_hashes = evaluator.load_baseline()
    source_episodes = list(csv.DictReader((SOURCE / 'episodes.csv').open(newline='', encoding='utf-8')))
    source_by_key = {row_key(row): row for row in source_episodes}
    if len(source_episodes) != 288 or len(source_by_key) != 288:
        raise ValueError('Expected 288 unique source episode rows')
    source_trace_path = SOURCE / 'episode_traces.jsonl.gz'
    source_traces = read_trace_index(source_trace_path)
    if set(source_traces) != set(source_by_key):
        raise ValueError('Source saved trace keys do not match the 288 episode rows')
    failed = [row for row in source_episodes if str(row['success']).lower() != 'true']
    if not failed or any(int(row['elapsed_steps']) != 80 for row in failed):
        raise ValueError('Failure cohort is not the saved 80-step failed subset')
    failed.sort(key=lambda row: (row['world_identity'], int(row['schedule']), row['method'], int(row['seed'])))
    keys = [row_key(row) for row in failed]
    if len(set(keys)) != len(keys):
        raise ValueError('Duplicate failed episode selection')

    original_config = evaluator.frozen_config(provenance)
    changed_config = json.loads(json.dumps(original_config))
    if changed_config['max_steps'] != 80:
        raise ValueError('Expected frozen 80-step source policy')
    changed_config['max_steps'] = NEW_HORIZON
    config_differences = [key for key in original_config
                          if original_config[key] != changed_config[key]]
    if config_differences != ['max_steps']:
        raise ValueError(f'Only max_steps may change, observed top-level differences: {config_differences}')

    worlds = evaluator.nav.admitted_worlds()
    world_by_id = {item['identity']: item for item in worlds}
    if len(world_by_id) != 36:
        raise ValueError('Expected exactly 36 admitted saved worlds; no generation is performed')
    source_hashes = {
        'source_episode_csv_sha256': file_sha(SOURCE / 'episodes.csv'),
        'source_trace_sha256': file_sha(source_trace_path),
        'source_manifest_sha256': file_sha(SOURCE / 'experiment_manifest.json'),
        'source_experiment_manifest_sha256': file_sha(SOURCE / 'experiment_manifest.json'),
        'baseline_manifest_sha256': file_sha(evaluator.BASELINE / 'artifact_manifest.json'),
        'evaluator_source_hashes': evaluator._source_hashes(),
    }

    output.mkdir(parents=True)
    results, traces = [], []
    started = time.monotonic()
    print(f'Running {len(failed)} saved failed episodes with horizon {NEW_HORIZON}; '
          'all other evaluator settings are frozen.', flush=True)
    for index, saved in enumerate(failed, 1):
        key = row_key(saved)
        if key not in source_traces:
            raise ValueError(f'Missing source trace: {key}')
        config = json.loads(json.dumps(changed_config))
        row, trace = evaluator.run_case(world_by_id[key[0]], key[1], key[2],
                                        config, with_safety=True, keep_trace=True)
        if row_key(row) != key:
            raise ValueError(f'Replay key changed: expected {key}, got {row_key(row)}')
        old_steps = source_traces[key]['steps']
        new_steps = trace['steps']
        if len(old_steps) != 81 or len(new_steps) < 81:
            raise ValueError(f'Expected a complete saved 0..80 trace prefix for {key}')
        for old, new in zip(old_steps, new_steps[:81]):
            if canonical(trace_core(old)) != canonical(trace_core(new)):
                raise ValueError(f'Run differs before the horizon boundary for {key}, step {old["step"]}')
        row['original_80_step_success'] = False
        row['original_80_step_elapsed_steps'] = int(saved['elapsed_steps'])
        row['horizon_extension_changed_prefix_through_step_80'] = False
        results.append(row)
        traces.append(trace)
        elapsed = time.monotonic() - started
        eta = elapsed / index * (len(failed) - index)
        if index == 1 or index % 5 == 0 or index == len(failed):
            print(f'Progress {index}/{len(failed)} ({100*index/len(failed):.1f}%) | '
                  f'elapsed {elapsed/60:.1f} min | ETA {eta/60:.1f} min | '
                  f'latest goal_step={row.get("goal_step") or "not reached"}', flush=True)

    csv_path = output / 'failed_episodes_horizon400.csv'
    fields = list(results[0])
    with csv_path.open('x', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        for row in results:
            writer.writerow({key: json.dumps(value, sort_keys=True, separators=(',', ':'))
                             if isinstance(value, (dict, list, tuple)) else value
                             for key, value in row.items()})
    trace_path = output / 'failed_episode_traces.jsonl.gz'
    with gzip.open(trace_path, 'wt', encoding='utf-8', newline='') as stream:
        for trace in traces:
            stream.write(json.dumps(trace, sort_keys=True, allow_nan=False) + '\n')

    completions = sum(bool(row['success']) for row in results)
    no_contact_completions = sum(bool(row['g1_contact_free_success']) for row in results)
    still_failed = [row for row in results if not row['success']]
    summary = {
        'cohort_size': len(results), 'original_80_step_failures': len(failed),
        'goal_completions_by_400': completions,
        'contact_free_goal_completions_by_400': no_contact_completions,
        'still_not_reached_by_400': len(still_failed),
        'goal_step_counts': {'reached': {
            f"{row['world_identity']}|schedule={row['schedule']}|{row['method']}|seed={row['seed']}": int(row['elapsed_steps'])
            for row in results if row['success']},
            'not_reached': [
                f"{row['world_identity']}|schedule={row['schedule']}|{row['method']}|seed={row['seed']}"
                for row in still_failed]},
        'contact_episodes_by_400': sum(int(row['g1_unwanted_contact_states']) > 0 for row in results),
        'mean_goal_step_among_completions': (
            sum(int(row['elapsed_steps']) for row in results if row['success']) / completions
            if completions else None),
    }
    write_json(output / 'summary.json', summary)

    lines = [
        '# Failed 61-ray episodes with 400-step horizon', '',
        f"Replayed the {len(failed)} episodes marked unsuccessful in the saved 288-episode 61-ray evaluation. "
        'The only policy configuration change was `max_steps: 80 → 400`. The 288-episode source run '
        'and all successful episodes were not rerun.', '',
        f"- Reached goal by step 400: **{completions}/{len(failed)}**",
        f"- Contact-free goal completions: **{no_contact_completions}/{len(failed)}**",
        f"- Still not reached by step 400: **{len(still_failed)}**",
        f"- Contact episodes in the extended cohort: **{summary['contact_episodes_by_400']}**",
        f"- Mean goal step among new completions: **{summary['mean_goal_step_among_completions']:.2f}**" if completions else '- Mean goal step: n/a',
        '', 'The per-episode `elapsed_steps` is the goal step for completed episodes; `goal_step` is blank for episodes that did not complete. `failed_episodes_horizon400.csv` lists every result. The trace file stores each full rerun.', '',
        '| World | Schedule | Policy | Original 80-step end | Horizon-400 result | Goal step | Unwanted contacts |',
        '|---|---:|---|---:|---|---:|---:|',
    ]
    for old, row in zip(failed, results):
        identity = row['world_identity'].split(':')[-1]
        lines.append(f"| {identity} | {row['schedule']} | {row['method']} | 80 | "
                     f"{'goal' if row['success'] else 'not reached'} | "
                     f"{row['elapsed_steps'] if row['success'] else '—'} | "
                     f"{row['g1_unwanted_contact_states']} states / {row['g1_unwanted_contact_pairs']} pairs |")
    (output / 'report.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')

    if file_sha(SOURCE / 'episodes.csv') != source_hashes['source_episode_csv_sha256']:
        raise RuntimeError('Source 61-ray episodes.csv changed during rerun')
    if file_sha(source_trace_path) != source_hashes['source_trace_sha256']:
        raise RuntimeError('Source 61-ray traces changed during rerun')
    evaluator._verify_output(SOURCE)
    phase15_after = evaluator.nav.verify_preserved_prefix()
    if phase15_before != phase15_after:
        raise RuntimeError('Protected Phase 1.5 inventory verification changed during rerun')

    manifest = {
        'task': 'rerun only previously failed 61-ray episodes at horizon 400',
        'source_result_directory': str(SOURCE.relative_to(ROOT)),
        'selection_rule': 'success=false in source episodes.csv; 63 selected from the 288 saved rows',
        'selected_episode_keys': [list(key) for key in keys],
        'source_evaluation_conditions': {
            'seed': evaluator.SEED, 'safety_config': evaluator.SAFETY_CONFIG,
            'policy_config_original': original_config,
            'policy_config_used': changed_config,
            'only_changed_config_key': 'max_steps',
            'admitted_worlds_reused': 36,
            'candidate_or_world_generation': False,
        },
        'prefix_validation': {
            'first_81_trace_frames_match_source_for_every_episode': True,
            'source_unsuccessful_endpoint_step': 80,
        },
        'source_hashes_before_run': source_hashes,
        'baseline_artifacts_verified': len(baseline_hashes),
        'phase15_preservation_verification': phase15_after,
        'summary': summary,
        'original_288_episode_result_modified': False,
        'evaluator_source_hashes': evaluator._source_hashes(),
    }
    write_json(output / 'experiment_manifest.json', manifest)

    artifact_manifest = []
    for path in sorted(p for p in output.rglob('*') if p.is_file() and p.name != 'artifact_manifest.json'):
        raw = path.read_bytes()
        artifact_manifest.append({'path': path.relative_to(output).as_posix(),
                                  'bytes': len(raw), 'sha256': sha(raw)})
    write_json(output / 'artifact_manifest.json', artifact_manifest)
    for item in artifact_manifest:
        raw = (output / item['path']).read_bytes()
        if len(raw) != item['bytes'] or sha(raw) != item['sha256']:
            raise ValueError(f'Output artifact hash mismatch: {item["path"]}')
    print(json.dumps({'status': 'PASS_HORIZON400_FAILED_COHORT',
        'output': str(output.relative_to(ROOT)), 'summary': summary,
        'artifact_count': len(artifact_manifest)}, indent=2), flush=True)


if __name__ == '__main__':
    main()
