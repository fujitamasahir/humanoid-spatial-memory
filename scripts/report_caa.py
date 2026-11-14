"""Frozen CAA descriptive analysis; no online or population generation inputs."""
from __future__ import annotations
import json,sys
from collections import Counter
from statistics import mean
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from caa_common import ROOT,episode,write,manifest,verify_manifest,sha,commit


def report(output):
    import run_caa_fit72 as matrix
    matrix.OUT=output;matrix.gate();verify_manifest(output/'fit72')
    target=output/'analysis';target.mkdir(parents=True,exist_ok=False)
    records={};raw={}
    for n in range(1,73):
      for arm in matrix.ARMS:
        e=episode(output/'fit72',n,arm);raw[n,arm]=e
        matrix.safety(e['row'],e['trace'],e['diagnostics'])
        records[n,arm]=matrix.flatten(n,arm,e['row'],e['diagnostics'])
    summary={a:{'goals':sum(r['success'] for (n,arm),r in records.items() if arm==a),
       'contact_free_goals':sum(r['contact_free_success'] for (n,arm),r in records.items() if arm==a),
       **{'mean_'+k:mean(r[k] for (n,arm),r in records.items() if arm==a) for k in matrix.METRICS},
       'mean_observation_update_ms':mean(r['mean_noninitial_update_ms'] for (n,arm),r in records.items() if arm==a),
       'mean_decide_ms':mean(r['mean_decide_ms'] for (n,arm),r in records.items() if arm==a)} for a in matrix.ARMS}
    pairs=[];pair_rows=[];common_means=[]
    contrasts=[(a,b) for a in ('age6','caa_fast','caa_slow','caa_full') for b in ('periodic','age4','age5')]
    contrasts += [(a,'age6') for a in ('caa_fast','caa_slow','caa_full')] + [('caa_full','caa_fast'),('caa_full','caa_slow')]
    for a,b in contrasts:
        rs=[]
        for n in range(1,73):
            x,y=records[n,b],records[n,a]
            if (x['identity'],x['schedule'])!=(y['identity'],y['schedule']):raise RuntimeError('Pair identity mismatch')
            common=x['success'] and y['success']
            r={'candidate':a,'reference':b,'episode':n,'identity':x['identity'],'schedule':x['schedule'],'reference_success':x['success'],'candidate_success':y['success'],'common_success':common,
                **{'delta_'+k:y[k]-x[k] for k in matrix.METRICS}}
            rs.append(r);pair_rows.append(r)
        both=[r for r in rs if r['common_success']]
        worlds=sorted({r['identity'] for r in rs});fields=('paid_memory_scans','combined_rays','elapsed_steps')
        array=np.array([[mean(r['delta_'+k] for r in rs if r['identity']==w) for k in fields] for w in worlds])
        rng=np.random.default_rng(2026111403);draw=rng.integers(0,len(worlds),(2000,len(worlds)))
        boots=array[draw].mean(axis=1)
        common_array=np.array([[sum(r['delta_elapsed_steps'] for r in both if r['identity']==w),sum(r['delta_travel_distance_m'] for r in both if r['identity']==w),sum(r['identity']==w for r in both)] for w in worlds])
        sums=common_array[draw].sum(axis=1);valid=sums[:,2]>0
        common_delta={k:mean(r['delta_'+k] for r in both) if both else None for k in ('elapsed_steps','travel_distance_m','paid_memory_scans','combined_rays')}
        v=summary[a];ref=summary[b]
        pair={'candidate':a,'reference':b,'rescues':sum(not r['reference_success'] and r['candidate_success'] for r in rs),'harms':sum(r['reference_success'] and not r['candidate_success'] for r in rs),
           'common_successes':len(both),'common_success_delta':common_delta,
           'clustered_95_intervals':{k:np.percentile(boots[:,j],[2.5,97.5]).tolist() for j,k in enumerate(fields)},
           'common_success_cluster_95_intervals':{k:np.percentile(sums[valid,j]/sums[valid,2],[2.5,97.5]).tolist() if valid.any() else None for j,k in enumerate(('elapsed_steps','travel_distance_m'))},
           'maze_clusters':len(worlds),'correlated_schedule_rule':'Two schedules sampled together within each maze',
           'joint_paid_and_navigation_improvement':bool(v['mean_unwanted_contacts']<=ref['mean_unwanted_contacts'] and v['goals']>=ref['goals'] and v['contact_free_goals']>=ref['contact_free_goals'] and v['mean_paid_memory_scans']<ref['mean_paid_memory_scans'] and both and common_delta['elapsed_steps']<0 and common_delta['travel_distance_m']<0)}
        pairs.append(pair)
        means={side:{k:mean(records[r['episode'],policy][k] for r in both) if both else None for k in ('elapsed_steps','travel_distance_m')} for side,policy in [('reference',b),('candidate',a)]}
        common_means.append({'candidate':a,'reference':b,'means':means})
    targets={a:bool(v['mean_unwanted_contacts']==0 and (v['goals']>66 or (v['goals']==66 and v['mean_paid_memory_scans']<10.694))) for a,v in summary.items()}
    diagnostics={}
    for a in matrix.ARMS:
        entries=[raw[n,a]['diagnostics'] for n in range(1,73)];dec=[d for e in entries for d in e['decisions']];scans=[s for e in entries for s in e['observation_log'][1:]]
        diagnostics[a]={'decisions':len(dec),'advanced_requests':sum(d.get('request_advanced_vs_uniform5',False) for d in dec),'advanced_paid_scans':sum(d['granted'] and d.get('request_advanced_vs_uniform5',False) for d in dec),'deferred_requests':sum(d.get('request_deferred_vs_uniform5',False) for d in dec),
            'budget_exhausted_decisions':sum(d['used_before']>=20 for d in dec),
            'global_class_cell_times':{c:sum(d['global_history']['classes'][c] for d in dec) for c in ('unknown','changing','intermediate','stable')},
            'effective_deadline_cell_times':{str(t):sum(d.get('effective_deadlines_known',{}).get(str(t),0) for d in dec) for t in (4,5,6)},
            'scans_with_new_cells':sum(s['new_cells']>0 for s in scans),'scans_with_changed_known':sum(s['changed_known_cells']>0 for s in scans),'scans_only_unchanged_known':sum(s['only_unchanged_known'] for s in scans),
            'scheduler_ms':sum(e['scheduler_total_ms'] for e in entries),'authorized_update_ms':sum(e['history_update_total_ms'] for e in entries),'diagnostic_ms':sum(e['diagnostic_total_ms'] for e in entries),
            'scheduler_plan_calls':sum(d.get('scheduler_plan_calls',0) for d in dec),'predicted_raycasts':sum(d.get('predicted_raycasts',0) for d in dec)}
    matrix.fit.csv_write(target/'paired_episode_deltas.csv',pair_rows)
    write(target/'results.json',{'status':'COMPLETED_DESCRIPTIVE_NOT_VALIDATION','source_commit':commit(),'arms':summary,'paired':pairs,'paired_common_success_means':common_means,'primary_descriptive_target':targets,'diagnostics':diagnostics,'bootstrap':'2000 maze-cluster resamples; seed2026111403; exploratory, reused FIT and unadjusted contrasts'})
    names=list(matrix.ARMS);fig,axes=plt.subplots(2,2,figsize=(12,8))
    for ax,(key,title) in zip(axes.flat,[('goals','Goal completion /72'),('mean_paid_memory_scans','Mean paid memory scans'),('mean_elapsed_steps','Mean H80-censored steps'),('mean_combined_rays','Mean memory + emergency rays')]):
        ax.bar(range(7),[summary[a][key] for a in names]);ax.set_title(title);ax.set_xticks(range(7),names,rotation=35,ha='right')
    fig.suptitle('CAA: reused FIT72 descriptive screen, paired schedules correlated');fig.tight_layout();fig.savefig(target/'outcomes.png',dpi=170);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(12,4))
    colors=('tab:red','tab:gray','tab:green')
    for ax,field,categories in [(axes[0],'global_class_cell_times',('changing','intermediate','stable')),(axes[1],'effective_deadline_cell_times',('4','5','6'))]:
        bottom=np.zeros(7)
        for c,color in zip(categories,colors):
            values=np.array([diagnostics[a][field][c]/max(1,sum(diagnostics[a][field][k] for k in categories)) for a in names])
            ax.bar(range(7),values,bottom=bottom,label=c,color=color);bottom+=values
        ax.set_xticks(range(7),names,rotation=35,ha='right');ax.legend();ax.set_ylim(0,1)
    axes[0].set_title('Known-cell history classes (diagnostic for baselines)');axes[1].set_title('Actual Age deadlines (Periodic uses a clock)');fig.tight_layout();fig.savefig(target/'history_deadlines.png',dpi=170);plt.close(fig)
    choices=[n for n in range(1,73) if records[n,'caa_full']['elapsed_steps']!=records[n,'age5']['elapsed_steps'] or records[n,'caa_full']['success']!=records[n,'age5']['success']]
    n=min(choices) if choices else 1
    fig,ax=plt.subplots(figsize=(8,6))
    for a in ('age4','age5','caa_full'):
        frames=raw[n,a]['trace']['steps'];positions=[f['position'] for f in frames]
        ax.plot(*zip(*positions),'-o',ms=3,label=a)
        observed=[f['position'] for f in frames if f['observation_granted']]
        ax.scatter(*zip(*observed),marker='x',s=40)
    key=raw[n,'age5']['trace']['key'];ax.set_title(f'Actual G1 paths: {key[0].split(":")[-2:]} schedule{key[1]}\nFirst sorted changed-step/outcome key; x=paid memory scan');ax.set_aspect('equal');ax.legend();fig.tight_layout();fig.savefig(target/'representative_trajectory.png',dpi=170);plt.close(fig)
    lines=['# CAA descriptive FIT72 results','','|Arm|Goals|Mean paid scans|Mean H80 steps|Mean combined rays|Mean scheduler ms|','|---|---:|---:|---:|---:|---:|']
    for a,v in summary.items():lines.append(f"|{a}|{v['goals']}|{v['mean_paid_memory_scans']:.6f}|{v['mean_elapsed_steps']:.6f}|{v['mean_combined_rays']:.3f}|{v['mean_scheduler_ms']:.4f}|")
    lines+=['','Primary target: '+str(targets),'','All complete paired/common-success, memory, timing, class/deadline and same-state attribution metrics are in results.json. No claim of novelty or independent validation.']
    (target/'summary.md').write_text('\n'.join(lines)+'\n');manifest(target);print('\n'.join(lines))
