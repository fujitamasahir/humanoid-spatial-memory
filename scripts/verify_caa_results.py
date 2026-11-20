"""Post-run read-only artifact/safety checks and descriptive clock diagnostics.

No policy changes, outcome-dependent parameter choices or new simulator runs.
"""
from __future__ import annotations
import hashlib,json,sys
from collections import Counter
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from caa_common import ROOT,OUT,write,manifest,verify_manifest,sha,episode,fit,ref
from spatial_memory.phase15_bprime_protocol import digest


def main():
    import run_caa_fit72 as matrix
    matrix.gate();target=OUT/'verification';target.mkdir(parents=True,exist_ok=False)
    audit=fit.verify_original_data_integrity();stores=[]
    import gzip
    for s in audit['stores']:
        directory=ROOT/s['path'];records={}
        for p in (directory/'records').glob('*.json.gz'):
            body=json.loads(gzip.decompress(p.read_bytes()));ident=body['identity'];payload=body['payload']
            if payload['partition']!='fit' or payload['identity']!=ident or body['payload_sha256']!=digest(payload) or p.name!=hashlib.sha256(ident.encode()).hexdigest()+'.json.gz' or ident in records:raise RuntimeError('FIT payload identity/digest mismatch')
            records[ident]=payload
        ids=set();sequences=set()
        for p in (directory/'recovered').glob('attempt-*.json'):
            entry=json.loads(p.read_text());job=entry['job'];ident=job['identity'];seq=job['sequence']
            if ident not in records or ident in ids or seq in sequences or p.name!=f'attempt-{seq+1}.json' or entry['run_id']!=s['run_id']:raise RuntimeError('Receipt mismatch')
            if any(records[ident].get(k)!=job.get(k) for k in ('partition','mechanism','index')):raise RuntimeError('Receipt payload disagreement')
            ids.add(ident);sequences.add(seq)
        if ids!=set(records) or len(ids)!=s['records']:raise RuntimeError('Pair coverage mismatch')
        stores.append({'path':s['path'],'pairs':len(ids),'inventory_sha256':s['inventory_sha256']})
    counts={};checked=0
    for folder in ('retrospective','periodic_replay_prefreeze_v1','periodic_replay_prefreeze_v2','periodic_replay','smoke','fit72'):
        counts[folder]={'manifest_files':verify_manifest(OUT/folder),'episodes':0}
        for p in (OUT/folder).glob('episode_*.json.gz'):
            e=json.loads(gzip.decompress(p.read_bytes()));matrix.safety(e['row'],e['trace'],e['diagnostics'])
            checked+=1;counts[folder]['episodes']+=1
    changed=[];slow_equal=0;class_effects=[]
    for n in range(1,73):
        base=episode(OUT/'fit72',n,'age5');slow=episode(OUT/'fit72',n,'caa_slow')
        if base['trace']==slow['trace']:slow_equal+=1
        for arm in ('caa_fast','caa_full'):
            e=episode(OUT/'fit72',n,arm)
            a=[f['step'] for f in base['trace']['steps'] if f['observation_granted']]
            b=[f['step'] for f in e['trace']['steps'] if f['observation_granted']]
            if a!=b or e['row']['travel_distance_m']!=base['row']['travel_distance_m']:
                common_steps=sorted(set(f['step'] for f in base['trace']['steps'])&set(f['step'] for f in e['trace']['steps']))
                bf={f['step']:f for f in base['trace']['steps']};ef={f['step']:f for f in e['trace']['steps']}
                first=next((t for t in common_steps if bf[t]['action']!=ef[t]['action'] or bf[t]['position']!=ef[t]['position'] or bf[t]['heading_yaw']!=ef[t]['heading_yaw']),None)
                changed.append({'episode':n,'arm':arm,'identity':base['row']['world_identity'],'schedule':base['row']['schedule'],'baseline_scan_steps':a,'candidate_scan_steps':b,'baseline_scans':len(a),'candidate_scans':len(b),'baseline_steps':base['row']['elapsed_steps'],'candidate_steps':e['row']['elapsed_steps'],'baseline_distance_m':base['row']['travel_distance_m'],'candidate_distance_m':e['row']['travel_distance_m'],'first_action_pose_heading_difference':first,'advanced_decisions':[d for d in e['diagnostics']['decisions'] if d.get('request_advanced_vs_uniform5')]})
        full=episode(OUT/'fit72',n,'caa_full');fast=episode(OUT/'fit72',n,'caa_fast')
        fd={d['step']:d for d in full['diagnostics']['decisions']};ad={d['step']:d for d in fast['diagnostics']['decisions']}
        for t in set(fd)&set(ad):
            if fd[t]['granted']!=ad[t]['granted']:class_effects.append({'episode':n,'step':t,'full_granted':fd[t]['granted'],'fast_granted':ad[t]['granted'],'full_local_classes':fd[t].get('local_class_counts'),'full_score':fd[t].get('score'),'fast_score':ad[t].get('score'),'same_history_not_assumed':True})
    write(target/'clock_changes.json',{'changed_episode_arms':changed,'slow_full_trace_equal_age5':slow_equal,'full_vs_fast_grant_differences':class_effects,'caveat':'Descriptive post-run timing/path associations. Per-decision attribution uses same-state uniform5; cross-policy histories may differ.'})
    # Display ALL changed keys, not a selected favorable outcome.
    for n in sorted({r['episode'] for r in changed}):
        fig,(path_ax,time_ax)=plt.subplots(1,2,figsize=(12,5))
        for j,arm in enumerate(('age5','caa_fast','caa_slow','caa_full')):
            e=episode(OUT/'fit72',n,arm);frames=e['trace']['steps'];positions=[f['position'] for f in frames]
            path_ax.plot(*zip(*positions),'-o',ms=3,label=arm,alpha=.7)
            scans=[f['step'] for f in frames if f['observation_granted']]
            time_ax.scatter(scans,[j]*len(scans),marker='|',s=200)
        e=episode(OUT/'fit72',n,'age5');key=e['trace']['key'];path_ax.set_aspect('equal');path_ax.legend();path_ax.set_xlabel('grid x (0.75 m/cell)');path_ax.set_ylabel('grid y')
        time_ax.set_yticks(range(4),('age5','caa_fast','caa_slow','caa_full'));time_ax.set_xlim(-1,81);time_ax.set_xlabel('Decision step; each mark is an actual paid scan');time_ax.set_title('Observation clocks, including initial scan')
        fig.suptitle(f'Descriptive changed key: {":".join(key[0].split(":")[-2:])}, schedule{key[1]}');fig.tight_layout();fig.savefig(target/f'changed_key_{n:03}.png',dpi=170);plt.close(fig)
    frozen=json.loads((OUT/'protocol_binding.json').read_text())
    if frozen['source_sha256']!=matrix.fingerprints():raise RuntimeError('Frozen source changed')
    env=json.loads((ROOT/'results/phase2_mujoco/c_v21_multistep_v1/environment/verification.json').read_text())
    for asset in env['g1_assets']:
        if sha(ROOT/asset['path'])!=asset['sha256']:raise RuntimeError('G1 asset changed')
    write(target/'integrity.json',{'status':'PASS','original_pairs':sum(s['pairs'] for s in stores),'stores':stores,'protected_phase15':ref.navigation.verify_preserved_prefix(),'episode_checks':checked,'folders':counts,'formal_actual_sensor_instrumented_episodes':518,'frozen_source_files_unchanged':len(frozen['source_sha256']),'g1_assets_unchanged':len(env['g1_assets']),'previous_cadence_manifest_files':verify_manifest(matrix.HIST),'reserved_or_new_cohort_access':False,'postprocessing_source_sha256':sha(__file__)})
    manifest(target);print(json.dumps({'status':'PASS','pairs':sum(s['pairs'] for s in stores),'episodes_checked':checked,'changed_keys':sorted({r['episode'] for r in changed}),'slow_exact_trace_matches':slow_equal},indent=2))
if __name__=='__main__':main()
