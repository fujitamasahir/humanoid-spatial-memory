#!/usr/bin/env python3
"""Validate and seal the H2 full spatial-memory replay recovery output."""
from __future__ import annotations
import base64,csv,gzip,hashlib,json,os,sys
from collections import Counter,defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src')]
OUT=ROOT/'results/phase2_mujoco/h2_full_spatial_memory_replay_v1'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def verify_memory(value):
    raw=base64.b64decode(value,validate=True)
    if len(raw)!=(25*25+3)//4:raise ValueError('Bad packed-memory length')
    for i in range(25*25):
        v=((raw[i//4]>>(2*(i%4)))&3)-1
        if v not in (-1,0,1):raise ValueError('Invalid ternary code')

def _load_manifest_inputs():
    import json
    binding=json.loads((OUT/'binding.json').read_text())
    pointer=OUT/'active_binding.json';active=json.loads(pointer.read_text())
    active_path=OUT/active['path']
    if sha(active_path)!=active['sha256']:raise RuntimeError('Active binding hash mismatch')
    bound=json.loads(active_path.read_text())
    for rel,digest in bound['source_sha256'].items():
        if sha(ROOT/rel)!=digest:raise RuntimeError(f'Source drift: {rel}')
    return binding,bound,active_path

def _stage(stage,expected):
    root=OUT/stage;ledger={}
    for line in (root/'journal.jsonl').read_text().splitlines():
        e=json.loads(line)
        if e.get('event')!='episode_committed':continue
        if e['path'] in ledger:raise RuntimeError(f'Duplicate journal path: {e["path"]}')
        ledger[e['path']]=e
    files=sorted((root/'episodes').rglob('*.json.gz'))
    if len(files)!=expected or len(ledger)!=expected:
        raise RuntimeError(f'{stage}: expected {expected} episodes; files={len(files)} journal={len(ledger)}')
    parity=Counter();models=defaultdict(lambda:{'episodes':0,'goals':0,'observations':0,'steps':0,'distance':0.0,'contacts':0})
    index=[];errors=[]
    for path in files:
        rel=path.relative_to(OUT).as_posix();entry=ledger.get(rel)
        if entry is None or sha(path)!=entry['sha256'] or path.stat().st_size!=entry['bytes']:
            raise RuntimeError(f'Journal/SHA mismatch: {rel}')
        with gzip.open(path,'rt',encoding='utf-8') as fh:d=json.load(fh)
        replay=d['replay'];row=d['row'];steps=replay['steps'];arm=d['arm']
        if len(steps)!=int(row['elapsed_steps'])+1:raise RuntimeError(f'Frame count mismatch: {rel}')
        if [int(x['step']) for x in steps]!=list(range(len(steps))):raise RuntimeError(f'Noncontiguous steps: {rel}')
        if not steps or int(steps[0]['step'])!=0:raise RuntimeError(f'Missing s0: {rel}')
        paid=[]
        for i,s in enumerate(steps):
            for key in ('spatial_memory_ternary_packed_2bit_base64','spatial_memory_end_of_step_packed_2bit_base64',
                        'spatial_memory_after_observation_update_packed_2bit_base64'):
                verify_memory(s[key])
            if i>0:
                verify_memory(s['spatial_memory_before_observation_decision_packed_2bit_base64'])
                verify_memory(s['spatial_memory_before_observation_update_packed_2bit_base64'])
            count=int(s['paid_observation_count']);paid.append(count)
            if count>20 or count<1:raise RuntimeError(f'Observation cap violation: {rel} step {i}')
            if i and count < paid[-2]:raise RuntimeError(f'Observation count decreased: {rel} step {i}')
        if int(row['observation_count'])!=paid[-1]:raise RuntimeError(f'Observation total mismatch: {rel}')
        if bool(replay['outcome']['success'])!=bool(row['success']):raise RuntimeError(f'Outcome mismatch: {rel}')
        p=d['parity'];parity[p['status']]+=1
        m=models[arm];m['episodes']+=1;m['goals']+=int(bool(row['success']))
        m['observations']+=int(row['observation_count']);m['steps']+=int(row['elapsed_steps'])
        m['distance']+=float(row.get('travel_distance_m',row.get('travel_distance',0)))
        m['contacts']+=int(row.get('g1_unwanted_contact_pairs',row.get('dynamic_contacts',0)))
        index.append({'path':rel,'sha256':entry['sha256'],'bytes':entry['bytes'],'dataset':d['dataset'],
            'condition':d['condition'],'model_id':arm,'map_identity':d['map_identity'],'schedule':d['schedule'],
            'seed':d['seed'],'frames':len(steps),'paid_observations':row['observation_count'],
            'success':bool(row['success']),'goal_step':row.get('goal_step',replay.get('outcome',{}).get('goal_step')),
            'steps':int(row['elapsed_steps']),'distance_m':float(row.get('travel_distance_m',row.get('travel_distance',0))),
            'unwanted_contact_pairs':int(row.get('g1_unwanted_contact_pairs',row.get('dynamic_contacts',0))),
            'parity_status':p['status'],'parity_detail':p.get('detail'),
            'historical_records':p.get('historical_records',[])})
    expected_models=12 if stage=='task_a' else 54
    if len(models)!=expected_models or any(m['episodes']!=72 for m in models.values()):
        raise RuntimeError(f'{stage}: per-model coverage is incomplete')
    return index,parity,models

def finalize():
    if (OUT/'artifact_manifest.json').exists():raise FileExistsError('Output already sealed')
    initial,active,active_path=_load_manifest_inputs()
    aidx,aparity,amodels=_stage('task_a',864)
    bidx,bparity,bmodels=_stage('task_b',3888)
    if aparity!=Counter({'PASS_EXACT_TRACE_AND_METRIC_SIGNATURE':864}):
        raise RuntimeError(f'Task A exact parity gate failed: {aparity}')
    import h2_high_frequency_dynamics as engine
    import h2_comprehensive_adapters as adapters
    from verify_dao_integrity import verify as verify_preservation
    from run_h2_comprehensive_benchmark import verify_manifests
    protected=verify_preservation()
    if protected.get('status')!='PASS':raise RuntimeError(f'Preservation gate after recovery failed: {protected}')
    if verify_manifests()!=initial['historical_manifests_verified']:
        raise RuntimeError('Historical H2 artifact manifest count changed')
    index=aidx+bidx
    idxpath=OUT/'replay_index.csv'
    with idxpath.open('x',newline='',encoding='utf-8') as fh:
        fields=['path','sha256','bytes','dataset','condition','model_id','map_identity','schedule','seed','frames','steps','goal_step','paid_observations','success','distance_m','unwanted_contact_pairs','parity_status','parity_detail','historical_records']
        w=csv.DictWriter(fh,fieldnames=fields);w.writeheader()
        for item in sorted(index,key=lambda x:(x['dataset'],x['map_identity'],x['schedule'],x['model_id'])):
            item=dict(item);item['historical_records']=json.dumps(item['historical_records'],sort_keys=True);w.writerow(item)
    # Backward-compatible union index: retain all 7,776 prior entries exactly
    # and append this recovery's three explicitly identified datasets.
    prior_path=ROOT/'results/phase2_mujoco/h2_comprehensive_benchmark_v1/combined_dataset/replay_index.json'
    prior=json.loads(prior_path.read_text())
    if len(prior.get('entries',[]))!=7776:raise RuntimeError('Prior integrated index count changed')
    additions=[]
    for item in index:
        dataset_id='fit72_known_original' if item['dataset']=='fit72_known' else 'h2_unseen_original'
        additions.append({'condition':'original','dataset_id':dataset_id,'model_id':item['model_id'],
            'world_identity':item['map_identity'],'map_id':item['map_identity'],'schedule':item['schedule'],
            'seed':item['seed'],'path':item['path'],'sha256':item['sha256'],'schema_version':'h2_full_spatial_memory_replay_v1',
            'active_steps':item['frames']-1,'frames':item['frames'],'goal_completion':item['success'],
            'paid_observation_count':item['paid_observations'],'full_spatial_memory_available':True,
            'historical_reproduction_status':item['parity_status'],'source_artifact_reference':item['path'],
            'protocol_binding_sha256':sha(active_path)})
    # Existing index already includes the unseen Original and High-Frequency
    # dataset entries. Do not rewrite their payload objects or source paths.
    combined={'schema_version':'phase2_combined_replay_index_v2',
        'legacy_index_path':prior_path.relative_to(ROOT).as_posix(),
        'legacy_index_sha256':sha(prior_path),'legacy_entry_count':len(prior['entries']),
        'new_entry_count':len(additions),'entries':prior['entries']+additions}
    indexdir=OUT/'combined_replay_index';indexdir.mkdir(exist_ok=True)
    combinedpath=indexdir/'replay_index_v2.json'
    combinedpath.write_text(json.dumps(combined,sort_keys=True,indent=2)+'\n')
    registry_path=ROOT/'results/phase2_mujoco/h2_comprehensive_benchmark_v1/protocol/model_registry.json'
    (OUT/'model_registry.json').write_bytes(registry_path.read_bytes())
    metrics=OUT/'model_metrics_summary.csv'
    with metrics.open('x',newline='',encoding='utf-8') as fh:
        fields=['dataset','model_id','episodes','goal_completions','total_paid_observations','mean_paid_observations','mean_steps','mean_distance_m','unwanted_contacts']
        w=csv.DictWriter(fh,fieldnames=fields);w.writeheader()
        for dataset,group in [('h2_unseen',amodels),('fit72_known',bmodels)]:
            for arm,m in sorted(group.items()):
                n=m['episodes'];w.writerow({'dataset':dataset,'model_id':arm,'episodes':n,'goal_completions':m['goals'],
                    'total_paid_observations':m['observations'],'mean_paid_observations':m['observations']/n,
                    'mean_steps':m['steps']/n,'mean_distance_m':m['distance']/n,'unwanted_contacts':m['contacts']})
    # Three condition table: known FIT72 Original (this recovery), plus both
    # previously completed unseen-map conditions from the old 7,776-row table.
    old_metrics=list(csv.DictReader((ROOT/'results/phase2_mujoco/h2_comprehensive_benchmark_v1/combined_dataset/episode_metrics.csv').open()))
    byold=defaultdict(list)
    for r in old_metrics:byold[(r['condition'],r['model_id'])].append(r)
    comparepath=OUT/'three_condition_comparison.csv'
    with comparepath.open('x',newline='',encoding='utf-8') as fh:
        fields=['dataset_id','model_id','episodes','goal_completions','goal_rate','total_paid_observations','mean_paid_observations','mean_navigation_steps','mean_travel_distance_m','unwanted_contact_pairs','source_status']
        w=csv.DictWriter(fh,fieldnames=fields);w.writeheader()
        for condition,dataset_id in [('original','h2_unseen_original'),('high_frequency','h2_unseen_high_frequency')]:
            for arm in sorted({r['model_id'] for r in old_metrics}):
                group=byold[(condition,arm)]
                if len(group)!=72:raise RuntimeError(f'Prior {condition}/{arm} coverage is not 72')
                n=len(group);goals=sum(str(r['success']).lower() in ('true','1') for r in group)
                w.writerow({'dataset_id':dataset_id,'model_id':arm,'episodes':n,'goal_completions':goals,'goal_rate':goals/n,
                    'total_paid_observations':sum(int(r['paid_observations']) for r in group),
                    'mean_paid_observations':sum(int(r['paid_observations']) for r in group)/n,
                    'mean_navigation_steps':sum(int(r['elapsed_steps']) for r in group)/n,
                    'mean_travel_distance_m':sum(float(r['distance_m']) for r in group)/n,
                    'unwanted_contact_pairs':sum(int(r['unwanted_contact_pairs']) for r in group),
                    'source_status':'existing_H2_comprehensive_result'})
        for arm,m in sorted(bmodels.items()):
            n=m['episodes'];w.writerow({'dataset_id':'fit72_known_original','model_id':arm,'episodes':n,
                'goal_completions':m['goals'],'goal_rate':m['goals']/n,
                'total_paid_observations':m['observations'],'mean_paid_observations':m['observations']/n,
                'mean_navigation_steps':m['steps']/n,'mean_travel_distance_m':m['distance']/n,
                'unwanted_contact_pairs':m['contacts'],'source_status':'recovery_or_first_time_per_episode_index'})
    summary={'status':'COMPLETE','task_a':{'episodes':864,'parity':dict(aparity),'models':{k:{**v,'goal_rate':v['goals']/v['episodes']} for k,v in sorted(amodels.items())}},
        'task_b':{'episodes':3888,'parity':dict(bparity),'models':{k:{**v,'goal_rate':v['goals']/v['episodes']} for k,v in sorted(bmodels.items())}},
        'excluded_blocked_models':['c_route3','c_routek','c_topology3c'],
        'existing_complete_before_after_spatial_memory_replays':json.loads((OUT/'task_b_historical_index_summary.json').read_text()).get('complete_before_after_memory_records',0),
        'task_b_case_classification':'Per-episode prior-result paths and exact comparison statuses are in replay_index.csv; FIRST_TIME_FIT72_EVALUATION is not described as reproduction.',
        'active_binding':{'path':active_path.name,'sha256':sha(active_path)},'preservation_gate':protected,
        'historical_h2_manifests_verified':initial['historical_manifests_verified']}
    summarypath=OUT/'summary.json';summarypath.write_text(json.dumps(summary,sort_keys=True,indent=2)+'\n')
    episode_metrics_path=OUT/'episode_metrics.csv'
    with episode_metrics_path.open('x',newline='',encoding='utf-8') as fh:
        fields=['dataset_id','condition','model_id','map_identity','schedule','seed','frames','elapsed_steps','goal_step','success','paid_observations','distance_m','unwanted_contact_pairs','parity_status','replay_path','replay_sha256']
        w=csv.DictWriter(fh,fieldnames=fields);w.writeheader()
        for x in index:w.writerow({'dataset_id':'fit72_known_original' if x['dataset']=='fit72_known' else 'h2_unseen_original',
            'condition':x['condition'],'model_id':x['model_id'],'map_identity':x['map_identity'],'schedule':x['schedule'],'seed':x['seed'],
            'frames':x['frames'],'elapsed_steps':x['steps'],'goal_step':x['goal_step'],'success':x['success'],
            'paid_observations':x['paid_observations'],'distance_m':x['distance_m'],'unwanted_contact_pairs':x['unwanted_contact_pairs'],
            'parity_status':x['parity_status'],'replay_path':x['path'],'replay_sha256':x['sha256']})
    model_rows=list(csv.DictReader(metrics.open(encoding='utf-8')))
    for name,rows in [('model_summary.csv',model_rows),('fit72_model_summary.csv',[r for r in model_rows if r['dataset']=='fit72_known'])]:
        with (OUT/name).open('x',newline='',encoding='utf-8') as fh:
            fields=list(rows[0]) if rows else ['dataset','model_id','episodes'];w=csv.DictWriter(fh,fieldnames=fields);w.writeheader();w.writerows(rows)
    def write_index_table(name,rows,fields):
        with (OUT/name).open('x',newline='',encoding='utf-8') as fh:
            w=csv.DictWriter(fh,fieldnames=fields);w.writeheader();w.writerows(rows)
    parity_rows=[{'dataset_id':'fit72_known_original' if x['dataset']=='fit72_known' else 'h2_unseen_original',
        'model_id':x['model_id'],'map_identity':x['map_identity'],'schedule':x['schedule'],'status':x['parity_status'],
        'historical_sources':json.dumps(x['historical_records'],sort_keys=True),'detail':x['parity_detail']} for x in index]
    pfields=['dataset_id','model_id','map_identity','schedule','status','historical_sources','detail']
    write_index_table('episode_parity.csv',parity_rows,pfields)
    step_rows=[{'dataset_id':'fit72_known_original' if x['dataset']=='fit72_known' else 'h2_unseen_original',
        'model_id':x['model_id'],'map_identity':x['map_identity'],'schedule':x['schedule'],
        'status':x['parity_status'],'active_steps':x['steps'],'detail':x['parity_detail']} for x in index]
    step_fields=['dataset_id','model_id','map_identity','schedule','status','active_steps','detail']
    write_index_table('step_parity_summary.csv',step_rows,step_fields)
    write_index_table('parity_mismatches.csv',[r for r in step_rows if r['status']=='MISMATCH'],step_fields)
    write_index_table('newly_evaluated_cases.csv',[r for r in step_rows if r['status']=='FIRST_TIME_FIT72_EVALUATION'],step_fields)
    coverage_rows=[]
    for key,n in sorted(Counter((x['dataset'],x['model_id']) for x in index).items()):
        dataset_id='fit72_known_original' if key[0]=='fit72_known' else 'h2_unseen_original'
        coverage_rows.append({'dataset_id':dataset_id,'model_id':key[1],'expected_cases':72,'replay_cases':n,'full_spatial_memory_cases':n})
    write_index_table('replay_coverage.csv',coverage_rows,['dataset_id','model_id','expected_cases','replay_cases','full_spatial_memory_cases'])
    validation={'status':'PASS','episodes':len(index),'full_memory_frames':sum(x['frames'] for x in index),
        'every_episode_sha_journal_verified':True,'every_episode_has_s0_and_terminal_frame':True,
        'all_full_memory_grids_are_valid_25x25_ternary':True,'observation_budget_preserved':True,
        'task_a_exact_parity':dict(aparity),'task_b_parity':dict(bparity),'preservation_gate':protected}
    (OUT/'replay_validation_summary.json').write_text(json.dumps(validation,sort_keys=True,indent=2)+'\n')
    report=['# H2 Full Spatial Memory Replay Recovery v1','',
      'This is a descriptive recovery/replay evaluation. Controllers and frozen navigation conditions were not changed.', '',
      '## Task A — unseen H2 maps','',
      '864/864 episodes have exact step-trace and metric-signature parity with the saved H2 final Original results. All 12 models match the frozen expected goal and paid-observation totals; see `model_metrics_summary.csv`.','',
      '## Task B — known FIT72 maps','',
      '3,888/3,888 Original-condition episode replays are present. Each indexed episode records whether a historical FIT72 trace was found and the result of direct parity comparison. A first-time FIT72 run is labeled distinctly from exact reproduction. Three gate-blocked arms were excluded.','',
      '## Data completeness','',
      'Each replay has s0 plus every active step, full ternary memory, observation-before/update/after state, observed cells, serialized controller state, environment events, robot pose/heading, pedestrians, ground truth, selected/executed action, safety evidence and outcome. Validation checks frame sequence, memory encoding, observation cap, journal hashes and outcome consistency.','',
      '## Integrity','',
      f'- Active source binding: `{active_path.name}` (SHA-256 `{sha(active_path)}`).',
      f'- Protected Phase 1.5 gate: `{protected.get("status")}`.',
      f'- Historical H2 manifest entries verified: {initial["historical_manifests_verified"]}.',
      '- Historical results and blocked research gates were not modified or bypassed.','',
      'See `historical_replay_audit.csv`, `replay_index.csv`, `summary.json`, and the append-only validation attempt records for details.']
    (OUT/'final_report.md').write_text('\n'.join(report)+'\n')
    completion={'status':'COMPLETE','binding_sha256':sha(active_path),'task_a_episodes':864,'task_b_episodes':3888,
        'replay_index_sha256':sha(idxpath),'summary_sha256':sha(summarypath),'validated':True}
    (OUT/'completion_record.json').write_text(json.dumps(completion,sort_keys=True,indent=2)+'\n')
    entries=[]
    for p in sorted(OUT.rglob('*')):
        if p.is_file() and p.name!='artifact_manifest.json':entries.append({'path':p.relative_to(OUT).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)})
    manifest={'schema':'h2_full_spatial_memory_replay_manifest_v1','files':entries}
    (OUT/'artifact_manifest.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
    print(json.dumps({'status':'COMPLETE','task_a_parity':dict(aparity),'task_b_parity':dict(bparity),
        'task_b_models':len(bmodels),'combined_index_entries':len(combined['entries']),'manifest_entries':len(entries),'output':OUT.relative_to(ROOT).as_posix()},indent=2))

if __name__=='__main__':finalize()
