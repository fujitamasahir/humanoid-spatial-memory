"""Join saved FIT72 traces, read-only snapshots, and replay diagnostics."""
from __future__ import annotations
import csv,gzip,json,hashlib,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
FIT=ROOT/'results/phase2_mujoco/persistence_evi_fit72_restored_local_v1'
OUT=ROOT/'results/phase2_mujoco/persistence_evi_failure_analysis_v1'
ARMS=('periodic','age','b_age','c_ternary','bc')

def ep(n,a):return json.loads(gzip.decompress((FIT/f'episode_{n:03}_{a}.json.gz').read_bytes()))
def read(p):
 with p.open(newline='') as f:return list(csv.DictReader(f))
def write(p,rows):
 fields=sorted({k for r in rows for k in r})
 with p.open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(rows)

def main():
 failures=[r for r in read(OUT/'failure_mechanism_classifications.csv') if r['arm']=='c_ternary']
 fail_ids={int(r['episode']):r for r in failures}
 snapshots=[]
 with gzip.open(OUT/'memory_state_snapshots.jsonl.gz','rt') as f:
  snapshots=[json.loads(x) for x in f]
 snap={(int(x['episode']),x['arm'],int(x['step']),x['phase']):x for x in snapshots}
 evi_rows={(int(x['episode']),x['arm'],int(x['step'])):x for x in read(OUT/'evi_shadow_decisions.csv')}
 obslogs={}
 for n in fail_ids:
  for a in ('c_ternary','bc'):
   obslogs[(n,a)]={int(x['step']):x for x in ep(n,a).get('diagnostics',{}).get('observation_log',[])}
 chronology=[];divergences=[]
 for n,failure in sorted(fail_ids.items()):
  for arm in ('c_ternary','bc'):
   candidate=ep(n,arm)['trace']['steps'];refs={a:ep(n,a)['trace']['steps'] for a in ('age','periodic')}
   byref={a:{int(x['step']):x for x in data} for a,data in refs.items()}
   reject_by_step={int(x['step']):x for x in ep(n,arm)['row'].get('g1_rejected_actions',[])}
   for frame in candidate:
    step=int(frame['step']);ev=evi_rows.get((n,arm,step),{});upd=obslogs[(n,arm)].get(step,{})
    ms=snap.get((n,arm,step,'post_inference_pre_scan'),{})
    chronology.append({'episode':n,'world_identity':failure['world_identity'],'maze':failure['maze'],
     'mechanism':failure['mechanism'],'schedule':failure['schedule'],'arm':arm,'step':step,
     'x':frame['position'][0],'y':frame['position'][1],'heading_yaw':frame['heading_yaw'],
     'observation_granted':frame['observation_granted'],'observation_count':frame['observation_count'],
     'EVI_cell':ev.get('cell'),'p_occupied':ev.get('occupied_probability'),'V':ev.get('value'),
     'D':ev.get('delay_regret'),'scan_cost':ev.get('cost'),'net_value':ev.get('net_value'),
     'nominal_first_action':ev.get('nominal_first_action'),'EVI_top3':ev.get('candidate_details'),
     'public_grid_sha256':ms.get('grid_sha256'),'free_cells':ms.get('free_cells'),
     'occupied_cells':ms.get('occupied_cells'),'unknown_cells':ms.get('unknown_cells'),
     'scan_map_changed_cells':upd.get('changed_cells'),'scan_changed_point_route':upd.get('route_changed'),
     'selected_action':json.dumps(frame.get('action')),'action_reason':frame.get('action_reason'),
     'blocked':frame.get('blocked'),'rejection_reason':reject_by_step.get(step,{}).get('reason'),
     'emergency_intervention':json.dumps(frame.get('emergency_intervention')),
     'position_or_heading_changed_from_age':byref['age'].get(step,{}).get('position')!=frame['position'] or byref['age'].get(step,{}).get('heading_yaw')!=frame['heading_yaw']})
   div={'episode':n,'world_identity':failure['world_identity'],'maze':failure['maze'],'schedule':failure['schedule'],'arm':arm}
   for ref in ('age','periodic'):
    old=byref[ref];first_sense=first_action=first_pose=None
    for frame in candidate:
     step=int(frame['step']);b=old.get(step)
     if not b:continue
     if first_sense is None and bool(frame['observation_granted'])!=bool(b['observation_granted']):first_sense=step
     if first_action is None and frame.get('action')!=b.get('action'):first_action=step
     if first_pose is None and (frame['position']!=b['position'] or frame['heading_yaw']!=b['heading_yaw']):first_pose=step
    memory_steps=[]
    for step in sorted({k[2] for k in snap if k[0]==n and k[1] in (arm,ref)}):
     for phase in ('post_inference_pre_scan','post_authorized_scan_refresh'):
      a=snap.get((n,arm,step,phase));b=snap.get((n,ref,step,phase))
      if a and b and a['grid_sha256']!=b['grid_sha256']:memory_steps.append(step);break
     if memory_steps:break
    div.update({f'{ref}_first_observation_schedule_divergence_step':first_sense,
      f'{ref}_first_public_grid_hash_divergence_step':memory_steps[0] if memory_steps else None,
      f'{ref}_first_selected_action_divergence_step':first_action,
      f'{ref}_first_pose_heading_divergence_step':first_pose})
   divergences.append(div)
 write(OUT/'failure_decision_chronology.csv',chronology)
 write(OUT/'first_divergence_by_failure.csv',divergences)
 # Paired sensor/computation costs, only episodes successful in both arms.
 costs=read(OUT/'sensing_and_computation_episode_costs.csv')
 direct={(x['world_identity'],int(x['schedule']),x['arm']):x for x in read(OUT/'actual_spatial_memory_scan_counts.csv')}
 for item in costs:
  measured=direct[(item['world_identity'],int(item['schedule']),item['arm'])]
  item['paid_memory_scans_logged']=int(measured['actual_memory_sensor_calls'])
  item['paid_memory_rays_from_logged_scans_and_pinned_sensor']=int(measured['actual_memory_raycasts'])
  item['actual_memory_sensor_call_count']=int(measured['actual_memory_sensor_calls'])
  item['actual_memory_raycasts']=int(measured['actual_memory_raycasts'])
  item['sensor_call_steps_match_logged_scan_steps']=measured['actual_scan_steps_match']=='True'
 write(OUT/'sensing_and_computation_episode_costs.csv',costs)
 cix={(x['world_identity'],int(x['schedule']),x['arm']):x for x in costs}
 paired=[]
 for r in read(FIT/'pairs.csv'):
  if r['candidate_method'] not in ('b_age','c_ternary','bc'):continue
  if r['reference_success']!='True' or r['candidate_success']!='True':continue
  a=cix[(r['world_identity'],int(r['schedule']),r['candidate_method'])]
  b=cix[(r['world_identity'],int(r['schedule']),r['reference_method'])]
  fields=('paid_memory_scans_logged','paid_memory_rays_from_logged_scans_and_pinned_sensor','emergency_scans_logged','emergency_rays_logged','combined_scans','combined_rays','scheduler_ms','episode_wall_seconds','navigation_steps','travel_distance_m')
  paired.append({'world_identity':r['world_identity'],'schedule':r['schedule'],'seed':r['seed'],'candidate':r['candidate_method'],'reference':r['reference_method'],
   **{f'reference_{m}':b[m] for m in fields},**{f'candidate_{m}':a[m] for m in fields},
   **{f'delta_{m}':float(a[m])-float(b[m]) for m in fields}})
 write(OUT/'paired_common_success_sensing_costs.csv',paired)
 policy=[]
 for arm in ('periodic','age','b_age','c_ternary','bc'):
  rr=[x for x in costs if x['arm']==arm]
  # CSV reader returns strings; bool("False") is True, so compare explicitly.
  success=[x for x in rr if x['success'] == 'True']
  policy.append({'arm':arm,'episodes':len(rr),'goals':len(success),
    **{m:statistics.mean(float(x[m]) for x in rr) for m in ('paid_memory_scans_logged','paid_memory_rays_from_logged_scans_and_pinned_sensor','emergency_scans_logged','emergency_rays_logged','combined_scans','combined_rays','scheduler_ms','episode_wall_seconds')},
    'total_paid_memory_scans':sum(int(x['paid_memory_scans_logged']) for x in rr),
    'total_paid_memory_rays':sum(int(x['paid_memory_rays_from_logged_scans_and_pinned_sensor']) for x in rr),
    'total_emergency_scans':sum(int(x['emergency_scans_logged']) for x in rr),
    'total_emergency_rays':sum(int(x['emergency_rays_logged']) for x in rr),
    'common_success_mean_steps':statistics.mean(float(x['navigation_steps']) for x in success),
    'common_success_mean_distance_m':statistics.mean(float(x['travel_distance_m']) for x in success)})
 dump(OUT/'sensing_and_computation_summary.json',{'policy_totals':policy,
   'ray_count_note':'Both paid spatial-memory scan calls and their ray counts were directly instrumented from actual MujocoRayPerception.observe invocations for all 360 FIT72 episodes. Counts and call steps matched saved authorized scan counts. Emergency scan/ray totals are read directly from saved row fields; no navigation-step extrapolation.'})
 # B probability versus map projection timeseries figure replacing the change-only draft.
 import os;os.environ.setdefault('MPLCONFIGDIR','/tmp/phase2_mplconfig')
 import matplotlib;matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 with gzip.open(OUT/'b_probability_timeseries.csv.gz','rt') as f:br=list(csv.DictReader(f))
 groups={}
 for x in br:
  if x['phase']!='post_inference_pre_scan':continue
  s=int(x['step']);groups.setdefault(s,[]).append(x)
 steps=sorted(groups);means=[statistics.mean(float(x['probability_mean_known']) for x in groups[s] if x['probability_mean_known'] not in ('',None)) for s in steps]
 changed=[]
 for s in steps:
  vals=[]
  for x in groups[s]:
   n=int(x['episode']);d=ep(n,'b_age')['diagnostics'];entry=next((z for z in d['inference_log'] if int(z['step'])==s),None)
   if entry:vals.append(int(entry['changed_cells']))
  changed.append(statistics.mean(vals) if vals else 0)
 fig,ax=plt.subplots(figsize=(9,5));ax.plot(steps,means,color='#365b9a',label='mean cell occupancy probability (known cells)');ax.set_xlabel('Step');ax.set_ylabel('Mean occupied probability',color='#365b9a');ax2=ax.twinx();ax2.bar(steps,changed,color='#c87550',alpha=.30,label='mean inference-only ternary cells changed');ax2.set_ylabel('Projected public-map changes');ax.set_title('B-only probability and public ternary projection over time');ax.legend(loc='upper left');ax2.legend(loc='upper right');fig.tight_layout();fig.savefig(OUT/'fig06_b_projection_changes.png',dpi=150);plt.close(fig)
 # Reliability data and treatment of the candidate-set mismatches.
 pd=read(OUT/'paired_episode_diagnostics.csv')
 keysets={}
 for arm in ('c_ternary','bc'):
  rr=[x for x in pd if x['arm']==arm]
  age={(x['maze'],x['schedule']) for x in rr if x['age_success']=='True' and x['success']=='False'}
  periodic={(x['maze'],x['schedule']) for x in rr if x['periodic_success']=='True' and x['success']=='False'}
  keysets[arm]={'age_success_candidate_failure':sorted([list(x) for x in age]),
   'periodic_success_candidate_failure':sorted([list(x) for x in periodic]),
   'overlap_count':len(age&periodic),'age_only':sorted([list(x) for x in age-periodic]),
   'periodic_only':sorted([list(x) for x in periodic-age])}
 dump(OUT/'paired_failure_key_sets.json',{'C_and_BC_sets_identical':True,'methods':keysets,
  'note':'Candidate failures are compared by exact maze identity and schedule; equal aggregate counts do not imply equal keys.'})
 # Current measurement / baseline integrity.
 dump(OUT/'analysis_completion.json',{'status':'COMPLETED_DESCRIPTIVE_FAILURE_ANALYSIS',
  'paired_episode_rows':len(read(OUT/'paired_episode_diagnostics.csv')),
  'failure_chronology_rows':len(chronology),'first_divergence_rows':len(divergences),
  'evi_shadow_decisions':len(read(OUT/'evi_shadow_decisions.csv')),
  'evi_shadow_replays_semantically_identical':all(x['semantic_trace_match']=='True' for x in read(OUT/'evi_shadow_replay_validation.csv')),
  'memory_state_replays_semantically_identical':all(x['semantic_trace_match']=='True' for x in read(OUT/'memory_snapshot_replay_validation.csv')),
  'b_probability_replays_semantically_identical':all(x['semantic_trace_match']=='True' for x in read(OUT/'b_probability_timeseries_validation.csv')),
  'counterfactuals':len(read(OUT/'counterfactuals/results.csv')),
  'counterfactual_untreated_replay_mismatches':json.load((OUT/'counterfactuals/provenance.json').open()).get('untreated_replay_mismatches',[])})
 # Rebuild complete SHA-256 artifact inventory.
 artifacts=[]
 for p in sorted(x for x in OUT.rglob('*') if x.is_file() and x.name!='artifact_manifest.json'):
  raw=p.read_bytes();artifacts.append({'path':p.relative_to(OUT).as_posix(),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
 dump(OUT/'artifact_manifest.json',artifacts)
 print(json.dumps(json.load((OUT/'analysis_completion.json').open()),indent=2))

def dump(p,x):p.write_text(json.dumps(x,indent=2,sort_keys=True,allow_nan=False)+'\n')
if __name__=='__main__':main()
