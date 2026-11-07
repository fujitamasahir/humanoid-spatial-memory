"""Synthetic public-memory decision workloads; no tuning or assessment outcomes."""
import argparse
from collections import defaultdict
from dataclasses import asdict
import json
from pathlib import Path
import sys
from time import perf_counter
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from spatial_memory.task_policies import METHODS,ABLATIONS,PolicyController,precommit_schedule
from spatial_memory.policy_planning import PlanningMeter
from spatial_memory.provenance import provenance
from run_phase1_4a_validation import write_json,protect_output
from run_adaptive_experiment import write_csv


def workloads():
    rng=np.random.default_rng(140401)
    result=[]
    for name,width,height,radius in [('known-open',13,9,3),('partly-unknown',17,9,3),
        ('two-passages',17,9,3),('no-route',17,9,3),('cluttered',25,17,3),('large-radius-stress',31,21,5)]:
        grid=np.zeros((height,width),np.int8)
        pose=(max(1,width//2-2),height//2)
        goal=(width-2,height//2)
        if name=='partly-unknown':
            grid[rng.random(grid.shape)<.65]=-1
        elif name=='two-passages':
            grid[:,width//2]=1
            grid[1,width//2]=0;grid[-2,width//2]=0
        elif name=='no-route':
            grid[:,width//2]=1
        elif name in {'cluttered','large-radius-stress'}:
            grid[rng.random(grid.shape)<.23]=1
            grid[rng.random(grid.shape)<.2]=-1
        grid[pose[1],pose[0]]=0;grid[goal[1],goal[0]]=0
        result.append(dict(name=name,grid=grid,pose=pose,goal=goal,radius=radius))
    return result


def counts():
    # 3,780 tuning + 13,440 assessment + 1,680 ablations = 18,900.
    result={m:840 for m in METHODS}
    result['random-quota']=4200
    for m in ('fixed-rate','route-weighted','disruption-visible','query-gate-conceptual'):
        result[m]+=945
    for ablation in ABLATIONS:
        result['disruption-visible:'+ablation]=280
    assert sum(result.values())==18900
    return result


def run(repeats=8):
    rows=[]
    labels=[(m,None) for m in METHODS]+[('disruption-visible',a) for a in ABLATIONS]
    cases=workloads()
    for method,ablation in labels:
        # Exactly one untimed call per core/ablation method before timing.
        warm=PolicyController(np.zeros((3,5),np.int8),method,goal=(4,1),ablation=ablation,max_observations=4)
        warm.decide(1,(1,1))
        for case in cases:
            for step,cap in ((1,4),(10,1),(30,None)):
                rng=np.random.default_rng(np.random.SeedSequence([140401,1404,0]))
                schedule=precommit_schedule(method,cap,40,rng) if method in {'random-quota','quota-periodic'} else ()
                for repeat in range(repeats):
                    c=PolicyController(case['grid'],method,goal=case['goal'],radius=case['radius'],
                        ablation=ablation,max_observations=cap,schedule=schedule)
                    # Public repeated history with stable and flipped visible samples.
                    # It is not a simulated realization or an assessment observation.
                    if not c.legacy:
                        sample=case['grid'].copy()
                        sample[0,0]=1 if sample[0,0]==0 else 0
                        c.observer.refresh(sample,0)
                    begin=perf_counter()
                    decision=c.decide(step,case['pose'])
                    outer=perf_counter()-begin
                    meter=PlanningMeter()
                    meter(c.memory.grid,case['pose'],case['goal'])
                    rows.append(dict(workload=case['name'],method=method,ablation=ablation,
                        step=step,cap=cap,repeat=repeat,radius=case['radius'],
                        scheduler_seconds=decision['scheduler_seconds'],
                        scheduler_astar_calls=decision['scheduler_astar_calls'],
                        scheduler_astar_seconds=decision['scheduler_astar_seconds'],
                        diagnostic_seconds=decision['diagnostic_seconds'],outer_seconds=outer,
                        common_planner_seconds=meter.seconds))
    groups=defaultdict(list)
    for row in rows:
        groups[(row['workload'],row['method'],row['ablation'])].append(row)
    summary=[]
    for key,items in groups.items():
        summary.append(dict(zip(('workload','method','ablation'),key))|
            dict(samples=len(items),median_seconds=float(np.median([r['scheduler_seconds'] for r in items])),
                 p95_seconds=float(np.percentile([r['scheduler_seconds'] for r in items],95)),
                 median_astar_calls=float(np.median([r['scheduler_astar_calls'] for r in items])),
                 max_astar_calls=max(r['scheduler_astar_calls'] for r in items)))
    return rows,summary,cases


def estimate(rows,smoke=None):
    # Runtime-only use of smoke records; no success/call-performance selection.
    overhead=0.
    if smoke:
        episodes=json.loads(smoke.read_text())['episodes']
        overhead=max(max(0.,r['episode_runtime_seconds']-r['scheduler_seconds']-
                         r['diagnostic_seconds']-r['common_planner_seconds'])/max(1,r['elapsed_steps']) for r in episodes)
    models=[]
    for label,decisions,percentile,include_stress in (
        ('short-episode-scenario',8,50,False),('full-horizon-median-workloads',40,50,False),
        ('full-horizon-p95-with-radius5-stress',40,95,True)):
        total=0.
        for name,episodes in counts().items():
            m,_,a=name.partition(':')
            sample=[r['outer_seconds']+r['common_planner_seconds'] for r in rows
                    if r['method']==m and (r['ablation'] or '')==a
                    and (include_stress or r['workload']!='large-radius-stress')]
            per_decision=float(np.percentile(sample,percentile))+overhead
            total+=episodes*decisions*per_decision
        models.append(dict(label=label,seconds=total,hours=total/3600,
                           decisions_per_episode=decisions,workload_percentile=percentile))
    return dict(episode_counts=counts(),total_episodes=18900,scenarios=models,
        measured_extra_overhead_seconds_per_step=overhead,
        caveats=['Scenario estimates, not confidence bounds or guaranteed upper bounds.',
            'Defaults and six synthetic map families do not predict tuned parameter/trajectory frequencies.',
            'Tuning thresholds can change sensing and episode lengths; caps do not skip denied decisions.',
            'Synthetic 8/40-decision scenarios bracket assumed horizons, not empirical assessment lengths.',
            'Includes measured diagnostic/trace construction and common A*; excludes future file I/O and thermal/load changes.',
            'Radius5 stress exceeds the frozen radius3 matrix and is labeled separately.'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--smoke',type=Path)
    args=parser.parse_args()
    protect_output(args.output)
    rows,summary,cases=run()
    cfg=dict(repeats=8,contexts=[dict(step=1,cap=4),dict(step=10,cap=1),dict(step=30,cap=None)],
             workloads=[{k:v for k,v in c.items()} for c in cases])
    # Convert arrays before provenance hashing; retain exact synthetic inputs.
    cfg=json.loads(json.dumps(cfg,default=lambda a:a.tolist()))
    payload=dict(label='Synthetic feasibility only, no algorithm performance conclusions',
        summary=summary,measurements=rows,full_matrix_runtime=estimate(rows,args.smoke),
        provenance=provenance(ROOT,cfg))
    args.output.mkdir(parents=True,exist_ok=True)
    write_json(args.output/'results.json',payload)
    write_csv(args.output/'latencies.csv',summary)
    for m in ('route-weighted','disruption-visible','query-gate-conceptual'):
        for s in summary:
            if s['method']==m and s['ablation'] is None:
                print(m,s['workload'],s['median_seconds'],s['p95_seconds'],s['median_astar_calls'],s['max_astar_calls'])
    print(payload['full_matrix_runtime'])


if __name__=='__main__':
    main()
