#!/usr/bin/env python3
"""Append-only H2 optimization parity and reconciliation helpers.

This runner uses only already admitted H2/FIT72 maps and the frozen experiment
engines. It does not generate maps or alter prior evidence.
"""
from __future__ import annotations

import argparse
import base64
import csv
import gzip
import hashlib
import json
import os
import platform
import random
import subprocess
import sys
import time
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'src')]
OUT = ROOT / 'results/phase2_mujoco/h2_final_benchmark_reconciliation_v1'
BASELINE = '840b0e2dbc7a8c302edcaef0e226ab88abcf6549'
OPTIMIZED = ('periodic5', 'age5')


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode('utf-8')


def append_journal(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    envelope = {'record': record, 'sha256': sha_bytes(canonical(record))}
    with path.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(envelope, sort_keys=True, ensure_ascii=False,
                                allow_nan=False) + '\n')
        stream.flush()
        import os
        os.fsync(stream.fileno())


def load_journal(path: Path, key_fn):
    records = {}
    if not path.exists():
        return records
    for line_no, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        item = json.loads(line)
        record = item['record']
        if sha_bytes(canonical(record)) != item.get('sha256'):
            raise RuntimeError(f'Journal hash mismatch at {path}:{line_no}')
        key = key_fn(record)
        if key in records:
            raise RuntimeError(f'Duplicate journal record at {path}:{line_no}: {key}')
        records[key] = record
    return records


def strip_diagnostic_fields(value, model: str):
    """Remove only cadence score fields that cannot affect later behavior."""
    removed = {'age_request', 'age_score'}
    if model == 'periodic5':
        removed.add('effective_age_score')
    if isinstance(value, dict):
        return {k: strip_diagnostic_fields(v, model) for k, v in value.items()
                if k not in removed}
    if isinstance(value, list):
        return [strip_diagnostic_fields(v, model) for v in value]
    if isinstance(value, tuple):
        return [strip_diagnostic_fields(v, model) for v in value]
    return value


def semantic_projection(value):
    """Match the established H2 semantic filter for runtime-only values."""
    ignored = ('timing', '_ns', '_ms', 'wall', 'duration', 'computation',
               '_seconds', 'runtime', 'elapsed_time', 'cpu_time')
    if isinstance(value, dict):
        return {k: semantic_projection(v) for k, v in value.items()
                if not any(part in k.lower() for part in ignored)}
    if isinstance(value, (tuple, list)):
        return [semantic_projection(v) for v in value]
    return value


def capture_states(engine, model: str, payload: dict, schedule: int, condition: str):
    """Run one case and capture model-owned state after every decision/update."""
    import spatial_memory.cadence_age as cadence
    import h2_final_common as frozen
    from run_h2_full_spatial_memory_replay import _controller_state

    engine._extend_frozen_arms()
    old_factory = frozen.factory
    states: list[dict] = []

    def capturing_factory(initial, arm, cfg, options, goal):
        core = old_factory(initial, arm, cfg, options, goal)

        def record(phase: str, step: int):
            states.append({'phase': phase, 'step': int(step),
                           'state': _controller_state(core)})

        record('initialized', 0)
        for method_name in ('decide', 'refresh'):
            original = getattr(core, method_name)
            if method_name == 'decide':
                def call(step, position, _original=original):
                    result = _original(step, position)
                    record('after_decision', step)
                    return result
            else:
                def call(observation, step, _original=original):
                    result = _original(observation, step)
                    record('after_update', step)
                    return result
            setattr(core, method_name, call)
        return core

    frozen.factory = capturing_factory
    try:
        if condition == 'unseen_high_frequency':
            row, replay, diagnostics = engine.run_dynamic_case(payload, schedule, model)
        elif condition == 'unseen_low_frequency':
            row, replay, diagnostics = engine.run_original_case(payload, schedule, model)
        elif condition == 'known_low_frequency':
            row, replay, diagnostics = engine.run_original_case(payload, schedule, model)
        else:
            raise ValueError(condition)
    finally:
        frozen.factory = old_factory
    digest_input = strip_diagnostic_fields(
        semantic_projection({'row': row, 'replay': replay,
                             'decision_log': diagnostics.get('decisions', []),
                             'controller_state_trace': states}), model)
    return row, replay, diagnostics, sha_bytes(canonical(digest_input)), states


def _reference_function():
    import math
    import numpy as np
    source = subprocess.check_output(['git', 'show',
        f'{BASELINE}:src/spatial_memory/cadence_age.py'], cwd=ROOT, text=True)
    namespace = {'__name__': 'spatial_memory.cadence_age_reference',
                 '__package__': 'spatial_memory', 'np': np, 'math': math}
    exec(compile(source, 'cadence_age_at_840b0e2.py', 'exec'), namespace)
    return namespace['cadence_decision']


def _case_sets():
    import h2_high_frequency_dynamics as engine
    import phase2_mujoco_navigation as navigation
    known = navigation.admitted_worlds()
    unseen = [item[0] for item in engine.source_maps()]
    if len(known) != 36 or len(unseen) != 36:
        raise RuntimeError(f'Unexpected source map counts known={len(known)}, unseen={len(unseen)}')
    return {
        'known_low_frequency': [(p, s) for p in known for s in (0, 1)],
        'unseen_low_frequency': [(p, s) for p in unseen for s in (0, 1)],
        'unseen_high_frequency': [(p, s) for p in unseen for s in (0, 1)],
    }


def run_parity():
    import spatial_memory.cadence_age as cadence
    import spatial_memory.cadence_age_optimized_v1 as optimized_module
    OUT.mkdir(parents=True, exist_ok=True)
    binding = OUT / 'parity_binding.json'
    if not binding.exists():
        value = {'protocol': 'h2-optimization-semantic-parity-v1',
                 'baseline_commit': BASELINE,
                 'baseline_cadence_source_sha256': sha_bytes(subprocess.check_output(
                     ['git', 'show', f'{BASELINE}:src/spatial_memory/cadence_age.py'], cwd=ROOT)),
                 'optimized_cadence_source_sha256': sha(ROOT / 'src/spatial_memory/cadence_age.py'),
                 'optimization_models': list(OPTIMIZED),
                 'conditions': {'known_low_frequency': 72, 'unseen_low_frequency': 72,
                                'unseen_high_frequency': 72},
                 'semantic_fields': 'H2 row/replay/decision and model-owned state at initialization, each decision and each update; diagnostic-only cadence score fields excluded; runtime-only fields excluded',
                 'maps_not_generated': True}
        binding.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')
    reference = _reference_function()
    optimized = optimized_module.cadence_decision
    cases = _case_sets()
    journal = OUT / 'semantic_parity_journal.jsonl'
    complete = load_journal(journal, lambda r: (r['condition'], r['model_id'],
                                                 r['map_identity'], r['schedule'], r['revision']))
    expected = len(OPTIMIZED) * sum(len(x) for x in cases.values()) * 2
    started = time.monotonic()
    total = len(complete)
    for condition, items in cases.items():
        for model in OPTIMIZED:
            for payload, schedule in items:
                for revision, function in (('baseline', reference), ('optimized', optimized)):
                    key = (condition, model, payload['identity'], int(schedule), revision)
                    if key in complete:
                        continue
                    cadence.cadence_decision = function
                    row, replay, diagnostics, digest, states = capture_states(
                        __import__('h2_high_frequency_dynamics'), model, payload,
                        schedule, condition)
                    record = {'condition': condition, 'model_id': model,
                              'map_identity': payload['identity'], 'schedule': int(schedule),
                              'revision': revision, 'semantic_sha256': digest,
                              'state_snapshots': len(states), 'success': bool(row['success']),
                              'goal_step': row.get('goal_step'),
                              'paid_observations': int(row.get('observation_count', 0)),
                              'elapsed_steps': int(row.get('elapsed_steps', 0)),
                              'unwanted_contacts': int(row.get('g1_unwanted_contact_pairs', 0))}
                    append_journal(journal, record)
                    complete[key] = record
                    total += 1
                    if total % 24 == 0 or total == expected:
                        elapsed = time.monotonic() - started
                        print(f'parity cases {total}/{expected} ({100*total/expected:.1f}%), '
                              f'elapsed={elapsed/60:.1f}m', flush=True)
    cadence.cadence_decision = optimized
    by_case = {}
    for rec in complete.values():
        key = (rec['condition'], rec['model_id'], rec['map_identity'], rec['schedule'])
        by_case.setdefault(key, {})[rec['revision']] = rec
    rows = []
    for key, pair in sorted(by_case.items()):
        old, new = pair.get('baseline'), pair.get('optimized')
        if old is None or new is None:
            status = 'INCOMPLETE'
        else:
            status = 'PASS_EXACT_SEMANTIC_PARITY' if old['semantic_sha256'] == new['semantic_sha256'] else 'FAIL_SEMANTIC_PARITY'
        rows.append({'condition':key[0], 'model_id':key[1], 'map_identity':key[2], 'schedule':key[3],
                     'baseline_sha256':None if old is None else old['semantic_sha256'],
                     'optimized_sha256':None if new is None else new['semantic_sha256'],
                     'baseline_success':None if old is None else old['success'],
                     'optimized_success':None if new is None else new['success'],
                     'baseline_goal_step':None if old is None else old['goal_step'],
                     'optimized_goal_step':None if new is None else new['goal_step'],
                     'status':status})
    with (OUT/'semantic_parity_validation.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]) if rows else ['status'])
        writer.writeheader(); writer.writerows(rows)
    failures = [r for r in rows if r['status'] != 'PASS_EXACT_SEMANTIC_PARITY']
    summary = {'expected_case_pairs': expected//2, 'paired_cases_written': len(rows),
               'passing_pairs': len(rows)-len(failures), 'failing_or_incomplete': failures,
               'status': 'PASS' if not failures and len(rows)==expected//2 else 'FAIL'}
    summary_path = OUT/'semantic_parity_summary.json'
    if summary_path.exists():
        raise FileExistsError(summary_path)
    summary_path.write_text(json.dumps(summary, sort_keys=True, indent=2) + '\n')
    print(json.dumps(summary, sort_keys=True), flush=True)
    if summary['status'] != 'PASS':
        raise RuntimeError('Full optimization semantic parity did not pass')


def run_timing(resume: bool = False):
    """Same-session 5-repetition cost run for optimized arms and anchors."""
    import importlib.metadata
    import h2_high_frequency_dynamics as engine
    import spatial_memory.cadence_age as cadence
    import spatial_memory.cadence_age_optimized_v1 as optimized_module
    from run_h2_controlled_compute_benchmark import semantic_sha, _quantile

    parity_summary = json.loads((OUT/'semantic_parity_summary.json').read_text())
    if parity_summary.get('status') != 'PASS':
        raise RuntimeError('Full 216-case semantic parity must pass before timing')
    maps, cases = engine.source_maps(), _case_sets()['unseen_high_frequency']
    if len(maps) != 36 or len(cases) != 72:
        raise RuntimeError('Saved high-frequency map/case matrix changed')
    baseline_fn = _reference_function()
    optimized_fn = optimized_module.cadence_decision
    treatments = (('periodic5', 'baseline', baseline_fn),
                  ('periodic5', 'optimized', optimized_fn),
                  ('age5', 'baseline', baseline_fn),
                  ('age5', 'optimized', optimized_fn),
                  ('periodic4', 'anchor', None),
                  ('age4', 'anchor', None))
    expected = 5 * len(cases) * len(treatments)
    journal = OUT/'episode_timings_journal.jsonl'
    completed = load_journal(journal, lambda r: (r['repetition'], r['case_index'], r['model_id'], r['revision']))
    if completed and not resume:
        raise RuntimeError('Timing journal exists; use --resume with its bound protocol')
    if len(completed) > expected:
        raise RuntimeError('Timing checkpoint exceeds the frozen matrix')
    parity_rows = {}
    with (OUT/'semantic_parity_validation.csv').open(encoding='utf-8') as stream:
        for r in csv.DictReader(stream):
            if r['condition'] == 'unseen_high_frequency':
                parity_rows[(r['model_id'], r['map_identity'], int(r['schedule']))] = r['status']
    if not (OUT/'timing_binding.json').exists():
        package_versions = {}
        for package in ('numpy', 'mujoco', 'pytest', 'pynauty'):
            try: package_versions[package] = importlib.metadata.version(package)
            except importlib.metadata.PackageNotFoundError: package_versions[package] = None
        binding = {'protocol': 'h2-final-reconciliation-controlled-cost-v1',
                   'baseline_commit': BASELINE,
                   'baseline_cadence_source_sha256': sha_bytes(subprocess.check_output(
                       ['git', 'show', f'{BASELINE}:src/spatial_memory/cadence_age.py'], cwd=ROOT)),
                   'optimized_cadence_source_sha256': sha(ROOT/'src/spatial_memory/cadence_age.py'),
                   'anchors': ['periodic4', 'age4'], 'optimized_models': ['periodic5', 'age5'],
                   'case_count_per_model_repetition': 72, 'repetitions': 5,
                   'randomized_order_seed': 2026111501, 'map_source': 'saved H2 high-frequency maps',
                   'timing_scope': 'initialization + observation decision + spatial memory update; using the existing H2 perf_counter_ns wrappers',
                   'excluded': ['sensor acquisition', 'emergency sensing', 'navigation planning', 'collision shield', 'environment update', 'replay logging', 'I/O'],
                   'python': sys.version, 'python_executable': sys.executable,
                   'platform': platform.platform(), 'machine': platform.machine(),
                   'packages': package_versions, 'bound_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
        binding_path = OUT/'timing_binding.json'
        with binding_path.open('x') as stream:
            json.dump(binding, stream, sort_keys=True, indent=2); stream.write('\n')
    case_index = {(p['identity'], s): (i, p, s) for i, (p, s) in enumerate(cases, 1)}
    cases_all = list(cases)
    start = time.monotonic()
    for rep in range(1, 6):
        tasks = [(ci, p, s, model, revision, fn)
                 for ci, (p, s) in enumerate(cases_all, 1)
                 for model, revision, fn in treatments]
        random.Random(2026111501 + rep).shuffle(tasks)
        for order_index, (ci, payload, schedule, model, revision, function) in enumerate(tasks, 1):
            key = (rep, ci, model, revision)
            if key in completed:
                continue
            if model in OPTIMIZED:
                cadence.cadence_decision = function
            t0 = time.perf_counter_ns()
            row, replay, diagnostics = engine.run_dynamic_case(payload, schedule, model)
            wall_ns = time.perf_counter_ns() - t0
            cadence.cadence_decision = optimized_fn
            timing = diagnostics.get('timing_ns', {})
            for field in ('initialization', 'decision', 'update'):
                if not isinstance(timing.get(field), list):
                    raise RuntimeError(f'Missing {field} timing samples for {model}')
            init = sum(timing['initialization']); decision = sum(timing['decision']); update = sum(timing['update'])
            sem_hash = semantic_sha(row, replay)
            parity_status = (parity_rows.get((model, payload['identity'], int(schedule)))
                             if revision != 'anchor' else 'NOT_APPLICABLE_ANCHOR')
            if revision != 'anchor' and parity_status != 'PASS_EXACT_SEMANTIC_PARITY':
                raise RuntimeError(f'No paired parity PASS for {(model, payload["identity"], schedule)}')
            samples = timing['decision']
            record = {'repetition': rep, 'order_index': order_index, 'case_index': ci,
                      'map_identity': payload['identity'], 'map_family': payload['mechanism'],
                      'schedule': int(schedule), 'seed': 42, 'model_id': model,
                      'revision': revision, 'success': bool(row['success']),
                      'goal_step': row.get('goal_step'), 'paid_observations': int(row['observation_count']),
                      'elapsed_steps': int(row['elapsed_steps']),
                      'initialization_ns': init, 'decision_ns': decision,
                      'memory_update_ns': update, 'total_model_computation_ns': init+decision+update,
                      'decision_calls': len(samples),
                      'decision_mean_ns_per_call': statistics.mean(samples) if samples else 0,
                      'decision_median_ns_per_call': statistics.median(samples) if samples else 0,
                      'decision_p95_ns_per_call': _quantile(samples, .95) if samples else 0,
                      'decision_p99_ns_per_call': _quantile(samples, .99) if samples else 0,
                      'case_wall_ns': wall_ns, 'semantic_sha256': sem_hash,
                      'parity_validation_status': parity_status}
            append_journal(journal, record); completed[key] = record
            cadence.cadence_decision = optimized_fn
            if len(completed) % 36 == 0 or len(completed) == expected:
                elapsed = time.monotonic() - start
                rate = (len(completed) - 0) / max(elapsed, 1e-9)
                eta = (expected-len(completed))/max(rate, 1e-9)
                print(f'timing {len(completed)}/{expected} ({100*len(completed)/expected:.1f}%), '
                      f'rep={rep}/5 elapsed={elapsed/60:.1f}m ETA={eta/60:.1f}m', flush=True)
    cadence.cadence_decision = optimized_fn
    ordered = sorted(completed.values(), key=lambda r:(r['model_id'],r['revision'],r['repetition'],r['case_index']))
    fields = list(ordered[0])
    with (OUT/'episode_timings.csv').open('w', newline='', encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(ordered)
    decision_rows=[]
    for model,revision,_fn in treatments:
        group=[r for r in ordered if r['model_id']==model and r['revision']==revision]
        values=[r['decision_mean_ns_per_call'] for r in group]
        compute=[r['total_model_computation_ns']/1e6 for r in group]
        if not group: continue
        decision_rows.append({'model_id':model,'revision':revision,'episodes':len(group),
            'mean_compute_ms':statistics.mean(compute),'median_compute_ms':statistics.median(compute),
            'compute_sd_ms':statistics.stdev(compute) if len(compute)>1 else 0,
            'compute_p95_ms':_quantile(compute,.95),'compute_p99_ms':_quantile(compute,.99),
            'mean_decision_call_us':statistics.mean(values)/1000,
            'median_decision_call_us':statistics.median(values)/1000,
            'decision_call_p95_us':_quantile(values,.95)/1000,
            'decision_call_p99_us':_quantile(values,.99)/1000,
            'speedup_vs_baseline':None})
    lookup={(r['model_id'],r['revision']):r for r in decision_rows}
    for model in OPTIMIZED:
        base=lookup[(model,'baseline')]['mean_compute_ms']; new=lookup[(model,'optimized')]['mean_compute_ms']
        lookup[(model,'optimized')]['speedup_vs_baseline']=base/new if new else None
    with (OUT/'decision_microbenchmark.csv').open('w',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(decision_rows[0]));writer.writeheader();writer.writerows(decision_rows)
    if len(ordered)!=expected:
        raise RuntimeError(f'Expected {expected} timing rows, got {len(ordered)}')
    print('timing complete: '+json.dumps(decision_rows,sort_keys=True),flush=True)


def run_b_age_correction(resume: bool = False):
    """Create corrected full replays for the two unseen conditions only."""
    import importlib.metadata
    import h2_high_frequency_dynamics as engine
    import h2_comprehensive_adapters as adapters
    from run_h2_controlled_compute_benchmark import semantic_sha

    target = OUT/'corrected_b_age_unseen_v1'
    journal = target/'journal.jsonl'
    expected = 36*2*2
    completed = load_journal(journal, lambda r:(r['condition'],r['map_identity'],r['schedule']))
    if completed and not resume:
        raise RuntimeError('B+Age correction journal exists; use --resume')
    maps = [x[0] for x in engine.source_maps()]
    if len(maps)!=36:
        raise RuntimeError('Expected 36 previously saved unseen maps')
    target.mkdir(parents=True,exist_ok=True)
    source_paths = [ROOT/'scripts/h2_comprehensive_adapters.py',
                    ROOT/'scripts/h2_high_frequency_dynamics.py',
                    ROOT/'scripts/h2_final_common.py',
                    ROOT/'results/phase2_mujoco/h2_comprehensive_benchmark_v1/protocol/model_registry.json',
                    ROOT/'results/phase2_mujoco/h2_comprehensive_benchmark_v1/binding.json']
    if not (target/'binding.json').exists():
        versions={}
        for name in ('numpy','mujoco','pynauty'):
            try: versions[name]=importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError: versions[name]=None
        binding={'protocol':'h2-b-age-unseen-correction-v1',
                 'model_definition':{'model_id':'b_age','persistence':True,'evi':False,
                                     'scheduler':'registered Age-based schedule'},
                 'conditions':['unseen_low_frequency','unseen_high_frequency'],
                 'cases_per_condition':72,'total_episodes':144,'maps_not_generated':True,
                 'maps':[{'identity':p['identity'],'sha256':h} for p,h in engine.source_maps()],
                 'source_hashes':{p.relative_to(ROOT).as_posix():sha(p) for p in source_paths},
                 'python':sys.version,'python_executable':sys.executable,
                 'platform':platform.platform(),'machine':platform.machine(),'packages':versions,
                 'old_mislabeled_records_preserved_and_excluded':True}
        with (target/'binding.json').open('x') as stream:
            json.dump(binding,stream,sort_keys=True,indent=2);stream.write('\n')
    started=time.monotonic();done=len(completed)
    for condition in ('unseen_low_frequency','unseen_high_frequency'):
        engine_condition='original' if condition=='unseen_low_frequency' else 'high_frequency'
        for mi,payload in enumerate(maps,1):
            for schedule in (0,1):
                key=(condition,payload['identity'],schedule)
                if key in completed:continue
                row,replay,diagnostics=adapters.run_case(payload,schedule,'b_age',engine_condition)
                if int(row['elapsed_steps'])+1 != len(replay['steps']):
                    raise RuntimeError(f'B+Age replay step count mismatch at {key}')
                if any(not step.get('spatial_memory_ternary_packed_2bit_base64') for step in replay['steps']):
                    raise RuntimeError(f'Missing full step memory at {key}')
                record={'schema':'h2_b_age_corrected_unseen_v1','model_id':'b_age',
                        'model_definition':{'persistence':True,'evi':False},
                        'condition':condition,'map_identity':payload['identity'],'map_index':mi,
                        'schedule':schedule,'seed':42,'row':row,'replay':replay,
                        'diagnostics':diagnostics,
                        'semantic_sha256':semantic_sha(row,replay)}
                rel=f'{condition}/{payload["identity"].replace(":","_")}_s{schedule}_seed42.json.gz'
                path=target/'episodes'/rel;path.parent.mkdir(parents=True,exist_ok=True)
                raw=canonical(record);packed=gzip.compress(raw,mtime=0);tmp=path.with_suffix(path.suffix+'.tmp')
                with tmp.open('xb') as stream:
                    stream.write(packed);stream.flush();os.fsync(stream.fileno())
                os.replace(tmp,path)
                event={'event':'episode_committed','condition':condition,
                       'model_id':'b_age','path':path.relative_to(OUT).as_posix(),
                       'map_identity':payload['identity'],'schedule':schedule,'seed':42,
                       'bytes':len(packed),'sha256':sha_bytes(packed),
                       'semantic_sha256':record['semantic_sha256'],
                       'success':bool(row['success']),'steps':int(row['elapsed_steps']),
                       'observations':int(row['observation_count']),
                       'unwanted_contacts':int(row.get('g1_unwanted_contact_pairs',0)),
                       'travel_distance_m':float(row.get('travel_distance_m',0.0))}
                append_journal(journal,event);completed[key]=event;done+=1
                if done%12==0 or done==expected:
                    elapsed=time.monotonic()-started
                    print(f'correct B+Age {done}/{expected} ({100*done/expected:.1f}%), elapsed={elapsed/60:.1f}m',flush=True)
    records=list(completed.values())
    if len(records)!=expected:
        raise RuntimeError(f'Expected {expected} corrected unseen B+Age cases, got {len(records)}')
    summary={'episodes':len(records),'by_condition':{c:sum(r['condition']==c for r in records)
              for c in ('unseen_low_frequency','unseen_high_frequency')},
             'successes':sum(bool(r['success']) for r in records),
             'unwanted_contacts':sum(int(r.get('unwanted_contacts',0)) for r in records),
             'journal_sha256':sha(journal),'binding_sha256':sha(target/'binding.json'),
             'status':'PASS'}
    summary_path=target/'summary.json'
    if not summary_path.exists():
        with summary_path.open('x') as stream:json.dump(summary,stream,sort_keys=True,indent=2);stream.write('\n')
    print(json.dumps(summary,sort_keys=True),flush=True)


def run_all_model_timing(resume: bool = False):
    """Remeasure all 54 models after the anchors showed material drift."""
    import importlib.metadata
    import h2_high_frequency_dynamics as engine
    import spatial_memory.cadence_age as cadence
    import spatial_memory.cadence_age_optimized_v1 as optimized_module
    import run_h2_controlled_compute_benchmark as prior_runner

    target=OUT/'all_model_timing_v1'
    target.mkdir(parents=True,exist_ok=True)
    journal=target/'journal.jsonl'
    csv_path=OUT/'all_model_episode_timings.csv'
    maps,cases=prior_runner.maps_and_cases()
    models=prior_runner.model_ids()
    if len(models)!=54 or len(cases)!=72:
        raise RuntimeError('Frozen all-model H2 matrix mismatch')
    historical=prior_runner.historical_index()
    expected=5*len(cases)*len(models)
    complete=load_journal(journal,lambda r:(r['repetition'],r['case_index'],r['model_id']))
    if complete and not resume:
        raise RuntimeError('All-model timing journal exists; use --resume')
    if len(complete)>expected:
        raise RuntimeError('All-model timing journal exceeds frozen matrix')
    source_paths=[ROOT/'scripts/run_h2_final_benchmark_reconciliation.py',
                  ROOT/'scripts/run_h2_controlled_compute_benchmark.py',
                  ROOT/'scripts/h2_high_frequency_dynamics.py',
                  ROOT/'scripts/h2_comprehensive_adapters.py',
                  ROOT/'scripts/h2_final_common.py',
                  ROOT/'src/spatial_memory/cadence_age.py',
                  ROOT/'results/phase2_mujoco/h2_comprehensive_benchmark_v1/protocol/model_registry.json']
    binding_path=target/'binding.json'
    if not binding_path.exists():
        versions={}
        for name in ('numpy','mujoco','pytest','pynauty'):
            try:versions[name]=importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:versions[name]=None
        binding={'protocol':'h2-final-reconciliation-all-model-controlled-cost-v1',
                 'matrix':{'models':list(models),'model_count':54,'maps':36,
                           'schedules':[0,1],'cases_per_repetition':3888,
                           'repetitions':5,'episodes':19440,'seed':42,
                           'max_steps':80,'observation_budget':20,'cell_size_m':0.75,
                           'workers':1},
                 'random_order_seed':prior_runner.ORDER_SEED,
                 'optimized_sources':{'src/spatial_memory/cadence_age.py':sha(ROOT/'src/spatial_memory/cadence_age.py')},
                 'timing_scope':'Initialization + observation decision + spatial-memory refresh only',
                 'timing_exclusions':['sensor acquisition','emergency sensing','navigation planning',
                    'selected-action collision shield','environment update','scene update',
                    'replay capture','file I/O'],
                 'old_historical_index_sha256':sha(prior_runner.PRIOR_INDEX),
                 'source_hashes':{p.relative_to(ROOT).as_posix():sha(p) for p in source_paths},
                 'map_hashes':[{'identity':p['identity'],'sha256':h} for p,h in maps],
                 'runtime':{'python':sys.version,'python_executable':sys.executable,
                    'platform':platform.platform(),'machine':platform.machine(),
                    'logical_cpus':__import__('os').cpu_count(),'packages':versions},
                 'reason_for_additional_matrix':'Same-session P4/A4 anchors differed from the immediately preceding 19,440-episode timing batch by >10%; a 54-model same-session authoritative cost matrix is needed before combining costs.'}
        with (target/'binding.json').open('x') as stream:
            json.dump(binding,stream,sort_keys=True,indent=2);stream.write('\n')
    else:
        bound=json.loads(binding_path.read_text(encoding='utf-8'))
        amendment=target/'binding_amendment_2.json'
        pointer=target/'active_binding.json'
        if amendment.exists():
            amended=json.loads(amendment.read_text(encoding='utf-8'))
            ptr=json.loads(pointer.read_text(encoding='utf-8')) if pointer.exists() else {}
            prior_amendment=target/'binding_amendment_1.json'
            if (amended.get('parent_binding_sha256')!=sha(prior_amendment) or
                ptr.get('path')!=amendment.name or ptr.get('sha256')!=sha(amendment) or
                amended.get('source_hashes',{}).get('scripts/run_h2_final_benchmark_reconciliation.py')!=
                    sha(ROOT/'scripts/run_h2_final_benchmark_reconciliation.py') or
                amended.get('source_hashes',{}).get('src/spatial_memory/cadence_age_optimized_v1.py')!=
                    sha(ROOT/'src/spatial_memory/cadence_age_optimized_v1.py')):
                raise RuntimeError('All-model timing amendment/source commitment validation failed')
        elif (target/'binding_amendment_1.json').exists():
            first=json.loads((target/'binding_amendment_1.json').read_text(encoding='utf-8'))
            ptr=json.loads(pointer.read_text(encoding='utf-8')) if pointer.exists() else {}
            if (ptr.get('path')!='binding_amendment_1.json' or ptr.get('sha256')!=sha(target/'binding_amendment_1.json') or
                first.get('source_hashes',{}).get('scripts/run_h2_final_benchmark_reconciliation.py')!=
                    sha(ROOT/'scripts/run_h2_final_benchmark_reconciliation.py')):
                raise RuntimeError('All-model timing first amendment validation failed')
            for name,digest in bound.get('source_hashes',{}).items():
                if name=='scripts/run_h2_final_benchmark_reconciliation.py':continue
                if name=='src/spatial_memory/cadence_age.py':continue
                if sha(ROOT/name)!=digest:raise RuntimeError(f'All-model timing source hash changed without amendment: {name}')
        else:
            for name,digest in bound.get('source_hashes',{}).items():
                if sha(ROOT/name)!=digest:
                    raise RuntimeError(f'All-model timing source hash changed without amendment: {name}')
    maps_by_index={i:(p,s) for i,(_mi,p,s) in enumerate(cases,1)}
    tasks=[(ci,p,s,model) for ci,(_mi,p,s) in enumerate(cases,1) for model in models]
    start=time.monotonic();initial_count=len(complete);last_snapshot=start;last_progress=start
    last_runtime_snapshot=''
    def runtime_snapshot(event):
        import datetime,subprocess
        snapshot={'event':event,'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  'load_average':__import__('os').getloadavg() if hasattr(__import__('os'),'getloadavg') else None}
        for command,key,timeout in ((['vm_stat'],'vm_stat',5),(['uptime'],'uptime',5),
                                    (['ps','-A','-o','%cpu=,comm='],'top_processes',10)):
            try:snapshot[key]=subprocess.run(command,text=True,capture_output=True,timeout=timeout,check=True).stdout.strip()
            except Exception as exc:snapshot[key+'_error']=repr(exc)
        return snapshot
    def save_snapshot(event):
        path=target/'runtime_observations.jsonl'
        with path.open('a',encoding='utf-8') as stream:
            stream.write(json.dumps(runtime_snapshot(event),sort_keys=True)+'\n');stream.flush()
            import os;os.fsync(stream.fileno())
    if not (target/'runtime_observations.jsonl').exists():save_snapshot('run_start')
    elif resume:save_snapshot('run_resume')
    unexpected=[]
    for rep in range(1,6):
        ordered=tasks.copy();random.Random(prior_runner.ORDER_SEED+rep).shuffle(ordered)
        for order_index,(ci,payload,schedule,model) in enumerate(ordered,1):
            key=(rep,ci,model)
            if key in complete:continue
            expected_digest,_=prior_runner.historical_semantic(model,payload['identity'],schedule,historical)
            old_cadence_function=cadence.cadence_decision
            cadence.cadence_decision=optimized_module.cadence_decision if model in OPTIMIZED else old_cadence_function
            try:
                t0=time.perf_counter_ns()
                row,replay,diagnostics=prior_runner.run_one(payload,schedule,model)
                wall=time.perf_counter_ns()-t0
            finally:
                cadence.cadence_decision=old_cadence_function
            actual_digest=prior_runner.semantic_sha(row,replay)
            record=prior_runner._timing_row(rep,order_index,ci,payload,schedule,model,
                row,diagnostics,actual_digest,expected_digest,wall)
            record['revision']='optimized_current'
            append_journal(journal,record);complete[key]=record
            if not record['parity_match'] and model!='b_age':
                unexpected.append({'model_id':model,'case_index':ci,'map_identity':payload['identity'],
                                   'schedule':schedule,'semantic_sha256':actual_digest,
                                   'historical_sha256':expected_digest})
                raise RuntimeError(f'Unexpected all-model semantic divergence: {unexpected[-1]}')
            if len(complete)%72==0 or len(complete)==expected:
                rows=sorted(complete.values(),key=lambda r:(r['repetition'],r['order_index']))
                fields=list(rows[0])
                with csv_path.open('w',newline='',encoding='utf-8') as stream:
                    writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(rows)
            now=time.monotonic()
            if len(complete)%108==0 or now-last_progress>=300 or len(complete)==expected:
                elapsed=now-start;new_done=len(complete)-initial_count
                eta=(expected-len(complete))*elapsed/max(new_done,1)
                print(f'all-model timing {len(complete)}/{expected} ({100*len(complete)/expected:.1f}%), '
                      f'rep={rep}/5 elapsed={elapsed/60:.1f}m ETA={eta/60:.1f}m',flush=True)
                last_progress=now
            if now-last_snapshot>=900:
                save_snapshot('15_minute');last_snapshot=now
    if len(complete)!=expected:raise RuntimeError(f'Incomplete all-model matrix: {len(complete)}/{expected}')
    save_snapshot('run_complete')
    expected_bad=sum(not r['parity_match'] and r['model_id']=='b_age' for r in complete.values())
    unexpected_count=sum(not r['parity_match'] and r['model_id']!='b_age' for r in complete.values())
    result={'episodes':len(complete),'models':len(models),'repetitions':5,
            'expected_b_age_historical_mismatch_records':expected_bad,
            'unexpected_semantic_mismatches':unexpected_count,
            'status':'PASS' if len(complete)==expected and expected_bad==360 and unexpected_count==0 else 'FAIL',
            'journal_sha256':sha(journal),'csv_sha256':sha(csv_path)}
    with (target/'summary.json').open('x') as stream:
        json.dump(result,stream,sort_keys=True,indent=2);stream.write('\n')
    print(json.dumps(result,sort_keys=True),flush=True)


def smoke_all_models():
    import h2_high_frequency_dynamics as engine
    import run_h2_controlled_compute_benchmark as runner
    maps,cases=runner.maps_and_cases();models=runner.model_ids();historical=runner.historical_index()
    payload,schedule=cases[0][1],cases[0][2]
    results=[]
    for model in models:
        expected,_=runner.historical_semantic(model,payload['identity'],schedule,historical)
        row,replay,diagnostics=runner.run_one(payload,schedule,model)
        actual=runner.semantic_sha(row,replay)
        match=actual==expected
        results.append({'model_id':model,'semantic_match':match,
                        'expected_historical_nonparity':model=='b_age',
                        'success':bool(row['success']),'elapsed_steps':int(row['elapsed_steps']),
                        'timing_keys':sorted(diagnostics.get('timing_ns',{}))})
    unexpected=[r for r in results if not r['semantic_match'] and r['model_id']!='b_age']
    if unexpected:
        raise RuntimeError(f'Unexpected all-model smoke mismatches: {unexpected}')
    if sum(not r['semantic_match'] for r in results)!=1:
        raise RuntimeError('Smoke must have only the declared historical B+Age semantic mismatch')
    path=OUT/'all_model_timing_smoke.json'
    if path.exists():raise FileExistsError(path)
    path.write_text(json.dumps({'models':len(models),'cases_per_model':1,
       'expected_b_age_mismatch':True,'unexpected_mismatches':0,'results':results,
       'status':'PASS'},sort_keys=True,indent=2)+'\n')
    print('all-model smoke PASS: 53 exact historical semantic matches; one declared old B+Age mismatch.',flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('parity', 'timing', 'correct-b-age', 'timing-all', 'smoke-all'))
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    if args.command == 'parity':
        run_parity()
    elif args.command == 'timing':
        run_timing(args.resume)
    elif args.command == 'correct-b-age':
        run_b_age_correction(args.resume)
    elif args.command == 'timing-all':
        run_all_model_timing(args.resume)
    elif args.command == 'smoke-all':
        smoke_all_models()


if __name__ == '__main__':
    main()
