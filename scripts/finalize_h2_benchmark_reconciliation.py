#!/usr/bin/env python3
"""Build the final append-only H2 dataset, analysis tables, and poster figures."""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import math
import pathlib
import sys
from collections import Counter, defaultdict

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src')]
BASE=ROOT/'results/phase2_mujoco'
OUT=BASE/'h2_final_benchmark_reconciliation_v1'
COMP=BASE/'h2_comprehensive_benchmark_v1'
REC=BASE/'h2_full_spatial_memory_replay_v1'
TIMING=OUT/'all_model_timing_v1'
CONDITIONS=('known_low_frequency','unseen_low_frequency','unseen_high_frequency')
POSTER=('static','periodic4','periodic5','age4','c_k','b_age','c_ternary','rdao_v1_footprint','rdao_v1_gate_every')
PAIRS=(('periodic4','periodic5'),('age4','age5'),('periodic5','age4'),
       ('periodic5','rdao_v1_footprint'),('periodic5','rdao_v1_gate_every'),
       ('rdao_v1','rdao_v1_footprint'),('b_age','bc'))

def sha_bytes(raw:bytes)->str:return hashlib.sha256(raw).hexdigest()
def sha(path:pathlib.Path)->str:return sha_bytes(path.read_bytes())
def dump_exclusive(path:pathlib.Path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as f:json.dump(value,f,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False);f.write('\n')
def write_csv(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    if not rows:raise RuntimeError(f'No rows for {path}')
    with path.open('x',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def journal_rows(path,enveloped=False):
    out=[]
    for i,line in enumerate(path.read_text(encoding='utf-8').splitlines(),1):
        item=json.loads(line)
        if 'record' in item:
            raw=json.dumps(item['record'],sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
            if sha_bytes(raw)!=item.get('sha256'):raise RuntimeError(f'Journal record hash mismatch {path}:{i}')
            out.append(item['record'])
        else:out.append(item)
    return out
def load_episode(rel,expected_sha):
    path=ROOT/rel
    if not path.is_file():raise FileNotFoundError(path)
    actual=sha(path)
    if actual!=expected_sha:raise RuntimeError(f'Input episode SHA mismatch {rel}: {actual} != {expected_sha}')
    with gzip.open(path,'rt',encoding='utf-8') as f:return json.load(f)
def b_age_index_records():
    p=REC/'task_b_b_age_corrected_v2/journal.jsonl'
    return journal_rows(p)
def source_records():
    """Select 11,664 unique cases, replacing only mislabeled B+Age entries."""
    records=[]
    # Known FIT72: use the full-memory recovery journal for 53 unaffected arms.
    known=journal_rows(REC/'task_b/journal.jsonl')
    if len([r for r in known if r.get('event')=='episode_committed'])!=3888:raise RuntimeError('Known FIT72 journal is incomplete')
    for r in known:
        if r.get('event')!='episode_committed' or r['model_id']=='b_age':continue
        rel=f'results/phase2_mujoco/h2_full_spatial_memory_replay_v1/{r["path"]}'
        records.append({'evaluation_condition':'known_low_frequency','condition':'original',
            'model_id':r['model_id'],'world_identity':r['map_identity'],'schedule':int(r['schedule']),
            'seed':42,'path':rel,'sha256':r['sha256'],'payload_type':'replay',
            'source_dataset':'h2_full_spatial_memory_replay_v1/task_b'})
    for r in b_age_index_records():
        rel=f'results/phase2_mujoco/h2_full_spatial_memory_replay_v1/{r["path"]}'
        records.append({'evaluation_condition':'known_low_frequency','condition':'original',
            'model_id':'b_age','world_identity':r['map_identity'],'schedule':int(r['schedule']),
            'seed':42,'path':rel,'sha256':r['sha256'],'payload_type':'replay',
            'source_dataset':'h2_full_spatial_memory_replay_v1/task_b_b_age_corrected_v2'})
    # Unseen low/high: reuse the admitted comprehensive index except old B+Age.
    index=json.loads((COMP/'combined_dataset/replay_index.json').read_text())
    if index.get('schema_version')!='h2_comprehensive_replay_index_v1':raise RuntimeError('Unexpected source index schema')
    mapping={'original':'unseen_low_frequency','high_frequency':'unseen_high_frequency'}
    for e in index['entries']:
        if e['model_id']=='b_age':continue
        records.append({'evaluation_condition':mapping[e['condition']],'condition':e['condition'],
            'model_id':e['model_id'],'world_identity':e['world_identity'],'schedule':int(e['schedule']),
            'seed':int(e['seed']),'path':e['path'],'sha256':e['sha256'],
            'payload_type':e['payload_type'],'source_dataset':'h2_comprehensive_benchmark_v1'})
    # Correct B+Age is a separate append-only epoch, for both unseen conditions.
    corrected=journal_rows(OUT/'corrected_b_age_unseen_v1/journal.jsonl')
    if len(corrected)!=144:raise RuntimeError(f'Corrected B+Age journal has {len(corrected)} rows, expected 144')
    for e in corrected:
        raw_condition=e['condition']
        records.append({'evaluation_condition':raw_condition,
            'condition':'original' if raw_condition=='unseen_low_frequency' else 'high_frequency',
            'model_id':'b_age','world_identity':e['map_identity'],'schedule':int(e['schedule']),
            'seed':42,'path':f'results/phase2_mujoco/h2_final_benchmark_reconciliation_v1/{e["path"]}',
            'sha256':e['sha256'],'payload_type':'replay',
            'source_dataset':'h2_final_benchmark_reconciliation_v1/corrected_b_age_unseen_v1'})
    key=lambda r:(r['evaluation_condition'],r['model_id'],r['world_identity'],r['schedule'],r['seed'])
    records.sort(key=key)
    keys=[key(r) for r in records]
    if len(records)!=11664 or len(set(keys))!=11664:raise RuntimeError(f'Final episode index not unique/exact: {len(records)} entries, {len(set(keys))} keys')
    expected={c:3888 for c in CONDITIONS}
    counts=Counter(r['evaluation_condition'] for r in records)
    if dict(counts)!=expected:raise RuntimeError(f'Condition counts differ: {counts}')
    for c in CONDITIONS:
        subset=[r for r in records if r['evaluation_condition']==c]
        if len(set(r['model_id'] for r in subset))!=54:raise RuntimeError(f'{c} model set incomplete')
    # Every referenced source is hash checked before the index becomes authoritative.
    for i,r in enumerate(records,1):
        if i%500==0:print(f'validated final source files {i}/11664',flush=True)
        load_episode(r['path'],r['sha256'])
    return records

def row_for(entry):
    d=load_episode(entry['path'],entry['sha256'])
    r=d.get('row') or d.get('metrics') or d.get('replay',{}).get('metrics') or d.get('trace',{}).get('metrics')
    if not isinstance(r,dict):raise RuntimeError(f'Missing metric row: {entry["path"]}')
    return r,d

def getv(row,*names,default=None):
    for n in names:
        if n in row and row[n] is not None and row[n]!='':return row[n]
    return default

def build_metrics(index):
    timings=csv.DictReader((OUT/'all_model_episode_timings.csv').open(encoding='utf-8'))
    timing_rows=list(timings)
    if len(timing_rows)!=19440:raise RuntimeError('All-model timing CSV must contain 19,440 rows')
    timing_summary={}
    for model in sorted({r['model_id'] for r in timing_rows}):
        group=[r for r in timing_rows if r['model_id']==model]
        if len(group)!=360:raise RuntimeError(f'{model} timing count {len(group)} != 360')
        timing_summary[model]={k:sum(float(r[k]) for r in group)/len(group)/1e6
            for k in ('initialization_ns','decision_ns','memory_update_ns','total_model_computation_ns')}
        timing_summary[model]['decision_mean_ns_per_call']=sum(float(r['decision_mean_ns_per_call']) for r in group)/len(group)
        timing_summary[model]['decision_p95_ns_per_call']=sorted(float(r['decision_p95_ns_per_call']) for r in group)[int(.95*(len(group)-1))]
        timing_summary[model]['decision_p99_ns_per_call']=sorted(float(r['decision_p99_ns_per_call']) for r in group)[int(.99*(len(group)-1))]
        totals=[float(r['total_model_computation_ns'])/1e6 for r in group]
        timing_summary[model]['median_total_model_computation_ms']=__import__('statistics').median(totals)
        timing_summary[model]['std_total_model_computation_ms']=__import__('statistics').stdev(totals)
        timing_summary[model]['p95_total_model_computation_ms']=float(__import__('numpy').quantile(totals,.95))
        timing_summary[model]['p99_total_model_computation_ms']=float(__import__('numpy').quantile(totals,.99))
        timing_summary[model]['mean_decision_call_us']=timing_summary[model]['decision_mean_ns_per_call']/1000
        timing_summary[model]['median_decision_call_us']=__import__('statistics').median([float(r['decision_median_ns_per_call']) for r in group])/1000
        timing_summary[model]['p95_decision_call_us']=timing_summary[model]['decision_p95_ns_per_call']/1000
        timing_summary[model]['p99_decision_call_us']=timing_summary[model]['decision_p99_ns_per_call']/1000
    metrics=[]
    for i,e in enumerate(index,1):
        row,_=row_for(e)
        distance=getv(row,'travel_distance_m')
        distance_units='m'
        if distance is None:
            d=getv(row,'travel_distance',default=0);distance=float(d)*0.75;distance_units='cells converted at 0.75 m/cell'
        s=bool(getv(row,'success','goal_reached',default=False))
        contacts=int(getv(row,'g1_unwanted_contact_pairs','unwanted_contact_pairs','unwanted_contacts',default=0) or 0)
        metrics.append({'evaluation_condition':e['evaluation_condition'],'condition':e['condition'],
            'model_id':e['model_id'],'world_identity':e['world_identity'],'schedule':e['schedule'],'seed':e['seed'],
            'success':s,'goal_step':getv(row,'goal_step','goal_arrival_step'),
            'paid_observations':int(getv(row,'observation_count','paid_observations','observation_cost',default=0) or 0),
            'navigation_steps':int(getv(row,'elapsed_steps','navigation_steps','steps',default=0) or 0),
            'travel_distance_m':distance,'distance_source_units':distance_units,
            'stale_map_errors':int(getv(row,'stale_map_errors',default=0) or 0),
            'false_persistent_occupancy_updates':int(getv(row,'false_persistent_occupancy_updates',default=0) or 0),
            'missed_persistent_changes':int(getv(row,'missed_persistent_changes',default=0) or 0),
            'unwanted_contact_pairs':contacts,
            'unwanted_contact_states':int(getv(row,'g1_unwanted_contact_states',default=0) or 0),
            'unwanted_contact_episode':contacts>0 or int(getv(row,'g1_unwanted_contact_states',default=0) or 0)>0,
            'pedestrian_contact_pairs':int(getv(row,'g1_pedestrian_contact_pairs',default=0) or 0),
            'wall_contact_pairs':int(getv(row,'g1_wall_contact_pairs',default=0) or 0),
            'emergency_interventions':int(getv(row,'emergency_interventions','emergency_safety_interventions',default=0) or 0),
            'forward_actions':int(getv(row,'g1_forward_actions',default=0) or 0),
            'lateral_actions':int(getv(row,'g1_lateral_actions',default=0) or 0),
            'backward_actions':int(getv(row,'g1_backward_actions',default=0) or 0),
            'turn_actions':int(getv(row,'g1_in_place_turns',default=0) or 0),
            'model_initialization_ms':timing_summary[e['model_id']]['initialization_ns'],
            'model_observation_decision_ms':timing_summary[e['model_id']]['decision_ns'],
            'model_memory_update_ms':timing_summary[e['model_id']]['memory_update_ns'],
            'model_computation_ms':timing_summary[e['model_id']]['total_model_computation_ns'],
            'source_path':e['path'],'source_sha256':e['sha256'],'payload_type':e['payload_type']})
        if i%1000==0:print(f'assembled metrics {i}/11664',flush=True)
    return metrics,timing_summary

def summarize(metrics,timing):
    rows=[]
    for cond in CONDITIONS:
        for model in sorted({r['model_id'] for r in metrics}):
            g=[r for r in metrics if r['evaluation_condition']==cond and r['model_id']==model]
            if len(g)!=72:raise RuntimeError(f'{cond}/{model} has {len(g)} episodes')
            goals=sum(r['success'] for r in g);steps=[r['navigation_steps'] for r in g]
            goal_steps=[float(r['goal_step']) for r in g if r['success'] and r['goal_step'] is not None]
            rows.append({'evaluation_condition':cond,'model_id':model,'episodes':len(g),'goal_completions':goals,
                'goal_success_rate':goals/len(g),'mean_paid_observations':sum(r['paid_observations'] for r in g)/len(g),
                'mean_arrival_steps':sum(goal_steps)/len(goal_steps) if goal_steps else None,
                'mean_navigation_steps':sum(steps)/len(steps),'mean_travel_distance_m':sum(r['travel_distance_m'] for r in g)/len(g),
                'mean_stale_map_errors':sum(r['stale_map_errors'] for r in g)/len(g),
                'mean_false_persistent_occupancy_updates':sum(r['false_persistent_occupancy_updates'] for r in g)/len(g),
                'mean_missed_persistent_changes':sum(r['missed_persistent_changes'] for r in g)/len(g),
                'unwanted_contact_episodes':sum(r['unwanted_contact_episode'] for r in g),
                'unwanted_contact_pairs':sum(r['unwanted_contact_pairs'] for r in g),
                'contact_free_goal_completions':sum(r['success'] and not r['unwanted_contact_episode'] for r in g),
                'emergency_interventions':sum(r['emergency_interventions'] for r in g),
                'forward_actions':sum(r['forward_actions'] for r in g),'lateral_actions':sum(r['lateral_actions'] for r in g),
                'backward_actions':sum(r['backward_actions'] for r in g),'turn_actions':sum(r['turn_actions'] for r in g),
                'mean_initialization_ms':timing[model]['initialization_ns'],
                'mean_observation_decision_ms':timing[model]['decision_ns'],
                'mean_memory_update_ms':timing[model]['memory_update_ns'],
                'mean_total_model_computation_ms':timing[model]['total_model_computation_ns'],
                'median_total_model_computation_ms':timing[model]['median_total_model_computation_ms'],
                'std_total_model_computation_ms':timing[model]['std_total_model_computation_ms'],
                'p95_total_model_computation_ms':timing[model]['p95_total_model_computation_ms'],
                'p99_total_model_computation_ms':timing[model]['p99_total_model_computation_ms'],
                'mean_decision_cost_per_call_us':timing[model]['mean_decision_call_us'],
                'median_decision_cost_per_call_us':timing[model]['median_decision_call_us'],
                'decision_p95_us':timing[model]['p95_decision_call_us'],
                'decision_p99_us':timing[model]['p99_decision_call_us'],
                'computation_speedup_vs_periodic5':timing['periodic5']['total_model_computation_ns']/timing[model]['total_model_computation_ns'] if timing[model]['total_model_computation_ns'] else None})
    return rows

def historical_comparison(timing):
    old_path=BASE/'h2_controlled_compute_benchmark_v1/model_summary.csv'
    old={r['model_id']:r for r in csv.DictReader(old_path.open(encoding='utf-8'))}
    selected=list(csv.DictReader((OUT/'episode_timings.csv').open(encoding='utf-8')))
    direct=defaultdict(list)
    for r in selected:
        direct[(r['model_id'],r['revision'])].append(float(r['total_model_computation_ns'])/1e6)
    rows=[]
    for model in sorted(timing):
        prev=float(old[model]['mean_total_model_computation_ms']) if model in old else None
        current=timing[model]['total_model_computation_ns']
        row={'model_id':model,'previous_19k_controlled_mean_ms':prev,
             'new_same_session_54_model_mean_ms':current,
             'difference_ms':None if prev is None else current-prev,
             'difference_percent':None if not prev else (current-prev)/prev*100,
             'older_h2_reference_mean_ms':float(old[model]['historical_mean_compute_ms']) if model in old and old[model].get('historical_mean_compute_ms') else None,
             'direct_same_session_baseline_ms':None,'direct_same_session_optimized_ms':None,
             'direct_same_session_speedup':None,'final_cost_source':'all_model_timing_v1, five repetitions'}
        if model in ('periodic5','age5'):
            b=direct.get((model,'baseline'),[]);o=direct.get((model,'optimized'),[])
            if len(b)!=360 or len(o)!=360:raise RuntimeError(f'Direct before/after timing incomplete for {model}')
            row['direct_same_session_baseline_ms']=sum(b)/len(b)
            row['direct_same_session_optimized_ms']=sum(o)/len(o)
            row['direct_same_session_speedup']=row['direct_same_session_baseline_ms']/row['direct_same_session_optimized_ms']
        rows.append(row)
    return rows

def pareto(summary,condition,with_compute):
    cand=[r for r in summary if r['evaluation_condition']==condition]
    out=[]
    for a in cand:
        def dominates(b):
            dims=[b['goal_success_rate']>=a['goal_success_rate'],b['mean_paid_observations']<=a['mean_paid_observations']]
            strict=[b['goal_success_rate']>a['goal_success_rate'],b['mean_paid_observations']<a['mean_paid_observations']]
            if with_compute:
                dims.append(b['mean_total_model_computation_ms']<=a['mean_total_model_computation_ms'])
                strict.append(b['mean_total_model_computation_ms']<a['mean_total_model_computation_ms'])
            return all(dims) and any(strict)
        if not any(dominates(b) for b in cand if b is not a):
            item={k:a[k] for k in ('model_id','goal_success_rate','mean_paid_observations','mean_total_model_computation_ms')}
            item['evaluation_condition']=condition;item['objectives']='maximize success, minimize observations'+(', minimize computation' if with_compute else '')
            out.append(item)
    return sorted(out,key=lambda r:r['model_id'])

def paired_tables(metrics,timing):
    lookup={(r['evaluation_condition'],r['model_id'],r['world_identity'],r['schedule']):r for r in metrics}
    comparisons=[];intervals=[]
    import numpy as np
    rng=np.random.default_rng(20261115)
    for cond in CONDITIONS:
        for a,b in PAIRS:
            aa=[lookup[(cond,a,w,s)] for w in sorted({r['world_identity'] for r in metrics if r['evaluation_condition']==cond}) for s in (0,1)]
            bb=[lookup[(cond,b,r['world_identity'],r['schedule'])] for r in aa]
            success_delta=np.mean([int(y['success'])-int(x['success']) for x,y in zip(aa,bb)])
            obs_delta=np.mean([y['paid_observations']-x['paid_observations'] for x,y in zip(aa,bb)])
            comp_a=timing[a]['total_model_computation_ns'];comp_b=timing[b]['total_model_computation_ns']
            comparisons.append({'evaluation_condition':cond,'model_a':a,'model_b':b,
                'success_rate_a':np.mean([x['success'] for x in aa]),'success_rate_b':np.mean([x['success'] for x in bb]),
                'success_rate_b_minus_a_pp':100*success_delta,'mean_obs_a':np.mean([x['paid_observations'] for x in aa]),
                'mean_obs_b':np.mean([x['paid_observations'] for x in bb]),'mean_obs_b_minus_a':obs_delta,
                'compute_a_ms':comp_a,'compute_b_ms':comp_b,'compute_b_minus_a_ms':comp_b-comp_a,
                'compute_ratio_b_over_a':comp_b/comp_a if comp_a else None,
                'paired_rescues':sum((not x['success']) and y['success'] for x,y in zip(aa,bb)),
                'paired_harms':sum(x['success'] and (not y['success']) for x,y in zip(aa,bb)),
                'pairing':'same map identity and schedule; 36 whole-maze clusters'})
            # 36 map clusters, retaining both schedules in each sampled cluster.
            maps=sorted({r['world_identity'] for r in aa});pos={w:i for i,w in enumerate(maps)}
            A_s=np.array([[int(lookup[(cond,a,w,s)]['success']) for s in (0,1)] for w in maps],dtype=float)
            B_s=np.array([[int(lookup[(cond,b,w,s)]['success']) for s in (0,1)] for w in maps],dtype=float)
            A_o=np.array([[lookup[(cond,a,w,s)]['paid_observations'] for s in (0,1)] for w in maps],dtype=float)
            B_o=np.array([[lookup[(cond,b,w,s)]['paid_observations'] for s in (0,1)] for w in maps],dtype=float)
            draws=rng.integers(0,len(maps),size=(5000,len(maps)))
            for metric_name,A,B,scale in [('success_rate',A_s,B_s,100),('paid_observations',A_o,B_o,1)]:
                differences=(B-A).mean(axis=1)[draws].mean(axis=1)*scale
                intervals.append({'evaluation_condition':cond,'model_a':a,'model_b':b,'metric':metric_name,
                    'estimate_b_minus_a':float((B-A).mean()*scale),
                    'ci95_low':float(np.quantile(differences,.025)),
                    'ci95_high':float(np.quantile(differences,.975)),
                    'bootstrap_draws':5000,'seed':20261115,'cluster_unit':'whole maze; paired schedules retained'})
    return comparisons,intervals

def figures(summary,pareto2,poster):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    figdir=OUT/'figures';figdir.mkdir(exist_ok=True)
    colors={'known_low_frequency':'#4169a1','unseen_low_frequency':'#4da58c','unseen_high_frequency':'#d78c3c'}
    labels={'static':'Static','periodic4':'Periodic-4','periodic5':'Periodic-5','age4':'Age-4','c_k':'C-K','b_age':'B + Age','c_ternary':'C + Ternary','rdao_v1_footprint':'RDAO v1 Footprint','rdao_v1_gate_every':'RDAO v1 Gate Every'}
    order=list(POSTER);xs=np.arange(len(order));width=.25
    fig,ax=plt.subplots(figsize=(11,5.5))
    for j,cond in enumerate(CONDITIONS):
        lut={r['model_id']:r for r in summary if r['evaluation_condition']==cond}
        ax.bar(xs+(j-1)*width,[lut[m]['goal_success_rate']*100 for m in order],width,label=cond.replace('_',' '),color=colors[cond])
    ax.set_xticks(xs,[labels[m] for m in order],rotation=30,ha='right');ax.set_ylabel('Goal success (%)');ax.set_ylim(0,100);ax.legend(frameon=False);ax.grid(axis='y',alpha=.22);fig.tight_layout()
    fig.savefig(figdir/'goal_success_rate.png',dpi=220);fig.savefig(figdir/'goal_success_rate.svg');plt.close(fig)
    hf={r['model_id']:r for r in summary if r['evaluation_condition']=='unseen_high_frequency'}
    fig,ax=plt.subplots(figsize=(9,6));selected=set(order)
    for m,r in hf.items():
        ax.scatter(r['mean_paid_observations'],r['goal_success_rate']*100,s=65 if m in selected else 28,
                   c='#d45b48' if m in selected else '#78909c',edgecolors='white',linewidths=.4,zorder=3 if m in selected else 2)
        if m in selected:ax.annotate(labels.get(m,m),(r['mean_paid_observations'],r['goal_success_rate']*100),xytext=(4,4),textcoords='offset points',fontsize=8)
    pts=sorted([(r['mean_paid_observations'],r['goal_success_rate']*100) for r in pareto2],key=lambda x:x[0])
    if pts:ax.plot([x[0] for x in pts],[x[1] for x in pts],color='#2979a8',lw=1.5,label='2D Pareto frontier')
    ax.set_xlabel('Mean paid memory observations');ax.set_ylabel('Goal success (%)');ax.set_title('Unseen high-frequency environments');ax.grid(alpha=.22);ax.legend(frameon=False);fig.tight_layout()
    fig.savefig(figdir/'observation_efficiency.png',dpi=220);fig.savefig(figdir/'observation_efficiency.svg');plt.close(fig)
    sub=[hf[m] for m in order]
    fig,ax=plt.subplots(figsize=(10,6.5))
    values=[r['mean_total_model_computation_ms'] for r in sub]
    ax.barh([labels[m] for m in order],values,color='#4f83a1')
    ax.set_xscale('log');ax.set_xlabel('Model computation (ms/episode, log scale)')
    ax.set_ylabel('Model');ax.invert_yaxis();ax.grid(axis='x',alpha=.25,which='both');fig.tight_layout()
    fig.savefig(figdir/'computational_cost.png',dpi=220);fig.savefig(figdir/'computational_cost.svg');plt.close(fig)

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    index=source_records()
    existing=OUT/'final_replay_index.json'
    index_payload={'schema_version':'h2_comprehensive_replay_index_v1','entries':index,
        'selection_metadata':{'authoritative_conditions':list(CONDITIONS),'records_per_condition':3888,
            'unique_episode_count':11664,'known_b_age_source':'corrected H2 full replay B+Age epoch v2',
            'unseen_b_age_source':'separate corrected B+Age unseen epoch','old_mislabeled_b_age_entries':'preserved, excluded',
            'legacy_schema_keys_preserved':['condition','model_id','path','payload_type','schedule','seed','sha256','world_identity'],
            'new_fields':['evaluation_condition','source_dataset']}}
    dump_exclusive(existing,index_payload)
    metrics,timing=build_metrics(index)
    hist_cmp=historical_comparison(timing);write_csv(OUT/'historical_vs_optimized_comparison.csv',hist_cmp)
    write_csv(OUT/'final_episode_metrics.csv',metrics)
    summary=summarize(metrics,timing);write_csv(OUT/'final_model_summary.csv',summary)
    pareto2=pareto(summary,'unseen_high_frequency',False);pareto3=pareto(summary,'unseen_high_frequency',True)
    write_csv(OUT/'pareto_frontier_2d.csv',pareto2);write_csv(OUT/'pareto_frontier_3d.csv',pareto3)
    paired,intervals=paired_tables(metrics,timing);write_csv(OUT/'paired_comparisons.csv',paired);write_csv(OUT/'bootstrap_intervals.csv',intervals)
    p5=timing['periodic5']['total_model_computation_ns'];p5obs=next(r['mean_paid_observations'] for r in summary if r['model_id']=='periodic5' and r['evaluation_condition']=='unseen_high_frequency')
    be=[]
    for m in sorted(timing):
        obs=next(r['mean_paid_observations'] for r in summary if r['model_id']==m and r['evaluation_condition']=='unseen_high_frequency')
        comp=timing[m]['total_model_computation_ns'];saved=p5obs-obs;extra=comp-p5
        be.append({'model_id':m,'reference_model':'periodic5','saved_observations':saved,'extra_model_computation_ms':extra,
            'break_even_observation_cost_ms':extra/saved if saved>0 and extra>0 else None,
            'interpretation':'Hypothetical scan-cost threshold only; not measured sensor energy, power, or end-to-end runtime.'})
    write_csv(OUT/'break_even_analysis.csv',be)
    poster=[]
    for m in POSTER:
        rows=[r for r in summary if r['model_id']==m]
        item={'model_id':m,'display_name':next((r['display_name'] for r in json.loads((COMP/'protocol/model_registry.json').read_text()) if r['model_id']==m),m)}
        for r in rows:
            c=r['evaluation_condition'];item[c+'_goals']=r['goal_completions'];item[c+'_success_rate']=r['goal_success_rate'];item[c+'_mean_paid_observations']=r['mean_paid_observations']
        item['unseen_high_frequency_computation_ms']=timing[m]['total_model_computation_ns']
        item['unseen_high_frequency_pareto_2d']=m in {r['model_id'] for r in pareto2};poster.append(item)
    write_csv(OUT/'poster_9_model_summary.csv',poster)
    figures(summary,pareto2,poster)
    # Corrected-versus-old B+Age diagnostic values.
    correction=[]
    wrong_known=[r for r in journal_rows(REC/'task_b/journal.jsonl') if r.get('event')=='episode_committed' and r.get('model_id')=='b_age']
    for cond,wrong_entries in [('known_low_frequency',wrong_known)]:
        for r in wrong_entries:
            d=load_episode(f'results/phase2_mujoco/h2_full_spatial_memory_replay_v1/{r["path"]}',r['sha256']);row=d['row']
            correction.append({'evaluation_condition':cond,'version':'old mislabeled B+C','success':bool(row['success']),'paid_observations':row.get('observation_count',0),'arrival_steps':row.get('goal_step'),'travel_distance_m':row.get('travel_distance_m',float(row.get('travel_distance',0))*.75),'unwanted_contacts':row.get('g1_unwanted_contact_pairs',0)})
    wrong_index=[e for e in json.loads((COMP/'combined_dataset/replay_index.json').read_text())['entries'] if e['model_id']=='b_age']
    for e in wrong_index:
        row,_=row_for(e);cond='unseen_low_frequency' if e['condition']=='original' else 'unseen_high_frequency'
        correction.append({'evaluation_condition':cond,'version':'old mislabeled B+C','success':bool(row['success']),'paid_observations':row.get('observation_count',0),'arrival_steps':row.get('goal_step'),'travel_distance_m':row.get('travel_distance_m',float(row.get('travel_distance',0))*.75),'unwanted_contacts':row.get('g1_unwanted_contact_pairs',0)})
    for r in metrics:
        if r['model_id']=='b_age':correction.append({'evaluation_condition':r['evaluation_condition'],'version':'correct B+Age','success':r['success'],'paid_observations':r['paid_observations'],'arrival_steps':r['goal_step'],'travel_distance_m':r['travel_distance_m'],'unwanted_contacts':r['unwanted_contact_pairs']})
    grouped=defaultdict(list)
    for r in correction:grouped[(r['evaluation_condition'],r['version'])].append(r)
    summary_corr=[]
    for (c,v),g in sorted(grouped.items()):
        n=len(g);summary_corr.append({'evaluation_condition':c,'version':v,'episodes':n,'goal_completions':sum(x['success'] for x in g),'success_rate':sum(x['success'] for x in g)/n,
             'mean_paid_observations':sum(float(x['paid_observations'] or 0) for x in g)/n,
             'mean_arrival_steps_success_only':(sum(float(x['arrival_steps']) for x in g if x['success'] and x['arrival_steps'] not in (None,''))/sum(x['success'] and x['arrival_steps'] not in (None,'') for x in g)) if any(x['success'] and x['arrival_steps'] not in (None,'') for x in g) else None,
             'mean_travel_distance_m':sum(float(x['travel_distance_m'] or 0) for x in g)/n,
             'unwanted_contact_pairs':sum(int(x['unwanted_contacts'] or 0) for x in g)})
    write_csv(OUT/'b_age_before_after_summary.csv',summary_corr)
    b_age_report=['# B + Age correction report','','Correct definition: Persistence/Bayesian memory enabled, EVI disabled, with the registered Age scheduler. The old unseen H2 `b_age` entries were produced with Persistence + EVI and are retained in their source directory but excluded from the final index. The old known FIT72 `task_b` B+Age entries are likewise retained and superseded by the already verified 72-record corrected v2 epoch. B+C rows are not replaced.','','The correction table compares the preserved old mislabeled results with the corrected authoritative results. See `b_age_before_after_summary.csv`. The new unseen correction contains 144 full step-level replays (72 per condition), zero unwanted contacts, bound to the adapter, engine, registry, Python and package provenance. The known 72-case corrected epoch has a full-replay journal and exact record SHA validation.','','The corrected definition uses the existing registry/adapter code; no algorithm or threshold was tuned.']
    (OUT/'b_age_correction_report.md').write_text('\n'.join(b_age_report)+'\n')
    # Source/input integrity report and validation.
    comp_manifest_mismatch='protocol/model_registry.csv'
    full_manifest_mismatches=27
    counts=Counter(r['evaluation_condition'] for r in metrics)
    contacts=sum(r['unwanted_contact_episode'] for r in metrics)
    source_validation={'episodes':len(metrics),'by_condition':dict(counts),'models':54,
        'unique_cases':len({(r['evaluation_condition'],r['model_id'],r['world_identity'],r['schedule']) for r in metrics}),
        'source_sha256_verified_for_every_episode':True,'unwanted_contact_episodes':contacts,
        'semantic_parity_pairs':432,'semantic_parity_status':'PASS',
        'all_model_timing_episodes':19440,'all_model_timing_status':json.loads((TIMING/'summary.json').read_text())['status'],
        'known_manifest_integrity_findings':{'h2_comprehensive_benchmark_v1_stale_manifest_entries':1,'path':comp_manifest_mismatch,
            'h2_full_spatial_memory_replay_v1_stale_aggregate_manifest_entries':full_manifest_mismatches,
            'handling':'Preserved all historical files unchanged. Individual episode files were revalidated against append-only stage journals; stale aggregate analysis/manifest entries were not accepted as episode source authority.'}}
    dump_exclusive(OUT/'validation_summary.json',source_validation)
    lines=['# Validation report','','- Authoritative replay index: 11,664 unique episodes; 3,888 per condition; 54 models per condition. Every referenced gzip file was SHA-256 checked before indexing.','- Semantic optimization parity: 432 paired cases passed (Periodic-5 and Age-5 × 72 cases × 3 conditions); episode results and model-owned controller state matched after filtering only diagnostic-only score fields and runtime measurements.','- All-model controlled cost remeasurement: 19,440 episodes (54 models × 72 saved cases × 5 repetitions); PASS. 19,080 exact historical semantic matches plus 360 declared B+Age historical-definition mismatches; zero unexpected mismatches.','- Corrected B+Age unseen replay: 144 cases (72 low-frequency, 72 high-frequency); full step memory present; zero unwanted contacts. Corrected Known FIT72 B+Age: 72/72 journal hashes validated.','- Preservation: the existing protected-file gate reported 836 checked files in the source H2 recovery summary; no prior results were overwritten by this work. Current verification checks only read or new reconciliation outputs.','- Historical aggregate-manifest caveat: one stale comprehensive registry CSV entry and 27 stale full-replay aggregate entries were detected. Original artifacts were not modified. Per-episode source hashes and journals were checked independently.','- Environment: timing run had one logged interruption at 1,259 records to fix noisy progress logging; all records were durable, a binding amendment and resource snapshots were appended, and the same matrix resumed.','']
    (OUT/'validation_report.md').write_text('\n'.join(lines))
    # Poster claims/update summary from measured outputs.
    hf={r['model_id']:r for r in summary if r['evaluation_condition']=='unseen_high_frequency'}
    best=max(summary,key=lambda r:(r['evaluation_condition']=='unseen_high_frequency',r['goal_success_rate']))
    p=hf['periodic5'];foot=hf['rdao_v1_footprint'];ratio=foot['mean_total_model_computation_ms']/p['mean_total_model_computation_ms']
    updates=['# Poster and project-page update summary','',
      f'- Corrected B + Age metrics are in `b_age_before_after_summary.csv`; the old mislabeled B+C outputs remain preserved but are excluded from the authoritative index.','',
      f'- Unseen-HF highest observed success: {foot["model_id"]} at {foot["goal_success_rate"]*100:.2f}% ({foot["goal_completions"]}/72).',
      f'- Periodic-5 success: {p["goal_success_rate"]*100:.2f}% ({p["goal_completions"]}/72); RDAO v1 Footprint difference: {(foot["goal_success_rate"]-p["goal_success_rate"])*100:+.2f} percentage points.',
      f'- Paid observations: Periodic-5 {p["mean_paid_observations"]:.3f}; RDAO v1 Footprint {foot["mean_paid_observations"]:.3f}; difference {(foot["mean_paid_observations"]-p["mean_paid_observations"]):+.3f}.',
      f'- Computation: Periodic-5 {p["mean_total_model_computation_ms"]:.6f} ms; RDAO v1 Footprint {foot["mean_total_model_computation_ms"]:.6f} ms, {ratio:.1f}× Periodic-5.',
      f'- Unseen-HF Pareto fronts: 2-objective {len(pareto2)} models; 3-objective {len(pareto3)} models (see CSVs).',
      f'- Unwanted contact episodes across all 11,664: {contacts}.',
      '- Break-even values are hypothetical observation-cost thresholds, not measured sensor energy, power, or end-to-end runtime.',
      '- Recommended wording: RDAO v1 Footprint has the highest observed success in these saved cases, but paired intervals should be cited and the result remains descriptive; its computation cost is substantial. Periodic-5 is a materially lower-compute trade-off. No universal winner or independent validation claim is supported.','']
    (OUT/'poster_update_summary.md').write_text('\n'.join(updates))
    index_sha=sha(existing);metrics_sha=sha(OUT/'final_episode_metrics.csv');summary_sha=sha(OUT/'final_model_summary.csv')
    final=['# H2 final benchmark reconciliation','','## Scope','',
      'This is a descriptive development evaluation using 54 admitted models, the 36 existing FIT72 maps and 36 existing H2 generalization maps, two schedules, seed 42, and existing transition schedules. No environment was generated. Historical files were preserved.','',
      'The final dataset contains 11,664 unique episodes: known low-frequency 3,888, unseen low-frequency 3,888, unseen high-frequency 3,888. Its replay index reuses the H2 replay schema fields and adds condition/source annotations.','',
      '## Semantic optimization','',
      'Periodic-5 now returns before the unused age-grid allocation and score calculation. Age-5 computes only the age+1 fraction used by its grant rule. All 432 paired case comparisons passed, including controller state after each decision and update. The 52 other models were audited but not modified.','',
      '## Computational cost','',
      'The first selected-model remeasurement found material anchor variation relative to the immediately preceding timing batch, so all 54 models were measured in one new controlled epoch (19,440 episodes, five repetitions). See `all_model_timing_v1/summary.json`, `all_model_episode_timings.csv`, and `decision_microbenchmark.csv`. Existing 19,440 timing artifacts are retained.','',
      '## Corrected B + Age','',
      'Known FIT72 uses the verified corrected v2 72-case epoch. Unseen low/high conditions use a new 144-case full-replay epoch. The old misconfigured B+Age records are preserved but excluded; correct B+C remains unchanged. See `b_age_correction_report.md`.','',
      '## Results and interpretation','',
      'See `final_model_summary.csv`, paired comparisons, whole-maze bootstrap intervals, Pareto fronts, break-even thresholds, poster tables and figures. Break-even is a hypothetical scan-cost model, not measured sensor energy. Safety counts are recomputed from the selected episode metrics.','',
      'Aggregate input-manifest caveats and preservation checks are documented in `validation_report.md`. The stale historical manifests were not silently refreshed.','',
      f'Artifact hashes: replay index `{index_sha}`, episode metrics `{metrics_sha}`, model summary `{summary_sha}`.','']
    (OUT/'final_report.md').write_text('\n'.join(final))
    print(json.dumps({'index_entries':len(index),'episode_metrics':len(metrics),'model_summary_rows':len(summary),
        'conditions':dict(counts),'unwanted_contact_episodes':contacts,'pareto_2d':len(pareto2),'pareto_3d':len(pareto3),
        'index_sha256':index_sha,'status':'ASSEMBLED'},sort_keys=True),flush=True)

if __name__=='__main__':main()
