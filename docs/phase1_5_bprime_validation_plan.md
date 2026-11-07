# Phase 1.5 B′ independent validation plan

Version **phase1.5-v0.4-BPRIME-1**, 2026-11-07.
Baseline `0c0f7d7b5fa394d5ec981ec7301b1987c4658ac5`.
This is a preregistered plan, not passed validation. No implementation, fixture
execution, sampling or experiment is authorized by documentation approval.
Read the [specification](phase1_5_bprime_generator_specification.md) and the
[amendment's normative table](phase1_5_bprime_protocol_amendment.md).

## 1. Authorization and evidence stages

1. Documentation review: approve complete sampling, lineage, exclusion policy,
   version/seed allocation, gates and accepted feasibility uncertainty.
2. Separate implementation/verification approval: faithful components and
   predeclared synthetic mathematical fixtures only, if explicitly authorized.
3. Separate artifact-audit approval: source/reference freeze and new development
   fit/calibration/selection artifact construction only. Not navigation fitting
   or policy calibration/selection. Reserved partitions remain inaccessible.
4. Scientific review of complete verified artifacts before any downstream work.
   A complete development audit neither authorizes navigation nor establishes
   future assessment independence. Assessment and final-held-out need distinct
   later approvals, locks and access gates.

Failure or missing evidence is not a pass. Verification may not quietly generate
new candidates, replace failed outputs or overwrite frozen artifacts. Any future
replay permission must distinguish saved-artifact verification from new draws.

## 2. Required independent gates

| Gate | Required checks and retained evidence |
| --- | --- |
| Sampler conformance | Independent exact-choice checks for room counts, eligible leaf/axis/cut sets, edge permutation/Kruskal and K/subset law; compare against analytical small-domain enumeration where tractable. Verify every integer bound, singleton draw and permutation order. No statistical frequency test substitutes for algorithm conformance. |
| Partition correctness | Disjoint complete 6×6 coverage, target leaf counts, splittability proof, rectangle bounds, minimum raster dimensions. Check each logged split against its parent and child rectangles. |
| Connectivity | Independently build adjacency from boundaries and flood raster cells without production connectivity routines. Verify selected spanning tree and G connectivity; failed guarantee stops as a defect. |
| Raster correspondence | Reconstruct every selected portal independently. Door neighbors, spacing, wall junction exclusion and unselected closed interfaces must hold. Verify N marked components and that pre-suppression quotient is the specified subdivision of G. Independently check density/free-count/border bounds. |
| Exact/near equivalence | Retain approved independent exhaustive small-graph oracle, relabeling/process checks, loop/parallel/cycle/door fixtures and full-key comparisons. Check leaf/edge operations and residual multiplicity. Verify cycle-rank preservation on normalized operations, and a deliberate cross-rank common-lineage fixture proving rank does not override lineage. |
| Historical exclusions | Seal exact category/include/ancestry inventory before candidates. Verify all original references and all prior admitted records; retain rejected valid candidates as nonreference ledger entries. Reconstruct every match and exclusion against included records only. Test a rejected historical bridge that must not be promoted automatically; separately test genuine ancestry crossing labels/versions. |
| Transitive accounting | Independent reconstruction without production union/index code: every candidate identity, relation, ancestry, insertion/rejection, merged component, earliest complete representative and mechanism credit. Check bridges that reduce credits, reactivate a mechanism, cross mechanisms and reject across partitions. Reconstruct final memberships and original fixed round-robin order. |
| RNG reproducibility | Independent stream framing/key tests, fixed raw-word fixtures under the pinned NumPy version, exact draw counters and cross-process replay. Verify disjoint old/new ranges, partition blocks and purposes. Changing K or a rejected schedule must not advance another stream. No stochastic-independence theorem is inferred from stream separation. |
| Pair/dynamics | Independent ordered eligibility/distances; protected endpoints; category and fixed onset/length; full retry reasons; swap disjointness; moving direction/dwell order and final truncation. Check 128-proposal failure stops without world replacement. |
| Artifact integrity | POSIX exclusive writer, durable atomic records, saved checkpoint publication/recovery rules, complete size/SHA-256 inventory and immutable source/config/reference/runtime identities. Detect duplicates, missing files, conflicts and source changes. Independently check payloads, not just manifest-to-manifest agreement. |
| Backend/resources | Retain production guards and dependency pins; memory exhaustion, native timeout, partial/malformed output and crash all fail explicitly. Log native node counts null. Stream verification bodies to avoid inherited large-parent RSS evidence problems. No weakened guard or heuristic fallback. |
| Population feasibility | Final 48 fit/24 calibration/24 selection components, per-mechanism 12/6/6, at most 10,000 attempts per mechanism/partition. Include every failure and credit reduction; related geometries and schedules are not independent samples. No navigation outcomes used. |
| Visual audit | Freeze the amendment's hash-selected at-least-20% rule before execution. Inspect all certificates plus selected final raster representatives blind to outcomes, with saved diagrams and discrepancy decisions. No favorable visual substitutions. |
| Public boundary | Projection contains only inherited dimensions/pose-goal/domain guarantees; no seed, mechanism, partition, ancestry, true geometry, future events, topology or labels. Development rejects reserved paths before opening. |

## 3. Reference archive dependencies

Before an artifact audit, independently verify these existing evidence inputs:

- B-02 `candidate_inventory.jsonl.gz`, `development_manifest.json`,
  `trace_storage_manifest.json`, `independent_verification.json`,
  `historical_topology.json`, `historical_integrity.json`, `provenance.json`,
  `archive_verification.json`, `delivery_verification.json` and checkout proof,
  all under `results/phase1_5b02/`, at the reviewed baseline.
- Original 110-reference metadata provenance and C3 keys. No old held-out world
  or policy assessment outcome is needed. Public benchmark memories are not
  invented physical rasters; retain the prior scope caveat.
- B-02's 4,534 gzip geometry payloads and 19,279 checkpoint records under the
  original ignored `results/raw/phase1_5b02_development` storage. Use the saved
  manifests to restore them from their Windows/WSL machine, mapping paths
  portably without altering payload bytes. Total geometry gzip bytes recorded
  are 7,320,747. All original payloads remain preserved even though only admitted
  geometries enter the new reference index. Missing dependencies block sealing.
- The 2,258 prior admitted identities (44 independent +2,214 related) must be
  distinguished from 2,276 rejected valid identities. Check every ledger row,
  component membership, archive identity and hash; deduplicate aliases explicitly.
- The original B-0 archives/provenance needed to verify original repeated R/M
  identities and any ancestry aliases, without replaying candidate constructors.
- Exact `configs/phase15_nauty_backend.json` and its pinned Python/native files,
  production parent/worker sources, Python/platform/NumPy metadata. Native files
  live outside Git; a different build needs separate revalidation and review.
- For a complete re-verification of prior execution claims, restore retained
  JUnit/resource-probe files, original measurement JSON and previous startup/
  verification incident evidence by their recorded hashes. The committed
  measurement gzip is lossless and may supply its original JSON bytes. None of
  these prior pass reports is a new B′ validation pass.

A future sealed reference inventory must give portable relative storage paths,
original absolute location as provenance, category/inclusion flag, source commit,
identity/ancestry, raw artifact bytes/hash and interpretation, matrix and exact/
near-key namespace. Include inventory/schema/selection-rule hashes. If a missing
file prevents the claimed exclusion scope, stop; do not reconstruct old worlds,
substitute graph summaries or silently shrink the inventory.

## 4. Reporting and independent reconstruction

Keep durable per-candidate identity, stream counters, construction trace, graph
edges/tree/additional K, doors, raster, quotient and exact/near certificates,
matching witnesses, category/include flags and exclusive rejection reason.
Store successful pairs/schedules only where the admission rules require them.
Invalid proposals keep failure evidence; they are not complete accepted worlds.
No field may be dropped merely to save space. Preserve full payloads outside Git
with portable immutable storage inventory; compact tables and provenance belong
in Git. Compression must roundtrip exactly. Resume/recovery must reject changed
source/reference identity and duplicates; no implicit scientific retry is allowed.

Report by partition/mechanism: attempts; validity/rejection counts; N and room
sizes; adjacency m and available r; selected K; normalized vertices/edges/β;
exact classes; near-only events; raster/lineage matches; historical category
exclusions; initially independent admissions; all credit transitions; final
components/memberships; cross-mechanism components; pairs/dynamics failures;
canonicalization timing/RSS; storage and verification incidents. These are
finite-prefix descriptions, not iid acceptance estimates or navigation outcomes.
Do not require balanced retained N or K: that would add unapproved filtering.

Reference-only rejected records are not unioned into the new admitted graph.
Claims concern the declared ordered admission universe, not all possible unseen
or rejected near bridges. Within-split transitive closure and cross-split rejected
bridges must be reported separately. Numerical partition PMFs are not claimed
computed; any later exact enumeration must be labeled mathematical analysis,
separately authorized, and must not silently select sampler parameters.

## 5. Decision gate and remaining uncertainty

Stop on failed invariants, backend/lock/access/resource failures or dynamics
exhaustion. If an underfilled mechanism consumes all 10,000 candidates, stop
before another draw and publish incomplete/provisional manifests with
`navigation_authorized=false`. Calibration/selection artifact stages cannot
start before their preceding partition is complete and frozen. No cap increase,
quota reduction, new sampler, graph repair, favorable subset, looser equivalence
or replacement mechanism is automatic. A change needs a separately reviewed
version preserving this and all older failed evidence.

Even a full 48/24/24 audit is only a population-feasibility gate. Independent
verification, visual review and explicit scientific approval must precede any
navigation. Existing v0.2 fitting/numerical/calibration/activation/controller gates
still apply later; their matrices/ceilings are unchanged. Assessment/final-held-out
reservations remain sealed and their future feasibility remains unestablished.

Known limitations: finite-budget success probability unknown; marginal ranks
favor low values; same-rank and lineage merging; macro-grid embedding; density/
redundancy shifts from B; ordered reference conditioning; potential pair/dynamics
failure; no guarantee of iid components, assessment feasibility, generalization,
superiority, novelty or physical safety. These limitations do not license
mid-run adaptation. Current status: documentation only, no B′ implementation,
fixtures, candidates, audits, navigation, calibration or selection executed.
