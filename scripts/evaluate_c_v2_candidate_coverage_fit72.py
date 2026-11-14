"""One-shot descriptive candidate-selection screen on existing FIT72 only.

The protocol's synthetic rejection gate must pass before execution. This script
never generates worlds and refuses output overwrite. It is intentionally not
invoked by the current task because frozen C-Route3 failed that gate.
"""
from __future__ import annotations
import argparse,csv,gzip,hashlib,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
import evaluate_persistence_evi_fit72 as runner
import evaluate_event_observation_fit72 as references
from spatial_memory.mujoco_perception import MujocoRayPerception

FIT=ROOT/'results/phase2_mujoco/persistence_evi_fit72_restored_local_v1'
INTEGRITY=ROOT/'results/phase2_mujoco/persistence_evi_fit72_analysis_restored_local_v2/integrity_verification.json'
ARMS=('c0_audit','c_k','c_route3','c_routek','c_topology3')
LABEL={'c0_audit':'C0','c_k':'C-K','c_route3':'C-Route3','c_routek':'C-RouteK','c_topology3':'C-Topology3'}
DEFAULT_ARMS=('c0_audit','c_k','c_route3','c_topology3')

def read_accepted_gate(path):
    """Read a numeric gate and honor any post-run conformance review."""
    document=json.loads(path.read_text())
    status=document.get('mechanism_gate',{}).get('status')
    review_path=path.parent/'gate_review.json'
    review_required='c_v2b_topology_protocol' in str(document.get('protocol',''))
    if review_required and not review_path.is_file():
        raise RuntimeError('C v2b FIT evaluation requires a passing gate_review.json')
    if review_path.is_file():
        review=json.loads(review_path.read_text())
        if review.get('status')!='ACCEPTED_FOR_FIT':
            raise RuntimeError(f"Post-run gate review blocks FIT72: {review.get('status')}")
    return status

def run_measured(payload,schedule,arm,config):
    original=MujocoRayPerception.observe;calls=[]
    def observe(self,world,position,yaw):
        result=original(self,world,position,yaw)
        if self.ray_count==61 and abs(self.horizontal_fov_deg-120.)<1e-9 and abs(self.range_m-6.)<1e-9:
            calls.append(int(world.step))
        return result
    MujocoRayPerception.observe=observe
    try: row,trace,diag=runner.run_arm(payload,schedule,arm,config)
    finally:MujocoRayPerception.observe=original
    expected=[int(x['step']) for x in trace['steps'] if x['observation_granted']]
    if calls!=expected or len(calls)!=int(row['observation_count']):
        raise RuntimeError(f'Actual memory sensor calls disagree with saved trace for {arm}')
    diag['actual_memory_sensor_calls']=len(calls)
    diag['actual_memory_raycasts']=61*len(calls)
    diag['actual_memory_call_steps']=calls
    if int(row['g1_unselected_action_shield_queries'])!=0 or int(row['observation_count'])>20:
        raise RuntimeError('Shield/budget invariant failed')
    return row,trace,diag

def episode_read(n,arm):
    return json.loads(gzip.decompress((FIT/f'episode_{n:03}_{arm}.json.gz').read_bytes()))

def make_summary(records, arms=ARMS):
    result={}
    for arm in ('periodic','age',*arms):
        a=[x for x in records if x['arm']==arm]
        result[arm]={'label':LABEL.get(arm,arm),'episodes':len(a),
          'goals':sum(bool(x['success']) for x in a),
          'unwanted_contact_episodes':sum(int(x['unwanted_contacts'])>0 for x in a),
          'paid_memory_scans':sum(int(x['paid_memory_scans']) for x in a),
          'paid_memory_rays':sum(int(x['actual_memory_raycasts']) for x in a),
          'emergency_scans':sum(int(x['emergency_safety_scans']) for x in a),
          'emergency_rays':sum(int(x['emergency_safety_raycasts']) for x in a),
          'combined_rays':sum(int(x['actual_memory_raycasts'])+int(x['emergency_safety_raycasts']) for x in a),
          'h80_censored_steps':sum(int(x['elapsed_steps']) for x in a),
          'blocked_attempts':sum(int(x['blocked_attempts']) for x in a),
          'emergency_interventions':sum(int(x['emergency_safety_interventions']) for x in a),
          'false_persistent_occupancy_updates':sum(int(x['false_persistent_occupancy_updates']) for x in a),
          'missed_persistent_changes':sum(int(x['missed_persistent_changes']) for x in a),
          'scheduler_ms_mean':sum(float(x['scheduler_ms']) for x in a)/len(a),
          'episode_wall_seconds_mean':sum(float(x['episode_wall_time_seconds']) for x in a)/len(a)}
    return result

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,default=ROOT/'results/phase2_mujoco/c_v2b_topology_v1/fit72_descriptive_screen')
    ap.add_argument('--gate',type=Path,default=ROOT/'results/phase2_mujoco/c_v2_candidate_coverage_v1/synthetic_fixture_frozen_v7/synthetic_fixture_results.json')
    ap.add_argument('--protocol',type=Path,default=ROOT/'docs/phase2_c_v2_candidate_coverage_protocol.md')
    ap.add_argument('--arms',nargs='+',choices=ARMS,default=list(DEFAULT_ARMS))
    args=ap.parse_args()
    gate_path=args.gate if args.gate.is_absolute() else ROOT/args.gate
    if not gate_path.is_file():raise RuntimeError('Frozen synthetic gate missing; refusing FIT72 access')
    gate_status=read_accepted_gate(gate_path)
    if gate_status!='PASS':
        raise RuntimeError(f"Pre-FIT synthetic mechanism gate is {gate_status}; FIT72 evaluation is blocked")
    if not args.output.is_absolute():args.output=ROOT/args.output
    verify_original_data_integrity()
    if args.output.exists():raise FileExistsError(f'Refusing to overwrite: {args.output}')
    meta=runner.source_metadata()
    if meta['branch']!='phase2/mujoco-proxy-pilot':raise RuntimeError('Wrong branch')
    _,_,prov,_=references.base.load_baseline();config=references.base.frozen_config(prov)
    baseline_rows=references._load_csv(references.BASE/'episodes.csv')
    base_idx={(r['world_identity'],int(r['schedule']),r['method'],int(r['seed'])):r for r in baseline_rows}
    hist_index={};saved_traces={}
    with gzip.open(references.BASE/'episode_traces.jsonl.gz','rt') as f:
        saved_traces={tuple(x['key']):x for x in map(json.loads,f)}
    worlds={x['identity']:x for x in references.navigation.admitted_worlds()}
    keys=sorted((r['world_identity'],int(r['schedule']),r['method'],int(r['seed']))
                for r in baseline_rows if r['method']=='age')
    if len(keys)!=72 or len(worlds)!=36:raise RuntimeError('FIT72 evidence incomplete')
    prefix=references.navigation.verify_preserved_prefix()
    protected={str(p.relative_to(ROOT)):references._sha(p) for p in references.PROTECTED}
    args.output.mkdir(parents=True,exist_ok=False)
    (args.output/'provenance.json').write_text(json.dumps({'status':'DESCRIPTIVE_FIT_NOT_VALIDATION',
      'protocol':str(args.protocol),'gate':str(gate_path.relative_to(ROOT)),'source':meta,
      'config':config,'fit_store':'read-only existing admitted FIT72','preserved_prefix':prefix,
      'protected_sha256':protected,'independent_validation':False},indent=2,sort_keys=True)+'\n')
    allrows=[];pairs=[];source_num={tuple(json.loads(gzip.decompress((FIT/f'episode_{n:03}_age.json.gz').read_bytes()))['trace']['key']):n for n in range(1,73)}
    for ix,key in enumerate(keys,1):
      world_id,schedule,method,seed=key;n=source_num.get((world_id,schedule,'age',seed))
      if n is None:raise RuntimeError(f'No stored episode number for {key}')
      payload=worlds[world_id];refs={}
      for method in ('periodic','age'):
        row,trace,diag=run_measured(payload,int(schedule),method,config)
        baseline=base_idx[(world_id,int(schedule),method,int(seed))]
        if references.rdao_evaluator._signature(row)!=references.rdao_evaluator._signature(baseline):
            raise RuntimeError(f'{method} metrics failed frozen reproduction: {key}')
        references._compare_trace(saved_traces[key],references.base._jsonable_row(trace))
        refs[method]=row
        save_episode(args.output,ix,method,row,trace,{'actual_memory_sensor_calls':diag['actual_memory_sensor_calls']})
        allrows.append(flat(method,row,diag))
      original_c=episode_read(n,'c_ternary')
      for arm in args.arms:
        row,trace,diag=run_measured(payload,int(schedule),arm,config)
        if arm=='c0_audit':
            if references.rdao_evaluator._signature(row)!=references.rdao_evaluator._signature(original_c['row']):
                raise RuntimeError(f'C0 metrics mismatch: {key}')
            runner.reference.base._compare_trace(original_c['trace'],runner.reference.base._jsonable_row(trace))
        save_episode(args.output,ix,LABEL[arm],row,trace,diag)
        flatrow=flat(arm,row,diag);allrows.append(flatrow)
        for method in ('periodic','age'):
            pairs.append(runner.pair_row(key,method,LABEL[arm],refs[method],row,diag))
      print(f'Completed {ix}/72 keys: {world_id} schedule={schedule}',flush=True)
    csv_write(args.output/'episodes.csv',allrows);csv_write(args.output/'paired.csv',pairs)
    summary=make_summary(allrows,args.arms)
    summary['baseline_reproduction_passed']=True;summary['C0_exact_saved_replay_passed']=True
    summary['paired_by_method']={a:{m:runner.summarize_pairs([r for r in pairs if r['candidate_method']==LABEL[a] and r['reference_method']==m]) for m in ('periodic','age')} for a in args.arms}
    summary['correlated_schedule_policy']='maze identity is paired cluster; two schedules are not independent'
    summary['status']='COMPLETED_DESCRIPTIVE_ENGINEERING_SCREEN_NOT_VALIDATION'
    (args.output/'summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True,allow_nan=False)+'\n')
    if references.navigation.verify_preserved_prefix()!=prefix or protected!={str(p.relative_to(ROOT)):references._sha(p) for p in references.PROTECTED}:
        raise RuntimeError('Protected evidence changed')
    inventory=[]
    for p in sorted(x for x in args.output.rglob('*') if x.is_file() and x.name!='artifact_manifest.json'):
        b=p.read_bytes();inventory.append({'path':p.relative_to(args.output).as_posix(),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()})
    (args.output/'artifact_manifest.json').write_text(json.dumps(inventory,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':summary['status'],'output':str(args.output),'episodes':len(allrows),'paired_rows':len(pairs)},indent=2))

def verify_original_data_integrity():
    """Read-only recheck of previously audited FIT stores and artifacts."""
    audit=json.loads(INTEGRITY.read_text())
    if audit['status']!='PASS_READ_ONLY_FIT72_INTEGRITY':raise RuntimeError('Prior FIT integrity audit missing/failing')
    prefix=references.navigation.verify_preserved_prefix()
    if prefix!=audit['phase15_preserved_prefix'] or prefix['files_checked']!=836:
        raise RuntimeError('Protected Phase 1.5 prefix changed')
    def digest(raw):return hashlib.sha256(raw).hexdigest()
    for store in audit['stores']:
        root=ROOT/store['path'];files=[]
        for p in sorted((root/'records').glob('*.json.gz'))+sorted((root/'recovered').glob('attempt-*.json')):
            b=p.read_bytes();files.append({'path':p.relative_to(root).as_posix(),'bytes':len(b),'sha256':digest(b)})
        b=(root/'run.json').read_bytes();files.append({'path':'run.json','bytes':len(b),'sha256':digest(b)})
        files.sort(key=lambda x:x['path'])
        inv=digest(json.dumps(files,sort_keys=True,separators=(',',':')).encode())
        if inv!=store['inventory_sha256'] or len(list((root/'records').glob('*.json.gz')))!=store['records'] or len(list((root/'recovered').glob('attempt-*.json')))!=store['receipts']:
            raise RuntimeError(f"FIT raw store integrity mismatch: {store['path']}")
        if list((root/'staging').iterdir()):raise RuntimeError(f"FIT staging not empty: {store['path']}")
    for item in json.loads((FIT/'artifact_manifest.json').read_text()):
        b=(FIT/item['path']).read_bytes()
        if len(b)!=item['bytes'] or digest(b)!=item['sha256']:raise RuntimeError(f"FIT72 artifact mismatch: {item['path']}")
    return audit

def save_episode(out,n,arm,row,trace,diag):
    with gzip.open(out/f'episode_{n:03}_{arm}.json.gz','xt') as f:
        json.dump(references.base._jsonable_row({'row':row,'trace':trace,'diagnostics':diag}),f,sort_keys=True,allow_nan=False)

def flat(arm,row,diag):
    decisions=diag.get('decisions',[]);calls=[int(x.get('plan_calls',0)) for x in decisions]
    selected=[c for x in decisions for c in x.get('shortlisted_candidates',[])]
    reasons={'D_zero':0,'E_action_agreement':0,'F_below_cost':0,'authorized':0,'budget_exhausted':0}
    for x in decisions:
        v=float(x.get('value') or 0);d=float(x.get('delay_regret') or 0);net=float(x.get('net_value') or 0)
        if int(x.get('used_before',0))>=20:reasons['budget_exhausted']+=1
        elif v<=1e-12:reasons['D_zero']+=1
        elif d<=1e-12:reasons['E_action_agreement']+=1
        elif net<=0:reasons['F_below_cost']+=1
        else:reasons['authorized']+=1
    return {'arm':arm,'success':bool(row['success']),'goal_step':row.get('goal_step'),
      'unwanted_contacts':int(row['g1_unwanted_contact_pairs']),'paid_memory_scans':int(row['observation_count']),
      'actual_memory_sensor_calls':int(diag.get('actual_memory_sensor_calls',row['observation_count'])),
      'actual_memory_raycasts':int(diag.get('actual_memory_raycasts',61*int(row['observation_count']))),
      'emergency_safety_scans':int(row['emergency_safety_scans']),'emergency_safety_raycasts':int(row['emergency_safety_raycasts']),
      'combined_rays':int(diag.get('actual_memory_raycasts',61*int(row['observation_count'])))+int(row['emergency_safety_raycasts']),
      'elapsed_steps':int(row['elapsed_steps']),'travel_distance_m':float(row['travel_distance_m']),
      'blocked_attempts':int(row['g1_footprint_blocked_attempts']),'emergency_safety_interventions':int(row['emergency_safety_interventions']),
      'false_persistent_occupancy_updates':int(row['false_persistent_occupancy_updates']),'missed_persistent_changes':int(row['missed_persistent_changes']),
      'scheduler_ms':float(diag.get('scheduler_total_ms',0.)),'episode_wall_time_seconds':float(row['episode_wall_time_seconds']),
      'mean_plan_calls':sum(calls)/len(calls) if calls else 0,'max_plan_calls':max(calls,default=0),
      'candidate_decisions':len(decisions),'selected_route_candidate_count':sum(bool(x.get('on_nominal_route')) for x in selected),
      'shortlist_cells_selected':len(selected),'mean_V':sum(float(x.get('value') or 0) for x in decisions)/len(decisions) if decisions else 0,
      'mean_D':sum(float(x.get('delay_regret') or 0) for x in decisions)/len(decisions) if decisions else 0,
      **{f'evi_{k}':v for k,v in reasons.items()}}

def csv_write(p,rows):
    fields=sorted({k for r in rows for k in r})
    with p.open('x',newline='') as f:
      w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(rows)

if __name__=='__main__':main()
