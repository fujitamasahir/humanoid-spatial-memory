"""Evaluate seven deterministic mechanism fixtures; never loads admitted worlds."""
from __future__ import annotations
import hashlib,json,sys
from time import perf_counter_ns
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from spatial_memory.evi import information_value,EVIParameters
from spatial_memory.candidate_coverage import (ExpandedEVIParameters,
    information_value_route,information_value_uncertainty_k)
from spatial_memory.candidate_coverage import eligible_candidates,rank_uncertainty_candidates
OUT=ROOT/'results/phase2_mujoco/c_v2_candidate_coverage_v1/synthetic_fixture_frozen_v7'
SENSOR={'range_m':6.,'cell_size':.75,'horizontal_fov_deg':120.,'ray_count':61}

def base():
    g=np.zeros((15,15),dtype=np.int8);g[[0,-1],:]=1;g[:,[0,-1]]=1
    p=np.full(g.shape,.01);return g,p

def fixtures():
    g,p=base();g[1:14,6]=1;g[7,6]=-1
    route=[(x,7) for x in range(2,13)]
    for x in (3,4,5,6):g[7,x]=-1
    for c in ((3,7),(4,7),(5,7)):p[c[1],c[0]]=.5
    critical=(6,7);p[7,6]=.5
    yield 'critical_uncertain_cell_outside_original_top3',g,p,route,critical

    g,p=base();g[6,4:9]=g[8,4:9]=1;route=[(x,7) for x in range(2,13)]
    for x in (3,4,5,6):g[7,x]=-1;p[7,x]=.5
    yield 'narrow_route_bottleneck',g,p,route,critical

    g,p=base();route=[(x,7) for x in range(2,13)]
    for c in ((6,7),(6,6),(6,8),(4,5)):g[c[1],c[0]]=-1;p[c[1],c[0]]=.5
    yield 'multiple_alternative_routes',g,p,route,(6,7)

    g,p=base();g[6,5:9]=g[8,5:9]=1;route=[(x,7) for x in range(2,13)]
    g[7,6]=-1;g[6,8]=-1;p[7,6]=.1;p[6,8]=.5
    yield 'irrelevant_high_uncertainty_cells',g,p,route,(6,7)

    g,p=base();route=[(x,7) for x in range(2,13)]
    for c in ((8,7),(8,6),(8,8),(3,6),(3,8)):g[c[1],c[0]]=-1;p[c[1],c[0]]=.45
    yield 'uncertain_obstacle_near_future_route_branch',g,p,route,(8,7)

    g,p=base();route=[(x,7) for x in range(2,13)]
    g[6,4]=-1;p[6,4]=.5
    yield 'no_observation_benefit',g,p,route,(4,6)

    g,p=base();g[6,5:9]=g[8,5:9]=1;route=[(x,7) for x in range(2,13)]
    for x in (5,6):g[7,x]=-1;p[7,x]=.5
    yield 'multiple_correlated_uncertain_cells',g,p,route,(5,7)

def run():
    OUT.mkdir(parents=True,exist_ok=False)
    variants={
      'C0':(information_value,EVIParameters(max_candidates=3)),
      'C-K':(information_value_uncertainty_k,ExpandedEVIParameters(max_candidates=5)),
      'C-Route3':(information_value_route,ExpandedEVIParameters(max_candidates=3)),
      'C-RouteK':(information_value_route,ExpandedEVIParameters(max_candidates=5)),}
    records=[]
    for name,g,p,route,critical in fixtures():
      for variant,(fn,params) in variants.items():
        started=perf_counter_ns()
        result=fn(g,p,(2,7),(12,7),0.,'optimistic',SENSOR,10,params)
        elapsed_ns=perf_counter_ns()-started
        selected=result.get('shortlisted_candidates',[])
        if variant=='C0':
          cells,_=eligible_candidates(g,p,(2,7),0.,SENSOR)
          ranked,_=rank_uncertainty_candidates(p,cells,result['nominal_route'] or [(2,7)])
          selected_cells=ranked[:params.max_candidates]
        else:selected_cells=[tuple(x['cell']) for x in selected]
        records.append({'fixture':name,'variant':variant,'candidate_count':result.get('candidate_count',len(cells) if variant=='C0' else None),
          'selected_candidates':[list(c if isinstance(c,tuple) else c['cell']) for c in selected] if selected else [list(c) for c in selected_cells],
          'critical_fixture_cell':list(critical),'critical_selected':critical in selected_cells,
          'best_value_cell':list(result['cell']) if result.get('cell') is not None else None,
          'V':result['value'],'D':result['delay_regret'],'cost':result['cost'],
          'net_value':result['net_value'],'scan_authorized':result['net_value']>0,
          'plan_calls':result['plan_calls'],'call_cap':7 if variant in ('C0','C-Route3') else 11,
          'diagnostic_elapsed_ns':elapsed_ns})
    grouped={}
    for row in records:grouped.setdefault(row['fixture'],{})[row['variant']]=row
    critical_names=('critical_uncertain_cell_outside_original_top3','narrow_route_bottleneck')
    c0_critical=sum(grouped[n]['C0']['critical_selected'] for n in critical_names)
    route3_critical=sum(grouped[n]['C-Route3']['critical_selected'] for n in critical_names)
    no_benefit={v:grouped['no_observation_benefit'][v]['scan_authorized']
                for v in ('C0','C-Route3','C-K','C-RouteK')}
    calls_within_caps=all(x['plan_calls']<=x['call_cap'] for x in records)
    gate={'route3_critical_selection_exceeds_C0':route3_critical>c0_critical,
      'route3_critical_selected_count':route3_critical,'C0_critical_selected_count':c0_critical,
      'no_benefit_fixture_scan_authorized':no_benefit,
      'all_plan_caps_respected':calls_within_caps,
      'status':'PASS' if route3_critical>c0_critical and not any(no_benefit.values()) and calls_within_caps else 'REJECTED_BEFORE_FIT72'}
    data={'status':'COMPLETED_SYNTHETIC_MECHANISM_FIXTURES','mechanism_gate':gate,
      'descriptive_fit72_permitted_by_frozen_gate':gate['status']=='PASS',
      'admitted_worlds_loaded':False,'phase15_generator_called':False,'fixtures':records,
      'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
      'policy_source_sha256':hashlib.sha256((ROOT/'src/spatial_memory/candidate_coverage.py').read_bytes()).hexdigest()}
    path=OUT/'synthetic_fixture_results.json';path.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n')
    inventory=[]
    for f in sorted(OUT.iterdir()):
      b=f.read_bytes();inventory.append({'path':f.name,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()})
    (OUT/'artifact_manifest.json').write_text(json.dumps(inventory,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':data['status'],'mechanism_gate':gate,'fixtures':len(list(fixtures())),'runs':len(records),'result':str(path)},indent=2))
if __name__=='__main__':run()
