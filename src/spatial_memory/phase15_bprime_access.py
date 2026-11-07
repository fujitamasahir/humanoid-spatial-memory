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
from .phase15_bprime import VERSION, IntegrityError, development_partition

APPROVED_PRODUCTION_MANIFESTS = MappingProxyType({})
_APPROVAL_TOKEN = object()
GROUPS = ('source', 'configuration', 'dependencies', 'references')


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
            expected = APPROVED_PRODUCTION_MANIFESTS.get(str(path))
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
        if not self.synthetic and APPROVED_PRODUCTION_MANIFESTS.get(str(self.manifest_path))!=self.approved_sha256:
            raise IntegrityError('Production binding remains disabled')
        # Revalidate original approval as well as ancestry on every access.
        if safe_read(self.manifest_path)!=self.manifest_bytes or sha(self.manifest_bytes)!=self.approved_sha256:
            raise IntegrityError('Approved stage manifest changed')
        result = checked_path(path)
        if not result.is_relative_to(checked_path(self.root)):
            raise IntegrityError('Alternate root is not approved')
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
