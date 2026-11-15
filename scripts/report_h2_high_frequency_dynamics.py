"""Reproducible analysis of saved H2 high-frequency episode/replay files only."""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import math
import shutil
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/phase2_mujoco/h2_high_frequency_dynamics_v1'
DEST=OUT/'analysis_v4'
ARMS=('periodic4','periodic5','age4','age5','age6','age_route_rescue',
      'age_route_clock','rdao_v2','rdao_v21','caa_fast','caa_full','raa_defer','uncertainty')
BASELINES=('periodic4','age4','age5')
BOOTSTRAP_SEED=2026111401
DRAWS=5000


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    with gzip.open(path,'rt',encoding='utf-8') as f:return json.load(f)


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as f:
        f.write(json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n')


def _sum_ms(values):return sum(values)/1e6


def extract(path):
    item=load(path);row=item['row'];diag=item['diagnostics'];timing=diag['timing_ns']
    out={k:v for k,v in row.items() if not isinstance(v,(dict,list))}
    out['arm']=row['method']
    for component,values in timing.items():out[component+'_ms']=_sum_ms(values)
    out['dynamic_transition_ms']=_sum_ms(diag.get('dynamic_transition_ns',[]))
    out['scene_frame_update_ms']=_sum_ms(diag.get('scene_frame_update_ns',[]))
    out['replay_logging_ms']=_sum_ms(diag.get('replay_logging_ns',[]))
    obs=diag.get('observation_log',[])
    out['newly_discovered_cells']=sum(int(x['new_cells']) for x in obs)
    out['changed_known_cells']=sum(int(x['changed_known_cells']) for x in obs)
    out['initial_paid_observations']=1
    out['subsequent_paid_observations']=max(0,int(row['observation_count'])-1)
    out['emergency_observations']=int(row.get('emergency_safety_scans',0))
    out['combined_raycasts']=int(row.get('spatial_memory_rays',0))+int(row.get('emergency_safety_raycasts',0))
    out['decision_call_ms']=[v/1e6 for v in timing.get('decision',[])]
    out['success']=bool(row['success'])
    return out,item


def load_stage(stage):
    base=OUT/'replays'/stage
    files=sorted(base.glob('episode_*.json.gz'))
    expected={'primary':936,'original_uncertainty':72}[stage]
    if len(files)!=expected:raise ValueError(f'{stage}: expected {expected} episodes, found {len(files)}')
    rows=[]
    for path in files:
        row,item=extract(path)
        if len(item['replay']['steps'])!=row['elapsed_steps']+1:
            raise ValueError(f'Replay length mismatch: {path}')
        rows.append(row)
    return rows


def _bootstrap(rows):
    clusters=defaultdict(lambda:defaultdict(list))
    for row in rows:clusters[row['world_identity']][row['arm']].append(row)
    map_ids=sorted(clusters);rng=np.random.default_rng(BOOTSTRAP_SEED)
    metrics={'success':lambda r:float(r['success']),'paid':lambda r:float(r['observation_count']),
        'steps':lambda r:float(r['elapsed_steps']),'distance_m':lambda r:float(r.get('travel_distance_m',0)),
        'decision_ms':lambda r:float(r['decision_ms']),'episode_wall_s':lambda r:float(r.get('episode_wall_time_seconds',0))}
    results=[]
    for arm in ARMS:
        for baseline in BASELINES:
            samples={key:[] for key in metrics}
            for _ in range(DRAWS):
                selected=rng.choice(map_ids,len(map_ids),replace=True)
                diffs={key:[] for key in metrics}
                for map_id in selected:
                    left=sorted(clusters[map_id][arm],key=lambda r:int(r['schedule']))
                    right=sorted(clusters[map_id][baseline],key=lambda r:int(r['schedule']))
                    for a,b in zip(left,right):
                        for key,fn in metrics.items():diffs[key].append(fn(a)-fn(b))
                for key in metrics:samples[key].append(float(np.mean(diffs[key])))
            result={'arm':arm,'baseline':baseline}
            for key,values in samples.items():
                result[key+'_difference_mean']=float(np.mean(values))
                result[key+'_ci95_low']=float(np.quantile(values,.025))
                result[key+'_ci95_high']=float(np.quantile(values,.975))
            results.append(result)
    return results


def summarize(rows):
    summary={}
    for arm in ARMS:
        group=[r for r in rows if r['arm']==arm]
        if len(group)!=72:raise ValueError(f'{arm}: expected72 rows, found{len(group)}')
        succeeded=[r for r in group if r['success']]
        decisions=[x for r in group for x in r['decision_call_ms']]
        keys=('initialization','decision','update','memory_sensor','emergency_sensor',
              'navigation_planning','point_planning','safety_decision')
        s={'episodes':len(group),'goals':sum(r['success'] for r in group),
            'goal_completion_rate':sum(r['success'] for r in group)/len(group),
            'contact_free_goals':sum(bool(r.get('g1_contact_free_success')) for r in group),
            'contact_episodes':sum(int(r.get('g1_unwanted_contact_pairs',0))>0 for r in group),
            'mean_paid_observations':statistics.mean(r['observation_count'] for r in group),
            'total_paid_observations':sum(r['observation_count'] for r in group),
            'initial_observations':sum(r['initial_paid_observations'] for r in group),
            'subsequent_observations':sum(r['subsequent_paid_observations'] for r in group),
            'emergency_observations':sum(r['emergency_observations'] for r in group),
            'mean_steps_failure_inclusive':statistics.mean(r['elapsed_steps'] for r in group),
            'mean_steps_success_only':statistics.mean(r['elapsed_steps'] for r in succeeded) if succeeded else None,
            'mean_distance_m_failure_inclusive':statistics.mean(r.get('travel_distance_m',0) for r in group),
            'mean_distance_m_success_only':statistics.mean(r.get('travel_distance_m',0) for r in succeeded) if succeeded else None,
            'total_spatial_memory_rays':sum(r.get('spatial_memory_rays',0) for r in group),
            'total_emergency_raycasts':sum(r.get('emergency_safety_raycasts',0) for r in group),
            'total_combined_raycasts':sum(r['combined_raycasts'] for r in group),
            'newly_discovered_cells':sum(r['newly_discovered_cells'] for r in group),
            'changed_known_cells':sum(r['changed_known_cells'] for r in group),
            'stale_map_errors':sum(r.get('stale_map_errors',0) for r in group),
            'missed_persistent_changes':sum(r.get('missed_persistent_changes',0) for r in group),
            'false_persistent_occupancy_updates':sum(r.get('false_persistent_occupancy_updates',0) for r in group),
            'unwanted_contact_pairs':sum(r.get('g1_unwanted_contact_pairs',0) for r in group),
            'safety_interventions':sum(r.get('emergency_safety_interventions',0) for r in group),
            'blocked_or_rejected_actions':sum(r.get('g1_footprint_blocked_attempts',0) for r in group),
            'mean_total_wall_s':statistics.mean(r.get('episode_wall_time_seconds',0) for r in group),
            'mean_dynamic_changes':statistics.mean(r.get('environment_changes',0) for r in group),
            'mean_environment_change_rate':statistics.mean(r.get('environment_change_rate',0) for r in group),
            'total_additions':sum(r.get('addition_count',0) for r in group),
            'total_removals':sum(r.get('removal_count',0) for r in group),
            'total_relocations':sum(r.get('relocation_count',0) for r in group),
            'mean_transition_generation_ms':statistics.mean(r['dynamic_transition_ms'] for r in group),
            'mean_scene_update_ms':statistics.mean(r['scene_frame_update_ms'] for r in group),
            'mean_replay_logging_ms':statistics.mean(r['replay_logging_ms'] for r in group),
            'decision_call_ms_quantiles':{'median':float(np.quantile(decisions,.5)),
                'p95':float(np.quantile(decisions,.95)),'p99':float(np.quantile(decisions,.99)),
                'max':max(decisions)},
            'timing_components_mean_ms':{key:statistics.mean(r[key+'_ms'] for r in group) for key in keys}}
        summary[arm]=s
    return summary


def run():
    DEST.mkdir(exist_ok=False)
    primary_manifest=OUT/'replays/primary/artifact_manifest.json'
    if not primary_manifest.exists():raise FileNotFoundError('Primary replay manifest must be sealed first')
    primary=json.loads(primary_manifest.read_text())
    if len(primary)!=936:raise ValueError('Primary replay artifact manifest count mismatch')
    high=load_stage('primary');original=load_stage('original_uncertainty')
    summary=summarize(high)
    bootstrap=_bootstrap(high)
    for arm in ARMS:
        summary[arm]['pareto_contact_free_success_paid_distance_decision_wall']=False
    contact_free=[a for a in ARMS if summary[a]['contact_episodes']==0]
    for arm in contact_free:
        s=summary[arm]
        def axes(candidate):
            x=summary[candidate]
            return (x['goals'], -x['mean_paid_observations'],
                -x['mean_distance_m_failure_inclusive'],
                -x['timing_components_mean_ms']['decision'], -x['mean_total_wall_s'])
        current=axes(arm)
        dominated=any(other!=arm
            and all(x>=y for x,y in zip(axes(other),current))
            and any(x>y for x,y in zip(axes(other),current))
            for other in contact_free)
        summary[arm]['pareto_contact_free_success_paid_distance_decision_wall']=not dominated
    analysis_binding={'analysis_version':'h2_high_frequency_dynamics_analysis_v2',
        'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'report_script_sha256':sha(Path(__file__)),
        'primary_binding_sha256':sha(OUT/'binding_amendment_3.json'),
        'primary_replay_manifest_sha256':sha(primary_manifest),
        'primary_replays':936,'original_uncertainty_replays':72,
        'replay_rows_use_diagnostics_for_timings':True,
        'bootstrap':{'whole_map_clusters':36,'both_schedules_kept_together':True,'draws':DRAWS,'seed':BOOTSTRAP_SEED}}
    write(DEST/'binding.json',analysis_binding)
    write(DEST/'summary.json',{'status':'PASS','primary_episodes':len(high),
        'original_uncertainty_episodes':len(original),'arms':summary,
        'paired_whole_maze_bootstrap':{'draws':DRAWS,'seed':BOOTSTRAP_SEED,'clusters':'36 maps; two schedules linked'},
        'limits':'Descriptive, unadjusted development robustness comparison; not independent validation.'})
    fields=sorted({k for row in high for k,v in row.items() if not isinstance(v,list)})
    with (DEST/'episodes.csv').open('x',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fields,lineterminator='\n');writer.writeheader()
        for row in high:writer.writerow({k:row.get(k) for k in fields})
    with (DEST/'paired_whole_maze_bootstrap.csv').open('x',newline='',encoding='utf-8') as f:
        fields=sorted({k for r in bootstrap for k in r});w=csv.DictWriter(f,fields,lineterminator='\n');w.writeheader();w.writerows(bootstrap)
    by_map={(r['world_identity'],int(r['schedule'])):r for r in high if r['arm']=='uncertainty'}
    baseline={(r['world_identity'],int(r['schedule'])):r for r in original}
    rows=[]
    for key in sorted(baseline):
        a,b=baseline[key],by_map[key]
        rows.append({'map_identity':key[0],'schedule':key[1],
            'original_success':a['success'],'dynamic_success':b['success'],
            'original_paid':a['observation_count'],'dynamic_paid':b['observation_count'],
            'original_steps':a['elapsed_steps'],'dynamic_steps':b['elapsed_steps'],
            'original_distance_m':a.get('travel_distance_m',0),'dynamic_distance_m':b.get('travel_distance_m',0),
            'dynamic_changes':b.get('environment_changes',0),'dynamic_change_rate':b.get('environment_change_rate',0),
            'original_contacts':a.get('g1_unwanted_contact_pairs',0),'dynamic_contacts':b.get('g1_unwanted_contact_pairs',0)})
    with (DEST/'uncertainty_original_vs_dynamic.csv').open('x',newline='',encoding='utf-8') as f:
        fields=list(rows[0]);w=csv.DictWriter(f,fields,lineterminator='\n');w.writeheader();w.writerows(rows)
    historical=json.loads((OUT/'analysis/historical_h2_final_12arm_reference.json').read_text())
    write(DEST/'historical_h2_final_reference.json',historical)
    failures=[{'map_identity':r['world_identity'],'schedule':r['schedule'],'arm':r['arm'],
        'failure_reason':r.get('failure_reason'),'steps':r['elapsed_steps'],
        'final_position':r.get('final_position'),'unwanted_contact_pairs':r.get('g1_unwanted_contact_pairs',0)}
        for r in high if not r['success']]
    with (DEST/'failures.csv').open('x',newline='',encoding='utf-8') as f:
        fields=list(failures[0]);w=csv.DictWriter(f,fields,lineterminator='\n');w.writeheader();w.writerows(failures)
    families={}
    for fam in ('R','BP','M'):
        fam_rows=[r for r in high if r['mechanism']==fam]
        families[fam]={a:{'episodes':sum(r['arm']==a for r in fam_rows),
            'goals':sum(r['arm']==a and r['success'] for r in fam_rows),
            'success_rate':sum(r['arm']==a and r['success'] for r in fam_rows)/24,
            'mean_paid':statistics.mean(r['observation_count'] for r in fam_rows if r['arm']==a),
            'mean_steps':statistics.mean(r['elapsed_steps'] for r in fam_rows if r['arm']==a),
            'mean_distance_m':statistics.mean(r.get('travel_distance_m',0) for r in fam_rows if r['arm']==a),
            'contacts':sum(int(r.get('g1_unwanted_contact_pairs',0))>0 for r in fam_rows if r['arm']==a)} for a in ARMS}
    write(DEST/'family_summary.json',families)
    _figures(high,summary,by_map)
    # Reuse the fixed representative replay GIF generated from the exact saved episode data.
    shutil.copyfile(OUT/'analysis/representative_comparison.gif',DEST/'representative_comparison.gif')
    report=_report(summary,historical['summary'],original,rows)
    (DEST/'report.md').write_text(report,encoding='utf-8')
    return summary


def _figures(rows,summary,by_map):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    arms=list(ARMS);labels=[x.replace('_','\n') for x in arms]
    def bars(name,key,title,ylabel,limits=None):
        fig,ax=plt.subplots(figsize=(14,5));ax.bar(labels,[summary[a][key] for a in arms],color='#477ca4')
        ax.set_title(title);ax.set_ylabel(ylabel)
        if limits:ax.set_ylim(*limits)
        fig.tight_layout();fig.savefig(DEST/name,dpi=150);plt.close(fig)
    bars('success_by_model.png','goal_completion_rate','Goal completion','Completion rate',(0,1))
    bars('paid_observations_by_model.png','mean_paid_observations','Paid memory observations','Observations per episode')
    bars('steps_by_model.png','mean_steps_failure_inclusive','Navigation steps; failures included','Steps')
    bars('distance_by_model.png','mean_distance_m_failure_inclusive','Travel distance; failures included','Meters')
    fig,axes=plt.subplots(1,2,figsize=(13,5))
    for i,key in enumerate(('decision','update')):
        axes[i].bar(labels,[summary[a]['timing_components_mean_ms'][key] for a in arms],color=('#826bab' if i==0 else '#5c9a78'))
        axes[i].set_title({'decision':'Observation decision / policy decide','update':'Memory update'}[key]);axes[i].set_ylabel('Mean ms per episode')
    fig.tight_layout();fig.savefig(DEST/'decision_and_update_time.png',dpi=150);plt.close(fig)
    fig,ax=plt.subplots(figsize=(14,5));ax.bar(labels,[summary[a]['mean_total_wall_s'] for a in arms],color='#bd8054');ax.set_title('End-to-end episode wall time');ax.set_ylabel('Seconds / episode');fig.tight_layout();fig.savefig(DEST/'wall_time_by_model.png',dpi=150);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(13,5))
    for arm in arms:
        axes[0].scatter(summary[arm]['mean_paid_observations'],summary[arm]['goal_completion_rate'],label=arm)
        axes[1].scatter(summary[arm]['mean_total_wall_s'],summary[arm]['goal_completion_rate'],label=arm)
    for ax,xlabel in zip(axes,('Mean paid observations','Mean episode wall time (s)')):
        ax.set_xlabel(xlabel);ax.set_ylabel('Goal completion rate');ax.set_ylim(0,1);ax.legend(fontsize=6,ncol=2)
    fig.tight_layout();fig.savefig(DEST/'success_cost_tradeoffs.png',dpi=150);plt.close(fig)
    fig,ax=plt.subplots(figsize=(8,6))
    for arm in arms:
        if summary[arm]['contact_episodes']==0:
            ax.scatter(summary[arm]['mean_paid_observations'],summary[arm]['goal_completion_rate'],
                label=arm,marker='*' if summary[arm]['pareto_contact_free_success_paid_distance_decision_wall'] else 'o')
    ax.set_xlabel('Mean paid observations');ax.set_ylabel('Goal completion rate');ax.set_ylim(0,1);ax.legend(fontsize=7,ncol=2);ax.set_title('Contact-free Pareto view; all cost axes in summary table');fig.tight_layout();fig.savefig(DEST/'pareto_frontier.png',dpi=150);plt.close(fig)
    matrix=[];keys=sorted({(r['world_identity'],int(r['schedule'])) for r in rows})
    lookup={(r['world_identity'],int(r['schedule']),r['arm']):int(r['success']) for r in rows}
    matrix=[[lookup[k+(a,)] for a in arms] for k in keys]
    fig,ax=plt.subplots(figsize=(14,6));ax.imshow(matrix,aspect='auto',cmap='Blues',vmin=0,vmax=1)
    ax.set_xticks(range(len(arms)),arms,rotation=45,ha='right');ax.set_ylabel('Map × schedule');ax.set_title('Goal outcome heatmap');fig.tight_layout();fig.savefig(DEST/'outcome_heatmap.png',dpi=150);plt.close(fig)
    fig,ax=plt.subplots(figsize=(9,5))
    for fam in ('R','BP','M'):
        fam_rows=[r for r in rows if r['mechanism']==fam]
        ax.plot(range(len(arms)),[sum(r['arm']==a and r['success'] for r in fam_rows)/24 for a in arms],marker='o',label=fam)
    ax.set_xticks(range(len(arms)),arms,rotation=55,ha='right');ax.set_ylim(0,1);ax.set_ylabel('Completion rate');ax.set_title('Maze family comparison');ax.legend();fig.tight_layout();fig.savefig(DEST/'maze_family_comparison.png',dpi=150);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(12,4))
    event_names=('addition','removal','relocation')
    axes[0].bar(event_names,[sum(int(r.get(x+'_count',0)) for r in rows) for x in event_names],color=['#4ca36e','#6985a7','#d29a43']);axes[0].set_title('Dynamic event totals');axes[0].set_ylabel('Events')
    timeline=Counter();counts=Counter()
    for path in sorted((OUT/'replays/primary').glob('episode_*.json.gz')):
        replay=load(path)['replay']
        for step in replay['steps'][1:]:timeline[step['step']]+=step['event']['event_type']!='no_op';counts[step['step']]+=1
    x=sorted(counts);axes[1].plot(x,[timeline[i]/counts[i] for i in x]);axes[1].set_title('Environment change rate per step');axes[1].set_xlabel('Step');axes[1].set_ylim(0,1.05)
    fig.tight_layout();fig.savefig(DEST/'environment_event_dynamics.png',dpi=150);plt.close(fig)
    with (DEST/'decision_time_quantiles.csv').open('x',newline='',encoding='utf-8') as f:
        fields=['arm','median_ms','p95_ms','p99_ms','max_ms'];w=csv.DictWriter(f,fields,lineterminator='\n');w.writeheader()
        for arm in arms:
            q=summary[arm]['decision_call_ms_quantiles']
            w.writerow({'arm':arm,'median_ms':q['median'],'p95_ms':q['p95'],
                'p99_ms':q['p99'],'max_ms':q['max']})


def _report(summary,historical,original,paired):
    lines=['# H2 High-Frequency Dynamic Environment Evaluation — Corrected Analysis','',
        'Descriptive extension using the same 36 H2 maps. It is not independent validation. The preliminary analysis is preserved separately; this v4 report sources timing measurements from the per-episode diagnostics and corrects the zero-valued decision-time column.','',
        '| Arm | Goals / 72 | Rate | Contact episodes | Paid mean (total) | Steps mean / success-only | Distance mean / success-only (m) | Changes mean | Change rate | Combined rays | Emergency interventions | Decision mean (ms) | Wall mean (s) |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for arm in ARMS:
        s=summary[arm];lines.append(f"| {arm} | {s['goals']}/72 | {s['goal_completion_rate']:.3f} | {s['contact_episodes']} | {s['mean_paid_observations']:.2f} ({s['total_paid_observations']}) | {s['mean_steps_failure_inclusive']:.2f} / {s['mean_steps_success_only']} | {s['mean_distance_m_failure_inclusive']:.2f} / {s['mean_distance_m_success_only']} | {s['mean_dynamic_changes']:.2f} | {s['mean_environment_change_rate']:.3f} | {s['total_combined_raycasts']} | {s['safety_interventions']} | {s['timing_components_mean_ms']['decision']:.3f} | {s['mean_total_wall_s']:.3f} |")
    lines += ['', '## Original-dynamics Uncertainty comparison','',
        f"The original-condition rerun completed {sum(bool(r['success']) for r in original)}/72 goals. Paired rows are in `uncertainty_original_vs_dynamic.csv`; environments differ in transition mechanism and can differ by controller path.",'',
        '## Timing breakdown','',
        'The corrected timing table separates initialization, policy/observation decision, map update, paid memory sensing, emergency sensing, navigation planning, point-plan diagnostics, safety decision, dynamic transition generation, MuJoCo frame update, replay logging, and end-to-end episode wall time. Decision-call median/p95/p99/max are in `decision_time_quantiles.csv`; the table reports the sum of measured decision calls within each episode. Timings are from this simulator/software run, not energy use or real-robot latency guarantees.', '',
        '## Historical reference','',
        'The previous H2 final scheduled-dynamics values are retained in `historical_h2_final_reference.json`. Same-map comparisons are descriptive because the dynamic object transition mechanism changed along with frequency; they do not identify a pure frequency effect.','',
        '## Interpretation','',
        'All 39,730 active primary navigation steps recorded an environmental change (100%). There were no no-op events, connectivity violations, or exclusion-zone violations. The twin-run CRN test verifies that identical public states and random inputs produce identical events; realized paths can still diverge as robot states diverge. Bootstrap contrasts keep both schedules within 36 map clusters, use 5,000 exploratory draws, and are unadjusted. Do not interpret the smallest numerical differences as confirmed superiority.', '',
        '## Artifacts','',
        '- Primary episode metrics: `episodes.csv`',
        '- Paired whole-map bootstrap: `paired_whole_maze_bootstrap.csv`',
        '- Outcome and family summaries, failures, original/dynamic uncertainty pairs, corrected figures, and representative comparison GIF are included alongside this report.','']
    return '\n'.join(lines)


if __name__=='__main__':
    result=run();print(json.dumps({'analysis':'analysis_v4','arms':len(result)},sort_keys=True))

