"""Same-machine replay of all five frozen references, never a new policy."""
from __future__ import annotations
import gzip,json,sys
from time import perf_counter_ns
from c_v21_common import ROOT,OUT,write,manifest,commit,sha
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
import evaluate_c_v2_candidate_coverage_fit72 as fit
import evaluate_event_observation_fit72 as ref
from spatial_memory.scheduling import ObservationController
ARMS=('periodic','age','c0_audit','c_k','c_topology3d')
LABEL={'periodic':'periodic','age':'age',**fit.LABEL}
HIST=ROOT/'results/phase2_mujoco/c_v2d_topology_v1/fit72_descriptive_screen'


def run():
    target=OUT/'reference_replays';target.mkdir(parents=True,exist_ok=False)
    integrity=fit.verify_original_data_integrity()
    _,_,prov,_=ref.base.load_baseline();config=ref.base.frozen_config(prov)
    worlds={p['identity']:p for p in ref.navigation.admitted_worlds()}
    rows=[];original=ObservationController.decide
    for n in range(1,73):
        old=json.load(gzip.open(HIST/f'episode_{n:03}_age.json.gz','rt'))
        identity,schedule,_,seed=old['trace']['key']
        for arm in ARMS:
            elapsed=[]
            def timed(self,*a,**kw):
                t=perf_counter_ns()
                try:return original(self,*a,**kw)
                finally:elapsed.append(perf_counter_ns()-t)
            ObservationController.decide=timed
            try:row,trace,diag=fit.run_measured(worlds[identity],schedule,arm,config)
            finally:ObservationController.decide=original
            saved=json.load(gzip.open(HIST/f'episode_{n:03}_{LABEL[arm]}.json.gz','rt'))
            if ref.rdao_evaluator._signature(row)!=ref.rdao_evaluator._signature(saved['row']):raise RuntimeError(f'Reference metric drift {n} {arm}')
            ref._compare_trace(saved['trace'],ref.base._jsonable_row(trace))
            if arm in ('periodic','age'):diag['scheduler_total_ms']=sum(elapsed)/1e6
            fit.save_episode(target,n,LABEL[arm],row,trace,diag)
            flat=fit.flat(arm,row,diag);flat.update(episode=n,identity=identity,schedule=schedule,contact_free_success=bool(row['success'] and int(row['g1_unwanted_contact_pairs'])==0))
            rows.append(flat)
        if n%6==0:print(f'Reference replay {n}/72: exact five-arm parity',flush=True)
    fit.verify_original_data_integrity()
    fit.csv_write(target/'episodes.csv',rows)
    summary=fit.make_summary(rows,('c0_audit','c_k','c_topology3d'))
    write(target/'summary.json',{'status':'PASS_EXACT_ALL_360_REFERENCE_REPLAYS','source_commit':commit(),'same_machine_only':True,'scheduler_instrumentation':'Original decide measured; baseline previously uninstrumented now measured','config':config,'arms':summary,'protected_phase15':ref.navigation.verify_preserved_prefix()})
    manifest(target)
if __name__=='__main__':run()
