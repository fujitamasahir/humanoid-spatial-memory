"""Read-only, committed prior execution prefix for a separately locked continuation.

Never opens the original writer, changes its lock, or constructs a world. The
old source commitment is checked against its immutable Git snapshot, not
misrepresented as the current fixed implementation. New writes use a new store.
"""
from dataclasses import dataclass
import gzip,hashlib,json,subprocess
from .phase15_bprime import IntegrityError,development_partition
from .phase15_bprime_access import GROUPS,StageBinding
from .phase15_bprime_protocol import canonical_bytes,digest
from .phase15_bprime_records import checkpoint_payload

_TOKEN=object()

def require(value,message):
    if not value:raise IntegrityError(message)

@dataclass(frozen=True)
class ReadOnlyPrefix:
    binding: StageBinding
    specification: bytes
    synthetic: bool
    backend: object
    _token: object=None
    _seal: tuple=()

    @classmethod
    def load(cls,binding,*,backend):
        require(isinstance(binding,StageBinding),'Approved continuation binding required')
        binding.verify();manifest=json.loads(binding.manifest_bytes)
        descriptor=manifest.get('continuation_prefix');require(isinstance(descriptor,dict),'Missing prefix commitment')
        raw=binding.read(binding._within(binding.root,descriptor['path']))
        require(hashlib.sha256(raw).hexdigest()==descriptor['sha256'],'Changed prefix manifest')
        value=json.loads(raw);development_partition(value['partition'])
        require(value['schema']==1 and value['partition']==manifest['partition'],'Prefix stage/schema conflict')
        require(value['root']==manifest.get('readonly_prefix_root'),'Unapproved prefix root')
        require(value['root'] not in manifest.get('stores',[]),'Original prefix must not be a writable store')
        original_root=binding._within(binding.root,value['root'])
        for relative in manifest.get('stores',[]):
            writable=binding._within(binding.root,relative)
            require(not writable.is_relative_to(original_root) and not original_root.is_relative_to(writable),'Overlapping prefix/writable roots')
        original_raw=binding.read(binding._within(binding.root,value['original_binding']))
        require(hashlib.sha256(original_raw).hexdigest()==value['original_binding_sha256'],'Original binding changed')
        old=json.loads(original_raw)
        require(old['root']==str(binding.root) and old['partition']==value['partition'] and old['profile']==manifest['profile'],'Original binding profile/root/stage conflict')
        if not binding.synthetic:
            commit=value['source_commit']
            require(isinstance(commit,str) and len(commit)==40 and all(c in '0123456789abcdef' for c in commit),'Missing original source commit')
            result=subprocess.run(['git','merge-base','--is-ancestor',commit,'HEAD'],cwd=binding.root,capture_output=True)
            require(result.returncode==0,'Original source is not in committed ancestry')
        for group in GROUPS:
            for relative,expected in old['files'][group].items():
                path=binding._within(binding.root,relative)
                if group=='source' and not binding.synthetic:
                    result=subprocess.run(['git','show',value['source_commit']+':'+relative],cwd=binding.root,capture_output=True)
                    require(result.returncode==0,'Missing original committed source')
                    data=result.stdout
                else:data=binding.read(path)
                require(hashlib.sha256(data).hexdigest()==expected,'Original '+group+' commitment changed')
        expected=dict(version=old['version'],profile=old['profile'],binding_sha256=value['original_binding_sha256'])
        expected.update({g+'_sha256':digest(old['files'][g]) for g in GROUPS})
        root=binding._within(binding.root,value['root']);lock=binding.read(root/'run.json')
        require(lock==canonical_bytes(expected) and hashlib.sha256(lock).hexdigest()==value['run_id'],'Original run lock changed')
        prefix=cls(binding,raw,binding.synthetic,backend,_TOKEN,(binding,raw,binding.synthetic,backend))
        prefix.scan()
        return prefix

    @property
    def partition(self):return json.loads(self.specification)['partition']

    @property
    def sha256(self):return hashlib.sha256(self.specification).hexdigest()

    def check_integrity(self):
        """Check every original file before another publication, without replay."""
        require(self._token is _TOKEN and self._seal==(self.binding,self.specification,self.synthetic,self.backend),'Unverified prefix object')
        value=json.loads(self.specification);root=self.binding._within(self.binding.root,value['root'])
        descriptor=json.loads(self.binding.manifest_bytes)['continuation_prefix']
        require(self.binding.read(self.binding._within(self.binding.root,descriptor['path']))==self.specification,'Prefix commitment changed')
        require({p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}=={e['path'] for e in value['files']},'Missing/unexpected prefix evidence')
        for e in value['files']:
            raw=self.binding.read(self.binding._within(root,e['path']))
            require(len(raw)==e['bytes'] and hashlib.sha256(raw).hexdigest()==e['sha256'],'Changed original prefix bytes')

    def scan(self):
        require(self._token is _TOKEN and self._seal==(self.binding,self.specification,self.synthetic,self.backend),'Unverified prefix object')
        self.binding.verify();value=json.loads(self.specification)
        descriptor=json.loads(self.binding.manifest_bytes)['continuation_prefix']
        require(self.binding.read(self.binding._within(self.binding.root,descriptor['path']))==self.specification,'Prefix commitment changed')
        root=self.binding._within(self.binding.root,value['root']);files=value['files']
        require(len({e['path'] for e in files})==len(files),'Duplicate prefix file')
        actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
        require(actual=={e['path'] for e in files},'Missing/unexpected prefix evidence')
        require(not (root/'pending.json').exists() and not list((root/'staging').iterdir()),'Unresolved original attempt')
        rows=[];receipts=[]
        for e in files:
            path=self.binding._within(root,e['path']);raw=self.binding.read(path)
            require(len(raw)==e['bytes'] and hashlib.sha256(raw).hexdigest()==e['sha256'],'Changed original prefix bytes')
            if e['path'].startswith('records/'):
                body=json.loads(gzip.decompress(raw));payload=body['payload'];identity=payload['identity']
                require(body['identity']==identity and body['run_id']==value['run_id'] and body['payload_sha256']==digest(payload),'Original checkpoint body/run conflict')
                require(path.name==hashlib.sha256(identity.encode()).hexdigest()+'.json.gz','Original checkpoint name conflict')
                checkpoint_payload(payload,synthetic=self.synthetic,backend=self.backend)
                require(payload['partition']==value['partition'],'Original candidate stage conflict')
                rows.append((dict(identity=identity,path=e['path'],bytes=e['bytes'],sha256=e['sha256'],prefix=True,source_run_id=value['run_id']),payload))
            elif e['path'].startswith('recovered/attempt-'):receipts.append((path.name,json.loads(raw)))
        rows.sort(key=lambda r:r[1]['sequence'])
        require(len(rows)==value['records'] and len({p['identity'] for _,p in rows})==len(rows),'Original identity/count conflict')
        require([p['sequence'] for _,p in rows]==list(range(len(rows))),'Original sequence gap/duplicate')
        byid={p['identity']:p for _,p in rows}
        require(len(receipts)==len(rows),'Original receipt count conflict')
        for name,r in receipts:
            require(r['job']['identity'] in byid,'Orphaned original receipt')
            payload=byid[r['job']['identity']]
            require(r['run_id']==value['run_id'] and r['job']=={k:payload[k] for k in ('identity','partition','mechanism','index','sequence')} and name==f"attempt-{payload['sequence']+1}.json",'Original receipt conflict')
        return rows
