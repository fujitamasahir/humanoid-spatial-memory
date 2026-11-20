"""Post-run mechanism diagnostics only; no new policy or simulator call."""
import json,sys
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src')]
from c_v21_common import write,manifest,verify_manifest
from run_c_v21a_depth_ablation import episode
OUT=ROOT/'results/phase2_mujoco/raa_v1'


def main():
    verify_manifest(OUT/'fit72');target=OUT/'mechanisms';target.mkdir(parents=True,exist_ok=False)
    nav_fields=('action','action_reason','position','heading_yaw','moved','blocked','contacts')
    same=0;savings=[];failures=[];joint_equal=0;certificates=Counter()
    for n in range(1,73):
        parent=episode(OUT/'fit72',n,'age5');defer=episode(OUT/'fit72',n,'raa_defer');advance=episode(OUT/'fit72',n,'raa_advance');joint=episode(OUT/'fit72',n,'raa_joint')
        same+=len(parent['trace']['steps'])==len(defer['trace']['steps']) and all(all(a[k]==b[k] for k in nav_fields) for a,b in zip(parent['trace']['steps'],defer['trace']['steps']))
        joint_equal+=advance['trace']==joint['trace']
        for d in defer['diagnostics']['decisions']:
            if d.get('point_plan_calls'):
                for key in ('route_available','prefix_free_fresh5','predicted_view_known_fresh5','prefix_recent_change'):certificates[key]+=int(d.get(key,False))
            if d.get('deferred'):
                p=next(s for s in parent['diagnostics']['observation_log'] if s['step']==d['step'])
                f=next(f for f in defer['trace']['steps'] if f['step']==d['step'])
                savings.append({'episode':n,'identity':parent['row']['world_identity'],'schedule':parent['row']['schedule'],
                    'deferred_decision':d,'parent_actual_scan_content':p,'terminal_step':d['step']==defer['row']['elapsed_steps'],
                    'goal_reached':defer['row']['success'],'final_action':f['action'],
                    'parent_paid':parent['row']['observation_count'],'candidate_paid':defer['row']['observation_count']})
        if parent['row']['success'] and not advance['row']['success']:
            a={s['step']:s for s in parent['trace']['steps']};b={s['step']:s for s in advance['trace']['steps']};both=sorted(a.keys()&b.keys())
            first=lambda key:next((t for t in both if a[t][key]!=b[t][key]),None)
            blocks=[f for f in advance['trace']['steps'] if f['blocked']]
            blockkeys=[str((b[f['step']-1]['position'],b[f['step']-1]['heading_yaw'],f['action'])) for f in blocks]
            ds=advance['diagnostics']['decisions'];t=first('observation_granted')
            failures.append({'episode':n,'identity':parent['row']['world_identity'],'schedule':parent['row']['schedule'],
                'first_scan_difference':t,'first_action_difference':first('action'),'first_pose_difference':first('position'),
                'first_heading_difference':first('heading_yaw'),
                'first_different_scan_decision':next((d for d in ds if d['step']==t),None),
                'parent_paid':parent['row']['observation_count'],'advance_paid':advance['row']['observation_count'],
                'first_budget_exhausted_decision':next((d['step'] for d in ds if d['used_before']>=20),None),
                'parent_last_scan':parent['diagnostics']['actual_memory_call_steps'][-1],
                'advance_last_scan':advance['diagnostics']['actual_memory_call_steps'][-1],
                'parent_blocks':parent['row']['g1_footprint_blocked_attempts'],'advance_blocks':len(blocks),
                'repeated_identical_pose_action_rejections':sum(v-1 for v in Counter(blockkeys).values()),
                'action_counts':dict(Counter((f['action'][0] if f['action'] else 'none') for f in b.values())),
                'parent_steps':parent['row']['elapsed_steps'],'advance_steps':advance['row']['elapsed_steps'],
                'scan_content':advance['diagnostics']['observation_log']})
    assert same==72 and joint_equal==72 and len(savings)==2 and len(failures)==7
    write(target/'summary.json',{'defer_exact_navigation_trace_matches_parent':same,'advance_joint_exact_full_trace_matches':joint_equal,
        'savings':savings,'advance_parent_success_harms':failures,'defer_feature_counts':dict(certificates),
        'interpretation':'Defer savings are two terminal scans in one maze lineage/two schedules. Parent readings each discover one new cell despite predicted zero unknowns; not proven useless scans. Advance timing/action/budget associations are not isolated causal interventions.',
        'additional_revision_triggered':False,'reason':'Defer meets predeclared immediate target; further tuning is not authorized by the failure-only revision condition.'})
    manifest(target);print('Verified72 Defer navigation traces unchanged;2 terminal omissions;7 Advance harms;Advance=Joint all72.')
if __name__=='__main__':main()
