"""Post-run reporting checks/corrections; no policy calls or gate changes.

The frozen analysis uses each ablation's assumed-availability oracle. Those
false-negative counts cannot be compared across visibility assumptions. This
additive supplement uses one visibility-aware reference for ALL arms and
retains the original artifacts. It also bypasses legacy one-step CSV aliases
when reporting multi-step copy/reason counters.
"""
from __future__ import annotations
import gzip,json,sys
from collections import Counter
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from c_v21_common import ROOT,OUT,write,manifest,sha,verify_manifest
from c_v21_fixtures import build,digest
sys.path.insert(0,str(ROOT/'src'))
from spatial_memory.multistep_reference import footprint,reference_cell


def run():
    target=OUT/'reporting_checks';target.mkdir(parents=True,exist_ok=False)
    binding=json.loads((OUT/'protocol_binding.json').read_text())
    if any(sha(ROOT/p)!=s for p,s in binding['source_sha256'].items()):raise RuntimeError('Frozen source changed')
    fixtures=build()
    if digest(fixtures)!=binding['fixture_population_sha256']:raise RuntimeError('Fixtures changed')
    result=json.loads((OUT/'synthetic/results.json').read_text());by_id={r['id']:r for r in result['fixtures']}
    common={a:{'false_positive':0,'false_negative':0,'scan':0} for a in result['fixtures'][0]['results']}
    for f in fixtures:
        grid=np.array(f['grid'],dtype=np.int8);q=np.array(f['probability'])
        eligible=[c for c in footprint(grid,f['start'],f['yaw'],f['sensor']) if c!=tuple(f['start']) and .05<q[c[1],c[0]]<.95]
        for a,r in by_id[f['id']]['results'].items():
            oracle=any(reference_cell(grid,c,float(q[c[1],c[0]]),f['start'],f['goal'],f['yaw'],f['unknown'],f['sensor'],r['cost'],True)['scan'] for c in eligible)
            scan=r['net_value']>0
            common[a]['false_positive']+=int(scan and not oracle);common[a]['false_negative']+=int(not scan and oracle);common[a]['scan']+=int(scan)
    write(target/'common_visibility_oracle.json',{'scope':'Post-run descriptive common-reference comparison; not a revised formal gate','future_visibility_reference':True,'same_reference_assumption_for_all_arms':True,'scan_price':'Each arm actual declared price','arms':common})
    fig,ax=plt.subplots(figsize=(11,4));names=list(common)
    ax.bar(range(len(names)),[common[a]['false_negative'] for a in names]);ax.set_xticks(range(len(names)),names,rotation=40,ha='right');ax.set_ylabel('Missed authorizations /96 fixtures');ax.set_title('All arms versus the SAME future-visibility reference\nPost-run reporting supplement; no gate or policy changes');fig.tight_layout();fig.savefig(target/'synthetic_common_reference.png',dpi=170);plt.close(fig)
    totals={};episodes=0;artifact_counts={}
    for directory in ('reference_replays','fit_smoke2','fit72','interventions'):
        artifact_counts[directory]=verify_manifest(OUT/directory)
        for p in sorted((OUT/directory).glob('episode_*.json.gz')):
            e=json.load(gzip.open(p,'rt'));r=e['row'];d=e['diagnostics'];frames=e['trace']['steps']
            scans=sum(bool(f['observation_granted']) for f in frames)
            actual=int(d['actual_memory_sensor_calls'])
            if not (scans==actual==int(r['observation_count'])<=20):raise RuntimeError('Paid count invariant')
            if d['actual_memory_raycasts']!=61*actual:raise RuntimeError('Memory rays mismatch')
            shield=sum(f.get('action') is not None and f['action'][0]!='wait' for f in frames)
            if r['g1_actual_collision_shield_queries']!=shield or r['g1_unselected_action_shield_queries']!=0 or not r['g1_shield_query_count_valid']:raise RuntimeError('Selected shield invariant')
            emergency=[f['emergency_scan'] for f in frames if 'emergency_scan' in f]
            if len(emergency)!=r['elapsed_steps'] or sum(s['ray_count'] for s in emergency)!=r['emergency_safety_raycasts']:raise RuntimeError('Emergency count invariant')
            episodes+=1
            if directory=='fit72':
                arm=d['multistep_arm'];dec=[v for v in d['decisions'] if v.get('plan_calls',0)>0]
                t=totals.setdefault(arm,{'scored_decisions':0,'budget_skipped_decisions':0,'actual_noninitial_grants':0,'counterfactual_grid_copy_cell_reads':0,'authorization_reasons':Counter(),'active_mean_value_sum':0.,'active_mean_delay_sum':0.,'predicted_target_visible_at_actual_scan':0,'predicted_target_not_seen_at_actual_scan':0})
                t['scored_decisions']+=len(dec);t['budget_skipped_decisions']+=len(d['decisions'])-len(dec);t['actual_noninitial_grants']+=len(d['observation_log'])
                t['counterfactual_grid_copy_cell_reads']+=sum(v['counterfactual_grid_cells_copied'] for v in dec)
                t['active_mean_value_sum']+=sum(v['value'] for v in dec);t['active_mean_delay_sum']+=sum(v['delay_regret'] for v in dec)
                t['authorization_reasons'].update(v.get('reason','budget_exhausted') for v in d['decisions'])
                for log in d['observation_log']:
                    t['predicted_target_visible_at_actual_scan']+=int(log.get('observed_candidate_outcome') in (0,1))
                    t['predicted_target_not_seen_at_actual_scan']+=int(log.get('observed_candidate_outcome')==-1)
    for t in totals.values():
        t['active_mean_V']=t.pop('active_mean_value_sum')/t['scored_decisions'];t['active_mean_delay']=t.pop('active_mean_delay_sum')/t['scored_decisions']
        t['authorization_reasons']=dict(t['authorization_reasons'])
    interventions=json.loads((OUT/'interventions/summary.json').read_text());full_prefix=[]
    for i,row in enumerate(interventions['rows'],1):
        a=json.load(gzip.open(OUT/f'interventions/episode_{i:03}_scan_now.json.gz','rt'));b=json.load(gzip.open(OUT/f'interventions/episode_{i:03}_scan_later.json.gz','rt'));t=row['selection']['step']
        if a['trace']['steps'][:t]!=b['trace']['steps'][:t]:raise RuntimeError('Full predecision trace mismatch')
        saved=json.load(gzip.open(OUT/f'fit72/episode_{row["selection"]["episode"]:03}_{row["selection"]["arm"]}.json.gz','rt'))
        if a['trace']!=saved['trace']:raise RuntimeError('Full untreated trace mismatch')
        af={f['step']:f for f in a['trace']['steps']};bf={f['step']:f for f in b['trace']['steps']}
        differences=[s for s in sorted(set(af)&set(bf)) if (af[s]['position'],af[s]['heading_yaw'],af[s]['action'])!=(bf[s]['position'],bf[s]['heading_yaw'],bf[s]['action'])]
        full_prefix.append({'case':i,'full_predecision_trace_equal':True,'full_untreated_trace_equal':True,'first_actual_action_pose_heading_difference':min(differences) if differences else None,'selection':row['selection']})
    write(target/'verification.json',{'status':'PASS_POSTRUN_REPORTING_AND_SENSOR_SAFETY_CHECKS','frozen_source_unchanged':True,'fixture_population_unchanged':True,'episodes_verified':episodes,'artifact_files_verified':artifact_counts,'multistep_counters_and_observation_diagnostics':totals,'intervention_full_prefix_checks':full_prefix,'legacy_alias_warning':'Do not use frozen fit.flat evi_* one-step classifiers or its zero copy-read fallback for new arms; direct multi-step decision fields above are authoritative. Original files preserved.','future_visibility_caveat':'Selected target observed at a real scan does not validate future observability, which may have no actual reading.','postprocessing_source_sha256':sha(__file__)})
    manifest(target);print(json.dumps({'common_oracle':common,'episodes_verified':episodes,'prefix_checks':full_prefix},indent=2))
if __name__=='__main__':run()
