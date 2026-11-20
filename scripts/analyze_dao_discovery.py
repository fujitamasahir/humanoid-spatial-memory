"""Saved-evidence discovery audit only. No policy evaluation or simulator runs."""
from __future__ import annotations
import csv, gzip, json, sys
from collections import defaultdict
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'scripts')]
from c_v21_common import sha, write, manifest
from spatial_memory.navigation import plan
import phase2_mujoco_navigation as navigation
OUT = ROOT/'results/phase2_mujoco/dao_v1/retrospective'


def load(path):
    return json.loads(gzip.decompress(path.read_bytes()))


def stats(values):
    return dict(zip(('min','q25','median','q75','max'), map(float, np.quantile(values, [0,.25,.5,.75,1])))) if values else None


def csv_write(path, rows):
    with path.open('x', newline='') as f:
        writer=csv.DictWriter(f, fieldnames=sorted(set().union(*(r.keys() for r in rows))))
        writer.writeheader(); writer.writerows(rows)


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    goals={w['identity']:tuple(w['world']['goal']) for w in navigation.admitted_worlds()}
    scan_rows=[]; episode_rows=[]; sources=[]; coverage=defaultdict(int)
    for arm in ('age4','age5','caa_fast','caa_slow','caa_full'):
        for n in range(1,73):
            path=ROOT/f'results/phase2_mujoco/caa_v1/fit72/episode_{n:03}_{arm}.json.gz'
            e=load(path); sources.append({'path':str(path.relative_to(ROOT)), 'sha256':sha(path)})
            rich=None
            if arm in ('age4','age5'):
                rp=ROOT/f'results/phase2_mujoco/caa_v1/retrospective/episode_{n:03}_{arm}.json.gz'
                rich=load(rp);sources.append({'path':str(rp.relative_to(ROOT)), 'sha256':sha(rp)})
                assert rich['trace']==e['trace'] and rich['diagnostics']['observation_log']==[{k:v for k,v in s.items() if k!='history_after_scan'} for s in e['diagnostics']['observation_log']]
            frames={f['step']:f for f in (rich['diagnostics']['retrospective_frames'] if rich else [])}
            trace={f['step']:f for f in e['trace']['steps']}; scans=e['diagnostics']['observation_log']; row=e['row']; prev=0
            for index, scan in enumerate(scans):
                t=scan['step']; pose=trace[max(0,t-1)]; after=trace[t]
                r={'arm':arm,'episode':n,'identity':row['world_identity'],'schedule':row['schedule'],
                   'initial':index==0,'scan_index':index,'step':t,'interval':t-prev if index else None,
                   'progress_bin':min(3,t//20),'elapsed_fraction':t/max(1,row['elapsed_steps']),
                   'pre_action_x':pose['position'][0],'pre_action_y':pose['position'][1],
                   'pre_action_yaw':pose['heading_yaw'],'success':row['success'],
                   'blocked_at_scan_step':after['blocked'],
                   'temporal_action_changed':after['action']!=pose['action'],
                   'next_step_blocked':trace.get(t+1,{}).get('blocked'), **scan}
                r.pop('history_after_scan',None)
                r.update(near_route_new=None, public_map_changed_cells=None, nominal_route_changed=None,
                         nominal_first_move_changed=None, immediate_actual_action_causal_effect=None)
                if t>0 and frames:
                    before=np.asarray(frames[t-1]['memory']); updated=np.asarray(frames[t]['memory'])
                    new=(before==-1)&(updated>=0); changed=(before>=0)&(updated>=0)&(before!=updated)
                    assert int(new.sum())==scan['new_cells'] and int(changed.sum())==scan['changed_known_cells']
                    pos=tuple(pose['position']);goal=goals[row['world_identity']]
                    a=plan(before,pos,goal,'optimistic');b=plan(updated,pos,goal,'optimistic')
                    ys,xs=np.where(new); prefix=a[1:6]
                    r.update(near_route_new=sum(any(abs(int(x)-u)+abs(int(y)-v)<=1 for u,v in prefix) for x,y in zip(xs,ys)),
                             public_map_changed_cells=int(new.sum()+changed.sum()),nominal_route_changed=a!=b,
                             nominal_first_move_changed=(a[1] if len(a)>1 else None)!=(b[1] if len(b)>1 else None))
                    coverage['rich_noninitial_scans']+=1
                elif t>0:
                    coverage['noninitial_scans_without_saved_cell_rasters']+=1
                scan_rows.append(r);prev=t
            noninitial=scans[1:]
            episode_rows.append({'arm':arm,'episode':n,'identity':row['world_identity'],'schedule':row['schedule'],
                'success':row['success'],'h80_steps':row['elapsed_steps'],'distance_m':row['travel_distance_m'],
                'blocked':row['g1_footprint_blocked_attempts'],'paid':len(scans),
                'new_cells_noninitial':sum(s['new_cells'] for s in noninitial),
                'new_per_noninitial_scan':sum(s['new_cells'] for s in noninitial)/len(noninitial) if noninitial else None})
    by_arm={}
    for arm in ('age4','age5','caa_fast','caa_slow','caa_full'):
        scans=[r for r in scan_rows if r['arm']==arm and not r['initial']];eps=[r for r in episode_rows if r['arm']==arm]
        by_arm[arm]={'episodes':72,'initial_scans':72,'noninitial_scans':len(scans),
           'new_cells_per_scan':stats([s['new_cells'] for s in scans]),
           'changed_known_per_scan':stats([s['changed_known_cells'] for s in scans]),
           'scan_intervals':stats([s['interval'] for s in scans]),
           'new_cells_total':sum(s['new_cells'] for s in scans),
           'with_new':sum(s['new_cells']>0 for s in scans),
           'with_changed_known':sum(s['changed_known_cells']>0 for s in scans),
           'unchanged_only':sum(s['only_unchanged_known'] for s in scans),
           'progress_bins':[{ 'steps':f'{20*b}-{80 if b==3 else 20*b+19}', 'scans':len(v:=[s for s in scans if s['progress_bin']==b]),
                             'mean_new':float(np.mean([s['new_cells'] for s in v])) if v else None,
                             'new_total':sum(s['new_cells'] for s in v)} for b in range(4)],
           'completion_strata':[{'success':outcome,'episodes':len(v:=[e for e in eps if e['success']==outcome]),
                  'mean_new_per_scan':float(np.mean([e['new_per_noninitial_scan'] for e in v if e['new_per_noninitial_scan'] is not None])) if v else None,
                  'mean_blocked':float(np.mean([e['blocked'] for e in v])) if v else None,
                  'mean_h80':float(np.mean([e['h80_steps'] for e in v])) if v else None} for outcome in (True,False)]}
        rich=[s for s in scans if s['near_route_new'] is not None]
        by_arm[arm]['saved_raster_route_audit']={'scans':len(rich),'new_near_route_total':sum(s['near_route_new'] for s in rich),
            'nominal_route_changes':sum(s['nominal_route_changed'] for s in rich),
            'nominal_first_move_changes':sum(s['nominal_first_move_changed'] for s in rich)} if rich else None
        by_arm[arm]['scan_content_strata']=[{'has_discovery':has,'scans':len(v:=[s for s in scans if (s['new_cells']>0)==has]),
            'blocked_scan_step':sum(s['blocked_at_scan_step'] for s in v),
            'next_step_blocked':sum(bool(s['next_step_blocked']) for s in v),
            'temporal_action_changes':sum(s['temporal_action_changed'] for s in v)} for has in (True,False)]
    csv_write(OUT/'scan_records.csv',scan_rows);csv_write(OUT/'episode_records.csv',episode_rows)
    # Include each stored available replication in an inventory, but never pool it.
    replicas=[{'path':str(p.relative_to(ROOT)),'sha256':sha(p),'role':'smoke_duplicate_not_pooled'}
              for p in sorted((ROOT/'results/phase2_mujoco/caa_v1/smoke').glob('episode_*.json.gz'))]
    write(OUT/'source_inventory.json',{'primary_and_rich_sources':sources,'replications_not_pooled':replicas})
    write(OUT/'summary.json',{'arms':by_arm,'coverage':dict(coverage),'episodes':len(episode_rows),
       'all_scan_records_including_initial':len(scan_rows),'new_simulator_runs':0,
       'caveats':['Discovery and changed-known categories overlap.',
       'Pre-action pose/heading uses frame t-1, not post-action frame t.',
       'CAA cell rasters/routes were not saved; spatial route analysis is missing, not inferred.',
       'Offline point-grid nominal routes at identical pre-action pose are proxies, not the actual G1 action plan.',
       'Unchanged-only readings verify knowledge; lack of immediate action change is not proof of uselessness.',
       'Survival/exposure, policy-conditioned discovery and two correlated schedules preclude causal efficacy inference.']})
    import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(11,4))
    for arm,s in by_arm.items():
        values=[r['new_cells'] for r in scan_rows if r['arm']==arm and not r['initial']]
        x=np.sort(values);axes[0].step(x,np.arange(1,len(x)+1)/len(x),label=arm)
        axes[1].plot(range(4),[v['mean_new'] for v in s['progress_bins']],'-o',label=arm)
    axes[0].set(xlabel='New cells per noninitial actual scan',ylabel='Empirical cumulative fraction')
    axes[1].set(xlabel='Absolute decision bin (0=steps 0–19)',ylabel='Mean new cells per actual scan');axes[0].legend();fig.tight_layout();fig.savefig(OUT/'discovery.png',dpi=160);plt.close(fig)
    manifest(OUT);print(json.dumps({'episodes':len(episode_rows),'coverage':dict(coverage),'arms':{a:{k:v[k] for k in ('noninitial_scans','with_new','with_changed_known','unchanged_only')} for a,v in by_arm.items()}},indent=2))
if __name__=='__main__':main()
