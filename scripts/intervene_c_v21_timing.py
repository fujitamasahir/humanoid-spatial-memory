"""Predeclared max-two-key real-scan now-versus-one-step-later diagnostics."""
from __future__ import annotations
import gzip,json,sys
from c_v21_common import ROOT,OUT,write,manifest,commit
from evaluate_c_v21_fit72 import require_gate
from c_v21_navigation import run_case
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
import evaluate_event_observation_fit72 as ref
import evaluate_c_v2_candidate_coverage_fit72 as fit
from spatial_memory.evi import PersistenceEVIController
FIELDS=('step','position','heading_yaw','action','moved','blocked','contacts','observation_granted','observation_count','emergency_intervention')


def equal_prefix(a,b,step):
    aa={f['step']:f for f in a['steps']};bb={f['step']:f for f in b['steps']}
    return all(tuple(aa.get(s,{}).get(k) for k in FIELDS)==tuple(bb.get(s,{}).get(k) for k in FIELDS) for s in range(step))


def run():
    require_gate();fit.verify_original_data_integrity()
    target=OUT/'interventions';target.mkdir(parents=True,exist_ok=False)
    candidates=[]
    for n in range(1,73):
      for arm in ('ms_k_visibility','ms_topology_visibility'):
        with_vis=json.load(gzip.open(OUT/f'fit72/episode_{n:03}_{arm}.json.gz','rt'))
        plain=json.load(gzip.open(OUT/f'fit72/episode_{n:03}_{arm.replace("_visibility","")}.json.gz','rt'))
        old={d['step']:d for d in plain['diagnostics']['decisions']}
        for d in with_vis['diagnostics']['decisions']:
            t=d['step']
            if d['granted'] and t in old and not old[t]['granted'] and (d.get('shared_prefix_moves') or 0)>=1 and t<80 and d['used_before']<=18 and equal_prefix(with_vis['trace'],plain['trace'],t):
                ident,sched,_,_=with_vis['trace']['key']
                candidates.append({'episode':n,'arm':arm,'identity':ident,'schedule':sched,'step':t,'used_before':d['used_before']})
    candidates.sort(key=lambda c:(c['identity'],c['schedule'],c['step'],c['arm']))
    chosen=[];seen=set()
    for c in candidates:
        key=(c['identity'],c['schedule'])
        if key not in seen:chosen.append(c);seen.add(key)
        if len(chosen)==2:break
    write(target/'selection_before_replays.json',{'source_commit':commit(),'rule':'lexicographic same-prefix opportunity disagreement; max2 distinct keys; no outcome selection','eligible_states':len(candidates),'chosen':chosen})
    worlds={p['identity']:p for p in ref.navigation.admitted_worlds()}
    _,_,prov,_=ref.base.load_baseline();config=ref.base.frozen_config(prov)
    rows=[]
    for ix,c in enumerate(chosen,1):
        saved=json.load(gzip.open(OUT/f'fit72/episode_{c["episode"]:03}_{c["arm"]}.json.gz','rt'))
        untreated=run_case(worlds[c['identity']],c['schedule'],c['arm'],config)
        if ref.rdao_evaluator._signature(untreated[0])!=ref.rdao_evaluator._signature(saved['row']):raise RuntimeError('Untreated metric drift')
        ref._compare_trace(saved['trace'],ref.base._jsonable_row(untreated[1]))
        original=PersistenceEVIController.decide;enacted=[]
        def delayed(self,step,position):
            result=original(self,step,position)
            if step not in (c['step'],c['step']+1):return result
            desired=step==c['step']+1
            if desired and self.used>=self.cap:raise RuntimeError('Intervention budget exhausted')
            before=result['observation_granted'];d=self.decisions[-1]
            self._pending=(step,tuple(position)) if desired else None
            self._prediction=d if desired else None
            self._before_route=d.get('nominal_route') if desired else None
            self.requests+=int(desired and not before)
            d.update(granted=desired,intervention_original_grant=before,intervention='one_step_delay')
            enacted.append({'step':step,'scan':desired})
            return {**result,'observation_requested':bool(desired or result['observation_requested']),'observation_granted':desired}
        PersistenceEVIController.decide=delayed
        try:treated=run_case(worlds[c['identity']],c['schedule'],c['arm'],config)
        finally:PersistenceEVIController.decide=original
        if not equal_prefix(untreated[1],treated[1],c['step']):raise RuntimeError('Predecision prefix drift')
        for label,(row,trace,diag) in [('scan_now',untreated),('scan_later',treated)]:fit.save_episode(target,ix,label,row,trace,diag)
        rows.append({'selection':c,'enacted':enacted,'contrast_valid':enacted==[{'step':c['step'],'scan':False},{'step':c['step']+1,'scan':True}],'now':fit.flat(c['arm'],untreated[0],untreated[2]),'later':fit.flat(c['arm'],treated[0],treated[2]),'identical_predecision_prefix':True,'untreated_parity':True})
    write(target/'summary.json',{'status':'COMPLETED' if chosen else 'NO_ELIGIBLE_SAME_PREFIX_OPPORTUNITY_STATES','rows':rows,'causal_scope':'Only enacted selected contrasts; no readings transferred; actual paid61-ray scans; cap20 unchanged'})
    manifest(target)
if __name__=='__main__':run()
