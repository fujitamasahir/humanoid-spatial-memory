"""Read-only preservation checks. Opens admitted FIT stores only, no worlds run."""
from __future__ import annotations
import gzip, hashlib, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src')]
from c_v21_common import sha
import evaluate_c_v2_candidate_coverage_fit72 as fit
import phase2_mujoco_navigation as nav
from spatial_memory.phase15_bprime_protocol import digest


def verify():
    audit=fit.verify_original_data_integrity();pairs=0
    for store in audit['stores']:
        directory=ROOT/store['path'];records={};ids=set();seqs=set()
        for p in (directory/'records').glob('*.json.gz'):
            body=json.loads(gzip.decompress(p.read_bytes()));ident=body['identity'];payload=body['payload']
            assert payload['partition']=='fit' and payload['identity']==ident
            assert body['payload_sha256']==digest(payload)
            assert p.name==hashlib.sha256(ident.encode()).hexdigest()+'.json.gz' and ident not in records
            records[ident]=payload
        for p in (directory/'recovered').glob('attempt-*.json'):
            e=json.loads(p.read_text());job=e['job'];ident=job['identity'];seq=job['sequence']
            assert ident in records and ident not in ids and seq not in seqs
            assert p.name==f'attempt-{seq+1}.json' and e['run_id']==store['run_id']
            assert all(records[ident].get(k)==job.get(k) for k in ('partition','mechanism','index'))
            ids.add(ident);seqs.add(seq)
        assert ids==set(records) and len(ids)==store['records'];pairs+=len(ids)
    caa=ROOT/'results/phase2_mujoco/caa_v1';items=json.loads((caa/'final_artifact_manifest.json').read_text())
    for item in items:
        path=caa/item['path'];assert path.stat().st_size==item['bytes'] and sha(path)==item['sha256']
    binding=json.loads((caa/'protocol_binding.json').read_text())
    assert all(sha(ROOT/p)==h for p,h in binding['source_sha256'].items())
    assets=json.loads((ROOT/'results/phase2_mujoco/c_v21_multistep_v1/environment/verification.json').read_text())['g1_assets']
    assert all(sha(ROOT/a['path'])==a['sha256'] for a in assets)
    return {'status':'PASS','checkpoint_receipt_pairs':pairs,
        'protected':nav.verify_preserved_prefix(),'caa_artifacts_unchanged':len(items),
        'caa_source_binding_unchanged':len(binding['source_sha256']),
        'g1_assets_unchanged':len(assets),'reserved_or_new_navigation_populations_accessed':False,
        'new_navigation_runs':0,'missing_inputs':[]}
if __name__=='__main__':print(json.dumps(verify(),indent=2))
