"""Reviewed path bindings and file-backed commitments; no population access.

Production registrations are deliberately empty pending separate restoration and
production-environment approval. Synthetic bindings cannot be upgraded in place.
"""
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import stat
from types import MappingProxyType
import subprocess
from .phase15_bprime import VERSION, IntegrityError, development_partition

APPROVED_PRODUCTION_MANIFESTS = MappingProxyType({})
_COMMITTED_REGISTRY = None
_APPROVAL_TOKEN = object()
GROUPS = ('source', 'configuration', 'dependencies', 'references')


def production_manifests():
    """Only committed, explicit Option B development bindings grant capability.

    The reviewed Git blob supplies provenance; a caller-provided digest or an
    uncommitted registry cannot enable execution. It is separate from run locks
    to avoid circular source/manifest hashes.
    """
    global _COMMITTED_REGISTRY
    root=Path(__file__).resolve().parents[2]
    path=root/'configs/phase15_macos_development_registry.json'
    if not path.exists():return APPROVED_PRODUCTION_MANIFESTS
    raw=safe_read(path)
    if _COMMITTED_REGISTRY is None:
        result=subprocess.run(['git','show','HEAD:configs/phase15_macos_development_registry.json'],cwd=root,capture_output=True)
        if result.returncode or raw!=result.stdout:raise IntegrityError('Production population generation disabled: uncommitted registry')
        _COMMITTED_REGISTRY=raw
    if raw!=_COMMITTED_REGISTRY:raise IntegrityError('Production registry changed during execution')
    value=json.loads(raw)
    approved_roots=value.get('roots',[value.get('root')])
    if (value.get('amendment')!='phase1.5-v0.4-MACOS-RSS-B1'
            or str(root) not in approved_roots):
        raise IntegrityError('Unapproved production authorization profile/root')
    for relative in value['manifests']:
        if not relative.startswith('configs/phase15_macos_bindings/') or Path(relative).is_absolute() or '..' in Path(relative).parts:
            raise IntegrityError('Unapproved production binding location')
    return {str(root/p):h for p,h in value['manifests'].items()}


def checked_path(path):
    path = Path(path)
    if not path.is_absolute() or '..' in path.parts:
        raise IntegrityError('Absolute nontraversing path required')
    for component in path.parts:
        if any(word in component.lower() for word in
               ('assessment','final','held_out','held-out','heldout')):
            raise IntegrityError('Reserved ancestor/path denied before opening')
    for parent in (*reversed(path.parents),path):
        if parent.is_symlink():
            raise IntegrityError('Symlink alias denied before opening')
    if path != path.resolve():
        raise IntegrityError('Noncanonical path alias')
    return path


def safe_read(path):
    """Walk from / with O_NOFOLLOW at every component, including the final file."""
    path = checked_path(path)
    fd = os.open('/',os.O_RDONLY|os.O_DIRECTORY)
    try:
        for component in path.parts[1:-1]:
            nxt = os.open(component,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
            os.close(fd)
            fd = nxt
        target = os.open(path.name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=fd)
        try:
            if not stat.S_ISREG(os.fstat(target).st_mode):
                raise IntegrityError('Regular committed file required')
            chunks = []
            while True:
                block = os.read(target,65536)
                if not block:
                    return b''.join(chunks)
                chunks.append(block)
        finally:
            os.close(target)
    except OSError as error:
        raise IntegrityError('Missing, aliased or inaccessible bound input') from error
    finally:
        os.close(fd)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def packed(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


@dataclass(frozen=True)
class StageBinding:
    root: Path
    manifest_path: Path
    approved_sha256: str
    manifest_bytes: bytes
    synthetic: bool
    _verified: object = None
    _seal: tuple = ()

    @classmethod
    def load(cls, manifest_path, *, approved_sha256=None, synthetic=False):
        path = checked_path(manifest_path)
        if not synthetic:
            expected = production_manifests().get(str(path))
            if expected is None or approved_sha256 not in (None,expected):
                raise IntegrityError('Production binding not approved; generation disabled')
        else:
            expected = approved_sha256
        raw = safe_read(path)
        if not expected or sha(raw)!=expected:
            raise IntegrityError('Manifest is not the independently approved bytes')
        value = json.loads(raw)
        development_partition(value.get('partition'))
        if value.get('version')!=VERSION or value.get('profile')!=('synthetic' if synthetic else 'production'):
            raise IntegrityError('Binding version/profile/stage conflict')
        root = checked_path(value['root'])
        if not path.is_relative_to(root):
            raise IntegrityError('Approval manifest outside bound development root')
        for group in GROUPS:
            entries = value.get('files',{}).get(group,{})
            if not entries:
                raise IntegrityError('All four commitment groups are mandatory')
            for relative,checksum in entries.items():
                if len(checksum)!=64 or any(c not in '0123456789abcdef' for c in checksum):
                    raise IntegrityError('Invalid reviewed file digest')
                cls._within(root,relative)
        return cls(root,path,expected,raw,synthetic,_APPROVAL_TOKEN,(root,path,expected,raw,synthetic))

    @staticmethod
    def _within(root,relative):
        relative = Path(relative)
        if relative.is_absolute() or '..' in relative.parts:
            raise IntegrityError('Bound paths must be relative and nontraversing')
        result = checked_path(root/relative)
        if not result.is_relative_to(root):
            raise IntegrityError('Path escapes approved root')
        return result

    def authorize(self,path):
        if (self._verified is not _APPROVAL_TOKEN or
            self._seal!=(self.root,self.manifest_path,self.approved_sha256,self.manifest_bytes,self.synthetic)):
            raise IntegrityError('Stage binding did not pass approval validation')
        if not self.synthetic and production_manifests().get(str(self.manifest_path))!=self.approved_sha256:
            raise IntegrityError('Production binding remains disabled')
        # Revalidate original approval as well as ancestry on every access.
        if safe_read(self.manifest_path)!=self.manifest_bytes or sha(self.manifest_bytes)!=self.approved_sha256:
            raise IntegrityError('Approved stage manifest changed')
        result = checked_path(path)
        if not result.is_relative_to(checked_path(self.root)):
            raise IntegrityError('Alternate root is not approved')
        if not self.synthetic:
            value=json.loads(self.manifest_bytes)
            files={self._within(self.root,p) for group in GROUPS for p in value['files'][group]}
            subtrees=[self._within(self.root,p) for p in value.get('stores',[])]
            if value.get('reference_archive_root'):
                subtrees.append(self._within(self.root,value['reference_archive_root']))
            if value.get('readonly_prefix_root'):
                subtrees.append(self._within(self.root,value['readonly_prefix_root']))
            subtrees.extend(self._within(self.root,p) for p in value.get('readonly_prefix_roots',[]))
            if (result not in {self.root,self.manifest_path,*files}
                and not any(result.is_relative_to(p) for p in subtrees)):
                raise IntegrityError('File is outside explicit development input/store bindings')
        return result

    def read(self,path):
        return safe_read(self.authorize(path))

    def verify(self):
        """Recompute file digests from bound bytes, never trust lock strings alone."""
        self.authorize(self.root)
        value = json.loads(self.manifest_bytes)
        lock = dict(version=VERSION,profile=value['profile'],binding_sha256=self.approved_sha256)
        for group in GROUPS:
            entries = value['files'][group]
            for relative,expected in entries.items():
                if sha(self.read(self._within(self.root,relative)))!=expected:
                    raise IntegrityError('Committed '+group+' input changed: '+relative)
            lock[group+'_sha256'] = sha(packed(entries))
        return lock
