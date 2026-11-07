"""Finish reviewed reference sealing after independent reconstruction; no worlds.

Requires the committed read-only binding (which cannot create a checkpoint store).
This is delegated agent review under the user's explicit continuation approval,
not a claim of an external human signature or cryptographic third-party audit.
"""
import argparse,gzip,hashlib,json,os
from pathlib import Path
from spatial_memory.phase15_macos_monitored import MonitoredBackend,PROFILE
from spatial_memory.phase15_bprime_access import StageBinding
from spatial_memory.phase15_bprime_protocol import validate_inventory,digest,canonical_bytes
ROOT=Path(__file__).resolve().parents[1]
sha=lambda b:hashlib.sha256(b).hexdigest()


def main():
 p=argparse.ArgumentParser();p.add_argument('--evidence',type=Path,required=True);p.add_argument('--references',type=Path,required=True);a=p.parse_args()
 output=ROOT/'results/phase15_macos_development/reference_seal.json'
 if output.exists():raise RuntimeError('Preserve existing seal')
 root=a.references.resolve();independent=ROOT/'results/phase15_macos_development/reference_independent_verification.json'
 report=json.loads(independent.read_bytes());inv=json.loads((root/'inventory.json').read_bytes());ledger=json.loads((root/'ledger.json').read_bytes())
 assert report['status']=='PASS_INDEPENDENT_RECONSTRUCTION_NOT_YET_SEALED'
 assert report['inventory_sha256']==digest(inv) and report['ledger_sha256']==digest(ledger)
 assert (report['included_identities'],report['original_history'],report['admitted_development'],report['rejected_nonreferences'])==(2368,110,2258,2276)
 # Recheck original B-0 aliases against immutable source manifests.
 b0=json.loads((ROOT/'results/phase1_5b0/trace_storage_manifest.json').read_bytes())['records'];assert len(b0)==2
 for row in b0:
  raw=(a.evidence/'raw/phase1_5b0_development'/Path(row['path']).name).read_bytes()
  assert len(raw)==row['bytes'] and sha(raw)==row['sha256']
  old=json.loads(gzip.decompress(raw));current=json.loads(gzip.decompress((a.evidence/'raw/phase1_5b02_development'/Path(row['path']).name).read_bytes()))
  assert old['matrix']==current['matrix']
  for k in ('free','construction','seed','mechanism','partition','lineage'):assert old['geometry'][k]==current['geometry'][k]
 # Independently reconstitute the transport's entire B-02 bulk commitment.
 bulk=a.evidence/'raw/phase1_5b02_development';files=[]
 for path in sorted(bulk.rglob('*')):
  if path.is_file():
   raw=path.read_bytes();files.append(dict(path='results/raw/phase1_5b02_development/'+path.relative_to(bulk).as_posix(),bytes=len(raw),sha256=sha(raw)))
 expected=json.loads((ROOT/'results/phase1_5b02/delivery_verification.json').read_bytes())['storage']
 assert len(files)==expected['files'] and sum(f['bytes'] for f in files)==expected['bytes'] and digest(files)==expected['inventory_sha256']
 binding=StageBinding.load((ROOT/'configs/phase15_macos_bindings/reference-review.json').resolve())
 assert not json.loads(binding.manifest_bytes)['stores']
 backend=MonitoredBackend()
 try:
  verified=validate_inventory(inv,ledger,root,expected_digest=report['inventory_sha256'],expected_ledger_digest=report['ledger_sha256'],backend=backend,binding=binding)
  assert len(verified.included)==2368 and len(verified.rejected_ledger)==2276
  body=dict(status='SEALED_AFTER_INDEPENDENT_RECONSTRUCTION_AND_PRODUCTION_LOADER_VERIFICATION',
   scientific_version=inv['version'],resource_profile=PROFILE,inventory_sha256=digest(inv),ledger_sha256=digest(ledger),
   independent_report_sha256=sha(independent.read_bytes()),independent_verifier_sha256=report['verifier_sha256'],
   binding_sha256=binding.approved_sha256,backend_pin_sha256=backend.pin_sha,
   original_history=110,admitted_development=2258,rejected_nonreferences=2276,included_identities=2368,completed_history=65,
   unique_included_geometries=report['unique_included_geometries'],unique_included_topologies=report['unique_included_topologies'],
   original_B0_archives=2,B02_bulk_files=len(files),B02_bulk_bytes=sum(f['bytes'] for f in files),B02_bulk_inventory_sha256=digest(files),
   review='Independent algorithmic verifier plus agent review under explicit delegated user authorization; no external human-signature claim',
   source_evidence=str(a.evidence.resolve()),reference_root=str(root),registered_candidates_generated=0,
   loader_resource_calls=len(backend.events))
  events=ROOT/'results/raw/phase15_macos_development/reference_loader_resource_events.json.gz'
  with events.open('xb') as f:f.write(gzip.compress(canonical_bytes(backend.events),mtime=0));f.flush();os.fsync(f.fileno())
  body['loader_resource_events']=dict(path=str(events.relative_to(ROOT)),sha256=sha(events.read_bytes()),bytes=events.stat().st_size)
  with output.open('xb') as f:f.write(canonical_bytes(body));f.flush();os.fsync(f.fileno())
  print(json.dumps(body))
 finally:backend.close()

if __name__=='__main__':main()
