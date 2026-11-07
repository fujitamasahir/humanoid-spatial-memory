"""Bound, commitment-verified immutable checkpoints. No population driver."""
from contextlib import contextmanager
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import uuid
from .phase15_bprime import VERSION, IntegrityError, development_partition
from .phase15_bprime_protocol import canonical_bytes, digest
from .phase15_bprime_access import StageBinding, checked_path
from .phase15_bprime_records import checkpoint_payload


def sync_directory(path):
    fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(fd)
    finally:os.close(fd)


class Checkpoints:
    def __init__(self,root,run_lock=None,*,partition=None,synthetic=False,binding=None,backend=None,fault=None):
        if not synthetic:development_partition(partition)
        if not isinstance(binding,StageBinding) or binding.synthetic!=synthetic:
            raise IntegrityError('Independently approved stage binding required')
        self.binding=binding;self.root=binding.authorize(root)
        approved=json.loads(binding.manifest_bytes)
        stores=[binding._within(binding.root,p) for p in approved.get('stores',[])]
        if self.root not in stores:raise IntegrityError('Checkpoint store is not in approved manifest')
        if partition is not None and partition!=approved['partition']:
            raise IntegrityError('Store partition is not approved')
        self.synthetic=synthetic;self.partition=approved['partition'];self.backend=backend
        actual=binding.verify()
        if run_lock is not None and run_lock!=actual:raise IntegrityError('Caller run lock conflicts with checked files')
        self._lock_bytes=canonical_bytes(actual);self.run_id=digest(actual);self.active=False;self._lease_fd=None
        if fault is not None and not synthetic:raise IntegrityError('Crash injection is synthetic-only')
        self.fault=fault or (lambda boundary,path:None)

    @property
    def lock(self):return json.loads(self._lock_bytes)

    def _paths(self):
        self.binding.authorize(self.root)
        for name in ('.writer.lock','staging','records','recovered','run.json','pending.json'):
            checked_path(self.root/name)

    def _check_lock(self):
        self._paths()
        if canonical_bytes(self.binding.verify())!=self._lock_bytes:
            raise IntegrityError('Source/config/dependencies/reference commitments changed')
        if self.binding.read(self.root/'run.json')!=self._lock_bytes:
            raise IntegrityError('Missing, stale or mixed-run lock')

    def _require_lease(self):
        if not self.active or self._lease_fd is None:raise IntegrityError('Exclusive writer lease required')
        self._check_lock()

    def _publish(self,path,data):
        self._paths();self.binding.authorize(path)
        temporary=self.root/'staging'/(path.name+'.'+uuid.uuid4().hex+'.part')
        with temporary.open('xb') as stream:
            self.fault('after_stage_create',path)
            stream.write(data);stream.flush();os.fsync(stream.fileno())
        sync_directory(temporary.parent)
        self.fault('after_stage_fsync',path)
        try:os.link(temporary,path)
        except FileExistsError as error:raise IntegrityError('Duplicate/conflicting publication; evidence preserved') from error
        self.fault('after_link',path)
        sync_directory(path.parent);self.fault('after_destination_fsync',path)
        temporary.unlink();self.fault('after_stage_unlink',path)
        sync_directory(temporary.parent);self.fault('after_stage_dir_fsync',path)

    def _retain_recovered(self,path):
        destination=self.root/'recovered'/path.name
        if destination.exists():raise IntegrityError('Recovery evidence name conflict')
        os.rename(path,destination)
        sync_directory(destination.parent);sync_directory(path.parent)

    def _initial_lock(self):
        path=self.root/'run.json'
        allowed={'.writer.lock','staging','records','recovered','run.json','pending.json'}
        if any(p.name not in allowed for p in self.root.iterdir()):
            raise IntegrityError('Unrecognized preexisting store evidence')
        stages=list((self.root/'staging').glob('*.part'))
        lock_stages=[p for p in stages if p.name.startswith('run.json.')]
        if path.exists():
            self._check_lock()
        elif (list((self.root/'records').iterdir()) or list((self.root/'recovered').iterdir())
              or (self.root/'pending.json').exists()):
            raise IntegrityError('Nonempty store lacks original run lock')
        elif stages:
            if len(stages)!=1 or len(lock_stages)!=1:
                raise IntegrityError('Ambiguous initial lock evidence preserved')
            staged=lock_stages[0]
            if self.binding.read(staged)!=self._lock_bytes:
                raise IntegrityError('Torn/conflicting initial lock preserved')
            os.link(staged,path);sync_directory(self.root)
        else:self._publish(path,self._lock_bytes)
        for staged in lock_stages:
            if (self.binding.read(staged)!=self._lock_bytes or not os.path.samefile(staged,path)):
                raise IntegrityError('Conflicting initial lock duplicate preserved')
            self._retain_recovered(staged)
        self._check_lock()

    @contextmanager
    def writer(self):
        self._paths();self.root.mkdir(parents=True,exist_ok=True)
        sync_directory(self.root.parent)
        fd=os.open(self.root/'.writer.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'a+b') as lease:
            try:fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError as error:raise IntegrityError('Concurrent B-prime writer') from error
            try:
                for name in ('staging','records','recovered'):(self.root/name).mkdir(exist_ok=True)
                sync_directory(self.root)
                self._initial_lock();self.active=True;self._lease_fd=lease.fileno()
                yield self
            finally:self.active=False;self._lease_fd=None;fcntl.flock(lease,fcntl.LOCK_UN)

    def _name(self,identity):
        if not isinstance(identity,str) or not identity:raise IntegrityError('Missing checkpoint identity')
        if self.synthetic:
            if not identity.startswith('synthetic:'):raise IntegrityError('Synthetic identity required')
        else:
            from .phase15_bprime import Identity
            fields=identity.split(':')
            if len(fields)!=4 or fields[0]!=VERSION:raise IntegrityError('Unknown production identity')
            actual=Identity(fields[1],fields[2],int(fields[3]))
            if actual.partition!=self.partition or actual.root!=identity:raise IntegrityError('Stage conflict')
        return hashlib.sha256(identity.encode()).hexdigest()+'.json.gz'

    def _validate(self,body,identity):
        self._name(identity)
        if (body.get('run_id')!=self.run_id or body.get('identity')!=identity
            or body.get('payload_sha256')!=digest(body.get('payload'))):
            raise IntegrityError('Checkpoint body/run/hash conflict')
        payload=body['payload']
        checkpoint_payload(payload,synthetic=self.synthetic,backend=self.backend)
        if payload.get('kind')=='candidate' and payload['identity']!=identity:
            raise IntegrityError('Candidate/checkpoint identity conflict')
        return payload

    def write(self,identity,payload):
        self._require_lease();name=self._name(identity)
        if list((self.root/'staging').glob('*.part')):raise IntegrityError('Unresolved staged evidence')
        body=dict(identity=identity,run_id=self.run_id,payload=payload,payload_sha256=digest(payload))
        self._validate(body,identity)
        data=gzip.compress(canonical_bytes(body),mtime=0)
        self._check_lock();self._publish(self.root/'records'/name,data);self._check_lock()
        return self._entry(identity,data)

    def _entry(self,identity,data):
        return dict(identity=identity,path='records/'+self._name(identity),bytes=len(data),
                    sha256=hashlib.sha256(data).hexdigest())

    def scan(self):
        self._check_lock();result=[]
        for path in sorted((self.root/'records').iterdir()):
            if not path.name.endswith('.json.gz'):raise IntegrityError('Unexpected checkpoint path')
            try:
                data=self.binding.read(path);body=json.loads(gzip.decompress(data));identity=body['identity']
            except (OSError,EOFError,ValueError,KeyError,UnicodeError) as error:
                raise IntegrityError('Malformed checkpoint bytes preserved') from error
            if path.name!=self._name(identity):raise IntegrityError('Unexpected checkpoint filename')
            self._validate(body,identity);result.append((self._entry(identity,data),body['payload']))
        self._check_lock();return result

    def inventory(self,entries,expected_identities,*,require_complete=True):
        self._check_lock();expected=set(expected_identities);seen=set()
        if len(expected)!=len(expected_identities):raise IntegrityError('Duplicate expected identity')
        actual={entry['identity']:entry for entry,_ in self.scan()}
        for entry in entries:
            identity=entry['identity']
            if identity in seen or identity not in expected or actual.get(identity)!=entry:
                raise IntegrityError('Missing/duplicate/conflicting checkpoint commitment')
            seen.add(identity)
        if set(actual)!=seen:raise IntegrityError('Unexpected or missing checkpoint file')
        if list((self.root/'staging').glob('*.part')):raise IntegrityError('Unresolved staged evidence')
        if require_complete and seen!=expected:raise IntegrityError('Missing expected checkpoints')
        self._check_lock();return expected-seen

    def recover(self,expected_identities):
        self._require_lease();expected=set(expected_identities);recovered=[]
        for path in sorted((self.root/'staging').glob('*.part')):
            try:
                packed=self.binding.read(path);body=json.loads(gzip.decompress(packed));identity=body['identity']
                if identity not in expected:raise IntegrityError('Unexpected staged identity')
                self._validate(body,identity)
            except (OSError,EOFError,ValueError,KeyError,UnicodeError) as error:
                raise IntegrityError('Torn/invalid staged evidence preserved') from error
            destination=self.root/'records'/self._name(identity)
            if destination.exists():
                if (not os.path.samefile(path,destination) or self.binding.read(destination)!=packed):
                    raise IntegrityError('Conflicting duplicate preserved')
            else:os.link(path,destination);sync_directory(destination.parent)
            self._check_lock();self._retain_recovered(path)
            recovered.append(self._entry(identity,packed))
        return recovered
