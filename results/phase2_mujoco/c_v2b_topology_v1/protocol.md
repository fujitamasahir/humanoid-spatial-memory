# C v2.0b Topology-aware Candidate Selection Protocol

**Frozen before formal fixtures are executed:** 2026-11-14  
**Status:** mechanism hypothesis only; no FIT data will be accessed unless the
mechanism gate below passes.

## Hypothesis and scope

Public-map global connectivity can rank uncertain, already-visible cells more
usefully than the original route-proximity shortlist at the same K=3 planning
budget. This is a new method, not a retuning of C-Route3. C0, C-K, and
C-Route3 remain unchanged. B, B+C, RDAO, Event, the sensor, planner, shield,
memory, probability model, and observation cap are frozen.

The online input is only the ternary memory grid, public occupancy
probabilities, start/current cell, goal, configured unknown-cell mode, and the
existing predicted visible-cell set. Candidate eligibility remains the exact
existing visibility and `.05 < q < .95` rule. No candidate or source/goal is
filtered by hidden data.

## Graph and topology computation

The graph has one vertex per cell traversable under the public grid and
configured unknown-cell policy, and an undirected edge between cardinally
adjacent vertices, matching `navigation.plan`. A single deterministic
Tarjan DFS from the current cell computes discovery/low links, articulation
vertices, bridges, and vertex-biconnected edge blocks in O(V+E). The DFS tree
and low links identify whether deleting an articulation vertex separates the
current cell from the goal; articulation points in irrelevant branches are
not promoted. A bridge-tree path marks bridge bottlenecks relevant to the
current-goal component pair. Biconnected blocks indicate alternate-cycle
structure; membership in a terminal block with multiple routes is recorded as
an alternate-route feature, not treated as proof that every cell in the block
is critical.

Remembered occupied candidates are absent from that graph, so articulation
analysis cannot rank them. For all eligible occupied candidates together, one
multi-source distance computation from the current cell and one from the goal
over the public graph provide neighbor distances. A candidate is a possible
connectivity shortcut if its traversable neighbors touch distinct current
components containing start and goal; it is a distance shortcut if clearing
it yields a shorter public path by the neighbor-distance lower bound. These
are public hypothetical features only. They do not call the MuJoCo shield and
do not inspect hidden occupancy. This bounded batch handles occupied cells
without one graph search per candidate.

## Frozen ranking

Candidates are ordered lexicographically by:

1. structural class: (a) traversable start-goal separating articulation or
   uncertain goal terminal (occupied or traversable), (b) occupied-cell connector/distance shortcut,
   (c) endpoint of a start-goal-separating bridge, (d) other traversable
   articulation on the nominal public route, (e) nominal-route cell in a
   cyclic biconnected block with an alternate route, (f) other eligible cell;
2. structural severity: number of start-goal-separating structures implicated
   (descending), then shorter connector path gain (descending);
3. occupancy uncertainty `q(1-q)` (descending);
4. cell coordinate `(y,x)` (ascending).

The class order is frozen as stated. It does not use weighted sums or values
learned from fixture outcomes. The ranked first three are evaluated by the
unchanged single-cell V/D equations; maximum calls remain 1 nominal plus 2 per
candidate, i.e. seven. Scan cost still charges all calls under the frozen
formula. Graph time is additional and is measured separately.

## Formal synthetic fixture set and exhaustive reference

Ten hand-specified public-memory fixtures cover: (1) a unique start-goal
articulation; (2) an irrelevant dead-end articulation; (3) a narrow corridor
with an alternative loop; (4) multiple serial bottlenecks; (5) a loop-rich
graph without articulation points; (6) a remembered occupied cell whose
clearing creates a shortcut; (7) a route-critical cell outside C0's top
three; (8) correlated uncertain cells; (9) no beneficial scan; and (10) two
different start/goal pairs on the same graph. All candidate probabilities,
geometry, start/goal pairs, and expected structural annotations are fixed in
the fixture source before the formal run.

For mechanism analysis only, an exhaustive offline reference evaluates V/D
for every eligible candidate using the same public map and exact existing
counterfactual planner. This is never called online. Its common comparison
cost uses seven A* calls, so `D > .5 + .01*7 + .5/remaining` is comparable
across arms. We report (a) recall of all tied exhaustive maximum-D candidates
at K=3, (b) recall of candidates individually exceeding that common cost,
(c) selected-best-D regret against the exhaustive maximum, (d) agreement of
the exhaustive common-cost decision, (e) each policy's actual authorization
using its own charged calls, (f) false-positive scan authorizations in the
predefined no-benefit fixture, and (g) exact graph workload/runtime,
counterfactual A* calls, and scheduler elapsed time.

Topology identification (correct classification of fixture-annotated
separators/connectors) is reported separately from useful-EVI candidate
recall. Fixture annotations are diagnostic labels, not policy inputs.

## Frozen gate

Proceed to any FIT fixed-state replay only if all conditions hold:

* C-Topology3 improves average K=3 recall of the exhaustive common-cost useful
  candidate set by at least 0.10 absolute over C0, and is not worse on
  exhaustive maximum-D candidate recall;
* its common-cost scan-decision agreement with the exhaustive reference is
  correct on at least 2 fixtures where C0 is incorrect, and it has no
  false-positive authorization on the no-benefit fixture;
* it respects seven A* calls on every fixture and its graph work is at most
  20*(V+E) counted primitive visits per decision;
* graph analysis p95 is at most 5 ms over 100 repeated fixture computations
  on the recorded machine, with machine and interpreter recorded.

All criteria are conjunctive and frozen. Failure archives the negative result
and stops all new causal replay and FIT72 evaluation. No fixture, score, or
threshold may be changed after viewing formal results. A failed result may
motivate a separately documented future development iteration, but not a
silent repair.

## Complexity, assumptions, limits

Tarjan articulation/bridge/block decomposition and graph traversals are
O(V+E); memory is O(V+E). The EVI counterfactual work remains at most seven
existing A* calls. The method assumes a static undirected four-neighbor cell
graph and does not model G1 footprint, heading, dynamic occupancy, observation
timing, or correlated occupancy probabilities. Biconnectivity is a structural
proxy, not a calibrated probability of route failure. Candidate values remain
the original approximate one-cell V/D, not physical scan effects.

## Integrity and next-stage gate

The formal fixture runner must not import FIT stores, world generators, or
ground-truth environment payloads. If the mechanism gate passes, a separate
protocol and parity review is required before limited causal replays; FIT72
remains descriptive and non-independent. The lineage-separated independent
cohort proposal remains unapproved and unexecuted. Independent evaluation
requires the joint sensing-cost and navigation-cost benefit together with
preserved completion and safety.
