"""Saved FIT trace audit before RAA design; no omitted readings or simulation."""
import json,gzip,sys
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from c_v21_common import write,sha,manifest,verify_manifest
from run_c_v21a_depth_ablation import episode
OLD=ROOT/'results/phase2_mujoco/history_gated_deadline_fit72_v1'
OUT=ROOT/'results/phase2_mujoco/raa_v1/prior_audit'


def main():
    OUT.mkdir(parents=True,exist_ok=False);verify_manifest(OLD/'fit72');verify_manifest(OLD/'analysis')
    rows=[];counts=Counter()
    for n in range(1,73):
        parent=episode(OLD/'fit72',n,'age5');a={f['step']:f for f in parent['trace']['steps']}
        for arm in ('deadline','deadline_stable','deadline_stable_quiet'):
            e=episode(OLD/'fit72',n,arm);b={f['step']:f for f in e['trace']['steps']};both=sorted(a.keys()&b.keys())
            first=lambda key:next((t for t in both if a[t][key]!=b[t][key]),None)
            scans=[f['step'] for f in e['trace']['steps'] if f['observation_granted']];baseline_scans=[f['step'] for f in parent['trace']['steps'] if f['observation_granted']]
            blocks=[f for f in e['trace']['steps'] if f['blocked']]
            # Rejections of identical action from identical public pose/heading.
            prior={t:(b[t-1]['position'],b[t-1]['heading_yaw']) for t in b if t-1 in b}
            keys=[str((prior.get(f['step']),f['action'])) for f in blocks];repeated=sum(v-1 for v in Counter(keys).values())
            r={'episode':n,'identity':e['row']['world_identity'],'schedule':e['row']['schedule'],'candidate':arm,
               'parent_success':bool(parent['row']['success']),'candidate_success':bool(e['row']['success']),
               'first_scan_difference':first('observation_granted'),'first_action_difference':first('action'),
               'first_position_difference':first('position'),'first_heading_difference':first('heading_yaw'),
               'parent_scan_steps':baseline_scans,'candidate_scan_steps':scans,
               'parent_blocked':parent['row']['g1_footprint_blocked_attempts'],'candidate_blocked':len(blocks),
               'repeated_exact_pose_heading_action_rejections':repeated,'blocked_action_reasons':e['row']['g1_blocked_movement_reasons'],
               'parent_steps':parent['row']['elapsed_steps'],'candidate_steps':e['row']['elapsed_steps']}
            if parent['row']['success'] and not e['row']['success']:
                t=r['first_scan_difference'];r['candidate_decision_at_first_scan_difference']=next((d for d in e['diagnostics']['decisions'] if d['step']==t),None)
                rows.append(r);counts[arm+'_harms']+=1
                if t is not None and t<baseline_scans[1]+1:counts[arm+'_first_noninitial_window']+=1
    write(OUT/'harm_divergences.json',rows)
    write(OUT/'summary.json',{'harm_pairs':len(rows),'counts':dict(counts),'new_navigation_episodes':0,
       'missing_evidence':['Per-cell before/after maps and omitted scan readings were not saved in these traces.','Nominal point route does not establish actual G1 clearance.'],
       'interpretation':'Denied Age5 requests, subsequent changed actions and repeated blocks are associations. Single-omission hand-fixture masks do not compose into a robust rollout. No causal rescue is inferred.'})
    manifest(OUT);print(json.dumps(dict(counts),indent=2))
if __name__=='__main__':main()
