#!/usr/bin/env python3
"""Replay the three saved 400-step 61-ray failures with an 800-step horizon."""
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
SOURCE_80 = ROOT / 'results/phase2_mujoco/g1_forward_first_61ray_emergency_safety_full_288_v1'
SOURCE_400 = ROOT / 'results/phase2_mujoco/g1_forward_first_61ray_emergency_safety_failed_episodes_h400_v1'
OUTPUT = ROOT / 'results/phase2_mujoco/g1_forward_first_61ray_emergency_safety_unreached_h400_h800_v1'
NEW_HORIZON = 800


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def file_sha(path: Path) -> str:
    return sha(path.read_bytes())


def load_module():
    spec = importlib.util.spec_from_file_location(
        'phase2_61ray_eval_horizon800',
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


def verify_artifacts(directory: Path):
    items = json.loads((directory / 'artifact_manifest.json').read_text(encoding='utf-8'))
    for item in items:
        raw = (directory / item['path']).read_bytes()
        if len(raw) != item['bytes'] or sha(raw) != item['sha256']:
            raise ValueError(f'Source artifact hash mismatch: {item["path"]}')
    return items


def main(output: Path = OUTPUT):
    if output.exists():
        raise FileExistsError(f'Refusing to overwrite {output}')
    evaluator = load_module()
    evaluator._verify_output(SOURCE_80)
    phase15_before = evaluator.nav.verify_preserved_prefix()
    old_manifest = json.loads((SOURCE_400 / 'experiment_manifest.json').read_text(encoding='utf-8'))
    source400_artifacts = verify_artifacts(SOURCE_400)
    if old_manifest['source_evaluation_conditions']['only_changed_config_key'] != 'max_steps':
        raise ValueError('The 400-step precursor does not document a single-key horizon change')
    if old_manifest['source_evaluation_conditions']['policy_config_used']['max_steps'] != 400:
        raise ValueError('400-step precursor manifest has the wrong horizon')
    if old_manifest['evaluator_source_hashes'] != evaluator._source_hashes():
        raise ValueError('The pinned evaluator source differs from the 400-step run')

    _base_rows, _base_index, provenance, baseline_hashes = evaluator.load_baseline()
    previous_rows = list(csv.DictReader((SOURCE_400 / 'failed_episodes_horizon400.csv').open(
        newline='', encoding='utf-8')))
    selected = [row for row in previous_rows if str(row['success']).lower() != 'true']
    if len(previous_rows) != 63 or len(selected) != 3:
        raise ValueError(f'Expected 3 failures in the 400-step cohort, found {len(selected)}')
    if any(int(row['elapsed_steps']) != 400 for row in selected):
        raise ValueError('Selected 400-step failures did not all reach the exact horizon')
    selected.sort(key=lambda row: (row['world_identity'], int(row['schedule']), row['method'], int(row['seed'])))
    keys = [row_key(row) for row in selected]
    if keys != [
        ('phase1.5-v0.4-BPRIME-1:fit:BP:80010004', 0, 'static', 42),
        ('phase1.5-v0.4-BPRIME-1:fit:BP:80010004', 1, 'static', 42),
        ('phase1.5-v0.4-BPRIME-1:fit:M:80030008', 1, 'static', 42),
    ]:
        raise ValueError(f'Unexpected residual failure cohort: {keys}')

    source_traces = read_trace_index(SOURCE_400 / 'failed_episode_traces.jsonl.gz')
    if not set(keys).issubset(source_traces):
        raise ValueError('A selected 400-step failure lacks its saved trace')
    original_config = evaluator.frozen_config(provenance)
    changed_config = json.loads(json.dumps(original_config))
    if changed_config['max_steps'] != 80:
        raise ValueError('Expected original frozen horizon 80')
    changed_config['max_steps'] = NEW_HORIZON
    changed_keys = [key for key in original_config if original_config[key] != changed_config[key]]
    if changed_keys != ['max_steps']:
        raise ValueError(f'Only max_steps may change; got {changed_keys}')
    source400_config = old_manifest['source_evaluation_conditions']['policy_config_used']
    if {**source400_config, 'max_steps': 80} != original_config:
        raise ValueError('The 400-step source changed a setting beyond max_steps')

    worlds = evaluator.nav.admitted_worlds()
    world_by_id = {item['identity']: item for item in worlds}
    if len(world_by_id) != 36:
        raise ValueError('Expected the same 36 admitted worlds; generation is not allowed')
    source_hashes = {
        'horizon400_csv_sha256': file_sha(SOURCE_400 / 'failed_episodes_horizon400.csv'),
        'horizon400_trace_sha256': file_sha(SOURCE_400 / 'failed_episode_traces.jsonl.gz'),
        'horizon400_manifest_sha256': file_sha(SOURCE_400 / 'experiment_manifest.json'),
        'original_288_manifest_sha256': file_sha(SOURCE_80 / 'experiment_manifest.json'),
        'original_288_episode_csv_sha256': file_sha(SOURCE_80 / 'episodes.csv'),
    }

    output.mkdir(parents=True)
    results, traces = [], []
    start = time.monotonic()
    for index, saved in enumerate(selected, 1):
        key = row_key(saved)
        config = json.loads(json.dumps(changed_config))
        row, trace = evaluator.run_case(world_by_id[key[0]], key[1], key[2],
                                        config, with_safety=True, keep_trace=True)
        if row_key(row) != key:
            raise ValueError(f'Replay key changed: {key}')
        prefix = source_traces[key]['steps']
        if len(prefix) != 401 or len(trace['steps']) < 401:
            raise ValueError(f'Expected the full step 0..400 prefix for {key}')
        for old, new in zip(prefix, trace['steps'][:401]):
            if canonical(trace_core(old)) != canonical(trace_core(new)):
                raise ValueError(f'Rerun diverges from 400-step trace at {key}, step {old["step"]}')
        row['previous_horizon400_success'] = False
        row['horizon_extension_changed_prefix_through_step_400'] = False
        results.append(row)
        traces.append(trace)
        elapsed = time.monotonic() - start
        print(f'Progress {index}/3 | elapsed {elapsed:.1f}s | goal_step={row.get("goal_step") or "not reached"}',
              flush=True)

    with (output / 'unreached_horizon800.csv').open('x', newline='', encoding='utf-8') as stream:
        fields = list(results[0])
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        for row in results:
            writer.writerow({key: json.dumps(value, sort_keys=True, separators=(',', ':'))
                             if isinstance(value, (dict, list, tuple)) else value
                             for key, value in row.items()})
    with gzip.open(output / 'unreached_traces.jsonl.gz', 'wt', encoding='utf-8', newline='') as stream:
        for trace in traces:
            stream.write(json.dumps(trace, sort_keys=True, allow_nan=False) + '\n')
    completions = sum(bool(row['success']) for row in results)
    summary = {
        'cohort_size': 3, 'previous_horizon400_failures': 3,
        'goal_completions_by_800': completions,
        'contact_free_goal_completions_by_800': sum(bool(row['g1_contact_free_success']) for row in results),
        'still_not_reached_by_800': 3 - completions,
        'contact_episodes_by_800': sum(int(row['g1_unwanted_contact_states']) > 0 for row in results),
        'episodes': [{
            'world_identity': row['world_identity'], 'schedule': int(row['schedule']),
            'policy': row['method'], 'seed': int(row['seed']), 'success': bool(row['success']),
            'goal_step': int(row['elapsed_steps']) if row['success'] else None,
            'elapsed_steps': int(row['elapsed_steps']), 'final_position': row['final_position'],
            'unwanted_contact_states': int(row['g1_unwanted_contact_states']),
            'unwanted_contact_pairs': int(row['g1_unwanted_contact_pairs']),
        } for row in results],
    }
    write_json(output / 'summary.json', summary)
    lines = [
        '# Residual 61-ray failures: 400 to 800 steps', '',
        'This run contains only the three episodes still unsuccessful at step 400. The only changed policy setting is `max_steps: 80 → 800`; source traces match exactly through step 400 for each case.', '',
        f"- Goal reached by step 800: **{completions}/3**",
        f"- Contact-free goal completions: **{summary['contact_free_goal_completions_by_800']}/3**",
        f"- Still not reached by step 800: **{3-completions}**",
        f"- Episodes with unwanted contacts: **{summary['contact_episodes_by_800']}**", '',
        '| Maze | Schedule | Policy | Result | Goal step | Contacts |',
        '|---|---:|---|---|---:|---:|',
    ]
    for row in results:
        lines.append(f"| {row['world_identity'].split(':')[-1]} | {row['schedule']} | {row['method']} | "
                     f"{'goal' if row['success'] else 'not reached'} | "
                     f"{row['elapsed_steps'] if row['success'] else '—'} | "
                     f"{row['g1_unwanted_contact_states']} states / {row['g1_unwanted_contact_pairs']} pairs |")
    (output / 'report.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')

    evaluator._verify_output(SOURCE_80)
    if file_sha(SOURCE_400 / 'failed_episodes_horizon400.csv') != source_hashes['horizon400_csv_sha256']:
        raise RuntimeError('The 400-step source CSV changed during rerun')
    verify_artifacts(SOURCE_400)
    phase15_after = evaluator.nav.verify_preserved_prefix()
    if phase15_before != phase15_after:
        raise RuntimeError('Protected Phase 1.5 inventory changed during rerun')
    manifest = {
        'task': 'replay only the three 400-step residual failures at horizon 800',
        'source_result_directories': [str(SOURCE_80.relative_to(ROOT)), str(SOURCE_400.relative_to(ROOT))],
        'selected_episode_keys': [list(key) for key in keys],
        'source_evaluation_conditions': {'seed': evaluator.SEED,
            'safety_config': evaluator.SAFETY_CONFIG,
            'policy_config_original': original_config, 'policy_config_used': changed_config,
            'only_changed_config_key': 'max_steps', 'admitted_worlds_reused': 36,
            'candidate_or_world_generation': False},
        'prefix_validation': {'steps_0_through_400_match_h400_source_for_all_three': True},
        'source_hashes': source_hashes, 'source400_artifacts_verified': len(source400_artifacts),
        'baseline_artifacts_verified': len(baseline_hashes),
        'phase15_preservation_verification': phase15_after,
        'summary': summary, 'original_288_and_h400_results_modified': False,
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
    print(json.dumps({'status': 'PASS_HORIZON800_RESIDUAL_COHORT',
                      'output': str(output.relative_to(ROOT)), 'summary': summary}, indent=2), flush=True)


if __name__ == '__main__':
    main()
