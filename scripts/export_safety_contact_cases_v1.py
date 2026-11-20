"""Every actual contact episode gets a timeline, evidence and run-level figure."""
import sys,json,gzip
from pathlib import Path
from collections import defaultdict
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from c_v21_common import write,manifest,verify_manifest
from safety_forensics_v1 import OUT
from report_predictive_safety_v1 import incident_analysis,read


def main():
    target=OUT/'contact_cases';target.mkdir(parents=True,exist_ok=False);verify_manifest(OUT/'matrix')
    definitions=json.loads((OUT/'prepared/scenarios.json').read_text());timelines=[];num_cases=0
    import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
    for p in sorted((OUT/'matrix').glob('*.json.gz')):
        e=read(p);n=int(p.name.split('_')[0]);d=definitions[n-1];onsets,_=incident_analysis(e,d)
        if not onsets:continue
        num_cases+=1;filename=p.name.removesuffix('.json.gz')+'.png';trace=e['trace']['steps'];decisions={r['step']:r for r in e['decisions']};cert={r['step']:r for r in e['candidate_diagnostics']}
        for onset in onsets:
            step=onset['step'];previous=decisions.get(step-1);now=decisions.get(step)
            if onset['proven_first_transition_unavoidable']:
                hypothesis='No robot action exists before transition1; first onset is imposed by unchanged advance-first timing.'
            elif e['safety']=='predictive_v1' and cert.get(step-1,{}).get('no_certifiably_safe_action'):
                hypothesis='Two-transition endpoint bound rejected available escapes; uncertified fallback wait remained in incoming path. No physical-unavoidability claim.'
            elif e['safety']=='original':
                hypothesis='Original direction-based reachable set/timing did not prevent entry of a proxy into the stationary robot after advancement. Inspect prior observed velocity and actual sync stages.'
            else:hypothesis='Observed environment-sync onset; uncertainty/model/visibility limitations require state-specific review, not a safety guarantee.'
            stages=[r for r in e['events'] if r['step'] in (step-1,step) and r['stage']!='selected_action_sweep_hypothesis']
            timelines.append({'file':str(p.relative_to(ROOT)),'scene':d['family'],'role':d['role'],'arm':e['arm'],'safety':e['safety'],
                **onset,'causal_hypothesis':hypothesis,'prior_public_decision':previous,'current_public_decision':now,
                'prior_candidate_certificate':cert.get(step-1),'current_candidate_certificate':cert.get(step),
                'actual_and_shadow_stage_evidence':stages,'trajectory_figure':filename})
        fig,(ax,tx)=plt.subplots(1,2,figsize=(11,4));robot=np.array([f['position'] for f in trace]);ax.plot(robot[:,0],robot[:,1],'-o',ms=3,label='robot')
        for i,path in enumerate(d['pedestrians']):
            ped=np.array([path[f['step']%len(path)] for f in trace]);ax.plot(ped[:,0],ped[:,1],'-s',ms=2,label=f'pedestrian{i}')
        contact_steps={o['step'] for o in onsets}
        for f in trace:
            if f['step'] in contact_steps:ax.scatter(*f['position'],s=70,facecolors='none',edgecolors='red')
        for stage,label in [('after_advance_raw_unsynchronized','after advance, unsynced'),('after_advance_synchronized_reference','synchronized reference'),('after_emergency_sensor_sync','actual after sensor sync'),('after_executed_action','actual executed frame')]:
            events=[r for r in e['events'] if r['stage']==stage];tx.plot([r['step'] for r in events],[sum(r['counts'].values()) for r in events],'-o',ms=2,label=label)
        for t in contact_steps:tx.axvline(t,color='red',alpha=.15)
        ax.set_aspect('equal');ax.set(xlabel='Grid x',ylabel='Grid y');ax.legend(fontsize=7);tx.set(xlabel='Step; red lines=actual onsets',ylabel='Unwanted contact pairs');tx.legend(fontsize=7)
        fig.suptitle(f'{d["role"]}/{d["family"]} {e["arm"]}, {e["safety"]}');fig.tight_layout();fig.savefig(target/filename,dpi=150);plt.close(fig)
    write(target/'all_contact_timelines.json',timelines)
    write(target/'summary.json',{'contacted_matrix_runs':num_cases,'distinct_actual_contact_episodes':len(timelines),
       'all_onsets_have_stage_evidence_and_figure':True,'onset_mechanisms':{k:sum(x['mechanism']==k for x in timelines) for k in sorted({x['mechanism'] for x in timelines})},
       'proven_first_transition_unavoidable':sum(x['proven_first_transition_unavoidable'] for x in timelines)})
    # A contact-free but non-reaching liveness counterexample must remain visible.
    fig,(ax,tx)=plt.subplots(1,2,figsize=(11,4))
    for safety in ('original','predictive_v1'):
        e=read(OUT/'matrix'/f'13_age5_{safety}.json.gz');frames=e['trace']['steps'];xy=np.array([f['position'] for f in frames]);ax.plot(xy[:,0],xy[:,1],'-o',ms=3,label=safety)
        tx.plot([f['step'] for f in frames],[abs(f['position'][0]-13)+abs(f['position'][1]-8) for f in frames],'-o',ms=3,label=safety)
    ax.set_aspect('equal');ax.set(xlabel='Grid x',ylabel='Grid y');tx.set(xlabel='Step',ylabel='Manhattan distance to goal');ax.legend();tx.legend();fig.suptitle('Contact-free crossing counterexample: candidate oscillation/liveness loss');fig.tight_layout();fig.savefig(target/'crossing_liveness_counterexample.png',dpi=170);plt.close(fig)
    manifest(target);print('Exported',len(timelines),'contact episode timelines across',num_cases,'contacted runs; no new simulation.')
if __name__=='__main__':main()
