# Phase 1.5B-0.1 canonicalization review

2026-11-07; base `2ed8393b715ffc66036258678fda0e1f98155e41`, branch
`feature/phase1-4c-assessment`. **The frozen literal certificate remains blocked.
An exact, substantially faster alternative is demonstrated, but its different
representation is proposed for review, not adopted.** No new artifact audit ran.

Reviewed the [generator validation](phase1_5b0_generator_validation.md),
[independence audit](phase1_5b0_topology_independence_audit.md),
[manifest review](phase1_5b0_development_manifest_review.md), and
[v0.2 specification](phase1_5a2_generator_specification.md). Original evidence,
samplers, old source and results remain unchanged. See the
[backend validation](phase1_5b01_exact_backend_validation.md) and
[development disposition](phase1_5b01_development_audit.md).

## Failure diagnosis

The preserved M matrix has 75 vertices, 89 nonloop adjacent pairs, no loops,
29 degree-one vertices, 35 degree-three vertices and 11 degree-four vertices.
The exact colored-incidence automorphism computation reports group order two
and 74 original-vertex orbits. Large symmetry is therefore **not** the principal
explanation for this instance. Automorphisms on the encoding correspond exactly
to original multigraph automorphisms under the proof below.

All loop counts tie initially. The literal next-row rule prefers leaves: each
has 73 zero entries followed by one unit edge. Thus 29 vertices tie before
true-twin pruning, even though almost all are globally inequivalent. The ordered
partition only refines by adjacency to already selected vertices. It deliberately
does not impose degree/equitable-refinement color order, which could exclude the
literal minimum. The search explores many tied possibilities before distinguishing
later rows. This is a verified structural weakness; no complete search tree was
enumerated, so its ultimate size is unknown.

The original saved audit failed after 17,540 nodes at five seconds. This task's
unprofiled replay failed after 16,853 nodes at 5.0004 seconds. A separate cProfile
run, with cache statistics added to an in-memory copy of the old function, recorded
5,168 misses, 255 hits and 5,128 retained completed entries at its five-second
stop. The hit fraction is about 4.7% of accesses during that partial run. Labeled
partition memoization does not identify differently labeled isomorphic states.
Profiling slows execution; those node counts are not throughput comparisons.
Its largest own-time categories include search itself (1.59 seconds), the
true-twin comparison generator (0.86 seconds), and row construction (0.35 seconds).
Full compact details are in [diagnostics](../results/phase1_5b01/diagnostics.json).

The original backend fails on the **first self certificate**. Near operations
did not cause that original timeout: M would require 119 calls (self + 29 leaf
deletions + 89 edge contractions) if self succeeded. The proposed backend's
complete set has 80 distinct keys. R requires 18 calls/eight distinct keys.
Variant enumeration, suppression and deduplication add real overhead; total
near timing includes them rather than just native labeling.

The dense integer matrix occupies O(n²) entries. The literal certificate contains
1+n+n(n-1)/2 integers. Search can require factorially many labelings in the worst
case; per-state splitting, tuple construction and twin checking add polynomial
cost (the twin checks alone can be O(n³)). Unbounded memoization retains both
partitions and long suffix tuples; an O(V n²) storage upper bound for V cached
states explains potential memory growth. The measured M worker peak was about
145 MiB, versus 76 MiB for branch-and-bound; interpreter/import baseline is included.
These are measured process high-water marks, not isolated allocator measurements
or an asymptotic fit.

## Alternatives evaluated

| Approach | Exactness and feasibility finding |
| --- | --- |
| Existing literal search | Byte-correct on reference cases; M and synthetic cycle75 exceed five seconds. |
| Literal prefix branch-and-bound | New isolated implementation compares a partial serialization with a completed incumbent. A larger prefix cannot improve the incumbent, so pruning preserves the minimum. No change to loop ordering, row minimization or true-twin proof. Reference bytes agree; M still fails at 13,595 nodes/5.0005 seconds. R uses 141 nodes versus 178. No general improvement claim. |
| nauty through pynauty2.8.8.1 | Exact colored-incidence prototype; M self about0.0006 seconds, complete near set0.4816 seconds. Different canonical bytes; native search-node counts are not exposed. Benchmark-only proposal. |
| bliss / Traces | Established exact individualization/refinement alternatives; neither installed or benchmarked here. They do not promise this specification's lex-min bytes. No invented timing comparison. |
| Exhaustive permutations | Independent small-graph oracle, factorial cost; retained rather than used at75 vertices. |
| Pairwise exact isomorphism (e.g. VF2), decomposition, automorphism-assisted literal search | Mathematically possible alternatives. Pairwise checks need a complete near-variant relation index rather than simply reusable keys; decomposition must preserve attachment/loop information. Using exact stabilizer orbits can preserve literal bytes, but M's small group limits the obvious opportunity. Not implemented or benchmarked; effectiveness remains a hypothesis. |

No degree sequence, WL summary or hash is treated as an equality proof. Cryptographic
hashes are storage checksums only. The prototype is not wired into any generator,
manifest or admission path. The original production function remains unchanged.

## Proposed amendment v0.3-CANON-1 — pending scientific approval

Change **only the canonical representation**, replacing literal lex-min labeling
with a version-pinned exact colored-incidence canonical labeling. Keep the
original graph normalization and exact unlabeled multigraph equivalence, all near
operations, transitive lineage/raster union, partition exclusion, quotas, sampling
and candidate order unchanged. This is a proposal before adoption; the v0.2
specification and historical certificate files have not been edited.

For normalized multigraph G, construct a simple colored graph E(G):

1. One original vertex per vertex v, color `(0, loop_count(v))`.
2. For every unordered distinct pair {u,v} with positive multiplicity m, one edge
   vertex of color `(1,m)`, adjacent to u and v. Absent pairs have no edge vertex.
3. Color classes are ordered by the full numeric pair. No private mechanism,
   coordinate, seed, route or start/goal label is added.

An isomorphism of G extends to E(G) by mapping each pair's edge vertex to the
corresponding pair's vertex; loops and multiplicities preserve colors. Conversely,
a color-preserving isomorphism of E(G) must map original vertices to originals,
preserve loop colors, and map each edge vertex to the same-multiplicity edge
between its mapped endpoints. Its restriction is therefore an isomorphism of G.
Consequently G≅H iff E(G)≅E(H). There are no spurious permutations among duplicate
edge nodes because there is exactly one node per positive unordered pair.

Take nauty's canonical-position-to-original-vertex `lab` array, keep the original
vertices in that order, and serialize their actual loop counts and upper triangle
using the existing serializer. Call this C₃(G). It is a relabeling of G, and its
order is induced by a canonical E(G), so G≅H implies C₃(G)=C₃(H). Conversely equal
decoded matrices supply an explicit isomorphism. Thus

`C₂(G)=C₂(H) ⇔ G≅H ⇔ C₃(G)=C₃(H)`.

It follows pointwise that near-set intersections and their transitive closures
are unchanged when **all** compared graphs use C₃. Equality of C₂ and C₃ bytes is
neither asserted nor required by this proof. A three-vertex one-edge witness has
upper triangles `(0,0,1)` under C₂ and `(1,0,0)` under this prototype. There are
444 byte disagreements among 1,215 reference fixtures, with no relation disagreement.

Before adoption: approve this versioned change; pin backend build/options/encoding
and byte protocol; expose native search-node statistics to enforce the existing
100,000-node ceiling (or obtain a separately reviewed guard amendment). Wall-time
success alone does not establish that node ceiling. Freeze source and dependency
hashes, then regenerate comparison keys from stored matrices in a **new** namespace,
including historical keys, without editing old evidence or mixing C₂/C₃ keys.
Never merely rename old bytes. Preserve complete original candidate identities,
including failed M and rejected B/V, and run the guarded new audit only after all
gates pass. No guard increase or audit migration is adopted here.

## Primary sources and limits

[nauty/Traces](https://pallini.di.uniroma1.it/) describes canonical labeling and
automorphism computation; [its refinement trace description](https://pallini.di.uniroma1.it/TheTrace.html)
explains early refinement comparisons. The [pynauty source documentation](https://github.com/pdobsan/pynauty)
identifies its nauty2_8_8 backend; the tested package is2.8.8.1, not a claim about
the newest nauty release. [bliss's definitions](https://users.aalto.fi/~tjunttil/bliss/definitions.html)
state canonical-form equivalence and warn that forms depend on version/options.
These establish the comparison framework, not a proof that arbitrary native
bytes equal v0.2's objective. The encoding proof and measured fixture evidence
are this report's contributions. Larger exact instances, cross-platform byte
stability and future population feasibility remain unverified.
