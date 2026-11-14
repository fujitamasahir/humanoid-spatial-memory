"""Count actual FIT72 MuJoCo spatial-memory sensor calls without changing policy."""
from __future__ import annotations
import csv,gzip,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
import evaluate_persistence_evi_fit72 as runner
from spatial_memory.mujoco_perception import MujocoRayPerception
FIT=ROOT/'results/phase2_mujoco/persistence_evi_fit72_restored_local_v1'
OUT=ROOT/'results/phase2_mujoco/persistence_evi_failure_analysis_v1'
ARMS=('periodic','age','b_age','c_ternary','bc')
def main():
 worlds={w['identity']:w for w in runner.reference.navigation.admitted_worlds()}
 _,_,prov,_=runner.reference.base.load_baseline();config=runner.reference.base.frozen_config(prov)
 original=MujocoRayPerception.observe;counts=[];validation=[]
 for n in range(1,73):
  for arm in ARMS:
   saved=json.loads(gzip.decompress((FIT/f'episode_{n:03}_{arm}.json.gz').read_bytes()))
   key=saved['trace']['key'];events=[]
   def observe(self,world,position,yaw):
    result=original(self,world,position,yaw)
    # Restrict to the agent's 61-ray, 120-degree, 6 m sensor. Emergency safety
    # is an independent 181-ray, 360-degree, 2 m sensor using the same class.
    if self.ray_count==61 and abs(self.horizontal_fov_deg-120)<1e-9 and abs(self.range_m-6)<1e-9:
     events.append({'step':int(world.step),'rays':int(self.last_stats['ray_count']),
       'visible_cells':int(self.last_stats['visible_cells']),'hits':int(self.last_stats['ray_hits'])})
    return result
   MujocoRayPerception.observe=observe
   try:row,trace,diag=runner.run_arm(worlds[key[0]],int(key[1]),arm,config)
   finally:MujocoRayPerception.observe=original
   old=saved['trace']['steps'];new=runner.reference.base._jsonable_row(trace['steps']);
   fields=('step','position','heading_yaw','action','moved','blocked','observation_granted','observation_count')
   semantic=len(old)==len(new) and all(all(a.get(k)==b.get(k) for k in fields) for a,b in zip(old,new))
   logged=int(saved['row']['observation_count']);steps=[int(x['step']) for x in events]
   counts.append({'episode':n,'world_identity':key[0],'schedule':key[1],'arm':arm,
     'actual_memory_sensor_calls':len(events),'logged_paid_observation_count':logged,
     'actual_memory_raycasts':sum(x['rays'] for x in events),'sensor_call_steps':json.dumps(steps),
     'logged_scan_steps':json.dumps(saved['row'].get('spatial_memory_observation_steps',[])),
     'scan_count_matches':len(events)==logged,'actual_scan_steps_match':steps==saved['row'].get('spatial_memory_observation_steps',[]),
     'semantic_trace_matches':semantic})
   validation.append({'episode':n,'arm':arm,'semantic_trace_matches':semantic,
     'scan_count_matches':len(events)==logged,'actual_scan_steps_match':steps==saved['row'].get('spatial_memory_observation_steps',[])})
   print(f'{n}/72 {arm}: calls={len(events)} rays={sum(x["rays"] for x in events)} trace={semantic}',flush=True)
 with (OUT/'actual_spatial_memory_scan_counts.csv').open('x',newline='') as f:
  fs=sorted({k for r in counts for k in r});w=csv.DictWriter(f,fieldnames=fs,lineterminator='\n');w.writeheader();w.writerows(counts)
 with (OUT/'actual_spatial_memory_scan_validation.csv').open('x',newline='') as f:
  fs=sorted({k for r in validation for k in r});w=csv.DictWriter(f,fieldnames=fs,lineterminator='\n');w.writeheader();w.writerows(validation)
if __name__=='__main__':main()
