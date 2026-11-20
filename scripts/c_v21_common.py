"""C v2.1 artifact helpers. No world-generation or sensor access."""
from __future__ import annotations
import hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/phase2_mujoco/c_v21_multistep_v1'
BASE_COMMIT='b6cb1fa233fbcd30b7ea26e88b865a69db96b91e'

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as f:f.write(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n')
def manifest(directory):
    directory=Path(directory)
    write(directory/'artifact_manifest.json',[{'path':p.relative_to(directory).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(directory.rglob('*')) if p.is_file() and p.name!='artifact_manifest.json'])
def commit():return subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
def verify_manifest(directory):
    directory=Path(directory);items=json.loads((directory/'artifact_manifest.json').read_text())
    names=set()
    for item in items:
        p=Path(item['path'])
        if p.is_absolute() or '..' in p.parts or str(p) in names:raise ValueError('Unsafe/duplicate artifact path')
        names.add(str(p));target=directory/p
        if target.stat().st_size!=item['bytes'] or sha(target)!=item['sha256']:raise ValueError(f'Artifact mismatch: {target}')
    return len(items)
