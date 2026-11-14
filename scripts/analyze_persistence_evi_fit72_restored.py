"""Compare restored FIT72 B/C arms with baselines and saved RDAO screens.

All input result directories are read-only. Analysis is written to a new output.
"""
from __future__ import annotations
import ast, csv, gzip, hashlib, json, random, statistics
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FIT=ROOT/'results/phase2_mujoco/persistence_evi_fit72_restored_local_v1'
OUT=ROOT/'results/phase2_mujoco/persistence_evi_fit72_analysis_restored_local_v2'
HISTORY={
 'rdao_v1':(ROOT/'results/phase2_mujoco/rdao_v1_phase2_evaluation','primary_episodes.csv','Initial RDAO v1'),
 'rdao_v1_footprint':(ROOT/'results/phase2_mujoco/rdao_v1_footprint_visibility_online_fit72_v1','paired_visibility_online.csv','RDAO v1 footprint-only follow-up'),
 'rdao_v2':(ROOT/'results/phase2_mujoco/rdao_v2_viewpoint_fit72_v1','paired_rdao_v2_viewpoint.csv','RDAO v2 viewpoint'),
 'rdao_v21':(ROOT/'results/phase2_mujoco/rdao_v21_current_view_quality_fit72_v1','paired_v21_vs_v1.csv','RDAO v2.1 current-view quality'),
 'rdao_v22':(ROOT/'results/phase2_mujoco/rdao_v22_decision_protected_fit72_v1','paired_v22_vs_v1.csv','RDAO v2.2 decision-protected'),
}
NEW=('periodic','age','b_age','c_ternary','bc')
METRICS=('success','observations','steps_h80','distance_m','false_persistent','missed_persistent',
         'emergency_interventions','unwanted_contacts','blocked_attempts','scheduler_ms','wall_ms')
LABELS={'periodic':'Periodic','age':'Age','b_age':'B only (Persistence + Age)',
 'c_ternary':'C only (EVI + Ternary Memory)','bc':'B+C (Persistence + EVI)'}
LABELS.update({k:v[2] for k,v in HISTORY.items()})

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def as_bool(v): return v if isinstance(v,bool) else str(v).lower()=='true'
def key(row): return str(row['world_identity']),int(row['schedule']),int(row['seed'])
def read_csv(p):
 with p.open(newline='',encoding='utf-8') as f:return list(csv.DictReader(f))
def normalize(row, historical=False, initial=False):
 if initial:
  fields={'success':'success','observations':'observation_count','steps_h80':'elapsed_steps',
   'distance_m':'travel_distance_m','false_persistent':'false_persistent_occupancy_updates',
   'missed_persistent':'missed_persistent_changes','emergency_interventions':'emergency_safety_interventions',
   'unwanted_contacts':'g1_unwanted_contact_pairs','blocked_attempts':'g1_footprint_blocked_attempts',
   'scheduler_ms':'rdao_scheduler_total_ms'}
 elif historical:
  fields={'success':'variant_success','observations':'variant_observations','steps_h80':'variant_elapsed_steps',
   'distance_m':'variant_travel_distance_m','emergency_interventions':'variant_emergency_interventions',
   'unwanted_contacts':'variant_unwanted_contacts','blocked_attempts':'variant_blocked_attempts',
   'scheduler_ms':'variant_scheduler_ms'}
  if 'candidate_success' in row:
   fields={'success':'candidate_success','observations':'candidate_observations','steps_h80':'candidate_steps_h80',
    'distance_m':'candidate_distance_m','emergency_interventions':'candidate_emergency_interventions',
    'unwanted_contacts':'candidate_unwanted_contacts','blocked_attempts':'candidate_blocked_attempts',
    'scheduler_ms':'candidate_scheduler_ms'}
 else:
  fields={'success':'success','observations':'observation_count','steps_h80':'elapsed_steps',
   'distance_m':'travel_distance_m','false_persistent':'false_persistent_occupancy_updates',
   'missed_persistent':'missed_persistent_changes','emergency_interventions':'emergency_safety_interventions',
   'unwanted_contacts':'g1_unwanted_contact_pairs','blocked_attempts':'g1_footprint_blocked_attempts',
   'scheduler_ms':'scheduler_total_ms'}
 result={}
 for metric,field in fields.items():
  val=row.get(field)
  result[metric]=None if val in (None,'') else int(as_bool(val)) if metric=='success' else float(val)
 if historical:
  result['false_persistent']=None;result['missed_persistent']=None;result['wall_ms']=None
 else:
  result['wall_ms']=float(row['episode_wall_time_seconds'])*1000 if row.get('episode_wall_time_seconds') else None
 return result

def load_new():
 data={m:{} for m in NEW}
 for p in sorted(FIT.glob('episode_*.json.gz')):
  entry=json.loads(gzip.decompress(p.read_bytes()));row=entry['row']
  m=p.name.split('_',2)[-1].removesuffix('.json.gz')
  if m in data:
   k=key(row)
   if k in data[m]:raise ValueError(f'duplicate {m} {k}')
   data[m][k]=normalize(row)
   if entry.get('diagnostics',{}).get('scheduler_total_ms') is not None:
    data[m][k]['scheduler_ms']=float(entry['diagnostics']['scheduler_total_ms'])
 target=set(data['periodic'])
 if len(target)!=72 or any(set(data[m])!=target for m in NEW):raise ValueError('New FIT72 keys incomplete or mismatched')
 return data,target

def load_history(target):
 data={};hashes={}
 for name,(directory,filename,_) in HISTORY.items():
  p=directory/filename;rows=read_csv(p);values={}
  for r in rows:
   if name=='rdao_v1':
    parsed=ast.literal_eval(r['episode_key']);k=(str(parsed[0]),int(parsed[1]),int(parsed[3]))
    v=normalize(r,initial=True)
   else:k=key(r);v=normalize(r,historical=True)
   if k in values:raise ValueError(f'duplicate history key {name} {k}')
   values[k]=v
  if set(values)!=target:raise ValueError(f'{name} keys differ: {len(values)}')
  data[name]=values
  hashes[p.relative_to(ROOT).as_posix()]=sha(p)
  sp=directory/'summary.json';hashes[sp.relative_to(ROOT).as_posix()]=sha(sp)
 return data,hashes

def avg(xs):
 v=[float(x) for x in xs if x is not None]
 return statistics.mean(v) if v else None
def summarize(rows):
 vals=list(rows.values());out={'episodes':len(vals),'goal_completions':sum(x['success'] or 0 for x in vals)}
 for m in METRICS:out['mean_'+m]=avg(r.get(m) for r in vals)
 for m in ('false_persistent','missed_persistent','emergency_interventions','unwanted_contacts','blocked_attempts'):
  out['total_'+m]=sum(r[m] or 0 for r in vals) if any(r[m] is not None for r in vals) else None
 out['episodes_with_unwanted_contacts']=sum((r['unwanted_contacts'] or 0)>0 for r in vals)
 out['contact_free_goal_completions']=sum(r['success']==1 and (r['unwanted_contacts'] or 0)==0 for r in vals)
 wins=[r for r in vals if r.get('success')==1]
 out['successes']=len(wins);out['success_mean_steps']=avg(r['steps_h80'] for r in wins)
 out['success_mean_distance_m']=avg(r['distance_m'] for r in wins)
 return out

def pair(ref_name,ref,cand_name,cand):
 rows=[]
 for k in sorted(ref):
  a,z=ref[k],cand[k]
  row={'world_identity':k[0],'schedule':k[1],'seed':k[2],
   'reference':ref_name,'candidate':cand_name,
   'reference_success':a.get('success'),'candidate_success':z.get('success'),
   'success_delta':z['success']-a['success'] if a.get('success') is not None and z.get('success') is not None else None,
   'rescued':int(a.get('success')==0 and z.get('success')==1),
   'harmed':int(a.get('success')==1 and z.get('success')==0)}
  for m in METRICS:
   if m!='success':row[m+'_delta']=z[m]-a[m] if a.get(m) is not None and z.get(m) is not None else None
  rows.append(row)
 return rows

def cluster_ci(rows,metric,draws=20000,seed=42):
 groups={}
 for r in rows:
  v=r.get(metric)
  if v is None:continue
  mechanism=r['world_identity'].rsplit(':',2)[-2]
  groups.setdefault(mechanism,{}).setdefault(r['world_identity'],[]).append(float(v))
 clusters={m:{w:statistics.mean(vs) for w,vs in worlds.items()} for m,worlds in groups.items()}
 if not clusters:return None
 observed=avg(v for ws in clusters.values() for v in ws.values());rng=random.Random(seed);boot=[]
 for _ in range(draws):
  sample=[]
  for _,worlds in sorted(clusters.items()):
   names=sorted(worlds);sample.extend(worlds[names[rng.randrange(len(names))]] for _ in names)
  boot.append(statistics.mean(sample))
 boot.sort()
 return {'paired_mean_delta':observed,'ci95_low':boot[int(.025*(draws-1))],
  'ci95_high':boot[int(.975*(draws-1))],'world_clusters':sum(map(len,clusters.values())),
  'bootstrap_draws':draws,'bootstrap_unit':'maze identity; two schedules averaged; stratified by R/BP/M'}

def write_csv(p,rows):
 if not rows:raise ValueError('empty analysis output '+str(p))
 fields=list(dict.fromkeys(k for r in rows for k in r))
 with p.open('x',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)

def main():
 if OUT.exists():raise FileExistsError(OUT)
 OUT.mkdir(parents=True)
 new,keys=load_new();history,hashes=load_history(keys);policies={**new,**history}
 summary_rows=[{'policy_id':name,'policy':LABELS[name],**summarize(rows)} for name,rows in policies.items()]
 write_csv(OUT/'policy_summary.csv',summary_rows)
 comps=[]
 for ref_name in ('periodic','age',*HISTORY):
  for cand_name in ('b_age','c_ternary','bc'):
   rows=pair(ref_name,policies[ref_name],cand_name,policies[cand_name])
   for metric in ('success_delta','observations_delta','steps_h80_delta','distance_m_delta',
    'false_persistent_delta','missed_persistent_delta','emergency_interventions_delta',
    'unwanted_contacts_delta','blocked_attempts_delta','scheduler_ms_delta','wall_ms_delta'):
    ci=cluster_ci(rows,metric)
    if ci is not None:
     comps.append({'reference':ref_name,'candidate':cand_name,'metric':metric,**ci,
       'rescued_episodes':sum(r['rescued'] for r in rows),'harmed_episodes':sum(r['harmed'] for r in rows)})
 write_csv(OUT/'paired_cluster_comparisons.csv',comps)
 entries=json.loads((FIT/'artifact_manifest.json').read_text())
 for e in entries:
  p=FIT/e['path']
  if p.stat().st_size!=e['bytes'] or sha(p)!=e['sha256']:raise ValueError('FIT artifact hash mismatch: '+e['path'])
 hashes['results/phase2_mujoco/persistence_evi_fit72_restored_local_v1/artifact_manifest.json']=sha(FIT/'artifact_manifest.json')
 provenance={'analysis':'descriptive FIT72 B/C versus Periodic/Age and historical RDAO',
  'fit_result_dir':FIT.relative_to(ROOT).as_posix(),'fit_summary_sha256':sha(FIT/'summary.json'),
  'fit_artifact_files_verified':len(entries),'input_sha256':hashes,'episode_keys_per_policy':len(keys),
  'maze_clusters':36,'bootstrap':'20,000 stratified cluster draws, seed 42; no multiplicity correction',
  'historical_memory_error_metrics':'Unavailable in most historical RDAO pair files; not inferred.',
  'policy_or_hyperparameter_changes':False}
 (OUT/'analysis_manifest.json').write_text(json.dumps(provenance,indent=2,sort_keys=True)+'\n')
 report=['# FIT72 B/C and historical RDAO comparisons','',
  'Descriptive development evaluation only. All methods use the same 72 FIT keys (36 mazes × two correlated schedules, seed 42). Historical RDAO values were reused; no historical run was rerun or changed.','',
  'The five-arm runner reproduced every saved Periodic/Age metric row and semantic trace before running B/C. All 72 paired keys completed.','',
  '## Policy-level results','',
  'Mean H80 steps and distance include every episode; failures contribute their 80-step censored horizon and partial path. The final columns give means among successful episodes only. All successful episodes were contact-free in this cohort.',
  '', '| Policy | Goals/contact-free | Mean observations | Mean H80 steps | Mean distance m | False persistence total | Missed changes total | Safety interventions | Unwanted contact pairs | Blocked attempts | Scheduler ms/episode | Wall ms/episode | Successful mean steps | Successful mean distance m |',
  '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
 def fmt(v): return 'n/a' if v is None else f'{v:.2f}'
 for r in summary_rows:
  report.append(f"| {r['policy']} | {r['goal_completions']}/{r['contact_free_goal_completions']} | {fmt(r['mean_observations'])} | {fmt(r['mean_steps_h80'])} | {fmt(r['mean_distance_m'])} | {fmt(r['total_false_persistent'])} | {fmt(r['total_missed_persistent'])} | {fmt(r['total_emergency_interventions'])} | {fmt(r['total_unwanted_contacts'])} | {fmt(r['total_blocked_attempts'])} | {fmt(r['mean_scheduler_ms'])} | {fmt(r['mean_wall_ms'])} | {fmt(r['success_mean_steps'])} | {fmt(r['success_mean_distance_m'])} |")
 report += ['', '## Paired outcomes against Periodic and Age', '',
  'Success deltas show rescued/harmed episode pairs. The 95% intervals resample 36 maze identities, average both schedules within a maze, and stratify by R/BP/M. They are exploratory and unadjusted for multiple comparisons.',
  '', '| Candidate vs reference | Goals ref→candidate | Rescued/harmed | Δ observations CI | Δ H80 steps CI | Δ distance CI | Δ missed changes CI | Δ false persistence | Δ safety interventions |',
  '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
 for cand in ('b_age','c_ternary','bc'):
  for ref in ('periodic','age'):
   rows=pair(ref,policies[ref],cand,policies[cand])
   def ci(metric):
    value=cluster_ci(rows,metric)
    return 'n/a' if value is None else f"{value['paired_mean_delta']:.2f} [{value['ci95_low']:.2f}, {value['ci95_high']:.2f}]"
   report.append(f"| {LABELS[cand]} vs {LABELS[ref]} | {sum(r['reference_success'] or 0 for r in rows)}→{sum(r['candidate_success'] or 0 for r in rows)} | {sum(r['rescued'] for r in rows)}/{sum(r['harmed'] for r in rows)} | {ci('observations_delta')} | {ci('steps_h80_delta')} | {ci('distance_m_delta')} | {ci('missed_persistent_delta')} | {ci('false_persistent_delta')} | {ci('emergency_interventions_delta')} |")
 report += ['', '## New B/C arms paired against saved RDAO generations', '',
  'These are same-key, maze-cluster paired descriptive comparisons; RDAO rows are read from historical evidence and were not rerun.','',
  '| Candidate vs historical RDAO | Goals ref→candidate | Rescued/harmed | Δ observations CI | Δ H80 steps CI | Δ distance CI | Δ safety interventions |','|---|---:|---:|---:|---:|---:|---:|']
 for cand in ('b_age','c_ternary','bc'):
  for ref in HISTORY:
   rows=pair(ref,policies[ref],cand,policies[cand])
   def hist_ci(metric):
    value=cluster_ci(rows,metric)
    return 'n/a' if value is None else f"{value['paired_mean_delta']:.2f} [{value['ci95_low']:.2f}, {value['ci95_high']:.2f}]"
   report.append(f"| {LABELS[cand]} vs {LABELS[ref]} | {sum(r['reference_success'] or 0 for r in rows)}→{sum(r['candidate_success'] or 0 for r in rows)} | {sum(r['rescued'] for r in rows)}/{sum(r['harmed'] for r in rows)} | {hist_ci('observations_delta')} | {hist_ci('steps_h80_delta')} | {hist_ci('distance_m_delta')} | {hist_ci('emergency_interventions_delta')} |")
 report += ['', '## Interpretation and limitations', '',
  '- B-only reproduced Age’s success count (66/72), observation count, steps, distance, safety counts, and trajectory metrics exactly. It changed the aggregate missed-change error by only −7 cell-time units over 72 episodes (cluster interval includes zero).',
  '- B-only versus Periodic rescued two and harmed two episodes, so completion was unchanged. Its all-episode H80-censored step delta was −1.72 [−3.14, −0.44], while the observation count rose by 0.69 [0.33, 1.07]. The distance interval crossed zero.',
  '- C-only and B+C each harmed 20 Periodic/Age successes and rescued none (46 vs 66 goals). Their paid observations fell by about 5.7 and 7.5 per episode versus Periodic, but missed-change error and blocked attempts rose; emergency interventions were 40 and 39 compared with 7 Periodic and 5 Age.',
  '- C-only/B+C measured scheduler cost averaged 123/128 ms per episode. Mean episode wall time was about 291/299 ms versus 145/154 ms for Age/Periodic in this same run. B-only scheduler cost was 2.22 ms. Wall-time differences include scene/runtime overhead.',
  '- All new and historical arms recorded zero unwanted contacts in these saved episodes. This does not establish safety beyond FIT72.',
  '- Both the initial RDAO v1 and its footprint-only follow-up are listed separately because they are distinct saved v1 results. RDAO v1/v2/v2.1/v2.2 all use the same 72 keys. Most historical RDAO tables lack memory-error fields; those values remain unavailable.',
  '- FIT72 is descriptive development evidence, not independent validation. The two schedules per maze remain clustered. No B/C parameter was tuned.', '',
  'Per-episode traces and provenance are in persistence_evi_fit72_restored_local_v1/. Policy summaries, paired deltas, cluster intervals and input hashes are in this analysis directory.', '',
  'Reproduction:', '',
  '    .venv/bin/python -m pytest tests/test_persistence_evi.py tests/test_persistence_evi_evaluation.py -q',
  '    .venv/bin/python scripts/evaluate_persistence_evi_fit72.py --output results/phase2_mujoco/persistence_evi_fit72_restored_local_v1',
  '    .venv/bin/python scripts/analyze_persistence_evi_fit72_restored.py', '']
 (OUT/'research_report.md').write_text('\n'.join(report),encoding='utf-8')
 manifest=[]
 for path in sorted(x for x in OUT.rglob('*') if x.is_file() and x.name!='artifact_manifest.json'):
  manifest.append({'path':path.relative_to(OUT).as_posix(),'bytes':path.stat().st_size,'sha256':sha(path)})
 (OUT/'artifact_manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
 print(json.dumps({'status':'ANALYSIS_COMPLETE','policies':len(policies),'paired_metrics':len(comps),
                   'output':OUT.relative_to(ROOT).as_posix()},indent=2))

if __name__=='__main__':
 main()
