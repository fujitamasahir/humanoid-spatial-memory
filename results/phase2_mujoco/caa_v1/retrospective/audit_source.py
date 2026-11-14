"""Pre-implementation retrospective Age/Age-5 mechanism audit; no CAA import."""
from __future__ import annotations
import json
from collections import Counter
from caa_common import ROOT,OUT,HIST,write,manifest,verify_manifest,sha,commit,episode,parity,run_case,ref,fit


def main():
    target=OUT/'retrospective';target.mkdir(parents=True,exist_ok=False)
    integrity=fit.verify_original_data_integrity();verify_manifest(HIST)
    _,_,prov,_=ref.base.load_baseline();config=ref.base.frozen_config(prov)
    worlds={w['identity']:w for w in ref.navigation.admitted_worlds()}
    changed=[];rows=[];all_counts={a:Counter() for a in ('age4','age5')}
    for n in range(1,73):
        saved=episode(HIST,n,'age');ident,schedule,_,_=saved['trace']['key'];runs={}
        for arm,label in [('age4','age'),('age5','age5')]:
            row,trace,diag=run_case(worlds[ident],schedule,arm,config,capture_frames=True)
            parity(episode(HIST,n,label),row,trace)
            fit.save_episode(target,n,arm,row,trace,diag);runs[arm]=(row,trace,diag)
            scans=diag['observation_log'];noninitial=scans[1:]
            counts={'noninitial_scans':len(noninitial),'scans_with_new_cells':sum(s['new_cells']>0 for s in noninitial),'scans_with_changed_known':sum(s['changed_known_cells']>0 for s in noninitial),'scans_only_unchanged_known':sum(s['only_unchanged_known'] for s in noninitial),'empty_scans':sum(s['empty'] for s in noninitial),'new_cells':sum(s['new_cells'] for s in noninitial),'changed_known_cells':sum(s['changed_known_cells'] for s in noninitial),'unchanged_known_cells':sum(s['unchanged_known_cells'] for s in noninitial),'budget_exhausted_decisions':sum(d['used_before']>=20 for d in diag['decisions'])}
            all_counts[arm].update(counts);rows.append({'episode':n,'arm':arm,'identity':ident,'schedule':schedule,**counts})
        a,b=runs['age4'],runs['age5']
        if bool(a[0]['success'])!=bool(b[0]['success']):
            af={f['step']:f for f in a[1]['steps']};bf={f['step']:f for f in b[1]['steps']};both=sorted(set(af)&set(bf))
            ma={f['step']:f for f in a[2]['retrospective_frames']};mb={f['step']:f for f in b[2]['retrospective_frames']}
            import numpy as np
            first=lambda predicate:next((t for t in both if predicate(t)),None)
            entry={'episode':n,'identity':ident,'schedule':schedule,'age_success':bool(a[0]['success']),'age5_success':bool(b[0]['success']),'first_scan_divergence':first(lambda t:af[t]['observation_granted']!=bf[t]['observation_granted']),'first_memory_divergence':first(lambda t:not np.array_equal(ma[t]['memory'],mb[t]['memory'])),'first_action_divergence':first(lambda t:af[t]['action']!=bf[t]['action']),'first_position_divergence':first(lambda t:af[t]['position']!=bf[t]['position']),'first_heading_divergence':first(lambda t:af[t]['heading_yaw']!=bf[t]['heading_yaw']), 'per_arm':{}}
            for arm,(row,trace,diag) in runs.items():
                entry['per_arm'][arm]={'scans':row['observation_count'],'steps':row['elapsed_steps'],'blocked':row['g1_footprint_blocked_attempts'],'emergency_interventions':row['emergency_safety_interventions'],'stale_occupied_cell_times':sum(f['stale_occupied_cells'] for f in diag['retrospective_frames']),'stale_free_cell_times':sum(f['stale_free_cells'] for f in diag['retrospective_frames']),'budget_exhausted_decisions':sum(d['used_before']>=20 for d in diag['decisions']),'scan_content':diag['observation_log']}
            changed.append(entry)
        if n%12==0:print(f'Audit {n}/72: exact Age/Age-5 replay parity',flush=True)
    expected_rescues={('M:80030009',0),('M:80030009',1),('R:80000000',0)}
    expected_harms={('BP:80010012',0),('BP:80010012',1),('M:80030000',1)}
    key=lambda r:(':'.join(r['identity'].split(':')[-2:]),r['schedule'])
    if {key(r) for r in changed if r['age5_success']}!=expected_rescues or {key(r) for r in changed if not r['age5_success']}!=expected_harms:raise RuntimeError('Provided outcome-flip set does not match saved evidence')
    fit.csv_write(target/'all72_observation_content.csv',rows)
    write(target/'summary.json',{'status':'PASS_EXACT_144_REPLAYS','source_commit':commit(),'all72_counts':{a:dict(v) for a,v in all_counts.items()},'changed_outcomes':changed,'interpretation':'Observational timing/content associations, not causal interventions. New and changed-known scan categories can overlap. Initial scans reported separately in episode logs. Stale occupied/free uses evaluator raster occupancy including current people, not hidden online labels.','integrity':{'checkpoint_receipt_pairs':sum(s['records'] for s in integrity['stores']),'protected':ref.navigation.verify_preserved_prefix()}})
    fit.verify_original_data_integrity();manifest(target)
if __name__=='__main__':main()
