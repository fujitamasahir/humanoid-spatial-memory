"""Immutable B′ checkpoints with a POSIX lease; no audit or automatic retries."""
from contextlib import contextmanager
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import uuid
from .phase15_bprime import VERSION, IntegrityError, development_partition
from .phase15_bprime_protocol import canonical_bytes, digest, development_path


def sync_directory(path):
    fd = os.open(path,os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class Checkpoints:
    """Stores complete caller-supplied records. Partial files block, not rerun.

    run_lock binds reviewed source/config/dependencies/reference commitments.
    Synthetic storage is explicitly labeled and cannot resume a production run.
    The class does not construct worlds, evaluate policy, or choose identities.
    """
    def __init__(self, root, run_lock, *, partition=None, synthetic=False):
        if not synthetic:
            development_partition(partition)  # before opening any path
        self.root = Path(root).resolve()
        if not synthetic:
            development_path(self.root,partition,self.root.parent)
            if self.root.name!=partition or self.root.parent.name!='phase1_5_bprime_development':
                raise IntegrityError('Production checkpoint root must be a new designated namespace')
        self.synthetic = synthetic
        self.partition = partition
        self.lock = json.loads(canonical_bytes(run_lock))
        if (self.lock.get('version')!=VERSION or self.lock.get('profile')!=
            ('synthetic' if synthetic else 'production')):
            raise IntegrityError('Checkpoint lock profile conflict')
        for key in ('source_sha256','configuration_sha256','dependencies_sha256','references_sha256'):
            value = self.lock.get(key,'')
            if len(value)!=64 or any(c not in '0123456789abcdef' for c in value):
                raise IntegrityError('Incomplete run/source/reference freeze')
        self.run_id = digest(self.lock)
        self.active = False

    def _require_lease(self):
        if not self.active:
            raise IntegrityError('Exclusive writer lease required')

    def _publish(self, path, data):
        temporary = self.root/'staging'/(path.name+'.'+uuid.uuid4().hex+'.part')
        with temporary.open('xb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary,path)  # exclusive; never overwrite existing evidence
        except FileExistsError as error:
            raise IntegrityError('Duplicate/conflicting publication; staged evidence preserved') from error
        sync_directory(path.parent)
        temporary.unlink()
        sync_directory(temporary.parent)

    @contextmanager
    def writer(self):
        self.root.mkdir(parents=True,exist_ok=True)
        for name in ('.writer.lock','staging','records','run.json'):
            if (self.root/name).is_symlink():
                raise IntegrityError('Symlink checkpoint metadata/directory denied')
        with (self.root/'.writer.lock').open('a+b') as lease:
            try:
                fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise IntegrityError('Concurrent B-prime writer') from error
            try:
                (self.root/'staging').mkdir(exist_ok=True)
                (self.root/'records').mkdir(exist_ok=True)
                lock_path = self.root/'run.json'
                if lock_path.exists():
                    if lock_path.read_bytes()!=canonical_bytes(self.lock):
                        raise IntegrityError('Changed source/config/dependencies/reference lock')
                else:
                    self._publish(lock_path,canonical_bytes(self.lock))
                self.active = True
                yield self
            finally:
                self.active = False
                fcntl.flock(lease,fcntl.LOCK_UN)

    def _name(self, identity):
        if not isinstance(identity,str) or not identity:
            raise IntegrityError('Missing checkpoint identity')
        if self.synthetic:
            if not identity.startswith('synthetic:'):
                raise IntegrityError('Synthetic checkpoint identity required')
        else:
            from .phase15_bprime import Identity
            fields = identity.split(':')
            if len(fields)!=4 or fields[0]!=VERSION:
                raise IntegrityError('Unknown production identity')
            actual = Identity(fields[1],fields[2],int(fields[3]))
            if actual.partition!=self.partition or actual.root!=identity:
                raise IntegrityError('Checkpoint partition conflict')
        return hashlib.sha256(identity.encode()).hexdigest()+'.json.gz'

    def _validate(self, body, expected_identity):
        self._name(expected_identity)
        if (body.get('run_id')!=self.run_id or body.get('identity')!=expected_identity
            or body.get('payload_sha256')!=digest(body.get('payload'))):
            raise IntegrityError('Checkpoint body/run/hash conflict')
        return body['payload']

    def write(self, identity, payload):
        self._require_lease()
        name = self._name(identity)
        if list((self.root/'staging').glob('*.part')):
            raise IntegrityError('Unresolved staging evidence blocks new work')
        body = dict(identity=identity,run_id=self.run_id,payload=payload,
                    payload_sha256=digest(payload))
        data = gzip.compress(canonical_bytes(body),mtime=0)
        self._publish(self.root/'records'/name,data)
        return dict(identity=identity,path='records/'+name,bytes=len(data),
                    sha256=hashlib.sha256(data).hexdigest())

    def inventory(self, entries, expected_identities, *, require_complete=True):
        if (self.root/'records').is_symlink() or (self.root/'staging').is_symlink():
            raise IntegrityError('Symlink checkpoint directory denied')
        expected = set(expected_identities)
        if len(expected)!=len(expected_identities):
            raise IntegrityError('Duplicate expected identity')
        seen = set()
        for entry in entries:
            identity = entry['identity']
            if identity in seen or identity not in expected:
                raise IntegrityError('Duplicate/unexpected checkpoint identity')
            name = self._name(identity)
            if entry['path']!='records/'+name:
                raise IntegrityError('Checkpoint path conflict')
            path = self.root/'records'/name
            if path.is_symlink():
                raise IntegrityError('Symlink checkpoint denied')
            packed = path.read_bytes()
            if len(packed)!=entry['bytes'] or hashlib.sha256(packed).hexdigest()!=entry['sha256']:
                raise IntegrityError('Checkpoint bytes changed')
            self._validate(json.loads(gzip.decompress(packed)),identity)
            seen.add(identity)
        if {p.name for p in (self.root/'records').iterdir()}!={self._name(i) for i in seen}:
            raise IntegrityError('Missing/extra/conflicting checkpoint file')
        if list((self.root/'staging').glob('*.part')):
            raise IntegrityError('Unresolved complete or torn staging evidence')
        if require_complete and seen!=expected:
            raise IntegrityError('Missing expected checkpoints')
        return expected-seen

    def recover(self, expected_identities):
        """Adopt complete staged records only. Preserve torn/conflicting bytes."""
        self._require_lease()
        expected = set(expected_identities)
        recovered = []
        for path in sorted((self.root/'staging').glob('*.part')):
            if path.is_symlink():
                raise IntegrityError('Symlink staged evidence denied before opening')
            try:
                packed = path.read_bytes()
                body = json.loads(gzip.decompress(packed))
                identity = body['identity']
                if identity not in expected:
                    raise IntegrityError('Unexpected staged identity')
                self._validate(body,identity)
            except (OSError,EOFError,ValueError,KeyError,UnicodeError) as error:
                raise IntegrityError('Torn/invalid staged evidence preserved; review required') from error
            destination = self.root/'records'/self._name(identity)
            try:
                os.link(path,destination)
            except FileExistsError as error:
                raise IntegrityError('Duplicate/conflicting staged record preserved') from error
            sync_directory(destination.parent)
            path.unlink()
            sync_directory(path.parent)
            recovered.append(dict(identity=identity,path='records/'+destination.name,
                                  bytes=len(packed),sha256=hashlib.sha256(packed).hexdigest()))
        return recovered
