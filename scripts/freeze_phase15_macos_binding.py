"""Freeze explicit development capabilities; no generator is imported or executed.

New bindings are exclusive. The registry is append-only and must be committed
before StageBinding can consume it. A review binding has no checkpoint stores.
"""
import argparse,hashlib,json,os,platform,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sha=lambda b:hashlib.sha256(b).hexdigest()
pack=lambda v:json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def main():
 p=argparse.ArgumentParser();p.add_argument('--name',required=True);p.add_argument('--partition',choices=['fit','calibration','selection'],required=True);p.add_argument('--references',type=Path,required=True);p.add_argument('--store');p.add_argument('--prior-seals',type=Path)
 a=p.parse_args()
 if '/' in a.name or '..' in a.name:raise ValueError('Simple binding name required')
 ref=a.references.resolve();inv=json.loads((ref/'inventory.json').read_bytes())
 pin=json.loads((ROOT/'configs/phase15_macos_option_b.json').read_bytes())
 source={str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in sorted((ROOT/'src/spatial_memory').glob('phase15*.py'))}
 for p in sorted((ROOT/'scripts').glob('*phase15_macos*.py')):source[str(p.relative_to(ROOT))]=sha(p.read_bytes())
 config={str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in (ROOT/'docs').glob('phase1_5*.md')}
 config['configs/phase15_macos_option_b.json']=sha((ROOT/'configs/phase15_macos_option_b.json').read_bytes())
 dependencies={p:h for p,h in pin['artifact_sha256'].items() if p.startswith('results/runs/')}
 references={str((ref/n).relative_to(ROOT)):sha((ref/n).read_bytes()) for n in ('inventory.json','ledger.json','historical-completion.json','preparation.json')}
 # Original/native verification provenance is committed separately; source bytes
 # are checked again when sealing and by the production inventory loader.
 verification=ROOT/'results/phase15_macos_development/reference_independent_verification.json'
 references[str(verification.relative_to(ROOT))]=sha(verification.read_bytes())
 seal=ROOT/'results/phase15_macos_development/reference_seal.json'
 if a.store is not None:
  if not seal.exists():raise ValueError('Sealed reference inventory required before a population capability')
  references[str(seal.relative_to(ROOT))]=sha(seal.read_bytes())
 previous={} if a.prior_seals is None else json.loads(a.prior_seals.read_bytes())
 value=dict(version='phase1.5-v0.4-BPRIME-1',profile='production',partition=a.partition,root=str(ROOT),
    files=dict(source=source,configuration=config,dependencies=dependencies,references=references),
    stores=[] if a.store is None else [a.store],reference_inventory_sha256=sha(pack(inv)),prior_partitions=previous,
    reference_archive_root=str(ref.relative_to(ROOT)),
    runtime=dict(python=sys.version,executable_sha256=sha(Path(sys.executable).resolve().read_bytes()),machine=platform.machine(),system=platform.system(),numpy='2.2.6'))
 target=ROOT/'configs/phase15_macos_bindings'/(a.name+'.json');target.parent.mkdir(exist_ok=True)
 raw=pack(value)
 with target.open('xb') as f:f.write(raw)
 registry_path=ROOT/'configs/phase15_macos_development_registry.json'
 registry=json.loads(registry_path.read_bytes()) if registry_path.exists() else dict(amendment='phase1.5-v0.4-MACOS-RSS-B1',root=str(ROOT),manifests={})
 key=str(target.relative_to(ROOT));assert key not in registry['manifests'];registry['manifests'][key]=sha(raw)
 temporary=registry_path.with_suffix('.tmp')
 with temporary.open('xb') as f:f.write(pack(registry));f.flush();os.fsync(f.fileno())
 os.replace(temporary,registry_path)
 print(json.dumps(dict(binding=key,sha256=sha(raw),stores=value['stores'],requires_commit=True)))

if __name__=='__main__':main()
