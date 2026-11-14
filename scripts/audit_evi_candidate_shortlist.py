"""Public-memory-only audit of value for excluded nominal-route candidates.

Replays the saved comparative FIT72 failure keys under frozen C/B+C and
requires exact semantic parity. This is instrumentation, not a new policy arm.
It computes diagnostic counterfactual public A* values, never shield queries.
"""
from __future__ import annotations
import csv, gzip, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
import numpy as np
import evaluate_persistence_evi_fit72 as runner
import spatial_memory.evi as evi
from spatial_memory.navigation import plan
FIT=ROOT/'results/phase2_mujoco/persistence_evi_fit72_restored_local_v1'
OUT=ROOT/'results/phase2_mujoco/persistence_evi_failure_analysis_v1'

def load(n,a):
    return json.loads(gzip.decompress((FIT/f'episode_{n:03}_{a}.json.gz').read_bytes()))

def loss(route,cell,occupied,failure_cost):
    if not route:return failure_cost
    return len(route)-1+(failure_cost if occupied and cell in route else 0)

def main():
    failures=list(csv.DictReader((OUT/'failure_mechanism_classifications.csv').open()))
    keys=sorted({(r['world_identity'],int(r['schedule']),int(r['episode'])) for r in failures if r['arm']=='c_ternary'})
    worlds={w['identity']:w for w in runner.reference.navigation.admitted_worlds()}
    _,_,prov,_=runner.reference.base.load_baseline();config=runner.reference.base.frozen_config(prov)
    original=evi.information_value; output=[]; parity=[]
    for world,schedule,number in keys:
      for arm in ('c_ternary','bc'):
        saved=load(number,arm); state={'step':None,'rows':[]}
        def instrument(grid,probability,position,goal,yaw,unknown,sensor,remaining,parameters=None):
            p=parameters or evi.EVIParameters()
            result=original(grid,probability,position,goal,yaw,unknown,sensor,remaining,p)
            route=result['nominal_route'] or [position]
            route_set=set(route);foot=evi.visible_cells(grid,position,yaw,**sensor)
            candidates=[c for c in foot if c!=position and .05<float(probability[c[1],c[0]])<.95]
            def rank(c):
                d=min(abs(c[0]-r[0])+abs(c[1]-r[1]) for r in route)
                q=float(probability[c[1],c[0]])
                return (-q*(1-q)/(1+d),c[1],c[0])
            candidates.sort(key=rank); selected=set(candidates[:p.max_candidates])
            top_d=float(result['delay_regret']); top_v=float(result['value'])
            cost=float(result['cost']); remain=max(1,int(remaining))
            for c in candidates[p.max_candidates:]:
                if c not in route_set:continue
                routes=[]
                for outcome in (0,1):
                    cf=grid.copy();cf[c[1],c[0]]=outcome
                    routes.append(plan(cf,position,goal,unknown))
                q=float(probability[c[1],c[0]])
                vals=[[loss(r,c,o,p.failure_cost) for o in (0,1)] for r in routes]
                before=min((1-q)*v[0]+q*v[1] for v in vals)
                after=(1-q)*min(v[0] for v in vals)+q*min(v[1] for v in vals)
                value=max(0.,before-after)
                acts=[tuple(r[1]) if r and len(r)>1 else None for r in routes]
                delay=value*min(q,1-q) if acts[0]!=acts[1] else 0.
                output.append({'episode':number,'world_identity':world,'schedule':schedule,'arm':arm,
                    'step':state['step'],'cell':json.dumps(c),'rank_original':candidates.index(c)+1,
                    'q_occupied':q,'on_nominal_route':True,'free_first_action':json.dumps(acts[0]),
                    'occupied_first_action':json.dumps(acts[1]),'first_action_changes':acts[0]!=acts[1],
                    'value_V':value,'delay_regret_D':delay,'original_cost_K3':cost,
                    'excluded_D_exceeds_original_selected_D':delay>top_d+1e-12,
                    'excluded_D_exceeds_frozen_K3_cost':delay>cost+1e-12,
                    'would_change_K3_authorization_if_maximum':delay>max(top_d,cost)+1e-12})
            state['rows'].append((result['delay_regret'],result['value'],result['net_value']))
            return result
        original_decide=evi.PersistenceEVIController.decide
        def mark(self,step,position):state['step']=step;return original_decide(self,step,position)
        evi.information_value=instrument;evi.PersistenceEVIController.decide=mark
        try: _,trace,diag=runner.run_arm(worlds[world],schedule,arm,config)
        finally:evi.information_value=original;evi.PersistenceEVIController.decide=original_decide
        old=saved['trace']['steps'];new=runner.reference.base._jsonable_row(trace['steps'])
        fields=('step','position','heading_yaw','action','moved','blocked','observation_granted','observation_count')
        match=len(old)==len(new) and all(all(a.get(k)==b.get(k) for k in fields) for a,b in zip(old,new))
        parity.append({'episode':number,'world_identity':world,'schedule':schedule,'arm':arm,
            'semantic_trace_match':match,'instrumented_decisions':len(state['rows']),'saved_decisions':len(diag['decisions'])})
        if not match:raise RuntimeError(f'Frozen replay mismatch: {number} {world} {schedule} {arm}')
        if len(state['rows'])!=len(diag['decisions']):raise RuntimeError('Decision count mismatch')
        print(f'{number} {arm} parity=PASS decisions={len(state["rows"])}',flush=True)
    write(OUT/'excluded_route_candidate_value_audit.csv',output)
    write(OUT/'excluded_route_candidate_value_audit_parity.csv',parity)
    print(json.dumps({'rows':len(output),'replays':len(parity),'all_parity':all(x['semantic_trace_match'] for x in parity)}))

def write(path,rows):
    if not rows:return
    with (OUT/path).open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=sorted({k for r in rows for k in r}),lineterminator='\n');w.writeheader();w.writerows(rows)
if __name__=='__main__':main()
