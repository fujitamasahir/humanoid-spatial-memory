"""Direct frozen six-arm RAA FIT comparison; actual original G1/safety pipeline."""
import sys,json,subprocess,hashlib,time,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src')]
from c_v21_common import write,manifest,verify_manifest,sha,commit
from run_c_v21a_depth_ablation import episode,parity
from run_dao_integration_v1_1 import native
from caa_common import run_case as measured,frozen_factory,ref,fit
from spatial_memory.route_adaptive_age_v1 import RouteAdaptiveAgeV1
from raa_preservation_v1 import verify_prior
OUT=ROOT/'results/phase2_mujoco/raa_v1';OLD=ROOT/'results/phase2_mujoco/age_cadence_v1/fit72'
REFERENCES=('periodic','age','age5');CANDIDATES=('raa_advance','raa_defer','raa_joint');ARMS=(*REFERENCES,*CANDIDATES)
SOURCES=('src/spatial_memory/route_adaptive_age_v1.py','tests/test_route_adaptive_age_v1.py','docs/raa_v1_protocol.md',
'scripts/run_raa_fit72_v1.py','scripts/caa_common.py','scripts/raa_preservation_v1.py',
'src/spatial_memory/scheduling.py','src/spatial_memory/cadence_age.py','src/spatial_memory/navigation.py',
'src/spatial_memory/evi.py','src/spatial_memory/memory.py','src/spatial_memory/evaluation.py',
'src/spatial_memory/mujoco_navigation.py','src/spatial_memory/mujoco_perception.py','src/spatial_memory/emergency_safety.py',
'scripts/evaluate_phase2_61ray_emergency_safety_full_288.py','scripts/evaluate_c_v2_candidate_coverage_fit72.py')


def fingerprints():return {p:sha(ROOT/p) for p in SOURCES}
def make(initial,arm,config,options):
    if arm in REFERENCES:return frozen_factory(initial,'age4' if arm=='age' else arm,config,options)
    sensor={k:config['mujoco_ray_sensor'][k] for k in ('range_m','horizontal_fov_deg','ray_count')};sensor['cell_size']=config['mujoco_cell_size_m']
    return RouteAdaptiveAgeV1(initial,mode=arm,sensor=sensor,**options)


def check():
    t=OUT/'prepared';t.mkdir(parents=True,exist_ok=False)
    tests=['tests/test_route_adaptive_age_v1.py','tests/test_history_gated_deadline_v1.py','tests/test_omission_public_features_v1.py',
        'tests/test_route_age.py','tests/test_view_age.py','tests/test_cadence_age.py','tests/test_caa_integration.py',
        'tests/test_change_aware_age.py','tests/test_phase2_mujoco.py','tests/test_phase2_emergency_safety.py']
    command=[sys.executable,'-m','pytest','-q',*tests,f'--junitxml={t/"tests.xml"}']
    result=subprocess.run(command,cwd=ROOT,text=True,capture_output=True);(t/'tests.log').write_text(result.stdout+result.stderr)
    write(t/'gate.json',{'returncode':result.returncode,'command':command});print(result.stdout+result.stderr,flush=True)
    if result.returncode:raise RuntimeError('Correctness gate failed')
    manifest(t);write(OUT/'binding.json',{'sources':fingerprints(),'prepared_manifest_sha256':sha(t/'artifact_manifest.json'),
        'reference_manifest_sha256':sha(OLD/'artifact_manifest.json'),'arms':list(ARMS),'base_commit':'9333928aa52acb24d42b739549bcaaa8a2180dbc'})


def gate():
    b=json.loads((OUT/'binding.json').read_text());verify_manifest(OUT/'prepared');verify_manifest(OLD)
    assert b['sources']==fingerprints() and b['prepared_manifest_sha256']==sha(OUT/'prepared/artifact_manifest.json')
    assert json.loads((OUT/'prepared/gate.json').read_text())['returncode']==0
    for p,h in {**b['sources'],'results/phase2_mujoco/raa_v1/binding.json':sha(OUT/'binding.json')}.items():
        assert hashlib.sha256(subprocess.check_output(['git','show',f'HEAD:{p}'],cwd=ROOT)).hexdigest()==h,p


def run(smoke):
    gate()
    if not smoke:
        verify_manifest(OUT/'smoke');assert json.loads((OUT/'smoke/summary.json').read_text())['status']=='PASS_SMOKE'
    target=OUT/('smoke' if smoke else 'fit72');target.mkdir(parents=True,exist_ok=False)
    _,_,prov,_=ref.base.load_baseline();config=ref.base.frozen_config(prov)
    worlds={p['identity']:p for p in ref.navigation.admitted_worlds()};assert len(worlds)==36
    write(target/'provenance.json',{'commit':commit(),'sources':fingerprints(),'config':config,'arms':list(ARMS),
        'original_safety_only':True,'reused_FIT_not_independent':True})
    completed=[];started=time.perf_counter();promises=0
    try:
        for n in range(1,3 if smoke else 73):
            baseline=episode(OLD,n,'age');identity,schedule,_,seed=baseline['trace']['key']
            for arm in ARMS:
                row,trace,diag=measured(worlds[identity],schedule,arm,config,factory=make)
                if arm in REFERENCES:parity(episode(OLD,n,arm),row,trace)
                if not smoke and n<=2:parity(episode(OUT/'smoke',n,arm),row,trace)
                if smoke:assert row['g1_unwanted_contact_pairs']==0
                ds=diag['decisions'];by={d['step']:d for d in ds}
                for d in ds:
                    assert d.get('point_plan_calls',0)<=1 and d.get('predicted_footprints',0)<=1 and d.get('sweep_cell_visits',0)<=200
                    if d.get('deferred') and d['step']+1 in by:
                        nxt=by[d['step']+1];assert nxt['forced_next'] and not nxt['deferred']
                        assert nxt['granted'] or nxt['used_before']>=20;promises+=1
                fit.save_episode(target,n,arm,row,trace,native(diag));completed.append([n,arm])
            if smoke or n%6==0:print(f'{"smoke" if smoke else "FIT72"} {n}/{2 if smoke else 72}',flush=True)
        write(target/'summary.json',{'status':'PASS_SMOKE' if smoke else 'COMPLETE','episodes':len(completed),
            'reference_parities':(2 if smoke else 72)*3,'forced_promises_checked':promises,'wall_seconds':time.perf_counter()-started})
        manifest(target)
    except Exception:
        (target/'failure.txt').write_text(traceback.format_exc());write(target/'partial.json',{'completed':completed});manifest(target);raise
if __name__=='__main__':
    stage=sys.argv[1]
    if stage=='check':check()
    elif stage in ('smoke','full'):run(stage=='smoke')
    else:raise ValueError('check/smoke/full only; reporting is read-only and separate')
