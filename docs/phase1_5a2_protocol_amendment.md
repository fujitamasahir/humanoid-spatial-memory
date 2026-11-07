# Phase 1.5A-2 protocol amendment proposal

Version0.2, 2026-11-07. **Scientific review copy; no implementation or experiment
authorization.** Preferred scope: at most6,720 estimation-focused assessment
executions. This document explicitly supersedes the corresponding design choices
in v0.1/Phase1.5A **if approved**; it does not modify those historical documents,
Phase1.4 equations/locks/results, or the original confirmatory conclusion.

## Reviewed record and linked specifications

Reviewed all eight existing reports: Phase1.5 [research review](phase1_5_research_review.md),
[method design](phase1_5_method_design.md), [protocol](phase1_5_experimental_protocol.md);
Phase1.5A [design audit](phase1_5a_design_audit.md),
[topology audit](phase1_5a_topology_audit.md), [power analysis](phase1_5a_power_analysis.md),
[feasibility](phase1_5a_feasibility.md) and
[recommendation](phase1_5a_protocol_recommendation.md).
The v0.2 normative specifications are
[G architecture](phase1_5a2_architecture_decision.md),
[spatial prior](phase1_5a2_spatial_prior_review.md),
[common controller](phase1_5a2_controller_specification.md) and
[generator rules](phase1_5a2_generator_specification.md).

| Earlier open issue | Proposed resolution | Not established by this phase |
| --- | --- | --- |
| F versus G; real-update mismatch | G generative predictive mixture; identical posterior conditioning and keyed controller; independent policy-value evaluation. | Real-world EVSI accuracy or navigation benefit. |
| iid.5 prior / saturated distances | Public-fit2x2 categorical B; tile refresh; finite soft routing potential. | Global connectivity calibration or absence of waiting traps. |
| Future-state leakage | Integrate refresh entry risk analytically; current-state-perfect comparator only. | Correct pedestrian dynamics or physical collision probabilities. |
| SE used as confidence | Remove two-SE gating; keep conditional numerical diagnostics. | Confidence coverage for model error. |
| Unspecified topology families | Four explicit raster samplers and common quotient/lineage rules. | Actual accepted counts, independence or generator feasibility. |
| Insufficient efficacy power |160-cluster estimation study, no confirmatory five-point claim. | Equivalence if intervals include zero. |

The simplifications (fixed tiling, refresh rather than unrestricted transition,
no Gibbs, revised controller, mean-value gate and four-mechanism held-out plan)
are declared research choices, not invisible implementation optimizations.

## 1. Estimands and population

160 independently audited topology/lineage clusters,40 from each of R/B/V/M;
two independently sampled schedules per cluster. One sensor condition: radius3,
occlusion enabled, independent returned-bit noise .05. Known pose, zero sensing
latency, T=80, total cap8 including initialization, c_s=.02 per granted full call.
Initial observations and per-time/cell sensor streams are shared across methods.
The publicly known occupied border/free start-goal guarantee applies to all rows.

Primary estimands: paired A-minus-quota-periodic contact-free completion, actual
call count and actual cost. Also estimate A-minus-fixed-second-step exactly
matched timing contrast. All intervals are **descriptive/estimation-focused**.
The prior analysis's roughly30% superiority power at discordance.2 remains a
warning; this study is not powered to establish a five-percentage-point gain.
No sample extension, winner selection or new confirmation using this same data.

Secondary outcomes: goal completion, contacts, blocked attempts, elapsed steps,
path length, last-write memory errors (known/unknown, cumulative/terminal/common-
horizon), belief/mask calibration, observation timing/request/denial counts,
utility estimates, negative value frequency, action changes, numerical SE,
rejection/acceptance counts, common/scheduler runtime, Dijkstra/A* counters,
model calls, peak RSS and archive size. Do not condition error summaries on success.
Utility is not the primary navigation endpoint. Cost/performance plots must
display actual sensing, not infer matching from equal caps.

## 2. Six essential scheduler rows

All rows use the same G belief, current/future loss, fixed-potential controller,
model fit and actual sensor. Common-control RNG is shared when public histories
are identical. A different scheduler cannot obtain a better inference budget.

| Row | Exact scheduling definition |
| --- | --- |
| Static | Charged t0 observation only. |
| Quota-periodic | Seven postinitial calls at floor(80*j/7), j=1,...,7:11,22,34,45,57,68,80; none after goal termination. |
| Random-quota | Precommit seven distinct times uniformly without replacement from1,...,80; five independent schedule streams; none after termination. |
| Frozen route-weighted | Original public last-write/flip/age estimator, optimistic nominal A* route and route-weighted entropy gate; locked route_weight1, threshold.85, strict >. Only this gate's shadow route uses old A*, not movement. |
| V_PC comparator | On the shared64-draw prior-control bank, min mean Lbar minus mean per-state min Lbar; query iff >.02. This is exact current-perfect value for that bank, not a real oracle, future-perfect channel, or a proven upper bound on G's approximation error. |
| A: G policy-conditioned EVSI approximation | Independent64-pair value estimate for the actual64-sample conditional controller; request iff mean>.02. Negative values remain negative. No two-SE/shadow-price rule. |

All unspecified legacy route gate priors/defaults are exactly those in the frozen
lock and original source, hash-pinned before implementation. No new legacy
parameter selection. Maintain its last-write public history alongside G. Internal
legacy scales are distinct from the common .02 actual-call ledger. Reports must
call it a timing port under a new common controller, not Phase1.4 reproduction.

Compute/log the ungated criterion even when cap is exhausted; a denied request
does not call the sensor, reset memory, refresh belief or alter model randomness.
Record this cost separately. V_PC uses the same action loss/potential and current
state, never the actual hidden map. It is an adaptation/comparator, not a faithful
published ATM/ALONE implementation or evidence of novelty.

### Maximum assessment plan

| Component | Exact maximum |
| --- | ---: |
| Core:160 x2 schedules x(5 configured rows +5 random streams) |3,200 |
| Exactly one-call assay:160 x2 x9 branches |2,880 |
| Two A ablations:160 x2 x2 |640 |
| Total |**6,720** |

No cost/sensor/cap sweep, B/C extension, extra legacy row, held-out execution or
MuJoCo work is added. Complete fixed identities/checkpoints define the plan;
do not hide an omitted method behind a smaller 'completed' count.

## 3. Exactly matched one-call timing

Fork the quota-periodic core trajectory immediately after its mandatory t0
observation, before world advancement1. Start/goal Manhattan>=5 guarantees that
no branch can reach the goal before decisions1–4 close. All branches have the
same public initialization, simulator state and remaining cap; no branch sees
another's future calls/outcomes. No additional prefix episode is needed.

Branches: A, V_PC, frozen route-weighted, fixed query on decision2, and five
independent uniform times from{1,2,3,4}. Each value gate can query earlier; if
it has not requested before decision4, force the one call there. Permit exactly
one postinitial grant, then no further observations until completion/T. Query
always returns the same full physical sensor. All branches therefore have two
total charged observations and cost.04, with no post-goal padding. Log force flags.

This assay estimates early conditional **timing**, including observation-induced
trajectory changes; it is not full-horizon optimal budget allocation. Shared
world events and per-time sensor streams are counter-based and immutable. The
generator onset2–12 provides a prespecified mixture of changing and nonchanging
windows, not outcome-selected interesting cases. Average five random streams
within world and schedules within topology before intervals. All160 clusters
are eligible by geometry rules unless an integrity/compute failure occurs.
Report missing branches and conservative sensitivity, never pair only successes.

## 4. Two gate-only ablations

**Phantom-goal gate:** choose the interior cell distinct from x and real g with
largest Manhattan distance from real g, ties row-major. It need not be truly free;
do not make it protected in the model. Compute a separate finite soft potential,
loss, a0 and value for that virtual gate goal. The executed controller always uses
the real goal, real D_t and real observation. This intentionally changes which
task values a query, not the task actually executed. The estimate is not a
prediction of real-controller benefit in this ablated row.

**Best-single-cell gate estimate:** for each footprint cell i, marginal channel
Y_i in {missing,free,occupied}, evaluate the same policy-conditioned value
algorithm with only that scalar return. Use64 independent outer pairs per cell,
posterior-control keys indexed by cell/return; take the maximum estimated value,
ties row-major, and compare it with.02. Marginal missingness supplies only that
ray's blocker constraint; unobserved other returns are marginalized. Actual
grants still return the full array and use the real full-return controller.
The maximum has selection/Monte Carlo optimism; log all per-cell values and
selected cells, and test the bias on exact fixtures. Do not claim the finite
estimate must be <= full-query value. Exact Bayes single-cell value does have
that ordering, but the noisy policy-conditioned gate need not.

These ablations are intentionally behaviorally tested in development. Keep both
after final lock, even if inactive in assessment. More calls alone is not an
ablation improvement. Do not substitute a more favorable phantom goal or cell
criterion after results.

Exact gate fixtures exist without navigation: with swapped blocked/free action
states, the real-goal table has EVSI.15 while a virtual goal making both moves
uphill leaves wait optimal and value0. With two independent targets blocked
with probability47/50 each, free/blocked losses-.195/.105 and wait.005, perfect
full sensing has value.02328 while either single-cell query has value.012.
Thus the full query crosses.02 and single-cell queries do not. These rational
fixtures demonstrate possible score/request contrasts, not their prevalence
under the fitted model or noisy sensor.

## 5. Development-only fitting and gates

Keep48 fit,24 calibration,24 selection clusters, each with two schedules. No
assessment layouts/outcomes enter design, learning or numerical parameter choice.

| Stage, future authorization required | Maximum navigation executions |
| --- | ---: |
| Fit:96 initial returns for B, continuing the same96 Periodic-1 histories for r |96 |
| Calibration:24 x2 x(10 core +9 assay +2 ablations) |1,008 |
| Selection/go-no-go: same retained matrix on24 new clusters |1,008 |
| Development total |**2,112** |

Fit uses occlusion off/noise.05/unlimited calls with provisional r=.03 for the
data-collection controller; B then r fitting is exactly specified in the prior
report. Calibration/selection use primary sensor/cap/price. Initial fit returns
are part of, not additional to,96 full histories. Fit changes only B and r by
public likelihood, never controller utility, price or navigation success.
Selection is an independent go/no-go check, not a search for the winning method.
No fallback to iid.5 if the learned model fails.

Fixed M=S=J=64, rejection limit4096. These define a finite approximation to test;
they are not claimed adequate in every problem. Before any navigation development,
exact small-state mathematical tests must check posterior normalization and
rejection identity, the full and marginal mask channels, protected cells, gap
evolution, analytic future uncertainty, terminal loss and identical real/hypothetical
updates. Compare approximate action/value to exact enumeration on those fixtures,
including rare events and negative algorithmic values. The standalone tests in
this phase cover deductions/tables, **not an unimplemented filter's behavior**.

Before assessment, require these development-only gates:

- No zero-support, nonfinite or rejection-limit failure; publish accepted/candidate
  counts for every update. Mean acceptance below.05 or p95 update time breaking
  the resource limits stops review, not permission to increase limits silently.
- Analytic positive query fixture value.15 exceeds price; null/common-optimal
  fixtures have exact EVSI0. Include rare-information cases even if sampled SE=0.
  Remove v0.1's criterion that a zero empirical SE alone demonstrates precision.
- On fixed quota-public history snapshots t=1,2,3,4,10 from calibration, run20
  independent numerical replicas of the fixed estimator; log value variance,
  action disagreement and fraction above price. Diagnostic J256 integration uses
  the same controller keys, independently sampled outer states; it is a noisy
  reference, not truth and not an alternative assessed policy. At least80% of
  primary replica gates must agree with its reference sign on snapshots with
  reference mean outside[.01,.03], with at least30 such snapshots from six clusters.
  Otherwise stop for numerical instability/insufficient evidence. This empirical
  gate has no universal confidence coverage or model-bias guarantee. Never choose
  assessment J or a favorable subset from these results; a change needs review.
- Define informative opportunities **before calibration** as a frozen synthetic
  fixture set plus all above fixed snapshots, excluding only cap0/terminated
  states. Require A noninitial activation on>=5% of calibration snapshots and
  no exact Periodic-1 request sequence in>95% of complete calibration worlds.
  Null-fixture false requests must be reported, not erased by clipping.
- Each ablation changes its score in>=10% and request in>=5% of those opportunities;
  at least30 opportunities/six clusters. Both must also have a declared exact
  positive contrast fixture. Failure stops the design; do not drop a failed row.
- Query timing A must occur before the forced deadline in>=25% of calibration
  assay worlds. This does not require sensing in every static world. Publish
  no-change and event categories separately without using them as agent inputs.
- Report mask Brier/ECE (ten fixed bins, bins>=100 samples), known/unknown occupancy
  Brier and uncertainty by topology. Require ECE<=.10 in supported bins and no
  worse Brier than a fit-only constant-mask and iid.5 occupancy reference. Unsupported
  bins are unverified; no general calibration pass is claimed for them. Evaluator
  truth can score development predictions, never fit/update the model. Score all
  cells/directions at fixed evaluation times, including unsensed ones, to avoid
  certifying calibration only where the policy chose to look.
- The shared controller must pass safe/uncertain progress, legitimate waiting,
  terminal, blocked-source and finite-potential fixtures. Publish waiting/blocked
  sequences in development; no timeout/repair policy may be added in assessment.

All gate denominators, values, failures and exact fixtures are frozen before
their execution. Thresholds here are explicit proposed review conventions, not
claims of optimality. A failed gate is a useful negative design result. It may
require a revised, reviewed development design; assessment remains sealed.

## 6. Cluster-aware estimation and failure reporting

Average random replicas within schedule, two schedules within topology, then
give each of four mechanisms weight1/4. Resample complete independent topology/
lineage components within mechanism10,000 times, bootstrap seed1505011. Keep
all methods/assays/ablations paired in each draw. Report percentile95% intervals,
point effects, discordant counts, degeneracy and leave-one-mechanism-out estimates.
No episode-row bootstrap, sensor-repetition inflation or p-value shopping.

Report all predeclared contrasts against A or quota, with no new confirmatory
claim or practical-significance stopping rule. Same caps do not match realized
calls. A benefit with more sensing is possible sensing-volume benefit; exact-count
timing is required for task-awareness evidence. A zero/inactive ablation is a
negative comparison. An interval containing harm and benefit is inconclusive,
not equivalence. Report conditions under which a five-point effect is excluded
by a descriptive interval without claiming the study was powered to establish it.

If a compute/support failure prevents an episode, record it as incomplete and
as failure in a separately labeled conservative intent-to-evaluate completion
summary. Bound its unobserved binary outcome in[0,1] for missing-data sensitivity;
do not invent its contact count, observation timing or continuation. Stop on
integrity/access/source-lock failure immediately. Preserve the exact cause and
checkpoint. No favorable-world replacements, pairwise deletion of failures or
same-data scientific parameter repair.

## 7. Resource, integrity and access ceilings

Assessment maximum537,600 decision events; proposed ceiling30 CPU-hours and25 GB
complete compressed traces,512 MiB peak RSS/worker. Separate ceilings: development
30 CPU-hours/15 GB, independent verification10 CPU-hours/5 GB temporary workspace.
These are approval budgets, not benchmarks. Fixed-history numerical replicas
count toward development CPU; fitting and failed/recovery jobs also count. Faithful
model/schema projection must fit before approval; the old dense-kernel measurements
do not prove this G architecture fits. Stop/amend resources **before** assessment
if projections fail. Never silently omit posterior work or required trace fields.

Measure shared model/control p95<=100 ms and incremental scheduler p95<=100 ms
on declared hardware during development; hard per-decision limit1 second. Exceeding
the hard deadline aborts the episode/run for review; do not invent a fallback
action or skip a slow state. Mid-run CPU/storage ceiling exhaustion similarly
preserves an incomplete result, not adaptive matrix reduction.

Use POSIX writer leases, deterministic job hashes, atomic per-episode checkpoints,
immutable trace SHA-256 inventory, duplicate/missing detection and independent
metric reconstruction. Include complete public histories, model/parent anchors,
loss/potential values, numerical/rejection counters and source/configuration
provenance; model and algorithm stream keys must permit exact replay. Imaginary
arrays may be counter-reconstructed only after a golden replay test; otherwise
retain them. Keep evaluator truth in a separate stream inaccessible to policies.
Compact mathematical evidence/metrics/manifests belong in Git; full traces do not.

Development entry points reject assessment/final paths before opening them.
Assessment admits only its locked manifest; final held-out is separately sealed.
Historical Phase1.4 and reserved held-out suites are not rerun. The final reserved
96 clusters are proposed as24 per these four generators, with unseen-generator
transfer deferred; this changes the original six-mechanism aspiration explicitly.
No final-held-out layout or outcome is accessed in this phase.

## 8. Status and review gate

Standalone mathematical fixtures accompany this proposal; no full filter,
controller, policy, generator or navigation episode was implemented/executed.
The reviewed base is `6c1f649628b7c14aea59c33c9920da02afdcc3a0` on
`feature/phase1-4c-assessment`. Old documents/data remain unchanged.

The [standalone audit](../scripts/audit_phase1_5a2.py) passed26 rational tests;
[exact fixture evidence](../results/phase1_5a2/mathematical_fixtures.json) retains
fractions and decimal renderings. Reproduce in Ubuntu with
`python3 scripts/audit_phase1_5a2.py --test` (no navigation imports). The optional
`--output results/phase1_5a2` writes these small mathematical tables. Documentation
links, arithmetic, source hashes and frozen Phase1.4 lock/manifest hashes are
checked separately; this is not a rerun of the historical trace inventory.

Review approval is needed for the complete v0.2 architecture/prior/controller,
four generator populations and topology invariant, numerical/activation gates,
2,112-development/6,720-assessment maxima and resources. Actual artifact-only
topology audit and faithful mathematical component verification remain later
empirical gates. They are not undefined scientific defaults or claimed successes.
If a choice is rejected, amend it explicitly before implementation/data access.
Stop for scientific review before Phase1.5B implementation.
