# C v2.0c Corrected Topology Candidate Selection Protocol

**Frozen before policy outcomes:** this protocol, implementation, fixture source,
annotation validator, runner, and separate reviewer are committed together
before the formal screen. Formal screen directory:
`results/phase2_mujoco/c_v2c_topology_v1/`.

## Objective and scope

Establish production/reference correctness and a conformance-valid mechanism
screen for the existing topology-aware candidate-selection hypothesis. This
is not a new ranking heuristic and does not tune v2.0b weights. The invalid
v2.0b code, protocol, raw screen, and review remain immutable historical
evidence. C v2.0c is a separate implementation with one semantic correction:
an occupied-cell **connectivity** restoration requires distinct current public
components containing start and goal. When they are already connected, the
cell is a distance shortcut only if a public shortest path becomes strictly
shorter after opening it.

The online inputs are the current public ternary grid, probability map,
position, goal, heading, unknown-cell mode, and existing 61-ray public-memory
visibility estimate. Hidden occupancy, object identity, future schedules,
failure labels, successful trajectories, simulator state, and hypothetical
MuJoCo shield queries are prohibited. The original C, K=3, and K=5 controls
remain unchanged.

## Independent correctness reference

`spatial_memory.topology_reference.brute_force_topology_reference` constructs
its own cardinal graph and uses BFS. It does not import production Tarjan code
or share its component labels. Offline it recomputes connected components and
shortest distance after removing every vertex and edge, and after restoring
each nontraversable eligible cell. It identifies true articulation vertices,
start-goal separators, all bridges, terminal-relevant bridges, vertices on
cycles, connectivity-restoring cells, distance-only shortcuts, and no-benefit
cells. It handles terminal cells explicitly. Its O(VE)-or-higher work is
test/reference work only and is never used by the online policy.

Production C v2.0c (`topology_evi_c.py`) uses an iterative Tarjan DFS to avoid
recursion-depth limits. Discovery/finish intervals are computed in every
component, but a vertex is marked start-goal-separating only if the baseline
terminals are connected and the goal lies in the terminal-separating child
subtree of that vertex in the start-rooted DFS tree. Articulation points in
other components are not terminal separators. The bridge forest is contracted
and only bridge edges on the terminal-region path are relevant. Cycle blocks
identify alternate-route structure. Two terminal BFS distance maps are reused
for all occupied/unknown candidate shortcut checks; there is no path search
per candidate.

Unknown-cell policy follows the existing `navigation.plan` convention exactly:
optimistic includes `-1` cells; blocked excludes them. If the public nominal
route is empty, the topology analysis still evaluates components and potential
connectivity restoration without inventing a route. If `start == goal`, there
are no start-goal separating vertices. Goal terminals are handled whether
currently traversable, occupied, or unknown under blocked mode.

Production ranking retains v2.0b structural priority order wherever valid:

1. terminal or start-goal separating vertex;
2. nontraversable connectivity restoration or strict distance shortcut;
3. endpoint of a terminal-relevant bridge;
4. nonterminal route articulation;
5. nominal-route cell in a cyclic block (alternate-route cue);
6. other articulation, then other candidate.

Within each class, structural severity / distance gain descends, then
`q(1-q)` descends, then `(y,x)` ascends. A traversable or unknown/occupied goal
terminal is class 1. The only semantic amendment is to distinguish true
connectivity restoration from distance improvement and to apply terminal
classification consistently. Every candidate still must satisfy the original
visible-footprint and `.05 < q < .95` filter.

Candidate sorting is O(C log C); graph construction, iterative Tarjan,
component/bridge decomposition, and two BFS maps are O(V+E). The output counts
grid scans, adjacency probes, DFS edge visits, component and bridge visits,
biconnected edge visits, terminal tests, BFS visits, candidate-neighbor and
component-pair checks, route membership, and sort comparisons. Work units are
the sum of these counts plus V+E; the fixed acceptance bound is
`20*(V+E)`. Runtime includes graph analysis plus topology-feature ranking.

## Correctness acceptance before formal screening

Before any formal candidate outcome is observed:

* Run all `3^6 = 729` two-by-three ternary public grids, both unknown modes,
  and every valid ordered start-goal pair, including `start == goal`.
* Run 1,000 deterministic random 4-by-5 ternary public grids using seed
  `20261114`; compare each under both unknown modes. Each case checks all
  articulation points, terminal separators, bridges, relevant bridges,
  cyclic vertices, component equivalence, reachability, distance, every
  nontraversable-cell restoration label and gain, and production work bound.
* Include explicit long-corridor, disconnected-component, occupied connector,
  occupied distance shortcut, irrelevant articulation, blocked unknown,
  terminal, deterministic tie, candidate-eligibility, and original V/D/cost
  parity checks.

The correctness gate requires zero mismatches, all tests passing, and no
unexplained retained seeds. Any mismatch blocks formal screening. These are
small public synthetic grids, not admitted environments.

## Formal fixtures

The suite has 48 conditions: eight balanced families with six fixtures each.
In each family variant 0 is a manually specified anchor; variants 1-5 are
deterministically generated using seeds `2026111400 + 100*family_index +
variant`, on 17-by-17 ternary grids. Families are: (1) exactly one nonterminal
start-goal separator; (2) multiple serial separators; (3) irrelevant
articulation; (4) alternate loop around a candidate; (5) occupied cell
restoring connectivity; (6) occupied distance shortcut and occupied no-benefit
controls; (7) no-benefit scans and C0 controls; (8) a non-articulation
high-value target and three terminal pairs on one identical grid.

Before policy selection, an automatic independent-reference validator checks
all structural annotations, target visibility and probability eligibility,
separator counts, restoration semantics, and same-grid terminal-pair identity.
If any annotation is inconsistent, candidate policy evaluation aborts and the
screen is invalid. The offline exhaustive EVI reference then evaluates every
eligible candidate; the target expected to be the best non-articulation
candidate must actually be tied for maximum D. This reference stage completes
before any candidate arm runs; failure aborts policy evaluation.

The count of 48 supplies six cases per family: enough repeated variations to
avoid a single hand-built topology deciding each family result, while keeping
the offline exhaustive reference bounded (48 x eligible candidates x two
public point-plan counterfactuals). Generated cases change terminal height,
candidate position/probability, and controlled family geometry only. No FIT
identity or outcome data informs construction.

## Arms and frozen computation

Compare C0 (original C, K=3), C-K (original ranking, K=5), C-Route3 (frozen
v2.0 ranking, K=3), and C-Topology3-corrected (v2.0c, K=3). Preserve exactly
the existing ternary memory, public probability approximation, ray-footprint
eligibility, single-cell V and D equations, sensing/plan/scarcity costs,
observation cap20 including initialization, actual planner, paid 61-ray sensor,
emergency safety sensor, and selected-action shield. C-Topology3-corrected
uses at most seven A* calls. C-K is charged normally at up to eleven calls.
Graph computation is separately measured and never described as free. No
multi-step EVI, G1-aware EVI, persistence-memory changes, or new scan-cost
parameters are included.

The exhaustive EVI reference independently reimplements V/D and uses the same
frozen public point A* planner only for the counterfactual routes (so first
action ties match the evaluated formulation). Its common comparison price is
the frozen K=3 price using seven plan calls. It is offline-only and does not
use the selected-action shield.

## Metrics and numeric gate

Useful means an eligible candidate whose exhaustive `D` exceeds the common
frozen K=3 observation cost. Report empty-useful fixtures separately; exclude
them from candidate-recall denominators. Report macro recall (mean across
fixtures with nonempty useful sets), micro recall (pooled useful candidates),
per-family metrics, and maximum-D tied-candidate recall. Also report selected
best-D regret; common-cost scan-decision agreement over all 48 fixtures;
actual authorization under each policy's own charged cost; false positives and
false negatives versus the exhaustive common-cost decision; no-benefit
authorizations; A* calls; graph work units; graph p95; and total scheduler
time.

The numeric gate is conjunctive:

* C-Topology3-corrected improves macro useful-candidate recall by at least
  0.10 absolute over C0; micro useful recall is not lower than C0.
* Macro maximum-D recall is not lower than C0.
* Common-cost scan-decision agreement is at least 0.05 absolute higher than
  C0 across all 48 fixtures, with numerator and denominator reported.
* No actual scan is authorized in any of the six predefined no-benefit cases.
* Every C-Topology3-corrected decision stays at or below seven A* calls.
* Every decision stays within `20*(V+E)` graph work units.
* After 10 warm-ups and 100 measured graph-plus-ranking calls per fixture,
  aggregate p95 graph-analysis runtime is at most 5 ms on the recorded host.

These thresholds, formulas, source, and seeds are frozen before candidate
screen execution. Numerical success alone is insufficient.

The formal result embeds SHA-256 fingerprints for this protocol, the
intervention protocol, fixture source, annotation validator, runner, reviewer,
production/reference modules, and frozen V/D and candidate-coverage modules.

## Separate conformance review and stop rule

After formal execution, a separate reviewer verifies the independent
correctness suite, annotation validator, production/reference agreement,
metric denominators, leakage flags, original C V/D/cost parity, all plan/work
bounds, runtime protocol, and complete SHA-256 manifest. The reviewer writes
`gate_review.json`. FIT fixed-state replay and FIT72 evaluation are permitted
only if both numeric status is PASS and review status is exactly
`ACCEPTED_FOR_FIT`. Any defect or inconsistency yields
`INVALID_STOP_BEFORE_FIT`; preserve the raw result unchanged and do not rerun
or edit this frozen protocol. A revised iteration requires a new protocol and
result version.

If accepted, a separately frozen intervention selection protocol is required
before FIT access, followed by protected-data/source integrity verification,
untreated parity, fixed-state diagnostics, selected real observations, a
two-case smoke, and at most one descriptive FIT72 screen. Independent cohort
work remains unapproved and unexecuted. Independent evaluation ultimately
requires reductions in both sensing and navigation cost, with preserved
completion and safety.
