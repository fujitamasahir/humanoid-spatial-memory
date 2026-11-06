"""Run paired baselines from a saved configuration; no external services."""
import argparse
import csv
import hashlib
from importlib.metadata import distributions
import json
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from spatial_memory.scenarios import generate_scenario, scenario_hash, scenario_record
from spatial_memory.evaluation import run_episode
from spatial_memory.visualization import save_figure


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=ROOT / 'configs/development_phase1_1.json')
    parser.add_argument('--output', type=Path, default=ROOT / 'results/phase1_1/development')
    parser.add_argument("--budgets", type=int, nargs="+", help="Separate diagnostic step budgets")
    parser.add_argument("--no-figures", action="store_true")
    args = parser.parse_args()
    raw = args.config.read_bytes()
    config = json.loads(raw)
    if config['max_steps'] < 1 or config['observation_cost'] < 0:
        raise ValueError('Invalid budget or cost')
    if not config['seeds'] or any(not isinstance(s, int) or s < 0 for s in config['seeds']):
        raise ValueError('Seeds must be nonnegative integers')
    if config['split'] != 'development':
        raise ValueError('Held-out execution is reserved for research review')
    budgets = args.budgets or [config['max_steps']]
    if any(b < 1 for b in budgets):
        raise ValueError('Budgets must be positive')
    if args.output.resolve() == (ROOT / 'results/representative').resolve() and args.output.exists():
        raise ValueError('Original representative results are protected; use a new output directory')
    args.output.mkdir(parents=True, exist_ok=True)
    rows, realized, traces = [], [], []
    for template in config['scenarios']:
        for seed in config['seeds']:
            scenario = generate_scenario(template, seed)
            if scenario.split != config['split']:
                raise ValueError('Do not mix development and held-out scenarios')
            fingerprint = scenario_hash(scenario)
            realized.append(dict(seed=seed, scenario_sha256=fingerprint,
                                 scenario=scenario_record(scenario)))
            for budget in budgets:
                episode_config = {**config, 'max_steps': budget}
                for method in ('static', 'periodic'):
                    metrics, frames = run_episode(scenario, episode_config, method, seed)
                    metrics['scenario_sha256'] = fingerprint
                    rows.append(metrics)
                    traces.append(dict(scenario=scenario.name, seed=seed, method=method,
                        max_steps=budget, frames=[dict(step=f['step'], position=f['position'],
                        next_target=f['planned'][1] if len(f['planned']) > 1 else None,
                        errors=f['errors']) for f in frames]))
                    if seed == config['seeds'][0] and not args.no_figures:
                        for step in sorted({0, min(4, len(frames)-1), len(frames)-1}):
                            save_figure(scenario, frames[step], args.output /
                                f'{scenario.name}_{method}_budget{budget}_step{step}.png')
    with (args.output / 'episodes.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
    summary = {}
    for method in ('static', 'periodic'):
        paired = [r for r in rows if r['method'] == method]
        summary[method] = {'episodes': len(paired), 'success_rate':
            sum(r['success'] for r in paired)/len(paired)}
    git = ['git', '-c', f'safe.directory={ROOT.as_posix()}']
    revision = subprocess.run(git+['rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True)
    status = subprocess.run(git+['status', '--porcelain', '--untracked-files=normal'],
                            cwd=ROOT, capture_output=True, text=True)
    # Include source hash because the generating code may not yet be committed.
    digest = hashlib.sha256()
    paths = sorted((ROOT/'src').rglob('*.py')) + [Path(__file__).resolve()]
    for path in paths:
        digest.update(path.relative_to(ROOT).as_posix().encode())
        digest.update(path.read_bytes())
    payload = dict(config=config, budgets=budgets, realized_scenarios=realized,
        episodes=rows, traces=traces, summary=summary, provenance=dict(
        commit_sha=revision.stdout.strip() if revision.returncode == 0 else None,
        working_tree_dirty=bool(status.stdout.strip()) if status.returncode == 0 else None,
        source_sha256=digest.hexdigest(), config_sha256=hashlib.sha256(raw).hexdigest(),
        method_version='phase1.1-metrics-v1-baselines-unchanged', python=sys.version, platform=platform.platform(),
        installed_packages=dict(sorted((d.metadata['Name'], d.version) for d in distributions()))))
    (args.output / 'results.json').write_text(
        json.dumps(payload, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps(summary, indent=2))
    print(f'Saved {len(rows)} episodes to {args.output}')


if __name__ == '__main__':
    main()
