# Phase 1.4 frozen candidate definitions and experimental protocol

Version 1, 2026-11-06. **Planning only; no implementation or new experiments.**
This is the candidate specification submitted for review, not authorization to
execute it. Review changes require a versioned amendment before assessment.
The [review](phase1_4_literature_review.md) and
[comparison](phase1_4_prior_work_comparison.md) define evidence/reproduction limits.
Phase 1.3 source/results and all existing configurations remain unchanged.

## 1. Question, assumptions and review gate

Hypothesis H1: with identical last-write maps, sensors, A*, dynamics and sensing
caps, route-disruption plus estimated visibility improves contact-free completion
over simple rate-matched and route-weighted controls on new development realizations.
H1 does not assert novelty, calibrated value of information, physical safety, or
that the policy learns transient-versus-persistent categories.

The potentially useful research question is **when does cheap decision sensitivity
remain informative under unmodeled occupancy change and unreliable visibility,
after rate and estimator effects are controlled?** The weighted score itself is
an obvious combination of existing ideas. ALONE directly constrains novelty claims;
no claim about absence of other prior solutions follows from nine reviewed works.

Retain Phase 1.3 world advance → decide/observe → plan/move ordering; step 0
observation is mandatory, charged, and shared. Sensing has zero simulated latency.
Robot pose is assumed known. Agents cannot access Scenario, world geometry,
pedestrian identity/schedules, change epochs, truth reachability, evaluator
metrics, future observations or another policy's realized call counts. No contact
or blocked-movement feedback is added to scheduler inputs in this first study.
Existing A* and movement semantics remain the common action controller, including
its deterministic tuple ordering in the heap and existing neighbor order. No
method-specific repair, contact avoidance or visibility-seeking motion is added.

**Explicit refinement from Phase 1.3's tentative design:** visibility is the soft
public-belief ray product below, route disruption is a normalized two-state
counterfactual, and unknown cells are included for the new heuristics. These are
new modeling choices for review, not established posterior probabilities or
silently inherited assumptions. They must be approved before implementation.

## 2. Common notation, outputs and budget

Grid has N cells; T=40 decisions after initialization, goal g, current pose x.
M_i ∈ {-1,0,1} is last-write occupancy. L_i=-1 means unknown. At time t let
F_i be observed binary flips and E_i accumulated time gaps between repeated
visible observations. Sensor radius R defines disk D(x); occlusion is never read
from the world by a policy. All new policies use the same public observation
history. A granted observation updates only returned nonnegative cells.

For known cells a_i=t-L_i and

r_i=clip((0.3+F_i)/(6+E_i), .01, .35),
p_i=.5+(p_i(L_i)-.5) exp(-2 r_i a_i),
p_i(L_i)=.95 if M_i=1, else .05,
H_i=-p_i log2 p_i-(1-p_i)log2(1-p_i).

Unknown cells use p_i=.5, H_i=1 in new heuristics. The original uncertainty trigger
still excludes them. These are public history proxies, not calibrated occupancy
posteriors. All new thresholds and priors are declared below; sensing noise does
not silently change this estimator. Walls are not given semantic certainty.

Each scheduler outputs a Boolean request plus logged components/reason. Common
controller grants only when the remaining capacity b=C-n is positive (b=∞ for
unlimited), increments calls n on grants, and counts denied requests individually.
Denied sensing never calls the sensor or resets history. Compute/log the ungated
request even at b=0 so denials remain interpretable; use b_eff=max(1,b) in threshold
formulas for finite caps. Initialization consumes one, so cap1 permits no later
calls. Each call costs c=1.5 resource units. A cap is a maximum, not an entitlement
to an identical realized count. All runs stop at goal or T as before.

For b=∞ use h/b_eff=0; for finite b use h/max(1,b).
Always use strict `>` for new heuristic score thresholds; historical Age and
Uncertainty retain `>=`. Exact ties in all action choices use existing A*;
new candidate cells are traversed in lexicographic (x,y) order, summed in that
order, with float64 arithmetic and no random jitter.

## 3. Frozen methods (twelve core rows)

All complexity bounds are per decision, additional to shared sensing and one
A* call O(N log N). New history arrays use O(N) space. K≤N is disk size. Existing
uncertainty code calculates arrays over N even though the score uses the disk;
report actual runtime rather than assuming local-only computation.

| ID | Observation request after initialization | Inputs beyond common time/cap | Extra worst-case computation |
| --- | --- | --- | --- |
| static | Never | None | O(1) |
| age | Mean of 1[a_i≥4] over known D(x) ≥ .5; empty set: false | x, R, visible timestamps | O(N) with current footprint code |
| uncertainty | Mean H_i over known D(x) ≥ .75; empty set: false | x, R, F/E/L/M | O(N) |
| periodic1 | t mod 1=0 | None | O(1) |
| periodic2 | t mod 2=0 | None | O(1) |
| periodic5 | t mod 5=0 | None | O(1) |
| fixed-rate | Same known-disk entropy rule, but r_i=r0 constant for every cell/time; no flip adaptation | x,R,L,M | O(N) |
| random-quota | Membership in precommitted random times A | Own RNG/time, configured C,T | O(T) initialization, O(1) lookup |
| quota-periodic | Membership in precommitted evenly spaced times A | Configured C,T | O(T) initialization, O(1) lookup |
| route-weighted | S_RW > θ_RW | g, M, p/H, current remembered route | O(N+K) after common A* |
| disruption-visible | S_DV > θ_D c + λ h/b_eff and visible mass ≥ .25 | g,M,p, ray geometry, route costs | O(K N log N + K R) |
| query-gate-conceptual | Nominal/confidence-masked routes have different next cells, mask increases cost ≥1, and low-confidence nominal support is sufficiently visible | g,M,p, ray geometry | O(N log N + K R) |

### Fixed rate and valid precommitted matching

Fixed-rate defaults: r0=.05, entropy threshold .75; refresh resets p exactly as
above. Its r0 and threshold have the nine tuning candidates in §5. It retains
known-only scoring so history adaptation is the sole structural difference.

For finite cap C, set Q=min(C-1,T). Random-quota samples Q distinct integers
uniformly without replacement from {1,…,T}, sorted before execution. For unlimited
set Q=8. Use five scheduling replicates with distinct stream IDs, shared across
all comparisons and averaged within an environment. Seed stream is derived from
(root environment seed, 1404, replicate ID), independent of sensing noise/generation.
No schedule depends on hidden events, future success or other methods.

Quota-periodic uses the same Q; A={floor(j T/Q):j=1,…,Q} when Q>0, else empty.
These times are unique since Q≤T. It provides an evenly spaced control for the
same maximum quota as random; goal termination can still shorten either schedule.
Unlimited random/quota rows have a deliberate quota of nine total calls including
initialization, unlike an always-sense unrestricted controller. Label that distinction.

Offline matching may compare frontiers at similar observed cost or stratify paired
results by *precommitted* cap. Never use a task policy's realized future count to
set an online random/periodic schedule. A retrospective schedule using that count
must be labeled a hindsight diagnostic, excluded from primary comparisons; none
is planned here. Unmatched realized calls must be reported, not hidden as “equal
budget”. No subset selection based on success or realized call count is primary.

### Route-weighted heuristic

P is deterministic A*(M,x,g) with optimistic unknown cells, including x and goal.
For i∈D(x), w_i=1+α 1[i∈P], and

S_RW = (sum_i w_i H_i)/(sum_i w_i).

If D is empty, request false; if no P, all w_i=1. It includes unknown cells and
has no visibility model or budget-dependent price. Defaults α=3, θ_RW=.75.
It never changes map occupancy or movement; request obeys the common cap.
The route-weighted comparison separates a simple spatial heuristic from expensive
counterfactual consequences, although unknown inclusion is an additional difference
from the historical baseline; the ablations isolate it.

### Proposed disruption-visible heuristic

For i∈D(x) except current x, let M^{i,z} overwrite just cell i with z∈{0,1}.
Let J be A* path length or N+1 when no remembered route exists (including an
occupied goal). Define

D_i = min(N, |J(M^{i,1},x,g)-J(M^{i,0},x,g)|)/N,
q_i = p_i if M_i=0; 1-p_i if M_i=1; .5 if M_i=-1.

For a supercover ray from x to i, let B(x,i) be the unique intervening cells,
excluding x and i. Use the existing `line_cells` geometry; no sensor call is
made to estimate it. Predicted revealability is

V_i = 1[i∈D(x)] product_{j∈B(x,i)}(1-p_j).

An empty product is 1. Unknown blockers contribute .5; remembered occupied
blockers are uncertain under the same decay model. This independent-ray proxy
is deliberately approximate: no assertion of calibrated visibility or a static
wall label is made. It predicts *being returned*, not *correctness under noise*.

S_DV = sum_{i∈D(x),i≠x} V_i q_i D_i.

“Visible mass” is sum V_i over those candidates; if empty, request false.
All occupied/free/unknown disk cells are candidates, including off-current-route
cells that might reopen alternatives. This is counterfactual sensitivity, not
Bayesian VOI; single-cell effects can double-count or miss joint changes.
Set h=max(1,J(M,x,g)) when a path exists; if none, h=N+1. Defaults θ_D=.1,
λ=.1. Candidate grid in §5 is fixed in advance. There is no hidden cooldown,
unbudgeted emergency refresh, true-geometry shortcut or no-route repair.

### Public-belief query gate (conceptual comparator)

Define rhat_i=max(p_i,1-p_i) for known cells, .5 for unknown cells. This proxy is
not supervised reliability. Construct M_mask by treating cells with rhat_i<τ as
occupied, except current x, and retaining every remembered occupied cell.
Compute nominal P=A*(M) and masked P_mask=A*(M_mask); no path has cost N+1 and
its next cell is the wait cell x. A route of length zero also next= x.

Let U={i∈P: i≠x and rhat_i<τ}. Request iff U nonempty, next(P)≠next(P_mask),
J(M_mask)-J(M)≥1, and (sum_{i∈U} V_i)/|U|≥η. Use the same V, cap and
last-write movement controller; if no nominal route, request false. Defaults
τ=.9, η=.5. These grid-specific choices are ours. They do not reproduce ALONE's
full decision rule, estimator, forced refresh or motion execution. Calling this
a faithful implementation is prohibited; see the comparison's conditional slot.

## 4. Faithful published-method slot

No faithful end-to-end scheduler has been verified feasible under the common
interfaces; do not count this as a thirteenth implemented method. P1/P3/P4/P5/P6
have estimator, sensing, data or action-space mismatches; P7/P9 are temporal
estimators. Before any faithful comparator is added, an approved amendment must
identify the exact publication/version, equations, artifacts/licenses and missing
details, training split and inputs, cap adaptations, computational resources and
paper sanity-check replication. Substituting an entropy/ray heuristic is never
called reproduction. If the slot stays empty, claims remain limited to conceptual
controls. This unresolved comparison is an implementation review gate.

## 5. Development tuning and fresh assessment

No new data is generated by this documentation task. Future manifests are created
only after approval using the Phase 1.3 generator frozen at the source hash in
its validation report; existing Phase 1.3 outcomes are diagnostic context only.
Seven existing development families remain. Reserve every existing held-out
configuration and do not use it for manifest selection, tuning or testing.

Tuning: five fresh accepted realizations per family (35), seed candidates 10000,
10001,… in ascending order independently per family. Assessment: ten per family
(70), candidates 20000,20001,… . Reject candidate seeds used by earlier stored
experiments. Canonical environment hashes omit name, seed and split but include
all geometry, start/goal, obstacles, ordered pedestrian paths and change events.
Reject duplicates across earlier runs, tuning and assessment, as well as invalid
final topology, by a predeclared evaluator-only audit. Keep every rejection reason;
never reject for method success, collision, observation count or difficulty.
Do not run any policy during manifest selection. If 10,000 candidates per family
cannot meet the count, stop for an amendment, do not silently relax duplication.

Seed disjointness alone is insufficient. Repeat truth audits record initial/event/
final persistent reachability, without filtering temporary contacts/deadline
performance. Truth manifests stay on the evaluator side; policy constructors
receive only allowed inputs. Related layouts may occur in both sets: this is
unseen-realization assessment, **not** proof of unseen-topology generalization.
Record a second layout hash over dimensions/walls/start/goal for clustering.
A stronger topology-disjoint claim requires a separately reviewed generator/split.

Tune only four new deterministic methods: fixed-rate, route-weighted,
disruption-visible and query-gate, nine configurations each:

| Method | Preregistered Cartesian candidates (nine) |
| --- | --- |
| fixed-rate | r0∈{.01,.05,.15}, threshold∈{.65,.75,.85} |
| route-weighted | α∈{1,3,9}, θ_RW∈{.65,.75,.85} |
| disruption-visible | θ_D∈{.025,.1,.4}, λ∈{0,.1,.4} |
| query-gate-conceptual | τ∈{.8,.9,.97}, η∈{.25,.5,.75} |

For each candidate use the same 35 tuning environments, caps 2/4/8 and noiseless
radius3/occlusion-on condition: 35×3×9=945 episodes per tuned method, 3,780 total.
Historical baselines remain frozen; no outcome tuning of Age/Uncertainty/Periodic.
Choose one global candidate per method by descending mean contact-free completion,
then descending completion, ascending all-episode call mean, ascending elapsed
steps, then lexicographic parameter tuple in table column order. Weight families
and caps equally. No family-specific tuning, conditional winning rule or runtime
exception is allowed. Publish every candidate result. Lock a parameter manifest,
source/data hashes and analysis script before unlocking assessment outcomes.
Retain the default candidate results in tuning reports; do not call tuning scores
evidence of generalization. New-method search effort is equally bounded, but
historical baselines receive no new tuning; state that limitation explicitly.

Assessment: all 70 worlds × caps {1,2,4,8,16,unlimited} × two sensor conditions:
(radius3, occlusion=true, noise0) and the same with noise .05. Same environment
and per-time sensor streams are paired across methods. Five random schedule
replicates are averaged per world/condition/cap; other methods run once.
Twelve core methods give 70×6×2×(11+5)=13,440 episode executions, not 13,440
independent samples. No parameter sweeps on assessment; larger radius, cost,
prior or timing experiments require amendments or are descriptive Phase 1.3 data.
Runtime cap remains T=40. No policy observes the assessment seed as a schedule
encoding; seeds only initialize controlled independent RNG streams.

## 6. Outcomes and paired analysis

Primary endpoints, each all-episode: contact-free goal completion (success and
zero dynamic contacts), goal completion, number of observations including initial,
and cost=1.5×count. Cost is an accounting scalar, not observed battery energy.
A higher priced sensing objective changes only policies whose request rule
contains c; a cost sweep would require a separate locked comparison. Plot success
and contact-free success versus actual mean cost for **all** caps/methods;
connect only a method's own predeclared cap points. Do not select the best cap
per method after observing outcomes or infer equivalence from equal caps alone.

Secondary: blocked movement attempts, dynamic contacts/count per elapsed step,
successful moves/path length, elapsed steps, legacy cumulative and terminal
persistent-map errors, common-horizon errors with terminal memory frozen through
T=40, denied requests, budget exhaustion, feasibility error and runtime. Legacy
collision_count is a compatibility sum, not a physical collision measurement.
Common-horizon sums have 41 cell-time sampling instants, not 41 independent events.
No observation is credited with revealing a change merely because it follows it.

Feasibility accuracy: before each actually granted noninitial observation, log V_i
for disk cells and compare with 1[returned ternary cell≠-1]. Report Brier score,
mean absolute error, and five fixed calibration bins [0,.2),[.2,.4),[.4,.6),[.6,.8),
[.8,1]. Exclude empty bins, report their counts. For denied/unsensed steps there
is no policy-visible label; any evaluator-only hypothetical-mask audit must be
reported separately as such and never feed the agent. Evaluate known/unknown
ray blockers separately. Cluster cell-level measurements by topology/environment;
cell-rays are not independent samples. The trigger may depend on its predictions,
so sensed-only calibration has selection bias and cannot establish global accuracy.

Runtime: single process, fixed hardware/Python/dependencies, no rendering timed;
record per-decision scheduler and common planner durations separately with a
monotonic high-resolution clock, plus total episode runtime. Include denied
request decisions. Report per-environment median and 95th-percentile decision
latency, warm-up policy (one untimed synthetic call per method), and planning calls.
No simulated world deadline or sensing semantics changes due to wall-clock timing.
If one method is too costly to complete the locked matrix, publish missing cells
and stop for review rather than lower its computational load post hoc.

For each environment/cap/sensor condition compute paired method differences;
average the five random schedules first. Equal-weight average environments within
family, then average seven families equally. Predeclared confirmatory contrast:
disruption-visible minus route-weighted contact-free completion at cap4/noise0.
Report analogous goal/call/cost differences and all other comparisons as secondary,
with descriptive pointwise intervals rather than selectively significant claims.
A 5 percentage point absolute gain is the prespecified smallest useful benefit,
not a power guarantee. No secondary p-value tests are planned. Secondary intervals
are descriptive and pointwise, not simultaneous evidence of superiority; any
additional confirmatory contrast or multiplicity procedure requires an amendment
before assessment access.

95% intervals: cluster bootstrap, 10,000 replicates with fixed analysis
seed 1404001. Resample the global list of unique layout-hash clusters with
replacement, retaining all their environment schedules, families, methods, caps,
sensor conditions and random replicates together. This also keeps a layout reused
by different families in the same resampling unit. Recompute the same equal-family
weighted paired statistic, allowing unequal cluster sizes within each family;
redraw any replicate missing a family and report that count. Stop without CIs if
100,000 attempts cannot produce 10,000 complete replicates. Report
percentile .025/.975 bounds, unique cluster counts and bootstrap degeneracy.
Repeated settings or deterministic duplicates never increase cluster count. If
fewer than 30 total independent layout clusters or a family has only one, report
point estimates, cluster counts and sensitivity ranges without inferential claims.
Seven families are fixed strata, not a population sample of all possible scenario
families. Leave-one-family-out point estimates expose family dependence; they are
not confidence intervals. Topology clustering addresses dependence conservatively,
but cannot justify unseen-family or physical-world generalization.

Do not call failure to reject zero a proof of equivalence. Binary all-success or
all-failure strata can give degenerate bootstrap intervals; report that fact.
If the main CI excludes zero with gain≥.05 and no cap1 or schema violations, the
route-weighted comparison supports that component of H1 *within this assessment*.
It does not alone establish superiority over the other controls. If its upper bound is <.05, the proposed
practical benefit is falsified for this setting. Otherwise evidence is inconclusive.
A gain only against generic uncertainty, disappearing against route-weighted,
quota-periodic or query-gate controls, does not support the extra complexity.

## 7. Frozen ablations

Use the selected disruption-visible parameters unchanged; do not retune ablations.
On all 70 assessment worlds, cap4 and cap8, both sensor conditions (280 episodes
per ablation; six rows=1,680 additional executions):

| Ablation | Exact replacement; all other behavior fixed |
| --- | --- |
| No route disruption | D_i=1 for every eligible disk cell |
| No visibility | V_i=1 in both score and visible-mass gate |
| Fixed rate | r_i=.05 in p_i; keep all other history/timestamps |
| Exclude unknown | Remove M_i=-1 from score, mass and candidates; unknown ray blockers still .5 |
| No budget threshold | λ=0; retain shared cap and θ_D c |
| No alternative candidates | Eligible candidates restricted to current nominal P excluding x; empty P means no request |

The unknown ablation changes only candidate inclusion; treating unknown as free
in visibility would be a different ablation. The alternative-route ablation also
removes off-route free cells: do not attribute its effect solely to occupied
shortcuts without inspecting the prespecified candidate logs. Keep every result,
including interactions and null effects. The six rows isolate mechanisms only
under the selected parameters and do not prove additive causal contributions.

## 8. Reproducibility, acceptance and transfer limits

Before later implementation acceptance, test budget accounting, exact threshold
and tie cases, RNG independence, duplicate/reachability audits, denied requests
without refresh, sensor-history-only inputs, counterfactual no-route cases,
unknown-cell handling, visibility blockers and computational counters. Regression
must retain all Phase 1.0–1.3 historical metric values. Add paired evaluator checks
without changing baseline or collision algorithms. Manifest/source/config hashes,
chosen parameters, complete candidate results and package/runtime metadata must
accompany any later result. Preserve original result paths and held-out files.

Likely failures: hard caps exhausted before a late change; noise written as a
persistent obstacle; unseen cells mispriced; false remembered occluders; independent
ray assumptions; simultaneous multi-cell changes; no-route abstention; transient
occupancy producing repeated sensing; runtime dominated by counterfactual A*.
The simplest adequate result may be quota-periodic or route-weighted entropy;
that is a useful negative finding, not grounds for adding post hoc heuristics.

For MuJoCo Unitree G1, first add real sensor timing/noise/field of view and pose
uncertainty, timestamps/latency, robot volume and swept-body/footstep traversability,
walking-controller feasibility, stopping/recovery behavior, moving-human geometry
and separate physical contact/fall metrics. Define observation cost empirically
and keep trained walking/perception dependencies distinct from scheduling. A
kinematic grid contact-free score provides no evidence of stable locomotion or
human safety. None of these extensions is implemented or assumed in H1.

Review must decide: is the surrogate comparison sufficient; is a published-system
reproduction required; are the soft visibility and unknown assumptions acceptable;
is the matrix affordable; and are cluster counts sufficient for inference? This
version freezes a concrete reviewable proposal; implementation remains **not yet
approved**, and no assessment/held-out outcome has been used to tune it.
