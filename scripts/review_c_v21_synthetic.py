"""New-process conformance check, independent from the formal runner."""
import json,sys
from c_v21_common import ROOT,OUT,write,sha,verify_manifest
from c_v21_fixtures import build,digest
sys.path.insert(0,str(ROOT/'src'))
from spatial_memory.multistep_review import review_document


def run():
    binding=json.loads((OUT/'protocol_binding.json').read_text())
    document=json.loads((OUT/'synthetic/results.json').read_text())
    sources_ok=(all(sha(ROOT/n)==s for n,s in binding['source_sha256'].items()) and document['source_sha256']==binding['source_sha256'] and document['binding_sha256']==sha(OUT/'protocol_binding.json'))
    try:verify_manifest(OUT/'synthetic');artifacts_ok=True
    except Exception:artifacts_ok=False
    annotation_path=OUT/binding['annotation_path']
    annotations=json.loads(annotation_path.read_text())
    fixtures=build()
    annotation_ok=(annotations['status']=='PASS' and sha(annotation_path)==binding['annotation_sha256'] and digest(fixtures)==binding['fixture_population_sha256']==document['fixture_population_sha256'])
    try:review=review_document(document,fixtures,sources_ok=sources_ok,artifacts_ok=artifacts_ok,annotations_ok=annotation_ok)
    except Exception as exc:review={'status':'INVALID_STOP_BEFORE_FIT','FIT_authorized':False,'review_error':repr(exc)}
    if document['numeric_gate']['status']!='PASS' and review.get('status')=='ACCEPTED_FOR_FIT':
        review.update(status='INVALID_STOP_BEFORE_FIT',FIT_authorized=False,review_error='Runner and reviewer gates disagree')
    review.update(result_sha256=sha(OUT/'synthetic/results.json'),binding_sha256=sha(OUT/'protocol_binding.json'),FIT_data_accessed=False,review_process='separate invocation; does not import new policy or runner')
    write(OUT/'gate_review.json',review)
    print(json.dumps(review,indent=2))
    return 0 if review['FIT_authorized'] else 2
if __name__=='__main__':raise SystemExit(run())
