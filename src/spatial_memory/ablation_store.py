"""Ablation checkpoints using the unchanged assessment POSIX/atomic primitives.

Recovery and inventory follow the assessment store, with exact ablation admission.
"""
import gzip
import json
import os
from pathlib import Path
import uuid
from .assessment_store import canonical_bytes, atomic_bytes, sync_directory, writer_lease
from .tuning_spec import file_sha256


def publish_receipt(root, path, key):
    receipt=dict(episode_id=key,sha256=file_sha256(path),compressed_bytes=path.stat().st_size)
    atomic_bytes(Path(root)/'receipts'/(key+'.json'),canonical_bytes(receipt),immutable=True)
    return receipt


def verify_receipt(root,path,key):
    receipt_path=Path(root)/'receipts'/(key+'.json')
    if not receipt_path.exists():
        raise ValueError('Missing committed checksum receipt')
    receipt=json.loads(receipt_path.read_text())
    if receipt!=dict(episode_id=key,sha256=file_sha256(path),compressed_bytes=path.stat().st_size):
        raise ValueError('Committed trace checksum/size changed')
    return receipt

def validate_bundle(bundle,expected,run_id):
    if bundle['run_id']!=run_id or bundle['job']!=expected:
        raise ValueError('Conflicting episode/job/run identity')
    m=bundle['result']['metrics'];frames=bundle['result']['frames']
    if (m['purpose']!='assessment' or m['split']!='development' or m['method']!=expected['method']
        or m['seed']!=expected['seed'] or m['max_observations']!=expected['cap']
        or m['policy_parameters']!=expected['parameters'] or m['ablation']!=expected['ablation']
        or m['replicate']!=expected['replicate']):
        raise ValueError('Conflicting episode configuration')
    if (len(frames)!=m['elapsed_steps']+1 or m['elapsed_steps']>40
        or m['observation_count']!=sum(f['observation_granted'] for f in frames)
        or (expected['cap'] is not None and m['observation_count']>expected['cap'])
        or m['observation_cost']!=1.5*m['observation_count']
        or m['contact_free_success']!=(m['success'] and m['dynamic_contacts']==0)):
        raise ValueError('Invalid trace/metric ledger')
    if m['observation_requests']!=sum(f['observation_requested'] for f in frames[1:]):
        raise ValueError('Invalid request ledger')
    if m['observation_requests_denied']!=sum(f['observation_requested'] and not f['observation_granted'] for f in frames[1:]):
        raise ValueError('Invalid denied-request ledger')
    for frame in frames:
        if not all(key in frame for key in ('geometry','people','memory','planned','executed','errors','received_observation')):
            raise ValueError('Required trace field missing')
        if frame['step']>0 and 'policy_details' not in frame:
            raise ValueError('Missing complete decision trace')
    return bundle


def read_bundle(path):
    with gzip.open(path,'rt',encoding='utf-8') as stream:
        return json.load(stream)


def checkpoint(root,job,result,run_id):
    root=Path(root)
    bundle=dict(run_id=run_id,job=job,result=result)
    validate_bundle(bundle,job,run_id)
    pending=root/'staging';pending.mkdir(parents=True,exist_ok=True)
    destination=root/'episodes'/(job['episode_id']+'.json.gz')
    destination.parent.mkdir(parents=True,exist_ok=True)
    temporary=pending/(job['episode_id']+'.'+uuid.uuid4().hex+'.part')
    raw=canonical_bytes(bundle)
    with temporary.open('xb') as stream:
        with gzip.GzipFile(fileobj=stream,mode='wb',filename='',mtime=0,compresslevel=6) as zipped:
            zipped.write(raw)
        stream.flush();os.fsync(stream.fileno())
    # Lease serializes writers; this check also prevents accidental overwrites.
    if destination.exists():
        raise ValueError('Duplicate episode publication; staged file preserved')
    os.replace(temporary,destination);sync_directory(destination.parent)
    publish_receipt(root,destination,job['episode_id'])
    return destination


def recover_staging(root,expected,run_id):
    root=Path(root);actions=[]
    for path in sorted((root/'staging').glob('*.part')):
        try:
            bundle=read_bundle(path)
        except (OSError,EOFError,ValueError,UnicodeError):
            quarantine=root/'quarantine';quarantine.mkdir(exist_ok=True)
            destination=quarantine/path.name
            # Record bytes/hash before moving; never delete or truncate a partial trace.
            entry=dict(file=path.name,sha256=file_sha256(path),bytes=path.stat().st_size,
                       reason='incomplete/unreadable uncommitted gzip; episode will be retried')
            atomic_bytes(quarantine/(path.name+'.json'),canonical_bytes(entry),immutable=True)
            os.replace(path,destination);sync_directory(quarantine)
            actions.append(entry)
            continue
        key=bundle.get('job',{}).get('episode_id')
        if key not in expected:
            raise ValueError('Unexpected staged episode')
        validate_bundle(bundle,expected[key],run_id)
        destination=root/'episodes'/(key+'.json.gz')
        destination.parent.mkdir(exist_ok=True)
        if destination.exists():
            raise ValueError('Duplicate/conflicting complete staged episode; both preserved')
        os.replace(path,destination);sync_directory(destination.parent)
        publish_receipt(root,destination,key)
        actions.append(dict(episode_id=key,reason='adopted complete staged checkpoint without reexecution'))
    # A crash can occur between publishing the trace and its checksum receipt.
    # Adopt the complete validated bundle rather than executing its episode again.
    for path in sorted((root/'episodes').glob('*.json.gz')):
        key=path.name.removesuffix('.json.gz')
        if not (root/'receipts'/(key+'.json')).exists():
            if key not in expected:
                raise ValueError('Unexpected unreceipted checkpoint')
            validate_bundle(read_bundle(path),expected[key],run_id)
            publish_receipt(root,path,key)
            actions.append(dict(episode_id=key,reason='adopted complete published checkpoint without receipt; no reexecution'))
    return actions


def inventory(root,expected,run_id,*,require_complete=False):
    root=Path(root);found=set();entries=[];rows=[]
    for path in sorted((root/'episodes').glob('*')):
        if not path.is_file() or not path.name.endswith('.json.gz'):
            raise ValueError('Unexpected checkpoint path')
        bundle=read_bundle(path)
        key=bundle.get('job',{}).get('episode_id')
        if key not in expected or key in found or path.name!=key+'.json.gz':
            raise ValueError('Duplicate/unexpected/conflicting episode record')
        validate_bundle(bundle,expected[key],run_id)
        receipt=verify_receipt(root,path,key)
        found.add(key)
        rows.append(dict(**expected[key],metrics=bundle['result']['metrics']))
        entries.append(dict(episode_id=key,path=path.relative_to(root).as_posix(),
                            sha256=file_sha256(path),compressed_bytes=path.stat().st_size))
        # Only compact metrics survive this iteration; the full trace is discarded.
        del bundle
    missing=sorted(set(expected)-found)
    if {p.name for p in (root/'receipts').glob('*')}!={key+'.json' for key in found}:
        raise ValueError('Unexpected/missing checksum receipt inventory')
    if require_complete and missing:
        raise ValueError(f'Missing {len(missing)} prescribed episode records')
    return rows,entries,missing
