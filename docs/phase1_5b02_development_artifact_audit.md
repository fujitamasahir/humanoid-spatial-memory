# Phase1.5B-0.2 development artifact audit

2026-11-07, branch `feature/phase1-4c-assessment`, base
`d2c3f58672b6732305385d37079de9269f2ee9de`.
**Not ready for Phase1.5B-1.** Exact nauty canonicalization and its amended
resource guards passed, but the new development audit stopped at the frozen
10,000-candidate fit-B limit. The required48/24/24 population is not established.
No filter/controller/EVSI implementation or policy experiment followed.

The [approved amendment](phase1_5b02_canonicalization_amendment.md) changes canonical
representation and technical guards only. The [production validation](phase1_5b02_production_backend_validation.md)
documents exactness, reproducibility, resource enforcement and limitations.
All original sources, samplers, specification documents, failed-audit records,
Phase1.4 artifacts and2,212 historical regression records remain unchanged.

## Population and stopping decision

| Partition | Required clusters (R/B/V/M) | Certified provisional clusters | Status |
| --- | --- | --- | --- |
| Fit |48 (12/12/12/12) |38 (12/2/12/12) |Stopped at B candidate limit |
| Calibration |24 (6/6/6/6) |0 |Not started |
| Selection |24 (6/6/6/6) |0 |Not started |

| Fit mechanism | Candidates | Valid base geometries | Initially independent admissions | Final cluster credits |
| --- | ---: | ---: | ---: | ---: |
| R |18 |18 |14 |12 |
| B |10000 |4492 |6 |2 |
| V |9249 |12 |12 |12 |
| M |12 |12 |12 |12 |
| Total |19279 |4534 |44 |38 |

The stream consumed every B seed50,010,000 through50,019,999; no10,001st candidate
was generated. V reached its quota at seed50,029,248 and stopped being proposed.
R used50,000,000 through50,000,017 and M50,030,000 through50,030,011. These ranges
describe attempted identities, including rejected/related candidates, not independent
sample sizes. The original R/B/V/M round-robin order and under-quota skips were
preserved. A later same-split bridge can reduce previous credits, which then
need refilling; no component is credited twice under different mechanism names.

The first four identities are unchanged: R50,000,000; B50,010,000; V50,020,000;
M50,030,000. B's connectivity rejection and V's seed-separation rejection remain
the same. The original R complete artifact reproduces exactly at the geometry,
pair and schedule level. Original M geometry/matrix now certifies under C3 and
receives its first pair/schedules; its old uncertified archive remains immutable.
This is a new audit, not an overwrite or retroactive success assigned to B-0.

## Feasibility and relation results

B's10,000 attempts contain5,204 connectivity and304 unsplittable rejections,
2,276 historical exclusions,2,210 same-partition related admissions, and six
initially independent worlds. Its valid-geometry fraction is44.92%, but transitive
near unions leave only two credited components. R similarly goes from14 initially
independent admissions to12 final components; its other four candidates are
same-partition related. This distinction explains why44 complete worlds do not
mean44 final independent topologies. It is supported by stored near sets and
independent union reconstruction, not inferred merely from scenario labels.
The two B components contain1,687 and529 admitted records (including related
artifacts without schedules). Across all4,490 relation events,2,330 have an exact
match and2,160 have near-only matches. These counts combine accepted same-fit
relations and rejected historical relations; they are not4,490 extra clusters.

V rejects9,077 for seed separation,129 for core constraints and31 for unintended
adjacency. Only12 of9,249 attempted geometries are valid (about0.130%). Every
valid V geometry in this frozen prefix fills a separate component; this says
nothing about later unseen seeds or cross-split feasibility. M fills12 components
in12 attempts, and R fills12 after18. These are conditional finite-prefix
feasibility facts, not iid acceptance-rate estimates or navigation outcomes.

Historical comparison regenerates new keys from110 permitted stored raster
interpretations: nine exact classes and eight near/lineage components, as before.
All2,276 `cross_partition_or_historical` events in this run are **historical**
exclusions in fit-B. Calibration/selection never start, so there is no empirical
new-development cross-partition separation result. Mathematical bridge fixtures
test that rejection rule; they do not establish future partition independence.
There are no final cross-mechanism components in the admitted fit population.

The relation is the prescribed ordered admission rule: reject a proposed
historical/cross-split bridge without inserting it or retroactively merging
already frozen partitions. No claim is made that admitted graphs are disconnected
under every possible unadmitted near bridge in the universe of graphs. Nor do
distinct seeds, disjoint certificates or the38 admitted components prove iid
sampling. The historical scope remains stored physical rasters, not unstored
states, public unknown-cell benchmark memories or reserved held-out worlds.

## Verification, runtime and storage

[Independent verification](../results/phase1_5b02/independent_verification.json)
replays every geometry outcome and candidate identity, reconstructs under-quota
order, validates every checkpoint/archive checksum and independently rebuilds
the near/lineage/raster unions without using the production IndependenceIndex.
It regenerates archived exact/near keys through the guarded backend, checks all
44 complete worlds' pair/schedules with a separate flood-distance validator,
and reconstructs the38 representatives and all component members. Exact-match
versus near-only match-event counts, component sizes and credit transitions are
saved there. These are match-event counts, not interchangeable with unordered
graph-pair counts.
Independent reconstruction completed in471.300 seconds; it performs artifact
replays solely for verification and does not add manifest candidates.

The complete suite passed243 tests; all2,212 historical record bytes/counts and
original tracked files remain unchanged. One preliminary eager-loading verifier
attempt failed its conservative resource-evidence check; streaming fixed the
verification harness without changing the backend or rerunning the audit.
The production validation and delivery report preserve that incident and its
standalone Linux RSS-accounting probe.

The runner recorded678.845 seconds (11.31 minutes) and179,720 KiB parent peak RSS
(175.51 MiB) at summary construction. Those values exclude subsequent final
metadata serialization/archive rechecks and independent verification; no complete
end-to-end peak or isolated performance comparison is inferred. Successful near
calls' wall/CPU/process-RSS data and full preflight M/R near-set costs are retained.
The inherited driver separately recomputes one self key per valid graph without
adding that duplicate call to the near-timing inventory; those calls still use
all production guards. Timing coverage and derived call counts are stated
explicitly in independent/delivery evidence rather than claiming every call was
separately logged. Native node counts remain unavailable.

The saved full-near inventory contains59,908 successful calls; its maximum parent
wall interval is0.196224 seconds and maximum worker peak RSS117,712 KiB
(114.95 MiB). Summed worker CPU across those calls is6.116 seconds. There are
another4,644 separately guarded self-key calls (110 historical +4,534 valid
candidates), for64,552 enforced calls in the audit. Those duplicate calls do not
have separate CPU/wall records. The large difference between native CPU and total
audit time includes normalization, geometry/schedule construction, supervision,
lineage bookkeeping and filesystem checkpoint work; it is not navigation runtime.

There are4,534 gzip geometry/construction/matrix/near-set artifacts, totaling
7,320,747 bytes, and19,279 atomic per-candidate checkpoints outside Git. Only44
artifacts contain selected pairs and two complete schedules; the38 final
representatives contain76 schedules, still38 topology clusters. Invalid geometry
draws have identity/reason checkpoints and deterministic replay, not invented
accepted-world payloads. No navigation episode trace was generated.

The original19,743,850-byte call-measurement JSON is retained outside Git; its
lossless gzip in Git is1,952,943 bytes. [Measurement storage](../results/phase1_5b02/measurement_storage.json)
pins both hashes and roundtrip equality. The
[artifact storage manifest](../results/phase1_5b02/trace_storage_manifest.json)
pins every geometry gzip; [delivery verification](../results/phase1_5b02/delivery_verification.json)
records total logical bulk bytes, checkpoint count and the reproducible sorted
whole-storage checksum. Filesystem allocation overhead is not included in logical
byte totals. Periodic `progress.json` is a live snapshot at19,275 candidates;
the final19,279-record inventory and terminal summary are authoritative.

Compact evidence: [summary](../results/phase1_5b02/summary.json),
[candidate inventory](../results/phase1_5b02/candidate_inventory.jsonl.gz),
[provisional manifest](../results/phase1_5b02/development_manifest.json),
[source/runtime provenance](../results/phase1_5b02/provenance.json),
[generator feasibility](../results/phase1_5b02/generator_feasibility.json), and
[compressed per-near-call measurements](../results/phase1_5b02/canonicalization_measurements.json.gz).
Reproduction steps are in the production validation; never overwrite this audit.

## Scientific review recommendation

The original computational blocker is resolved for this frozen prefix under
the approved exact representation and enforceable guards. The remaining blocker
is population feasibility: the prescribed B stream did not produce12 independent
components within its allowance, despite thousands of valid geometries, while V
has a very low raw acceptance rate. This does not prove that12 B components are
mathematically impossible over an unlimited population, or that near equivalence
is scientifically wrong. It does establish failure of this frozen development
construction and budget.

Review the generator population and conservative transitive near relation
together before authorizing any revised artifact protocol. Do not raise limits,
relax equivalence, replace B, reduce quotas or count related worlds as independent
without a new explicit scientific decision. No new default or replacement sampler
is selected here. Keep `navigation_authorized=false` and do not begin Phase1.5B-1
belief-filter implementation or Phase1.5C experiments. Stop for scientific review.
