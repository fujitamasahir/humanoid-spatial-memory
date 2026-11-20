"""One committed C v2.1 formal run; refuses overwrite or source drift."""
from __future__ import annotations
import json,platform,resource,subprocess,sys,tracemalloc
from time import perf_counter_ns
import numpy as np
from c_v21_common import ROOT,OUT,write,manifest,sha,commit
from c_v21_fixtures import build,digest
sys.path.insert(0,str(ROOT/'src'))
from spatial_memory.multistep_evi import ARMS
from spatial_memory.candidate_coverage import information_value_original_audit,information_value_uncertainty_k
from spatial_memory.topology_evi_d import information_value_topology_d
from spatial_memory.multistep_reference import reference_cell,footprint

FROZEN={'C0':information_value_original_audit,'C-K':information_value_uncertainty_k,'C-Topology3-d':information_value_topology_d}
ALL={**FROZEN,**ARMS}


def run():
    binding_path=OUT/'protocol_binding.json';binding=json.loads(binding_path.read_text())
    committed=subprocess.check_output(['git','show','HEAD:'+binding_path.relative_to(ROOT).as_posix()],cwd=ROOT)
    if committed!=binding_path.read_bytes():raise RuntimeError('Prospective binding must already be committed')
    for name,expected in binding['source_sha256'].items():
        if sha(ROOT/name)!=expected:raise RuntimeError(f'Frozen source drift: {name}')
    fixtures=build()
    if digest(fixtures)!=binding['fixture_population_sha256']:raise RuntimeError('Fixture population drift')
    annotation_path=OUT/binding['annotation_path']
    annotations=json.loads(annotation_path.read_text())
    if annotations['status']!='PASS' or sha(annotation_path)!=binding['annotation_sha256']:raise RuntimeError('Annotation gate failed')
    target=OUT/'synthetic';target.mkdir(parents=True,exist_ok=False)
    results=[];timings=[];opportunity={a:0 for a in ARMS};controls={a:0 for a in ARMS};limits_ok=True;max_error=0.;fp={a:0 for a in ARMS}
    for f in fixtures:
        grid=np.array(f['grid'],dtype=np.int8);prob=np.array(f['probability']);args=(grid,prob,tuple(f['start']),tuple(f['goal']),f['yaw'],f['unknown'],f['sensor'],f['remaining'])
        row={}
        for name,fn in ALL.items():
            tracemalloc.start();result=fn(*args);_,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
            result['peak_traced_bytes']=peak
            row[name]=result
            if name in ARMS:
                k=3 if 'topology' in name else 5
                limits_ok &= (result['plan_calls']<=1+2*k and result['visibility_computations']<=1+12*k and result['prefix_step_visits']<=24*k and result['recovery_checks']<=36*k and result['counterfactual_grid_cells_copied']<=2*k*grid.size)
                scan=result['net_value']>0
                if f['family'] in ('last_chance','occupied_shortcut'):opportunity[name]+=int(scan)
                if f['expectation'] in ('postpone','no_benefit','ineligible'):controls[name]+=int(scan)
                for c in result['candidate_evaluations']:
                    cell=tuple(c['cell']);r=reference_cell(grid,cell,float(prob[cell[1],cell[0]]),f['start'],f['goal'],f['yaw'],f['unknown'],f['sensor'],result['cost'],'visibility' in name)
                    max_error=max(max_error,*(abs(c[key]-r[key]) for key in ('value','delay_regret','net_value','best_postpone_cost')))
                eligible=[c for c in footprint(grid,f['start'],f['yaw'],f['sensor']) if c!=tuple(f['start']) and .05<float(prob[c[1],c[0]])<.95]
                oracle=any(reference_cell(grid,c,float(prob[c[1],c[0]]),f['start'],f['goal'],f['yaw'],f['unknown'],f['sensor'],result['cost'],'visibility' in name)['scan'] for c in eligible)
                fp[name]+=int(scan and not oracle)
            if f['id'].endswith('_00'):
                for _ in range(3):fn(*args)
                samples=[]
                for _ in range(10):
                    t=perf_counter_ns();repeated=fn(*args);samples.append(perf_counter_ns()-t)
                    if repeated['net_value']!=result['net_value']:raise RuntimeError('Nondeterministic formal timing repeat')
                timings.append({'fixture':f['id'],'arm':name,'grid_cells':grid.size,'samples_ns':samples,'median_ns':float(np.median(samples)),'p95_ns':float(np.percentile(samples,95)),'max_ns':max(samples)})
        results.append({'id':f['id'],'family':f['family'],'results':row})
    checks={'operation_limits':bool(limits_ok),'restricted_reference_accuracy':max_error<=1e-9,'zero_global_false_positive':not any(fp.values()),'negative_controls_defer':not any(controls.values()),'opportunity_positive_k':opportunity['ms_k']==0 and opportunity['ms_k_visibility']==16,'opportunity_positive_topology':opportunity['ms_topology']==0 and opportunity['ms_topology_visibility']==16}
    document={'status':'FORMAL_SYNTHETIC_COMPLETED_PENDING_CONFORMANCE','source_commit':commit(),'binding_sha256':sha(binding_path),'source_sha256':binding['source_sha256'],'fixture_population_sha256':digest(fixtures),'fixtures':results,'timings':timings,'numeric_gate':{'status':'PASS' if all(checks.values()) else 'REJECTED','checks':checks,'max_reference_error':max_error,'opportunity_authorizations':opportunity,'negative_controls':controls,'global_false_positives':fp},'platform':platform.platform(),'python':sys.version,'peak_process_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'peak_memory_note':'macOS process RSS bytes; per-call traced Python peaks are separately instrumented; timing samples are untraced','FIT_or_reserved_data_accessed':False}
    write(target/'results.json',document);manifest(target)
    print(json.dumps(document['numeric_gate'],indent=2))
if __name__=='__main__':run()
