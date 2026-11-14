"""Independent, isolated post-screen review of C v2.0d evidence."""
from __future__ import annotations
import hashlib,json,subprocess,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/phase2_mujoco/c_v2d_topology_v1'
RESULT=OUT/'synthetic_mechanism_results.json'
MANIFEST=OUT/'artifact_manifest.json'
sys.path.insert(0,str(ROOT/'src'))
from spatial_memory.topology_review_d import review_document


def _sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def _artifact_integrity(binding):
    if not MANIFEST.is_file():return False,[]
    try:items=json.loads(MANIFEST.read_text())
    except Exception:return False,[]
    if not isinstance(items,list):return False,[]
    expected={'protocol_binding.json':OUT/'protocol_binding.json',
              'synthetic_mechanism_results.json':RESULT}
    seen=set();errors=[]
    for item in items:
        name=item.get('path')
        if name not in expected or name in seen:
            errors.append(f'unexpected or duplicate manifest path: {name}');continue
        seen.add(name);path=expected[name]
        if not path.is_file():errors.append(f'missing artifact: {name}');continue
        if item.get('bytes')!=path.stat().st_size or item.get('sha256')!=_sha(path):
            errors.append(f'hash/size mismatch: {name}')
    if seen!=set(expected):errors.append('manifest artifact population mismatch')
    return not errors,errors


def review():
    if not RESULT.is_file():raise FileNotFoundError(RESULT)
    binding=json.loads((OUT/'protocol_binding.json').read_text())
    data=json.loads(RESULT.read_text())
    artifact_ok,artifact_errors=_artifact_integrity(binding)
    cmd=[sys.executable,'-m','pytest','-q',
       'tests/test_topology_evi_c_correctness.py',
       'tests/test_topology_evi_d_equivalence.py',
       'tests/test_topology_evi_d_v2c_regression.py',
       'tests/test_c_v2c_fixture_annotations.py',
       'tests/test_topology_review_d.py']
    tested=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True)
    source_paths=binding.get('source_sha256',{})
    expected={path:_sha(ROOT/path) for path in source_paths}
    result=review_document(data,expected_source_hashes=expected,
      artifact_integrity_ok=artifact_ok,
      correctness_status=data.get('correctness_validation',{}).get('status'),
      annotation_status=data.get('annotation_validation',{}).get('status'),
      expected_fixture_population_sha256=binding.get('fixture_population_sha256'))
    checks=result['checks']
    checks['independent_test_rerun']=tested.returncode==0
    if tested.returncode:
        result.setdefault('validity_errors',{})['independent_test_rerun']=[tested.stderr or tested.stdout]
    if artifact_errors:
        result.setdefault('validity_errors',{})['artifact_integrity_details']=artifact_errors
    if result['status'] not in ('INVALID_STOP_BEFORE_FIT',):
        if not all(checks.values()):result['status']='INVALID_STOP_BEFORE_FIT'
        elif result['status']=='ACCEPTED_FOR_FIT' and data.get('numeric_gate',{}).get('status')!='PASS':
            result['status']='INVALID_STOP_BEFORE_FIT'
    result['FIT_authorized']=result['status']=='ACCEPTED_FOR_FIT'
    result.update({'protocol':'docs/phase2_c_v2d_topology_protocol.md',
      'intervention_protocol':'docs/phase2_c_v2d_fit_intervention_protocol.md',
      'synthetic_result_sha256':_sha(RESULT),'protocol_binding_sha256':_sha(OUT/'protocol_binding.json'),
      'source_sha256_independent':expected,'artifact_manifest_errors':artifact_errors,
      'independent_test_command':cmd,'independent_test_returncode':tested.returncode,
      'independent_test_stdout':tested.stdout,'independent_test_stderr':tested.stderr,
      'FIT_data_accessed_by_reviewer':False})
    target=OUT/'gate_review.json'
    target.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':result['status'],'checks':checks,
      'numeric_errors':result.get('numeric_errors'),'output':str(target)},indent=2))
    return 0 if result['status']=='ACCEPTED_FOR_FIT' else 2


if __name__=='__main__':raise SystemExit(review())
