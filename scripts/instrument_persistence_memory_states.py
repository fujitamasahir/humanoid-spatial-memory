"""Read-only map-state snapshots for paired FIT72 failure replays and B calibration.

Snapshots are captured after controller inference and after real authorized
refreshes. Wrappers return each original decision unchanged.
"""
from __future__ import annotations
import csv,gzip,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
import evaluate_persistence_evi_fit72 as runner
from spatial_memory.evi import PersistenceEVIController
from spatial_memory.scheduling import ObservationController
FIT=ROOT/'results/phase2_mujoco/persistence_evi_fit72_restored_local_v1'
OUT=ROOT/'results/phase2_mujoco/persistence_evi_failure_analysis_v1'

def load(n,a):return json.loads(gzip.decompress((FIT/f'episode_{n:03}_{a}.json.gz').read_bytes()))
def snap(records,agent,step,phase,world,arm):
    grid=agent.memory.grid.astype('int8',copy=True)
    rec={'episode':None,'world_identity':world,'arm':arm,'step':int(step),'phase':phase,
         'free_cells':int((grid==0).sum()),'occupied_cells':int((grid==1).sum()),
         'unknown_cells':int((grid<0).sum()),'grid_sha256':hashlib.sha256(grid.tobytes()).hexdigest(),
         'grid_flat':''.join('1' if x==1 else '0' if x==0 else 'u' for x in grid.ravel())}
    if isinstance(agent,PersistenceEVIController):
        p=agent.probabilities(int(step));rec['p_mean_known']=float(p[grid>=0].mean()) if (grid>=0).any() else None
        rec['p_min_known']=float(p[grid>=0].min()) if (grid>=0).any() else None
        rec['p_max_known']=float(p[grid>=0].max()) if (grid>=0).any() else None
        rec['p_unknown_mean']=float(p[grid<0].mean()) if (grid<0).any() else None
        rec['probability_grid']=','.join(f'{float(x):.4f}' for x in p.ravel()) if agent.belief is not None else None
    records.append(rec)

def main():
    failure_rows=list(csv.DictReader((OUT/'failure_mechanism_classifications.csv').open()))
    cases={int(r['episode']):(r['world_identity'],int(r['schedule'])) for r in failure_rows if r['arm']=='c_ternary'}
    worlds={w['identity']:w for w in runner.reference.navigation.admitted_worlds()}
    _,_,prov,_=runner.reference.base.load_baseline();config=runner.reference.base.frozen_config(prov)
    records=[];validation=[]
    old_pd=PersistenceEVIController.decide;old_pr=PersistenceEVIController.refresh
    old_ad=ObservationController.decide;old_ar=ObservationController.refresh
    original_run=runner.run_arm
    for number,(world,schedule) in sorted(cases.items()):
      for arm in ('age','c_ternary','bc'):
        saved=load(number,arm);local=[];context={'agent':None,'world':world,'arm':arm,'episode':number}
        def patch_decide(original):
          def wrapped(agent,step,position):
            result=original(agent,step,position);snap(local,agent,step,'post_inference_pre_scan',world,arm);return result
          return wrapped
        def patch_refresh(original):
          def wrapped(agent,observation,step):
            result=original(agent,observation,step);snap(local,agent,step,'post_authorized_scan_refresh',world,arm);return result
          return wrapped
        PersistenceEVIController.decide=patch_decide(old_pd);PersistenceEVIController.refresh=patch_refresh(old_pr)
        ObservationController.decide=patch_decide(old_ad);ObservationController.refresh=patch_refresh(old_ar)
        try: row,trace,diag=runner.run_arm(worlds[world],schedule,arm,config)
        finally:
          PersistenceEVIController.decide=old_pd;PersistenceEVIController.refresh=old_pr
          ObservationController.decide=old_ad;ObservationController.refresh=old_ar
        sem_fields=('step','position','heading_yaw','action','moved','blocked','observation_granted','observation_count')
        saved_steps=saved['trace']['steps'];new=runner.reference.base._jsonable_row(trace['steps'])
        semantic=len(saved_steps)==len(new) and all(all(a.get(k)==b.get(k) for k in sem_fields) for a,b in zip(saved_steps,new))
        validation.append({'episode':number,'world_identity':world,'schedule':schedule,'arm':arm,'semantic_trace_match':semantic})
        if semantic:
            for r in local:r['episode']=number;records.append(r)
        print(f'{number} {arm}: semantic_match={semantic} snapshots={len(local)}',flush=True)
    # Preserve one compressed, append-only analysis dataset.
    with gzip.open(OUT/'memory_state_snapshots.jsonl.gz','xt',compresslevel=9) as f:
        for r in records:f.write(json.dumps(r,sort_keys=True,separators=(',',':'))+'\n')
    with (OUT/'memory_snapshot_replay_validation.csv').open('x',newline='') as f:
        fields=sorted({k for x in validation for k in x});w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(validation)

if __name__=='__main__':main()
