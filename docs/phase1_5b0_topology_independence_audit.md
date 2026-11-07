# Phase 1.5B-0 topology-independence audit

2026-11-07. **Partial artifact audit; independent development population not
established.** The exact backend hit its declared resource guard on the first
maze quotient, so generation stopped. Sampling distributions, quotient rules,
near-equivalence and frozen candidate limits were not relaxed. See
[generator validation](phase1_5b0_generator_validation.md) and
[development manifest review](phase1_5b0_development_manifest_review.md).

## What exactness means here

The room/corridor quotient follows v0.2: mark all cells in fully free2x2 squares;
contract four-connected marked components; initially remove contraction-created
loops/duplicate edges; suppress degree2 paths while preserving corridor multiedges
and loops. A pure cycle reduces to a one-node/one-loop graph regardless of length;
SINGLE has one node/no loop. Start/goal and metric coordinates do not color the
normalized graph. Raw free-cell rasters remain archived, so their labeled
four-neighbor graphs can be reconstructed; no claim is made to have computed
large **unlabeled raw-cell** canonical certificates in addition to the quotient.

The exact certificate minimizes the loop vector and upper-triangle multiplicity
serialization over all labelings. The implementation uses ordered partitions
tied by loops and prior rows, sorts each cell by adjacency to the next vertex,
and explores only vertices with minimal next-row prefixes. True twin transpositions
are pruned as proved automorphisms; memoization reuses identical labeled subproblems.
These preserve the literal lexicographic objective. They do not treat degree,
fingerprints, seeds or hashes as proof of equivalence.

Near keys include the exact normalized graph and the specified one-leaf deletions
and one-non-loop-edge contractions followed by suppression. Contracting one of
several parallel edges turns the remaining parallel edges into loops; it does
not discard them. Common lineage, raster symmetry or intersecting exact near-key
sets induces a union. All unions are transitive. Cross-partition bridges are
rejected rather than silently merged into 'independent' data.

## Mathematical validation

Golden cases include narrow versus two-cell doorways, long corridors, cycles of
different lengths, multiedges, loop-producing contraction, graph relabelings,
equal-degree nonisomorphic graphs and a chain that merges two old components
before a cross-partition rejection. The exhaustive checks comprise all1,099
simple graphs through five vertices, plus90 random small multigraphs against
independent full-permutation references. These support correctness on tractable
graphs, not performance or exhaustive correctness for every75-node input.

The [measurements](../results/phase1_5b0/canonicalization_measurements.json) record
every historical/candidate variant searched, including the failed one. The
[independent report](../results/phase1_5b0/independent_verification.json) records
small-graph reference timings and byte/source verification.

| Workload | Observed exact-search behavior |
| --- | --- |
|1,024 simple five-node graphs, independent comparison run | .0732 s total exact backend; .2554 s unpruned reference |
| Historical variants,1–11 vertices | All certified; observed per-call maximum about1.85 ms |
| R fit seed50,000,000,11-node normalized graph |18 self/near variant calls; largest about2.58 ms; eight unique near keys |
| M fit seed50,030,000,75-node normalized graph | First exact self-certificate timed out at5.000 s after17,540 search nodes; no key returned |

A search call is capped at100,000 nodes or five wall-clock seconds, whichever
comes first. These are explicit technical feasibility guards, not the scientific
10,000-candidate limit. The75-node failure is evidence this implementation does
not meet that guard on this graph/hardware, not a proof that exact labeling is
intrinsically impossible or that another exact backend cannot succeed. There was
no background full-suite run competing with the artifact timing measurement.
Graph structure and size both vary across these workloads; the observations
do not fit an asymptotic scaling law or establish a universal75-node limit.

## Historical overlap: permitted metadata only

Read only complete stored scenario arrays from the six historical result files,
Phase1.4A tuning/assessment manifests and smoke artifacts. No old scenario was
regenerated for exclusion, and no reserved held-out configuration/outcome was
opened. Old assessment **geometry metadata**, not policy performance, was used
for exclusion. Both walls-only and walls-plus-initial-objects interpretations
were conservatively included because old fixed/dynamic occupancy boundaries do
not map identically onto the new base-geometry definition.

There are110 distinct raw raster interpretations in this permitted inventory,
all certified. They reduce to **nine exact quotient classes**, with959 unordered
raw-geometry pairs sharing exact classes. The near/lineage union yields **eight
components** of sizes26,25,19,18,18,2,1,1. These are raw interpretations, not110
independent historical worlds. The lone admitted R candidate matched none of
these historical exact/near/raster components.

The audit's metadata scanner flags
`results/phase1_4a/benchmark/results.json` because it has no scenario arrays.
Read-only inspection of the hash-pinned benchmark source establishes that it
constructs **public ternary memory workloads**, including unknown cells, rather
than physical world scenarios. Therefore this flag is not evidence of a missing
true assessment layout. The source hash and scope review are recorded separately
in verification; the raw scanner flag is preserved, not edited away.

No true layout was inferred by arbitrarily assigning those unknown bits free
or occupied. If research review requires exclusion against the original benchmark
memory arrays as a separate object class, obtain their saved arrays/checksums
or separately authorize source-only reconstruction of those public workloads,
without calling policies or opening any old held-out world. Such an exercise
would not manufacture a true-occupancy certificate. The present no-overlap claim
is restricted to the110 stored physical-raster interpretations, not all possible
unstored historical states or every future held-out layout.

## Current candidate and partition results

The driver scans fit/calibration/selection, using deterministic repeated R/B/V/M
rounds for underfilled mechanism quotas. It credits a merged same-split component
only once, to its earliest complete representative. A new bridge can reduce old
counts; it cannot increase the number of independent clusters by appearing under
another mechanism name. Split boundaries freeze only after successful completion.

| Fit candidate | Outcome | Independence disposition |
| --- | --- | --- |
| R50,000,000 | Valid geometry, pair distance16, two valid schedules | One provisional component disjoint from certified historical components |
| B50,010,000 | Connectivity rejection | No accepted world; no repair |
| V50,020,000 | Seed-separation rejection | No accepted world; no replacement seed selected for performance |
| M50,030,000 | Valid raw geometry,75-node quotient; labeling guard | Uncertified; no pair/schedules or independence credit |

There are zero measured development exact/near collisions and zero measured
cross-mechanism/cross-partition collisions before the stop. This is **not**
evidence that collisions are rare: only R reached admission, and calibration/
selection were never generated. Full duplicate/lineage/cross-split behavior was
tested with adversarial mathematical fixtures, not empirically established on
a completed development population.

## Is the equivalence too coarse?

Two findings are supported:

1. The rule intentionally merges different corridor lengths and can merge two
   rooms through a two-cell opening; golden fixtures show this. It discards some
   metric/visibility distinctions that can matter for observation scheduling.
2. The historical inventory compresses strongly under the quotient. Most of that
   compression is exact-class sharing (nine classes); near transitivity merges
   those into eight. This inventory is template-heavy and contains alternative
   interpretations, so compression does not by itself demonstrate excessive
   merging of genuinely independent new topologies.

Whether the new population experiences excessive transitive merging remains
unverified. No rule was changed in response. The audit stopped for computational
feasibility before a meaningful new-population sample existed.

## Decision and next review

Not ready for Phase1.5C or policy development. Review an optimized **exact**
backend or formally equivalent exact representation, preserving the independent
small-graph oracle, loops/multiplicities and near relation. Any resumed audit
must pin its source/technical limits, preserve this stopped evidence, honor all
candidate identities, and repeat allowed exclusion checks. Do not silently raise
limits, substitute WL/hash equality, omit M, reduce quotas or relax samplers.

Future assessment independence is wholly unverified: no assessment/final world
was generated. Even a later successful development audit would not establish
future cross-partition exclusion until those separately authorized artifacts
are actually audited. Stop for review.
