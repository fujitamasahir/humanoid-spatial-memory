# Phase 1.5 B′ macOS development validation and critical stop

2026-11-07. **Not ready to continue generation.** A newly added deterministic
crash-recovery continuation test fails. The authorized fit run was stopped at a
clean checkpoint boundary, preserving 313 candidates. This is not quota
exhaustion, a completed population audit, or a successful Phase 1.5 result.

Branch: `feature/phase1-5-bprime-development-macos`.
Execution source: `2dcadbef876195b43bab6d3ef0da84151c498348`.
Original hardening base: `0d6a8dfc310286d674d1a492826d911c58e67667`;
macOS starting point: `f654004930658ca1349fb16c9a1ac8c9f8dd3f15`.

## Prospective platform policy

[Option B amendment](phase1_5_bprime_macos_option_b_amendment.md), identifier
`phase1.5-v0.4-MACOS-RSS-B1`, was committed as
`78598e5619c4117b592c954a9a929e27b730f8bc` before registered generation.
The user explicitly authorized its adoption and continuation through passed gates.
Original frozen documents, Linux pins, Phase 1.4 locks/results and B-02 evidence
remain unchanged.

The adapter uses the existing ARM64 pynauty 2.8.8.1 / nauty 2.8.8 build and the
unchanged graph encoding, options, serialization and near enumeration. Native
artifact SHA-256 is
`a93063d44e265f92c324148153db5d82aba569a04b068bcd31f0b1d980bce3fd`.
The execution resource pin is
`274810b7801aa2f1fe485587b94eedd6ce635f75fb5b07ddf163eca623b4d9f6`.
The original 4,534-graph Linux/macOS compatibility evidence remains unchanged;
this task did not rerun its standalone compatibility suite. Production inventory
validation recomputed stored certificates and near sets and found no mismatch.
The 1,215 synthetic graph fixtures also pass the independent literal-class oracle.

Acceptance uses a five-second parent deadline and a 536,870,912-byte threshold,
nominal 10-ms libproc parent sampling and independent Darwin lifetime peak-RSS
reports. Missing/conflicting evidence fails closed. This is **not a preventive
hard memory cap**; sampling can overshoot or miss spikes. In the fit runner's
75,856 native calls, there were zero backend failures; the greatest reported
worker peak and parent sample were 19,202,048 bytes. Longest call was 0.054717 s;
the greatest observed within-call sample gap was 0.054681 s, so 10 ms is not a
measured maximum-gap guarantee. Synthetic native excess, freed transient excess,
hangs, crashes, partial/malformed replies and missing evidence are rejected.
No new RLIMIT, privileged-API or operating-system investigation was performed.

## Historical certificates and inventory

All 65 missing historical near-key records were completed into **new** artifacts
from verified stored rasters/matrices. Originals were not overwritten. An
independent raster-quotient implementation and retained literal-class enumeration
verified the completed C3 sets. Historical exact keys and previously present near
sets agree. All 19,279 B-02 checkpoints and 4,534 archives were independently
checked; admission order and unions reproduce 38 components, including the B
components containing 1,687 and 529 records. Both original B-0 archives were
checked. The B-02 bulk commitment still covers 23,815 files / 82,399,048 bytes:
`d0c714c8c23e67b53f74d21dfc6c31c08c5638297c1d168c65aa0278d72efbe5`.

The sealed exclusion scope is exactly 110 original historical identities plus
2,258 admitted development identities. The 2,276 rejected-valid identities remain
nonreferences. Original B-0 repetitions are provenance aliases, not extra units.
There are 2,368 distinct coordinate base rasters, 2,337 dihedral raster classes,
and 95 exact C3 topology classes. The earlier report field
`unique_included_geometries` means dihedral-normalized raster classes.

Inventory digest:
`f80f3d8930a3d51520ab52462cff9e9998992e7b774fc8d9e99932e880cbf3cb`.
Ledger digest:
`23a1f913d66871a09729cedbcb312840d76437a7e54ac2934b5692a6851e6913`.
[Independent report](../results/phase15_macos_development/reference_independent_verification.json)
and [seal](../results/phase15_macos_development/reference_seal.json) document
independent algorithmic verification plus agent review under delegated user
authorization; no external human signature is claimed. The read-only review
binding authorized no population store. A separate committed fit binding was
issued only after sealing. Its source snapshot is distinct from the earlier
completed reference-review snapshot; Git preserves both.

## Gates and synthetic results

| Gate | Status | Evidence or limitation |
| --- | --- | --- |
| Prospective resource amendment | PASS | Adopted before generation |
| Native C3 semantics / stored certificates | PASS | Immutable compatibility evidence, synthetic oracle, inventory loader |
| Option B watchdog/resource evidence | PASS | Focused synthetic probes; monitored acceptance only |
| Historical completion and reference seal | PASS | Exact 110 / 2,258 / 2,276 categorization |
| Pre-launch synthetic tests | PASS, limited coverage | 166 passed; continuation after staged recovery was missing |
| Crash-recovery continuation | **FAIL** | New scripted continuation fixture fails |
| Saved-prefix locks and integrity | PASS | 313 checkpoints / 313 receipts, no pending or staged record |
| Fit population completion | INCOMPLETE | Current credits 36/48; allowance not exhausted |
| Calibration/selection artifact stages | BLOCKED | Not started |
| Navigation, model fitting, policy calibration/selection | BLOCKED | Zero executions |
| Reserved assessment/final-held-out | NOT AUTHORIZED | No reserved outcomes accessed or executions performed |
| Phase 2 | NOT READY | Phase 1.5 gates incomplete |

The final permitted synthetic run reports **166 passed, 1 failed**, with no
historical or registered generator calls inside tests. The failing test is
retained without xfail/skip. Its [JUnit evidence](../results/phase15_macos_development/phase15-stopped-gates.xml)
and [failure log](../results/phase15_macos_development/phase15-recovery-continuation.log)
are committed. Earlier passing reports are retained and do not supersede it.

The new cache in `Coordinator.restore()` is populated from `rows` captured before
recovering a fully staged record. Recovery publishes and applies the record but
does not add it to that snapshot. The next `execute_one()` sees an unexpected
publication and raises `Missing/conflicting completed publication; no retry`,
before constructing the next candidate. The existing tests verified restoration
but not continuation. This regression was introduced during this migration;
it should have been covered before launch. No fix was applied to the locked
execution source after registered generation began.

## Retained development prefix

| Mechanism | Attempted | Geometry-valid | Complete worlds / current credits |
| --- | ---: | ---: | ---: |
| R | 24 | 24 | 12 |
| BP | 14 | 14 | 12 |
| V | 263 | 0 | 0 |
| M | 12 | 12 | 12 |
| Total | 313 | 50 | 36 |

Exclusive outcomes: independent 36; same-partition related 1; historical/other-
partition rejection 13; Voronoi seed separation 254; Voronoi core 8; unintended
adjacency 1. There were no registered backend failures or dynamics-limit stops.
No transitive credit-reducing bridge occurred in this prefix. These are
provisional credits, not a frozen final population or a claim that V exhausted
its allowance. All eight calibration/selection mechanism quotas remain
unstarted.

The stop was external to candidate construction after the critical synthetic
failure: the parent was paused, absence of `pending.json` was verified, and
SIGINT was queued before resuming. The runner drained resource records and closed
its writer. Source/configuration/dependency/reference commitments still verify.
Independent saved-record reconstruction and the production record validator
both pass. There are no missing records, staged files, duplicate identities,
unresolved attempts or resampled candidates. The last candidate was
`phase1.5-v0.4-BPRIME-1:fit:V:80020262`. Candidate order, quotas, seeds and
sampler/equivalence definitions were not changed.

Elapsed run time: 908.894 s; parent CPU 897.497 s; native CPU 7.592 s. The large
integrity-checking overhead and growing per-decision rehash cost warrant an
infrastructure benchmark before further execution. No computational budget was
exhausted; this was a recovery-validation stop. No navigation performance,
generalization, statistical superiority, novelty or physical-safety claim follows.

## Storage and next review

Complete new raw evidence: 5,331 files / 34,370,678 bytes, file-inventory digest
`38ed166e067f80d5389c8c41fcd9dc537569793fa25fe8a3caaabb4340d9a885`.
Original files remain under `results/raw/phase15_macos_development`; an exact
verified read-only durable copy is at:

`/Users/masahir0/ResearchEvidence/humanoid-spatial-memory/phase15-macos-development-stop-2dcadbe-313`

The [storage manifest](../results/phase15_macos_development/development_storage_manifest.json.gz)
pins every raw file. A compact [checkpoint package](../results/phase15_macos_development/fit_checkpoints.tgz)
contains the complete original checkpoint/receipt/run-lock bytes. Full resource
journals are retained locally and durably with hashes; none were truncated or
deleted. The original Windows transport and restored historical directory are
unchanged. No multi-gigabyte artifact was committed.

Before further generation, approve and test a narrow post-recovery snapshot fix,
including continuation at every publication boundary, missing/deleted/conflicting
record checks, receipt accounting and no resampling. Any performance improvement
must preserve actual input/path/hash checks and scientific behavior. A reviewed
provenance-preserving continuation design is required: do not alter the original
run lock, rewrite its 313 records, reset quotas/seeds, or relabel this prefix as a
new independent population. The next scientific draw, if approved, must follow
reconstruction of this same fit prefix. Then finish fit and its independent/visual
gates, followed by calibration and selection artifact stages. Downstream Phase
1.5 numerical/controller/navigation gates and separate assessment authorizations
remain prerequisites to any Phase 2 claim.
