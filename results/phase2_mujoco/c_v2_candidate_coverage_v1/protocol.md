# C v2.0 candidate-coverage protocol

**Frozen before implementation and candidate evaluation:** 2026-11-14
**Scope:** route-relevant candidate coverage only. C0, B, B+C, RDAO and Event
remain frozen. No multi-step EVI or G1-aware counterfactual planner is included.

## Motivation and audit boundary

The saved FIT72 shadow replay established that outside-top-three nominal-route
cells could alter an immediate public point-plan action at 643 C and 650 B+C
decision steps. That is not equivalent to positive value, positive delay
regret, authorization, a useful physical scan, or goal rescue.

A supplemental public-memory-only replay of the same comparative failures
evaluated the excluded nominal-route cells' existing single-step V/D equations.
Across 3,890 excluded C and 3,925 B+C candidate instances, 952 and 977 could
change the point-plan first action. Positive V occurred for 552/572 instances;
positive D for 301/312; D exceeded the frozen K=3 scan cost for 241/225; and an
excluded candidate individually exceeded both the currently selected D and
the K=3 cost at 237/225 candidate instances, across 233/225 decision steps.
The precise overlap with action-changing candidates is separately available in
`excluded_route_candidate_value_audit.csv`. These are public point-plan
counterfactual diagnostics, not causal online interventions. All 44 replays
matched the saved semantic traces.

This audit supports candidate coverage as a testable mechanism, but does not
show that all excluded candidates were valuable. In particular, many action
changes had zero V/D or stayed below scan cost. The original C's top-three
selected candidates had positive D at only 267/1,760 C and 259/1,760 B+C
decision steps; the candidate audit will distinguish the candidate-selection
effect from these scheduler limitations.

### Fixture-design iteration and final freeze (2026-11-14)

Two exploratory fixture outputs are retained (`synthetic_fixture_results.json`
and `synthetic_fixture_frozen_v1/`). Inspection showed their horizontal narrow
corridor made successive route cells similarly constrained, so the label
“unique critical cell” was inaccurate. These outputs are fixture-construction
trials, not the predeclared mechanism gate. This was a fixture correction, not
a change to the ranking formula. The final frozen mechanism fixture uses a
vertical public wall with exactly one uncertain route-cell opening; the opening
is the unique connection between start and goal regions. The formula, weights,
K and rejection rule remain unchanged. v2-v6 retain prior gate records. v7
includes per-call diagnostic wall time, computes C0 shortlist membership
directly from the original ranking, uses distinct critical geometries (one-cell
wall opening and multi-cell narrow corridor), and validates exact C0/C-K
decision-value parity. It is authoritative. No FIT trajectory was inspected
for these synthetic reruns.

## Frozen hypothesis

Among fixed-state public-memory decisions, ranking visible uncertain cells by
route criticality will include more candidates with positive D and candidates
whose D exceeds the original scan cost than the original uncertainty/distance
ranking, at the same K=3 planning-call budget. If this does not occur in the
predefined synthetic fixtures, reject the mechanism hypothesis before FIT72.
FIT72 is not used to tune weights or choose K; it is one descriptive engineering
screen after protocol and synthetic tests are frozen.

The online ranking uses only: (a) the current public ternary grid, (b) current
public occupancy probabilities, (c) the nominal public point-plan route, and
(d) the already computed optimistic 61-ray memory footprint. It cannot inspect
hidden geometry/occupancy, future motion, identity of a FIT maze, retrospective
failure labels, prior baseline success, or shield results.

For each eligible visible candidate cell c, define uncertainty

    U(c) = 4 q(c) (1 - q(c))

Let `on(c)` be 1 if c is on the nominal route and 0 otherwise. Let `d(c)` be
the minimum Manhattan distance to the nominal route. A public branch point is
a nominal-route cell with at least three cardinal neighbors that are traversable
under the existing unknown-cell mode. Let `b(c)` be the minimum Manhattan
distance to such a branch point, or infinity if none exists. Let `n(c)` count
cardinal neighbors of c that are traversable under the same mode, and define
`narrow(c)=1/(n(c)-1)` for n>=2, otherwise zero. Rank descending by

    score(c) = U(c) * [2 on(c) + 1/(1+d(c))
                       + 0.5/(1+b(c)) + 0.25 narrow(c)]

where `1/(1+infinity)=0`. Ties break by y then x ascending. Candidates remain
eligible under the original strict probability bounds and visibility estimate.
The route term prioritizes cells on the current nominal path; proximity,
branch proximity, and public local corridor width provide bounded secondary
signals for near-route alternatives. Coefficients are fixed design choices,
not FIT-derived or calibrated parameters. Ranking is O(NL) with N visible
uncertain candidates and L nominal-route cells (bounded by the fixed map and
episode geometry); it adds zero A* calls.

## Four policy arms and resource ceiling

- **C0:** frozen original C, original ranking, K=3, at most 7 A* calls/decision.
- **C-K:** original ranking, K=5.
- **C-Route3:** formula above, K=3.
- **C-RouteK:** formula above, K=5.

K=5 is frozen as a small coverage expansion of two candidates. It raises the
worst-case A* count from 7 to 11 per scheduler decision; candidates add two
public point-plans each. The original `.01 * number_of_plans` price applies
without change, along with the original sensing cost `.5`, scarcity cost
`.5 / remaining_budget`, scan test `D > cost`, original 20-observation cap,
original ternary memory/probability approximation, G1 planner, paid sensor,
independent emergency sensor and selected-only shield. At most 11 A* calls per
decision is the hard computational limit. Runtime does not influence decisions.

C0 is compared by exact trace and metric parity to the saved original C arm.
No original implementation or result is overwritten. K=5 will not be reduced
or increased based on any FIT72 outcome.

## Synthetic fixture protocol and rejection criteria

Before FIT72, run deterministic public-grid fixtures for: a critical uncertain
cell ranked below the original top three; a single-cell narrow bottleneck;
multiple alternative routes; high-uncertainty irrelevant cells; uncertainty
near a future route branch; no-benefit observation; and correlated uncertain
cells. Fixtures specify only ternary grids, probabilities, pose, goal, sensor
footprint and unknown mode. They are not admitted environments and do not call
MuJoCo or the action shield.

Report per fixture candidate coverage, selected candidates, V/D, authorization,
planning-call count and deterministic compute count. The route-ranking
hypothesis fails its mechanism test if C-Route3 fails to select the explicitly
route-critical fixture cell more often than C0 at K=3, if it authorizes in the
no-benefit fixture when C0 does not, or if any arm exceeds its 7/11 call cap.
These tests do not establish navigation or safety benefit.

## FIT72 descriptive screen and no-tuning rule

The exact sequence is: verify source/protected evidence; run synthetic tests;
freeze code/configuration hashes; reproduce Periodic/Age and original C0
metrics/traces; run C-K, C-Route3, C-RouteK once on the same 72 existing FIT
keys. No environment generation or store writes are permitted. FIT72 results
are not an independent test set and cannot be used to revise this formula.
Report all goals, safety, paired common-success movement, sensing, EVI and
compute outcomes. A candidate-coverage change is useful only if it improves
authorized real observations without safety loss and maintains goal completion
and navigation cost; otherwise retain the negative result.

Independent development and evaluation require a new lineage-separated cohort
and a frozen policy. The proposal and approval gates are in
`docs/independent_cohort_proposal.md`.
