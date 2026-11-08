"""Create an append-only M3 binding for the verified 418-record fit prefix."""
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/phase15_bprime_recovery_2'
PREFIX = OUT / 'prefix.json'
BIND = ROOT / 'configs/phase15_macos_bindings/fit-recovery-2.json'
REGISTRY = ROOT / 'configs/phase15_macos_development_registry.json'
PRIOR_PREFIX = ROOT / 'results/phase15_bprime_recovery/prefix.json'
PRESERVATION = ROOT / 'results/phase1_5_bprime_macos/m3_checkpoint_receipt_manifest.json.gz'
LIVE_RSS = ROOT / 'results/phase1_5_bprime_macos/m3_live_rss_validation.json'
OPTION_PIN = ROOT / 'results/runs/phase15_m3_migration_c3/option_b_pin.json'
NATIVE_ROOT = ROOT / 'results/runs/phase15_m3_migration_c3/native-build/lib.macosx-10.13-universal2-cpython-312/pynauty'
NEW_STORE = 'results/raw/phase15_bprime_fit_recovery_2/store'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canon(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def file_sha(path):
    return sha(path.read_bytes())


def write_exclusive(path, raw):
    with path.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def main():
    if PREFIX.exists() or BIND.exists():
        raise RuntimeError('Second-continuation preparation artifacts already exist; preserve them')
    report = json.loads(LIVE_RSS.read_bytes())
    pin = json.loads(OPTION_PIN.read_bytes())
    if report['status'] != 'PASS_ABOVE_THRESHOLD_REJECTED':
        raise RuntimeError('Native M3 live RSS gate has not passed')
    if (report['policy']['threshold_bytes'], report['policy']['production_deadline_seconds']) != (536870912, 5):
        raise RuntimeError('Live RSS report does not preserve the approved Option B limits')
    if report['script']['sha256'] != file_sha(ROOT / 'scripts/validate_macos_live_rss.py'):
        raise RuntimeError('Live RSS report does not match the committed diagnostic source')

    old_prefix = json.loads(PRIOR_PREFIX.read_bytes())
    inventory = json.loads(__import__('gzip').decompress(PRESERVATION.read_bytes()))
    original = inventory['stores']['original_fit']
    first = inventory['stores']['continuation_1']
    if (original['records'], original['receipts'], first['records'], first['receipts']) != (313, 313, 105, 105):
        raise RuntimeError('Preservation manifest is not the verified 313+105 prefix')
    if (old_prefix['records'], old_prefix['run_id'], old_prefix['original_binding_sha256']) != (
            313, original['run_id'], old_prefix['original_binding_sha256']):
        raise RuntimeError('Original prefix manifest differs from preservation evidence')

    roots = {
        'original_fit': 'results/raw/phase15_macos_development/fit',
        'continuation_1': 'results/raw/phase15_bprime_fit_recovery_1/store',
    }
    epochs = [
        dict(name='original_fit', root=roots['original_fit'], run_id=original['run_id'],
             binding_path='configs/phase15_macos_bindings/fit.json',
             binding_sha256=old_prefix['original_binding_sha256'],
             source_commit=old_prefix['source_commit'], sequence_start=0, records=313),
        dict(name='continuation_1', root=roots['continuation_1'], run_id=first['run_id'],
             binding_path='configs/phase15_macos_bindings/fit-recovery-1.json',
             binding_sha256=file_sha(ROOT/'configs/phase15_macos_bindings/fit-recovery-1.json'),
             source_commit=subprocess.check_output(['git','rev-parse','e5112e7'],cwd=ROOT,text=True).strip(),
             sequence_start=313, records=105),
    ]
    files = []
    for entry in inventory['files']:
        match = next((name for name, root in roots.items() if entry['path'].startswith(root+'/')), None)
        if match is None:
            raise RuntimeError('Unexpected path in preserved checkpoint manifest')
        files.append(dict(epoch=match, path=entry['path'][len(roots[match])+1:],
                          bytes=entry['bytes'], sha256=entry['sha256']))
    if len(files) != 836:
        raise RuntimeError('Expected exactly 836 checkpoint and receipt commitments')
    for item in files:
        path=ROOT/roots[item['epoch']]/item['path'];raw=path.read_bytes()
        if len(raw)!=item['bytes'] or sha(raw)!=item['sha256']:
            raise RuntimeError('Checkpoint/receipt changed during binding preparation: '+str(path))
    prefix = dict(schema=1, partition='fit', records=418, epochs=epochs,
                  preservation_manifest='results/phase1_5_bprime_macos/m3_checkpoint_receipt_manifest.json.gz',
                  preservation_manifest_sha256=file_sha(PRESERVATION), files=files)
    prefix_raw=canon(prefix)
    OUT.mkdir(exist_ok=False)
    write_exclusive(PREFIX,prefix_raw)

    source={}
    for path in sorted((ROOT/'src/spatial_memory').glob('phase15*.py')):
        source[path.relative_to(ROOT).as_posix()]=file_sha(path)
    for path in sorted((ROOT/'scripts').glob('*phase15_macos*.py')):
        source[path.relative_to(ROOT).as_posix()]=file_sha(path)
    source['scripts/prepare_phase15_macos_recovery_2.py']=file_sha(Path(__file__).resolve())

    configuration={p.relative_to(ROOT).as_posix():file_sha(p)
                   for p in sorted((ROOT/'docs').glob('phase1_5*.md'))}
    for rel in ('configs/phase15_macos_option_b.json','configs/phase15_nauty_backend.json'):
        configuration[rel]=file_sha(ROOT/rel)

    dependencies={p:h for p,h in pin['artifact_sha256'].items()}
    dependencies['results/runs/phase15_m3_migration_c3/option_b_pin.json']=file_sha(OPTION_PIN)
    dependencies['results/phase1_5_bprime_macos/m3_environment_validation.json']=file_sha(
        ROOT/'results/phase1_5_bprime_macos/m3_environment_validation.json')
    dependencies['results/phase1_5_bprime_macos/build_manifest.json']=file_sha(
        ROOT/'results/phase1_5_bprime_macos/build_manifest.json')

    reference_paths=[
        'configs/phase15_macos_bindings/fit.json',
        'configs/phase15_macos_bindings/fit-recovery-1.json',
        'results/phase15_bprime_recovery/prefix.json',
        'results/phase15_bprime_recovery/continuation_verification.json',
        'results/phase15_bprime_recovery/continuation_execution.json',
        'results/phase15_macos_development/development_storage_manifest.json.gz',
        'results/phase15_macos_development/fit_post_stop_integrity.json',
        'results/phase15_macos_development/fit_execution.json',
        'results/phase15_macos_development/reference_independent_verification.json',
        'results/phase15_macos_development/reference_seal.json',
        'results/raw/phase15_macos_development/references/inventory.json',
        'results/raw/phase15_macos_development/references/ledger.json',
        'results/raw/phase15_macos_development/references/historical-completion.json',
        'results/raw/phase15_macos_development/references/preparation.json',
        'results/phase1_5_bprime_macos/m3_checkpoint_receipt_manifest.json.gz',
        'results/phase1_5_bprime_macos/m3_live_rss_validation.json',
        'scripts/validate_macos_live_rss.py',
        'results/phase15_bprime_recovery_2/prefix.json',
    ]
    references={rel:file_sha(ROOT/rel) for rel in reference_paths}
    inv=json.loads((ROOT/'results/raw/phase15_macos_development/references/inventory.json').read_bytes())
    inventory_sha=sha(canon(inv))
    binding=dict(version='phase1.5-v0.4-BPRIME-1',profile='production',partition='fit',
        root=str(ROOT),files=dict(source=source,configuration=configuration,
            dependencies=dependencies,references=references),stores=[NEW_STORE],
        reference_inventory_sha256=inventory_sha,prior_partitions={},
        reference_archive_root='results/raw/phase15_macos_development/references',
        readonly_prefix_roots=[roots['original_fit'],roots['continuation_1']],
        continuation_prefix=dict(path='results/phase15_bprime_recovery_2/prefix.json',sha256=sha(prefix_raw)),
        runtime=dict(python=sys.version,executable_sha256=file_sha(Path(sys.executable).resolve()),
                     machine=platform.machine(),system=platform.system(),numpy='2.2.6',
                     native_artifact_sha256=pin['artifact_sha256'][next(
                         p for p in pin['artifact_sha256'] if p.endswith('.so'))],
                     option_b_pin_sha256=file_sha(OPTION_PIN)))
    binding_raw=canon(binding)
    write_exclusive(BIND,binding_raw)

    registry=json.loads(REGISTRY.read_bytes())
    key=BIND.relative_to(ROOT).as_posix()
    if key in registry['manifests']:
        raise RuntimeError('Registry already contains the second continuation binding')
    roots_allowed=list(registry.get('roots',[registry['root']]))
    if registry['root'] not in roots_allowed:roots_allowed.insert(0,registry['root'])
    if str(ROOT) not in roots_allowed:roots_allowed.append(str(ROOT))
    registry['roots']=roots_allowed
    registry['manifests'][key]=sha(binding_raw)
    temp=REGISTRY.with_name(REGISTRY.name+'.recovery-2.tmp')
    write_exclusive(temp,canon(registry))
    os.replace(temp,REGISTRY)
    print(json.dumps(dict(status='PREPARED_REQUIRES_COMMIT',prefix_records=418,
        original_run_id=original['run_id'],continuation_1_run_id=first['run_id'],
        next_sequence=418,next_identity='phase1.5-v0.4-BPRIME-1:fit:V:80020368',
        prefix_sha256=sha(prefix_raw),binding_sha256=sha(binding_raw),
        registry_sha256=file_sha(REGISTRY)),indent=2),flush=True)


if __name__=='__main__':
    main()
