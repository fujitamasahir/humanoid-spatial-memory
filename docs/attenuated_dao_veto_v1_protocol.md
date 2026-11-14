# Attenuated DAO-Veto v1: isolated estimator engineering comparison

Base b59b7f3d98757c5c31b1cde2b09133b2bb853529. Preserve the previous
attenuated-discovery accuracy audit, original DAO, all safety policies and
the Phase Wait expanded-gate rejection. In the previous selected-scan audit,
optimistic had the smallest count MAE under both safety variants. q=.5
had the fewest threshold-5 disagreements; neither demonstrates online
decision improvement or sensing efficiency. These results motivate a
fixed estimator ablation, not fitting or optimizing a new coefficient.

## Mechanism

Preserve DAO-Veto's Age5 anchor, frontier-based verification term,
oldest-local-cell fallback at10, all constants, initial-inclusive cap20
and memory update semantics. Replace ONLY the frontier unknown-cell
count D in its discovery predicate (D>=5) with the attenuated estimate
sum(q^k) from the frozen public geometry estimator. Compare q=.5, .8
and1.0, with the frozen original frontier DAO-Veto (q=0) as control.
No changes to verification geometry, fallback, other DAO variants,
safety, planner or real sensors. The existing authorized decision/refresh
contract is retained. The compatibility adapter has no extra route plan
for DAO-Veto; the implementation currently computes both original
assessment and attenuation, so geometry arithmetic is duplicated and
scheduler overhead is recorded. No actual sensing is added.

Each new estimate is at least the frontier count at the same public
state. Consequently it cannot directly suppress an original DAO-Veto
request in the same state; added grants might improve future navigation
or reduce subsequent scans, but that is untested. Log same-state extra
requests and grants; do not infer whole-episode monotonicity. q=0 must
match the original controller's authorization, memory and timestamps.
Factors are fixed heuristic transmission weights, not calibrated
probabilities. Retain all three alternatives; do not select the
best retrospective factor and silently omit others.

## Evaluation scope

The previous safety expansion has 26 explicit hand-defined scenes.
Use the identical scenarios, horizons, programs, common configurations,
and legacy actual-sensor/instrumented execution wrapper. Two safety
versions (original and frozen RES-H1 Phase Wait) are separate conditions.
Phase Wait FAILED its original expanded adoption criterion and remains
an unqualified engineering comparison only. No adoption or relaxation
of the original safety criterion is implied by these results.

Eight observation arms: Periodic4, Age4, Age5, CAA-Full, DAO-Veto,
DAO-Veto-q50, DAO-Veto-q80, DAO-Veto-Optimistic. 26 x8 x2 =416 episodes.
Require exact archived semantic/metric parity for all five reference arms
under each safety version (260 replays). Preserve roles (12 original
regressions,14 former prospective benchmark scenes); these are now reused
engineering scenes, not independent efficacy data. Original safety may
contact pedestrians. Record all onsets, not just contact-free goals;
only the specifically declared first-transition contacts have the
previously established unavoidable timing witness. No other contacts
are excused. All actual paid/emergency sensor calls and selected-only
shield checks, finite cap and last-write memory invariants are enforced
by the original wrapper. Preserve partial failures.

Compute per-scene paired results against all five references under each
safety condition. Report goal and contact-free goal counts, all onsets
and pair counts, paid scans, emergency rays, combined sensing workload,
elapsed steps with the scenario's own horizon, common-success steps and
distance, same-state extra grants, measured scheduler time for DAO arms
and episode wall-clock time. Do not present failure-shortened distance
as efficiency. Baseline scheduler runtime is not measured consistently
and must not be represented by zero. No pooled safety-version estimate,
independent efficacy, physical safety, promotion or production-pilot
authorization. Report all results even if no new variant improves the
reference. No post-outcome threshold tuning.

## Execution

Exclusive output results/phase2_mujoco/attenuated_dao_veto_v1.
Run scripts/run_attenuated_dao_veto_v1.py check, run, report.
Before execution verify previous expansion and accuracy-audit manifests,
frozen source bindings, original FIT 2907 pairs,836 protected files,
CAA artifacts and G1 assets via the existing verifier. Correctness tests
include synthetic differing-discovery rule, q0 controller parity, caps,
unknown/empty readings and prior discovery/safety regressions.
Source and protocol committed before new navigation; local test and
navigation execution pending. No FIT72 rollout, production/pilot/dev/
sealed population generation or reserved access. No safety re-tuning.
