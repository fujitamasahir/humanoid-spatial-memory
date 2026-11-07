# Phase 1.5 B′ generator specification

Version **phase1.5-v0.4-BPRIME-1**, 2026-11-07. Documentation preregistration
only. Baseline: `0c0f7d7b5fa394d5ec981ec7301b1987c4658ac5`.
Implementation, sampling, artifact audits and navigation are not authorized.
The [amendment](phase1_5_bprime_protocol_amendment.md) contains the single
normative execution table and exclusion policy; the
[validation plan](phase1_5_bprime_validation_plan.md) defines future gates.

## 1. Population and immutable evidence

B′ (machine label `BP`) replaces B in a new R/BP/V/M population. It samples
rectangular indoor partitions with connected subsets of adjacent-room links.
It is not uniform over partitions, floorplans, spanning trees, connected graphs
or final audit components. R/V/M construction distributions remain unchanged,
but their realizations use the fresh population namespace. No old quota credits
are carried forward. The failed B-02 audit remains immutable: 38/48 final fit
components, R=12, B=2, V=12, M=12; calibration/selection unstarted.
This document does not retrospectively repair that audit.

## 2. Partition distribution

Use 25×25 cells `(x,y)`, coordinates 0 through 24, four-neighbor connectivity,
and an occupied outer ring. Start occupied. Macro coordinates `(i,j)` range
from 0 through 5. Each macro-cell has core
`[4i+1,4i+3] × [4j+1,4j+3]`.

On the partition stream choose N uniformly from the ordered list `[12,16,20]`.
Start with inclusive macro rectangle `(0,0,5,5)`. Until there are N leaves:

1. Sort splittable leaves by numeric tuple `(x0,y0,x1,y1)` and choose uniformly.
   A leaf is splittable when either macro dimension is at least two.
2. Choose uniformly among eligible axes in order `[x,y]`.
3. For x choose c uniformly from increasing integers `x0+1,...,x1`, replacing
   the leaf by `(x0,y0,c-1,y1)` and `(c,y0,x1,y1)`. For y use the analogous rule.

No doors are placed during splitting. No partition restart is allowed. Before
36 leaves, some leaf is nonunit and splittable; N≤20 cannot exhaust this rule.
Final rectangle `(a,b,c,d)` becomes the completely free raster rectangle
`[4a+1,4c+3] × [4b+1,4d+3]`. Everything else initially remains occupied.
Each room is at least 3×3. Assign room IDs from zero in sorted final rectangle
order. This rectangle ordering explicitly overrides the inherited general
row-major convention; cell ordering elsewhere remains `(y,x)`.

## 3. Connection graph distribution

The simple graph H has one vertex per final room. An edge exists exactly when
two macro rectangles share a positive-length side, not just a corner. Multiple
shared boundary segments give one edge. Represent endpoints as `(min ID,max ID)`
and sort these pairs numerically. H is connected: it is obtained by contracting
connected rectangular blocks in the connected 6×6 macro-cell grid and simplifying.

On the tree stream uniformly permute the complete sorted edge list and apply
Kruskal's cycle test, retaining each edge joining separate components. Process
the whole permutation. The result T is a spanning tree. This random-edge-order
law is not a uniform spanning-tree assertion.

Let U be the sorted unused edges and r=|U|=|E(H)|-N+1. On the chords stream draw
K uniformly from increasing integers 0,...,r; then uniformly permute the complete
U and take its first K edges A, even when K=0. Select G=T∪A. Conditional on T,
`P(A | T)=1/((r+1) binomial(r,|A|))`. Do not reject a selected graph based on
its descriptor, apparent novelty, density or anticipated policy behavior.

## 4. Doors, connectivity and extraction

Process selected edges in sorted endpoint order on the doors stream. For rooms
separated by vertical wall x=4c, list common macro rows j increasingly and choose
uniformly one door `(4c,4j+2)`. For horizontal wall y=4c use common macro columns
i increasingly and door `(4i+2,4c)`. Open exactly that cell. Do not widen doors,
open unselected links, tunnel, insert obstacles or repair geometry.

A door's two opposite neighbors are in its designated rooms; its other two
neighbors remain occupied. Doors are separated and never at wall junctions.
G contains T, so its raster is connected by construction. At least 36×9=324
core cells remain free, and the outer ring has 96 occupied cells. Thus free
count≥80 and occupied fraction lies between 96/625 and 301/625, within the
inherited inclusive [.15,.85] requirement. Failed assertions are defects that
stop execution, not ordinary rejections to resample away.

All room cells participate in free 2×2 squares; doors do not. The approved
extractor therefore finds exactly N marked room components, with one degree-two
unmarked node per door. Before suppression its quotient is a subdivision of G;
after suppression it is the approved normalized multigraph of G. Construction
room count, selected graph vertex count and normalized vertex count must be
logged separately. Degree-two rooms may disappear; loops/multiplicities remain.
No independent evidence is claimed until implementation validation passes.

## 5. Pairs and dynamics

Use separate start-goal and dynamics-0/dynamics-1 streams. For an unmatched valid
geometry enumerate free starts by `(y,x)`, then free goals by `(y,x)`. Eligible
ordered pairs have base shortest-path distance 12–40 inclusive and Manhattan
distance≥5. Choose uniformly from this list. If empty, reject the candidate
without inserting it in the relation index. Connectivity alone is not assumed
to prove pair eligibility. Start and goal remain free under all schedules.

The complete dynamics law and draw order are the unchanged baseline
`src/spatial_memory/phase15_generators.py::dynamic_schedule` and `grow_path`,
with `retry_rule='fixed'`, under the new stream prefix:

- Choose category uniformly in order `[none,addition,removal,swap,moving]`.
  None consumes no further schedule draws and has no initial objects/events.
- For addition/removal/swap draw onset uniformly in 2,...,12, then length uniformly
  in `[2,3,4]`, once. Moving instead draws length once from `[4,6,8]`, no onset.
- Propose at most 128 footprints in that category, keeping length/onset fixed.
  Choose first cell uniformly from row-major base-free cells excluding protected
  start/goal. Grow a simple path by uniform unused eligible cardinal neighbors
  ordered north/east/south/west. A dead end rejects that proposal. Swap draws a
  second path excluding the first path as well as protected cells; retry both
  on proposal failure. No category redraw, pair replacement or geometry repair.
- Addition occupies F at onset; removal initially occupies F and removes it;
  swap initially occupies F, then removes F and occupies disjoint G simultaneously.
  Check start-goal connectivity in initial and final static occupancies.
- Moving occupancy ignores transient occupancy in those static checks. After a
  valid path, reverse it with probability 1/2, traverse endpoints back and forth,
  using first dwell uniform `[2,3,4]`, later dwells uniform `[2,3,4,5,6]`. Append
  complete dwells until at least 81 positions exist; retain positions 0,...,80.
  Consume the last full dwell draw even if its positions are truncated.
- Preserve every proposal failure. Exhaustion stops manifest construction; it
  does not consume a replacement candidate to hide the failure.

No rule consults agent outcomes, future trajectories, observation requests or
navigation difficulty. Relation-only records do not receive extra pairs or
schedules. Truth, seeds, mechanisms, partition IDs, geometry and events stay
with the evaluator; the inherited public projection remains unchanged.

## 6. Lineage

One root is one complete base-geometry draw: final partition, selected graph and
placed doors. A fresh independent draw has identity
`phase1.5-v0.4-BPRIME-1:<partition>:<mechanism>:<seed>`; this is provenance, not a
new equivalence criterion. Deliberate geometry variants, transformations,
changed pairs and schedules inherit the actual source root, including across
versions/mechanism labels. New seeds or labels never erase genuine derivation.
If several roots contribute to a derivative, retain all ancestral root links
and union their lineage components. No such derivative generation is prescribed
by this sampler; it is not a way to fill quotas. Independent draws accidentally
sharing a partition are not declared derivatives merely by partition equality;
all exact/near/raster comparisons still apply. Freeze ancestry before admission.

Common lineage may join different cycle ranks. It must not be ignored to retain
rank-separated credits. The new root namespace cannot launder old variants.

## 7. Diversity argument and finite-budget uncertainty

For a finite multigraph use β=E−V+c, counting loops once. Exact isomorphism
preserves β. Deleting a degree-one vertex removes one edge/vertex; contracting
one nonloop edge removes one edge/vertex, retaining residual parallel edges as
loops. Degree-two suppression likewise removes one net edge/vertex. Component
count stays fixed. A pure cycle represented by one loop retains β=1; SINGLE
has β=0. Thus each approved near key has its normalized graph's β; intersecting
near sets and near-only transitive chains preserve it. Room contraction from
raw cells need not preserve β. Common-lineage unions can cross β values.

Conditional on a partition, β(G)=K is uniform on 0,...,r. A reachable 4×5 room
partition (macro widths 1,1,2,2 and heights 1,1,1,1,2) has 20 rooms, 31 adjacency
edges and r=12. This proves positive support for selected ranks 0–12, not thirteen
independent components or useful frequencies. Lineage, exact/near compression,
historical exclusion and ordered admission remain authoritative.

For exact partition probabilities let μ1 put mass one on the initial rectangle.
For partitions P,Q of consecutive leaf counts, let a(P) be eligible leaf count,
b(R) eligible axis count, and d_s the selected axis's macro length for split s:

`μ(t+1)(Q) = ΣP μt(P) Σ{s:P→Q} 1/[a(P) b(Rs) (ds−1)]`.

Sum over all histories; final partitions are not equiprobable. For N∈{12,16,20},
`pN(r)=Σ{|P|=N} μN(P) 1{|E(H_P)|−N+1=r}`. H is a simple planar minor of the
6×6 grid, so `0≤r≤min(25,2N−5)` (bounds, not full support claims). Mixing the
three N values equally gives P(r), and the marginal rank probability is
`qk=Σ{r≥k} P(r)/(r+1)`. Hence `qk−q(k+1)=P(r=k)/(k+1)≥0`: marginal ranks favor
lower values, despite conditional uniformity. In particular q0≥1/26.
`E[K|P]=r/2`, `Var(K|P)=r(r+2)/12`.

No numerical partition recurrence or quota-success probability has been
established. Positive support does not prove adequate frequency in 10,000 draws;
raw rank frequencies would not predict history-dependent final credits anyway.
The mechanism removes a known connectivity failure and introduces graph-level
cycle/connection variation, but same-rank merging, finite support, lattice bias,
exclusions and dynamics limits can still defeat quotas. Retained N need not be
uniform after filtering. No success, iid independence, assessment feasibility,
navigation benefit, novelty or physical safety claim follows from this design.
