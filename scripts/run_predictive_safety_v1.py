"""Prospectively frozen common-safety matrix; hand-defined engineering only."""
import sys,json,gzip,subprocess,hashlib,time,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from c_v21_common import write,sha,manifest,verify_manifest,commit
from safety_forensics_v1 import run_case,save,parity,OUT,ARMS
from predictive_safety_benchmark_v1 import all_cases
from spatial_memory.predictive_emergency_v1 import PredictiveEmergencySafetyV1
SOURCES=('src/spatial_memory/predictive_emergency_v1.py','scripts/safety_forensics_v1.py',
 'scripts/predictive_safety_benchmark_v1.py','scripts/run_predictive_safety_v1.py','tests/test_predictive_emergency_v1.py',
 'docs/predictive_safety_v1_protocol.md','docs/predictive_safety_contact_audit.md',
 'src/spatial_memory/emergency_safety.py','src/spatial_memory/pedestrian_tracking.py','src/spatial_memory/evaluation.py',
 'src/spatial_memory/mujoco_navigation.py','src/spatial_memory/mujoco_perception.py','src/spatial_memory/navigation.py',
 'src/spatial_memory/discovery_observation.py','src/spatial_memory/dao_navigation_compat_v1_1.py',
 'src/spatial_memory/change_aware_age.py','src/spatial_memory/cadence_age.py','src/spatial_memory/scheduling.py',
 'scripts/dao_engineering_scenes_v1.py','scripts/evaluate_phase2_61ray_emergency_safety_full_288.py')


def prepare():
    target=OUT/'prepared';target.mkdir(parents=True,exist_ok=False);write(target/'scenarios.json',all_cases())
    tests=['tests/test_predictive_emergency_v1.py','tests/test_phase2_safety_outcome_analysis.py',
      'tests/test_dao_navigation_infrastructure_v1.py','tests/test_dao_navigation_compat_v1_1.py',
      'tests/test_dao_generator_connectivity_v1_1.py','tests/test_dao_statistical_bounds_v1_1.py',
      'tests/test_discovery_observation.py','tests/test_dao_artifacts.py','tests/test_change_aware_age.py',
      'tests/test_caa_integration.py','tests/test_cadence_age.py','tests/test_phase2_mujoco.py',
      'tests/test_phase2_emergency_safety.py','tests/test_persistence_evi_evaluation.py']
    command=[sys.executable,'-m','pytest','-q',*tests,f'--junitxml={target/"tests.xml"}']
    r=subprocess.run(command,cwd=ROOT,text=True,capture_output=True);(target/'tests.log').write_text(r.stdout+r.stderr)
    write(target/'gate.json',{'command':command,'returncode':r.returncode});manifest(target)
    if r.returncode:raise RuntimeError(r.stdout+r.stderr)
    write(OUT/'binding.json',{'sources':{p:sha(ROOT/p) for p in SOURCES},'scenes_sha256':sha(target/'scenarios.json'),
      'prepared_manifest_sha256':sha(target/'artifact_manifest.json'),'formal_episodes':416,
      'arms':list(ARMS),'safety_versions':['original','predictive_v1']})
    print(r.stdout)


def gate():
    b=json.loads((OUT/'binding.json').read_text());assert b['sources']=={p:sha(ROOT/p) for p in SOURCES}
    verify_manifest(OUT/'prepared');verify_manifest(OUT/'forensics')
    assert json.loads((OUT/'prepared/gate.json').read_text())['returncode']==0
    assert b['scenes_sha256']==sha(OUT/'prepared/scenarios.json')
    for p,h in {**b['sources'],'results/phase2_mujoco/predictive_safety_v1/binding.json':sha(OUT/'binding.json'),
        'results/phase2_mujoco/predictive_safety_v1/prepared/scenarios.json':b['scenes_sha256']}.items():
        assert hashlib.sha256(subprocess.check_output(['git','show',f'HEAD:{p}'],cwd=ROOT)).hexdigest()==h,p


def formal():
    gate();target=OUT/'matrix';target.mkdir(parents=True,exist_ok=False);completed=[];started=time.perf_counter();parities=0
    try:
        for n,d in enumerate(json.loads((OUT/'prepared/scenarios.json').read_text()),1):
            for arm in ARMS:
                for label,cls in [('original',None),('predictive_v1',PredictiveEmergencySafetyV1)]:
                    e=run_case(d,arm,candidate_class=cls,detailed=False)
                    if d['role']=='original_regression' and arm.startswith('dao_') and cls is None:
                        base=ROOT/'results/phase2_mujoco/dao_integration_v1'
                        path=next(p for folder in ('engineering','engineering_recovery_v1_1') if (p:=base/folder/f'{d["family"]}_{arm}.json.gz').exists())
                        parity(json.loads(gzip.decompress(path.read_bytes())),e);parities+=1
                    e.update(role=d['role'],declared_contact_class=d['declared_contact_class'])
                    save(target/f'{n:02}_{arm}_{label}.json.gz',e)
                    completed.append({'scene_index':n,'family':d['family'],'role':d['role'],'arm':arm,'safety':label})
            print(f'Completed safety matrix scene{n}/26: {d["role"]}/{d["family"]}',flush=True)
        write(target/'summary.json',{'status':'COMPLETE_ACCOUNTING_NOT_SAFETY_ACCEPTANCE','source_freeze':commit(),
           'episodes':len(completed),'regression_original_DAO_exact_parities':parities,
           'elapsed_seconds':time.perf_counter()-started,'records':completed});manifest(target)
    except Exception:
        (target/'failure.txt').write_text(traceback.format_exc());write(target/'partial.json',{'completed':completed});manifest(target);raise
if __name__=='__main__':{'prepare':prepare,'formal':formal}[sys.argv[1]]()
