"""Portable source/config provenance for evaluators and synthetic benchmarks."""
import hashlib
from importlib.metadata import distributions
import json
from pathlib import Path
import platform
import subprocess
import sys


def provenance(root, config):
    root=Path(root)
    files=sorted((root/'src').rglob('*.py'))+sorted((root/'scripts').glob('*.py'))
    files+=sorted((root/'docs').glob('phase1_4_*.md'))
    manifest={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest() for p in files}
    return dict(commit_sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
        working_tree_dirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True).strip()),
        source_files_sha256=manifest,source_sha256=hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest(),
        config=config,config_sha256=hashlib.sha256(json.dumps(config,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
        python=sys.version,platform=platform.platform(),processor=platform.processor(),
        packages=dict(sorted((d.metadata['Name'],d.version) for d in distributions())))
