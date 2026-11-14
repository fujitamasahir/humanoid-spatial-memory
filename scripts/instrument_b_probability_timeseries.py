"""Capture B-only public probabilities over frozen FIT72 replays, read-only."""
from __future__ import annotations
import csv,gzip,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
import evaluate_persistence_evi_fit72 as runner
from spatial_memory.evi import PersistenceEVIController
FIT=ROOT/'results/phase2_mujoco/persistence_evi_fit72_restored_local_v1'
OUT=ROOT/'results/phase2_mujoco/persistence_evi_failure_analysis_v1'

def main():
 worlds={w['identity']:w for w in runner.reference.navigation.admitted_worlds()}
 _,_,prov,_=runner.reference.base.load_baseline();config=runner.reference.base.frozen_config(prov)
 rows=[];validation=[];od=PersistenceEVIController.decide;orr=PersistenceEVIController.refresh
 for n in range(1,73):
  saved=json.loads(gzip.decompress((FIT/f'episode_{n:03}_b_age.json.gz').read_bytes()))
  key=saved['trace']['key'];world=key[0];schedule=int(key[1]);local=[]
  def snap(agent,step,phase):
   grid=agent.memory.grid; p=agent.probabilities(int(step));known=grid>=0
   vals=p[known]
   local.append({'episode':n,'world_identity':world,'schedule':schedule,'step':int(step),'phase':phase,
    'free_cells':int((grid==0).sum()),'occupied_cells':int((grid==1).sum()),'unknown_cells':int((grid<0).sum()),
    'probability_mean_known':float(vals.mean()) if vals.size else None,
    'probability_mean':float(p.mean()),'probability_p10':float(__import__('numpy').quantile(p,.1)),
    'probability_p50':float(__import__('numpy').quantile(p,.5)),'probability_p90':float(__import__('numpy').quantile(p,.9)),
    'cells_below_free_threshold':int((known&(p<=agent.belief.params.free_threshold)).sum()),
    'cells_above_occupied_threshold':int((known&(p>=agent.belief.params.occupied_threshold)).sum()),
    'projection_changed_cells_last_inference':int(agent.belief.inference_log[-1]['changed_cells']) if agent.belief.inference_log else 0})
  def decide(self,step,pos):
   result=od(self,step,pos);snap(self,step,'post_inference_pre_scan');return result
  def refresh(self,obs,step):
   result=orr(self,obs,step);snap(self,step,'post_authorized_scan_refresh');return result
  PersistenceEVIController.decide=decide;PersistenceEVIController.refresh=refresh
  try: row,trace,diag=runner.run_arm(worlds[world],schedule,'b_age',config)
  finally:PersistenceEVIController.decide=od;PersistenceEVIController.refresh=orr
  old=saved['trace']['steps'];new=runner.reference.base._jsonable_row(trace['steps']);fields=('step','position','heading_yaw','action','moved','blocked','observation_granted','observation_count')
  ok=len(old)==len(new) and all(all(a.get(k)==b.get(k) for k in fields) for a,b in zip(old,new))
  validation.append({'episode':n,'world_identity':world,'schedule':schedule,'semantic_trace_match':ok,'snapshots':len(local)})
  if ok:rows.extend(local)
  print(f'{n}/72 B-only shadow replay: semantic_match={ok}',flush=True)
 with gzip.open(OUT/'b_probability_timeseries.csv.gz','xt',compresslevel=9,newline='') as f:
  fields=sorted({k for r in rows for k in r});w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(rows)
 with (OUT/'b_probability_timeseries_validation.csv').open('x',newline='') as f:
  fields=sorted({k for r in validation for k in r});w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(validation)
if __name__=='__main__':main()
