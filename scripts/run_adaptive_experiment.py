"""Paired development-only adaptive schedule comparison; no held-out execution."""
import argparse
from collections import Counter
import csv
import hashlib
from importlib.metadata import distributions
import json
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from spatial_memory.evaluation import run_episode
from spatial_memory.scenarios import generate_scenario, scenario_hash, scenario_record
from spatial_memory.scheduling import AdaptiveParameters
from spatial_memory.visualization import save_figure, save_observation_tradeoff


def summarize(rows, keys):
    groups = {}
    for row in rows:
        group = tuple(row[k] for k in keys)
        groups.setdefault(group, []).append(row)
    summaries = []
    numeric = ('elapsed_steps', 'travel_distance', 'blocked_movement_attempts',
               'dynamic_contacts', 'observation_count', 'observation_cost',
               'observation_requests_denied', 'stale_map_errors',
               'false_persistent_occupancy_updates', 'missed_persistent_changes',
               'final_stale_map_errors', 'final_false_persistent_occupancy_updates',
               'final_missed_persistent_changes')
    for group, episodes in groups.items():
        successes = [r for r in episodes if r['success']]
        summary = dict(zip(keys, group))
        summary.update(episodes=len(episodes), successes=len(successes),
            success_rate=len(successes)/len(episodes),
            successful_observation_count_mean=(sum(r['observation_count'] for r in successes)
                                               /len(successes) if successes else None),
            failure_reasons=dict(Counter(r['failure_reason'] for r in episodes if not r['success'])))
        for key in numeric:
            summary[key+'_mean'] = sum(r[key] for r in episodes)/len(episodes)
        summaries.append(summary)
    return summaries


def validate_config(config):
    if config['split'] != 'development' or any(t['split'] != 'development' for t in config['scenarios']):
        raise ValueError('Held-out execution is reserved for research review')
    if not config['scenarios'] or not config['seeds']:
        raise ValueError('Scenarios and seeds must be nonempty')
    if any(type(s) is not int or s < 0 for s in config['seeds']):
        raise ValueError('Invalid seeds')
    if config['max_steps'] < 1 or config['observation_cost'] < 0:
        raise ValueError('Invalid deadline or cost')
    if set(config['methods']) != {'static', 'periodic', 'age', 'uncertainty'} or len(config['methods']) != 4:
        raise ValueError('Exactly the four baseline methods are required')
    if len({t['name'] for t in config['scenarios']}) != len(config['scenarios']):
        raise ValueError('Scenario names must be unique')
    settings = config['settings']
    if not settings or len({s['name'] for s in settings}) != len(settings):
        raise ValueError('Settings must have unique names')
    for setting in settings:
        cap = setting['max_observations']
        if cap is not None and (type(cap) is not int or cap < 1):
            raise ValueError('Invalid observation budget')
        if not setting['name'].isalnum():
            raise ValueError('Setting names must be alphanumeric')
    AdaptiveParameters(**config['adaptive'])


def write_csv(path, rows):
    with path.open('w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, sort_keys=True) if isinstance(v, (dict,list,tuple))
                             else v for k,v in row.items()})


def write_json_report(path, payload):
    # Keep bulky machine-readable records on one line each; avoid hundreds of
    # thousands of indentation-only artifact lines in source review.
    sections = []
    for key, value in payload.items():
        if isinstance(value, list):
            encoded = '[\n' + ',\n'.join('    '+json.dumps(item, separators=(',', ':'))
                                         for item in value) + '\n  ]'
        else:
            encoded = json.dumps(value, indent=2).replace('\n', '\n  ')
        sections.append('  '+json.dumps(key)+': '+encoded)
    path.write_text('{\n'+',\n'.join(sections)+'\n}\n', encoding='utf-8', newline='\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=ROOT/'configs/development_phase1_2.json')
    parser.add_argument('--output', type=Path, default=ROOT/'results/phase1_2/development')
    parser.add_argument('--no-figures', action='store_true')
    args = parser.parse_args()
    raw = args.config.read_bytes()
    config = json.loads(raw)
    validate_config(config)
    output = args.output.resolve()
    for preserved in (ROOT/'results/representative', ROOT/'results/phase1_1'):
        preserved = preserved.resolve()
        if output == preserved or preserved in output.parents or output in preserved.parents:
            raise ValueError('Earlier phase artifacts are protected')
    output.mkdir(parents=True, exist_ok=True)
    rows, realizations, traces = [], [], []
    for template in config['scenarios']:
        for seed in config['seeds']:
            scenario = generate_scenario(template, seed)
            fingerprint = scenario_hash(scenario)
            realizations.append(dict(seed=seed, scenario_sha256=fingerprint,
                                     scenario=scenario_record(scenario)))
            for setting in config['settings']:
                episode_config = {**config, 'max_observations':setting['max_observations']}
                for method in config['methods']:
                    metrics, frames = run_episode(scenario, episode_config, method, seed)
                    metrics.update(setting=setting['name'], scenario_sha256=fingerprint)
                    rows.append(metrics)
                    traces.append(dict(scenario=scenario.name, seed=seed, method=method,
                        setting=setting['name'], frames=[{k:f[k] for k in
                        ('step','position','planned','blocked','moved','observation_count',
                         'observation_requested','observation_granted','observation_score','observation_position','errors')}
                        for f in frames]))
                    if seed == config['seeds'][0] and setting['max_observations'] is None and not args.no_figures:
                        save_figure(scenario, frames[-1], output/f'{scenario.name}_{method}_final.png')
    summary = summarize(rows, ('setting','method'))
    by_scenario = summarize(rows, ('scenario','setting','method'))
    write_csv(output/'episodes.csv', rows)
    write_csv(output/'summary.csv', summary)
    write_csv(output/'scenario_summary.csv', by_scenario)
    git = ['git','-c',f'safe.directory={ROOT.as_posix()}']
    revision = subprocess.run(git+['rev-parse','HEAD'],cwd=ROOT,capture_output=True,text=True,check=True)
    status = subprocess.run(git+['status','--porcelain'],cwd=ROOT,capture_output=True,text=True,check=True)
    digest = hashlib.sha256()
    for path in sorted((ROOT/'src').rglob('*.py')) + sorted((ROOT/'scripts').glob('*.py')):
        digest.update(path.relative_to(ROOT).as_posix().encode())
        # Normalize platform line endings for portable source fingerprints.
        digest.update(path.read_bytes().replace(b'\r\n', b'\n'))
    payload = dict(config=config, episodes=rows, summary=summary, scenario_summary=by_scenario,
        realized_scenarios=realizations, traces=traces, provenance=dict(
            commit_sha=revision.stdout.strip(), working_tree_dirty=bool(status.stdout.strip()),
            source_sha256=digest.hexdigest(), config_sha256=hashlib.sha256(raw).hexdigest(),
            method_version='phase1.2-scheduling-v1', python=sys.version,platform=platform.platform(),
            installed_packages=dict(sorted((d.metadata['Name'],d.version) for d in distributions()))))
    write_json_report(output/'results.json', payload)
    if not args.no_figures:
        save_observation_tradeoff(summary, output/'observation_tradeoff.png')
    for row in summary:
        print(f"{row['setting']:10} {row['method']:12} success={row['successes']}/{row['episodes']} "
              f"mean observations={row['observation_count_mean']:.3f}; "
              f"successful mean={row['successful_observation_count_mean']}")
    print(f'Saved {len(rows)} episodes to {output}')


if __name__ == '__main__':
    main()
