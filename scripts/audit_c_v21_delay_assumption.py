"""Read-only historical mechanism audit with exact frozen-policy replay parity.

Sample rule fixed before replay: first two V>0,D=0 decisions per reference
arm/episode; no outcome-based case selection. H=3 is fixed before this audit.
"""
from __future__ import annotations
import gzip,json,math,sys
import numpy as np
from c_v21_common import ROOT,OUT,write,manifest,commit
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
import evaluate_c_v2_candidate_coverage_fit72 as fit
import evaluate_event_observation_fit72 as ref
from spatial_memory.evi import PersistenceEVIController,visible_cells
from spatial_memory.navigation import plan
H=3
SENSOR=dict(range_m=6.,cell_size=.75,horizontal_fov_deg=120.,ray_count=61)
HIST=ROOT/'results/phase2_mujoco/c_v2d_topology_v1/fit72_descriptive_screen'
ARMS={'c0_audit':'C0','c_k':'C-K','c_topology3d':'C-Topology3-d'}


def run():
    target=OUT/'one_step_audit';target.mkdir(parents=True,exist_ok=False)
    fit.verify_original_data_integrity()
    _,_,prov,_=ref.base.load_baseline();config=ref.base.frozen_config(prov)
    worlds={p['identity']:p for p in ref.navigation.admitted_worlds()}
    totals={a:{'decisions':0,'positive_V_zero_D':0,'positive_V_positive_D':0,'V_zero':0,'scan':0} for a in ARMS}
    rows=[];original=PersistenceEVIController.decide
    for n in range(1,73):
      for arm,label in ARMS.items():
        saved=json.load(gzip.open(HIST/f'episode_{n:03}_{label}.json.gz','rt'))
        decisions=saved['diagnostics']['decisions'];stats=totals[arm]
        for d in decisions:
            v=float(d.get('value') or 0);delay=float(d.get('delay_regret') or 0)
            stats['decisions']+=1;stats['positive_V_zero_D']+=int(v>1e-12 and delay<=1e-12)
            stats['positive_V_positive_D']+=int(v>1e-12 and delay>1e-12)
            stats['V_zero']+=int(v<=1e-12);stats['scan']+=int(d['granted'])
        wanted={d['step'] for d in decisions if float(d.get('value') or 0)>1e-12 and float(d.get('delay_regret') or 0)<=1e-12}
        wanted=set(sorted(wanted)[:2])
        if not wanted:continue
        captured=[]
        def capture(self,step,position):
            result=original(self,step,position)
            if step in wanted:
                goal,yaw,unknown=self.context
                captured.append(dict(step=step,position=position,goal=goal,yaw=yaw,unknown=unknown,grid=self.memory.grid.copy(),probability=self.probabilities(step).copy(),decision=dict(self.decisions[-1])))
            return result
        PersistenceEVIController.decide=capture
        ident,schedule,_,_=saved['trace']['key']
        try:row,trace,diag=fit.run_measured(worlds[ident],schedule,arm,config)
        finally:PersistenceEVIController.decide=original
        ref._compare_trace(saved['trace'],ref.base._jsonable_row(trace))
        for s in captured:
            c=tuple(s['decision']['cell']);q=float(s['probability'][c[1],c[0]])
            routes=[]
            for o in (0,1):
                grid=s['grid'].copy();grid[c[1],c[0]]=o
                routes.append(plan(grid,s['position'],s['goal'],s['unknown']))
            common=0
            while all(len(r)>common for r in routes) and routes[0][common]==routes[1][common]:common+=1
            shared=max(0,common-1)
            future=[]
            for h in range(1,min(H,shared)+1):
                pos=routes[0][h];prev=routes[0][h-1];yaw=math.atan2(pos[1]-prev[1],pos[0]-prev[0])
                future.append({'h':h,'position':pos,'yaw':yaw,'visible':c in visible_cells(s['grid'],pos,yaw,**SENSOR)})
            rows.append({'episode':n,'arm':arm,'identity':ident,'schedule':schedule,'step':s['step'],'cell':c,'V':s['decision']['value'],'D':s['decision']['delay_regret'],'shared_prefix_moves':shared,'decision_within_H':shared<H,'future_shared_prefix_opportunities':future,'last_chance_within_H':bool(shared<H and future and not any(v['visible'] for v in future)),'safe_one_step_postpone_in_point_model':bool(shared>=1 and future and future[0]['visible']),'routes':routes,'grid':s['grid'].tolist(),'probability':s['probability'].tolist(),'position':s['position'],'goal':s['goal'],'yaw':s['yaw'],'unknown':s['unknown']})
      if n%12==0:print(f'Audit historical keys {n}/72',flush=True)
    write(target/'audit.json',{'status':'COMPLETED_DESCRIPTIVE_MECHANISM_AUDIT','source_commit':commit(),'horizon_fixed_before_audit':H,'sampling':'first two positive-V zero-D decisions per arm/episode; all saved decisions counted','saved_decision_counts':totals,'sampled_states':len(rows),'last_chance_states':sum(r['last_chance_within_H'] for r in rows),'safe_one_step_postpone_states':sum(r['safe_one_step_postpone_in_point_model'] for r in rows),'states':rows,'limitations':['Counterfactual routes/visibility are public predictions, not actual future observations.','V=0 after expanded selection alone cannot identify global no-benefit vs unselected-cell omission.','No causal navigation inference and no FIT tuning.']})
    manifest(target)
if __name__=='__main__':run()
