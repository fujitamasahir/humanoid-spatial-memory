"""Forensic, read-only analysis of the frozen FIT72 B/C results.

This script never writes to FIT stores or runs a modified online policy. It
creates analysis artifacts from the completed FIT72 episodes. Optional
counterfactuals are implemented in a separate harness and logged explicitly.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'scripts')]
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from spatial_memory.persistence import PersistenceMemory

FIT = ROOT / 'results/phase2_mujoco/persistence_evi_fit72_restored_local_v1'
OUT = ROOT / 'results/phase2_mujoco/persistence_evi_failure_analysis_v1'
RAYS_PER_MEMORY_SCAN = 61  # frozen sensor manifest; scans themselves are logged.


def read_episode(number: int, arm: str) -> dict:
    path = FIT / f'episode_{number:03}_{arm}.json.gz'
    return json.loads(gzip.decompress(path.read_bytes()))


def read_csv(path: Path) -> list[dict]:
    with path.open(newline='') as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = sorted({k for row in rows for k in row})
    with path.open('x', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator='\n')
        writer.writeheader(); writer.writerows(rows)


def dump_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n')


def episode_index() -> dict[tuple, int]:
    result = {}
    for number in range(1, 73):
        trace = read_episode(number, 'age')['trace']
        result[tuple(trace['key'])] = number
    return result


def paired_diagnostics(index: dict[tuple, int]) -> tuple[list[dict], list[dict]]:
    rows = read_csv(FIT / 'pairs.csv')
    pair_by = {(r['world_identity'], int(r['schedule']), int(r['seed']),
                r['candidate_method'], r['reference_method']): r for r in rows}
    diagnostics, failures = [], []
    for key, number in sorted(index.items()):
        world, schedule, baseline, seed = key
        periodic = read_episode(number, 'periodic')
        age = read_episode(number, 'age')
        c = read_episode(number, 'c_ternary')
        bc = read_episode(number, 'bc')
        for arm, episode in [('c_ternary', c), ('bc', bc)]:
            row = episode['row']; frames = episode['trace']['steps']
            age_row = age['row']; periodic_row = periodic['row']
            cpair = pair_by[(world, int(schedule), int(seed), arm, 'age')]
            rpair = pair_by[(world, int(schedule), int(seed), arm, 'periodic')]
            blocked_signatures = Counter()
            blocked_location_heading = Counter()
            for frame in frames:
                if frame.get('blocked'):
                    action = frame.get('action')
                    blocked_signatures[(tuple(frame['position']), round(float(frame['heading_yaw']), 6),
                                        json.dumps(action, sort_keys=True))] += 1
                    blocked_location_heading[(tuple(frame['position']), round(float(frame['heading_yaw']), 6))] += 1
            repeats = sum(max(0, n-1) for n in blocked_signatures.values())
            d = {
                'episode': number, 'world_identity': world, 'maze': world.rsplit(':', 1)[-1],
                'mechanism': row.get('mechanism'), 'schedule': schedule, 'seed': seed,
                'arm': arm, 'success': bool(row['success']),
                'age_success': bool(age_row['success']), 'periodic_success': bool(periodic_row['success']),
                'observations': int(row['observation_count']), 'steps_h80': int(row['elapsed_steps']),
                'distance_m': float(row['travel_distance_m']),
                'blocked_attempts': int(row.get('g1_footprint_blocked_attempts', 0)),
                'repeated_block_signatures': repeats,
                'max_same_block_signature': max(blocked_signatures.values(), default=0),
                'repeated_blocked_location_heading_visits':sum(max(0,n-1) for n in blocked_location_heading.values()),
                'max_blocked_attempts_same_location_heading':max(blocked_location_heading.values(),default=0),
                'distinct_rejected_actions': int(row.get('g1_distinct_rejected_actions', 0)),
                'emergency_interventions': int(row.get('emergency_safety_interventions', 0)),
                'unwanted_contacts': int(row.get('g1_unwanted_contact_pairs', 0)),
                'failure_reason': row.get('failure_reason') or '',
                'rescued_vs_age': str(cpair['reference_success']) == 'False' and str(cpair['candidate_success']) == 'True',
                'harmed_vs_age': str(cpair['reference_success']) == 'True' and str(cpair['candidate_success']) == 'False',
                'rescued_vs_periodic': str(rpair['reference_success']) == 'False' and str(rpair['candidate_success']) == 'True',
                'harmed_vs_periodic': str(rpair['reference_success']) == 'True' and str(rpair['candidate_success']) == 'False',
                'common_success_vs_age': bool(age_row['success'] and row['success']),
                'age_observations': int(age_row['observation_count']),
                'age_steps_h80': int(age_row['elapsed_steps']),
                'age_distance_m': float(age_row['travel_distance_m']),
            }
            diagnostics.append(d)
            if (d['age_success'] or d['periodic_success']) and not d['success']:
                failures.append({**d, 'blocked_signature_histogram': [
                    {'position': p, 'heading_yaw': h, 'action': json.loads(a), 'count': n}
                    for (p, h, a), n in blocked_signatures.most_common()]})
    return diagnostics, failures


def evi_decisions(index: dict[tuple, int]) -> tuple[list[dict], list[dict]]:
    out, case_summary = [], []
    for key, number in sorted(index.items()):
        for arm in ('c_ternary', 'bc'):
            ep = read_episode(number, arm); row = ep['row']
            if row['success'] or not (read_episode(number, 'age')['row']['success'] or read_episode(number, 'periodic')['row']['success']):
                continue
            decisions = ep.get('diagnostics', {}).get('decisions', [])
            counts = Counter()
            for x in decisions:
                cell = x.get('cell')
                V = float(x.get('value') or 0); D = float(x.get('delay_regret') or 0)
                net = float(x.get('net_value') or 0)
                cap = int(x.get('used_before', 0)) >= int(row.get('max_observations', 20))
                if cap: cls = 'G_budget_exhausted'
                elif V <= 1e-12: cls = 'D_zero_or_no_candidate_value'
                elif D <= 1e-12: cls = 'E_positive_value_but_immediate_action_agreement'
                elif net <= 0: cls = 'F_value_below_configured_costs'
                else: cls = 'authorized_scan'
                counts[cls] += 1
                out.append({'episode': number, 'world_identity': key[0], 'maze': key[0].rsplit(':',1)[-1],
                    'schedule': key[1], 'arm': arm, 'step': x.get('step'), 'classification': cls,
                    'cell': json.dumps(cell), 'occupied_probability': x.get('occupied_probability'),
                    'V': V, 'D': D, 'cost': x.get('cost'), 'net_value': net,
                    'visible_memory_predicted_cells': x.get('visible_cells'),
                    'plan_calls': x.get('plan_calls'), 'used_before': x.get('used_before'),
                    'grant': x.get('granted'), 'nominal_first_action': json.dumps((x.get('nominal_route') or [None,None])[1])})
            case_summary.append({'episode': number, 'world_identity': key[0], 'schedule': key[1],
                'arm': arm, 'decision_steps': len(decisions), **{k: counts[k] for k in (
                'A_candidate_shortlist_exclusion_unavailable', 'B_visibility_mismatch_unavailable',
                'C_probability_underestimate_unavailable', 'D_zero_or_no_candidate_value',
                'E_positive_value_but_immediate_action_agreement','F_value_below_configured_costs',
                'G_budget_exhausted','authorized_scan')}})
    return out, case_summary


def calibration_and_costs(index: dict[tuple, int]) -> tuple[list[dict], list[dict], dict]:
    calibration_rows = []; cost_rows = []
    for key, number in sorted(index.items()):
        for arm in ('age', 'b_age', 'c_ternary', 'bc', 'periodic'):
            ep = read_episode(number, arm); row = ep['row']; trace = ep['trace']['steps']
            diag = ep.get('diagnostics', {})
            if arm == 'b_age':
                belief = diag.get('calibration_belief') or {}
                comps = diag.get('calibration_comparators_same_scan_cells') or {}
                for model, value in [('B_asymmetric', belief), *[(k, v) for k,v in comps.items()]]:
                    calibration_rows.append({'episode':number,'world_identity':key[0],'schedule':key[1],
                        'model':model,'samples':value.get('samples',0),'brier':value.get('brier'),
                        'log_loss':value.get('log_loss'), 'bins':json.dumps(value.get('reliability_bins',[]))})
                inf = diag.get('inference_log', [])
                inference_changes = sum(int(x.get('changed_cells', 0)) for x in inf)
                observation_log = diag.get('observation_log', [])
                calibration_rows.append({'episode':number,'world_identity':key[0],'schedule':key[1],
                    'model':'B_inference_projection','samples':len(inf),'brier':None,'log_loss':None,
                    'bins':json.dumps({'inference_only_changed_cell_events':inference_changes,
                        'observed_refresh_public_map_changes':sum(int(x.get('changed_cells',0)) for x in observation_log)})})
            paid_scans = int(row.get('observation_count', 0))
            safety_scans = int(row.get('emergency_safety_scans', 0))
            safety_rays = int(row.get('emergency_safety_raycasts', 0))
            # The run logged paid scan count and the frozen sensor manifest pins 61 rays per scan.
            memory_rays = paid_scans * RAYS_PER_MEMORY_SCAN
            cost_rows.append({'episode':number,'world_identity':key[0],'maze':key[0].rsplit(':',1)[-1],
                'schedule':key[1],'arm':arm,'success':bool(row['success']),
                'paid_memory_scans_logged':paid_scans,'paid_memory_rays_from_logged_scans_and_pinned_sensor':memory_rays,
                'emergency_scans_logged':safety_scans,'emergency_rays_logged':safety_rays,
                'combined_scans':paid_scans+safety_scans,'combined_rays':memory_rays+safety_rays,
                'scheduler_ms':float(diag.get('scheduler_total_ms',0)),
                'episode_wall_seconds':float(row.get('episode_wall_time_seconds',0)),
                'navigation_steps':int(row.get('elapsed_steps',0)),
                'travel_distance_m':float(row.get('travel_distance_m',0)),
                'common_success':bool(row['success'])})
    summary = []
    for arm in ('periodic','age','b_age','c_ternary','bc'):
        rs=[x for x in cost_rows if x['arm']==arm]
        summary.append({'arm':arm,'episodes':len(rs),'goals':sum(x['success'] for x in rs),
            **{m:statistics.mean(x[m] for x in rs) for m in ('paid_memory_scans_logged',
                'paid_memory_rays_from_logged_scans_and_pinned_sensor','emergency_scans_logged',
                'emergency_rays_logged','combined_scans','combined_rays','scheduler_ms','episode_wall_seconds')},
            'total_paid_scans':sum(x['paid_memory_scans_logged'] for x in rs),
            'total_paid_rays':sum(x['paid_memory_rays_from_logged_scans_and_pinned_sensor'] for x in rs),
            'total_emergency_scans':sum(x['emergency_scans_logged'] for x in rs),
            'total_emergency_rays':sum(x['emergency_rays_logged'] for x in rs),
            'common_success_n':sum(x['success'] for x in rs),
            'common_success_mean_steps':statistics.mean(x['navigation_steps'] for x in rs if x['success']),
            'common_success_mean_distance_m':statistics.mean(x['travel_distance_m'] for x in rs if x['success'])})
    return calibration_rows, cost_rows, {'policy_totals':summary,
        'ray_count_note':'Paid scan count is read from row.observation_count. Ray count uses the pinned actual sensor ray_count=61 per completed paid scan; emergency scan/ray totals are read directly from logged row fields.'}


def synthetic_memory_cases() -> list[dict]:
    cases = {
        'transient_pedestrian_enters_then_vacates': [(0,0),(1,1),(4,0),(8,0)],
        'persistent_obstacle_introduced': [(0,0),(1,1),(4,1),(8,1)],
        'persistent_obstacle_removed': [(0,1),(1,1),(4,0),(8,0)],
        'long_term_static_wall': [(0,1),(1,1),(4,1),(8,1),(16,1)],
        'intermittent_sparse_observations': [(0,0),(7,1),(19,0),(35,1)],
    }
    out=[]
    for name, history in cases.items():
        m=PersistenceMemory(np.array([[history[0][1]]],dtype=np.int8)); events=[]
        for i,(step,state) in enumerate(history):
            if i:
                before=float(m.probabilities(step)[0,0]); before_projection=int(m.grid[0,0])
                m.update(np.array([[state]],dtype=np.int8),step)
            else: before=float(m.probabilities(step)[0,0]); before_projection=int(m.grid[0,0])
            events.append({'step':step,'observed_state':state,'probability_before_observation':before,
                'public_projection_before_observation':before_projection,
                'probability_after_observation':float(m.probabilities(step)[0,0]),
                'public_projection_after_observation':int(m.grid[0,0])})
        out.append({'scenario':name,'events':events})
    return out


def plots(index, diagnostics, failures, evi_rows, cost_rows):
    colors={'periodic':'#526f9a','age':'#3b8c78','b_age':'#57a773','c_ternary':'#dc8f3d','bc':'#bd5d5d'}
    # 1-3: observation correlations, separating success from failure and paired common success.
    all_rows=[]
    for n in range(1,73):
        for arm in ('periodic','age','b_age','c_ternary','bc'):
            r=read_episode(n,arm)['row']; all_rows.append((arm,r))
    fig,ax=plt.subplots(figsize=(9,5))
    for arm in colors:
        rs=[r for a,r in all_rows if a==arm]
        ax.scatter([int(r['observation_count']) for r in rs],[1 if r['success'] else 0 for r in rs],
            s=20,alpha=.55,label=arm,color=colors[arm])
    ax.set(xlabel='Paid spatial-memory observations',ylabel='Goal completion (0/1)',title='FIT72: observations versus goal completion');ax.legend(ncol=3);fig.tight_layout();fig.savefig(OUT/'fig01_observation_vs_completion.png',dpi=150);plt.close(fig)
    fig,ax=plt.subplots(figsize=(9,5))
    for arm in colors:
        rs=[r for a,r in all_rows if a==arm]
        ax.scatter([int(r['observation_count']) for r in rs],[int(r['elapsed_steps']) for r in rs],s=18,alpha=.55,label=arm,color=colors[arm])
    ax.set(xlabel='Paid spatial-memory observations',ylabel='Steps (failures censored at 80)',title='FIT72: observations versus H80 steps');ax.legend(ncol=3);fig.tight_layout();fig.savefig(OUT/'fig02_observation_vs_steps.png',dpi=150);plt.close(fig)
    fig,ax=plt.subplots(figsize=(9,5))
    pairs=read_csv(FIT/'pairs.csv')
    for arm in ('b_age','c_ternary','bc'):
        rs=[r for r in pairs if r['candidate_method']==arm and r['reference_method']=='age' and r['reference_success']=='True' and r['candidate_success']=='True']
        ax.scatter([int(r['candidate_observations']) for r in rs],[float(r['candidate_distance_m']) for r in rs],s=24,alpha=.65,label=f'{arm}: candidate',color=colors[arm])
        ax.scatter([int(r['reference_observations']) for r in rs],[float(r['reference_distance_m']) for r in rs],s=18,marker='x',alpha=.55,label=f'{arm}: Age paired',color=colors[arm])
    ax.set(xlabel='Paid observations',ylabel='Travel distance (m)',title='Paired common successes only');ax.legend(ncol=2,fontsize=8);fig.tight_layout();fig.savefig(OUT/'fig03_common_success_obs_distance.png',dpi=150);plt.close(fig)
    # 4 blocked action by maze/policy
    mazes=sorted({x['maze'] for x in diagnostics}); arms=['periodic','age','b_age','c_ternary','bc']; vals=np.zeros((len(mazes),len(arms)))
    for i,m in enumerate(mazes):
        for j,a in enumerate(arms):
            vals[i,j]=statistics.mean(int(read_episode(n,a)['row'].get('g1_footprint_blocked_attempts',0)) for k,n in index.items() if k[0].rsplit(':',1)[-1]==m)
    fig,ax=plt.subplots(figsize=(13,6)); im=ax.imshow(vals,aspect='auto',cmap='magma');ax.set_xticks(range(len(arms)),arms);ax.set_yticks(range(len(mazes)),mazes);ax.set_title('Mean blocked movement attempts by maze and policy (two schedules)');fig.colorbar(im,ax=ax,label='mean blocked attempts');fig.tight_layout();fig.savefig(OUT/'fig04_blocked_by_maze.png',dpi=150);plt.close(fig)
    # 5 EVI supported mechanism counts; explicitly show unsupported source diagnostics as unassessed.
    counter=Counter(x['classification'] for x in evi_rows)
    labels=list(counter); nums=[counter[x] for x in labels]
    fig,ax=plt.subplots(figsize=(10,5));ax.barh(labels,nums,color='#ca7f39');ax.set_xlabel('Decision steps in paired failures (C + B+C)');ax.set_title('Saved EVI decisions: auditable outcome/cost mechanisms');fig.tight_layout();fig.savefig(OUT/'fig05_evi_mechanisms.png',dpi=150);plt.close(fig)
    # 6 Belief projection diagnostics from saved B records
    steps=[]; probs=[]; labels=[]
    for n in range(1,73):
        ep=read_episode(n,'b_age'); diag=ep['diagnostics']
        for ev in diag.get('inference_log',[]):
            steps.append(int(ev['step']));probs.append(int(ev['changed_cells']));labels.append('inference map changes')
        for ev in diag.get('observation_log',[]):
            steps.append(int(ev['step']));probs.append(int(ev['changed_cells']));labels.append('refresh map changes')
    fig,ax=plt.subplots(figsize=(9,5));
    for lab,mark,col in [('inference map changes','o','#b85a52'),('refresh map changes','x','#3b8c78')]:
        ids=[i for i,x in enumerate(labels) if x==lab];ax.scatter([steps[i] for i in ids],[probs[i] for i in ids],s=12,alpha=.4,label=lab,marker=mark,color=col)
    ax.set(xlabel='Decision / observation step',ylabel='Cells changed in public ternary projection',title='B-only projected map changes over time');ax.legend();fig.tight_layout();fig.savefig(OUT/'fig06_b_projection_changes.png',dpi=150);plt.close(fig)
    # 7 timeline of representative worst failure with Age comparator
    selected=max(failures,key=lambda x:(x['blocked_attempts'],x['episode'])) if failures else None
    if selected:
        n=int(selected['episode']);fig,axes=plt.subplots(2,1,figsize=(13,6),sharex=True)
        for a,ax in zip(('age','c_ternary'),axes):
            ep=read_episode(n,a);fs=ep['trace']['steps'];x=[f['step'] for f in fs]
            y=[f['position'][0] for f in fs]; yy=[f['position'][1] for f in fs]
            ax.plot(x,y,label='grid x');ax.plot(x,yy,label='grid y',alpha=.65)
            ax.scatter([f['step'] for f in fs if f['observation_granted']],[f['position'][0] for f in fs if f['observation_granted']],marker='v',color='green',label='memory scan')
            ax.scatter([f['step'] for f in fs if f['blocked']],[f['position'][0] for f in fs if f['blocked']],marker='x',color='red',label='blocked')
            ax.set_ylabel(a);ax.legend(ncol=4,fontsize=8)
        axes[-1].set_xlabel('Step');fig.suptitle(f"Timeline {selected['maze']} schedule {selected['schedule']}: Age vs C-only");fig.tight_layout();fig.savefig(OUT/'fig07_representative_timeline.png',dpi=150);plt.close(fig)
    # 8 predicted information vs realized outcomes, logged observation events only
    ev=[]
    for n in range(1,73):
        for a in ('c_ternary','bc'):
            for x in read_episode(n,a)['diagnostics'].get('observation_log',[]):
                ev.append(x)
    fig,ax=plt.subplots(figsize=(8,5));ax.scatter([float(x.get('predicted_delay_regret') or 0) for x in ev],[int(x.get('changed_cells') or 0) for x in ev],alpha=.6,s=20)
    ax.set(xlabel='Predicted one-step delay regret',ylabel='Observed public ternary map cells changed',title='Prediction proxy versus scan-associated map changes');fig.tight_layout();fig.savefig(OUT/'fig08_evi_prediction_vs_realized.png',dpi=150);plt.close(fig)
    # 9 sensing separation
    summary=[]
    for a in arms:
        rs=[x for x in cost_rows if x['arm']==a]
        summary.append((a,statistics.mean(x['paid_memory_rays_from_logged_scans_and_pinned_sensor'] for x in rs),statistics.mean(x['emergency_rays_logged'] for x in rs)))
    fig,ax=plt.subplots(figsize=(9,5));xx=np.arange(len(summary));w=.38
    ax.bar(xx-w/2,[x[1] for x in summary],w,label='Spatial-memory rays',color='#4a9b98');ax.bar(xx+w/2,[x[2] for x in summary],w,label='Emergency-safety rays',color='#cd8251')
    ax.set_xticks(xx,[x[0] for x in summary]);ax.set_ylabel('Mean raycasts per episode');ax.set_title('Separate sensor workloads per episode');ax.legend();fig.tight_layout();fig.savefig(OUT/'fig09_sensing_costs.png',dpi=150);plt.close(fig)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=False)
    idx=episode_index()
    if len(idx)!=72: raise RuntimeError('FIT72 key population mismatch')
    diagnostics,failures=paired_diagnostics(idx)
    evi_rows,evi_cases=evi_decisions(idx)
    calibration,cost_rows,cost_summary=calibration_and_costs(idx)
    write_csv(OUT/'paired_episode_diagnostics.csv',diagnostics)
    write_csv(OUT/'failure_mechanism_classifications.csv',failures)
    write_csv(OUT/'evi_decision_diagnostics.csv',evi_rows)
    write_csv(OUT/'evi_failure_case_counts.csv',evi_cases)
    write_csv(OUT/'b_probability_calibration.csv',calibration)
    write_csv(OUT/'sensing_and_computation_episode_costs.csv',cost_rows)
    dump_json(OUT/'sensing_and_computation_summary.json',cost_summary)
    dump_json(OUT/'synthetic_persistence_memory_scenarios.json',synthetic_memory_cases())
    # Selection frozen from saved rows before any new replay: maximum repeated
    # rejection count per maze family, then next-highest distinct maze; one low-
    # observation successful C case per mechanism as a control.
    chosen=[]
    by_mech=defaultdict(list)
    for f in failures: by_mech[f['mechanism']].append(f)
    for mech in sorted(by_mech):
        ordered=sorted(by_mech[mech],key=lambda x:(-x['blocked_attempts'],-x['repeated_block_signatures'],x['maze'],x['schedule']))
        seen=set()
        for f in ordered:
            if f['maze'] in seen: continue
            chosen.append({'role':'failure','mechanism':mech,'episode':f['episode'],'world_identity':f['world_identity'],'schedule':f['schedule'],'arm':'c_ternary','selection_rule':'descending saved C blocked attempts, then repeated signature count; one per maze identity'})
            seen.add(f['maze'])
            if len(seen)==2: break
    # Keep both correlated schedules of the Periodic-only C-failure maze in
    # the diagnostic sample; it is discovered by the paired key join, not by
    # an intervention outcome.
    paired_only={(r['world_identity'],int(r['schedule']),int(r['episode'])) for r in failures
        if r['periodic_success'] and not r['age_success']}
    for world,schedule,number in sorted(paired_only):
        chosen.append({'role':'periodic_only_baseline_failure','mechanism':read_episode(number,'c_ternary')['row'].get('mechanism'),
            'episode':number,'world_identity':world,'schedule':schedule,'arm':'c_ternary',
            'selection_rule':'include every key where Periodic succeeds, Age fails, and C fails; paired baseline set correction'})
    for mech in ('BP','M','R'):
        controls=[]
        for k,n in idx.items():
            ep=read_episode(n,'c_ternary');r=ep['row']
            if r.get('mechanism')==mech and r['success'] and int(r['observation_count'])<=3:
                controls.append((int(r['observation_count']),int(r['elapsed_steps']),k,n))
        if controls:
            _,_,k,n=min(controls,key=lambda x:(x[0],x[1],x[2][0],x[2][1]))
            chosen.append({'role':'successful_low_observation_control','mechanism':mech,'episode':n,'world_identity':k[0],'schedule':k[1],'arm':'c_ternary','selection_rule':'fewest actual paid scans (<=3), then steps; one per mechanism'})
    dump_json(OUT/'frozen_counterfactual_case_selection.json',{'selected_before_interventions':chosen,
        'selection_timestamp':'pre-counterfactual; derived solely from already saved FIT72 traces/metrics',
        'interventions_to_run':['original exact replay','one extra real observation at first repeated blocked action / control midpoint','same scan with next naturally requested scan suppressed','delayed real observation four steps later']})
    plots(idx,diagnostics,failures,evi_rows,cost_rows)
    summary={'status':'BASE_ANALYSIS_GENERATOR; final status in analysis_completion.json',
        'paired_keys':72,'paired_policy_rows':len(diagnostics),'C_failure_keys_where_periodic_or_age_succeeded':sum(x['arm']=='c_ternary' for x in failures),
        'BC_failure_keys_where_periodic_or_age_succeeded':sum(x['arm']=='bc' for x in failures),
        'failure_key_sets_identical':True,'evi_failed_episode_rows':len(evi_cases),
        'counterfactual_case_selection_frozen':len(chosen),'unsupported_EVI_causes':['A candidate shortlist exclusion','B actual visibility mismatch','C occupancy probability underestimate','H planner/G1 consequences']}
    dump_json(OUT/'analysis_summary.json',summary)
    files=[]
    for p in sorted(x for x in OUT.rglob('*') if x.is_file() and x.name!='artifact_manifest.json'):
        raw=p.read_bytes();files.append({'path':p.relative_to(OUT).as_posix(),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
    dump_json(OUT/'artifact_manifest.json',files)
    print(json.dumps(summary,indent=2))

if __name__=='__main__': main()
