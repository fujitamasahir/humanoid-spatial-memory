# FIT72 persistence/EVI failure analysis

Date: 2026-11-13. This is a descriptive development analysis of the already
completed 72-key FIT72 evaluation, not independent validation. The frozen B/C
policies and the five-arm evaluation outputs were not changed. Detailed evidence
and replay files are in
[`persistence_evi_failure_analysis_v1`](../results/phase2_mujoco/persistence_evi_failure_analysis_v1/README.md).

## Paired outcome findings

Periodic, Age, and B-only each reached the goal in 66/72 episodes. C-only and
B+C each reached 46/72. The C and B+C failure key sets are identical: each
fails on 20 keys where Age succeeds and 20 where Periodic succeeds, with an
overlap of 18. The union comprises 22 distinct keys where either baseline
succeeds but C/B+C fails. There are no cases in this cohort where C or B+C
succeeds while both baselines fail. This paired comparison avoids treating
equal aggregate success counts as equal episode outcomes.

All 52 C/B+C candidate failure episodes reached the H80 limit. Four failures
per arm also failed under both Periodic and Age; the comparative chronology,
EVI instrumentation subset, and causal interventions below focus on the 22
distinct keys where at least one reference method succeeded. Within those 22
keys, C had 337 shield-rejected translation attempts and B+C had 339 (across
all 26 failures, totals were 389 and 391); the saved reason is translation
collision, not rotation collision. Rejected actions were often at different
positions or headings: same-position-and-heading repeated visits occurred in
5/22 episodes per arm, with at most two visits at a signature. This does not
support a broad claim that all failures are a single repeated-action loop.
Unwanted contacts were zero in all five arms.

## Observation timing and EVI mechanisms

Read-only decision instrumentation replayed the 44 comparative failure traces (3,520
decisions) with exact agreement in action-relevant semantic traces. The first
scan schedule divergence from Age and Periodic is step 4 for all 22 failure
keys; C/B+C public ternary memory then diverges from Age at step 5 in all 22.
First selected action/pose divergence from Age occurs at steps 4, 5, 6, 7, 8,
or 13. The Periodic memory snapshots were unavailable, so no claim is made
about the first public-memory divergence from Periodic.

Across the 1,760 decisions per C arm in the failure set, most had uncertain
candidates but estimated value V=0: 1,466 C and 1,478 B+C decisions. Positive
value with immediate action agreement (D=0) occurred 27 / 23 times; positive
delay value below configured costs occurred 245 / 241 times; observations were
granted at 22 / 18 decisions. The observation budget was never exhausted in
these failures. Candidate shortlist shadow analysis found an outside-top-three
route candidate capable of changing the immediate point-plan first action in
643 C and 650 B+C decision steps. This supports shortlist omission as a
plausible contributor, not a demonstrated cause: the shadow route is not a
G1 collision query and does not prove the excluded scan would rescue the
episode.

At the 40 actually authorized memory scans within these failed traces, the
predicted visibility omitted a nominal-route cell once for C and zero times
for B+C. No selected top-three candidate showed directional probability error
at those scans. This does not test what an unselected scan would have seen.
Mechanisms A (shortlist exclusion), B (visibility mismatch), C (probability
underestimate), and H (point planner versus G1 consequences) remain
unconfirmed as causal explanations. The implementation's single-cell,
top-three public point-plan approximation is a known limitation.

## Controlled real-scan counterfactuals

Ten cases and interventions were frozen before counterfactual execution: six
representative failures, both Periodic-only M80030009 schedule cases, and two
successful low-observation controls. Interventions used the original admitted
worlds and actual authorized 61-ray MuJoCo memory observations. They did not
inject occupancy or query unselected shield actions. The 20-scan cap and
independent emergency sensor were retained.

There were 68 intervention outputs. One untreated B+C replay (episode 63,
R80000018 schedule 0) diverged from its saved semantic trace at step 66 in
action, action reason, blocked status, and heading; that arm/case is excluded
from causal contrasts. For M80030004 schedule 0, one early real scan rescued
both C and B+C: C reached at step 74 (14 scans; 6 blocked attempts) and B+C at
step 71 (10 scans; 5 blocked attempts). The scan-swap variant also rescued
both (steps 75 and 72 respectively). Delaying four steps rescued C at step 75
but did not rescue B+C. Other selected failure cases generally reduced some
blocked attempts without reaching the goal. These results establish that
timing can causally change outcomes in this selected case, not that a general
online schedule or a particular untested scan would solve the other failures.

## B-only versus Age

B-only used precisely the same observation steps and frame traces as Age for
all 72 keys; paired outcomes, action/pose traces, scans, blocked attempts, and
distance are identical. B therefore did not alter navigation in this setup.
Across 2,915 inference calls, its public ternary projection changed 182 cells
in total; these inference changes did not change the selected route/action
trace. For policy-selected observed-cell predictions, Brier/log-loss were
0.151509/0.451921, versus 0.140513/0.410104 for last-write and
0.159129/0.485240 for fixed age-rate. These are selected-observation samples,
not global map calibration. Synthetic transition cases show the conservative
projection can retain stale occupied status after an unobserved vacancy until
a later observation/projection crossing. The probability ledger and public
ternary projection should therefore be interpreted separately.

## Total sensing and computation

Direct instrumentation of `MujocoRayPerception.observe` matched saved paid
scan counts and scan steps for all 360 arm episodes. Mean paid memory scans
were 11.11 Periodic, 11.81 Age/B, 5.38 C, and 3.64 B+C. Mean combined paid
memory plus emergency rays per episode were approximately 3,252 Periodic,
3,190 Age/B, 3,580 C, and 3,497 B+C. Thus fewer paid memory scans did not
reduce total modeled ray workload because the emergency sensor ran over more
navigation steps. C/B+C mean scheduler time was 123/128 ms per episode;
their mean wall times were 291/299 ms versus 145/145 ms for Age/B. Baseline
scheduler time was not instrumented, so no exact overhead ratio is available.

On paired common successes, C versus Age saved 2.63 paid scans but used about
247 more combined rays, 6.67 more steps, and 0.95 m more distance; B+C saved
5.04 scans but used about 137 more combined rays, 7.28 more steps, and 1.27 m
more distance. Incomplete routes are not interpreted as efficiency gains.

## Ranked research hypotheses (not implemented)

1. **Route-relevant candidate coverage:** Mechanism addressed: top-three
   shortlist may omit cells that change point-plan actions. Potential benefit:
   earlier useful sensing. Risk: more planner work and scans; point-plan value
   may still disagree with G1 feasibility. Test: frozen candidate-generation
   ablation with exact replay parity, paired held-out development worlds, and
   actual authorized sensing.
2. **Multi-step value of information:** Mechanism addressed: immediate-action
   agreement sets delay regret to zero despite route consequences several
   steps later. Potential benefit: detect observations that prevent later
   dead ends. Risk: computational growth and model error. Test: compare a
   bounded multi-step public-memory estimator with the frozen C baseline,
   logging prediction calibration and actual outcomes.
3. **G1-feasibility-aware public planning value:** Mechanism addressed: point
   A* surrogate versus footprint/shield effects. Potential benefit: align
   information value to realizable actions. Risk: expensive or leaking
   unselected collision queries. Test: use only permitted public dimensions
   and actual observations; validate that counterfactual scoring never calls
   the shield for unselected actions.
4. **B probability-to-map calibration:** Mechanism addressed: inference
   probabilities changed without affecting decisions and were worse than
   last-write on selected samples. Potential benefit: useful uncertainty
   without unnecessary conservative occupancy. Risk: tuning to FIT72 and
   stale obstacle removal. Test: preregister parameters on separate training
   worlds and evaluate once on a reserved cohort.

These are hypotheses for future experiments, not recommendations to change
the frozen algorithms based on FIT72. The two schedules per maze are correlated;
FIT72 is descriptive development evidence and does not establish generalization.
