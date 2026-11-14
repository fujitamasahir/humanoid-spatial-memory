"""Post-outcome descriptive analysis only; never feeds an online decision."""
from __future__ import annotations
import gzip,json,sys
from collections import Counter
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from c_v21_common import ROOT,OUT,write,manifest,commit
from c_v21_fixtures import build
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from spatial_memory.multistep_reference import reference_cell,footprint

NEW=('ms_k','ms_k_visibility','ms_topology','ms_topology_visibility')
OLD=('periodic','age','C0','C-K','C-Topology3-d')


def load(n,arm):
    directory='fit72' if arm in NEW else 'reference_replays'
    return json.load(gzip.open(OUT/f'{directory}/episode_{n:03}_{arm}.json.gz','rt'))


def metric(e):
    r=e['row'];d=e['diagnostics'];dec=d.get('decisions',[])
    return {'success':float(bool(r['success'])),'contact_free_success':float(bool(r['success']) and int(r['g1_unwanted_contact_pairs'])==0),
        'contacts':int(r['g1_unwanted_contact_pairs']),'scans':int(r['observation_count']),
        'memory_rays':int(d.get('actual_memory_raycasts',61*r['observation_count'])),
        'emergency_scans':int(r['emergency_safety_scans']),'emergency_rays':int(r['emergency_safety_raycasts']),
        'combined_rays':61*int(r['observation_count'])+int(r['emergency_safety_raycasts']),
        'steps':int(r['elapsed_steps']),'distance':float(r['travel_distance_m']),
        'blocked':int(r['g1_footprint_blocked_attempts']),'interventions':int(r['emergency_safety_interventions']),
        'false_persistent':int(r['false_persistent_occupancy_updates']),'missed_changes':int(r['missed_persistent_changes']),
        'scheduler_ms':float(d.get('scheduler_total_ms',0)),
        'episode_seconds':float(r['episode_wall_time_seconds']),
        'astar_calls':sum(v.get('plan_calls',0) for v in dec),
        'visibility_computations':sum(v.get('visibility_computations',int(v.get('plan_calls',0)>0)) for v in dec),
        'future_visibility_computations':sum(v.get('future_visibility_computations',0) for v in dec),
        'estimated_value_mean':float(np.mean([v.get('value',0) for v in dec])) if dec else None,
        'estimated_delay_mean':float(np.mean([v.get('delay_regret',0) for v in dec])) if dec else None,
        'authorization_reasons':dict(Counter(v.get('reason','frozen_one_step_or_budget') for v in dec))}


def paired(episodes,candidate,reference):
    rows=[];clusters={}
    for n in range(1,73):
        a=metric(episodes[n,reference]);b=metric(episodes[n,candidate]);key=episodes[n,reference]['trace']['key']
        delta={k:b[k]-a[k] for k in ('success','scans','steps','combined_rays','scheduler_ms')}
        common=bool(a['success'] and b['success'])
        row={'identity':key[0],'schedule':key[1],'reference_success':a['success'],'candidate_success':b['success'],'common_success':common,'delta':delta,'common_step_delta':b['steps']-a['steps'] if common else None,'common_distance_delta':b['distance']-a['distance'] if common else None}
        rows.append(row);clusters.setdefault(key[0],[]).append(row)
    worlds=sorted(clusters);matrix=np.array([[np.mean([r['delta'][k] for r in clusters[w]]) for k in ('success','scans','steps','combined_rays','scheduler_ms')] for w in worlds])
    rng=np.random.default_rng(2026111402);draw=rng.integers(0,len(worlds),(2000,len(worlds)))
    estimates=matrix[draw].mean(axis=1)
    ci={k:np.percentile(estimates[:,j],[2.5,97.5]).tolist() for j,k in enumerate(('success','scans','steps','combined_rays','scheduler_ms'))}
    common=[r for r in rows if r['common_success']]
    common_sums=np.array([[sum(r['common_step_delta'] or 0 for r in clusters[w]),sum(r['common_distance_delta'] or 0 for r in clusters[w]),sum(r['common_success'] for r in clusters[w])] for w in worlds])
    summed=common_sums[draw].sum(axis=1);mask=summed[:,2]>0
    common_ci={name:(np.percentile(summed[mask,j]/summed[mask,2],[2.5,97.5]).tolist() if mask.any() else None) for j,name in enumerate(('steps','distance'))}
    return {'candidate':candidate,'reference':reference,'rescues':sum(not r['reference_success'] and r['candidate_success'] for r in rows),'harms':sum(r['reference_success'] and not r['candidate_success'] for r in rows),'common_successes':len(common),'common_mean_step_delta':float(np.mean([r['common_step_delta'] for r in common])) if common else None,'common_mean_distance_delta':float(np.mean([r['common_distance_delta'] for r in common])) if common else None,'maze_mean_deltas':matrix.mean(axis=0).tolist(),'maze_bootstrap_95_intervals':ci,'common_success_cluster_bootstrap_95_intervals':common_ci,'correlated_schedules_clustered':True,'maze_clusters':len(worlds),'paired_rows':rows}


def run():
    target=OUT/'analysis';target.mkdir(parents=True,exist_ok=False)
    result=json.loads((OUT/'synthetic/results.json').read_text());review=json.loads((OUT/'gate_review.json').read_text())
    fixtures={f['id']:f for f in build()};synthetic=[]
    for row in result['fixtures']:
        f=fixtures[row['id']];grid=np.array(f['grid'],dtype=np.int8);prob=np.array(f['probability'])
        eligible=[c for c in footprint(grid,f['start'],f['yaw'],f['sensor']) if c!=tuple(f['start']) and .05<float(prob[c[1],c[0]])<.95]
        for arm,r in row['results'].items():
            refs=[reference_cell(grid,c,float(prob[c[1],c[0]]),f['start'],f['goal'],f['yaw'],f['unknown'],f['sensor'],r['cost'],('visibility' in arm or arm not in NEW)) for c in eligible]
            oracle=any(v['scan'] for v in refs);scan=r['net_value']>0
            synthetic.append({'fixture':f['id'],'family':f['family'],'arm':arm,'scan':scan,'oracle_scan':oracle,'false_positive':scan and not oracle,'false_negative':not scan and oracle,'V':r['value'],'delay':r['delay_regret'],'net':r['net_value'],'plan_calls':r['plan_calls'],'visibility_computations':r.get('visibility_computations',1),'peak_traced_bytes':r['peak_traced_bytes']})
    aggregate={a:{'scans':sum(r['scan'] for r in synthetic if r['arm']==a),'oracle_false_positive':sum(r['false_positive'] for r in synthetic if r['arm']==a),'oracle_false_negative':sum(r['false_negative'] for r in synthetic if r['arm']==a),'max_traced_bytes':max(r['peak_traced_bytes'] for r in synthetic if r['arm']==a),'median_scheduler_ms':float(np.median([v/1e6 for t in result['timings'] if t['arm']==a for v in t['samples_ns']])),'p95_scheduler_ms':float(np.percentile([v/1e6 for t in result['timings'] if t['arm']==a for v in t['samples_ns']],95))} for a in result['fixtures'][0]['results']}
    write(target/'synthetic_analysis.json',{'rows':synthetic,'aggregate':aggregate,'oracle_scope':'Declared finite point-route catalog, not calibrated navigation utility; frozen arms compared to visibility-aware multi-step reference at their own prices'})
    names=list(aggregate);fig,axes=plt.subplots(1,2,figsize=(13,4))
    axes[0].bar(range(len(names)),[aggregate[a]['oracle_false_negative'] for a in names]);axes[0].set_title('Synthetic missed scan authorizations');axes[0].set_ylabel('96 public-memory conditions')
    axes[1].bar(range(len(names)),[aggregate[a]['median_scheduler_ms'] for a in names]);axes[1].set_title('Same-machine median scheduler time');axes[1].set_ylabel('ms (untraced timing calls)')
    for ax in axes:ax.set_xticks(range(len(names)),names,rotation=55,ha='right')
    fig.tight_layout();fig.savefig(target/'synthetic_mechanism.png',dpi=170);plt.close(fig)
    f=fixtures['last_chance_00'];r=next(v for v in result['fixtures'] if v['id']==f['id'])['results']['ms_k_visibility'];candidate=next(v for v in r['candidate_evaluations'] if tuple(v['cell'])==tuple(f['target']))
    fig,ax=plt.subplots(figsize=(7,6));ax.imshow(f['grid'],cmap='Greys',vmin=0,vmax=1,origin='lower')
    for path,label in zip(candidate['routes'],('free hypothesis','occupied hypothesis')):
        if path:ax.plot(*zip(*path),'--o',ms=3,label=label)
    ax.scatter(*f['start'],c='green',s=90,label='current pose');ax.scatter(*f['target'],c='purple',marker='*',s=150,label='uncertain target')
    ax.set_title('Predicted routes: shared prefix, lost future FOV\nPublic synthetic fixture; no actual future observations');ax.legend(fontsize=8);fig.tight_layout();fig.savefig(target/'future_opportunity_public_predictions.png',dpi=170);plt.close(fig)
    nav=None
    if (OUT/'fit72/summary.json').is_file():
        episodes={(n,a):load(n,a) for n in range(1,73) for a in (*OLD,*NEW)}
        summaries={a:{k:(sum(metric(episodes[n,a])[k] for n in range(1,73)) if k not in ('scheduler_ms','episode_seconds') else np.mean([metric(episodes[n,a])[k] for n in range(1,73)]).item()) for k in ('success','contact_free_success','contacts','scans','memory_rays','emergency_scans','emergency_rays','combined_rays','steps','distance','blocked','interventions','false_persistent','missed_changes','scheduler_ms','episode_seconds','astar_calls','visibility_computations','future_visibility_computations')} for a in (*OLD,*NEW)}
        contrasts=[(a,b) for a in NEW for b in ('periodic','age','C0','C-Topology3-d' if 'topology' in a else 'C-K')]+[('ms_k_visibility','ms_k'),('ms_topology_visibility','ms_topology')]
        pairs=[paired(episodes,a,b) for a,b in contrasts]
        joint={}
        for a in NEW:
            b='C-Topology3-d' if 'topology' in a else 'C-K';p=next(v for v in pairs if v['candidate']==a and v['reference']==b)
            joint[a]=bool(summaries[a]['success']>=summaries[b]['success'] and summaries[a]['contact_free_success']>=summaries[b]['contact_free_success'] and summaries[a]['contacts']<=summaries[b]['contacts'] and summaries[a]['scans']<summaries[b]['scans'] and p['common_mean_step_delta'] is not None and p['common_mean_step_delta']<0 and p['common_mean_distance_delta']<0)
        nav={'status':'DESCRIPTIVE_FIT_ONLY','summary':summaries,'contrasts':pairs,'joint_navigation_benefit_vs_matched_selector':joint,'bootstrap':'2000 resamples of36 whole maze clusters; seed2026111402; not independent validation'}
        write(target/'navigation_analysis.json',nav)
        fig,axes=plt.subplots(2,2,figsize=(14,9))
        for ax,(metric_name,title,divisor) in zip(axes.flat,[('success','Goals /72',1),('scans','Mean paid scans',72),('steps','Mean H80-censored steps',72),('combined_rays','Mean combined memory+safety rays',72)]):
            ax.bar(range(9),[summaries[a][metric_name]/divisor for a in (*OLD,*NEW)])
            ax.set_title(title);ax.set_xticks(range(9),(*OLD,*NEW),rotation=55,ha='right')
        fig.tight_layout();fig.savefig(target/'navigation_outcomes.png',dpi=170);plt.close(fig)
        choices=[n for n in range(1,73) if metric(episodes[n,'ms_k_visibility'])['steps']!=metric(episodes[n,'C-K'])['steps']]
        n=min(choices) if choices else 1
        fig,ax=plt.subplots(figsize=(8,6))
        for a in ('C-K','ms_k','ms_k_visibility'):
            frames=episodes[n,a]['trace']['steps'];positions=[v['position'] for v in frames]
            ax.plot(*zip(*positions),'-o',ms=3,label=a)
            scans=[v['position'] for v in frames if v['observation_granted']]
            if scans:ax.scatter(*zip(*scans),marker='x',s=50)
        key=episodes[n,'C-K']['trace']['key'];ax.set_title(f'Actual G1 paths: {key[0].split(":")[-2:]} schedule{key[1]}\nFirst sorted key with different steps; x=paid scans');ax.set_aspect('equal');ax.legend();fig.tight_layout();fig.savefig(target/'representative_actual_trajectory.png',dpi=170);plt.close(fig)
    write(target/'completion.json',{'source_commit':commit(),'numeric_gate':result['numeric_gate']['status'],'conformance_gate':review['status'],'navigation_executed':nav is not None,'independent_cohort_generated_or_accessed':False})
    manifest(target)
    print(json.dumps({'synthetic':aggregate,'navigation':nav['summary'] if nav else None,'joint_benefit':nav['joint_navigation_benefit_vs_matched_selector'] if nav else None},indent=2))
if __name__=='__main__':run()
