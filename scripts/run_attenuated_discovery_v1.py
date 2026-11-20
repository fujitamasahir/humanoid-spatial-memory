"""Read-only actual-scan assessment of fixed discovery attenuation estimates.

No simulator, navigation rollout, new sensor query, fitting or policy selection.
"""
from __future__ import annotations
import argparse,csv,gzip,json,subprocess,sys,time,traceback
from collections import defaultdict
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src')]
from c_v21_common import write,manifest,verify_manifest,sha,commit
from spatial_memory.attenuated_discovery_v1 import attenuated_footprints,FACTORS
from spatial_memory.discovery_observation import predicted_footprints
OUT=ROOT/'results/phase2_mujoco/attenuated_discovery_v1'
OLD=ROOT/'results/phase2_mujoco/res_phase_wait_v1'
BASE='99f004fc6ff2de576479b2756beb57f83ae23a9f'
SOURCES=('src/spatial_memory/attenuated_discovery_v1.py','src/spatial_memory/discovery_observation.py',
    'tests/test_attenuated_discovery_v1.py','scripts/run_attenuated_discovery_v1.py',
    'docs/attenuated_discovery_v1_protocol.md')
NAMES=('frontier','q50','q80','optimistic')

def load(p):return json.loads(p.read_text())
def fingerprints():return {p:sha(ROOT/p) for p in SOURCES}

def check():
    t=OUT/'prepared';t.mkdir(parents=True,exist_ok=False)
    for p in (OLD/'prepared',OLD/'compact',OLD/'analysis',OLD/'phase_analysis',OLD/'expansion',OLD/'expansion_analysis'):
        verify_manifest(p)
    cmd=[sys.executable,'-m','pytest','-q','tests/test_attenuated_discovery_v1.py','tests/test_discovery_observation.py']
    p=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
    (t/'tests.log').write_text(p.stdout+p.stderr);print(p.stdout+p.stderr,flush=True)
    write(t/'gate.json',{'returncode':p.returncode,'command':cmd})
    manifest(t)
    if p.returncode:raise SystemExit(p.returncode)
    write(OUT/'binding.json',{'base':BASE,'source_commit':commit(),'sources':fingerprints(),
        'prior_matrix_manifest_sha256':sha(OLD/'expansion/artifact_manifest.json'),
        'prepared_manifest_sha256':sha(t/'artifact_manifest.json'),
        'fixed_factors':list(FACTORS),'expected_episodes':416,'expected_paid_scans':1861})

def gate():
    b=load(OUT/'binding.json');verify_manifest(OUT/'prepared');verify_manifest(OLD/'expansion')
    assert b['sources']==fingerprints()
    assert b['prior_matrix_manifest_sha256']==sha(OLD/'expansion/artifact_manifest.json')
    assert b['prepared_manifest_sha256']==sha(OUT/'prepared/artifact_manifest.json')
    assert load(OUT/'prepared/gate.json')['returncode']==0
    import hashlib
    for name,h in b['sources'].items():
        assert hashlib.sha256(subprocess.check_output(['git','show',f'HEAD:{name}'],cwd=ROOT)).hexdigest()==h,name

def csv_write(p,rows):
    if not rows:raise ValueError('No rows')
    with p.open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def audit():
    gate();target=OUT/'audit';target.mkdir(parents=True,exist_ok=False)
    records=[];depth_rows=defaultdict(lambda:[0,0]);started=time.perf_counter()
    try:
        spec=load(OLD/'expansion/matrix_spec.json')
        episodes=0
        for n,d in enumerate(spec['scenarios'],1):
            for arm in spec['arms']:
                for version in spec['versions']:
                    source=OLD/'expansion'/f'{n:02}_{arm}_{version}.json.gz'
                    e=json.loads(gzip.decompress(source.read_bytes()))
                    decisions={v['step']:v for v in e['decisions']}
                    init=e['trace']['steps'][0]
                    assert init['step']==0
                    memory=np.full((d['height'],d['width']),-1,np.int8)
                    paid=e['paid'];assert len(paid)==e['actual_calls']['memory']==e['metrics']['observation_count']
                    assert paid and paid[0]['step']==0
                    previous=-1
                    for r in paid:
                        step=r['step'];assert step>previous;previous=step
                        pose=tuple(init['position'] if step==0 else decisions[step]['position'])
                        yaw=init['heading_yaw'] if step==0 else decisions[step]['yaw']
                        reading=np.asarray(r['reading'],dtype=np.int8)
                        assert reading.shape==memory.shape and np.isin(reading,[-1,0,1]).all()
                        yy,xx=np.where((reading>=0)&(memory<0))
                        actual={(int(x),int(y)) for x,y in zip(xx,yy)}-{pose}
                        t=time.perf_counter_ns()
                        error=attenuated_footprints(memory,pose,yaw,factors=(0.,.5,.8,1.))
                        elapsed=(time.perf_counter_ns()-t)/1e6
                        legacy=predicted_footprints(memory,pose,yaw)
                        assert error['frontier']==legacy['frontier'] and error['optimistic']==legacy['optimistic']
                        row={'scene_index':n,'scene':d['family'],'role':d['role'],'arm':arm,'safety':version,
                            'step':step,'initial':int(step==0),'actual_new':len(actual),
                            'optimistic_missed_actual':len(actual-set(error['unknown_depth'])),
                            'estimator_ms':elapsed}
                        for name,q in zip(NAMES,(0.,.5,.8,1.)):
                            weights=error['weights'][q];estimate=sum(weights.values())
                            row[name]=estimate
                            row[name+'_signed_error']=estimate-len(actual)
                            row[name+'_absolute_error']=abs(estimate-len(actual))
                            row[name+'_threshold_mismatch']=int((estimate>=5)!=(len(actual)>=5))
                        for c,k in error['unknown_depth'].items():
                            key=(version,d['role'],int(step==0),k)
                            depth_rows[key][0]+=1;depth_rows[key][1]+=int(c in actual)
                        records.append(row)
                        memory[reading>=0]=reading[reading>=0]
                    episodes+=1
            print(f'Audited scene {n}/{len(spec["scenarios"])}',flush=True)
        assert episodes==416 and len(records)==1861,(episodes,len(records))
        csv_write(target/'paid_scan_predictions.csv',records)
        csv_write(target/'depth_counts.csv',[{'safety':k[0],'role':k[1],'initial':k[2],'unknown_depth':k[3],
            'predicted_cells':v[0],'actually_discovered':v[1],'realized_fraction':v[1]/v[0]}
            for k,v in sorted(depth_rows.items())])
        write(target/'summary.json',{'episodes':episodes,'paid_scans':len(records),'noninitial_scans':sum(not r['initial'] for r in records),
            'navigation_runs':0,'new_sensor_calls':0,'elapsed_seconds':time.perf_counter()-started})
        manifest(target)
    except Exception:
        (target/'failure.txt').write_text(traceback.format_exc())
        write(target/'partial.json',{'scans_processed':len(records)})
        manifest(target);raise

def report():
    gate();verify_manifest(OUT/'audit')
    target=OUT/'analysis';target.mkdir(parents=True,exist_ok=False)
    with (OUT/'audit/paid_scan_predictions.csv').open(newline='') as f:rows=list(csv.DictReader(f))
    groups=defaultdict(list)
    for r in rows:
        if int(r['initial']):continue
        groups[(r['safety'],'all')].append(r)
        groups[(r['safety'],r['role'])].append(r)
    metrics=[]
    for (safety,role),rr in sorted(groups.items()):
        for name in NAMES:
            absolute=[float(r[name+'_absolute_error']) for r in rr]
            signed=[float(r[name+'_signed_error']) for r in rr]
            metrics.append({'safety':safety,'role':role,'estimate':name,'scans':len(rr),
                'mae':sum(absolute)/len(rr),'mean_signed_error':sum(signed)/len(rr),
                'threshold_mismatches':sum(int(r[name+'_threshold_mismatch']) for r in rr)})
    # Scene-level paired MAE differences; no independent inference or selection.
    per_scene=defaultdict(list)
    for r in rows:
        if not int(r['initial']):per_scene[r['safety'],r['role'],r['scene']].append(r)
    deltas=[]
    for (v,role,s),rr in sorted(per_scene.items()):
        for name in ('q50','q80'):
            deltas.append({'safety':v,'role':role,'scene':s,'estimate':name,'scans':len(rr),
                'mae_delta_vs_optimistic':sum(float(r[name+'_absolute_error'])-float(r['optimistic_absolute_error']) for r in rr)/len(rr)})
    csv_write(target/'metrics.csv',metrics);csv_write(target/'scene_deltas.csv',deltas)
    write(target/'summary.json',{'metrics':metrics,'primary_estimate':'q50','sensitivity_estimate':'q80',
        'new_navigation_runs':0,'new_sensor_calls':0,'controlled_policy_comparison':False,
        'selection_authorized':False,'caveat':'Only selected paid scans on previously visited trajectories; no inference at denied decisions or new worlds.'})
    lines=['# Attenuated discovery: retrospective actual-scan audit','',
       '|Safety|Role|Estimator|Noninitial scans|MAE|Signed error|Threshold mismatches|',
       '|---|---|---|---:|---:|---:|---:|']
    for r in metrics:
        lines.append(f"|{r['safety']}|{r['role']}|{r['estimate']}|{r['scans']}|{r['mae']:.3f}|{r['mean_signed_error']:.3f}|{r['threshold_mismatches']}|")
    lines+=['','Fixed q=.5 and .8 are heuristic transmission factors, not fitted/calibrated probabilities.',
      'Only actual previously authorized observations are assessed. Initial scans are saved separately in the CSV, excluded from the main comparison.',
      'No new controller or navigation policy is evaluated; no safety promotion or production cohort permission.']
    (target/'research_report.md').write_text('\n'.join(lines)+'\n');manifest(target);print('\n'.join(lines))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('stage',choices=('check','audit','report'))
    {'check':check,'audit':audit,'report':report}[p.parse_args().stage]()
