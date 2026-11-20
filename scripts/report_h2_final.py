"""Frozen-analysis H2 tables/figures/report. Reads completed episodes only."""
import sys,json,csv,math
from pathlib import Path
from statistics import mean
from collections import Counter
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from h2_final_common import *
from h2_generate_maps import raster
LABEL=dict(zip(ARMS,LABELS));COLORS=plt.get_cmap('tab20')(np.arange(12))
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'figure.dpi':130,'savefig.dpi':170})
def csvwrite(path,rows):
    with path.open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]) if rows else ['episode','arm','identity','schedule','success'],lineterminator='\n');w.writeheader();w.writerows(rows)
def flat(n,arm,e):
    r=e['row'];d=e['diagnostics'];t=d['timing_ns'];dec=np.asarray(t['decision'])/1e6
    return {'episode':n,'arm':arm,'label':LABEL[arm],'identity':r['world_identity'],'family':r['mechanism'],'schedule':r['schedule'],
    'success':int(r['success']),'contact_free_success':int(r['success'] and r['g1_unwanted_contact_pairs']==0),'contacts':r['g1_unwanted_contact_pairs'],
    'paid':r['observation_count'],'paid_rays':d['actual_memory_raycasts'],'emergency_rays':r['emergency_safety_raycasts'],'combined_rays':d['actual_memory_raycasts']+r['emergency_safety_raycasts'],
    'steps':r['elapsed_steps'],'distance_m':r['travel_distance_m'],'blocked':r['g1_footprint_blocked_attempts'],'interventions':r['emergency_safety_interventions'],
    'new_cells':sum(x['new_cells'] for x in d['observation_log']),'changed_known_cells':sum(x['changed_known_cells'] for x in d['observation_log']),
    **{k+'_ms':sum(v)/1e6 for k,v in t.items()},'decision_mean_step_ms':float(dec.mean()) if len(dec) else 0.,
    **{'decision_'+k+'_ms':float(np.percentile(dec,q)) if len(dec) else 0. for k,q in [('median',50),('p95',95),('p99',99),('max',100)]},
    'wall_s':r['episode_wall_time_seconds'],'scene_s':r['scene_construction_time_seconds'],'loop_s':r['evaluation_loop_time_seconds']}
def load(stage):return [flat(n,a,episode(OUT/stage,n,a)) for n in range(1,73) for a in ARMS]
SUMS=('paid','paid_rays','emergency_rays','combined_rays','steps','distance_m','blocked','interventions','contacts','new_cells','changed_known_cells','decision_ms','update_ms','initialization_ms','memory_sensor_ms','emergency_sensor_ms','navigation_planning_ms','point_planning_ms','safety_decision_ms','wall_s','scene_s','loop_s')
def agg(rows):
    success=[r for r in rows if r['success']]
    return {'episodes':len(rows),'goals':sum(r['success'] for r in rows),'contact_free_goals':sum(r['contact_free_success'] for r in rows),'success_rate':mean(r['success'] for r in rows),
    **{k+'_total':sum(r[k] for r in rows) for k in SUMS},**{k+'_mean':mean(r[k] for r in rows) for k in SUMS},
    **{k+'_success_only_mean':mean(r[k] for r in success) if success else None for k in ('paid','steps','distance_m','decision_ms','wall_s')}}
def nondominated(summary,keys):
    return [a for a in summary if not any(b!=a and all(sign*summary[b][k]<=sign*summary[a][k] for k,sign in keys) and any(sign*summary[b][k]<sign*summary[a][k] for k,sign in keys) for b in summary)]
def savefig(fig,directory,name):
    fig.savefig(directory/(name+'.png'),bbox_inches='tight');fig.savefig(directory/(name+'.pdf'),bbox_inches='tight');plt.close(fig)
def main():
    deadline_guard(180)
    for stage in ('maps','fit_replay','smoke','primary','timing_repeat'):verify_manifest(OUT/stage)
    target=OUT/'analysis';target.mkdir(exist_ok=False);figs=target/'figures';figs.mkdir();mapsdir=figs/'maps';mapsdir.mkdir()
    rows=load('primary');old=load('fit_replay');repeat=load('timing_repeat');idx={(r['episode'],r['arm']):r for r in rows};repidx={(r['episode'],r['arm']):r for r in repeat}
    summary={a:agg([r for r in rows if r['arm']==a]) for a in ARMS};fit_summary={a:agg([r for r in old if r['arm']==a]) for a in ARMS};repeat_summary={a:agg([r for r in repeat if r['arm']==a]) for a in ARMS}
    family={f:{a:agg([r for r in rows if r['arm']==a and r['family']==f]) for a in ARMS} for f in ('R','BP','M')}
    # Exact primary/repeat semantics were checked by the runner. Median paired
    # timing is descriptive; primary navigation statistics are never doubled.
    medians=[]
    for r in rows:
        q=repidx[r['episode'],r['arm']];medians.append({**{k:r[k] for k in ('episode','arm','identity','schedule')},**{k:float(np.median([r[k],q[k]])) for k in ('decision_ms','update_ms','initialization_ms','memory_sensor_ms','emergency_sensor_ms','navigation_planning_ms','wall_s')}})
    timing_compare={a:{k:repeat_summary[a][k+'_total']/summary[a][k+'_total'] if summary[a][k+'_total'] else None for k in ('decision_ms','memory_sensor_ms','wall_s')} for a in ARMS}
    csvwrite(target/'episodes.csv',rows);csvwrite(target/'fit_replay_metrics.csv',old);csvwrite(target/'timing_repeat_metrics.csv',repeat);csvwrite(target/'paired_median_timings.csv',medians)
    csvwrite(target/'overall.csv',[{'arm':a,**summary[a]} for a in ARMS]);csvwrite(target/'family.csv',[{'family':f,'arm':a,**family[f][a]} for f in family for a in ARMS])
    csvwrite(target/'failures.csv',[r for r in rows if not r['success']])
    matrix=[{'episode':n,'identity':idx[n,ARMS[0]]['identity'],'family':idx[n,ARMS[0]]['family'],'schedule':idx[n,ARMS[0]]['schedule'],**{a:idx[n,a]['success'] for a in ARMS}} for n in range(1,73)];csvwrite(target/'success_matrix.csv',matrix)
    # Original map order is12/family, two adjacent schedules per lineage.
    rng=np.random.default_rng(2026111401);clusters=rng.integers(0,36,(5000,36));sample=(clusters[:,:,None]*2+np.arange(2)).reshape(5000,72)
    pairs=[]
    for a in ARMS:
        for b in ('periodic4','age4','age5'):
            if a==b:continue
            aa=[idx[n,a] for n in range(1,73)];bb=[idx[n,b] for n in range(1,73)];sa=np.array([r['success'] for r in aa],bool);sb=np.array([r['success'] for r in bb],bool);common=sa&sb
            pair={'candidate':a,'reference':b,'rescues':int((sa&~sb).sum()),'harms':int((~sa&sb).sum()),'common_successes':int(common.sum()),'common_failures':int((~sa&~sb).sum()),'contrasts':{}}
            pair.update(rescued_episodes=[int(i)+1 for i in np.flatnonzero(sa&~sb)],harmed_episodes=[int(i)+1 for i in np.flatnonzero(~sa&sb)],common_success_episodes=[int(i)+1 for i in np.flatnonzero(common)],common_failure_episodes=[int(i)+1 for i in np.flatnonzero(~sa&~sb)])
            for k in ('success','paid','combined_rays','steps','distance_m','decision_ms','wall_s'):
                diff=np.array([r[k]-s[k] for r,s in zip(aa,bb)],float);boot=diff[sample].mean(axis=1)
                pair['contrasts'][k]={'mean_delta':float(diff.mean()),'cluster_bootstrap95':np.percentile(boot,[2.5,97.5]).tolist()}
                if k!='success':
                    numerator=(diff*common)[sample].sum(axis=1);den=common[sample].sum(axis=1);valid=den>0
                    pair['contrasts'][k]['common_success_delta']=float(diff[common].mean()) if common.any() else None
                    pair['contrasts'][k]['common_success_cluster95']=np.percentile(numerator[valid]/den[valid],[2.5,97.5]).tolist() if valid.any() else None
            pairs.append(pair)
    write(target/'paired_cluster_analysis.json',{'unit':'36 map lineages; two schedules kept together','resamples':5000,'seed':2026111401,'unadjusted_exploratory':True,'comparisons':pairs})
    csvwrite(target/'paired_summary.csv',[{**{k:p[k] for k in ('candidate','reference','rescues','harms','common_successes','common_failures')},**{k+'_delta':v['mean_delta'] for k,v in p['contrasts'].items()},**{k+'_common_success_delta':v['common_success_delta'] for k,v in p['contrasts'].items() if k!='success'}} for p in pairs])
    safe={a:s for a,s in summary.items() if s['contacts_total']==0};eligible=safe or {a:s for a,s in summary.items() if s['contacts_total']==min(v['contacts_total'] for v in summary.values())}
    frontier=nondominated(eligible,[('goals',-1),('paid_total',1),('combined_rays_total',1),('steps_total',1),('distance_m_total',1),('decision_ms_total',1),('wall_s_total',1)])
    two_frontier=nondominated(eligible,[('goals',-1),('paid_total',1)])
    break_even=[]
    for a in ('caa_full','raa_defer'):
        for b in ('periodic4','age4','age5'):
            delta=sum(summary[a][k+'_total']-summary[b][k+'_total'] for k in ('decision_ms','update_ms','initialization_ms'));saved=summary[b]['paid_total']-summary[a]['paid_total']
            noinit=delta-(summary[a]['initialization_ms_total']-summary[b]['initialization_ms_total'])
            break_even.append({'candidate':a,'reference':b,'extra_fixed_ms':delta,'extra_fixed_without_initialization_ms':noinit,'saved_observations':saved,'positive_crossover_ms':delta/saved if saved>0 and delta>0 else None,'positive_crossover_without_initialization_ms':noinit/saved if saved>0 and noinit>0 else None,'interpretation':'positive crossover: candidate cheaper only above it' if saved>0 and delta>0 else 'candidate never cheaper for nonnegative observation cost' if saved<=0 and delta>=0 else 'candidate already cheaper at zero; inspect slope'})
    write(target/'break_even.json',break_even)
    quantiles={}
    for a in ARMS:
        ns=[v/1e6 for n in range(1,73) for v in episode(OUT/'primary',n,a)['diagnostics']['timing_ns']['decision']]
        quantiles[a]={'mean_ms':float(np.mean(ns)),**{k:float(np.percentile(ns,q)) for k,q in [('median_ms',50),('p95_ms',95),('p99_ms',99),('max_ms',100)]},'calls':len(ns)}
    # Structural coverage and all36 map images. No unseen world is generated here.
    info=json.loads((OUT/'maps/summary.json').read_text());payloads=[json.loads((OUT/'maps'/r['path']).read_text()) for r in info['maps']]
    def drawmap(ax,p,title):
        g=raster(p['geometry']['free']);ax.imshow(g,cmap='Greys',vmin=0,vmax=1,origin='lower')
        start=p['world']['start'];goal=p['world']['goal'];ax.scatter(*start,c='limegreen',s=22,marker='o');ax.scatter(*goal,c='crimson',s=30,marker='*')
        for si,sch in enumerate(p['world']['schedules']):
            cells=sch.get('positions') or sch.get('initial') or [e['cell'] for e in sch.get('events',[])]
            if cells:
                pts=np.array(cells);ax.plot(pts[:,0],pts[:,1],'.',ms=2,color=('dodgerblue','orange')[si],alpha=.6)
            for event in sch.get('events',[]):
                ax.scatter(*event['cell'],marker='+' if event['action']=='add' else 'x',s=18,c='red' if event['action']=='add' else 'teal',linewidths=.7,alpha=.7)
        ax.set_title(title,fontsize=8);ax.set_xticks([]);ax.set_yticks([])
    fig,axs=plt.subplots(6,6,figsize=(14,14))
    for i,(p,ax) in enumerate(zip(payloads,axs.flat)):
        title=f'{i+1:02} {p["mechanism"]} / {p["seed"]}';drawmap(ax,p,title)
        f,a=plt.subplots(figsize=(5,5));drawmap(a,p,title);savefig(f,mapsdir,f'map_{i+1:02}')
    fig.suptitle('36 prospectively generated H2 maps | green start, red goal, blue/orange schedules');fig.tight_layout();savefig(fig,figs,'01_map_atlas')
    def bars(name,key,ylabel,scale=1,log=False):
        fig,ax=plt.subplots(figsize=(12,4));ax.bar(LABELS,[summary[a][key]*scale for a in ARMS],color=COLORS);ax.set_ylabel(ylabel);ax.tick_params(axis='x',rotation=45)
        if log:ax.set_yscale('log')
        ax.set_title('H2 unseen72 | primary run | all episodes');savefig(fig,figs,name)
    bars('02_success','success_rate','Goal success (%)',100);bars('03_paid','paid_mean','Paid observations / episode');bars('05_combined_rays','combined_rays_mean','Memory + emergency rays / episode');bars('06_decision_cost','decision_ms_mean','Decision ms / episode (log scale)',log=True);bars('07_episode_wall','wall_s_mean','Episode wall seconds')
    fig,axs=plt.subplots(1,2,figsize=(14,4))
    for ax,k,title in zip(axs,('steps_mean','distance_m_mean'),('Elapsed steps (H80, failures included)','Travel distance (m, failures included)')):
        ax.bar(LABELS,[summary[a][k] for a in ARMS],color=COLORS);ax.set_title(title);ax.tick_params(axis='x',rotation=65)
    savefig(fig,figs,'04_movement')
    for name,key,xlabel in [('08_success_paid','paid_mean','Paid observations / episode'),('09_success_compute','decision_ms_mean','Decision ms / episode'),('10_pareto','paid_mean','Paid observations / episode')]:
        fig,ax=plt.subplots(figsize=(10,6))
        for i,a in enumerate(ARMS):
            s=summary[a];ax.scatter(s[key],100*s['success_rate'],c=[COLORS[i]],marker='x' if s['contacts_total'] else 'o',s=65);ax.annotate(LABEL[a],(s[key],100*s['success_rate']),xytext=(5,(i%3-1)*12),textcoords='offset points',fontsize=8)
        if name=='10_pareto':
            fs=sorted(two_frontier,key=lambda a:summary[a][key]);ax.plot([summary[a][key] for a in fs],[100*summary[a]['success_rate'] for a in fs],'k--',alpha=.5,label='Zero-contact 2D frontier');ax.legend()
        if key=='decision_ms_mean':ax.set_xscale('log')
        ax.set_xlabel(xlabel);ax.set_ylabel('Goal success (%)');ax.set_title('H2 unseen72 | contacts shown as crosses');savefig(fig,figs,name)
    fig,axs=plt.subplots(1,3,figsize=(17,5),sharey=True)
    for ax,f in zip(axs,('R','BP','M')):
        ax.bar(LABELS,[family[f][a]['success_rate']*100 for a in ARMS],color=COLORS);ax.set_title(f'{f}: 12 maps / 24 cases');ax.tick_params(axis='x',rotation=85);ax.set_ylim(0,105)
    axs[0].set_ylabel('Goal success (%)');savefig(fig,figs,'11_family_success')
    fig,axs=plt.subplots(1,2,figsize=(16,5));x=np.arange(12)
    for ax,k,title in zip(axs,('success_rate','paid_mean'),('Success rate','Paid observations / episode')):
        ax.bar(x-.18,[fit_summary[a][k] for a in ARMS],.36,label='Reused FIT72');ax.bar(x+.18,[summary[a][k] for a in ARMS],.36,label='New H2 unseen72');ax.set_xticks(x,LABELS,rotation=75);ax.set_title(title);ax.legend()
    savefig(fig,figs,'12_fit_vs_unseen')
    mat=np.array([[idx[n,a]['success'] for a in ARMS] for n in range(1,73)])
    fig,ax=plt.subplots(figsize=(11,14));ax.imshow(mat,aspect='auto',cmap=matplotlib.colors.ListedColormap(['#d6604d','#4daf4a']),vmin=0,vmax=1);ax.set_xticks(range(12),LABELS,rotation=70);ax.set_yticks(range(72),[f'{n:02} {idx[n,ARMS[0]]["family"]} s{idx[n,ARMS[0]]["schedule"]}' for n in range(1,73)],fontsize=6)
    for y in (23.5,47.5):ax.axhline(y,color='white',lw=2)
    ax.set_title('All72 primary outcomes | green goal / red failure');savefig(fig,figs,'13_success_heatmap')
    costs=np.logspace(-3,5,241);fig,ax=plt.subplots(figsize=(11,6))
    for i,a in enumerate(ARMS):
        s=summary[a];fixed=sum(s[k+'_total'] for k in ('decision_ms','update_ms','initialization_ms'));ax.loglog(costs,(fixed+s['paid_total']*costs)/72,label=LABEL[a],color=COLORS[i])
    measured=sum(summary[a]['memory_sensor_ms_total'] for a in ARMS)/sum(summary[a]['paid_total'] for a in ARMS);ax.axvline(measured,ls='--',color='k',label=f'Measured simulator mean {measured:.3g} ms')
    ax.set_xlabel('Assumed cost per paid observation (ms)');ax.set_ylabel('Decision + initialization + update + paid cost (ms / case)');ax.set_title('Hypothetical observation cost model | not measured hardware energy');ax.legend(ncol=2,fontsize=8);savefig(fig,figs,'14_break_even')
    fig,ax=plt.subplots(figsize=(12,5));xs=np.arange(12)
    for i,(k,m) in enumerate((('median_ms','o'),('p95_ms','s'),('p99_ms','^'),('max_ms','x'))):ax.plot(xs,[quantiles[a][k] for a in ARMS],marker=m,label=k)
    ax.set_xticks(xs,LABELS,rotation=60);ax.set_yscale('log');ax.set_ylabel('Decision call ms');ax.legend();savefig(fig,figs,'15_decision_quantiles')
    # Deterministic representative selection under frozen rule.
    chosen=[]
    for a in ('caa_full','raa_defer'):
        flips=[n for n in range(1,73) if idx[n,a]['success']!=idx[n,'age5']['success']]
        if flips:chosen.append((flips[0],a,'first_success_contrast'))
        n=max(range(1,73),key=lambda n:abs(idx[n,a]['paid']-idx[n,'age5']['paid']));chosen.append((n,a,'largest_paid_difference'))
    trajectories=[]
    for n,a,why in chosen:
        p=payloads[(n-1)//2];fig,axs=plt.subplots(1,2,figsize=(11,5))
        for ax,arm in zip(axs,('age5',a)):
            e=episode(OUT/'primary',n,arm);drawmap(ax,p,LABEL[arm]);xy=np.array([f['position'] for f in e['trace']['steps']]);ax.plot(xy[:,0],xy[:,1],color='purple',lw=1.5);sc=np.array([f['position'] for f in e['trace']['steps'] if f['observation_granted']]);ax.scatter(sc[:,0],sc[:,1],s=15,facecolors='none',edgecolors='cyan');r=idx[n,arm];ax.set_title(f'{LABEL[arm]} | goal {r["success"]}, paid {r["paid"]}, steps {r["steps"]}')
        fig.suptitle(f'Case{n:02} {p["mechanism"]} schedule{(n-1)%2} | {why}');name=f'trajectory_{n:02}_{a}_{why}';savefig(fig,figs,name);trajectories.append({'episode':n,'candidate':a,'selection':why,'figure':name+'.png'})
    struct=[]
    fitworlds=ref.navigation.admitted_worlds()
    for group,worlds in (('FIT36',fitworlds),('H2_new36',payloads)):
        for p in worlds:
            free=set(map(tuple,p['geometry']['free']));degrees=[sum((x+dx,y+dy) in free for dx,dy in ((1,0),(-1,0),(0,1),(0,-1))) for x,y in free]
            struct.append({'group':group,'family':p['mechanism'],'identity':p['identity'],'free_cells':len(free),'point_shortest_distance':p['world']['distance'],'dead_end_cells':degrees.count(1),'junction_cells':sum(v>=3 for v in degrees),'dynamics0':p['world']['schedules'][0]['category'],'dynamics1':p['world']['schedules'][1]['category']})
    csvwrite(target/'structural_coverage.csv',struct)
    oracle=int(np.any(mat,axis=1).sum());data={'summary':summary,'fit_summary':fit_summary,'repeat_summary':repeat_summary,'family':family,'decision_call_quantiles':quantiles,'timing_repeat_to_primary_ratios':timing_compare,'pareto_all_axes_zero_contact':frontier,'pareto_success_paid_zero_contact':two_frontier,'oracle_casewise_goals_upper_bound':oracle,'trajectories':trajectories,'primary_cases':72,'lineages':36,'primary_policy_episodes':864,'timing_repeat_policy_runs':864,'timing_repeat_independent_cases':0,'bootstrap_resamples':5000,'measured_mean_memory_sensor_ms':measured}
    ranks=[]
    for group,ss in (('FIT72',fit_summary),('H2_unseen72',summary)):
        for a in ARMS:
            ranks.append({'group':group,'arm':a,'success_rank':1+sum(ss[b]['goals']>ss[a]['goals'] for b in ARMS),'paid_rank':1+sum(ss[b]['paid_total']<ss[a]['paid_total'] for b in ARMS),'decision_cost_rank':1+sum(ss[b]['decision_ms_total']<ss[a]['decision_ms_total'] for b in ARMS),'goals':ss[a]['goals'],'paid':ss[a]['paid_total']})
    csvwrite(target/'rankings.csv',ranks)
    csvwrite(target/'generalization_changes.csv',[{'arm':a,**{k+'_FIT':fit_summary[a][k] for k in ('success_rate','paid_mean','steps_mean','distance_m_mean','decision_ms_mean','wall_s_mean')},**{k+'_unseen':summary[a][k] for k in ('success_rate','paid_mean','steps_mean','distance_m_mean','decision_ms_mean','wall_s_mean')},**{k+'_unseen_minus_FIT':summary[a][k]-fit_summary[a][k] for k in ('success_rate','paid_mean','steps_mean','distance_m_mean','decision_ms_mean','wall_s_mean')}} for a in ARMS])
    assessment=[]
    for a in ('caa_full','raa_defer'):
        for b in ('periodic4','age4','age5'):
            assessment.append({'candidate':a,'reference':b,'goal_delta':summary[a]['goals']-summary[b]['goals'],'paid_delta':summary[a]['paid_total']-summary[b]['paid_total'],'zero_contacts':summary[a]['contacts_total']==0,'descriptively_maintains_success_and_saves_scans':summary[a]['contacts_total']==0 and summary[a]['goals']>=summary[b]['goals'] and summary[a]['paid_total']<summary[b]['paid_total'],'not_noninferiority_proof':True})
    write(target/'target_assessment.json',assessment)
    csvwrite(target/'timing_and_observation_related_cost.csv',[{'arm':a,'stage':stage,'decision_ms':ss[a]['decision_ms_total'],'initialization_ms':ss[a]['initialization_ms_total'],'refresh_ms':ss[a]['update_ms_total'],'actual_memory_sensor_ms':ss[a]['memory_sensor_ms_total'],'measured_observation_related_total_ms':sum(ss[a][k+'_total'] for k in ('decision_ms','initialization_ms','update_ms','memory_sensor_ms')),'end_to_end_wall_s':ss[a]['wall_s_total']} for stage,ss in (('primary',summary),('timing_repeat',repeat_summary)) for a in ARMS])
    write(target/'summary.json',data)
    report(data,pairs,break_even,struct,info,target)
    manifest(target);print('H2 report/tables/figures complete; frontier:',frontier,flush=True)

def report(data,pairs,break_even,struct,admission,target):
    s=data['summary'];old=data['fit_summary'];labels=LABEL
    def table():
        text='| Model | Goals | Contacts | Paid scans | H80 steps | Distance m | Combined rays | Decision ms/case | Wall s/case |\n|---|---:|---:|---:|---:|---:|---:|---:|---:|\n'
        for a in ARMS:
            r=s[a];text+=f'| {labels[a]} |{r["goals"]}/72|{r["contacts_total"]}|{r["paid_total"]}|{r["steps_total"]}|{r["distance_m_total"]:.2f}|{r["combined_rays_total"]}|{r["decision_ms_mean"]:.4f}|{r["wall_s_mean"]:.4f}|\n'
        return text
    lines=['# H2 final research report: adaptive observation scheduling','',
    '## Abstract','',
    'We conclude H2 with a prospectively frozen comparison of twelve previously developed observation schedulers on36 freshly generated R/BP/M map lineages, two schedules each. The864 primary policy episodes are accompanied by864 exact FIT reproduction episodes and864 timing repeat runs. Repeats are not independent navigation samples. All candidate parameters and original G1/safety/sensor settings remained fixed. This is new-map generalization under a documented conditional generator, not an independently custodied sealed superiority trial.','',table(),
    '## Motivation and research questions','',
    'Paid memory observations trade freshness and discovery against sensing and computation. H2 asked whether public spatial memory, route relevance, observed change history and viewpoint timing can improve goal completion or reduce paid observations without sacrificing safety; whether those effects transfer to fresh maps; and whether added decision cost is justified. The final benchmark addresses success, sensing, movement, compute and map-family tradeoffs without reducing them to one arbitrary weighted score.','',
    '## Previously developed hypotheses and implementations','',
    'Periodic clocks and local stale-fraction Age rules provide simple baselines. Cadence controls separate longer intervals/deadlines from adaptive mechanisms. Directional/view/route Age variants ask whether stale local information is relevant to the upcoming path. Age-Route-Rescue adds a public-route rescue to a directional veto; Route-Clock also proactively refreshes relevant route neighbors. RDAO models visible uncertain route regions with a V×U×D×T heuristic, a remaining-budget threshold and viewpoint competition; v2.1 changes current-view angular quality. These are heuristics, not calibrated value of information. CAA classifies cells using authorized repeated readings/endpoint-change history: Fast and Full use fixed age4/5/6 priorities, with no simulator change labels. RAA uses an Age5 parent and conservative public route/view conditions: Defer postpones a narrowly certified request exactly one decision and protects the first noninitial scan.','',
    'H2 also tested persistence/EVI and topology/multistep candidates, unconditional event/route triggers, DAO history/deadline suppression, and predictive safety engineering. More detailed hypotheses frequently failed to translate into better rollouts. The latest DAO Deadline/Stable/Quiet screens achieved52/51/51 goals on FIT72, below66 for simple references; no revision of those weak parents was admitted here. Predictive safety was rejected after contacts and lost completions in hand scenes; it was never substituted into this benchmark. RAA Advance/Joint reached59 goals on FIT72 and were rejected. RAA-Defer and historical CAA-Full each reduced Age5 scans770→768 at66 goals, an extremely small development signal. These negative results remain preserved, not erased by final model selection.','',
    '## Development benchmark and exact reproduction','',
    '| Model | Reproduced FIT72 goals | FIT paid | New goals | New paid | Goal-rate change pp |\n|---|---:|---:|---:|---:|---:|',
    *[f'|{labels[a]}|{old[a]["goals"]}|{old[a]["paid_total"]}|{s[a]["goals"]}|{s[a]["paid_total"]}|{100*(s[a]["success_rate"]-old[a]["success_rate"]):+.2f}|' for a in ARMS], '',
    'All twelve arms were re-executed on all72 historical keys before unseen generation. Existing metric signatures and semantic traces match exactly; RDAO archives expose a smaller saved metric projection, which was compared in full along with all saved navigation/sensing semantics. New and FIT sets are not paired maps. Computation comparisons use the new unified FIT replay instrument, not historical zero placeholders or differing timer scopes.','',
    '## Independent map generation and admission methodology','',
    'The original frozen25×25 R/BP/M construction, ordered start/goal sampling and two original dynamics laws were reused through a separate H2 stream adapter. Seeds start910000000(R),910010000(BP),910030000(M), sequentially within each family; independent framed SHA256/Philox streams use h2-final-generalization-v1-20261114. First12 admitted lineages per family are retained. Geometry, objects, pedestrian paths and schedules are freshly sampled; schedules may legitimately draw no dynamics or identical categories. There is no outcome-based balancing, seed search, repair or case removal.','',
    f'Admission counts: `{json.dumps(admission["candidate_counts"],sort_keys=True)}`. Every attempted candidate, reason, stream counter, accepted hash and static witness is saved. Accessible authorized FIT checkpoint geometries (including related/rejected attempts) and newly accepted maps were checked for exact D4 raster copies, free-space Jaccard distance<=0.05 and exact normalized raster-quotient topology equality using the existing monitored macOS nauty backend. No reserved or sealed evaluation world was opened. Historical FIT evidence was consulted read-only for duplicate exclusion and integrity, not reused as a new case. Opaque protected signatures were unavailable; complete near-topology/graph-edit exclusion is not established.','',
    'Static G1 geometry admission checks the deterministic shortest point path using the original sampled MuJoCo G1 move/turn checker, east initial heading, at initial and every persistent-event occupancy state in each schedule. These offline truth-based admission queries are separate from runtime selected-action-only shield accounting. They never enter a scheduler. Persistent occupied cells use static wall-box proxies for this witness, conservatively taller than the runtime persistent objects. A witness is sufficient for its sampled static path only: dynamic pedestrian safety, continuous geometry and H80 completion are not guaranteed. Conditioning on duplicate separation and a specific static witness changes the admitted population; this limits claims of an identical unconditioned FIT difficulty distribution. Structural coverage is saved in structural_coverage.csv.','',
    'This named36-map evaluation was explicitly approved by the owner, superseding previous proposal-only restrictions solely for this final H2 population. The disabled DAO production generators,24-lineage pilot and80/200-lineage proposals remain disabled/unexecuted. Same-investigator local generation is not independent custody. No sealed/reserved evaluation dataset was accessed.','',
    '![All36 maps](../results/phase2_mujoco/h2_final_generalization_v1/analysis/figures/01_map_atlas.png)','',
    '## Frozen evaluation and computational measurement','',
    'The prospective protocol and source binding were committed before unseen generation. Original Unitree G1 MuJoCo navigation, ternary last-write memory, emergency safety and selected-action shield,61-ray120-degree6m memory sensor, seed42,H80 and cap20(initial included) remain unchanged. Algorithms receive only their original public inputs. Twelve public FIT warmups precede each stage. Cyclic arm order balances every arm across twelve execution positions in72 cases; the timing repeat reverses per-case order. Forty-eight smoke runs precede primary evaluation and are required to match the corresponding primary semantics.','',
    'Core decide, refresh, initialization, authorized memory provider, emergency sensor, G1 navigation callback, evaluator point-plan diagnostics and safety choice are timed separately with perf_counter_ns. Sensor/refresh work is outside decide. Inherited policy planning and policy diagnostic computations remain inside the original API timings; these are executable API costs rather than stripped score kernels. Refresh includes historical after-observation bookkeeping/planning. The actual sensor callback and navigation plan costs are not inferred from ray counts. Per-call vectors retain median/p95/p99/max; complete primary/repeat metrics and two-run per-key median times are saved. These are instrumented single-machine costs with remaining OS/order effects, not hardware latency/energy estimates.','',
    '## Overall results and generalization','',table(),
    '![Success](../results/phase2_mujoco/h2_final_generalization_v1/analysis/figures/02_success.png)',
    '![Sensing](../results/phase2_mujoco/h2_final_generalization_v1/analysis/figures/03_paid.png)',
    '![Movement](../results/phase2_mujoco/h2_final_generalization_v1/analysis/figures/04_movement.png)',
    '![Combined rays](../results/phase2_mujoco/h2_final_generalization_v1/analysis/figures/05_combined_rays.png)',
    '![FIT versus unseen](../results/phase2_mujoco/h2_final_generalization_v1/analysis/figures/12_fit_vs_unseen.png)','',
    'Failure-inclusive H80 steps/distance are distinct from success-only means in overall.csv. A shorter failed path is not an efficiency benefit. Goals and contact-free goals are both recorded; any contact prevents calling a method safe or recommending it solely on efficiency. The final data identify descriptive tradeoffs, not a universal winner.','',
    '## Paired comparisons and uncertainty','',
    '| Candidate vs Age5 | Rescue / harm | Common success | Paid delta/case | 95% cluster interval | Common-success step delta | Common-success distance delta m |\n|---|---:|---:|---:|---|---:|---:|',
    *[f'|{labels[p["candidate"]]}|{p["rescues"]} / {p["harms"]}|{p["common_successes"]}|{p["contrasts"]["paid"]["mean_delta"]:+.4f}|{p["contrasts"]["paid"]["cluster_bootstrap95"]}|{p["contrasts"]["steps"]["common_success_delta"]:+.4f}|{p["contrasts"]["distance_m"]["common_success_delta"]:+.4f}|' for p in pairs if p['reference']=='age5'], '',
    'Full paired tables include all eleven nonself contrasts against each of Periodic4/Age4/Age5, rescue/harm/common failure, sensing/movement/compute and common-success costs. Bootstrap5000 draws with seed2026111401 resamples36 whole lineages, preserving each pair of schedules. Intervals are exploratory, unadjusted across many comparisons and conditional on this admitted sample; lack of significance does not prove equality/noninferiority. Small samples, family counts12 and retrospective development selection limit power and external inference.','',
    f'The posthoc case-wise oracle succeeds on{data["oracle_casewise_goals_upper_bound"]}/72. This uses future outcome labels and is only an unattainable reference upper bound, not an implemented adaptive policy. failures.csv and success_matrix.csv retain every failure and all72×12 outcomes.','',
    '![All outcomes](../results/phase2_mujoco/h2_final_generalization_v1/analysis/figures/13_success_heatmap.png)','',
    '## Map-family effects','',
    '| Family | Model | Goals /24 | Paid scans | Combined rays |\n|---|---|---:|---:|---:|',
    *[f'|{f}|{labels[a]}|{data["family"][f][a]["goals"]}|{data["family"][f][a]["paid_total"]}|{data["family"][f][a]["combined_rays_total"]}|' for f in ('R','BP','M') for a in ARMS], '',
    'Family differences are descriptive interaction evidence, not posthoc license to dispatch on hidden family IDs. Object/pedestrian categories and structural coverage are retained for interpretation without causal attribution from observed correlations.','',
    '![Family comparison](../results/phase2_mujoco/h2_final_generalization_v1/analysis/figures/11_family_success.png)','',
    '## Computational efficiency and break-even','',
    '| Model | Mean decide ms/step | Median / p95 / p99 / max ms | Update total ms | Actual memory sensor total ms | Emergency sensor total ms | G1 plan total ms | Primary / repeat wall s |\n|---|---:|---|---:|---:|---:|---:|---|',
    *[f'|{labels[a]}|{data["decision_call_quantiles"][a]["mean_ms"]:.5f}|'+ ' / '.join(f'{data["decision_call_quantiles"][a][k]:.5f}' for k in ('median_ms','p95_ms','p99_ms','max_ms'))+f'|{s[a]["update_ms_total"]:.3f}|{s[a]["memory_sensor_ms_total"]:.3f}|{s[a]["emergency_sensor_ms_total"]:.3f}|{s[a]["navigation_planning_ms_total"]:.3f}|{s[a]["wall_s_total"]:.3f} / {data["repeat_summary"][a]["wall_s_total"]:.3f}|' for a in ARMS], '',
    'Fixed full-matrix repeat timings and primary/repeat ratios are in summary.json, with paired median timing CSV. Repetitions add no independent maps or navigation evidence. Highly variable microsecond costs and single-machine order effects should not support precise cross-platform claims.','',
    '![Decision costs](../results/phase2_mujoco/h2_final_generalization_v1/analysis/figures/06_decision_cost.png)',
    '![Decision quantiles](../results/phase2_mujoco/h2_final_generalization_v1/analysis/figures/15_decision_quantiles.png)',
    '![Wall times](../results/phase2_mujoco/h2_final_generalization_v1/analysis/figures/07_episode_wall.png)','',
    'Observation-related hypothetical cost is decision_ms+refresh_ms+initialization_ms+paid_count×c_ms (also provide requested form without initialization). It excludes navigation/emergency and is not an end-to-end runtime or energy model. Crossover conditions follow fixed-cost difference divided by observations saved; with no saving, an extra-compute method cannot break even by increasing sensing cost.','',
    '| Candidate | Reference | Observations saved | Extra fixed ms | Positive crossover ms/scan |\n|---|---|---:|---:|---|',
    *[f'|{labels[b["candidate"]]}|{labels[b["reference"]]}|{b["saved_observations"]}|{b["extra_fixed_ms"]:.4f}|{b["positive_crossover_ms"] if b["positive_crossover_ms"] is not None else b["interpretation"]}|' for b in break_even], '',
    f'The measured pooled simulator observation is{data["measured_mean_memory_sensor_ms"]:.5f}ms/scan. It is only a plotted reference. Real robots may have very different latency/compute/power costs. Energy was not measured; no power-saving claim is made.','',
    '![Break-even](../results/phase2_mujoco/h2_final_generalization_v1/analysis/figures/14_break_even.png)','',
    '## Contact-aware Pareto analysis','',
    'Zero-contact full-axis nondominated set: '+', '.join(labels[a] for a in data['pareto_all_axes_zero_contact'])+'. Two-axis success/paid frontier: '+', '.join(labels[a] for a in data['pareto_success_paid_zero_contact'])+'.',
    'A high-dimensional frontier can retain many methods, particularly with noisy wall time; this is not proof they are equally useful. The CSV exposes all axes and paired common-success costs. Practical recommendation must prioritize reliable completion and absence of contacts before savings in scans or CPU.','',
    '![Success-paid](../results/phase2_mujoco/h2_final_generalization_v1/analysis/figures/08_success_paid.png)',
    '![Success-compute](../results/phase2_mujoco/h2_final_generalization_v1/analysis/figures/09_success_compute.png)',
    '![Pareto](../results/phase2_mujoco/h2_final_generalization_v1/analysis/figures/10_pareto.png)','',
    '## Representative trajectories','',
    'Examples follow the predeclared first outcome contrast / largest absolute paid difference rule, not a favorable-case selection. Cyan circles indicate actual paid readings. These are outcome/path associations, not isolated causal interventions.','',
    *[f'![Case{t["episode"]}: {t["selection"]}](../results/phase2_mujoco/h2_final_generalization_v1/analysis/figures/{t["figure"]})' for t in data['trajectories']], '',
    '## Discussion, negative results and original contributions','',
    'Complex observation decisions do not automatically dominate clocks. Public memory contains only authorized first-hit observations, so predicted visibility can miss newly discoverable cells; a geometric score is not expected goal benefit. An earlier scan changes route/timing and consumes scarce budget, while a deferred reading can conceal changes before a later forced observation. Long-lived transient occupancy and G1 turning/rejected-action feedback complicate point-route heuristics. These mechanisms are supported by the preserved earlier trace analyses; final aggregate associations alone do not identify a unique causal explanation.','',
    'Contributions are the implemented public-information scheduling families, explicit authorization/budget/history semantics, controlled ablations and negative findings, reproducible original-G1 integration, and this frozen twelve-model new-lineage/cost benchmark. Distinct implementation mechanisms and a useful reproducibility artifact do not establish globally novel algorithms or calibrated value-of-information theory. Report practical tradeoffs without manufacturing a superior winner.','',
    '## Limitations and integrity','',
    'Only36 conditionally admitted maps and two correlated schedules each; same investigator and machine, no independent custody, no opaque protected signatures, incomplete near-topology proof, static shortest-path admission bias, original discrete kinematic environment and horizon80. Safety/contact results are confined to these scenes and do not reverse archived pedestrian contacts or prove physical humanoid safety. Multiple models/metrics are exploratory; FIT was repeatedly reused in development. No new algorithms, parameter fitting, thresholds, outcome exclusions or safety changes were made. Only the newly approved H2 final36-map population was generated; earlier DAO pilot/production populations remain ungenerated.','',
    'Related tests:163 passed in final pre-freeze gate (15 benchmark plumbing cases plus frozen-model/safety regressions). An initial incorrect test filename ran no tests; its original log is preserved. The historical native-build directory was missing, so a separately committed pre-draw restoration pinned the existing local pynauty2.8.8.1/nauty2_8_8 build and reproduced all51 available archived exact graph keys before any unseen draw. Original sources, seed/admission laws and failed setup evidence were preserved; the new native hash differs from the missing old binary. See h2_backend_recovery_v1_1.md. Pre-freeze harness representation/timing and geometric-admission design corrections are documented in setup_notes.md, with no unseen outcome access. Baseline parity gates all864 FIT replays. Actual sensor authorization, cap20 and selected-only shield accounting are checked per episode; timing repeat exact semantics are required. Known20 pre-existing historical archive issue entries are recorded separately, never silently repaired. Final verification and recursive manifest are stored alongside the evidence.','',
    '## Final H2 conclusion and future directions','',
    'The fixed-model results above close H2 observation scheduling. A defensible conclusion distinguishes new-map performance from a small reused-FIT scan saving and distinguishes cheaper sensing counts from actual decision/runtime costs. No statistically nonsignificant contrast is interpreted as equivalence. Future independent custody, broader distributions, longer routes, calibrated visibility/value models and real-hardware latency/energy studies would require new approval and a new project protocol; this task performs no further algorithm development.','',
    '## Artifacts and reproduction','',
    '`results/phase2_mujoco/h2_final_generalization_v1/` holds source binding, tests,prior preservation,maps/admission,full FIT replay,smoke,primary,timing_repeat,analysis tables/figures,verification and final manifest. Protocol: docs/h2_final_evaluation_protocol_v1.md. Runner stages: run_h2_final.py freeze / fit_replay; h2_generate_maps.py; run_h2_final.py smoke / primary / timing_repeat; report_h2_final.py. Frozen stages refuse overwrite; partial stages retain exclusive episodes and a hash journal for validated resume. Portfolio unchanged.']
    # Result-specific answer, kept explicit rather than a generic conclusion.
    maximum=max(v['goals'] for v in s.values());leaders=[a for a in ARMS if s[a]['goals']==maximum]
    practical=min([a for a in leaders if s[a]['contacts_total']==0] or leaders,key=lambda a:s[a]['decision_ms_total'])
    findings=['## Direct answers and practical recommendation','',f'Highest observed completion is{maximum}/72: '+', '.join(labels[a] for a in leaders)+f'. Among the completion leaders with the best available contact status, {labels[practical]} has the lowest measured primary decision cost. This is a descriptive practical default for this sample, not proof of universal optimality.','']
    for a in ('caa_full','raa_defer'):
        for b in ('periodic4','age4','age5'):
            ga=s[a]['goals']-s[b]['goals'];pd=s[a]['paid_total']-s[b]['paid_total'];cd=s[a]['decision_ms_total']-s[b]['decision_ms_total'];wd=s[a]['wall_s_total']-s[b]['wall_s_total']
            findings.append(f'{labels[a]} vs {labels[b]}: goals {ga:+d}, paid {pd:+d}, total decision cost {cd:+.3f}ms, episode wall {wd:+.3f}s. '+('It meets the point-estimate same-or-higher-success/fewer-scans criterion with zero contacts.' if s[a]['contacts_total']==0 and ga>=0 and pd<0 else 'It does not meet the joint point-estimate same-or-higher-success/fewer-scans criterion.')+' This does not constitute a noninferiority test.')
        findings.append(f'Development transfer for {labels[a]} vs Age5: FIT goal difference {old[a]["goals"]-old["age5"]["goals"]:+d}, paid difference {old[a]["paid_total"]-old["age5"]["paid_total"]:+d}; unseen goal difference {s[a]["goals"]-s["age5"]["goals"]:+d}, paid difference {s[a]["paid_total"]-s["age5"]["paid_total"]:+d}.')
    findings+=['','### Movement transfer (unpaired map-set means)','', '| Model | FIT / new mean H80 steps | FIT / new mean distance m | FIT / new success-only steps |','|---|---|---|---|']
    for a in ARMS:
        findings.append(f'|{labels[a]}|{old[a]["steps_mean"]:.3f} / {s[a]["steps_mean"]:.3f}|{old[a]["distance_m_mean"]:.3f} / {s[a]["distance_m_mean"]:.3f}|{old[a]["steps_success_only_mean"]:.3f} / {s[a]["steps_success_only_mean"]:.3f}|')
    findings+=['','The final conclusion is to retain the measured tradeoffs and end H2 without another model revision. rankings.csv documents relative-rank changes; success/paid evidence, common-success movement and actual CPU/wall costs must be considered together.','']
    where=lines.index('## Final H2 conclusion and future directions');lines[where:where]=findings
    text='\n'.join(lines)+'\n';p=ROOT/'docs/h2_final_research_report.md'
    with p.open('x') as f:f.write(text)
    (target/'research_report.md').write_text(text)
if __name__=='__main__':main()
