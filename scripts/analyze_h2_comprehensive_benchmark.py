"""Integrate historical H2 results and analyze the new 54-model benchmark."""
from __future__ import annotations
import csv,gzip,json,math,hashlib,random
from collections import Counter,defaultdict
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/phase2_mujoco/h2_comprehensive_benchmark_v1'
REGISTRY=json.loads((OUT/'protocol/model_registry.json').read_text())
CONDITIONS=('original','high_frequency')
REFERENCES=('periodic4','periodic5','age4','age5')
BOOTSTRAPS=5000
BOOT_SEED=20261115

def read_gz(path):
    with gzip.open(path,'rt') as f:return json.load(f)

def key_of(row):return (str(row['world_identity']),int(row['schedule']),int(row.get('seed',42)))

def all_inputs():
    records=[];replay_by={}
    def model_from_filename(path):
        # Historical row['method'] is not an experiment-arm identifier; it
        # records the underlying controller family and repeats across arms.
        # The immutable, preregistered historical artifact suffix is canonical.
        stem=Path(path).name.removesuffix('.json.gz')
        suffix=stem.split('_',2)[-1]
        aliases={'periodic4':'periodic4','periodic5':'periodic5','age4':'age4','age5':'age5','age6':'age6',
                 'age_route_clock':'age_route_clock','age_route_rescue':'age_route_rescue',
                 'caa_fast':'caa_fast','caa_full':'caa_full','raa_defer':'raa_defer','rdao_v2':'rdao_v2','rdao_v21':'rdao_v21',
                 'uncertainty':'uncertainty'}
        if suffix not in aliases:raise RuntimeError(f'Unknown historical arm suffix: {path}')
        return aliases[suffix]
    # Original H2: 12 policies; Uncertainty's Original replay was stored separately.
    old=ROOT/'results/phase2_mujoco/h2_final_generalization_v1/primary'
    for p in sorted(old.glob('episode_*.json.gz')):
        x=read_gz(p);row=x['row'];arm=model_from_filename(p)
        records.append(('original',arm,row,x.get('diagnostics',{}),x.get('trace'),p))
    # High-frequency: all 13 frozen H2 arms have complete replay records.
    hf=ROOT/'results/phase2_mujoco/h2_high_frequency_dynamics_v1/replays/primary'
    for p in sorted(hf.glob('episode_*.json.gz')):
        x=read_gz(p);row=x['row'];arm=model_from_filename(p)
        records.append(('high_frequency',arm,row,x.get('diagnostics',{}),x.get('replay'),p))
    # Original Uncertainty is preserved in the separately named archive.
    for p in sorted((ROOT/'results/phase2_mujoco/h2_high_frequency_dynamics_v1/replays/original_uncertainty').glob('episode_*.json.gz')):
        x=read_gz(p);row=x['row'];records.append(('original','uncertainty',row,x.get('diagnostics',{}),x.get('replay'),p))
    for condition in CONDITIONS:
        folder=OUT/('original_environment' if condition=='original' else 'high_frequency_environment')/'episodes'
        for p in sorted(folder.rglob('*.json.gz')):
            x=read_gz(p);records.append((condition,x['arm'],x['row'],x['diagnostics'],x['replay'],p))
    for condition,arm,row,diag,replay,p in records:
        k=(condition,arm,*key_of(row))
        if k in replay_by:raise RuntimeError(f'Duplicate model episode key: {k}')
        replay_by[k]=(replay,p)
    return records,replay_by

def build_rows(records):
    registry={r['model_id']:r for r in REGISTRY};out=[];replay_by={}
    for condition,arm,row,diag,replay,path in records:
        family=registry.get(arm,{}).get('family',arm)
        timing=diag.get('timing_ns',{}) or {}
        def ms(name):return sum(timing.get(name,[]) or [])/1e6
        decisions=[v/1e6 for v in timing.get('decision',[]) or []]
        def count_value(value):
            if isinstance(value,(list,tuple,dict,set)):return len(value)
            try:return int(value or 0)
            except (TypeError,ValueError):return 0
        event_types=Counter();adds=rems=relocs=noops=0;objects=[]
        object_distribution=row.get('object_count_step_distribution',{}) or {}
        if replay:
            for st in replay.get('steps',[]):
                event=st.get('event',{})
                kind=event.get('event_type','unavailable');event_types[kind]+=1
                adds+=kind=='addition';rems+=kind=='removal';relocs+=kind=='relocation'
                noops+=kind in ('no_op','no_change_in_saved_schedule')
                if event.get('object_count_after') is not None:objects.append(int(event['object_count_after']))
        out.append({
            'condition':condition,'model_id':arm,'model_name':registry.get(arm,{}).get('display_name',arm),
            'family':family,'world_identity':row['world_identity'],'map_family':row.get('mechanism',str(row['world_identity']).split(':')[-2]),
            'schedule':int(row['schedule']),'seed':int(row.get('seed',42)),
            'success':int(bool(row.get('success'))),'contact_free_success':int(bool(row.get('contact_free_success',row.get('success',False)))),
            'elapsed_steps':int(row.get('elapsed_steps',0)),'goal_step':row.get('goal_step') or '',
            'distance_m':float(row.get('travel_distance_m',row.get('travel_distance',0)*.75)),
            'paid_observations':int(row.get('observation_count',0)),
            'noninitial_observations':max(0,int(row.get('observation_count',0))-1),
            'memory_raycasts':int(row.get('spatial_memory_rays',row.get('mujoco_sensor_rays',0))),
            'emergency_raycasts':int(row.get('emergency_safety_raycasts',0)),
            'combined_raycasts':int(row.get('spatial_memory_rays',row.get('mujoco_sensor_rays',0)))+int(row.get('emergency_safety_raycasts',0)),
            'new_cells':sum(int(x.get('new_cells',0)) for x in diag.get('observation_log',[]) or []),
            'changed_known_cells':sum(int(x.get('changed_known_cells',0)) for x in diag.get('observation_log',[]) or []),
            'observation_budget_exhausted':int(bool(row.get('budget_exhausted',False))),
            'stale_map_errors':int(row.get('stale_map_errors',0)),
            'false_persistent_occupancy_updates':int(row.get('false_persistent_occupancy_updates',0)),
            'missed_persistent_changes':int(row.get('missed_persistent_changes',0)),
            'unwanted_contact_pairs':int(row.get('g1_unwanted_contact_pairs',0)),
            'unwanted_contact_states':int(row.get('g1_unwanted_contact_states',0)),
            'emergency_interventions':int(row.get('emergency_safety_interventions',0)),
            'shield_rejections':count_value(row.get('g1_rejected_actions',row.get('g1_footprint_blocked_attempts',0))),
            'forward_translations':int(row.get('g1_executed_forward_translations',0)),
            'lateral_steps':int(row.get('g1_executed_lateral_steps',0)),
            'backward_steps':int(row.get('g1_executed_backward_steps',0)),
            'turns':int(row.get('g1_in_place_turns',0)),
            'decision_total_ms':ms('decision'),'decision_calls':len(decisions),
            'decision_mean_call_ms':float(np.mean(decisions)) if decisions else None,
            'decision_median_call_ms':float(np.median(decisions)) if decisions else None,
            'decision_p95_call_ms':float(np.percentile(decisions,95)) if decisions else None,
            'decision_p99_call_ms':float(np.percentile(decisions,99)) if decisions else None,
            'decision_max_call_ms':max(decisions,default=None),
            'initialization_ms':ms('initialization'),'memory_update_ms':ms('update'),
            'memory_sensor_ms':ms('memory_sensor'),'emergency_sensor_ms':ms('emergency_sensor'),
            'navigation_planning_ms':ms('navigation_planning'),'safety_decision_ms':ms('safety_decision'),
            'compute_ms':ms('initialization')+ms('decision')+ms('update'),
            'episode_wall_seconds':float(row.get('episode_wall_time_seconds',0)),
            'replay_logging_ms':float(row.get('replay_logging_total_ms',0)),
            'active_environment_steps':int(row.get('dynamic_steps',row.get('elapsed_steps',0))),
            'environment_changes':int(row.get('environment_changes',adds+rems+relocs)),
            'event_additions':int(row.get('addition_count',adds)),
            'event_removals':int(row.get('removal_count',rems)),
            'event_relocations':int(row.get('relocation_count',relocs)),
            'environment_noops':int(row.get('environment_no_ops',noops)),
            'mean_object_count':float(row.get('mean_object_count',np.mean(objects) if objects else 0)),
            **{f'object_steps_{n}':int(object_distribution.get(str(n),0)) for n in range(5)},
            'mean_changed_cells_per_step':float(row.get('changed_cells_per_step_mean',0)),
            'mean_robot_distance_to_changed_cells':float(row.get('changed_cell_chebyshev_distance_mean',0)),
            'candidate_rejections':sum(int(v) for v in (row.get('candidate_rejections_by_reason',{}) or {}).values()),
            'candidate_rejections_by_reason':json.dumps(row.get('candidate_rejections_by_reason',{}) or {},sort_keys=True),
            'connectivity_violations':int(row.get('connectivity_violations',0)),
            'exclusion_zone_violations':int(row.get('exclusion_zone_violations',0)),
            'transition_generation_ms':float(row.get('transition_generation_total_ms',0)),
            'scene_frame_update_ms':float(row.get('scene_frame_update_total_ms',0)),
            'failure_reason':row.get('failure_reason') or '',
            'historical_or_new_source':('historical' if registry.get(arm,{}).get('previously_evaluated') else 'new'),
            'replay_path':path.relative_to(ROOT).as_posix(),
        })
        if replay:replay_by[(condition,arm,*key_of(row))]=(replay,path)
    return out,replay_by

def write_csv(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore',lineterminator='\n');w.writeheader();w.writerows(rows)

def aggregate(rows):
    n=len(rows)
    if not n:return {'episodes':0}
    out={'episodes':n,'goals':sum(r['success'] for r in rows),'goal_rate':sum(r['success'] for r in rows)/n,
        'contact_free_goals':sum(r['contact_free_success'] for r in rows),
        'contact_free_goal_rate':sum(r['contact_free_success'] for r in rows)/n,
        'mean_paid_observations':float(np.mean([r['paid_observations'] for r in rows])),
        'mean_elapsed_steps':float(np.mean([r['elapsed_steps'] for r in rows])),
        'mean_distance_m':float(np.mean([r['distance_m'] for r in rows])),
        'mean_decision_ms_per_episode':float(np.mean([r['decision_total_ms'] for r in rows])),
        'mean_compute_ms':float(np.mean([r['compute_ms'] for r in rows])),
        'mean_episode_wall_seconds':float(np.mean([r['episode_wall_seconds'] for r in rows])),
        'combined_raycasts':sum(r['combined_raycasts'] for r in rows),
        'mean_combined_raycasts':float(np.mean([r['combined_raycasts'] for r in rows])),
        'unwanted_contact_episodes':sum(r['unwanted_contact_pairs']>0 for r in rows),
        'unwanted_contact_states':sum(r['unwanted_contact_states'] for r in rows),
        'unwanted_contact_pairs':sum(r['unwanted_contact_pairs'] for r in rows),
        'emergency_interventions':sum(r['emergency_interventions'] for r in rows),
        'observation_budget_exhaustions':sum(r['observation_budget_exhausted'] for r in rows),
        'false_persistent_occupancy_updates':sum(r['false_persistent_occupancy_updates'] for r in rows),
        'missed_persistent_changes':sum(r['missed_persistent_changes'] for r in rows),
        'candidate_rejections':sum(r['candidate_rejections'] for r in rows),
        'connectivity_violations':sum(r['connectivity_violations'] for r in rows),
        'exclusion_zone_violations':sum(r['exclusion_zone_violations'] for r in rows),
        'mean_initialization_ms':float(np.mean([r['initialization_ms'] for r in rows])),
        'mean_memory_update_ms':float(np.mean([r['memory_update_ms'] for r in rows])),
        'mean_memory_sensor_ms':float(np.mean([r['memory_sensor_ms'] for r in rows])),
        'mean_emergency_sensor_ms':float(np.mean([r['emergency_sensor_ms'] for r in rows])),
        'mean_navigation_planning_ms':float(np.mean([r['navigation_planning_ms'] for r in rows])),
        'mean_safety_decision_ms':float(np.mean([r['safety_decision_ms'] for r in rows])),
        'mean_transition_generation_ms':float(np.mean([r['transition_generation_ms'] for r in rows])),
        'mean_scene_frame_update_ms':float(np.mean([r['scene_frame_update_ms'] for r in rows])),
        'mean_replay_logging_ms':float(np.mean([r['replay_logging_ms'] for r in rows])),
        'mean_changed_cells_per_step':float(np.mean([r['mean_changed_cells_per_step'] for r in rows])),
        'mean_robot_distance_to_changed_cells':float(np.mean([r['mean_robot_distance_to_changed_cells'] for r in rows])),
        'mean_decision_call_ms':float(np.mean([r['decision_mean_call_ms'] for r in rows if r['decision_mean_call_ms'] is not None])) if any(r['decision_mean_call_ms'] is not None for r in rows) else None,
        'decision_call_median_ms':float(np.median([r['decision_median_call_ms'] for r in rows if r['decision_median_call_ms'] is not None])) if any(r['decision_median_call_ms'] is not None for r in rows) else None,
        'decision_call_p95_ms':float(np.percentile([r['decision_p95_call_ms'] for r in rows if r['decision_p95_call_ms'] is not None],95)) if any(r['decision_p95_call_ms'] is not None for r in rows) else None,
        'decision_call_p99_ms':float(np.percentile([r['decision_p99_call_ms'] for r in rows if r['decision_p99_call_ms'] is not None],99)) if any(r['decision_p99_call_ms'] is not None for r in rows) else None,
    }
    succ=[r for r in rows if r['success']]
    out['success_only_mean_steps']=float(np.mean([r['elapsed_steps'] for r in succ])) if succ else None
    out['success_only_mean_distance_m']=float(np.mean([r['distance_m'] for r in succ])) if succ else None
    return out

def bootstrap_delta(candidate,reference,metric):
    cm=defaultdict(list);rm=defaultdict(list)
    for r in candidate:cm[r['world_identity']].append(r)
    for r in reference:rm[r['world_identity']].append(r)
    ids=sorted(set(cm)&set(rm))
    if len(ids)!=36:raise RuntimeError(f'Whole-maze bootstrap expected 36 maps, got {len(ids)}')
    cluster=[]
    for identity in ids:
        ca={r['schedule']:r for r in cm[identity]};ra={r['schedule']:r for r in rm[identity]}
        if set(ca)!=set(ra) or len(ca)!=2:raise RuntimeError(f'Paired schedule mismatch {identity}')
        cluster.append(float(np.mean([float(ca[s][metric])-float(ra[s][metric]) for s in ca])))
    arr=np.asarray(cluster);rng=np.random.default_rng(BOOT_SEED)
    draws=rng.integers(0,len(arr),(BOOTSTRAPS,len(arr)))
    vals=arr[draws].mean(axis=1)
    return float(arr.mean()),float(np.quantile(vals,.025)),float(np.quantile(vals,.975))

def analyze():
    output=OUT/'analysis';output.mkdir(exist_ok=False)
    records,replay_index=all_inputs();rows,replay_index=build_rows(records)
    expected=54*72*2
    if len(rows)!=expected:raise RuntimeError(f'Expected {expected} available episodes, got {len(rows)}')
    ids={(r['condition'],r['model_id'],r['world_identity'],r['schedule']) for r in rows}
    if len(ids)!=len(rows):raise RuntimeError('Duplicate combined episode identity')
    write_csv(OUT/'combined_dataset/episode_metrics.csv',rows)
    reg={x['model_id']:x for x in REGISTRY}
    model_summaries=[];per_condition={}
    for cond in CONDITIONS:
        for mid,meta in reg.items():
            rr=[r for r in rows if r['condition']==cond and r['model_id']==mid]
            status=meta['authorization_status']
            model_summaries.append({'condition':cond,'model_id':mid,'display_name':meta['display_name'],
                'family':meta['family'],'status':status,'episodes':len(rr),**aggregate(rr)})
        per_condition[cond]={mid:[r for r in rows if r['condition']==cond and r['model_id']==mid] for mid in reg}
    write_csv(output/'model_summary.csv',model_summaries)
    for cond,name in [('original','original_environment_summary.csv'),('high_frequency','high_frequency_environment_summary.csv')]:
        write_csv(output/name,[r for r in model_summaries if r['condition']==cond])
    # Matched original-to-high-frequency change for each available model.
    env=[]
    metrics=('success','paid_observations','elapsed_steps','distance_m','compute_ms','episode_wall_seconds','unwanted_contact_pairs')
    for mid,meta in reg.items():
        a=per_condition['original'][mid];b=per_condition['high_frequency'][mid]
        if not a or not b:env.append({'model_id':mid,'status':meta['authorization_status'],'episodes':0});continue
        aa={key_of(r):r for r in a};bb={key_of(r):r for r in b}
        if aa.keys()!=bb.keys():raise RuntimeError(f'Environment pairing mismatch: {mid}')
        out={'model_id':mid,'display_name':meta['display_name'],'family':meta['family'],'episodes':len(aa),'status':'COMPLETE'}
        for m in metrics:out['delta_'+m]=float(np.mean([bb[k][m]-aa[k][m] for k in aa]))
        env.append(out)
    write_csv(output/'environment_comparison.csv',env)
    # Prespecified paired contrasts and whole-maze clustered bootstrap.
    paired=[];boot=[]
    for cond in CONDITIONS:
        for mid,meta in reg.items():
            cand=per_condition[cond][mid]
            if not cand:continue
            for base in REFERENCES:
                ref=per_condition[cond][base]
                if not ref:continue
                ci={key_of(r):r for r in cand};ri={key_of(r):r for r in ref}
                if ci.keys()!=ri.keys():raise RuntimeError(f'Paired episode key mismatch {mid}/{base}/{cond}')
                rescues=sum(not ri[k]['success'] and ci[k]['success'] for k in ci)
                harms=sum(ri[k]['success'] and not ci[k]['success'] for k in ci)
                common=[k for k in ci if ri[k]['success'] and ci[k]['success']]
                row={'condition':cond,'candidate':mid,'reference':base,'episodes':len(ci),
                    'rescues':rescues,'harms':harms,'common_successes':len(common),
                    'goal_rate_delta':float(np.mean([ci[k]['success']-ri[k]['success'] for k in ci])),
                    'observation_delta':float(np.mean([ci[k]['paid_observations']-ri[k]['paid_observations'] for k in ci])),
                    'steps_delta_all':float(np.mean([ci[k]['elapsed_steps']-ri[k]['elapsed_steps'] for k in ci])),
                    'distance_delta_all_m':float(np.mean([ci[k]['distance_m']-ri[k]['distance_m'] for k in ci])),
                    'steps_delta_common_success':float(np.mean([ci[k]['elapsed_steps']-ri[k]['elapsed_steps'] for k in common])) if common else None,
                    'distance_delta_common_success_m':float(np.mean([ci[k]['distance_m']-ri[k]['distance_m'] for k in common])) if common else None,
                    'contact_pair_delta':int(sum(ci[k]['unwanted_contact_pairs']-ri[k]['unwanted_contact_pairs'] for k in ci))}
                paired.append(row)
                for metric in ('success','paid_observations','elapsed_steps','distance_m','compute_ms','episode_wall_seconds','unwanted_contact_pairs'):
                    mean,lo,hi=bootstrap_delta(cand,ref,metric)
                    boot.append({'condition':cond,'candidate':mid,'reference':base,'metric':metric,
                        'cluster_count':36,'schedules_per_cluster':2,'draws':BOOTSTRAPS,'seed':BOOT_SEED,
                        'mean_delta':mean,'ci95_low':lo,'ci95_high':hi})
    write_csv(output/'paired_comparisons.csv',paired);write_csv(output/'bootstrap_intervals.csv',boot)
    # Safety, dynamics, failures and Pareto/break-even tables.
    safety=[];dynamics=[];failures=[];pareto=[];breakeven=[]
    for cond in CONDITIONS:
        summaries={r['model_id']:r for r in model_summaries if r['condition']==cond}
        for mid,m in summaries.items():
            rr=per_condition[cond][mid]
            safety.append({'condition':cond,'model_id':mid,'status':m['status'],'episodes':m['episodes'],
                'contact_episodes':m.get('unwanted_contact_episodes',0),'contact_states':m.get('unwanted_contact_states',0),
                'contact_pairs':m.get('unwanted_contact_pairs',0),'emergency_interventions':m.get('emergency_interventions',0),
                'shield_rejections':sum(r['shield_rejections'] for r in rr)})
            dynamics.append({'condition':cond,'model_id':mid,'episodes':len(rr),
                'active_steps':sum(r['active_environment_steps'] for r in rr),
                'environment_changes':sum(r['environment_changes'] for r in rr),
                'mean_change_rate':float(np.mean([r['environment_changes']/max(1,r['active_environment_steps']) for r in rr])) if rr else None,
                'additions':sum(r['event_additions'] for r in rr),'removals':sum(r['event_removals'] for r in rr),
                'relocations':sum(r['event_relocations'] for r in rr),'noops':sum(r['environment_noops'] for r in rr),
                'candidate_rejections':sum(r['candidate_rejections'] for r in rr),
                **{f'candidate_rejection_{reason}':sum(int(json.loads(r['candidate_rejections_by_reason']).get(reason,0)) for r in rr)
                   for reason in ('existing_object','goal_connectivity','goal_protected','robot_exclusion_zone','same_source_destination','static_wall')},
                'connectivity_violations':sum(r['connectivity_violations'] for r in rr),
                'exclusion_zone_violations':sum(r['exclusion_zone_violations'] for r in rr),
                'mean_changed_cells_per_step':float(np.mean([r['mean_changed_cells_per_step'] for r in rr])) if rr else None,
                'mean_robot_distance_to_changed_cells':float(np.mean([r['mean_robot_distance_to_changed_cells'] for r in rr])) if rr else None,
                **{f'object_steps_{n}':sum(r[f'object_steps_{n}'] for r in rr) for n in range(5)},
                'mean_object_count':float(np.mean([r['mean_object_count'] for r in rr])) if rr else None})
            for r in rr:
                if not r['success']:failures.append({k:r[k] for k in ('condition','model_id','world_identity','schedule','seed','elapsed_steps','distance_m','failure_reason','unwanted_contact_pairs','paid_observations')})
        available=[m for m in summaries.values() if m['episodes']]
        for m in available:
            dominated=False
            for q in available:
                if q['model_id']==m['model_id']:continue
                no_worse=(q['goal_rate']>=m['goal_rate'] and q['mean_paid_observations']<=m['mean_paid_observations'] and q['mean_compute_ms']<=m['mean_compute_ms'])
                strictly=(q['goal_rate']>m['goal_rate'] or q['mean_paid_observations']<m['mean_paid_observations'] or q['mean_compute_ms']<m['mean_compute_ms'])
                if no_worse and strictly:dominated=True;break
            pareto.append({'condition':cond,'model_id':m['model_id'],'pareto_optimal':not dominated,
                'goal_rate':m['goal_rate'],'mean_paid_observations':m['mean_paid_observations'],
                'mean_compute_ms':m['mean_compute_ms'],'mean_wall_seconds':m['mean_episode_wall_seconds']})
        base=summaries.get('periodic5')
        if base and base['episodes']:
            for m in available:
                obs_saving=base['mean_paid_observations']-m['mean_paid_observations']
                compute_delta=m['mean_compute_ms']-base['mean_compute_ms']
                c=compute_delta/obs_saving if obs_saving else None
                breakeven.append({'condition':cond,'model_id':m['model_id'],'reference':'periodic5',
                    'break_even_observation_cost_ms':c,'candidate_observation_savings':obs_saving,
                    'compute_cost_delta_ms':compute_delta,
                    'nonnegative_break_even':bool(c is not None and c>=0)})
    write_csv(output/'safety_summary.csv',safety);write_csv(output/'environment_dynamics_summary.csv',dynamics)
    write_csv(output/'failure_cases.csv',failures);write_csv(output/'pareto_frontier.csv',pareto);write_csv(output/'break_even_analysis.csv',breakeven)
    replay_rows=[{'condition':key[0],'model_id':key[1],'world_identity':key[2],'schedule':key[3],
        'seed':key[4],'path':p.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
        for key,(r,p) in replay_index.items()]
    write_csv(output/'replay_index.csv',replay_rows)
    make_figures(model_summaries,env,paired,safety,dynamics,boot,output)
    validation={'status':'PASS','rows':len(rows),'available_models':54,'blocked_models':3,
        'expected_rows':7776,'historical_original_rows':936,'historical_high_frequency_rows':936,
        'bootstrap':{'draws':BOOTSTRAPS,'seed':BOOT_SEED,'clusters':36,'paired_schedules':2},
        'independent_validation':False,'analysis_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (output/'analysis_validation.json').write_text(json.dumps(validation,indent=2,sort_keys=True)+'\n')
    print(json.dumps(validation,sort_keys=True),flush=True)

def make_figures(summaries,env,paired,safety,dynamics,boot,out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    colors={'Baseline':'#34495e','Periodic':'#2878b5','Age':'#63a83b','Event-triggered':'#d97828','RDAO':'#8e63b0','Persistence/EVI':'#cc4f78','Candidate coverage':'#ab7c20','Topology EVI':'#25a8a1','Multi-step EVI':'#4370b4','Multi-step depth':'#5b9f97','CAA':'#906b46','DAO':'#d14b45','RAA':'#697a89','Uncertainty':'#8b8b8b'}
    ids=[r['model_id'] for r in REGISTRY];labels={r['model_id']:r['display_name'] for r in REGISTRY}
    fam={r['model_id']:r['family'] for r in REGISTRY}
    by={(r['condition'],r['model_id']):r for r in summaries}
    def save(name):
        plt.tight_layout();plt.savefig(out/(name+'.png'),dpi=180,bbox_inches='tight');plt.close()
    def bars(cond,metric,title,ylabel,name):
        vals=[by.get((cond,i),{}).get(metric,np.nan) for i in ids]
        plt.figure(figsize=(21,7));plt.bar(range(len(ids)),vals,color=[colors.get(fam[i],'gray') for i in ids]);plt.xticks(range(len(ids)),[labels[i] for i in ids],rotation=70,ha='right',fontsize=7);plt.title(title);plt.ylabel(ylabel);save(name)
    for cond,suffix in [('original','original'),('high_frequency','high_frequency')]:
        bars(cond,'goal_rate','Goal completion rate','rate','goal_completion_'+suffix)
        bars(cond,'mean_paid_observations','Mean paid observations','observations','paid_observations_'+suffix)
        bars(cond,'mean_elapsed_steps','Mean steps including failures','steps','mean_steps_'+suffix)
        bars(cond,'mean_distance_m','Mean travel distance including failures','m','mean_distance_'+suffix)
        bars(cond,'mean_decision_ms_per_episode','Mean decision computation time','ms / episode','decision_time_'+suffix)
        bars(cond,'mean_episode_wall_seconds','Mean episode wall time','seconds','episode_wall_time_'+suffix)
        bars(cond,'mean_combined_raycasts','Mean combined raycasts','rays','combined_raycasts_'+suffix)
        bars(cond,'unwanted_contact_pairs','Unwanted contact pairs','pairs','safety_contacts_'+suffix)
        # Cost plots, family faceting and Pareto view.
        avail=[by[(cond,i)] for i in ids if (cond,i) in by and by[(cond,i)].get('episodes',0)]
        plt.figure(figsize=(11,8))
        for r in avail:plt.scatter(r['mean_paid_observations'],r['goal_rate'],color=colors.get(fam[r['model_id']],'gray'),s=35);plt.text(r['mean_paid_observations'],r['goal_rate'],labels[r['model_id']],fontsize=6)
        plt.xlabel('Mean paid observations');plt.ylabel('Goal completion rate');plt.title('Goal completion vs observation cost — '+cond);save('success_vs_paid_'+cond)
        plt.figure(figsize=(11,8))
        for r in avail:plt.scatter(r['mean_compute_ms'],r['goal_rate'],color=colors.get(fam[r['model_id']],'gray'),s=35);plt.text(r['mean_compute_ms'],r['goal_rate'],labels[r['model_id']],fontsize=6)
        plt.xlabel('Initialization + decision + memory-update ms / episode');plt.ylabel('Goal completion rate');plt.title('Goal completion vs compute — '+cond);save('success_vs_compute_'+cond)
        plt.figure(figsize=(12,8))
        for r in avail:plt.scatter(r['mean_paid_observations'],r['mean_compute_ms'],c=[r['goal_rate']],cmap='viridis',vmin=0,vmax=1,s=55);plt.text(r['mean_paid_observations'],r['mean_compute_ms'],labels[r['model_id']],fontsize=6)
        plt.xlabel('Mean paid observations');plt.ylabel('Initialization + decision + update ms / episode');plt.title('Pareto design space (color = success rate) — '+cond);save('pareto_'+cond)
        # Failure-inclusive outcome heatmap: 36 maps x 2 schedules, blocked rows stay blank.
        subset=[r for r in OUT.joinpath('combined_dataset/episode_metrics.csv').read_text().splitlines()[1:]] if False else None
    # Cross-condition comparisons, families, and schedule-preserving outcomes.
    av=[r for r in env if r.get('episodes')]
    plt.figure(figsize=(18,7));x=np.arange(len(av));plt.bar(x,[r['delta_success'] for r in av],color=[colors.get(fam[r['model_id']],'gray') for r in av]);plt.xticks(x,[labels[r['model_id']] for r in av],rotation=70,ha='right',fontsize=7);plt.ylabel('HF minus Original success');plt.title('Within-model environment change');save('goal_completion_environment_delta')
    plt.figure(figsize=(18,7));plt.bar(x,[r['delta_paid_observations'] for r in av],color=[colors.get(fam[r['model_id']],'gray') for r in av]);plt.xticks(x,[labels[r['model_id']] for r in av],rotation=70,ha='right',fontsize=7);plt.ylabel('HF minus Original paid observations');plt.title('Observation change by environment');save('observation_environment_delta')
    for metric,title in [('goal_rate','Goal completion by model family'),('mean_paid_observations','Paid observations by model family')]:
        plt.figure(figsize=(14,7));families=list(dict.fromkeys(fam.values()))
        for i,f in enumerate(families):
            ys=[by[(c,m)][metric] for c in ('original','high_frequency') for m in ids if fam[m]==f and (c,m) in by and by[(c,m)].get('episodes',0)]
            if ys:plt.scatter([f]*len(ys),ys,label=f,color=colors.get(f,'gray'),alpha=.75)
        plt.xticks(rotation=55,ha='right');plt.title(title);plt.ylabel(metric);save('family_'+metric)
    # Maze-family outcome rates by model. Blocked rows remain absent, never imputed.
    with (OUT/'combined_dataset/episode_metrics.csv').open() as f:data=list(csv.DictReader(f))
    for cond in CONDITIONS:
        for maze_family in ('R','BP','M'):
            rates=[]
            for model in ids:
                subset=[r for r in data if r['condition']==cond and r['model_id']==model and r['map_family']==maze_family]
                if subset:rates.append((model,sum(float(r['success']) for r in subset)/len(subset)))
            plt.figure(figsize=(20,7));xx=np.arange(len(rates))
            plt.bar(xx,[v for _,v in rates],color=[colors.get(fam[m],'gray') for m,_ in rates])
            plt.xticks(xx,[labels[m] for m,_ in rates],rotation=70,ha='right',fontsize=7);plt.ylim(0,1)
            plt.ylabel('Goal completion rate');plt.title(f'{maze_family} maze-family outcomes — {cond}')
            save(f'maze_family_{maze_family}_{cond}')
    for cond in CONDITIONS:
        table=defaultdict(dict)
        for r in data:
            if r['condition']==cond:table[r['model_id']][(r['world_identity'],int(r['schedule']))]=float(r['success'])
        grid=np.full((len(ids),72),np.nan)
        for i,m in enumerate(ids):
            keys=sorted(table[m])
            for j,k in enumerate(keys[:72]):grid[i,j]=table[m][k]
        plt.figure(figsize=(20,12));plt.imshow(grid,aspect='auto',interpolation='nearest',cmap='RdYlGn',vmin=0,vmax=1);plt.yticks(range(len(ids)),[labels[i] for i in ids],fontsize=7);plt.xlabel('Preserved map/schedule key');plt.title('Episode outcome heatmap — '+cond);plt.colorbar(label='Goal reached');save('outcome_heatmap_'+cond)
    # Environmental event distribution and object counts.
    for cond in CONDITIONS:
        d=[r for r in dynamics if r['condition']==cond and r['episodes']]
        plt.figure(figsize=(20,6));x=np.arange(len(d));bottom=np.zeros(len(d))
        for key,color in [('additions','#398bd1'),('removals','#ed8a32'),('relocations','#4b9f55'),('noops','#888888')]:
            vals=np.array([r[key] for r in d]);plt.bar(x,vals,bottom=bottom,label=key,color=color);bottom+=vals
        plt.xticks(x,[labels[r['model_id']] for r in d],rotation=70,ha='right',fontsize=7);plt.legend();plt.title('Environment transitions — '+cond);save('environment_event_distribution_'+cond)
        plt.figure(figsize=(20,7));bottom=np.zeros(len(d))
        for n,color in zip(range(5),('#39536b','#4c86a8','#6ab7b5','#efb85a','#dc7954')):
            vals=np.array([r[f'object_steps_{n}'] for r in d],dtype=float)
            totals=np.maximum(1,np.array([sum(r[f'object_steps_{k}'] for k in range(5)) for r in d],dtype=float))
            frac=vals/totals;plt.bar(x,frac,bottom=bottom,label=str(n),color=color);bottom+=frac
        plt.xticks(x,[labels[r['model_id']] for r in d],rotation=70,ha='right',fontsize=7);plt.ylabel('Fraction of recorded steps');plt.title('Object-count distribution by model — '+cond);plt.legend(title='Objects',ncol=5);save('object_count_distribution_'+cond)
    # Explicit break-even curves versus Periodic-5.
    with (OUT/'analysis/break_even_analysis.csv').open() as f:be=list(csv.DictReader(f))
    for cond in CONDITIONS:
        vals=[r for r in be if r['condition']==cond]
        c=np.linspace(0,1000,100);plt.figure(figsize=(11,7))
        for r in vals:
            rec=by.get((cond,r['model_id']))
            if rec and rec.get('episodes'):plt.plot(c,rec['mean_compute_ms']+rec['mean_paid_observations']*c,label=labels[r['model_id']],linewidth=.8)
        plt.xlabel('Cost per paid observation (ms-equivalent)');plt.ylabel('Total modeled cost per episode');plt.title('Break-even observation cost — '+cond);plt.legend(fontsize=6,ncol=2);save('break_even_'+cond)
    # Paired bootstrap intervals for the four predeclared baselines.
    sel=[r for r in boot if r['metric']=='success' and r['candidate'] not in REFERENCES]
    plt.figure(figsize=(18,9));
    for i,r in enumerate(sel):
        plt.errorbar(i,r['mean_delta'],yerr=[[r['mean_delta']-r['ci95_low']],[r['ci95_high']-r['mean_delta']]],fmt='.',color='tab:blue' if r['condition']=='original' else 'tab:orange',alpha=.45)
    plt.axhline(0,color='black',linewidth=.8);plt.title('Whole-maze bootstrap success deltas (blue Original, orange High-Frequency)');plt.ylabel('success-rate delta');save('paired_bootstrap_success_intervals')

if __name__ == '__main__':
    analyze()
