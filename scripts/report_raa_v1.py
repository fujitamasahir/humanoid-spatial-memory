"""Read-only paired/cluster-aware reports for prospectively frozen RAA arms."""
import sys,json,math
from pathlib import Path
from collections import defaultdict
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src')]
from c_v21_common import write,manifest,verify_manifest
from run_c_v21a_depth_ablation import episode
from run_dao_integration_v1_1 import native


def report(root):
    verify_manifest(root/'fit72');out=root/'analysis';out.mkdir(parents=True,exist_ok=False)
    arms=json.loads((root/'binding.json').read_text())['arms'];refs=('periodic','age','age5');candidates=[a for a in arms if a not in refs]
    records={};totals={};identities=defaultdict(list)
    for n in range(1,73):
        for arm in arms:
            e=episode(root/'fit72',n,arm);r=e['row'];d=e['diagnostics'];dec=d['decisions']
            x={'episode':n,'arm':arm,'identity':r['world_identity'],'schedule':r['schedule'],'goal':bool(r['success']),
               'contact_free_goal':bool(r['success'] and r['g1_unwanted_contact_pairs']==0),'contacts':r['g1_unwanted_contact_pairs'],
               'paid':d['actual_memory_sensor_calls'],'paid_rays':d['actual_memory_raycasts'],
               'emergency_scans':r['emergency_safety_scans'],'emergency_rays':r['emergency_safety_raycasts'],
               'combined_rays':d['actual_memory_raycasts']+r['emergency_safety_raycasts'],
               'h80_steps':r['elapsed_steps'],'distance_m':r['travel_distance_m'],'blocked':r['g1_footprint_blocked_attempts'],
               'rejected_selected':r['g1_rejected_action_attempts'],'emergency_interventions':r['emergency_safety_interventions'],
               'false_persistent':r['false_persistent_occupancy_updates'],'missed_changes':r['missed_persistent_changes'],
               'scheduler_ms':d['scheduler_total_ms'],'update_ms':d['history_update_total_ms'],'diagnostic_ms':d['diagnostic_total_ms'],
               'wall_seconds':r['episode_wall_time_seconds'],
               'advances':sum(z.get('advance',False) and z['granted'] for z in dec),
               'deferrals':sum(z.get('deferred',False) for z in dec),'forced_next':sum(z.get('forced_next',False) and z['granted'] for z in dec),
               'plans':sum(z.get('point_plan_calls',0) for z in dec),'footprints':sum(z.get('predicted_footprints',0) for z in dec)}
            records[n,arm]=x
        identities[records[n,refs[0]]['identity']].append(n)
    sumkeys=('goal','contact_free_goal','contacts','paid','paid_rays','emergency_scans','emergency_rays','combined_rays','h80_steps',
       'distance_m','blocked','rejected_selected','emergency_interventions','false_persistent','missed_changes','scheduler_ms','update_ms',
       'diagnostic_ms','wall_seconds','advances','deferrals','forced_next','plans','footprints')
    for arm in arms:totals[arm]={'episodes':72,**{k:sum(records[n,arm][k] for n in range(1,73)) for k in sumkeys}}
    clusters=[identities[k] for k in sorted(identities)];assert len(clusters)==36 and all(len(v)==2 for v in clusters)
    draws=np.random.default_rng(2026111602).integers(0,36,size=(2000,36));paired=[];comparisons=[]
    for candidate in candidates:
        for ref in refs:
            pair=[(records[n,ref],records[n,candidate]) for n in range(1,73)];common=[(a,b) for a,b in pair if a['goal'] and b['goal']]
            for a,b in pair:
                paired.append({'candidate':candidate,'reference':ref,'episode':a['episode'],'identity':a['identity'],'schedule':a['schedule'],
                    'reference_goal':a['goal'],'candidate_goal':b['goal'],
                    **{f'delta_{k}':b[k]-a[k] for k in sumkeys}})
            x,y=totals[ref],totals[candidate]
            dsteps=float(np.mean([b['h80_steps']-a['h80_steps'] for a,b in common])) if common else None
            ddistance=float(np.mean([b['distance_m']-a['distance_m'] for a,b in common])) if common else None
            boots={'paid_per_episode':[],'goal_difference':[],'common_steps':[],'common_distance':[]}
            for draw in draws:
                ns=[n for index in draw for n in clusters[int(index)]];pp=[(records[n,ref],records[n,candidate]) for n in ns]
                cc=[(a,b) for a,b in pp if a['goal'] and b['goal']]
                boots['paid_per_episode'].append(np.mean([b['paid']-a['paid'] for a,b in pp]));boots['goal_difference'].append(np.mean([int(b['goal'])-int(a['goal']) for a,b in pp]))
                if cc:
                    boots['common_steps'].append(np.mean([b['h80_steps']-a['h80_steps'] for a,b in cc]));boots['common_distance'].append(np.mean([b['distance_m']-a['distance_m'] for a,b in cc]))
            comparisons.append({'candidate':candidate,'reference':ref,'rescues':sum(not a['goal'] and b['goal'] for a,b in pair),
              'harms':sum(a['goal'] and not b['goal'] for a,b in pair),'common_successes':len(common),
              'common_step_delta':dsteps,'common_distance_delta_m':ddistance,'paid_delta':y['paid']-x['paid'],
              'combined_ray_delta':y['combined_rays']-x['combined_rays'],
              'primary_target_vs_reference':y['contacts']==0 and (y['goal']>x['goal'] or (y['goal']==x['goal'] and y['paid']<x['paid'])),
              'strong_joint_gain':bool(y['contacts']==0 and y['goal']>=x['goal'] and y['paid']<x['paid'] and y['combined_rays']<x['combined_rays']
                 and dsteps is not None and dsteps<=0 and ddistance<=0 and (dsteps<0 or ddistance<0)),
              'exploratory_whole_maze_bootstrap95':{k:np.quantile(v,[.025,.975]).tolist() if v else None for k,v in boots.items()}})
    targets={a:{'immediate_task_target':bool(totals[a]['contacts']==0 and (totals[a]['goal']>=67 or (totals[a]['goal']==66 and totals[a]['paid']<=769))),
        'beats_periodic_and_age':all(p['primary_target_vs_reference'] for p in comparisons if p['candidate']==a and p['reference'] in ('periodic','age')),
        'also_beats_age5':all(p['primary_target_vs_reference'] for p in comparisons if p['candidate']==a),
        'strong_joint_all_three':all(p['strong_joint_gain'] for p in comparisons if p['candidate']==a)} for a in candidates}
    write(out/'episode_metrics.json',list(records.values()));write(out/'paired.json',paired)
    write(out/'summary.json',native({'totals':totals,'comparisons':comparisons,'targets':targets,
         'independent_generalization_established':False,'cluster_resamples':2000,'seed':2026111602}))
    lines=['# RAA descriptive FIT72 results','', '|Policy|Goals/72|Paid scans|H80 steps|Blocked|Combined rays|Contacts|','|---|---:|---:|---:|---:|---:|---:|']
    for a,v in totals.items():lines.append(f"|{a}|{v['goal']}|{v['paid']}|{v['h80_steps']}|{v['blocked']}|{v['combined_rays']}|{v['contacts']}|")
    lines+=['','|Candidate vs reference|Rescues/harms|Common successes|Step delta|Distance delta m|Primary target|','|---|---:|---:|---:|---:|---|']
    for p in comparisons:lines.append(f"|{p['candidate']} vs {p['reference']}|{p['rescues']}/{p['harms']}|{p['common_successes']}|{p['common_step_delta']}|{p['common_distance_delta_m']}|{p['primary_target_vs_reference']}|")
    lines+=['','Immediate and stronger targets: '+str(targets),'','Reused development FIT72,36 correlated maze clusters. Conditional travel metrics use only common successes. No independent superiority claim.']
    (out/'research_report.md').write_text('\n'.join(lines)+'\n')
    import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,3,figsize=(12,4));xx=range(len(arms))
    for ax,key,label in zip(axes,('goal','paid','combined_rays'),('Goals/72','Paid scans','Paid+emergency rays')):
        ax.bar(xx,[totals[a][key] for a in arms]);ax.set_xticks(list(xx),arms,rotation=55,ha='right');ax.set_ylabel(label)
    fig.tight_layout();fig.savefig(out/'comparison.png',dpi=170);plt.close(fig)
    manifest(out);print('\n'.join(lines))
if __name__=='__main__':report(ROOT/'results/phase2_mujoco'/sys.argv[1] if len(sys.argv)>1 else ROOT/'results/phase2_mujoco/raa_v1')
