# Phase 1.5A-2 topology and dynamics specification

2026-11-07, proposal v0.2. These are **recommended exact sampling rules for
review**, not implemented generators. No development, assessment or held-out
layout was generated in this phase. No independence audit has passed. Unlike
the family names in v0.1 and alternatives T1/T2, the four constructions below
specify the raster population, acceptance rules and common topology extraction.
They are explicit new scientific choices, not claims about an existing dataset.

## 1. Common domain and sampling contract

Use25x25 cells with coordinates0,...,24, four-neighbor free-space connectivity,
and an occupied outer ring. Every raster begins occupied unless specified.
Base static geometry must have one connected free component, at least80 free
cells, occupied fraction between .15 and .85 inclusive over625 cells, and at
least one valid ordered start/goal pair. These broad density limits exclude
degenerate empty/full maps, not optimize success. No diagonal traversability.

Eligible start/goal pairs are distinct free cells with base-grid shortest-path
distance12–40 inclusive and Manhattan distance>=5. Sample uniformly from all
eligible ordered pairs in row-major pair order. Reject a base candidate if none
exists. Start and goal remain free under all events, a public domain guarantee.
No other true wall, topology, route or event label is exposed to policies.
Shortest paths used here are evaluator-only geometry validity checks, not agent
inputs or policy outcomes. No choice depends on a simulated navigation trajectory.

Independent graph/raster, start/goal and two dynamics streams are keyed separately.
All Bernoulli draws have the probabilities below; 'uniform' means discrete
uniform over the stated ordered set. Random edge ordering is a uniform permutation,
not an assertion of a uniform spanning-tree distribution. All tie orders are
lexicographic(y,x), then endpoints, unless stated otherwise.

Each candidate consumes its seed whether accepted or rejected. At most10,000
base candidates per mechanism/partition; impossible target counts stop review,
without repairs, looser signatures or performance-selected regeneration. Geometry
validity/exclusion is checked before start/goal selection and dynamics. A dynamics
failure has its own budget below and never draws a different outcome category
to make a difficult candidate disappear.

## 2. Mechanism R: room graph with narrow doors

Put wall lines at x,y in {0,6,12,18,24}. Free the16 room interiors
`{6i+1,...,6i+5} x {6j+1,...,6j+5}` for i,j=0,...,3. The candidate room graph
is the4x4 lattice with24 horizontal/vertical neighboring-room edges.

Draw a uniform permutation of these24 edges. Kruskal's cycle test selects a
spanning tree of15 edges; add each remaining edge independently with probability
.30. For each selected shared wall, open one cell with its along-wall coordinate
uniform in that room span's five interior coordinates. Do not open junction
corners, widen doors or add obstacles inside rooms. Uniform edge ordering plus
Kruskal is the specified distribution; it is not uniform over spanning trees.

This intentionally controls room size while varying branch/loop topology and
door visibility. It retains a lattice embedding bias; topology audit, not different
door coordinates, determines independent clusters. One accepted base graph is
one lineage root, never16 independent room examples.

## 3. Mechanism B: recursive partition rooms

Free the interior rectangle[1,23]x[1,23]. Draw desired leaf count uniformly from
{12,16,20}. Maintain inclusive leaf rectangles. Until that count is reached,
choose a uniformly random splittable leaf. An axis is eligible if its coordinate
span contains a wall coordinate c in `[min+3,max-3]`; choose uniformly among
eligible axes and then among its eligible integer wall coordinates. This leaves
both children at least three cells wide on the split axis.

Mark that full vertical/horizontal line across the leaf occupied, except for
one door cell selected uniformly along its orthogonal inclusive span. Replace
the leaf by the two rectangles excluding the wall line. Leaves are ordered by
their coordinate tuples before every random index selection. If none can split
before reaching the desired count, reject the candidate. Child walls may make
an ancestor door ineffective; the common connectivity check rejects that case,
not a repair routine. No late door widening or wall deletion is allowed.

The generator samples a partition process, not uniform floorplans or arbitrary
graphs. Common extraction below determines topology independently of the BSP
tree, so different partition histories of one topology are not independent data.

## 4. Mechanism V: irregular discrete Voronoi rooms

Draw n uniformly from {12,16,20}. Select n interior seed cells uniformly without
replacement; reject the candidate unless every pair has Manhattan distance>=4.
Assign each interior cell to its closest seed by Manhattan distance, ties to the
seed with smallest(y,x). Require each resulting region to be four-connected.

For each region, its core consists of cells whose four neighbors are all interior
and assigned to the same region. Require each core nonempty, four-connected and
containing at least one2x2 square; otherwise reject. Free the cores, leaving all
region boundaries occupied initially. Form the region adjacency graph from
neighboring cells with different original region labels; it must be connected.

On that adjacency graph select a random-order Kruskal spanning tree, then each
unused edge independently with probability .25. For each selected pair of
regions, find a shortest four-neighbor path joining their cores while staying
inside the union of the two regions. Among equal paths choose the lexicographically
first coordinate sequence; multi-source BFS initializes core cells in row-major
order and expands north,east,south,west. Free all cells on this path, width1.

Verify the carved corridor network does not create unintended room adjacencies:
remove all core cells from the free raster, find each remaining free component,
and connect every pair of distinct cores adjacent to that component. Also include
direct core-to-core free adjacency. This resulting simple graph must equal the
selected region graph; otherwise reject the candidate. No shortest path may
borrow a third room to avoid rejection. Apply common raster validity afterwards.

This gives an exact discrete irregular-room sampler, not a Euclidean Voronoi
claim. Pair-distance/core/corridor constraints may cause high rejection. Their
feasibility is unknown until a later artifact-only audit; do not relax them based
on performance or pretend the desired cluster counts already exist.

## 5. Mechanism M: maze with chords

Use121 coarse nodes `(2+2i,2+2j)` for i,j=0,...,10, with220 lattice neighbor
edges. Select a spanning tree by uniformly permuting edges and applying Kruskal;
include each of the100 unused edges independently with probability .15. Free
every coarse node and midpoint of every selected edge. Other cells remain walls;
no room expansion, diagonal join or arbitrary chord tunneling. Apply common
validity and pair selection. A chord changes the graph; subdividing a corridor
or moving its endpoint along the same corridor does not create independence.

Compared with R, M has fine one-cell passage structure; compared with B it has
edge-sampled maze loops; V changes geometry via irregular region boundaries.
These are four different construction processes, but they can still produce
related topologies. Mechanism names do not override common isomorphism rejection.
No claim of independent real-world scenario families follows from the labels.

## 6. Dynamics: two independent schedules per base geometry

For each schedule draw one category with probabilities .20 each: no change,
persistent addition, persistent removal, coordinated swap, moving occupancy.
These are mixture probabilities, not an exact20% quota within every small split.
All random choices are independent of policy trajectory and observation requests.
Only the start/goal and geometry validity constraints below condition acceptance.

For addition/removal/swap, draw onset tau uniformly from integers2,...,12 and
footprint length l uniformly from {2,3,4}. A footprint is a simple cardinal path
of l base-free cells excluding start/goal: choose first cell uniformly, then each
unused eligible neighbor uniformly, with north/east/south/west ordering. A dead
end rejects this footprint proposal. This is a sequential path distribution,
not uniform over all simple paths. For swap draw two disjoint such footprints.

- **No change:** no objects or moving occupancy beyond static base geometry.
- **Addition:** no initial object; occupy all footprint cells from tau onward.
- **Removal:** initially occupy the footprint; remove it at tau.
- **Swap:** initially occupy F; simultaneously remove F and occupy disjoint G
  at tau, each of length l. This is a multi-cell joint change, not a semantic
  class supplied to the agent.

Require start/goal connectivity in the initial and final static occupancies;
all footprint cells must be base-free. Do not require a fixed route to remain
valid or reject by an agent's eventual success. Retry at most128 geometry/event
proposals within the already drawn category; on exhaustion stop manifest
construction for review, not redraw a convenient category or quietly replace
the base topology. Record every attempt and constraint failure.

For **moving occupancy**, choose path length uniformly from {4,6,8}; sample a
simple base-free path by the same growth rule, excluding start/goal. Draw its
direction by a fair reversal coin. Traverse endpoints back and forth. Initial
dwell is uniform{2,3,4}; subsequent dwells are independently uniform{2,3,4,5,6}.
At each dwell's end advance one path cell, reversing direction at endpoints.
Expand positions for times0,...,80 before any policy is run. Occupancy is one
cell at any time; no person identity is given to agents. Apply the128-proposal
limit; permanent geometry must remain connected as already required, but a
mover can temporarily block a passage. This is a finite nonconstant-dwell
schedule, not a learned pedestrian-motion model.

Initial and final static checks ignore the transient mover, and do not assert
every robot can finish contact-free. A movement-induced entry is scored by the
same evaluator semantics for every method. Off-route events arise naturally;
do not select a 'relevant' footprint by consulting an agent's future route.
The onset range deliberately permits changes during the four-decision timing
assay while spreading others later. It does not guarantee every assay contains
a change or reveal change times to a policy.

## 7. Common canonical topology and lineage

Define a **single raster-derived corridor/room quotient**, applicable across all
four generators, not their private construction labels:

1. Start with the undirected four-neighbor free-cell graph of base geometry.
2. Mark cells participating in at least one fully free2x2 square. Find four-
   connected components of marked cells and contract each to a room-region node.
   Unmarked free cells remain nodes. Delete internal loops and duplicate edges
   introduced by this room contraction only; the quotient here is a simple graph.
3. Suppress maximal degree2 paths; preserve parallel corridor edges and self-loops
   created by this suppression as multigraph edges. Repeatedly handle a degree2
   vertex incident to a loop as a pure-cycle component. A whole degree2 connected
   component has the single special certificate CYCLE, independent of length.
   A one-node quotient has certificate SINGLE; a single corridor has two endpoints.
4. Compute an exact unlabeled multigraph certificate, ignoring room/cell origin,
   coordinates, corridor length and start/goal. Formally minimize the serialized
   loop counts/upper-triangular edge-multiplicity matrix over all vertex labels.
   An exact canonical-labeling implementation can optimize this definition;
   hash/WL summaries alone are never an isomorphism proof.

Also retain orientation/reflection-canonical raster bitmaps, raw free-cell graph
certificates and construction lineage IDs. Room contraction intentionally ignores
some metric/visibility structure and may merge open-space distinctions. It is
a declared conservative audit invariant, not a claim of a unique natural
navigation topology. Thin gaps and two-cell doorways must have golden audit
fixtures before generator use. Variants of one root (raster transforms, changed
goals, event schedules, edge-length perturbations) share a cluster regardless
of exact certificates.

Near-equivalence keys: the normalized graph's own certificate and every certificate
obtained by deleting one leaf or contracting one non-loop edge, followed by the
same degree2 suppression. When two candidates' key sets intersect, union them;
take full transitive closure with common lineage and exact raster/isomorphism
matches. Loops/multiplicities are preserved after edge contraction; contracting
a loop is prohibited. Reject any candidate related to a stored historical base
under the same rules. Dynamic schedules never create new independent samples.

**Explicit amendment:** coarse degree/block-cut/cycle summaries are diagnostic
prefilters, not automatic cross-split exclusions. Identical summaries of
nonisomorphic graphs are not sufficient evidence of shared lineage. v0.1's
unspecified coarse-signature exclusion is replaced by the exact/near rules above.
This change is proposed before layouts or results exist, not relaxed after a
failed audit. Publish both coarse collisions and exact/near matches.

## 8. Partitions and outcome-blind rejection

Retain development48 fit/24 calibration/24 selection clusters and assessment160
(40 per mechanism). Propose final held-out96 with24 per these same four mechanisms;
defer the original two additional unimplemented held-out mechanisms and any
unseen-generator generalization claim. This is an explicit scope amendment;
no held-out layouts/outcomes are generated or accessed now.

Use fit50,000,000–50,099,999; calibration50,100,000–50,199,999;
selection50,200,000–50,299,999; assessment60,000,000–60,999,999;
reserved final70,000,000–70,999,999. Within each range, reserve consecutive
10,000-seed blocks for R,B,V,M in that order. Derive all substreams from the
seed plus purpose; never give those seeds/partition IDs to the policy.

Before any policy run, an artifact-only audit processes the fixed candidate
order and unions within each proposed split. If a candidate connects to any
previously accepted other-split/historical component, reject it; do not merge
cross-split records and keep claiming independence. Accepted cluster counts are
counts after transitive closure, with one base representative per component.
New same-split near matches join its existing lineage and do not fill another
slot. Freeze accepted components before moving to the next split; later proposed
cross-split bridges are rejected with their complete relation evidence. This
order changes the conditional sample population and must be reported.

The historical comparison must use already stored rasters/certificates, never
re-execute Phase 1.4 or open reserved old held-out worlds. Missing historical
metadata blocks a strong no-overlap assertion; review a non-experimental
exclusion solution rather than silently omitting it. A separate curator can
audit/seal final-held-out artifacts later, exposing only commitments/counts.

Rejection priority: malformed sampler output, connectivity/density, topology/
historical relation, no eligible start/goal, dynamic validity failure. Preserve
all raw reason flags but count first reason for exclusive rate summaries. Report
attempts, accepted independent components, exact/near/coarse collisions and
lineage sizes by mechanism/split. No rejection uses success, policy contact,
score, observation count or future trajectory. Canonical nonidentity and this
rejection design do not prove iid sampling; uncertainty estimates are conditional
on this constructed population and clustering rules.

## Review status

All four mechanisms now have precise proposed distributions. Their actual
acceptance, diversity, cross-split separation and feasibility remain **unmeasured**.
Unknown acceptance is a testable gate, not permission to invent fallback defaults.
Review the room quotient, Voronoi constraints, onset mixture, fixed25x25 scale
and narrowed held-out population before implementation. Then authorize artifact-
only generator/audit work separately. This phase generates no layouts and stops
for scientific review.
