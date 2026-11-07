# Phase 1.5A topology specification audit

2026-11-07. **Verified finding: no topology generator is sufficiently specified
by Phase 1.5 v0.1 to implement without new scientific choices.** The user's
conditional instruction therefore stops generation at this ambiguity. Zero
candidates, zero layouts and zero navigation episodes were generated. This is a
specification audit, not a successful independence certification.

Read the unchanged [protocol](phase1_5_experimental_protocol.md) and the
[proposed amendments](phase1_5a_protocol_recommendation.md). Existing Phase 1.4
environments/results and reserved held-out configurations were not used to
select new layouts. No held-out world was instantiated or inspected.

## Missing choices that affect the scientific population

| Area | v0.1 specifies | Missing decision; why it is scientific |
| --- | --- | --- |
| Room/corridor graphs | Family name, roughly12–24 regions | Node/edge distribution, room geometry, loops and degree constraints determine route alternatives. |
| BSP partitions | Family name | Split axis/depth/ratio, door probabilities/widths and reconnection rules change bottlenecks. |
| Irregular planar rooms | Family name | Spatial point process, graph sampler, embedding and obstacle distributions change visibility and detours. |
| Maze with chords | Family name | Maze algorithm, chord number/placement and corridor width change cycle and bypass structure. |
| Rasterization | Odd dimensions21/23/25 | Embedding, wall thickness, diagonal handling and connectivity preservation are undefined. |
| Region/junction extraction | Merge junction regions, contract degree2 | Open rooms contain many grid cycles; a region graph and a full free-cell graph are different invariants. |
| Near-topology equivalence | One leaf pruning or edge contraction | Operation ordering, loop/multiedge handling and the coarse block-cut/degree signature are not defined. |
| Clustering/partitioning | Transitive unions, no cross-split signature reuse | A long chain of near-neighbor graphs can merge a large population; allocation/rejection order can bias the sample. |
| Start/goal and dynamics | Distances12–40, two schedules | Start/goal sampling and exact event distributions remain open; these affect task difficulty. |
| Historical exclusion | No historical topology matches | Previously stored layout hashes are not canonical abstract-topology certificates. A wall-array hash alone cannot prove no isomorphism. |

Different seeds, mirror images, corridor-length changes and moved goals do not
establish topological independence. Conversely, equal unweighted abstract graphs
can have different metric/visibility difficulty. Both the graph invariant and
its limits must be declared. No truthful rejection rate or independent cluster
count can be computed without an actual sampler and extraction rule.

## Exact alternatives for review, not implemented

These are **new alternatives**, not claimed completions of the original four
generators. Choosing either changes the target population and needs approval.

### T1: graph-only pilot to settle canonicalization

Sample n uniformly from {16,20,24}. For each unordered vertex pair independently
include an edge with probability .12; reject unless the simple graph is connected,
planar and has maximum degree4. Use seed namespaces from v0.1, one lineage root
per accepted base draw. Enumerate exact unlabeled graph isomorphism classes;
contract maximal degree2 paths, recording a pure-cycle component as a special
cycle object and preserving self-loops/parallel-edge multiplicities. Near keys
are the exact certificates of the original and every graph obtainable by one
edge contraction or one leaf deletion followed by contraction. Union two records
when their near-key sets intersect; compute transitive components. Canonical
labeling must be exact, not only Weisfeiler–Lehman hashing.

Partition entire components in fixed seed order, balanced by n, before outcomes.
Stop after10,000 attempts per n if targets cannot be filled. This is an exact
abstract-graph audit proposal, but supplies **no navigation layouts** and does
not retain four generator mechanisms. Orthogonal embedding/rasterization still
requires a separately reviewed specification. It is useful for discovering
whether the proposed near-equivalence collapses nearly everything, not for
claiming the original environment plan is ready.

### T2: fully specified lattice-layout alternative

Use a25x25 raster, all cells initially occupied. Candidate coarse nodes are
`(2+2i,2+2j)` for i,j=0,...,10. Independently retain each horizontal/vertical
neighbor edge with probability .60. Reject unless the resulting graph on all
121 nodes is connected and has at least one cycle. Free every coarse node and
each retained edge midpoint; leave other cells occupied. No clipping, room
expansion, diagonal connectivity or undocumented repair is allowed. This yields
one-cell corridors with a known exact coarse graph. Use row-major edge order and
one draw per seed; rejected candidates consume their seed.

Sample ordered distinct start/goal coarse nodes uniformly from all pairs meeting
graph-raster distance12–40 and Manhattan distance>=5; reject a candidate if there
is no eligible pair. Pair selection does not change its topology cluster. The
Manhattan constraint is an explicit new option to guarantee the initial one-call
assay's eligibility, not an existing v0.1 rule.

For this alternative use full raster free-cell adjacency (four neighbors), then
maximal degree2-path contraction with the multigraph convention above; no vague
'junction merging'. Apply T1's near keys and lineage union. A tentative coarse
signature is the sorted multiset of (block vertex count, block edge count,
articulation incidence degree), together with the degree histogram and cycle
rank. Its cross-partition reuse is rejected, even for nonisomorphic graphs.
State this conservative signature explicitly rather than choosing one after
inspecting acceptance. Exact signature identity is not statistical dependence.

T2 is implementable as an artifact-only generator after review. It provides only
one narrow lattice-corridor population, may fail connectivity/rejection budgets,
and cannot replace four independently defined generators while retaining their
generalization claim. Varying .60 to make four labels would be parameter strata,
not four unrelated topology mechanisms. **Recommendation: do not silently adopt
T2 merely because it is easy to code.** Obtain four complete generator definitions
or explicitly approve a narrower pilot with appropriately limited claims.

## Required future audit artifacts and ordering

After generator review, the audit must precede final preregistration and policies:

1. Freeze generator specifications, extraction rules, seed ranges, exact graph
   canonicalization dependency/version and exclusion/near-equivalence rules.
2. Obtain historical abstract certificates by read-only processing of already
   stored public artifacts, not rerunning worlds. If a historical layout cannot
   be certified, record it as an exclusion uncertainty and stop the strong
   independence claim. Do not access reserved historical held-out worlds to fill
   that gap without a separately reviewed non-experimental plan.
3. Generate development/assessment candidates artifact-only in their new ranges;
   allocate accepted complete lineage components once, before any policy result.
   Never repair a rejected graph based on navigation performance.
4. Have a separate curator audit/seal final held-out candidate artifacts, exposing
   only commitments, counts and exclusions. This phase did not generate them.
5. Report attempted, invalid, isomorphic, near-related, historical-match and
   accepted counts, both by mechanism and partition; retain rejection reason
   priority so categories do not double count. Publish all component sizes and
   descriptor distributions. Audit canonicalization on manually equivalent and
   non-equivalent graphs, multigraphs, pure cycles and transformed rasters.
6. Count independent components, not seeds or two dynamics schedules. If a union
   crosses partitions, reject/reallocate before lock; do not call it independent.
   Meet the accepted-cluster and proposal-limit criteria without relaxation.

## Current inventory and limits

| Quantity | Current verified status |
| --- | --- |
| Generated candidates / accepted layouts | 0 / 0 |
| Audited independent clusters in any new partition/mechanism | Not established |
| Rejection and isomorphism rates | Not estimable; no generator executed |
| Historical topology exclusion | Required, not newly certified |
| Held-out outcome access | None |

Independent graph draws plus lineage handling support a statistical sampling
argument; canonical uniqueness alone does not prove independence. Near-signature
rejection changes the population and may induce dependence between accepted
records. Future inference should state it conditions on that sampling design,
and audit overlap without pretending all graphs in nature were sampled uniformly.
This blocker is documented rather than bypassed. Stop for generator review.
