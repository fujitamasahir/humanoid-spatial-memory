# Phase 1.5 B′ population preregistration amendment

Version **phase1.5-v0.4-BPRIME-1**, 2026-11-07.
Baseline commit: `0c0f7d7b5fa394d5ec981ec7301b1987c4658ac5`.
Branch: `feature/phase1-5-bprime-preregistration`.

The user approves these three documentation additions and their commit/push
only. No generator implementation, synthetic execution, candidate sampling,
topology audit, navigation, fitting, calibration, selection, assessment or
final-held-out access is authorized. Future permissions must name the stage.
The immutable B-02 result remains 38/48 fit components (12/2/12/12); its frozen
10,000 B candidates were exhausted. Calibration and selection did not start.

## 1. Scope, baseline and departures

Read with the [generator specification](phase1_5_bprime_generator_specification.md)
and [validation plan](phase1_5_bprime_validation_plan.md). The applicable baseline
is [v0.2 generator rules](phase1_5a2_generator_specification.md),
[v0.2 downstream amendment](phase1_5a2_protocol_amendment.md), recorded
[clarifications](phase1_5b0_generator_validation.md), and approved
[canonicalization amendment](phase1_5b02_canonicalization_amendment.md).

| Original B / prior population | Explicit new departure |
| --- | --- |
| Arbitrary integer-coordinate recursive cuts | Recursive 6×6 macro-grid partitions; unchanged uniform room-count choices 12/16/20 |
| One door during each split | Finish partitions, sample room graph, then isolated doors |
| No separate cycle-link sampler | Random-edge-order Kruskal tree plus uniform K additional edges from the unused list |
| Descendant splits can disable ancestor access | Connectivity by construction; no post-rejection repair |
| Original geometry RNG | Separate partition/tree/chords/doors streams and fresh population prefix |
| Old provisional quota credits | New four-mechanism realizations; no credits transferred |
| Historical reference scope | Original references plus previously admitted development geometries; rejected valid candidates remain a separate nonreference category |

R/V/M construction laws, approved topology/near relation, pair/dynamics laws and
Phase 1.4 locks are unchanged. The target is now R/BP/V/M conditional on ordered
admission and the frozen reference inventory. It is not a successful execution
of original B. Cross-version comparisons are descriptive, not paired population
replications. Denser connection variation can change route redundancy and task
difficulty. Different seeds and canonical nonidentity do not establish iid data.

## 2. Historical exclusion decision

The following three categories must remain distinguishable in a future sealed
inventory, before artifact execution:

1. **Original historical references:** preserve exactly the 110 permitted stored
   physical-raster interpretations and their approved lineage/matching scope.
   Use stored metadata/certificates, never old world execution or reserved worlds.
2. **Previously admitted development geometries:** include all records actually
   inserted in the prior development relation index, not only final representatives
   or initially independent complete worlds. In B-02 these are the 44 `independent`
   and 2,214 `same_partition_related` records: 2,258 identities. Include their
   component memberships and genuine ancestry. Older admitted identities repeated
   in B-02 are provenance aliases, not extra statistical units.
3. **Previously rejected valid development candidates:** B-02's 2,276
   `cross_partition_or_historical` valid candidates remain identifiable but are
   **not automatically inserted as exclusion references**. Missing/invalid outputs
   and old uncertified partial geometry are not silently promoted either.

Thus the 4,534 valid B-02 payloads partition into 2,258 admitted references and
2,276 nonreference rejections; the 110 original references remain separately
identified. Alias/content deduplication must preserve source IDs and categories.
A rejected record with an independently established genuine ancestral link to
an included root cannot be used to evade common-lineage rules. No artificial
ancestry is inferred merely from a near match. New intentional derivatives of
any old root cannot be relabeled fresh independent draws.

This is a new versioned population decision approved for drafting, not a change
to B-02's admissions. The frozen baseline §8 rejects matches to stored historical
bases and previously admitted other-split records; it does not mandate promoting
all failed valid proposals. No conflicting mandatory all-rejections rule was
identified in the reviewed baseline. Discovery of such a rule stops the process
for scientific review; do not silently override it using document precedence.

This choice avoids reusing selected/admitted development samples while avoiding
an unapproved expansion through rejected bridges. It does not promise novelty
relative to every generated/rejected geometry or every possible near bridge.
No-overlap statements must name the included inventory. Exclusions condition
the population and can disproportionately remove particular topology classes.
No subsequent choice between exclusion scopes may use acceptance or outcomes.

Future inventory entries must pin category, inclusion flag, original identity,
ancestry/aliases, source commit/path, compressed bytes/SHA-256, raster dimensions,
static-base interpretation, quotient matrix, C3 exact/near keys and key namespace.
Seal the complete sorted inventory and its digest before candidate execution.
Cross-check categories against every saved candidate outcome. Preserve rejected
records and their hashes in a separate ledger without entering their keys into
the reference index. Report original-history and admitted-development exclusions
separately. All keys must use the approved C3 representation.

## 3. Single normative execution table

This table consolidates execution rules; it grants no execution permission.
The companion specification supplies its mathematical construction details.

| Topic | Normative rule |
| --- | --- |
| Coordinates | Cells `(x,y)`; row-major `(y,x)` unless expressly overridden. Inclusive macro rectangles `(x0,y0,x1,y1)` sorted by that tuple for leaf choices and room IDs. Axes x then y; cuts increase numerically; graph edges sorted by ordered room-ID pair. Door positions increase along shared side. |
| RNG framing | UTF-8 fields `(phase1.5-v0.4-BPRIME-1, decimal_seed, purpose)`, each prefixed by uint32 little-endian byte length; SHA-256, first 16 digest bytes interpreted little-endian as Philox key. NumPy 2.2.6 raw uint64 convention is pinned; no global mutable stream. |
| Purposes | BP: `partition`, `tree`, `chords`, `doors`, `start-goal`, `dynamics-0`, `dynamics-1`. R/V/M use their unchanged baseline purpose structure under the new prefix. Geometry names/seeds remain evaluator-only. |
| Uniform/permutation | Reject uint64 words at or above the largest multiple of bound n not exceeding 2^64; return remainder. Singleton uniform choices consume a word. Fisher–Yates visits indices length−1 through 1; no permutation words for lists of length≤1. |
| Consumption | Partition: N then leaf/axis/cut per split. Tree: full edge permutation. Chords: K then full unused-edge permutation even K=0. Doors: one choice per sorted selected edge. Separate pair and schedule streams; no alternative draw on another purpose after rejection. |
| Seed allocations | Fit 80,000,000–80,099,999; calibration 80,100,000–80,199,999; selection 80,200,000–80,299,999. Assessment reservation 90,000,000–90,999,999; final reservation 100,000,000–100,999,999. Within each range offsets 0/10,000/20,000/30,000 belong to R/BP/V/M; indices 0–9,999 only. Unused remainder stays reserved. These ranges do not overlap frozen 50/60/70-million ranges. |
| Lineage | One complete base draw is one root; deliberate derivatives inherit all actual ancestral links across versions/labels. Independent accidental equality is handled by exact/near/raster rules. Common lineage can merge different cycle ranks. |
| Priority | Malformed output or failed BP construction invariant stops as a defect. Then geometry constraints; historical/other-split matches reject without insertion; same-split matches insert a relation-only record and union; unmatched candidates proceed to pair selection, then two schedules, then complete-world admission. Empty pair list rejects without insertion. Preserve reason flags; count first reason exclusively. |
| Relation | Exact approved raster quotient, suppression, loops/multiplicities, C3 full keys, intersecting near sets, raster symmetries and genuine lineage; transitive same-split union. No heuristic/hash/coarse-summary substitution. Cross-partition bridges reject without insertion, not retrospective merging. |
| Credits | One credit per final transitive component, assigned to its earliest complete representative's mechanism. Related records and two schedules do not add credits. Cross-mechanism components never earn multiple credits. Recompute credits after every insertion; under-quota mechanisms can reactivate after merges. |
| Order/quotas | Fit then calibration then selection. Repeated R/BP/V/M rounds, one candidate for each currently under-quota mechanism. Per-mechanism targets 12/6/6, total 48/24/24. Freeze each completed split before the next. No old credits carried forward. |
| Scientific limit | At most 10,000 candidates per mechanism per development partition, every attempted index consumed. At an under-quota exhausted cursor stop before another draw. No extension, replacement, sampler switch, quota reduction or weakened relation. Mark manifests provisional and navigation unauthorized. |
| Canonical guards | Keep `phase1.5-v0.3-CANON-1`, pinned pynauty/nauty artifacts/options and approved supervisor. Five wall seconds per call, isolated worker peak RSS≤512 MiB, Linux hard/soft RLIMIT_AS=536870912 bytes. Native node count unavailable/null; do not claim the old 100,000-node guard. Any failed/late/malformed/memory/crash reply stops with no key or retry. |
| Dynamics | Existing category order none/addition/removal/swap/moving; category and length fixed across at most 128 footprint proposals; static onset fixed too. No-change draws nothing else. Moving reversal after successful path; complete final dwell draw then truncate positions to 81. Exhaustion stops, no category/geometry replacement. |
| Integrity | Pin source/configuration/runtime/dependencies and reference inventory before execution; POSIX single-writer lease, durable atomic checkpoints, immutable archive hashes and complete membership/rejection records. Changed locks, missing/conflicting records or source failures stop. |
| Access | A development entry point must reject assessment/final partitions and paths before opening them, despite reserved seeds. Assessment admits only a separately approved locked manifest and compares against all frozen development references. Final-held-out requires a separate curator/access gate. No stage follows automatically from another's success. |
| Resources/downstream | Retain v0.2: at most 2,112 development navigation executions and 6,720 assessment executions; development 30 CPU-hours/15 GB, assessment 30 CPU-hours/25 GB, independent verification 10 CPU-hours/5 GB temporary workspace. No current execution authorization. Preserve v0.2 numerical, activation, calibration, timing and controller gates. |
| Analysis | Retain v0.2 estimation-focused paired analysis: average replicas then schedules within topology, weight mechanisms 1/4, 10,000 within-mechanism component bootstrap draws with seed 1505011; report failures, degeneracy and leave-one-mechanism-out results. No superseded v0.1 superiority or matrix rules. |
| Precedence | These three new docs amend population construction, namespaces, lineage clarification, reference scope and inherited audit details only for this new version. This table governs execution; companion spec governs mathematical sampling; validation plan governs gates. Approved C3 amendment governs canonicalization; recorded v0.2 clarifications and v0.2 downstream amendment govern unchanged behavior. v0.1 survives only where not superseded, including resolved visual inspection below. A genuine conflict stops review, not discretionary interpretation. |

## 4. Inherited audit requirements and limits

Retain the original preselected visual inspection requirement as follows: before
any future audit, freeze its selection rule. For each completed development
partition, select ceil(0.20×component count) final representatives by increasing
SHA-256 of the length-framed fields `(population version, visual-audit,
representative identity)`, identity tie-break. Inspect all certificates and this
at-least-20% visual subset blind to policy outcomes. Selection uses no additional
candidate RNG and does not choose visually convenient worlds. Publish diagrams,
checks and discrepancies; inspection does not authorize geometry repairs.
This explicitly resolves the inherited underspecified sampling rule without
changing generator probabilities. Preflight design fixtures are separate from
manifest candidates and require separate permission before execution.

A saved free-cell raster plus four-neighbor rule reconstructs its labeled raw-cell
graph. No large unlabeled raw-cell canonical certificate is asserted or required
as already available. This carries forward the scope stated in B-0's topology
report and explicitly supersedes the earlier unfulfilled raw-certificate wording.
Exact canonicalization remains mandatory for the normalized quotient.

Finite-budget quota-success probability is unknown. A completed development
population would not prove stochastic independence, assessment feasibility,
generalization, superiority, novelty or physical safety. The target is conditional
on the declared sampler, reference inventory and ordered admission. Quota failure
is a valid negative result, never permission for silent adaptation. Preserve
all Phase 1.4 locks/results and B-02 files byte-for-byte. Stop for separate
implementation approval after documentation delivery.
