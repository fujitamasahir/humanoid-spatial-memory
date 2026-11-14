# C v2.0 candidate-coverage research report

**Date:** 2026-11-14
**Branch:** `phase2/mujoco-proxy-pilot`
**Decision:** route-critical ranking hypothesis rejected at the pre-FIT72
synthetic gate. No C-K/C-Route3/C-RouteK navigation rollout or candidate FIT72
screen was run.

## 1. Candidate-selection audit

The original C implementation estimates an optimistic 61-ray visibility
footprint using only its remembered ternary grid. It keeps visible cells with
`.05 < q < .95`, computes one nominal public A* route, and ranks candidates by

    q(1-q) / (1 + ManhattanDistance(cell, nominal route)).

The first three cells are evaluated one at a time by making free and occupied
public-grid copies and planning each route. V is the expected loss before
perfect single-cell revelation minus the expected best loss after revelation.
The loss is path length plus the fixed failure penalty when an occupied
candidate remains on the route. D is V times `min(q,1-q)` only if the two
counterfactual routes have different first actions; otherwise D=0. The selected
candidate is the maximum `(D,V)`, not a sum. A scan is requested only when
`D > .5 + .01*plan_calls + .5/remaining_budget`. The current three-candidate
limit makes the maximum seven A* calls. The original code is unchanged by the
candidate-ranking module; the controller injection hook defaults to the same
original function.

The saved comparative-failure shadow data found excluded nominal-route
candidates capable of changing the immediate point-plan action in 643 C and
650 B+C decision steps. Those figures correspond to 952 and 977 candidate
instances. They do not mean that every one had positive V/D or deserved a
real scan.

A read-only replay then calculated V and D for every excluded nominal-route
candidate in those same 44 C/B+C comparative traces. All 44 replay traces
matched the saved semantic traces. Results were:

| Excluded nominal-route candidate instances | C | B+C |
|---|---:|---:|
| Evaluated | 3,890 | 3,925 |
| Change point-plan first action | 952 | 977 |
| Positive V | 552 | 572 |
| Positive D | 301 | 312 |
| D exceeds frozen K=3 cost | 241 | 225 |
| D exceeds both current selected D and K=3 cost | 237 | 225 |
| Decision steps with any candidate D above current best and K=3 cost | 233 | 225 |
| Actual no-scan → scan flips if that candidate were added | 233 | 224 |

Among just the action-changing candidate instances, only 301/952 C and 312/977
B+C had positive V/D; 241/952 and 225/977 exceeded the existing K=3 scan cost.
These are candidate-level diagnostic quantities. Multiple candidate instances
can occur at one decision step; one B+C step was already authorized, so only
224 B+C decisions would flip from no scan to scan. The current selected top-three shortlist had
positive V at 62 and positive D at 38 of the C action-change steps; its scan was
granted at 8. For B+C these values were 58, 36, and 8 of 650 steps. A changed
counterfactual point-plan action is therefore distinct from estimated positive
value, beating cost, current scan authorization, and a real scan's effect.

The evidence supports an incomplete candidate-coverage mechanism in the
existing public point-plan approximation. It does **not** establish that
shortlist omission caused the 22 comparative failure keys, that an actual
observation would have changed G1 navigation, or that broader coverage improves
completion. No unselected shield queries were made.

## 2. Frozen variants and implementation status

The protocol in `docs/phase2_c_v2_candidate_coverage_protocol.md` was written
before the final synthetic gate. It fixes a route-criticality score using only
public grid/probability/route/footprint information, with no added A* calls for
ranking. It defines:

- C0: original C at K=3.
- C-K: original ranking at K=5.
- C-Route3: public route-criticality ranking at K=3.
- C-RouteK: the same ranking at K=5.

K=5 is a fixed two-candidate expansion: at most 11 A* calls (nominal plus two
per candidate), versus 7 at K=3. Existing scan, sensing, plan, scarcity, memory,
sensor, G1 planner, emergency sensing, shield, and cap20 rules are unchanged.
The evaluation runner implements all variants and refuses to access FIT72
unless the frozen synthetic gate passes. It was not run beyond `--help`.

## 3. Synthetic mechanism result and decision gate

Seven deterministic public-memory fixtures ran under all four arms (28
fixture-arm runs): a unique critical cell below the original top three, a
narrow bottleneck, multiple alternatives, irrelevant high uncertainty, an
uncertain cell near a future branch, a no-benefit case, and correlated
uncertainties. Tests verified reproducibility, candidate/call bounds, the
single-cell max-not-sum rule, and no authorization in the no-benefit fixture.

The predeclared Route3 mechanism criterion failed. On the two explicit
critical-cell/bottleneck fixtures, C0 selected the target 0/2 times and
C-Route3 also selected it 0/2 times. C-K and C-RouteK selected it 2/2 times by
expanding K, but neither critical fixture changed the best V/D cell or the scan
decision: both C0 and Route3 already authorized a scan based on another
selected cell. This is evidence for increased shortlist
coverage from evaluating more candidates, but not evidence that route ranking
improves useful EVI selection at the same computational budget.

All arms stayed within 7/11 A* call caps, and none authorized a scan in the
no-benefit fixture. Per-fixture diagnostic wall times are saved, but the
single-process microsecond/millisecond timings are warm-order and machine
dependent; the fixed A* call ceiling is the interpretable computation bound.
The candidate-ranking hypothesis was therefore **rejected
before FIT72**, exactly as the frozen protocol required. The initial two
exploratory fixture outputs are retained and labeled as invalid fixture
construction trials; v2-v6 preserve earlier formal-gate runs, while
`synthetic_fixture_frozen_v7/` is authoritative. It records C0 shortlist
membership directly, uses distinct critical geometries, includes separate
diagnostic timing, and validates C0/C-K value parity; the same negative gate
result is reproduced.

## 4. Causal replay and FIT72 screen

No new real-observation interventions or navigation rollouts were run after
the gate failed. The earlier FIT72 study already established one selected
early real scan could rescue M80030004 for C and B+C, while other tested
interventions generally did not; it cannot be attributed to this new ranking.
The previously mismatched episode 63 B+C intervention remains excluded from
causal contrasts. The new candidate runner reproduces Periodic/Age and C0
before its variants, verifies actual paid 61-ray calls, preserves the existing
observation cap and shield, and never writes to FIT stores. Its default output
path is unused.

`results/phase2_mujoco/c_v2_candidate_coverage_v1/fig_candidate_selection_audit.png`
visualizes the excluded-candidate V/D/threshold counts. `fig_critical_fixture_shortlists.png`
compares synthetic candidate coverage and call counts. For historical context
only, the prior FIT72 report's
[`observation/completion`](../results/phase2_mujoco/persistence_evi_failure_analysis_v1/fig01_observation_vs_completion.png),
[`navigation timeline`](../results/phase2_mujoco/persistence_evi_failure_analysis_v1/fig07_representative_timeline.png),
[`EVI mechanism`](../results/phase2_mujoco/persistence_evi_failure_analysis_v1/fig05_evi_mechanisms.png),
and [`sensing-cost`](../results/phase2_mujoco/persistence_evi_failure_analysis_v1/fig09_sensing_costs.png)
figures describe C0/B+C versus prior methods, not any new candidate-coverage
arm. No new navigation-outcome visualization exists because the pre-FIT gate
blocked candidate navigation runs.

No new FIT72 descriptive comparison, outcome visualization, rescue/harm count,
or navigation-cost claim is reported. The cohort was not independent and the
pre-FIT gate rejected the tested mechanism. Candidate shortlist visualization
is synthetic only; the route diagrams must not be read as G1 navigation.

## 5. Tests, integrity, and remaining uncertainty

Executed focused tests: **37 passed** across `test_candidate_coverage.py`,
`test_persistence_evi.py`, and `test_persistence_evi_evaluation.py`. The new
FIT72 evaluator's `--help` and Python compilation checks passed. The preserved
Phase 1.5 prefix and FIT data were rehashed read-only: 836 protected files,
2,907 store payloads plus 2,907 receipts, and 363 FIT72 result files matched
their existing audits. The evaluator's execution guard was exercised and
refused before FIT access because the mechanism gate was rejected. No Phase
1.5 generator or heldout store was accessed.

The significant unresolved issue is whether the route score is a useful
same-budget priority signal. Its branch-proximity term can prioritize cells
near a public junction above a more remote single-cell chokepoint. This failure
was not repaired by changing weights because that would be tuning on the
synthetic results. The candidate-count control suggests coverage can increase
at extra A* cost, but whether this changes scan authorization or G1 outcomes is
unknown. No multi-step EVI, G1-aware value, B, or B+C behavior was changed.

## 6. Recommended next step

Do not proceed automatically to C v2.1 or v2.2 and do not run the blocked
FIT72 screen. First decide whether to abandon this route-ranking formula or
start a separately documented development iteration with newly specified
mechanism fixtures and a new pre-FIT protocol. Any revised ranking must show
same-budget Route3 coverage of the unique public bottleneck, must not authorize
in the no-benefit fixture, and must remain within the seven-call K=3 cap before
any further FIT interaction. Independent evaluation also requires the approved
lineage-separated cohort described in `docs/independent_cohort_proposal.md`;
that proposal has not been executed.
