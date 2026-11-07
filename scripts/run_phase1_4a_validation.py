"""Limited development smoke and manifest generation; no tuning/assessment runner."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from spatial_memory.task_policies import METHODS, ABLATIONS
from spatial_memory.robustness import generate_robustness, truth_audit
from spatial_memory.manifests import (historical_exclusions,build_manifests,validate_manifest,
                                     environment_hash,layout_hash,require_smoke_record)
from spatial_memory.protocol_evaluation import run_protocol_episode
from spatial_memory.provenance import provenance
from run_adaptive_experiment import write_csv,write_json_report


def write_json(path,payload):
    def encode(obj):
        if isinstance(obj,np.ndarray):
            return obj.tolist()
        if isinstance(obj,np.generic):
            return obj.item()
        raise TypeError(type(obj).__name__)
    normalized=json.loads(json.dumps(payload,default=encode))
    write_json_report(path,normalized)


def protect_output(path):
    path=path.resolve()
    for old in ('representative','phase1_1','phase1_2','phase1_3'):
        previous=(ROOT/'results'/old).resolve()
        if path==previous or previous in path.parents or path in previous.parents:
            raise ValueError('Historical artifacts protected')


def smoke(config,output):
    if config['purpose']!='smoke' or config['split']!='development':
        raise ValueError('Only development smoke execution allowed')
    if len(config['realizations'])>2 or config['max_steps']>40:
        raise ValueError('Smoke size limit: two worlds, forty steps')
    # Prevent new assessment/tuning worlds from being relabeled as smoke inputs.
    if any(10000<=r['seed']<30000 for r in config['realizations']):
        raise ValueError('Reserved tuning/assessment seed namespaces')
    rows,traces,realized=[],[],[]
    for case in config['realizations']:
        seed=case['seed']
        scenario=generate_robustness(case['family'],seed)
        record=dict(partition='smoke',scenario=asdict(scenario),seed=seed,
                    environment_sha256=environment_hash(scenario),layout_sha256=layout_hash(scenario),
                    topology=truth_audit(scenario,config['max_steps']))
        realized.append(record)
        scenario=require_smoke_record(record)
        for method,ablation in [(m,None) for m in METHODS]+[('disruption-visible',a) for a in ABLATIONS]:
            metrics,frames,samples=run_protocol_episode(scenario,config,method,seed,ablation=ablation,
                                                       replicate=config['random_replicate'])
            metrics.update(environment_sha256=record['environment_sha256'],layout_sha256=record['layout_sha256'])
            rows.append(metrics)
            traces.append(dict(method=method,ablation=ablation,seed=seed,frames=frames,
                               feasibility_samples=samples))
    payload=dict(label='Development smoke only: execution debugging, not algorithm selection',
                 episodes=rows,traces=traces,realized_scenarios=realized,provenance=provenance(ROOT,config))
    output.mkdir(parents=True,exist_ok=True)
    write_json(output/'results.json',payload)
    write_csv(output/'episodes.csv',rows)
    print(f'Smoke executed {len(rows)} episodes; no parameter selection or assessment.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['manifests','smoke'])
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    protect_output(args.output)
    if args.action=='manifests':
        hashes,seeds=historical_exclusions(ROOT)
        manifests=build_manifests(hashes,seeds)
        parts=[validate_manifest(m) for m in manifests.values()]
        if parts[0]&parts[1]:
            raise ValueError('Cross-partition duplicate')
        args.output.mkdir(parents=True,exist_ok=True)
        for partition,manifest in manifests.items():
            manifest['provenance']=provenance(ROOT,dict(partition=partition,counts={'tuning':35,'assessment':70},horizon=40))
            write_json(args.output/(partition+'.json'),manifest)
        print('Generated 35 tuning and 70 assessment environments; no policies executed.')
    else:
        config=json.loads((ROOT/'configs/development_phase1_4a_smoke.json').read_text())
        # One untimed synthetic warm-up per method (no environment or outcome).
        from spatial_memory.task_policies import PolicyController,precommit_schedule
        for method,ablation in [(m,None) for m in METHODS]+[('disruption-visible',a) for a in ABLATIONS]:
            rng=np.random.default_rng(np.random.SeedSequence([0,1404,0]))
            schedule=precommit_schedule(method,4,40,rng) if method in {'random-quota','quota-periodic'} else ()
            c=PolicyController(np.zeros((3,5),np.int8),method,goal=(4,1),max_observations=4,schedule=schedule,ablation=ablation)
            c.decide(1,(1,1))
        smoke(config,args.output)


if __name__=='__main__':
    main()
