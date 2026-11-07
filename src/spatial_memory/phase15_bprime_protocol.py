"""Lineage, reference validation and admission primitives; no population runner."""
from collections import Counter
from dataclasses import dataclass
import gzip
import hashlib
import json
from pathlib import Path
from . import phase15_topology as top
from .phase15_bprime import (VERSION, PARTITIONS, MECHANISMS, CANONICAL_NAMESPACE,
                            IntegrityError, development_partition, seed_for)

CATEGORIES = ('original_history', 'admitted_development', 'rejected_valid')
OUTCOMES = {'original_history': ('historical',),
            'admitted_development': ('independent','same_partition_related'),
            'rejected_valid': ('cross_partition_or_historical',)}


def canonical_bytes(value):
    try:
        return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    except (ValueError,TypeError) as error:
        raise IntegrityError('Nonfinite or unserializable checkpoint/inventory value') from error


def digest(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def development_path(path, partition, root):
    """Reject stage and escape paths before any file is opened."""
    development_partition(partition)
    root = Path(root).resolve()
    path = Path(path).resolve()
    if not path.is_relative_to(root):
        raise IntegrityError('Path escapes development root')
    relative = path.relative_to(root)
    if any(any(word in p.lower() for word in ('assessment','held_out','held-out','heldout','final'))
           for p in relative.parts):
        raise IntegrityError('Reserved path denied before opening')
    return path


@dataclass(frozen=True)
class Lineage:
    roots: frozenset

    def __post_init__(self):
        if isinstance(self.roots,(str,bytes)):
            raise IntegrityError('Ancestry must be a set of complete root identities')
        object.__setattr__(self,'roots',frozenset(self.roots))
        if not self.roots or any(not isinstance(r,str) or not r for r in self.roots):
            raise IntegrityError('Actual ancestor roots required')

    @classmethod
    def fresh(cls, identity):
        return cls(frozenset((identity.root,)))

    @classmethod
    def derived(cls, *parents):
        if not parents or any(not isinstance(p,cls) for p in parents):
            raise IntegrityError('Derivative requires actual parent lineages')
        return cls(frozenset().union(*(p.roots for p in parents)))


@dataclass(frozen=True)
class Record:
    identity: str
    partition: str
    mechanism: str
    exact: tuple
    keys: frozenset
    raster: tuple
    lineage: Lineage
    category: str = ''

    def __post_init__(self):
        if not isinstance(self.raster,tuple) or any(not isinstance(v,(str,int)) for v in self.raster):
            raise IntegrityError('Immutable canonical raster tuple required')
        object.__setattr__(self,'exact',tuple(self.exact))
        object.__setattr__(self,'keys',frozenset(map(tuple,self.keys)))
        for key in self.keys:
            if (len(key)<2 or not isinstance(key[0],str) or type(key[1]) is not int
                or key[1]<0 or len(key)!=2+key[1]+key[1]*(key[1]-1)//2
                or any(type(v) is not int or v<0 for v in key[2:])):
                raise IntegrityError('Malformed full canonical key')
        if not self.identity or self.exact not in self.keys:
            raise IntegrityError('Missing identity or self key')
        if not isinstance(self.lineage,Lineage):
            raise IntegrityError('Frozen ancestry required')


class AdmissionIndex:
    """Same relation as approved index, extended to sets of genuine ancestors."""
    def __init__(self, *, synthetic=False):
        self.synthetic = synthetic
        self.records = []
        self.parent = []
        self.complete = set()
        self.frozen = set()
        self.prior_roots = frozenset()

    def _partition(self, partition):
        if self.synthetic:
            if not partition.startswith('synthetic-'):
                raise IntegrityError('Synthetic index requires synthetic partition labels')
        else:
            development_partition(partition)
            previous = list(PARTITIONS)[:list(PARTITIONS).index(partition)]
            if any(p not in self.frozen for p in previous):
                raise IntegrityError('Earlier development partition is not frozen')

    def root(self, i):
        while self.parent[i]!=i:
            i = self.parent[i]
        return i

    def matches(self, record):
        return [i for i,r in enumerate(self.records) if
                r.keys & record.keys or r.raster==record.raster
                or r.lineage.roots & record.lineage.roots]

    def _insert(self, record, found, complete):
        if any(r.identity==record.identity for r in self.records):
            raise IntegrityError('Duplicate record identity')
        i = len(self.records)
        roots = {self.root(j) for j in found}
        self.records.append(record)
        self.parent.append(i)
        for r in roots:
            self.parent[r] = i
        if complete:
            self.complete.add(i)
        return dict(record_index=i, matches=found, merged_components=len(roots),
                    exact_matches=[j for j in found if self.records[j].exact==record.exact])

    def _keys(self, record):
        namespace = 'synthetic-exact-oracle' if self.synthetic else CANONICAL_NAMESPACE
        if any(k[0]!=namespace for k in record.keys):
            raise IntegrityError('Synthetic/production canonical key profile conflict')

    def add_reference(self, record):
        self._keys(record)
        if record.partition!='reference' or record.category not in CATEGORIES[:2]:
            raise IntegrityError('Rejected valid records are not references')
        return self._insert(record,self.matches(record),False)

    def classify(self, record):
        self._partition(record.partition)
        self._keys(record)
        if record.partition in self.frozen:
            raise IntegrityError('Partition already frozen')
        if record.category or record.mechanism not in MECHANISMS:
            raise IntegrityError('Invalid development record')
        if any(r.identity==record.identity for r in self.records):
            raise IntegrityError('Duplicate identity, not a new candidate')
        found = self.matches(record)
        if (any(self.records[i].partition!=record.partition for i in found)
            or record.lineage.roots & self.prior_roots):
            reason = 'cross_partition_or_historical'
        else:
            reason = 'same_partition_related' if found else 'independent'
        return reason,found

    def admit(self, record, *, complete=False):
        reason, found = self.classify(record)
        if reason=='cross_partition_or_historical':
            return dict(reason=reason, inserted=False, matches=found,
                        lineage_exclusions=sorted(record.lineage.roots & self.prior_roots))
        if complete != (reason=='independent'):
            raise IntegrityError('Only unmatched complete worlds may earn new credits')
        result = self._insert(record,found,complete)
        return dict(reason=reason,inserted=True,**result)

    def components(self, partition):
        groups = {}
        for i,r in enumerate(self.records):
            if r.partition==partition:
                groups.setdefault(self.root(i),[]).append(i)
        return list(groups.values())

    def credits(self, partition):
        result = Counter()
        for members in self.components(partition):
            complete = [i for i in members if i in self.complete]
            if complete:
                result[self.records[min(complete)].mechanism] += 1
        return result

    def freeze(self, partition):
        self._partition(partition)
        if self.synthetic:
            raise IntegrityError('Synthetic components cannot seal population partitions')
        target = PARTITIONS[partition][1]
        if any(self.credits(partition)[m]!=target for m in MECHANISMS):
            raise IntegrityError('Cannot freeze incomplete 48/24/24 population')
        self.frozen.add(partition)


class DevelopmentOrder:
    """Deterministic identity accounting only. Does not construct candidates."""
    def __init__(self):
        self.partition = 'fit'
        self.position = 0
        self.cursors = Counter()
        self.pending = None
        self.stopped = False

    def next_identity(self, index):
        if self.stopped:
            raise IntegrityError('Development order stopped; scientific review required')
        if self.pending is not None:
            raise IntegrityError('Previous attempted identity has no checkpoint')
        while True:
            counts = index.credits(self.partition)
            target = PARTITIONS[self.partition][1]
            if all(counts[m]>=target for m in MECHANISMS):
                index.freeze(self.partition)
                parts = list(PARTITIONS)
                if self.partition==parts[-1]:
                    return None
                self.partition = parts[parts.index(self.partition)+1]
                self.position = 0
                continue
            mechanism = MECHANISMS[self.position%4]
            self.position += 1
            if counts[mechanism]>=target:
                continue
            key = (self.partition,mechanism)
            try:
                seed = seed_for(*key,self.cursors[key])  # before draw 10001
            except IntegrityError:
                self.stopped = True
                raise
            self.cursors[key] += 1
            self.pending = (self.partition,mechanism,seed)
            return self.pending

    def checkpointed(self, identity):
        if self.pending is None or self.pending != identity:
            raise IntegrityError('Attempt/checkpoint identity conflict')
        self.pending = None


def validate_inventory(payload, ledger, archive_root, *, expected_digest,
                       expected_ledger_digest, backend, synthetic=False):
    """Read/verify supplied saved geometry only; never regenerate old worlds.

    The caller must obtain both expected hashes from reviewed commitments, not
    compute a replacement from untrusted inputs. No file is written or sealed.
    Synthetic inventories are explicit small fixtures and cannot load into a
    production index. Reference/nonreference ledgers remain separately returned.
    """
    if not synthetic:
        from .phase15_nauty import Backend
        if not isinstance(backend,Backend):
            raise IntegrityError('Production inventory requires approved guarded backend')
    namespace = 'synthetic-exact-oracle' if synthetic else CANONICAL_NAMESPACE
    profile = 'synthetic' if synthetic else 'production'
    if (payload.get('version')!=VERSION or payload.get('schema')!=1
        or payload.get('profile')!=profile or payload.get('namespace')!=namespace
        or digest(payload)!=expected_digest or digest(ledger)!=expected_ledger_digest
        or payload.get('ledger_sha256')!=expected_ledger_digest):
        raise IntegrityError('Unsealed or conflicting reference inventory/ledger')
    rows = payload['entries']
    if len({e['identity'] for e in rows})!=len(rows) or set(ledger)!={e['identity'] for e in rows}:
        raise IntegrityError('Duplicate, missing or unexpected reference identity')
    if rows != sorted(rows,key=lambda e:(e['category'],e['identity'])):
        raise IntegrityError('Inventory must have canonical category/identity ordering')
    if not synthetic and Counter(e['category'] for e in rows)!=Counter(
        original_history=110,admitted_development=2258,rejected_valid=2276):
        raise IntegrityError('Incomplete historical category coverage')
    if not synthetic and Counter(e['outcome'] for e in rows)!=Counter(
        historical=110,independent=44,same_partition_related=2214,cross_partition_or_historical=2276):
        raise IntegrityError('Incomplete historical admission/rejection ledger')
    root = Path(archive_root).resolve()
    included, excluded = [],[]
    aliases = {}
    for e in rows:
        category = e['category']
        evidence = ledger[e['identity']]
        if (category not in CATEGORIES or e['outcome'] not in OUTCOMES[category]
            or e['included'] is not (category!='rejected_valid')
            or any(e[k]!=evidence[k] for k in (
                'outcome','sha256','bytes','roots','aliases','source_commit','source_path','interpretation'))):
            raise IntegrityError('Category, inclusion, provenance or ancestry conflict')
        if (not isinstance(e['source_commit'],str) or len(e['source_commit'])!=40
            or any(c not in '0123456789abcdef' for c in e['source_commit'])
            or not e['source_path'] or not e['interpretation']):
            raise IntegrityError('Missing source commitment or base interpretation')
        path = Path(e['path'])
        if path.is_absolute() or not (root/path).resolve().is_relative_to(root):
            raise IntegrityError('Nonportable or escaping archive path')
        resolved = (root/path).resolve()
        if any(any(w in p.lower() for w in ('assessment','heldout','held_out','held-out','final'))
               for p in (*path.parts,*resolved.relative_to(root).parts)):
            raise IntegrityError('Reserved archive path denied')
        packed = resolved.read_bytes()
        if len(packed)!=e['bytes'] or hashlib.sha256(packed).hexdigest()!=e['sha256']:
            raise IntegrityError('Missing/changed reference payload')
        body = json.loads(gzip.decompress(packed))
        geometry = body['geometry']
        width,height = geometry['width'],geometry['height']
        if (type(width) is not int or type(height) is not int or width<=0 or height<=0
            or (e['width'],e['height'])!=(width,height)):
            raise IntegrityError('Raster dimension conflict')
        free = frozenset(map(tuple,geometry['free']))
        if (len(free)!=len(geometry['free']) or
            any(type(x) is not int or type(y) is not int or not (0<=x<width and 0<=y<height)
                for x,y in free)):
            raise IntegrityError('Malformed raster')
        if not synthetic:
            if category=='original_history':
                from .phase15_generators import canonical_bytes as historical_bytes, row_key
                original = dict(width=width,height=height,free=sorted(free,key=row_key))
                source_identity = hashlib.sha256(historical_bytes(original)).hexdigest()
            else:
                source_identity = f"{geometry['partition']}:{geometry['mechanism']}:{geometry['seed']}"
            if source_identity!=e['identity']:
                raise IntegrityError('Archive geometry identity does not match ledger')
        graph,_ = top.raster_quotient(free)
        exact = backend.exact_certificate(graph)
        keys = backend.near_certificates(graph)
        if (body['matrix']!=list(map(list,graph.matrix)) or e['matrix']!=body['matrix']
            or tuple(e['exact'])!=exact or frozenset(map(tuple,e['near_keys']))!=keys
            or tuple(body['exact'])!=exact or frozenset(map(tuple,body['near_certificates']))!=keys
            or exact not in keys or any(k[0]!=namespace for k in keys)):
            raise IntegrityError('Stored geometry/matrix/key disagreement')
        lineage = Lineage(frozenset(e['roots']))
        if not synthetic and category!='original_history' and geometry.get('lineage') not in lineage.roots:
            raise IntegrityError('Original geometry root was erased from ancestry')
        for alias in (e['identity'],*e['aliases']):
            signature = (e['sha256'],lineage.roots)
            if alias in aliases and aliases[alias]!=signature:
                raise IntegrityError('Conflicting alias/content/ancestry')
            aliases[alias] = signature
        record = Record(e['identity'],'reference',e.get('mechanism','historical'),
                        exact,keys,top.raster_certificate(free,width,height),lineage,category)
        (excluded if category=='rejected_valid' else included).append(record)
    return ValidatedInventory(tuple(included),tuple(excluded),expected_digest,synthetic)


@dataclass(frozen=True)
class ValidatedInventory:
    included: tuple
    rejected_ledger: tuple
    sha256: str
    synthetic: bool

    def load(self, index):
        if index.synthetic!=self.synthetic or index.records:
            raise IntegrityError('Reference profile conflict or nonempty index')
        for record in self.included:
            index.add_reference(record)
        # Preserve known ancestry without promoting rejected topology/raster keys.
        index.prior_roots = frozenset().union(*(r.lineage.roots for r in
                                               self.included+self.rejected_ledger))
