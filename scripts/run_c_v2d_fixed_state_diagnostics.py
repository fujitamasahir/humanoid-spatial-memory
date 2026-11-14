"""One frozen-rule public-memory scan/no-scan diagnostic for C v2.0d FIT72."""
from __future__ import annotations
import gzip,hashlib,json,sys
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
import evaluate_c_v2_candidate_coverage_fit72 as fit
import evaluate_event_observation_fit72 as reference
import evaluate_persistence_evi_fit72 as runner
from run_c_v2d_topology_fixtures import independent_exhaustive_evi
from spatial_memory.evi import PersistenceEVIController,visible_cells

FIT_OUT=ROOT/'results/phase2_mujoco/c_v2d_topology_v1/fit72_descriptive_screen'
OUT=ROOT/'results/phase2_mujoco/c_v2d_topology_v1/fit72_fixed_state_diagnostic_v1'
COMMON_COST=.5+.01*7+.5/20
SENSOR={'range_m':6.,'cell_size':.75,'horizontal_fov_deg':120.,'ray_count':61}
TRACE_FIELDS=('step','position','heading_yaw','action','moved','blocked','contacts',
              'observation_granted','observation_count','emergency_intervention')


def _sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_episode(n,arm):
    p=FIT_OUT/f'episode_{n:03}_{arm}.json.gz'
    return json.loads(gzip.decompress(p.read_bytes()))


def _trace_prefix_equal(a,b,step):
    aa={int(x['step']):x for x in a['trace']['steps']}
    bb={int(x['step']):x for x in b['trace']['steps']}
    for i in range(step):
        if tuple(aa.get(i,{}).get(k) for k in TRACE_FIELDS)!=tuple(bb.get(i,{}).get(k) for k in TRACE_FIELDS):
            return False
    return True


def _collect_d_states(payload,schedule,wanted_steps,saved_trace):
    original=PersistenceEVIController.decide;snapshots={}
    def capturing(self,step,position):
        decision=original(self,step,position)
        if step in wanted_steps:
            goal,yaw,unknown=self.context
            snapshots[step]={'step':int(step),'position':tuple(position),'yaw':float(yaw),
              'goal':tuple(goal),'unknown':unknown,'used_before':int(self.used),
              'grid':self.memory.grid.copy(),'probability':self.probabilities(step).copy(),
              'decision':dict(self.decisions[-1])}
        return decision
    PersistenceEVIController.decide=capturing
    try:row,trace,diag=runner.run_arm(payload,schedule,'c_topology3d',_config())
    finally:PersistenceEVIController.decide=original
    reference._compare_trace(saved_trace,reference.base._jsonable_row(trace))
    return snapshots,row,trace,diag


def _config():
    _,_,provenance,_=reference.base.load_baseline()
    return reference.base.frozen_config(provenance)


def _run_forced(payload,schedule,step,force_scan,config):
    original=PersistenceEVIController.decide;original_observe=fit.MujocoRayPerception.observe
    calls=[];forced=[]
    def observe(self,world,position,yaw):
        result=original_observe(self,world,position,yaw)
        if self.ray_count==61 and self.horizontal_fov_deg==120. and self.range_m==6.:
            calls.append(int(world.step))
        return result
    def deciding(self,current_step,position):
        result=original(self,current_step,position)
        if current_step!=step:return result
        decision=self.decisions[-1]
        before=bool(result['observation_granted'])
        if force_scan and not before:
            if self.used>=self.cap:raise RuntimeError('selected intervention exhausted cap')
            goal,yaw,unknown=self.context
            self._pending=(current_step,tuple(position))
            self._before_route=decision.get('nominal_route')
            if self._before_route is None:
                from spatial_memory.navigation import plan
                self._before_route=plan(self.memory.grid,position,goal,unknown)
            self._prediction=decision
        elif not force_scan and before:
            self._pending=None;self._before_route=None;self._prediction=None
        decision['granted']=bool(force_scan)
        decision['diagnostic_forced']=True
        decision['diagnostic_original_grant']=before
        forced.append({'step':int(step),'original_grant':before,'forced_grant':bool(force_scan)})
        return {**result,'observation_granted':bool(force_scan)}
    PersistenceEVIController.decide=deciding
    fit.MujocoRayPerception.observe=observe
    try:row,trace,diag=runner.run_arm(payload,schedule,'c_topology3d',config)
    finally:
        PersistenceEVIController.decide=original
        fit.MujocoRayPerception.observe=original_observe
    expected=[int(x['step']) for x in trace['steps'] if x['observation_granted']]
    if calls!=expected:raise RuntimeError('61-ray calls do not match the replay grant trace')
    if int(row['g1_unselected_action_shield_queries'])!=0 or int(row['observation_count'])>20:
        raise RuntimeError('safety shield or paid observation cap violated')
    return {'row':row,'trace':trace,'diagnostics':diag,'memory_sensor_calls':calls,
      'memory_rays':61*len(calls),'forced':forced}


def run():
    if OUT.exists():raise FileExistsError(f'Refusing to overwrite {OUT}')
    review=json.loads((FIT_OUT.parent/'gate_review.json').read_text())
    if review.get('status')!='ACCEPTED_FOR_FIT' or review.get('FIT_authorized') is not True:
        raise RuntimeError('C v2.0d independent gate review blocks diagnostics')
    integrity=fit.verify_original_data_integrity()
    _,_,provenance,_=reference.base.load_baseline();config=reference.base.frozen_config(provenance)
    payloads={x['identity']:x for x in reference.navigation.admitted_worlds()}
    candidate_states=[];candidate_total=0
    for number in range(1,73):
        c0=_read_episode(number,'C0');d=_read_episode(number,'C-Topology3-d')
        age_key=tuple(d['trace']['key']);identity,schedule,_method,seed=age_key
        a={int(x['step']):x for x in c0['diagnostics']['decisions']}
        b={int(x['step']):x for x in d['diagnostics']['decisions']}
        eligible_steps=[s for s in sorted(set(a)&set(b))
          if a[s].get('granted')!=b[s].get('granted')
          and _trace_prefix_equal(c0,d,s)
          and int(b[s].get('used_before',20))<20]
        if not eligible_steps:continue
        snaps,rerun_row,rerun_trace,_diag=_collect_d_states(
            payloads[identity],int(schedule),set(eligible_steps),d['trace'])
        for step in eligible_steps:
            snap=snaps.get(step)
            if snap is None:continue
            exhaustive,cost,_calls,_nominal,candidates=independent_exhaustive_evi(
                snap['grid'],snap['probability'],snap['position'],snap['goal'],
                snap['yaw'],snap['unknown'])
            if not candidates:continue
            maxd=max(x['D'] for x in exhaustive)
            if maxd<=COMMON_COST:continue
            selected_d=float(snap['decision'].get('delay_regret') or 0.)
            cell=snap['decision'].get('cell')
            if cell is None:continue
            cell=tuple(cell)
            footprint=visible_cells(snap['grid'],snap['position'],snap['yaw'],**SENSOR)
            q=float(snap['probability'][cell[1],cell[0]])
            if cell not in footprint or not .05<q<.95:continue
            tied=sorted((tuple(x['cell']) for x in exhaustive if x['D']==maxd),key=lambda p:(p[1],p[0]))
            candidate_states.append({'episode_number':number,'identity':identity,
              'schedule':int(schedule),'seed':int(seed),'step':int(step),
              'position':list(snap['position']),'heading':snap['yaw'],
              'C0_granted':bool(a[step]['granted']),'C_v2d_granted':bool(b[step]['granted']),
              'exhaustive_max_D':float(maxd),'common_K3_cost':COMMON_COST,
              'selected_C_v2d_D':selected_d,'selected_candidate':list(cell),
              'selected_candidate_probability':q,'exhaustive_max_D_cells':[list(c) for c in tied],
              'paid_observations_used_before':int(snap['used_before']),
              'candidate_count':len(candidates),
              'prefix_identical_before_decision':True,
              'public_grid':snap['grid'],'probability_map':snap['probability']})
        candidate_total+=len(eligible_steps)
    if not candidate_states:
        result={'status':'NO_QUALIFYING_FIXED_STATE_DIAGNOSTIC',
          'eligible_trace_decision_disagreements':candidate_total,
          'intervention_executed':False,'FIT_integrity_status':integrity['status']}
        OUT.mkdir(parents=True,exist_ok=False);(OUT/'diagnostic.json').write_text(json.dumps(result,indent=2)+'\n')
        return result
    candidate_states.sort(key=lambda x:(-(x['exhaustive_max_D']-COMMON_COST),
      -(x['selected_C_v2d_D']-COMMON_COST),x['identity'],x['schedule'],x['step'],
      x['exhaustive_max_D_cells'][0][1],x['exhaustive_max_D_cells'][0][0]))
    chosen=candidate_states[0]
    # Confirm C0 and D are at exactly the same public pre-decision memory state.
    c0_snapshots={};original=PersistenceEVIController.decide
    def capturing_c0(self,step,position):
        out=original(self,step,position)
        if step==chosen['step']:
            c0_snapshots['state']={'grid':self.memory.grid.copy(),
              'probability':self.probabilities(step).copy(),'position':tuple(position),
              'yaw':float(self.context[1]),'used_before':int(self.used)}
        return out
    PersistenceEVIController.decide=capturing_c0
    try:
        c0_row,c0_trace,c0_diag=runner.run_arm(payloads[chosen['identity']],
          chosen['schedule'],'c0_audit',config)
    finally:PersistenceEVIController.decide=original
    c0_saved=_read_episode(chosen['episode_number'],'C0')
    reference._compare_trace(c0_saved['trace'],reference.base._jsonable_row(c0_trace))
    if not c0_snapshots or not np.array_equal(c0_snapshots['state']['grid'],chosen['public_grid']) or not np.array_equal(c0_snapshots['state']['probability'],chosen['probability_map']):
        raise RuntimeError('C0 and C v2.0d public memory state differs before selected intervention')
    if c0_snapshots['state']['position']!=tuple(chosen['position']) or c0_snapshots['state']['used_before']!=chosen['paid_observations_used_before']:
        raise RuntimeError('C0 and C v2.0d pre-decision pose/budget differs')
    selected_cell=chosen['exhaustive_max_D_cells'][0]
    chosen['intervention_cell_for_rule']=selected_cell
    chosen['intervention_method']='force_one_full_actual_61_ray_observation_at_selected_state'
    chosen['outcomes_opened_before_state_selection']=False
    OUT.mkdir(parents=True,exist_ok=False)
    selection_path=OUT/'selection_pre_outcome.json'
    serializable={k:v for k,v in chosen.items() if k not in ('public_grid','probability_map')}
    serializable['public_grid_sha256']=hashlib.sha256(np.ascontiguousarray(chosen['public_grid']).tobytes()).hexdigest()
    serializable['probability_map_sha256']=hashlib.sha256(np.ascontiguousarray(chosen['probability_map'],dtype='<f8').tobytes()).hexdigest()
    selection_path.write_text(json.dumps({'status':'FROZEN_INTERVENTION_SELECTION_BEFORE_SCAN_SWAP',
      'selected':serializable,'eligible_state_count':len(candidate_states),
      'eligible_trace_decision_disagreements':candidate_total,
      'selection_rule':'descending exhaustive max-D minus common K=3 cost; descending C-v2d selected D minus common cost; identity/schedule/step/y/x ascending',
      'FIT_data_accessed_read_only':True,'hidden_state_used_for_selection':False},indent=2,sort_keys=True)+'\n')
    no_scan=_run_forced(payloads[chosen['identity']],chosen['schedule'],chosen['step'],False,config)
    with_scan=_run_forced(payloads[chosen['identity']],chosen['schedule'],chosen['step'],True,config)
    no_trace={int(x['step']):x for x in no_scan['trace']['steps']}
    yes_trace={int(x['step']):x for x in with_scan['trace']['steps']}
    if not all(tuple(no_trace[t].get(k) for k in TRACE_FIELDS)==tuple(yes_trace[t].get(k) for k in TRACE_FIELDS)
       for t in range(chosen['step'])):
        raise RuntimeError('Scan/no-scan counterfactuals did not share the same prefix')
    if no_scan['memory_sensor_calls'].count(chosen['step'])!=0 or with_scan['memory_sensor_calls'].count(chosen['step'])!=1:
        raise RuntimeError('Actual memory observation intervention did not match its assignment')
    result={'status':'COMPLETED_ONE_FIXED_STATE_SCAN_SWAP_DIAGNOSTIC',
      'FIT_integrity_status':integrity['status'],'selected_state':serializable,
      'eligible_state_count':len(candidate_states),
      'eligible_trace_decision_disagreements':candidate_total,
      'scan_swap':{'prefix_identical_through_predecision':True,
        'no_scan':{'success':bool(no_scan['row']['success']),
          'goal_step':no_scan['row'].get('goal_step'),'contacts':int(no_scan['row']['g1_unwanted_contact_pairs']),
          'observations':int(no_scan['row']['observation_count']),'memory_sensor_calls':no_scan['memory_sensor_calls'],
          'emergency_interventions':int(no_scan['row']['emergency_safety_interventions'])},
        'with_scan':{'success':bool(with_scan['row']['success']),
          'goal_step':with_scan['row'].get('goal_step'),'contacts':int(with_scan['row']['g1_unwanted_contact_pairs']),
          'observations':int(with_scan['row']['observation_count']),'memory_sensor_calls':with_scan['memory_sensor_calls'],
          'emergency_interventions':int(with_scan['row']['emergency_safety_interventions'])}},
      'causal_scope':'single-state paired scan/no-scan replay; descriptive diagnostic, no parameter tuning',
      'hidden_state_used_online':False,'reserved_cohorts_accessed':False}
    for label,pair in (('no_scan',no_scan),('with_scan',with_scan)):
        (OUT/f'{label}_episode.json.gz').write_bytes(gzip.compress(json.dumps(
          reference.base._jsonable_row({'row':pair['row'],'trace':pair['trace'],'diagnostics':pair['diagnostics']}),
          sort_keys=True,allow_nan=False).encode(),mtime=0))
    (OUT/'diagnostic.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    manifest=[]
    for p in sorted(x for x in OUT.iterdir() if x.is_file() and x.name!='artifact_manifest.json'):
        b=p.read_bytes();manifest.append({'path':p.name,'bytes':len(b),'sha256':_sha(p)})
    (OUT/'artifact_manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    return result


if __name__=='__main__':
    result=run();print(json.dumps(result,indent=2,default=lambda x:x.tolist() if isinstance(x,np.ndarray) else x))
