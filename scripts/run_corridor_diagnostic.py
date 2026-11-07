"""Timing/prior audit of the existing corridor; no new policy or held-out run."""
from copy import deepcopy
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from spatial_memory.scenarios import generate_scenario, scenario_hash, scenario_record
from spatial_memory.evaluation import run_episode
from run_adaptive_experiment import write_csv, write_json_report
from run_robustness_experiment import provenance


def run():
    cfg = json.loads((ROOT/'configs/development_phase1_2.json').read_text(encoding='utf-8-sig'))
    template = cfg['scenarios'][-1]
    rows, traces, realized = [], [], []
    for removal in (8,9,10,11,12,14):
        changed = deepcopy(template)
        next(e for e in changed['changes'] if e['action']=='remove')['step'] = removal
        scenario = generate_scenario(changed, 7)
        realized.append(dict(scenario_sha256=scenario_hash(scenario), scenario=scenario_record(scenario)))
        for prior_name, flips in [('default',0.3),('slow',0.06),('fast',0.9)]:
            current = deepcopy(cfg)
            current['adaptive']['prior_flips'] = flips
            current['common_horizon_metrics'] = True
            for method in cfg['methods']:
                m, frames = run_episode(scenario,current,method,7)
                m.update(removal_step=removal, prior=prior_name, prior_flips=flips,
                    scenario_sha256=scenario_hash(scenario), observation_steps=[f['step'] for f in frames if f['observation_granted']])
                rows.append(m)
                traces.append(dict(removal_step=removal,prior=prior_name,method=method,
                    frames=[dict(step=f['step'],position=f['position'],
                        observation_position=f['observation_position'], requested=f['observation_requested'],
                        granted=f['observation_granted'], score=f['observation_score'],
                        remembered_gate=int(f['memory'][3,6]),
                        gate_truth=int(f['geometry'][3,6]), blocked=f['blocked']) for f in frames]))
    return dict(episodes=rows,traces=traces,realized_scenarios=realized,
        specification=dict(removal_steps=[8,9,10,11,12,14],prior_flips=[0.3,0.06,0.9],
                           config=cfg,seed=7,independence='six timing worlds; prior/method repeated measures'),
        provenance=provenance((ROOT/'configs/development_phase1_2.json').read_bytes()))


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'results/phase1_3/corridor_diagnostic')
    args = parser.parse_args()
    from run_robustness_experiment import protect_output
    protect_output(args.output.resolve())
    payload = run()
    args.output.mkdir(parents=True,exist_ok=True)
    write_csv(args.output/'episodes.csv',payload['episodes'])
    write_json_report(args.output/'results.json',payload)
    for r in payload['episodes']:
        if r['method']=='uncertainty':
            print(r['removal_step'],r['prior'],r['success'],r['observation_steps'],r['dynamic_contacts'])
