"""Frozen, retrospective FIT72 observation-timing diagnostics.

Only the observation grant is overridden at a preselected step. Real MuJoCo
61-ray memory sensing, all planners, G1 checks, and emergency safety remain the
same. This is a post-hoc intervention study, never a deployable policy.
"""
from __future__ import annotations
import gzip, hashlib, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
import evaluate_persistence_evi_fit72 as runner
from spatial_memory.evi import PersistenceEVIController
from spatial_memory.mujoco_perception import MujocoRayPerception

FIT=ROOT/'results/phase2_mujoco/persistence_evi_fit72_restored_local_v1'
ANALYSIS=ROOT/'results/phase2_mujoco/persistence_evi_failure_analysis_v1'
OUT=ANALYSIS/'counterfactuals'

def load_episode(number,arm):
    return json.loads(gzip.decompress((FIT/f'episode_{number:03}_{arm}.json.gz').read_bytes()))

def main():
    cases=json.loads((ANALYSIS/'frozen_counterfactual_case_selection.json').read_text())['selected_before_interventions']
    OUT.mkdir(exist_ok=False)
    worlds={w['identity']:w for w in runner.reference.navigation.admitted_worlds()}
    _,_,prov,_=runner.reference.base.load_baseline();config=runner.reference.base.frozen_config(prov)
    rows=[]; saved_hashes={}; replay_mismatches=[]
    original_decide=PersistenceEVIController.decide
    original_observe=MujocoRayPerception.observe
    try:
      for case in cases:
        number=int(case['episode']);base_arm=case['arm']
        reference_ep=load_episode(number,base_arm)
        frames=reference_ep['trace']['steps']
        is_failure=case['role'] in ('failure','periodic_only_baseline_failure')
        if is_failure:
            first=next((int(f['step']) for f in frames if f.get('blocked')),None)
            if first is None: raise RuntimeError(f'No recorded blocked step for selected failure {number}')
        else:
            goal=reference_ep['row'].get('goal_step') or reference_ep['row']['elapsed_steps']
            first=max(1,int(goal)//2)
        arms=['c_ternary','bc'] if is_failure else ['c_ternary']
        for arm in arms:
          for condition in ('original_exact_replay','extra_scan_at_selected_step','scan_swap_at_selected_step','delayed_extra_scan_four_steps'):
            target=first+(4 if condition=='delayed_extra_scan_four_steps' else 0)
            state={'condition':condition,'target':target,'forced':False,'suppressed':False,
                   'natural_at_target':False,'sensor_events':[]}
            # Capture only the real scan result just returned to the controller.
            def observe(self,world,position,yaw):
                result=original_observe(self,world,position,yaw)
                obs_cells={(int(x),int(y)) for y,x in __import__('numpy').argwhere(result>=0)}
                prior=set().union(*(e['observed_cell_set'] for e in state['sensor_events'])) if state['sensor_events'] else set()
                event={'step':int(world.step),'position':list(position),'rays':int(self.last_stats['ray_count']),
                       'visible_cells':int(self.last_stats['visible_cells']),'ray_hits':int(self.last_stats['ray_hits']),
                       'hits_by_type':self.last_stats['hits_by_type'],'newly_observed_cells':len(obs_cells-prior),
                       'observed_cell_set':obs_cells}
                state['sensor_events'].append(event)
                return result
            def decide(self,step,position):
                result=original_decide(self,step,position)
                if condition=='original_exact_replay': return result
                if step==target:
                    state['natural_at_target']=bool(result['observation_granted'])
                    if not result['observation_granted'] and self.used<self.cap:
                        latest=self.decisions[-1]
                        self._before_route=latest.get('nominal_route')
                        if self._before_route is None and self.context is not None:
                            from spatial_memory.navigation import plan
                            goal,_,unknown=self.context
                            self._before_route=plan(self.memory.grid,position,goal,unknown)
                        self._pending=(step,tuple(position));self._prediction=None
                        self.requests+=1;latest['granted']=True;latest['retrospective_forced_scan']=condition
                        result={**result,'observation_requested':True,'observation_granted':True,
                                'observation_score':None,'observation_position':position}
                        state['forced']=True
                    return result
                if condition=='scan_swap_at_selected_step' and state['forced'] and step>target and result['observation_granted'] and not state['suppressed']:
                    self._pending=None;self.denied+=1
                    self.decisions[-1]['granted']=False;self.decisions[-1]['retrospective_scan_swap_suppressed']=True
                    result={**result,'observation_granted':False}
                    state['suppressed']=True
                return result
            PersistenceEVIController.decide=decide
            MujocoRayPerception.observe=observe
            try:
                payload=worlds[case['world_identity']]
                row,trace,diag=runner.run_arm(payload,int(case['schedule']),arm,config)
            finally:
                PersistenceEVIController.decide=original_decide
                MujocoRayPerception.observe=original_observe
            refsteps=reference_ep['trace']['steps']
            canonical_steps=runner.reference.base._jsonable_row(trace['steps'])
            full_trace_match=canonical_steps==refsteps
            first_trace_difference=None
            if not full_trace_match:
                for old,new in zip(refsteps,canonical_steps):
                    if old!=new:
                        first_trace_difference={'step':old.get('step'),
                            'different_fields':[k for k in old if old.get(k)!=new.get(k)]}
                        break
            semantic_fields=('step','position','heading_yaw','action','moved','blocked',
                             'observation_granted','observation_count')
            semantic_match=(len(canonical_steps)==len(refsteps) and all(
                all(a.get(k)==b.get(k) for k in semantic_fields)
                for a,b in zip(refsteps,canonical_steps)))
            if condition=='original_exact_replay' and not semantic_match:
                replay_mismatches.append({'episode':number,'arm':arm,'world_identity':case['world_identity'],
                    'schedule':case['schedule'],'first_difference':first_trace_difference,
                    'action':'Excluded this arm/case from causal contrasts because its untreated replay did not match saved semantic trace.'})
                print(f'SKIP intervention contrasts {number} {arm}: saved semantic trace mismatch {first_trace_difference}',flush=True)
                break
            # omit bulky cell set when serializing; retain real measurement summaries.
            scan_events=[]
            for e in state['sensor_events']:
                scan_events.append({k:v for k,v in e.items() if k!='observed_cell_set'})
            intervention={
              'episode':number,'world_identity':case['world_identity'],'schedule':int(case['schedule']),
              'role':case['role'],'arm':arm,'condition':condition,'target_step':target,
              'selected_step_rule':'first recorded blocked attempt' if is_failure else 'floor(saved goal step / 2)',
              'forced_scan_executed':state['forced'],'natural_scan_already_at_target':state['natural_at_target'],
              'full_saved_trace_match':full_trace_match if condition=='original_exact_replay' else None,
              'semantic_saved_trace_match':semantic_match if condition=='original_exact_replay' else None,
              'first_full_trace_difference':first_trace_difference if condition=='original_exact_replay' else None,
              'next_natural_scan_suppressed':state['suppressed'],'success':bool(row['success']),
              'goal_step':row.get('goal_step'),'steps':int(row['elapsed_steps']),
              'travel_distance_m':float(row['travel_distance_m']),
              'paid_observations':int(row['observation_count']),
              'blocked_attempts':int(row.get('g1_footprint_blocked_attempts',0)),
              'emergency_interventions':int(row.get('emergency_safety_interventions',0)),
              'unwanted_contacts':int(row.get('g1_unwanted_contact_pairs',0)),
              'observation_steps':row['spatial_memory_observation_steps'],
              'scan_measurements':scan_events,
              'memory_update_events':diag.get('observation_log',[]),
              'trace':canonical_steps,
              'sensor_rule':'actual authorized MuJoCo memory observation; no occupancy injection or hidden query',
              'instrumentation':'controller grant override only at predetermined step; sensor/planner/shield/safety implementations unchanged'}
            outfile=OUT/f'case_{number:03}_{arm}_{condition}.json'
            outfile.write_text(json.dumps(intervention,indent=2,sort_keys=True,allow_nan=False)+'\n')
            rows.append({k:v for k,v in intervention.items() if k not in ('scan_measurements','memory_update_events')})
            saved_hashes[str(outfile.relative_to(ROOT))]=hashlib.sha256(outfile.read_bytes()).hexdigest()
            print(f"{number} {arm} {condition}: success={row['success']} scans={row['observation_count']} blocked={row.get('g1_footprint_blocked_attempts')}",flush=True)
    finally:
        PersistenceEVIController.decide=original_decide
        MujocoRayPerception.observe=original_observe
    import csv
    with (OUT/'results.csv').open('x',newline='') as f:
        fields=sorted({k for r in rows for k in r});w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(rows)
    (OUT/'provenance.json').write_text(json.dumps({'status':'COMPLETED_RETROSPECTIVE_DIAGNOSTIC_INTERVENTIONS',
       'selection_sha256':hashlib.sha256((ANALYSIS/'frozen_counterfactual_case_selection.json').read_bytes()).hexdigest(),
       'result_sha256':saved_hashes,'n':len(rows),'untreated_replay_mismatches':replay_mismatches,
       'not_an_online_policy':True},indent=2,sort_keys=True)+'\n')

if __name__=='__main__': main()
