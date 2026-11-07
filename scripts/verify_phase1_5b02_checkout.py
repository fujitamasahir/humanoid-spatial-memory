"""Verify staged blob bytes equal frozen working bytes; no experiments."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
git=['git','-c',f'safe.directory={ROOT}']
names=subprocess.check_output(git+['diff','--cached','--name-only'],cwd=ROOT,text=True).splitlines()
hashes={}
for name in names:
    blob=subprocess.check_output(git+['show',':'+name],cwd=ROOT)
    assert blob==(ROOT/name).read_bytes(),name
    hashes[name]=hashlib.sha256(blob).hexdigest()
pre=json.loads((ROOT/'results/phase1_5b02/preflight.json').read_text())
for name,expected in pre['source_sha256'].items():
    assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==expected,name
report=dict(all_staged_bytes_match_tested_worktree=True,files=len(hashes),sha256=hashes,
    config_checkout_rule='configs/.gitattributes: phase15_nauty_backend.json -text',
    production_source_freeze_unchanged=True,
    delivery_sha256=hashlib.sha256((ROOT/'results/phase1_5b02/delivery_verification.json').read_bytes()).hexdigest())
output=ROOT/'results/phase1_5b02/checkout_integrity.json'
if output.exists(): raise ValueError('Preserve existing checkout proof')
output.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(staged_files=len(hashes),exact_bytes_match=True,source_freeze_matches=True)))
