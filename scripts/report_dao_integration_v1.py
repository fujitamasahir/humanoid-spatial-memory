"""Read-only postprocessing/independent reconstruction; no new sensing or episodes."""
import json,gzip,sys
from pathlib import Path
from collections import defaultdict
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from c_v21_common import write,manifest,verify_manifest,sha
from spatial_memory.discovery_reference import footprint_reference
from verify_dao_integrity import verify
OUT=ROOT/'results/phase2_mujoco/dao_integration_v1'


def load_episodes():
    result={};fixtures={}
    for folder in ('engineering','engineering_recovery_v1_1'):
        verify_manifest(OUT/folder)
        for p in sorted((OUT/folder).glob('*_dao_*.json.gz')):
            e=json.loads(gzip.decompress(p.read_bytes()));key=(e['scene'],e['mode']);assert key not in result
            result[key]=(e,p)
        for p in (OUT/folder).glob('*_fixture.json'):
            e=json.loads(p.read_text());assert e['scene'] not in fixtures;fixtures[e['scene']]=(e,p)
    assert len(result)==48 and len(fixtures)==12
    return result,fixtures


def check_scans(scans):
    grid=np.full((15,15),-1,np.int8);last=np.full(grid.shape,-1,np.int64)
    for scan in scans:
        step=scan['step'];position=tuple(scan['position']);ref=footprint_reference(grid.tolist(),position,scan['yaw'])
        observed={tuple(c):v for c,v in zip(scan['actual_observed_cells'],scan['actual_observation_values'])}
        new={c for c in observed if last[c[1],c[0]]<0};changed={c for c,v in observed.items() if last[c[1],c[0]]>=0 and grid[c[1],c[0]]!=v}
        stale={c for c in observed if last[c[1],c[0]]>=0 and step-last[c[1],c[0]]>=5}
        assert new==set(map(tuple,scan['actual_new_cells'])) and changed==set(map(tuple,scan['actual_changed_known_cells']))
        assert stale==set(map(tuple,scan['actual_stale_verified_cells']))
        for name in ('frontier','optimistic'):
            assert ref[name]==set(map(tuple,scan['footprints'][name]))
            pred={c for c in ref[name] if grid[c[1],c[0]]==-1};assert pred==set(map(tuple,scan['predicted_new'][name]))
            actual=new-{position};m=scan['metrics'][name]
            assert m['signed_error']==len(pred)-len(actual) and m['absolute_error']==abs(len(pred)-len(actual))
            assert m['precision']==(len(pred&actual)/len(pred) if pred else None)
            assert m['recall']==(len(pred&actual)/len(actual) if actual else None)
        for (x,y),v in observed.items():grid[y,x]=v;last[y,x]=step
    return len(scans)


def main():
    target=OUT/'analysis';target.mkdir(parents=True,exist_ok=False);episodes,fixtures=load_episodes()
    summaries={};scan_rows=[];checks=0;contact_cases=[];fallback_rows=[]
    for (scene,mode),(e,path) in episodes.items():
        checks+=check_scans(e['scans']);m=e['metrics'];calls=e['actual_calls']
        assert calls['memory']==len(e['scans'])==m['observation_count']<=20
        assert calls['emergency']==m['emergency_safety_scans'] and calls['shield']==m['g1_actual_collision_shield_queries']
        assert m['g1_shield_query_count_valid'] and m['g1_unselected_action_shield_queries']==0
        v=summaries.setdefault(mode,defaultdict(float));v['episodes']+=1;v['goals']+=m['success'];v['paid_scans']+=calls['memory']
        v['emergency_scans']+=calls['emergency'];v['selected_shield_calls']+=calls['shield'];v['contact_pairs']+=m['g1_unwanted_contact_pairs'];v['contact_states']+=m['g1_unwanted_contact_states']
        v['route_plan_calls']+=e['route_plan_calls'];v['route_plan_ms']+=e['route_plan_ms'];v['scheduler_ms']+=e['scheduler_ms'];v['wall_seconds']+=m['episode_wall_time_seconds']
        v['vetoed_Age5_requests']+=sum(d['age5_anchor'] and not d['requested'] for d in e['decisions'])
        if m['g1_unwanted_contact_pairs']:contact_cases.append({'scene':scene,'mode':mode,'pairs':m['g1_unwanted_contact_pairs'],'states':m['g1_unwanted_contact_states'],
            'pedestrian_pairs':m['g1_pedestrian_contact_pairs'],'emergency_interventions':m['emergency_safety_interventions']})
        decision={d['step']:d for d in e['decisions']}
        for scan in e['scans']:
            scan_rows.append({'role':'navigation','scene':scene,'mode':mode,'step':scan['step'],'metrics':scan['metrics']})
            d=decision.get(scan['step'])
            if d and d['fallback']:
                fallback_rows.append({'scene':scene,'mode':mode,'step':scan['step'],'new':len(scan['actual_new_cells']),
                  'changed':len(scan['actual_changed_known_cells']),'stale_verified':len(scan['actual_stale_verified_cells'])})
    for scene,(fixture,path) in fixtures.items():
        checks+=check_scans(fixture['scans']);assert len(fixture['scans'])==fixture['fixture_scan_calls']==10
        for scan in fixture['scans']:scan_rows.append({'role':'fixture','scene':scene,'mode':'fixture','step':scan['step'],'metrics':scan['metrics']})
    statistics={}
    for role in ('navigation','fixture'):
        statistics[role]={}
        for name in ('frontier','optimistic'):
            rows=[r['metrics'][name] for r in scan_rows if r['role']==role]
            statistics[role][name]={'scans':len(rows),'mean_signed_error':float(np.mean([r['signed_error'] for r in rows])),
              'mean_absolute_error':float(np.mean([r['absolute_error'] for r in rows])),
              'macro_precision':float(np.mean([r['precision'] for r in rows if r['precision'] is not None])) if any(r['precision'] is not None for r in rows) else None,
              'macro_recall':float(np.mean([r['recall'] for r in rows if r['recall'] is not None])) if any(r['recall'] is not None for r in rows) else None,
              'undefined_precision':sum(r['precision'] is None for r in rows),'undefined_recall':sum(r['recall'] is None for r in rows)}
    # Caution: JSON compatibility fields in legacy metric rows may be zero because
    # the original closure lacks sensor.last_stats; independent measured calls win.
    write(target/'results.json',{'status':'ENGINEERING_COMPLETE_WITH_CONTACT_FINDINGS','arms':summaries,
       'prediction_statistics':statistics,'contact_cases':contact_cases,'fallback_scans':fallback_rows,
       'fallback_no_discovery_or_change':sum(r['new']==0 and r['changed']==0 for r in fallback_rows),
       'fallback_no_discovery_change_or_stale_verification':sum(r['new']==r['changed']==r['stale_verified']==0 for r in fallback_rows),
       'completed_navigation_episodes':48,'incomplete_formal_navigation_attempts':1,'separate_fixture_scans':120,
       'reconstructed_actual_scans':checks,'source_preserved':True})
    integrity=verify();old=ROOT/'results/phase2_mujoco/dao_v1';items=json.loads((old/'final_artifact_manifest.json').read_text())
    for item in items:
        p=old/item['path'];assert sha(p)==item['sha256'] and p.stat().st_size==item['bytes']
    for binding in ('binding.json','binding_v1_1.json'):
        b=json.loads((OUT/binding).read_text());assert all(sha(ROOT/p)==h for p,h in b['sources'].items())
    assert sha(OUT/'prepared/scenes.json')==sha(OUT/'prepared_v1_1/scenes.json')
    write(target/'integrity.json',{**integrity,'previous_DAO_artifacts_unchanged':len(items),'independently_reconstructed_scans':checks,
       'scene_definitions_unchanged':True,'both_source_bindings_unchanged':True,
       'new_navigation_runs':48,'engineering_only_not_cohort':True,'protected_or_production_cohort_access':False,
       'actual_failed_formal_attempts':1,'physical_safety_acceptance':False})
    import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(10,4))
    for name,marker in [('frontier','o'),('optimistic','x')]:
        rows=[r['metrics'][name] for r in scan_rows if r['role']=='navigation']
        axes[0].scatter([r['actual_comparable'] for r in rows],[r['predicted'] for r in rows],s=14,alpha=.35,label=name,marker=marker)
    axes[0].plot([0,100],[0,100],'k--');axes[0].set(xlabel='Actual new cells (exclude robot cell)',ylabel='Predicted unknown cells',title='Actual paid navigation scans');axes[0].legend()
    arms=list(summaries);axes[1].bar(range(4),[summaries[a]['contact_states'] for a in arms],color='darkred');axes[1].set_xticks(range(4),arms,rotation=30,ha='right');axes[1].set(ylabel='Recorded unwanted contact states',title='All contacts occur in pedestrian scene')
    fig.tight_layout();fig.savefig(target/'actual_prediction_contacts.png',dpi=170);plt.close(fig)
    power=json.loads((OUT/'infrastructure/coverage_power.json').read_text())['simulations']
    fig,ax=plt.subplots(figsize=(7,4))
    for q in (.05,.2):
        for rho in (0.,.8):
            rows=[r for r in power if r['discordance']==q and r['schedule_correlation']==rho and r['true_loss']==0]
            ax.plot([r['n'] for r in rows],[r['proposed_NI_probability'] for r in rows],'-o',label=f'discordance={q}, schedule correlation={rho}')
    ax.axhline(.8,color='gray',ls='--');ax.set(xlabel='Independent lineages (synthetic simulation)',ylabel='Proposed3-point NI rejection probability',ylim=(0,1));ax.legend(fontsize=8);fig.tight_layout();fig.savefig(target/'power_sensitivity.png',dpi=170);plt.close(fig)
    manifest(target);print(json.dumps({'arms':summaries,'prediction':statistics,'fallbacks':len(fallback_rows),'checked_scans':checks},indent=2))
if __name__=='__main__':main()
