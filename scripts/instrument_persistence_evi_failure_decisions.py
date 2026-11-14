"""Shadow-audit EVI's candidate ranking on frozen C/B+C failure episodes.

The shadow work reads only each decision's public memory and parameters. It
does not feed diagnostics into the controller or query MuJoCo collision state.
"""
from __future__ import annotations
import csv,gzip,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
import evaluate_persistence_evi_fit72 as runner
import spatial_memory.evi as evi
from spatial_memory.navigation import plan
from spatial_memory.mujoco_perception import MujocoRayPerception
FIT=ROOT/'results/phase2_mujoco/persistence_evi_fit72_restored_local_v1'
OUT=ROOT/'results/phase2_mujoco/persistence_evi_failure_analysis_v1'

def load(n,a):return json.loads(gzip.decompress((FIT/f'episode_{n:03}_{a}.json.gz').read_bytes()))
def loss(route,cell,occupied,failure_cost):
    if not route:return failure_cost
    return len(route)-1+(failure_cost if occupied and cell in route else 0)

def main():
    idx={}
    for n in range(1,73):
        t=load(n,'age')['trace'];idx[tuple(t['key'])]=n
    failures=load_failures()
    uniq={(x['world_identity'],int(x['schedule'])):int(x['episode']) for x in failures}
    worlds={w['identity']:w for w in runner.reference.navigation.admitted_worlds()}
    _,_,prov,_=runner.reference.base.load_baseline();config=runner.reference.base.frozen_config(prov)
    original=evi.information_value;original_observe=MujocoRayPerception.observe
    decision_rows=[];candidate_rows=[];replays=[]
    for (world,schedule),n in sorted(uniq.items()):
      for arm in ('c_ternary','bc'):
        saved=load(n,arm);shadow={'rows':[],'step':None,'observations':{}}
        def observe(self,world,pos,yaw):
            result=original_observe(self,world,pos,yaw)
            # The safety sensor shares this low-level ray class but is 181-ray,
            # 360-degree, 2 m. Keep only the agent's scheduled 61-ray/120-degree
            # memory scan; never misattribute the independent safety channel.
            if self.ray_count==61 and abs(self.horizontal_fov_deg-120.0)<1e-9 and abs(self.range_m-6.0)<1e-9:
                shadow['observations'][int(world.step)]={(int(x),int(y)):int(result[y,x]) for y,x in __import__('numpy').argwhere(result>=0)}
            return result
        def info(grid,probability,position,goal,yaw,unknown,sensor,remaining,parameters=None):
            result=original(grid,probability,position,goal,yaw,unknown,sensor,remaining,parameters)
            p=parameters or evi.EVIParameters();nom=plan(grid,position,goal,unknown) or [position]
            route_cells=set(nom);foot=evi.visible_cells(grid,position,yaw,**sensor)
            cells=[c for c in foot if c!=position and .05<float(probability[c[1],c[0]])<.95]
            def rank(c):
                d=min(abs(c[0]-r[0])+abs(c[1]-r[1]) for r in nom);q=float(probability[c[1],c[0]])
                return (-q*(1-q)/(1+d),c[1],c[0])
            cells.sort(key=rank);short=cells[:p.max_candidates]
            items=[]
            for c in short:
                routes=[plan((lambda g:(g.__setitem__((c[1],c[0]),o),g)[1])(grid.copy()),position,goal,unknown) for o in (0,1)]
                q=float(probability[c[1],c[0]])
                vals=[[loss(r,c,o,p.failure_cost) for o in (0,1)] for r in routes]
                before=min((1-q)*x[0]+q*x[1] for x in vals)
                after=(1-q)*min(x[0] for x in vals)+q*min(x[1] for x in vals)
                V=max(0.,before-after);acts=[tuple(r[1]) if r and len(r)>1 else None for r in routes]
                D=V*min(q,1-q) if acts[0]!=acts[1] else 0.
                items.append({'cell':c,'q_occupied':q,'rank_score':-rank(c)[0],
                    'V':V,'D':D,'free_first_action':acts[0],'occupied_first_action':acts[1],
                    'free_route':routes[0],'occupied_route':routes[1],
                    'on_nominal_route':c in route_cells})
            excluded_route=[c for c in cells[p.max_candidates:] if c in route_cells]
            excluded_route_action_changes=0;excluded_route_path_changes=0
            selected=set(short)
            for c in excluded_route:
                routes=[]
                for outcome in (0,1):
                    counterfactual=grid.copy();counterfactual[c[1],c[0]]=outcome
                    routes.append(plan(counterfactual,position,goal,unknown))
                actions=[tuple(r[1]) if r and len(r)>1 else None for r in routes]
                excluded_route_action_changes+=actions[0]!=actions[1]
                excluded_route_path_changes+=routes[0]!=routes[1]
            shadow['rows'].append({'step':shadow['step'],'position':list(position),'yaw':yaw,
                'nominal_route':nom,'predicted_visible_cells':len(foot),'uncertain_candidates':len(cells),
                'predicted_visible_cell_list':[list(c) for c in sorted(foot)],
                'top3':items,'excluded_cells_on_nominal_route':[list(c) for c in excluded_route],
                'excluded_on_route_count':len(excluded_route),'actual_value_cell':result.get('cell'),
                'excluded_route_action_change_count':excluded_route_action_changes,
                'excluded_route_path_change_count':excluded_route_path_changes,
                'actual_V':result.get('value'),'actual_D':result.get('delay_regret'),
                'actual_cost':result.get('cost'),'actual_net_value':result.get('net_value')})
            return result
        def mark_step(self,step,position):
            shadow['step']=step
            return original_decide(self,step,position)
        original_decide=evi.PersistenceEVIController.decide
        evi.information_value=info;evi.PersistenceEVIController.decide=mark_step
        MujocoRayPerception.observe=observe
        try: row,trace,diag=runner.run_arm(worlds[world],schedule,arm,config)
        finally:
            evi.information_value=original;evi.PersistenceEVIController.decide=original_decide
            MujocoRayPerception.observe=original_observe
        saved_steps=saved['trace']['steps'];new_steps=runner.reference.base._jsonable_row(trace['steps'])
        fields=('step','position','heading_yaw','action','moved','blocked','observation_granted','observation_count')
        semantic=len(saved_steps)==len(new_steps) and all(all(a.get(k)==b.get(k) for k in fields) for a,b in zip(saved_steps,new_steps))
        replay={'episode':n,'world_identity':world,'schedule':schedule,'arm':arm,'semantic_trace_match':semantic,
            'decision_count':len(diag['decisions']),'shadow_count':len(shadow['rows'])}
        replays.append(replay)
        if not semantic:
            continue
        if len(shadow['rows'])!=len(diag['decisions']):raise RuntimeError('Shadow EVI call count differed from controller decisions')
        for decision,sh in zip(diag['decisions'],shadow['rows']):
            step=int(decision['step']);observed=shadow['observations'].get(step,{})
            predicted=set(map(tuple,sh['predicted_visible_cell_list']))
            route_cells=set(map(tuple,sh['nominal_route']))
            missing=[list(c) for c in sorted((set(observed)-predicted)&route_cells)]
            candidates=sh['top3']
            observed_candidate_errors=[]
            for candidate in candidates:
                cell=tuple(candidate['cell'])
                if cell in observed:
                    q=float(candidate['q_occupied']);outcome=int(observed[cell])
                    if (q<.5 and outcome==1) or (q>.5 and outcome==0):
                        observed_candidate_errors.append({'cell':list(cell),'q':q,'outcome':outcome})
            d={**{k:decision.get(k) for k in ('step','granted','value','delay_regret','cost','net_value','cell','occupied_probability','used_before','plan_calls')},
               'episode':n,'world_identity':world,'schedule':schedule,'arm':arm,
               'uncertain_candidates':sh['uncertain_candidates'],'excluded_nominal_route_candidates':sh['excluded_on_route_count'],
               'excluded_route_candidates_that_change_first_action':sh['excluded_route_action_change_count'],
               'excluded_route_candidates_that_change_full_route':sh['excluded_route_path_change_count'],
               'candidate_details':json.dumps(sh['top3'],sort_keys=True),'excluded_cells_on_nominal_route':json.dumps(sh['excluded_cells_on_nominal_route']),
               'actual_scan_visible_cells':len(observed) if step in shadow['observations'] else None,
               'actual_visible_nominal_route_cells_missing_from_prediction':json.dumps(missing),
               'shortlist_candidates_with_directional_probability_error_at_scan':json.dumps(observed_candidate_errors)}
            decision_rows.append(d)
            for rank,cell in enumerate(sh['top3'],1):candidate_rows.append({'episode':n,'world_identity':world,'schedule':schedule,'arm':arm,'step':decision['step'],'rank':rank,**{k:json.dumps(v) if isinstance(v,(list,tuple)) else v for k,v in cell.items()}})
        print(f'{n} {arm}: semantic_match={semantic} decisions={len(shadow["rows"])}',flush=True)
    write(OUT/'evi_shadow_decisions.csv',decision_rows);write(OUT/'evi_shadow_candidate_shortlists.csv',candidate_rows)
    write(OUT/'evi_shadow_replay_validation.csv',replays)

def load_failures():
    with (OUT/'failure_mechanism_classifications.csv').open() as f:
        rows=list(csv.DictReader(f))
    return [x for x in rows if x['arm']=='c_ternary']
def write(path,rows):
    fields=sorted({k for r in rows for k in r})
    with (OUT/path).open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(rows)
if __name__=='__main__':main()
