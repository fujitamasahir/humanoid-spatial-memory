# Phase 1.5A proposed protocol amendments and review decision

2026-11-07. **Recommendation: continue design review; do not begin Phase 1.5B.**
This is a separately documented amendment proposal. The original Phase 1.5
[research review](phase1_5_research_review.md), [method design](phase1_5_method_design.md)
and [protocol](phase1_5_experimental_protocol.md) remain unchanged, as do all frozen
Phase 1.4 policies, locks and results. No new scheduler or navigation experiment
was implemented. Only mathematical tests and synthetic numerical/compression
workloads ran for this review.

Reviewed Git base and fetched remote tip were
`9ba556158511a4808518c897878406f53f17b4c7` on
`feature/phase1-4c-assessment`; the working tree was initially clean. Continue on
that branch without rewriting history. All changes in this follow-up are new
audit documentation, standalone audit code and compact mathematical evidence.

## Evidence and decisions

| Basis | Finding | Review decision proposed |
| --- | --- | --- |
| Verified finite-table checks | EVSI bounds, null/positive/parity fixtures hold for the declared finite model. | Retain decision relevance as the research question; do not claim navigation validation. |
| Mathematical audit | Finite-bank SE does not bound belief/forecast/model error; a rebuilt real posterior may differ from the evaluated controller. | Resolve finite-bank F versus generative G architecture before implementation. |
| Source inspection | Mask is deterministic supercover occlusion, bit noise only on returns; world advances before queries. | Adopt the exact likelihood and timing corrections, subject to review. |
| Specification audit | Four topology generators and graph-extraction choices are incomplete. | Generate no layouts now; approve complete specifications first. |
| Analytic power scenarios |160 clusters give only29.6% superiority power for5 points at q=.2. | Choose an estimation-focused first independent assessment. |
| Synthetic measurement | J64 dense arithmetic median7.896 ms; complete inference/planning unmeasured. | Narrow the first matrix; retain a model-specific feasibility gate. |

Supporting reports: [design audit](phase1_5a_design_audit.md),
[topology audit](phase1_5a_topology_audit.md),
[power analysis](phase1_5a_power_analysis.md),
[feasibility](phase1_5a_feasibility.md). Verified evidence is stored in
[mathematical_audit.json](../results/phase1_5a/mathematical_audit.json).

## Amendment P1: bounded target and primary estimands

Recommend an **estimation-focused**, independently generated study of decision
relevance under stale, noisy, occluded occupancy. The target population is four
reviewed topology mechanisms, equal weights,160 genuinely independent topology/
lineage clusters,40 each. This is a resource-bounded first study, not the smallest
sample guaranteeing five-point efficacy. It can estimate effects and falsify
large/clear failures; it may leave five-point benefit unresolved.

Retain96 development clusters (48 fit,24 calibration,24 selection) and the separate
96-cluster final held-out concept from v0.1, but all generator definitions and
actual independence certificates must first pass review. Do not generate final
held-out here. Do not replace independent clusters with repeated seeds or repeated
sensor settings. Historical Phase 1.4 assessment is design context only.

Primary prospective condition: radius3, occlusion on, noise .05, total cap8,
price .02, horizon80, two dynamics schedules per topology, one fixed common
controller. These choices retain the original primary condition, not a condition
chosen from Phase 1.5 assessment outcomes. Pose is known; sensing zero-latency.
No claim of robustness across sensors, budgets or locomotion follows from this
one-condition first assessment. Development can still check all proposed sensor
conditions for model calibration without using them as extra assessment n.

Primary estimands are A-minus-quota-periodic paired contact-free completion,
actual call count and actual observation cost. Report goal completion, contacts,
blocked attempts, time, memory errors, runtime/memory and all activation metrics.
Keep cost as its own outcome; do not claim the short-horizon utility is the
contact-free completion endpoint. All intervals in this first study are descriptive.
The five-point improvement remains a practical reference, not a powered success
threshold or proof that a point estimate>=.05 establishes a true five-point gain.

## Amendment P2: smallest recommended matrix

Use six scheduler rows with a fair common controller, public inputs, inference
budget and actual sensor. Frozen legacy gates are ports, not old full-stack
reproductions. The future implementation must lock its stochastic streams; a
single configured algorithm stream does not make A mathematically deterministic.

| Essential core row | Reason |
| --- | --- |
| Static | Detect collapse into no extra sensing; establish initialization-only endpoint. |
| Quota-periodic | Strong budget-allocation control and primary paired comparison. |
| Random-quota, five schedule streams | Separate timing structure from chance; average replicas within each world. |
| Frozen route-weighted gate | Cheap task-proximity comparator; keep legacy feature scales/parameters explicit. |
| Current-state-perfect decision comparator V_PC | Decision-aware upper-information comparator; never reveals actual world state to the agent. |
| Sensor EVSI A | Primary actual-sensor value approximation, architecture selected before implementation. |

V_PC is the model quantity in the design audit, not the original future-perfect
V_PI or a faithful published ATM reproduction. Replacing V_PI with V_PC is an
explicit proposed correction. The ledger charges every actual call at .02;
legacy gates may retain their frozen internal scales, including1.5 where required.
No policy gets contact labels, hidden topology, event schedules or better maps.

| Component | Maximum execution count |
| --- | ---: |
| Core:160 x2 dynamics x(5 configured rows +5 random streams) |3,200 |
| One-call timing:160 x2 x9 branches |2,880 |
| Two ablations:160 x2 x2 |640 |
| Total future assessment maximum |**6,720** |

This is94.64% fewer than v0.1's maximum125,440. It is a **proposal**, not an
executed matrix or a change to the original protocol. Budget development separately;
the reduced matrix does not imply rerunning all16 selection rows. Before any
development episode, approve a revised development job manifest for only retained
methods, analytic gates and calibration histories. Do not execute v0.1's12,672
development jobs automatically and call them necessary for this reduced design.

### Exactly matched timing remains essential

Use the common post-initialization t=0 prefix only. First branch decision is t=1
after advancement, window decisions1–4. All branches must have public Manhattan
distance>4, remaining budget>=1 and enough horizon before forking. Propose adding
start-goal Manhattan>=5 to the future generator's outcome-blind validity rule;
that is a new scientific choice requiring review. If not approved, report the
conditional eligible subset and do not replace it using navigation outcomes.

Compare A, V_PC, frozen route-weighted, fixed second-decision query and five
uniform random window times. Every branch grants exactly one call within the
window; value gates not yet requesting are forced at its last decision. Then no
further calls. All share prefix cost, one additional cost and common world/sensor
noise, with no access to another branch's future. Goal cannot be reached before
the window closes under the public distance rule. Do not add artificial post-goal
queries. Report forced fractions and the limitation to early-history timing.

The primary timing estimand is A-minus-fixed-second-decision contact-free
completion; random and route-weighted timing contrasts strengthen interpretation
but are not opportunities to select a winner. Keep160 eligible clusters if the
approved generator ensures eligibility; otherwise report counts and conditional
population. At least80 global eligible clusters and20 per mechanism are required
for the planned cluster intervals. At less than those counts, label the timing
estimate a sparse descriptive diagnostic; make no task-awareness claim.

### Two essential ablations

Retain gate-only phantom-goal and best-single-cell value ablations of A; executed
controller and real observation stay unchanged. They directly test decision
relevance and joint-sensor advantage at manageable cost. The phantom goal need
not be reachable and must use the same finite-loss unreachable convention; failure
to change a gate is reported, not fixed by picking a different goal in assessment.
No 'ablation success' is defined as more sensing. Actual cost and count changes
must accompany each navigation contrast.

Defer B, C, the broader price/cap/sensor matrix, remaining legacy periodic/age/uncertainty
rows, fixed-rate, conceptual query gate, disruption-visible port and other
two proposed ablations. Historical Phase 1.4 results remain available as context,
not fresh control executions. Dependence-removal and occlusion-removal ablations
should follow only after the base estimator/model is interpretable. Deferred
questions are not answered by the reduced study. Nothing permits dropping a row
after its final manifest is locked.

## Amendment P3: numerical, model and activation gates

JB-1 in the design audit is a fully specified mathematical **proposal**, not an
approved or benchmarked filter. Review the .5 initial occupancy prior, global
tiling, boundary restriction, Dirichlet-two transition fit, pose-derived evidence,
adapted proposal, importance correction and path-conditional Gibbs target.
Review architecture G versus F, conditional-forecast integration and current-state
V_PC before implementing A. A correct finite estimator alone does not clear these.
Also review posterior-advantage sampling versus the original difference-of-risks
estimator, and the weak-prior/capped-distance wait degeneracy. Algebraic EVSI
correctness does not establish a useful common motion controller.

Before navigation development, require exact-enumerable public synthetic checks:
normalized mask likelihoods, support, importance correction, invariant Gibbs
target, no action-changing information=>zero value, parity/joint information,
rare outcomes, noise and terminal-time semantics. No evaluator truth may be a
model input. The18 audit tests executed here cover identities/examples, **not**
an unimplemented JB-1 filter's correctness. Its invariant-kernel and importance
tests are future gates, not passed checks.

Retain v0.1's legitimate activation and ablation-difference gates, but define every
opportunity in a reviewed fixture manifest before development. Do not infer
precision solely from empirical SE: repeat independent numerical streams and
compare exact small-model values, reporting bias, tail error and zero-SE misses.
Use development only for J/P precision and runtime go/no-go; never assessment
adaptation. Missing sparse calibration strata mean unverified calibration, not
a pass. Show mask/occupancy calibration and filter ESS/support. Failure of an
activation/support gate stops the design instead of selecting the inactive
candidate for its cheap cost.

No fixed G architecture precision tolerance or J/P choice is approved here; the
original .01 goal must be reviewed against the rare-event and finite-model bias
findings. Defaults J64 and P8 are candidate workload sizes, not secretly selected
parameters. Future fit/calibration may learn only explicitly approved public-data
parameters, with no hidden-state supervision or cost/loss retuning from assessment.

## Amendment P4: analysis, resources and negative-result criteria

Use the power report's stratified topology bootstrap,10,000 draws, seed1505011;
average random streams then dynamics within each cluster, equal mechanism weights.
Keep complete paired blocks in every draw. Timing uses the same eligible cluster
structure, not independent branches. Report interval sensitivity, discordant
counts, zero/degenerate contrasts and leave-one-mechanism-out estimates. A160-
cluster study estimates effects conditional on four mechanisms; it does not
establish generalization to all layouts. No post-assessment sample extension,
primary-method switch or threshold revision is permitted.

Predeclared interpretation, not a set of new confirmatory tests:

- If A makes no extra requests or behaves exactly like Static, report failure
  to demonstrate adaptive sensing. Do not infer sensing is intrinsically useless.
- If A improves completion while using more observations, report a possible
  sensing-volume benefit. Do not attribute it to task-aware timing.
- If exact-count timing is null/inconclusive, report that explicitly, even if
  unrestricted completion improves. If its upper interval excludes+.05, it
  limits a five-point benefit in that conditional assay, not every sensing task.
- If completion intervals include both meaningful benefit and harm, the study
  is inconclusive. A nonsignificant result is not equivalence or proof of no effect.
- If ablations are inactive after passing development, retain their exact negative
  comparisons; do not drop them or claim the conceptual component is irrelevant.
- Any support/integrity/access failure aborts and preserves checkpoints; no truth
  reset or scientific parameter change. Define deadline failure as an aborted
  incomplete episode, with conservative failure in an explicitly labeled
  intent-to-evaluate summary and missing sensitivity bounds. Never silently skip
  it or fabricate a controller continuation. Publish missingness and reasons.

Resources: the6,720 maximum has537,600 decision events. Generic dense-kernel
contribution is about1.18/2.38/5.07 core-hours for J64/128/256 if charged at every
event, not end-to-end runtime. Set a provisional30-core-hour assessment planning
allowance and25-GB archive allowance, plus separately approved development and
verification. Faithful benchmark/schema projections must fit before approval;
otherwise amend resources before assessment, not scientific behavior during it.
Keep the512-MiB RSS gate and separate common/scheduler timing measurements; the
synthetic36.16-MiB process peak does not prove they pass. Full per-episode atomic
checkpoints, POSIX leases, exact job hashes, trace checksums, source/configuration
provenance and independent metric reconstruction remain mandatory.

## Explicit research-review checklist

1. Approve model architecture and JB-1 amendments or request alternatives; decide
   whether a weak spatial prior plus tile dynamics can answer the question at all.
2. Approve corrected timing/terminal loss, forecast integration, V_PC comparator,
   numerical-error interpretation and the loss/price units.
3. Supply/approve four complete generator specifications and exact canonicalization
   rules; authorize artifact-only generation/audit separately. T1/T2 in the topology
   report are explicit alternatives, not adopted replacements.
4. Approve estimation-focused160-cluster scope, reduced6,720 maximum, development
   manifest and resource ceilings, or specify a powered independent confirmatory
   design before any assessment access.
5. Finalize fixtures, opportunity definitions, calibration/stopping criteria,
   source/parameter lock, partition commitments and publication plan before runs.

These are scientific decisions requiring review, not routine implementation
defaults. No generator, new policy, navigation study or held-out access follows
automatically from this report. Stop for research review before Phase 1.5B.
