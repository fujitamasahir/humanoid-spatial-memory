"""Read-only reconstruction of a fit prefix spanning distinct run-lock epochs."""
from dataclasses import dataclass
import gzip
import hashlib
import json
import subprocess
from pathlib import Path

from . import phase15_bprime as bp
from .phase15_bprime_access import StageBinding
from .phase15_bprime_protocol import canonical_bytes, digest
from .phase15_bprime_records import checkpoint_payload

_TOKEN = object()


def require(value, message):
    if not value:
        raise bp.IntegrityError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class ReadOnlyEpochPrefix:
    """Immutable candidate history across the original and first continuation."""
    binding: StageBinding
    specification: bytes
    backend: object
    _token: object = None
    _seal: tuple = ()

    @classmethod
    def load(cls, binding, *, backend):
        require(isinstance(binding, StageBinding) and not binding.synthetic,
                'Approved production binding required for epoch prefix')
        binding.verify()
        manifest = json.loads(binding.manifest_bytes)
        descriptor = manifest.get('continuation_prefix')
        require(isinstance(descriptor, dict), 'Missing multi-epoch prefix commitment')
        raw = binding.read(binding._within(binding.root, descriptor['path']))
        require(sha(raw) == descriptor['sha256'], 'Multi-epoch prefix manifest changed')
        spec = json.loads(raw)
        require(spec.get('schema') == 1 and spec.get('partition') == 'fit'
                and spec.get('records') == 418, 'Unexpected multi-epoch prefix schema/count')
        epochs = spec.get('epochs')
        require(isinstance(epochs, list) and [e.get('name') for e in epochs]
                == ['original_fit', 'continuation_1'], 'Prefix epochs/order changed')
        roots = [e['root'] for e in epochs]
        require(roots == manifest.get('readonly_prefix_roots'),
                'Prefix roots are not explicitly approved')
        all_files = spec.get('files')
        require(isinstance(all_files, list) and len(all_files) == 836,
                'Checkpoint/receipt manifest count conflict')
        for epoch, expected_start, expected_count in zip(epochs, (0, 313), (313, 105)):
            require(epoch.get('sequence_start') == expected_start
                    and epoch.get('records') == expected_count,
                    'Epoch sequence boundary conflict')
            binding_path = binding._within(binding.root, epoch['binding_path'])
            previous_raw = binding.read(binding_path)
            require(sha(previous_raw) == epoch['binding_sha256'],
                    'Historical epoch binding changed')
            previous = json.loads(previous_raw)
            require(previous.get('partition') == 'fit' and previous.get('profile') == 'production',
                    'Historical epoch binding profile/stage conflict')
            expected_lock = dict(version=previous['version'], profile=previous['profile'],
                                 binding_sha256=epoch['binding_sha256'])
            expected_lock.update({g + '_sha256': digest(previous['files'][g])
                                  for g in ('source', 'configuration', 'dependencies', 'references')})
            lock_path = binding._within(binding.root, epoch['root']) / 'run.json'
            lock_raw = binding.read(lock_path)
            require(lock_raw == canonical_bytes(expected_lock)
                    and sha(lock_raw) == epoch['run_id'],
                    'Historical run lock/binding commitment conflict')
            if epoch.get('source_commit'):
                commit = epoch['source_commit']
                require(len(commit) == 40 and all(c in '0123456789abcdef' for c in commit),
                        'Invalid historical source commit')
                result = subprocess.run(['git', 'merge-base', '--is-ancestor', commit, 'HEAD'],
                                        cwd=binding.root, capture_output=True)
                require(result.returncode == 0, 'Historical source commit is not in Git ancestry')
                for relative, expected in previous['files']['source'].items():
                    result = subprocess.run(['git', 'show', commit + ':' + relative],
                                            cwd=binding.root, capture_output=True)
                    require(result.returncode == 0 and sha(result.stdout) == expected,
                            'Historical source snapshot commitment conflict')
        prefix = cls(binding, raw, backend, _TOKEN, (binding, raw, backend))
        prefix.check_integrity()
        prefix.scan()
        return prefix

    @property
    def sha256(self):
        return sha(self.specification)

    @property
    def partition(self):
        return json.loads(self.specification)['partition']

    @property
    def synthetic(self):
        return False

    def _check_seal(self):
        require(self._token is _TOKEN and self._seal == (self.binding, self.specification, self.backend),
                'Unverified multi-epoch prefix object')
        require(self.binding.read(self.binding._within(self.binding.root,
                json.loads(self.binding.manifest_bytes)['continuation_prefix']['path']))
                == self.specification, 'Prefix commitment changed')

    def check_integrity(self):
        """Rehash all immutable checkpoint and receipt bytes before continuation."""
        self._check_seal()
        spec = json.loads(self.specification)
        by_epoch = {e['name']: e for e in spec['epochs']}
        listed = {e['name']: {} for e in spec['epochs']}
        for entry in spec['files']:
            name = entry['epoch']
            require(name in listed and entry['path'] not in listed[name],
                    'Duplicate/unknown epoch file commitment')
            listed[name][entry['path']] = entry
        for epoch in spec['epochs']:
            root = self.binding._within(self.binding.root, epoch['root'])
            records_root = root / 'records'
            receipts_root = root / 'recovered'
            require(records_root.is_dir() and receipts_root.is_dir(), 'Missing epoch store directory')
            require(not (root / 'pending.json').exists()
                    and not list((root / 'staging').iterdir()), 'Unresolved epoch attempt')
            actual = {p.relative_to(root).as_posix() for directory in (records_root, receipts_root)
                      for p in directory.iterdir() if p.is_file()}
            require(actual == set(listed[epoch['name']]), 'Missing/unexpected epoch checkpoint or receipt')
            for relative, entry in listed[epoch['name']].items():
                path = self.binding._within(root, relative)
                raw = self.binding.read(path)
                require(len(raw) == entry['bytes'] and sha(raw) == entry['sha256'],
                        'Changed historical checkpoint/receipt bytes')

    def scan(self):
        self._check_seal()
        self.check_integrity()
        spec = json.loads(self.specification)
        epochs = {e['name']: e for e in spec['epochs']}
        files = {e['name']: [] for e in spec['epochs']}
        for entry in spec['files']:
            files[entry['epoch']].append(entry)
        rows = []
        for name in ('original_fit', 'continuation_1'):
            epoch = epochs[name]
            root = self.binding._within(self.binding.root, epoch['root'])
            records = {}
            receipts = []
            for entry in files[name]:
                path = self.binding._within(root, entry['path'])
                packed = self.binding.read(path)
                if entry['path'].startswith('records/'):
                    try:
                        body = json.loads(gzip.decompress(packed))
                        payload = body['payload']
                    except (ValueError, KeyError, EOFError, UnicodeError) as error:
                        raise bp.IntegrityError('Malformed epoch checkpoint') from error
                    identity = payload.get('identity')
                    require(body.get('identity') == identity and body.get('run_id') == epoch['run_id']
                            and body.get('payload_sha256') == digest(payload),
                            'Epoch checkpoint/run/payload hash conflict')
                    require(path.name == hashlib.sha256(identity.encode()).hexdigest() + '.json.gz',
                            'Epoch checkpoint identity filename conflict')
                    checkpoint_payload(payload, synthetic=False, backend=self.backend)
                    require(payload.get('partition') == 'fit', 'Non-fit record in continuation prefix')
                    require(identity not in records, 'Duplicate epoch identity')
                    records[identity] = payload
                    rows.append((dict(identity=identity,
                                      path=name + '/' + entry['path'],
                                      bytes=entry['bytes'], sha256=entry['sha256'],
                                      prefix=True, source_run_id=epoch['run_id']), payload))
                elif entry['path'].startswith('recovered/attempt-'):
                    receipts.append((path.name, json.loads(packed)))
                else:
                    raise bp.IntegrityError('Unexpected epoch prefix path')
            start = epoch['sequence_start']
            expected_sequences = set(range(start, start + epoch['records']))
            require(len(records) == epoch['records']
                    and {p['sequence'] for p in records.values()} == expected_sequences,
                    'Epoch record count/sequence conflict')
            require(len(receipts) == epoch['records'], 'Epoch receipt count conflict')
            for filename, receipt in receipts:
                job = receipt.get('job', {})
                payload = records.get(job.get('identity'))
                require(payload is not None and receipt.get('run_id') == epoch['run_id']
                        and job == {k: payload[k] for k in ('identity', 'partition', 'mechanism', 'index', 'sequence')}
                        and filename == f"attempt-{payload['sequence']+1}.json",
                        'Epoch receipt does not match its checkpoint')
        rows.sort(key=lambda row: row[1]['sequence'])
        require([p['sequence'] for _, p in rows] == list(range(418)),
                'Combined prefix sequence is not exactly 0..417')
        require(len({p['identity'] for _, p in rows}) == 418,
                'Duplicate identity across fit epochs')
        return rows
