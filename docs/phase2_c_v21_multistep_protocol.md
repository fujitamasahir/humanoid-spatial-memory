# C v2.1 bounded multi-step observation timing — prospective v1

Date: 2026-11-14. Freeze this protocol, all source and synthetic annotations
in a committed binding BEFORE any formal candidate execution. No horizon sweep,
fixture replacement, parameter fitting or policy selection on FIT outcomes.
Previous candidate-ranking policies and evidence remain immutable.

## Hypotheses and scope

A frozen one-step rule can ignore useful information when two public point
routes share their first move. However, most such information may safely wait.
H21a: explicit now/delay/no-information costs distinguish useful postponement
from movement regret. H21b: predicted loss of a future sensing opportunity can
justify scanning before a later route divergence. These are engineering
hypotheses, not calibrated EVI or a novelty claim. No B changes, G1-aware
counterfactual planner, new events or new topology ranking are allowed.

Migration preflight and replay are independent of the new mechanism gate:
verify Python3.12/.venv, exact requirements, G1 XML/meshes, all2,907 original FIT
checkpoint/receipt pairs,836 protected files and frozen evidence. Replay all72
keys of Periodic/Age/C0/C-K/Topology3-d with identical metrics AND semantic
traces on this Mac, instrumenting baseline schedulers too. Historical timings
from another machine are not comparators. No reserved population is accessed.

## Frozen action catalog and equations

The conceptual lookahead is **H=3 point-grid move opportunities**, selected
before the historical mechanism audit as a small constant (next few local
choices), not from FIT outcomes. A point move predicts heading toward its
neighbor. It is not a real G1 step, turn-duration estimate or future reading.

For a shortlisted cell c with public occupancy probability q, compute the
existing two A* paths r0/r1 for hypothetical free/occupied c. Reuse those paths;
there is no A* at future states. Public-map candidate selectors are unchanged:
original uncertainty ranking with K=5 or exact Topology3-d with K=3.
All other cells and q are held fixed during the lookahead. Unknown handling,
61-ray footprint, range/FOV and sensor parameters are the existing definitions.

The existing loss is L(r,o)=length(r)-1+80*I[o=occupied and c in r]; an empty
path costs80. Let p(o)=(1-q,q), N=min_r E L(r,o), and I=E min_r L(r,o).
The existing full-route value V=N-I is retained as a diagnostic. This model
compares a bounded action prefix with a full-route terminal surrogate, not an
H-step physical rollout or a globally optimal belief-space plan.

A blind delayed choice is a pair (r,h), r in {r0,r1}, h in {1,2,3}, chosen
BEFORE the outcome. Simulate the first h intended moves of that fixed path:
if an occupied c would be entered, remain at its predecessor for the remaining
prefix; the attempted direction determines heading. End-of-path prefixes wait.
Prefix time is h, including modeled blocked attempts/waits. No shield query is
made. This outcome simulation is a public counterfactual, not actual feedback.

After that prefix, predict c's visibility from the simulated position/heading
on the CURRENT public grid using the existing memory ray arithmetic. It does
not read a future scene or call a sensor. In the no-visibility ablation, assume
perfect future availability instead. A single (r,h) must serve both outcomes;
no outcome-dependent scan time or route is selected before observing.

If c is visible, take the outcome's minimum-L path and recover by reversing
some executed prefix to any vertex shared with that path, then follow its
suffix. Cost = h + minimum backward distance + suffix length. If that path is
empty/infeasible, use h + its terminal loss. This is a conservative restricted
recovery catalog, not an additional shortest-path search. If c is unobservable,
retain L(r,o): its prefix movement is already included, and no second V is
added. This fallback ignores some waiting/recovery detail and is an explicit
surrogate limitation.

Let B=min_(r,h) E[delayed movement loss]+C and A=I+C. The common one-scan price
is C=.5+.01*(actual A* calls)+.5/max(1,remaining paid budget), unchanged from the
frozen cost conventions. Choose a scan now iff

    min(N, B) - A > 0.

Tie at zero means postpone/no scan; absolute roundoff below1e-12 is set to zero.
This compares scan now, a nonanticipatory delayed scan, and no information.
The pure movement-delay diagnostic is max(0,B-C-I), distinct from net value.
A scan is selected only if it is better than BOTH alternatives. No sums over
cells: select the single candidate maximizing (net value,V), preserving the
frozen shortlist tie order. Correlated cells are evaluated as marginal
hypotheses, never multiplied as independent joint outcomes or added as benefits.
This does not solve correlated belief planning. All sensing/computation prices
are engineering proxies, not calibrated economic or navigation costs.

## Arms and fixed costs

Formal public-memory arms: C0, C-K, C-Topology3-d; ms_k, ms_k_visibility,
ms_topology, ms_topology_visibility. The four new arms are a2x2 factorial:
frozen selector K5/Topology3-d × assumed future availability/predicted visibility.
C0 is archival; it is not given a new shortlist formula. No persistence arm.
The controller integration uses its existing evi_function hook only. Actual
G1 planning, independent emergency sensing and selected-action shield remain
unchanged. Cap20 includes initialization. Predictions are not observations.

## Exact computation/resource limits

N=grid cells, V/E=public traversable graph vertices/edges, M=eligible cells,
L=nominal route length, R=61 rays, S=ceil(range/(cell_size*.1))+1, K=5 or3,
H=3. A safe bound for the frozen A* is A(N)=O(N² log(N+1)); it does not discard
stale heap entries. Calls per decision:1+2s ≤11/7, where s is actual shortlist
size. Future planning calls=0. Counterfactual copy reads=2sN ≤2KN.

Current footprint computations=1; future footprint computations ≤4sH ≤60/36;
with a shared (position,heading) cache actual counts can be lower. Each costs
O(RS), including wall/bounds termination. Future route/time options=2sH ≤30/18;
outcome evaluations=4sH. Literal prefix-loop visits=2sH(H+1) ≤120/72.
Recovery membership checks ≤2sH(H+3) ≤180/108. Indexing the outcome paths visits
at most2sN vertices. These unlike units are logged separately, never summed.

K5 selection retains the frozen O(ML+M log M) ranking. Topology selection
retains its frozen O(N+V+E+L+M log(K+1)+K²) work and original counters.
Including copies, path indexing, loss membership, prefixes and visibility:

    O((1+2K)A(N) + selector(N,V,E,M,L)
      + (1+4KH)RS + KN + KH²).

Auxiliary memory includes grids/graph O(N+E), ordered candidates O(M), paths
O(KN), options O(KH), and cached footprints O(KH*min(N,RS)). It is not merely
O(KH). Record traced Python allocation peaks separately from process peak RSS.
Memory/scheduler benchmarks are single-process on this Mac, separate from
sensor and movement work. No cross-Mac latency ratios or unsupported real-time
claims. For each first fixture per family:3 warm-up and10 untraced timing
calls per arm, in the one formal run; all samples/median/p95/max are saved.

## Synthetic population and annotation gate

`scripts/c_v21_fixtures.py` fixes96 public-memory cases:12 named families ×8
conditions, seed namespace2026111401 +100*family_index + condition. Families
cover immediate divergence, shared prefix, future branch, last chance,
continued visibility, permanent occlusion, occupied shortcut, irrelevant
uncertainty, no benefit, correlated cells, competing candidates, and map-size/
heading/range variation. Deterministic padding, quarter rotations, q in
{.35,.5,.65}, sensor ranges5/6/7 and120/360 degree FOV are declared in source.
These are isolated public-grid fixtures, not a generated navigation cohort.

Annotations are verified BEFORE formal policy execution by a separately
implemented finite-prefix reference with BFS path-length certificates. It
imports neither the new policy nor its runner. The conservative K5 scan price
is used to certify designated controls. Save its full annotation result and
fixture digest in the committed source binding. No formal fixture is used for
policy unit-test development or changed after policy outcome inspection.

Correctness includes exhaustive81 ternary2x3 maps, four uncertain nonterminal
cells, two unknown modes and both visibility ablations (1,296 cases), independent
ray footprints, randomized selector parity, no-truth imports, cap enforcement
and separate reviewer fault injection. The reference exhausts the DECLARED
finite two-route/prefix catalog, not all possible belief-space navigation.

## Conjunctive numeric gates and independent conformance

All four new arms must agree with their independently enumerated restricted
reference to1e-9, retain the exact matched frozen shortlists/costs, obey all
call/operation limits, and match each independently calculated future pose,
heading and visibility. Malformed, inconsistent or fingerprint-mismatched
artifacts mean INVALID_STOP_BEFORE_FIT, not a negative scientific result.

For a valid experiment, require: zero false-positive scans against the
exhaustive eligible-cell reference at each arm's own price; zero scans in all
preannotated postpone/no-benefit/occluded controls; exactly16 opportunity
positive scans for each visibility-aware selector (8 last-chance +8 occupied
shortcut) and zero in its matched no-visibility arm. Immediate positive controls
must match their reference. Candidate-omission false negatives in correlated/
competing cases are reported separately, not hidden by a selected-only metric.
The known finite reference and selected fixture families limit interpretation.

The formal runner computes provisional numeric checks. A separately invoked
reviewer rebuilds the fixture population, reference numbers, shortlist parity,
predicted states, resource counts, aggregates, source/artifact fingerprints
and annotation gate in a new process. Error lists are isolated by category;
fault-injection tests cover numerical, selection, visibility, accounting,
source and artifact failures. No online simulation/world access by reviewer.
Only numeric PASS plus exact reviewer ACCEPTED_FOR_FIT authorizes new-policy
navigation. A valid numeric failure archives REJECTED and stops. Any invalidity
archives INVALID and stops. No post-result repair/rerun of this formal v1.

## Conditional navigation and causal matrix

If every gate passes, require the completed360 same-machine frozen reference
replays, then run exactly two sorted FIT keys ×four new arms as a smoke gate.
Require sensor-count, shield, cap, contacts and valid output; the full matrix
then runs once for72 keys ×four new arms. Its first two keys must match the
smoke semantically. Compare to the already replayed Periodic/Age/C0/C-K/
Topology3-d under the same pinned environment; do not use cross-machine times.
Any missing data, integrity, baseline or smoke failure stops the full screen.

Optional causal diagnostic is predeclared, maximum2 distinct keys. From saved
full new-policy traces, find a visibility-aware scan versus matched no-visibility
deferral with identical preceding semantic traces, shared point-route prefix≥1,
step<80 and used_before≤18. Select lexicographically by(identity,schedule,step,
arm), with one state per key; do not select by rescue/outcome. Replay untreated
with exact trace/metric parity, then compare its natural scan now to suppressing
that one grant and forcing one real authorized scan at t+1. If goal/horizon
prevents the later scan, mark the contrast non-enacted. Require identical
predecision traces and actual61-ray calls, preserve cap20/emergency/shield,
never transfer readings across trajectories. Report route/action/memory changes,
blocked attempts, cost and completion; do not infer general causality from two
selected states. If no state qualifies, report no eligible intervention.

## Navigation metrics, integrity and statistical limits

Save completion/contact-free completion, unwanted contacts, paid memory scans/
rays, emergency scans/rays, combined rays, H80-censored steps, paired rescue/
harm, steps/distance among common successes, blocked actions, emergency
interventions, evaluator-only false persistence/missed changes, V/net/delay,
authorization reasons, future visibility, A*/visibility calls, scheduler and
episode wall time. Include separate memory/compute summaries and representative
trajectory/decision visualizations. Each maze is a cluster; report paired
maze-level means and deterministic2,000 whole-maze bootstrap intervals, seed
2026111402. Schedules within a maze are NOT independent samples. No efficacy
claim from shorter failed episodes, repeated FIT development or exploratory CIs.

A descriptive joint navigation benefit requires no loss in goals/contact-free
completion, no extra contacts, fewer mean paid scans AND lower common-success
steps/distance relative to its matched frozen selector. Report all metrics if
that joint rule fails; do not select an arm after results as a validated policy.
The unapproved24-lineage pilot and80/200-lineage cohorts remain unopened and
ungenerated. Do not automatically proceed to G1-aware EVI after this task.

## Measurement scope clarifications before source freeze

The A* ceiling above is for the EVI scheduler only. It excludes unchanged
actual G1/normal route planning and the existing single post-scan public point
plan used for observation logs. `decide` timing excludes sensing/refresh;
episode wall time includes the full original pipeline. Future-visibility CPU
work is bounded and measured, but has no additional fitted price beyond the
unchanged A*-based computation proxy. This is an explicit cost-model limitation.
Benchmark arm order is fixed, not randomized; report host/load/order limitations.
The independent review is an isolated software reference/process, not an
external human peer review. Its oracle is the declared restricted catalog,
not mathematically calibrated or globally optimal EVI.
