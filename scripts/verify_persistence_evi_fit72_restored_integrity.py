"""Read-only audit of restored FIT stores and completed FIT72 artifacts."""
from __future__ import annotations
import gzip, hashlib, json, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
sys.path.insert(0,str(ROOT/'src'))
import phase2_mujoco_navigation as nav
from spatial_memory.phase15_bprime_protocol import digest

OUT=ROOT/'results/phase2_mujoco/persistence_evi_fit72_analysis_restored_local_v2'
FIT=ROOT/'results/phase2_mujoco/persistence_evi_fit72_restored_local_v1'
STORES=(
 ('results/raw/phase15_macos_development/fit','results/phase15_macos_development/fit_independent_verification.json',313),
 ('results/raw/phase15_bprime_fit_recovery_1/store','results/phase15_bprime_recovery/continuation_execution.json',105),
 ('results/raw/phase15_bprime_fit_recovery_2/store','results/phase15_bprime_recovery_2/continuation_verification.json',2489),
)

def sha(raw):return hashlib.sha256(raw).hexdigest()

def main():
 stores=[];total=0
 for relative,proof_path,expected in STORES:
  root=ROOT/relative;proof=json.loads((ROOT/proof_path).read_text())
  run_id=proof.get('continuation_run_id') or proof.get('run_id')
  if not root.is_dir() or not run_id:raise ValueError(f'missing store/proof {relative}')
  records={};inventory=[]
  for p in sorted((root/'records').glob('*.json.gz')):
   raw=p.read_bytes();body=json.loads(gzip.decompress(raw));identity=body['identity'];payload=body['payload']
   if p.name!=sha(identity.encode())+'.json.gz' or payload.get('identity')!=identity or body.get('payload_sha256')!=digest(payload):
    raise ValueError(f'checkpoint mismatch {p}')
   records[identity]=body;inventory.append({'path':p.relative_to(root).as_posix(),'bytes':len(raw),'sha256':sha(raw)})
  receipts=sorted((root/'recovered').glob('attempt-*.json'))
  if len(records)!=expected or len(receipts)!=expected:raise ValueError(f'count mismatch {relative}')
  sequences=set()
  for p in receipts:
   raw=p.read_bytes();entry=json.loads(raw);job=entry['job'];seq=int(job['sequence'])
   if (p.name!=f'attempt-{seq+1}.json' or seq in sequences or entry.get('run_id')!=run_id
       or job['identity'] not in records):raise ValueError(f'receipt mismatch {p}')
   payload=records[job['identity']]['payload']
   if any(payload.get(k)!=job.get(k) for k in ('index','mechanism','partition')):
    raise ValueError(f'receipt/checkpoint payload disagreement {p}')
   sequences.add(seq);inventory.append({'path':p.relative_to(root).as_posix(),'bytes':len(raw),'sha256':sha(raw)})
  if list((root/'staging').iterdir()):raise ValueError(f'non-empty staging: {relative}')
  run_raw=(root/'run.json').read_bytes();inventory.append({'path':'run.json','bytes':len(run_raw),'sha256':sha(run_raw)})
  inventory.sort(key=lambda x:x['path'])
  root_hash=sha(json.dumps(inventory,sort_keys=True,separators=(',',':')).encode())
  stores.append({'path':relative,'records':len(records),'receipts':len(receipts),'run_id':run_id,
   'files_in_inventory':len(inventory),'bytes_in_inventory':sum(x['bytes'] for x in inventory),
   'inventory_sha256':root_hash,'staging_empty':True})
  total+=len(records)
 preserved=nav.verify_preserved_prefix();worlds=nav.admitted_worlds()
 if total!=2907 or len(worlds)!=36:raise ValueError('FIT population aggregate mismatch')
 manifest=json.loads((FIT/'artifact_manifest.json').read_text())
 for item in manifest:
  path=FIT/item['path'];raw=path.read_bytes()
  if len(raw)!=item['bytes'] or sha(raw)!=item['sha256']:raise ValueError(f'FIT result mismatch {item["path"]}')
 summary=json.loads((FIT/'summary.json').read_text())
 if (summary.get('status')!='COMPLETED_DESCRIPTIVE_FIT_NOT_VALIDATION'
     or summary.get('episodes_per_arm')!=72
     or not summary.get('baseline_metrics_and_traces_reproduced')):
  raise ValueError('FIT72 completion or baseline reproduction gate failed')
 result={'status':'PASS_READ_ONLY_FIT72_INTEGRITY','stores':stores,'total_checkpoint_payloads':total,
  'admitted_fit_worlds':len(worlds),'phase15_preserved_prefix':preserved,
  'fit72_arms':5,'episodes_per_arm':72,'baseline_metrics_and_traces_reproduced':True,
  'fit72_artifact_files_verified':len(manifest),'store_access':'read-only; no store writer/generator invoked'}
 target=OUT/'integrity_verification.json'
 with target.open('x',encoding='utf-8') as f:f.write(json.dumps(result,indent=2,sort_keys=True)+'\n')
 am=OUT/'analysis_manifest.json';data=json.loads(am.read_text())
 data['fit_store_integrity_sha256']=sha(target.read_bytes())
 am.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n')
 inventory=[]
 for p in sorted(x for x in OUT.rglob('*') if x.is_file() and x.name!='artifact_manifest.json'):
  raw=p.read_bytes();inventory.append({'path':p.relative_to(OUT).as_posix(),'bytes':len(raw),'sha256':sha(raw)})
 (OUT/'artifact_manifest.json').write_text(json.dumps(inventory,indent=2,sort_keys=True)+'\n')
 print(json.dumps(result,indent=2))

if __name__=='__main__':main()
