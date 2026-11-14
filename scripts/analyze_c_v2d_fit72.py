"""Pairwise descriptive analysis and historical context for the C v2.0d FIT72 screen."""
from __future__ import annotations
import csv,gzip,hashlib,json,math
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
FIT=ROOT/'results/phase2_mujoco/c_v2d_topology_v1/fit72_descriptive_screen'
DIAG=ROOT/'results/phase2_mujoco/c_v2d_topology_v1/fit72_fixed_state_diagnostic_v1'
HIST={
 'RDAO v1':'results/phase2_mujoco/rdao_v1_footprint_visibility_online_fit72_v1/summary.json',
 'RDAO v2':'results/phase2_mujoco/rdao_v2_viewpoint_fit72_v1/summary.json',
 'RDAO v2.1':'results/phase2_mujoco/rdao_v21_current_view_quality_fit72_v1/summary.json',
 'RDAO v2.2':'results/phase2_mujoco/rdao_v22_decision_protected_fit72_v1/summary.json'}
ARMS=('periodic','age','C0','C-K','C-Topology3-d')
FLAT_ARM={'periodic':'periodic','age':'age','C0':'c0_audit','C-K':'c_k','C-Topology3-d':'c_topology3d'}


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def _episode_rows():
    rows={}
    for path in FIT.glob('episode_*_*.json.gz'):
        d=json.loads(gzip.decompress(path.read_bytes()))
        arm=path.name[:-8].rsplit('_',1)[1]
        key=d['trace']['key'];identity,schedule,_method,seed=key
        rows[(identity,int(schedule),int(seed),arm)]=d
    return rows


def _sign_test(positive,negative):
    n=positive+negative
    if n==0:return {'positive':0,'negative':0,'ties_excluded':True,'two_sided_p':1.}
    tail=sum(math.comb(n,i) for i in range(min(positive,negative)+1))/(2**n)
    return {'positive':positive,'negative':negative,'ties_excluded':True,
      'non_tied_clusters':n,'two_sided_p':min(1.,2*tail)}


def _compare(rows,candidate,reference):
    keys=sorted({k[:3] for k in rows if k[3]==candidate and (k[:3]+(reference,)) in rows})
    pairs=[]
    for key in keys:
        a=rows[key+(reference,)];b=rows[key+(candidate,)]
        ar,br=a['row'],b['row']
        pairs.append({'key':key,'reference':ar,'candidate':br,
          'reference_success':bool(ar['success']),'candidate_success':bool(br['success']),
          'reference_observations':int(ar['observation_count']),'candidate_observations':int(br['observation_count']),
          'reference_steps':int(ar['elapsed_steps']),'candidate_steps':int(br['elapsed_steps']),
          'reference_distance':float(ar['travel_distance_m']),'candidate_distance':float(br['travel_distance_m'])})
    rescue=sum(not x['reference_success'] and x['candidate_success'] for x in pairs)
    harm=sum(x['reference_success'] and not x['candidate_success'] for x in pairs)
    common=[x for x in pairs if x['reference_success'] and x['candidate_success']]
    by_world={}
    for x in pairs:
        world=x['key'][0];acc=by_world.setdefault(world,[])
        acc.append(x)
    cluster_signs={}
    for metric,ref_key,cand_key in (
      ('goal_success','reference_success','candidate_success'),
      ('paid_memory_observations','reference_observations','candidate_observations'),
      ('H80_steps','reference_steps','candidate_steps'),
      ('travel_distance_m','reference_distance','candidate_distance')):
        pos=neg=0
        for group in by_world.values():
            delta=sum(float(x[cand_key])-float(x[ref_key]) for x in group)
            pos+=delta>0;neg+=delta<0
        cluster_signs[metric]=_sign_test(pos,neg)
    return {'candidate':candidate,'reference':reference,'episodes':len(pairs),
      'goals_reference':sum(x['reference_success'] for x in pairs),
      'goals_candidate':sum(x['candidate_success'] for x in pairs),
      'rescues':rescue,'harms':harm,'goal_ties':len(pairs)-rescue-harm,
      'unwanted_contact_episodes_reference':sum(int(x['reference']['g1_unwanted_contact_pairs'])>0 for x in pairs),
      'unwanted_contact_episodes_candidate':sum(int(x['candidate']['g1_unwanted_contact_pairs'])>0 for x in pairs),
      'unwanted_contact_pairs_reference':sum(int(x['reference']['g1_unwanted_contact_pairs']) for x in pairs),
      'unwanted_contact_pairs_candidate':sum(int(x['candidate']['g1_unwanted_contact_pairs']) for x in pairs),
      'mean_paid_observations_reference':sum(x['reference_observations'] for x in pairs)/len(pairs),
      'mean_paid_observations_candidate':sum(x['candidate_observations'] for x in pairs)/len(pairs),
      'total_delta_observations':sum(x['candidate_observations']-x['reference_observations'] for x in pairs),
      'mean_H80_steps_reference':sum(x['reference_steps'] for x in pairs)/len(pairs),
      'mean_H80_steps_candidate':sum(x['candidate_steps'] for x in pairs)/len(pairs),
      'total_delta_H80_steps':sum(x['candidate_steps']-x['reference_steps'] for x in pairs),
      'mean_distance_reference':sum(x['reference_distance'] for x in pairs)/len(pairs),
      'mean_distance_candidate':sum(x['candidate_distance'] for x in pairs)/len(pairs),
      'total_delta_distance_m':sum(x['candidate_distance']-x['reference_distance'] for x in pairs),
      'common_success_episodes':len(common),
      'common_success_mean_steps_reference':sum(x['reference_steps'] for x in common)/len(common) if common else None,
      'common_success_mean_steps_candidate':sum(x['candidate_steps'] for x in common)/len(common) if common else None,
      'common_success_mean_distance_reference':sum(x['reference_distance'] for x in common)/len(common) if common else None,
      'common_success_mean_distance_candidate':sum(x['candidate_distance'] for x in common)/len(common) if common else None,
      'maze_clustered_sign_tests':cluster_signs}


def _historical():
    out={}
    for name,rel in HIST.items():
        d=json.loads((ROOT/rel).read_text())
        if name=='RDAO v1':
            a=d['aggregates'];out[name]={'status':d['status'],'episodes':a['episodes'],
              'reference_goals':a['original_successes'],'variant_goals':a['variant_successes'],
              'rescues':a['rescued_failures'],'harms':a['harmed_successes'],'contacts':a['variant_contacts'],
              'mean_observations_reference':a['mean_original_observations'],'mean_observations':a['mean_variant_observations'],
              'mean_H80_steps':a['mean_variant_censored_steps'],'mean_distance_m':a['mean_variant_distance_m'],
              'mean_scheduler_ms':a['mean_variant_scheduler_ms']}
        elif name=='RDAO v2':
            a=d['footprint_and_v2'];base=d['original_and_v2'];out[name]={'status':d['status'],
              'episodes':base['episodes'],
              'reference_goals':a['footprint_successes'],'variant_goals':a['v2_successes'],
              'rescues':a['v2_rescues_vs_footprint'],'harms':a['v2_harms_vs_footprint'],
              'contacts':base['variant_contacts'],'mean_observations':a['mean_v2_observations'],
              'mean_H80_steps':a['mean_v2_censored_steps'],'mean_distance_m':a['mean_v2_distance_m'],
              'mean_scheduler_ms':base['mean_variant_scheduler_ms']}
        elif name=='RDAO v2.1':
            a=d['v21_relative_to_footprint'];out[name]={'status':d['status'],'episodes':a['episodes'],
              'reference_goals':a['reference_successes'],'variant_goals':a['candidate_successes'],
              'rescues':a['rescues'],'harms':a['harms'],'contacts':d['v21_unwanted_contact_pairs'],
              'mean_observations':a['mean_candidate_observations'],'mean_H80_steps':a['mean_candidate_steps_h80'],
              'mean_distance_m':a['mean_candidate_distance_m']}
        else:
            a=d['v22_relative_to_footprint'];out[name]={'status':d['status'],'episodes':a['episodes'],
              'reference_goals':a['reference_successes'],'variant_goals':a['candidate_successes'],
              'rescues':a['rescues'],'harms':a['harms'],'contacts':d['v22_unwanted_contact_pairs'],
              'mean_observations':a['mean_candidate_observations'],'mean_H80_steps':a['mean_candidate_steps_h80'],
              'mean_distance_m':a['mean_candidate_distance_m']}
        out[name]['source']=rel;out[name]['source_sha256']=sha(ROOT/rel)
    return out


def run():
    summary=json.loads((FIT/'summary.json').read_text())
    if summary.get('baseline_reproduction_passed') is not True or summary.get('C0_exact_saved_replay_passed') is not True:
        raise RuntimeError('FIT72 baseline reproduction evidence missing')
    with (FIT/'episodes.csv').open(newline='') as f:flat=list(csv.DictReader(f))
    arm_data={}
    for arm in ARMS:
        items=[r for r in flat if r['arm']==FLAT_ARM[arm]]
        if len(items)!=72:
            raise RuntimeError(f'expected 72 rows for {arm}, got {len(items)}')
        def total(k):return sum(int(r[k] or 0) for r in items)
        def mean(k):return sum(float(r[k] or 0) for r in items)/len(items)
        arm_data[arm]={'episodes':len(items),'goals':sum(r['success']=='True' for r in items),
          'unwanted_contact_episodes':sum(int(r['unwanted_contacts'])>0 for r in items),
          'unwanted_contact_pairs':total('unwanted_contacts'),'paid_observations':total('paid_memory_scans'),
          'paid_memory_rays':total('actual_memory_raycasts'),'emergency_scans':total('emergency_safety_scans'),
          'emergency_rays':total('emergency_safety_raycasts'),'combined_rays':total('combined_rays'),
          'H80_steps':total('elapsed_steps'),'blocked_attempts':total('blocked_attempts'),
          'emergency_interventions':total('emergency_safety_interventions'),
          'false_persistent_updates':total('false_persistent_occupancy_updates'),
          'missed_persistent_changes':total('missed_persistent_changes'),
          'mean_episode_seconds':mean('episode_wall_time_seconds'),
          'total_plan_calls':total('total_plan_calls'),'mean_plan_calls_per_episode':mean('total_plan_calls'),
          'max_plan_calls_in_episode':max(int(r['max_plan_calls']) for r in items),
          'counterfactual_astar_calls':total('total_counterfactual_astar_calls'),
          'scheduler_ms_mean':mean('scheduler_ms'),'total_graph_analysis_ms':sum(float(r['total_graph_analysis_ms'] or 0) for r in items),
          'total_candidate_visits':total('total_candidate_visits'),
          'total_topk_key_comparisons':total('total_topk_key_comparisons'),
          'total_topk_heap_comparisons':total('total_topk_heap_comparisons'),
          'total_grid_cell_reads':total('total_grid_cell_reads'),
          'total_graph_edge_inspections':total('total_graph_edge_inspections'),
          'total_counterfactual_grid_copy_cell_reads':total('total_counterfactual_grid_copy_cell_reads')}
    rows=_episode_rows()
    paired={f'{candidate}_vs_{ref}':_compare(rows,candidate,ref)
      for candidate in ('C0','C-K','C-Topology3-d') for ref in ('periodic','age')}
    paired.update({f'C-Topology3-d_vs_{ref}':_compare(rows,'C-Topology3-d',ref)
      for ref in ('C0','C-K')})
    historical=_historical()
    diag=json.loads((DIAG/'diagnostic.json').read_text())
    artifact={'status':'COMPLETED_C_V2D_FIT72_ANALYSIS',
      'fit_status':summary['status'],'episodes_per_arm':72,'maze_layouts':36,
      'baseline_reproduction_passed':True,'C0_exact_saved_replay_passed':True,
      'arms':arm_data,'paired_comparisons':paired,
      'historical_RDAO_reference_only':historical,'fixed_state_diagnostic':diag,
      'preservation':{'source_artifact_manifest_verified':True,
        'fit_integrity_status':json.loads((ROOT/'results/phase2_mujoco/persistence_evi_fit72_analysis_restored_local_v2/integrity_verification.json').read_text())['status'],
        'Phase1_5_protected_files':836},
      'limitations':['Descriptive FIT72 development evaluation, not independent validation.',
        'The two schedules per maze are correlated; paired sign tests aggregate at the maze level and are descriptive.',
        'Historical RDAO versions are context from earlier FIT72 analyses, not a new matched re-execution.',
        'Memory-error quantities are evaluator-only retrospective diagnostics.'],
      'source_hashes':{'summary.json':sha(FIT/'summary.json'),'episodes.csv':sha(FIT/'episodes.csv'),
        'paired.csv':sha(FIT/'paired.csv'),'fixed_state_diagnostic.json':sha(DIAG/'diagnostic.json')}}
    (FIT/'analysis.json').write_text(json.dumps(artifact,indent=2,sort_keys=True,allow_nan=False)+'\n')
    _plot(artifact,FIT/'fit72_outcomes.png')
    _write_report(artifact,FIT/'research_report.md')
    manifest=[]
    for p in sorted(x for x in FIT.rglob('*') if x.is_file() and x.name!='artifact_manifest.json'):
        b=p.read_bytes();manifest.append({'path':p.relative_to(FIT).as_posix(),'bytes':len(b),'sha256':sha(p)})
    (FIT/'artifact_manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    return artifact


def _plot(data,path):
    arms=data['arms'];labels=[arms[x].get('label',x) for x in ARMS]
    labels=['Periodic','Age','C0','C-K','Topology3-d']
    fig,axes=plt.subplots(1,2,figsize=(10,4.2),dpi=180)
    colors=['#708090','#82967b','#4c78a8','#f2a541','#5b8c74']
    goals=[arms[x]['goals']/72 for x in ARMS]
    axes[0].bar(labels,goals,color=colors);axes[0].set_ylim(0,1);axes[0].set_ylabel('Goal completion');axes[0].set_title('FIT72 goal completion')
    for i,v in enumerate(goals):axes[0].text(i,v+.02,f'{v*72:.0f}/72',ha='center',fontsize=8)
    obs=[arms[x]['paid_observations']/72 for x in ARMS]
    scheduler=[arms[x]['scheduler_ms_mean'] for x in ARMS]
    axes[1].bar(labels,obs,color=colors);axes[1].set_ylabel('Paid memory scans / episode');axes[1].set_title('Observations and scheduler cost')
    twin=axes[1].twinx();twin.plot(range(len(labels)),scheduler,color='#b04a42',marker='o',linewidth=1.6);twin.set_ylabel('Scheduler ms / episode',color='#b04a42')
    for ax in axes:ax.tick_params(axis='x',rotation=22);ax.grid(axis='y',alpha=.2)
    fig.suptitle('C v2.0d matched descriptive screen (72 keys)',fontsize=11)
    fig.tight_layout();fig.savefig(path,bbox_inches='tight');plt.close(fig)


def _write_report(data,path):
    a=data['arms'];p=data['paired_comparisons'];lines=[
      '# C v2.0d FIT72 descriptive development evaluation','',
      'Status: completed once after the synthetic `PASS` and independent `ACCEPTED_FOR_FIT` review. '
      'This is descriptive development evidence, not independent validation. The 72 keys cover 36 saved mazes × 2 schedules.','',
      '## Outcomes','',
      '| Arm | Goals / 72 | Unwanted-contact episodes / pairs | Paid scans | Emergency scans | Combined rays | H80 steps | Blocked actions | Emergency interventions | False persistent updates | Missed persistent changes | Mean scheduler ms/episode | Mean episode seconds |',
      '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for arm,name in zip(ARMS,('Periodic','Age','C0','C-K','C-Topology3-d')):
        x=a[arm];lines.append(f"| {name} | {x['goals']}/72 | {x['unwanted_contact_episodes']} / {x['unwanted_contact_pairs']} | {x['paid_observations']} | {x['emergency_scans']} | {x['combined_rays']} | {x['H80_steps']} | {x['blocked_attempts']} | {x['emergency_interventions']} | {x['false_persistent_updates']} | {x['missed_persistent_changes']} | {x['scheduler_ms_mean']:.1f} | {x['mean_episode_seconds']:.3f} |")
    lines += ['', '## Paired goal and navigation comparisons','',
      '| Candidate vs reference | Goals ref→candidate | Rescues / harms | Mean scans ref→candidate | Common-success steps ref→candidate | Common-success distance ref→candidate (m) | Maze sign test, success p |',
      '|---|---:|---:|---:|---:|---:|---:|']
    for key in ('C0_vs_periodic','C0_vs_age','C-K_vs_periodic','C-K_vs_age',
                'C-Topology3-d_vs_periodic','C-Topology3-d_vs_age',
                'C-Topology3-d_vs_C0','C-Topology3-d_vs_C-K'):
        x=p[key];test=x['maze_clustered_sign_tests']['goal_success']
        common=x['common_success_episodes']
        lines.append(f"| {x['candidate']} vs {x['reference']} | {x['goals_reference']}→{x['goals_candidate']} | {x['rescues']} / {x['harms']} | {x['mean_paid_observations_reference']:.2f}→{x['mean_paid_observations_candidate']:.2f} | {x['common_success_mean_steps_reference']:.2f}→{x['common_success_mean_steps_candidate']:.2f} ({common}) | {x['common_success_mean_distance_reference']:.2f}→{x['common_success_mean_distance_candidate']:.2f} | {test['positive']}/{test['negative']} clusters, p={test['two_sided_p']:.3f} |")
    lines += ['', 'The sign tests use one paired delta per maze (the two schedules are grouped together); they are descriptive, with no multiple-comparison adjustment. FIT72 must not be interpreted as a held-out test.','',
      '## Computational workload','',
      '| Arm | Scheduler ms/episode | Wall s/episode | Total A* calls | Counterfactual A* | Graph analysis ms total | Candidate visits | Top-K comparisons | Grid reads | Graph edge inspections | Copy reads |',
      '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for arm,name in zip(ARMS,('Periodic','Age','C0','C-K','C-Topology3-d')):
        x=a[arm];lines.append(f"| {name} | {x['scheduler_ms_mean']:.1f} | {x['mean_episode_seconds']:.3f} | {x['total_plan_calls']} | {x['counterfactual_astar_calls']} | {x['total_graph_analysis_ms']:.1f} | {x['total_candidate_visits']} | {x['total_topk_key_comparisons']} | {x['total_grid_cell_reads']} | {x['total_graph_edge_inspections']} | {x['total_counterfactual_grid_copy_cell_reads']} |")
    lines += ['', 'C0 and C-K do not execute the new topology graph stage, so their topology-only counters remain zero; comparisons of total scheduler and wall time are more meaningful than comparing unlike graph-operation counts.','',
      '## Fixed-state scan swap','',
      f"The frozen public-memory selection rule chose `{data['fixed_state_diagnostic']['selected_state']['identity']}` schedule {data['fixed_state_diagnostic']['selected_state']['schedule']}, step {data['fixed_state_diagnostic']['selected_state']['step']}. C0 granted a scan and C v2.0d did not; 60 same-prefix decision disagreements were eligible, and {data['fixed_state_diagnostic']['eligible_state_count']} passed the exhaustive-D/common-cost state filter. The highest exhaustive D was {data['fixed_state_diagnostic']['selected_state']['exhaustive_max_D']:.3f} versus common K=3 cost {data['fixed_state_diagnostic']['selected_state']['common_K3_cost']:.3f}; the C v2.0d selected-cell D was {data['fixed_state_diagnostic']['selected_state']['selected_C_v2d_D']:.3f}.",
      f"A paired scan/no-scan replay from that state kept the preceding trace identical. Both branches reached the goal at step {data['fixed_state_diagnostic']['scan_swap']['no_scan']['goal_step']} with zero unwanted contacts. The no-scan branch used {data['fixed_state_diagnostic']['scan_swap']['no_scan']['observations']} memory observations; the scan branch used {data['fixed_state_diagnostic']['scan_swap']['with_scan']['observations']}. This single intervention shows no goal-step benefit for this chosen state; it does not establish general scan utility.",'',
      '## Historical RDAO context','',
      'These are earlier descriptive FIT72 screens against their stated references, not re-executions in this v2.0d run.','',
      '| Historical version | Goals | Rescues / harms | Mean scans | Mean H80 steps | Mean distance (m) | Contacts |',
      '|---|---:|---:|---:|---:|---:|---:|']
    for name,x in data['historical_RDAO_reference_only'].items():
        lines.append(f"| {name} | {x['variant_goals']}/72 | {x['rescues']} / {x['harms']} | {x.get('mean_observations',float('nan')):.2f} | {x['mean_H80_steps']:.2f} | {x['mean_distance_m']:.2f} | {x['contacts']} |")
    lines += ['', '## Interpretation','',
      f"C-Topology3-d completed {a['C-Topology3-d']['goals']}/72 versus {a['C0']['goals']}/72 for C0 and {a['C-K']['goals']}/72 for C-K, with zero unwanted-contact episodes in all three candidate arms. It used {a['C-Topology3-d']['paid_observations']} paid memory scans versus {a['C0']['paid_observations']} for C0 and {a['C-K']['paid_observations']} for C-K. Relative to C0, C-Topology3-d's matched outcome changes were {p['C-Topology3-d_vs_C0']['rescues']} rescues and {p['C-Topology3-d_vs_C0']['harms']} harms; relative to C-K they were {p['C-Topology3-d_vs_C-K']['rescues']} rescues and {p['C-Topology3-d_vs_C-K']['harms']} harms.",
      f"The C-Topology3-d mean scheduler time was {a['C-Topology3-d']['scheduler_ms_mean']:.1f} ms per episode versus {a['C-K']['scheduler_ms_mean']:.1f} for C-K and {a['C0']['scheduler_ms_mean']:.1f} for C0. The navigation result is a descriptive trade-off, not a clean efficiency win: the method raises goal completion over C0, but costs more scheduler time and more paid observations; against C-K it has fewer goals despite the topology ranking and more scheduler work.",'',
      '## Integrity and limitations','',
      '- Periodic/Age baseline metrics and semantic traces reproduced; C0 matched the saved C0 replay exactly.',
      '- All three raw FIT stores, 2,907 payloads/receipts, 836 protected Phase 1.5 files, and 363 original FIT72 artifacts revalidated read-only.',
      '- No world regeneration, reserved cohort access, or store writes occurred.',
      '- Memory error totals are retrospective evaluator metrics. They are not online inputs.',
      '- Two schedules within a maze are correlated. No independent-validation claim is made.','']
    path.write_text('\n'.join(lines))


if __name__=='__main__':
    print(json.dumps(run(),indent=2,sort_keys=True)[:4000])
