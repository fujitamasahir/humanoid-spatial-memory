"""Explicit local approvals and noncandidate payloads for synthetic unit tests."""
import json
from pathlib import Path
from spatial_memory.phase15_bprime_access import StageBinding, sha, packed
from spatial_memory.phase15_bprime import VERSION
from spatial_memory.phase15_bprime_store import Checkpoints


def binding_for(store, *, inventory=None, ledger=None, stores=None):
    store=Path(store).resolve();anchor=store.parent
    approval=anchor/(store.name+'.approval');approval.mkdir(exist_ok=True)
    inputs={'source':{'source.py':b'# explicit fixture source\n'},
            'configuration':{'config.json':b'{"fixture":true}'},
            'dependencies':{'dependency.bin':b'explicit fixture dependency'},
            'references':{'references.json':packed(inventory or {'fixture':'references'}),
                          'ledger.json':packed(ledger or {'fixture':'ledger'})}}
    files={}
    for group,entries in inputs.items():
        files[group]={}
        for name,data in entries.items():
            path=approval/name
            if path.exists() and path.read_bytes()!=data:
                raise ValueError('Synthetic approval inputs already changed')
            path.write_bytes(data)
            files[group][path.relative_to(anchor).as_posix()]=sha(data)
    manifest=dict(version=VERSION,profile='synthetic',partition='fit',root=str(anchor),
                  files=files,stores=[Path(p).resolve().relative_to(anchor).as_posix() for p in (stores or [store])],
                  reference_inventory_sha256=sha(inputs['references']['references.json']))
    raw=packed(manifest);path=approval/'approved.json'
    if path.exists() and path.read_bytes()!=raw:raise ValueError('Synthetic approval cannot be silently changed')
    path.write_bytes(raw)
    return StageBinding.load(path,approved_sha256=sha(raw),synthetic=True)


def toy_store(root, *, override=None, binding=None, backend=None, fault=None):
    return Checkpoints(root,override,synthetic=True,binding=binding or binding_for(root),
                       backend=backend,fault=fault)


def fixture(data):
    return dict(kind='synthetic-storage-fixture',data=data)
