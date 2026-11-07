"""Predefined development robustness sweeps, not parameter optimization."""
import argparse
import hashlib
import json
import platform
from importlib.metadata import distributions
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from spatial_memory.evaluation import run_episode
from spatial_memory.robustness import FAMILIES, generate_robustness, truth_audit, episode_config
from spatial_memory.scenarios import scenario_hash, scenario_record
from run_adaptive_experiment import summarize, write_csv, write_json_report, validate_config


def validate(config):
    # Reuse common baseline validation without invoking older scenario generation.
    validate_config({**config, 'scenarios': [dict(name=f, split='development') for f in config['families']]})
    if set(config['families']) != set(FAMILIES) or len(config['seeds']) != len(set(config['seeds'])):
        raise ValueError('Require all families and distinct seeds')
    if any(s.get('purpose') != 'robustness' for s in config['settings']):
        raise ValueError('No tuning or selected winners in this runner')


def protect_output(output):
    for relative in ('results/representative', 'results/phase1_1', 'results/phase1_2'):
        old = (ROOT/relative).resolve()
        if output == old or old in output.parents or output in old.parents:
            raise ValueError('Historical artifacts are protected')


def run(config, figure_output=None):
    validate(config)
    rows, realizations, traces = [], [], []
    for family in config['families']:
        for seed in config['seeds']:
            for setting in config['settings']:
                scenario = generate_robustness(family, seed, setting.get('timing', 0),
                                               setting.get('dwell_shift', 0))
                audit = truth_audit(scenario, config['max_steps'])
                fingerprint = scenario_hash(scenario)
                realizations.append(dict(family=family, seed=seed, setting=setting['name'],
                    scenario_sha256=fingerprint, scenario=scenario_record(scenario), topology=audit))
                cfg = episode_config(config, setting)
                for method in config['methods']:
                    metrics, frames = run_episode(scenario, cfg, method, seed)
                    if (figure_output is not None and seed == config['seeds'][0]
                            and setting['name'] == 'reference' and family == 'occluded'):
                        from spatial_memory.visualization import save_figure
                        save_figure(scenario, frames[-1], figure_output/f'occluded_{method}_final.png')
                    granted = [f['step'] for f in frames if f['observation_granted']]
                    # Timing is descriptive, not proof that a changed cell was visible.
                    timing = [dict(event_step=e['step'], action=e['action'],
                        first_observation_delay=next((t-e['step'] for t in granted if t >= e['step']), None))
                        for e in scenario.changes]
                    metrics.update(setting=setting['name'], scenario_sha256=fingerprint,
                        observation_steps=granted, persistent_observation_timing=timing)
                    rows.append(metrics)
                    traces.append(dict(scenario=family, seed=seed, setting=setting['name'], method=method,
                        frames=[{k: f[k] for k in ('step','position','observation_position',
                        'observation_requested','observation_granted','observation_score',
                        'observation_count','blocked','moved','errors')} for f in frames]))
    summaries = summarize(rows, ('setting','method'))
    for summary in summaries:
        group = [r for r in rows if all(r[k] == summary[k] for k in ('setting','method'))]
        summary.update(contact_free_success_rate=sum(r['contact_free_success'] for r in group)/len(group),
            unique_environments=len({r['scenario_sha256'] for r in group}),
            dynamic_contact_rate=sum(r['dynamic_contacts'] for r in group)/sum(r['elapsed_steps'] for r in group),
            budget_exhaustion_rate=sum(r['budget_exhausted'] for r in group)/len(group))
        for key in ('common_horizon_stale_map_errors', 'common_horizon_missed_persistent_changes'):
            summary[key+'_mean'] = sum(r[key] for r in group)/len(group)
    return dict(config=config, episodes=rows, summary=summaries,
        scenario_summary=summarize(rows, ('scenario','setting','method')),
        realized_scenarios=realizations, traces=traces)


def provenance(raw):
    paths = sorted((ROOT/'src').rglob('*.py')) + sorted((ROOT/'scripts').glob('*.py'))
    manifest = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes().replace(b'\r\n', b'\n')).hexdigest() for p in paths}
    return dict(commit_sha=subprocess.check_output(['git','rev-parse','HEAD'], text=True).strip(),
        working_tree_dirty=bool(subprocess.check_output(['git','status','--porcelain'], text=True).strip()),
        config_sha256=hashlib.sha256(raw).hexdigest(), source_files_sha256=manifest,
        source_sha256=hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest(),
        python=sys.version, platform=platform.platform(),
        installed_packages=dict(sorted((d.metadata['Name'], d.version) for d in distributions())),
        baseline_version='phase1.2-scheduling-v1')


def figure(summary, path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    names = list(dict.fromkeys(s['setting'] for s in summary))
    fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
    for method in ('static','periodic','age','uncertainty'):
        values = [next(s for s in summary if s['setting']==name and s['method']==method) for name in names]
        axes[0].plot(names, [v['success_rate'] for v in values], marker='.', label=method)
        axes[1].plot(names, [v['contact_free_success_rate'] for v in values], marker='.', label=method)
    axes[0].set_ylabel('Goal completion rate')
    axes[1].set_ylabel('Contact-free completion rate')
    axes[0].legend(ncol=4)
    axes[1].tick_params(axis='x', rotation=65)
    fig.suptitle('Development-only one-factor sweeps; shared reference, no tuning')
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=ROOT/'configs/development_phase1_3.json')
    parser.add_argument('--output', type=Path, default=ROOT/'results/phase1_3/development')
    parser.add_argument('--no-figures', action='store_true')
    args = parser.parse_args()
    raw = args.config.read_bytes()
    cfg = json.loads(raw)
    output = args.output.resolve()
    protect_output(output)
    validate(cfg)
    output.mkdir(parents=True, exist_ok=True)
    payload = run(cfg, None if args.no_figures else output)
    payload['provenance'] = provenance(raw)
    output.mkdir(parents=True, exist_ok=True)
    for key in ('episodes','summary','scenario_summary'):
        write_csv(output/(key+'.csv'), payload[key])
    write_json_report(output/'results.json', payload)
    if not args.no_figures:
        figure(payload['summary'], output/'robustness.png')
    for s in payload['summary']:
        print(f"{s['setting']:16} {s['method']:12} {s['successes']}/{s['episodes']} contact-free={s['contact_free_success_rate']:.3f} observations={s['observation_count_mean']:.2f}")


if __name__ == '__main__':
    main()
