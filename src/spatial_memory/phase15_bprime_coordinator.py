"""Fail-closed audit integration, executable only with explicit synthetic builders.

No command line entry point and no production capability is issued. Production
population generation stays disabled pending separate approval and preflight.
"""
import hashlib
import json
import os
from pathlib import Path
from . import phase15_bprime as bp
from .phase15_bprime_protocol import AdmissionIndex, canonical_bytes, digest
from .phase15_bprime_records import validate_candidate, TERMINAL, GEOMETRY_REJECTIONS
from .phase15_bprime_store import Checkpoints, sync_directory

PRODUCTION_GENERATION_ENABLED = False


def visual_selection(identities):
    if len(set(identities))!=len(identities) or any(not isinstance(i,str) or not i for i in identities):
        raise bp.IntegrityError('Unique complete representative identities required')
    def key(identity):
        fields=(bp.VERSION,'visual-audit',identity)
        raw=b''.join(len(f.encode()).to_bytes(4,'little')+f.encode() for f in fields)
        return hashlib.sha256(raw).digest(),identity
    return sorted(identities,key=key)[:(len(identities)+4)//5]


class Coordinator:
    def __init__(self,store,references,*,backend,synthetic=False,previous=(),prefix=None):
        # No environment variable, manifest flag or caller argument enables production.
        if not synthetic and not PRODUCTION_GENERATION_ENABLED:
            from .phase15_bprime_access import production_manifests
            if not production_manifests():
                raise bp.IntegrityError('Production population generation disabled pending separate approval')
            from .phase15_macos_monitored import MonitoredBackend
            if not isinstance(backend,MonitoredBackend):
                raise bp.IntegrityError('Production population generation disabled for unpinned backend; Option B backend required')
        if (not isinstance(store,Checkpoints) or store.synthetic!=synthetic
            or references.synthetic!=synthetic):
            raise bp.IntegrityError('Coordinator/store/reference profile conflict')
        self.synthetic=synthetic
        if not synthetic and not isinstance(backend,bp.Backend):
            raise bp.IntegrityError('Production requires the approved guarded C3 backend')
        if json.loads(store.binding.manifest_bytes).get('reference_inventory_sha256')!=references.sha256:
            raise bp.IntegrityError('Reference inventory is not the independently committed inventory')
        store.binding.verify()
        self.store=store;self.references=references;self.backend=backend
        self.prefix=prefix
        declared_prefix=json.loads(store.binding.manifest_bytes).get('continuation_prefix')
        if prefix is not None:
            from .phase15_bprime_prefix import ReadOnlyPrefix
            from .phase15_bprime_epochs import ReadOnlyEpochPrefix
            if (not isinstance(prefix,(ReadOnlyPrefix,ReadOnlyEpochPrefix)) or prefix.synthetic!=synthetic
                or prefix.partition!=store.partition or not declared_prefix
                or declared_prefix['sha256']!=prefix.sha256 or prefix.binding!=store.binding):
                raise bp.IntegrityError('Unverified or mismatched continuation prefix')
        elif declared_prefix:
            raise bp.IntegrityError('Declared continuation requires its verified original prefix')
        self.stage=store.partition;self.previous=tuple(previous)
        if any(not isinstance(p,Coordinator) or p.synthetic!=synthetic for p in self.previous):
            raise bp.IntegrityError('Prior seals require verified coordinator evidence')
        expected=list(bp.PARTITIONS)[:list(bp.PARTITIONS).index(self.stage)]
        if [p.stage for p in self.previous]!=expected:
            raise bp.IntegrityError('All preceding partitions must be complete and separately bound')
        commitments=json.loads(store.binding.manifest_bytes).get('prior_partitions',{})
        if commitments!={p.stage:digest(p.completion()) for p in self.previous}:
            raise bp.IntegrityError('Prior partition seals are not independently approved')
        self._reset()
        self._restored=False
        self._publications={}

    def _reset(self):
        self.index=AdmissionIndex(synthetic=self.synthetic);self.references.load(self.index)
        from dataclasses import replace
        for previous in self.previous:
            previous.completion()
            for _,payload in previous._scan():
                evidence=validate_candidate(payload,synthetic=self.synthetic,backend=self.backend)
                if evidence.record is not None:
                    self.index.prior_roots |= evidence.record.lineage.roots
                if evidence.record is not None and payload['outcome'] in ('independent','same_partition_related'):
                    self.index.add_reference(replace(evidence.record,partition='reference',category='admitted_development'))
            self.index.frozen.add(('synthetic-' if self.synthetic else '')+previous.stage)
        self.part=self.stage;self.position=0;self.cursors={};self.sequence=0;self.stopped=False

    def _stage_key(self):
        return 'synthetic-'+self.part if self.synthetic else self.part

    def _profile(self):
        return 'synthetic' if self.synthetic else 'production'

    def _job(self):
        if self.stopped:raise bp.IntegrityError('Terminal stop; no retry or substitution')
        while True:
            counts=self.index.credits(self._stage_key());target=bp.PARTITIONS[self.part][1]
            if all(counts[m]>=target for m in bp.MECHANISMS):
                # Synthetic sealing is explicitly separate from production seals.
                if self.synthetic:self.index.frozen.add(self._stage_key())
                else:self.index.freeze(self.part)
                return None  # Next stage requires its own approved binding/seals.
            m=bp.MECHANISMS[self.position%4];self.position+=1
            if counts[m]>=target:continue
            key=(self.part,m);n=self.cursors.get(key,0)
            if n>=10000:
                self.stopped=True;raise bp.IntegrityError('Frozen candidate allowance exhausted')
            self.cursors[key]=n+1
            identity=(f'synthetic:{self.part}:{m}:{n}' if self.synthetic else
                      bp.Identity(self.part,m,bp.seed_for(self.part,m,n)).root)
            return dict(identity=identity,partition=self.part,
                        mechanism=m,index=n,sequence=self.sequence)

    def _apply(self,payload,expected):
        if any(payload[k]!=v for k,v in expected.items()):raise bp.IntegrityError('Fixed order/identity conflict')
        evidence=validate_candidate(payload,synthetic=self.synthetic,backend=self.backend)
        if payload['outcome'] in TERMINAL:self.stopped=True
        elif evidence.record is not None:
            if payload['outcome']=='no_start_goal_pair':pass
            else:
                reason,_=self.index.classify(evidence.record)
                if reason!=payload['outcome']:raise bp.IntegrityError('Saved admission differs from independent reconstruction')
                self.index.admit(evidence.record,evidence=evidence)
        self.sequence+=1

    def _pending(self):return self.store.root/'pending.json'

    def _scan(self):
        return ([] if self.prefix is None else self.prefix.scan())+self.store.scan()

    def _clear_pending(self):
        path=self._pending()
        if path.exists():
            # Preserve durable attempt evidence, including committed aliases.
            destination=self.store.root/'recovered'/f'attempt-{self.sequence}.json'
            if destination.exists():raise bp.IntegrityError('Attempt recovery evidence conflict')
            os.rename(path,destination);sync_directory(destination.parent);sync_directory(path.parent)

    def restore(self):
        """Rebuild all state from validated records, never execute a saved job."""
        self.store._require_lease();self._reset()
        rows=self._scan();rows.sort(key=lambda r:r[1]['sequence'])
        for _,payload in rows:
            expected=self._job()
            if expected is None:raise bp.IntegrityError('Extra record after completed quotas')
            self._apply(payload,expected)
        # Durable receipts survive deletion of a checkpoint: never silently
        # replay a previously completed attempt just because its file is missing.
        by_identity={p['identity']:p for e,p in rows if not e.get('prefix')}
        for receipt in (self.store.root/'recovered').glob('attempt-*.json'):
            value=json.loads(self.store.binding.read(receipt))
            if value.get('run_id')!=self.store.run_id or not isinstance(value.get('job'),dict):
                raise bp.IntegrityError('Malformed or stale attempt receipt')
            job=value['job'];saved=by_identity.get(job.get('identity'))
            fields=('identity','partition','mechanism','index','sequence')
            if (saved is None or set(job)!=set(fields) or job!={k:saved[k] for k in fields}
                or receipt.name!=f"attempt-{saved['sequence']+1}.json"):
                raise bp.IntegrityError('Missing/conflicting completed checkpoint; no retry')
        pending_path=self._pending()
        if pending_path.exists():
            try:pending=json.loads(self.store.binding.read(pending_path))
            except (ValueError,UnicodeError) as error:
                raise bp.IntegrityError('Torn pending attempt preserved') from error
            if (set(pending)!={'run_id','job'} or not isinstance(pending['job'],dict)
                or set(pending['job'])!={'identity','partition','mechanism','index','sequence'}):
                raise bp.IntegrityError('Incomplete pending attempt preserved')
            if pending.get('run_id')!=self.store.run_id:raise bp.IntegrityError('Stale pending attempt')
            committed=[payload for e,payload in rows if not e.get('prefix') and payload['identity']==pending['job']['identity']]
            if committed:
                if any(committed[0][k]!=v for k,v in pending['job'].items()):raise bp.IntegrityError('Attempt/checkpoint conflict')
                self._clear_pending()
            else:
                # Only a fully staged, validated record may be recovered. No builder
                # is called to retry an interrupted, uncheckpointed candidate.
                expected=self._job()
                if pending['job']!=expected:raise bp.IntegrityError('Pending order conflict')
                recovered=self.store.recover([expected['identity']])
                if len(recovered)!=1:raise bp.IntegrityError('Uncheckpointed attempt preserved; review required')
                # Recovery can add a publication absent from the initial scan.
                # Return and cache that verified post-recovery inventory without
                # applying the recovered decision a second time.
                rows=self._scan();rows.sort(key=lambda r:r[1]['sequence'])
                payload=next(p for e,p in rows if e['identity']==expected['identity'])
                self._apply(payload,expected);self._clear_pending()
        elif list((self.store.root/'staging').glob('*.part')):
            # A staged alias of already committed output can be verified without
            # another candidate invocation. An unknown staged identity stops.
            self.store.recover([e['identity'] for e,_ in rows if not e.get('prefix')])
        if list((self.store.root/'staging').glob('*.part')):
            self.store.recover([e['identity'] for e,_ in self.store.scan()])
        self.store._check_lock()
        self._publications={e['path']:e['sha256'] for e,_ in rows if not e.get('prefix')}
        self._restored=True
        return rows

    def execute_one(self,builder):
        """Run a supplied builder under the profile gate; production stays disabled."""
        self.store._require_lease()
        if not self._restored:self.restore()
        if self.prefix is not None:self.prefix.check_integrity()
        # Recheck durable bytes without recanonicalizing every previous graph on
        # every decision. A fresh process still reconstructs the complete index.
        files=list((self.store.root/'records').iterdir())
        if {str(p.relative_to(self.store.root)) for p in files}!=set(self._publications):
            raise bp.IntegrityError('Missing/conflicting completed publication; no retry')
        for relative,expected in self._publications.items():
            if hashlib.sha256(self.store.binding.read(self.store.root/relative)).hexdigest()!=expected:
                raise bp.IntegrityError('Completed publication changed; no retry')
        job=self._job()
        if job is None:return None
        pending=dict(run_id=self.store.run_id,job=job)
        if self._pending().exists():raise bp.IntegrityError('Unresolved previous attempt')
        # Exclusive durable intent before any synthetic construction. A crash
        # without complete output requires review, never automatic reexecution.
        fd=os.open(self._pending(),os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'wb') as handle:
            handle.write(canonical_bytes(pending));handle.flush();os.fsync(handle.fileno())
        sync_directory(self.store.root)
        phase='geometry';partial=None
        try:
            partial=builder.geometry(dict(job))
            payload=dict(partial,**job,kind='candidate',version=bp.VERSION,profile=self._profile(),
                         outcome='same_partition_related',reasons=['same_partition_related'],world=None)
            phase='canonicalization'
            provisional=validate_candidate(payload,synthetic=self.synthetic,backend=self.backend)
            reason,_=self.index.classify(provisional.record)
            payload.update(outcome=reason,reasons=[reason])
            if reason=='independent':
                phase='pair';payload=builder.complete(payload)
            if any(payload[k]!=v for k,v in job.items()):
                raise bp.IntegrityError('Builder changed fixed candidate identity/order')
            evidence=validate_candidate(payload,synthetic=self.synthetic,backend=self.backend)
        except bp.legacy.Rejected as error:
            reason=str(error)
            if phase=='geometry' and reason in GEOMETRY_REJECTIONS and job['mechanism']!='BP':
                payload=dict(job,kind='candidate',version=bp.VERSION,profile=self._profile(),
                             outcome=reason,reasons=[reason],phase=phase,
                             rejection_evidence=builder.rejection_evidence(),streams=builder.stream_counters())
            elif phase=='pair' and reason=='no_start_goal_pair':
                payload.update(outcome=reason,reasons=[reason],world=None)
                payload['streams'].update(builder.stream_counters())
            else:payload=self._failure(job,phase,'implementation_error',error,partial)
        except bp.legacy.DynamicLimit as error:
            payload=self._failure(job,'dynamics','DynamicLimit',error,partial)
        except bp.topology.CanonicalizationLimit as error:
            payload=self._failure(job,'canonicalization','BackendFailure',error,partial)
        except Exception as error:
            payload=self._failure(job,phase,'implementation_error',error,partial)
        # Validation/publication errors leave durable pending evidence; the next
        # restore stops without calling the builder again.
        validate_candidate(payload,synthetic=self.synthetic,backend=self.backend)
        entry=self.store.write(job['identity'],payload)
        self._publications[entry['path']]=entry['sha256']
        self._apply(payload,job);self._clear_pending()
        return entry

    def completion(self):
        self.store._check_lock()
        rows=self._scan()
        # Rebuild state to prevent caller mutation of in-memory credits.
        self._reset()
        for _,payload in sorted(rows,key=lambda r:r[1]['sequence']):
            self._apply(payload,self._job())
        counts=self.index.credits(self._stage_key())
        if self.stopped or any(counts[m]!=bp.PARTITIONS[self.part][1] for m in bp.MECHANISMS):
            raise bp.IntegrityError('Partition quota is not complete')
        if self._pending().exists() or list((self.store.root/'staging').glob('*.part')):
            raise bp.IntegrityError('Unresolved evidence cannot be sealed')
        representatives=[self.index.records[min(i for i in members if i in self.index.complete)].identity
                         for members in self.index.components(self._stage_key())
                         if any(i in self.index.complete for i in members)]
        return dict(version=bp.VERSION,partition=self.part,run_id=self.store.run_id,
                    visual_representatives=visual_selection(representatives),
                    records_sha256=digest([e for e,_ in sorted(rows,key=lambda r:r[1]['sequence'])]),
                    recovery_evidence_sha256=digest([(p.name,hashlib.sha256(self.store.binding.read(p)).hexdigest())
                        for p in sorted((self.store.root/'recovered').iterdir())]),
                    counts=dict(counts))

    def visual_representatives(self):
        return self.completion()['visual_representatives']

    def _failure(self,job,phase,outcome,error,partial):
        return dict(job,kind='candidate',version=bp.VERSION,profile=self._profile(),
                    outcome=outcome,reasons=[outcome],phase=phase,error=repr(error),
                    partial_evidence=partial)
