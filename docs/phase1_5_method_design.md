# Phase 1.5 method design

Proposed specification v0.1, 2026-11-07; design only, pending research review.
Read with the [evidence review](phase1_5_research_review.md) and
[protocol](phase1_5_experimental_protocol.md). None of the algorithms below has
been implemented, benchmarked or validated. Mathematical properties refer to
the declared model, not to unknown real-world occupancy.

## 1. Public information and common decision interface

At time t, H_t contains poses, executed actions, returned local observation arrays
(including not-returned entries), observation times, goal, grid bounds, sensor
configuration, horizon, observation price and remaining cap. It excludes Scenario,
true occupancy, event schedules, obstacle identity, future observations, contact
labels, evaluator reachability, topology identifiers and seeds. Executed pose
changes can reveal a failed move; no extra privileged blocked/contact flag is
provided. All policies receive the same interface and initial charged observation.

Let Z_t be binary occupancy of the whole grid and b_t a joint predictive model
over W=(Z_t,Z_{t+1}). Unknown is epistemic uncertainty, not a third physical state.
The observation Y includes the complete radius-3 return and missingness mask.
Its likelihood must model occlusion and configured bit noise jointly. Treating
the missingness mask as uninformative would discard evidence; multiplying
independent marginal visibility probabilities is not the proposed likelihood.

All Phase 1.5 schedulers use a shared probabilistic motion controller. This is a
new experimental stack; legacy gate ports are not historical end-to-end results.
For each a in {wait, north, east, south, west} that stays in bounds, particle W_j
predicts the resulting pose x'_j(a), leaving the robot in place on a blocked move.
Use deterministic listed-order tie breaking and

```
Q_j(a) = 0.1 * blocked_in_Zt(a)
       + 1.0 * I[Zt(x'_j)=0 and Zt+1(x'_j)=1]
       + 0.005
       + min(1, d_Zt+1(x'_j, goal) / max(1, T-t)).
```

At the goal, terminate rather than apply this expression. An unreachable goal
has terminal distance penalty 1. Reverse breadth-first search provides all
distances per particle. Occupied current cells can be departure nodes; an occupied
goal is unreachable unless the episode has already terminated. This convention
must be tested rather than silently repaired by optimism. The action is
argmin_a sum_j w_j Q_j(a). The bound is 0 <= Q <= 2.105. These coefficients
are proposed utility conventions, not fits to Phase 1.4 assessment outcomes.
The entry term is a one-step hazard proxy, not a calibrated contact probability.
The distance term is short-horizon navigation relevance, not true completion
value. Bias from this proxy is a major falsifiable limitation.

Actual world advancement/contact accounting retains a single shared physics
implementation. Only the proposed shared planner/model changes. The old A* stack
and every frozen Phase 1.4 artifact remain untouched.

## 2. Common joint belief model: bounded approximation

Propose 64 weighted whole-map particles. A minimal temporal prior uses binary
2x2 occupancy tiles (16 local states), four offset tilings in a fixed mixture,
and one transition matrix shared across tiles. This permits some coordinated
changes without semantic pedestrian or event labels. Cross-tile dependencies,
large moving objects and long memory can be badly represented; the model is not
a general dynamics solution. Mixture components and complete sensor likelihoods
induce correlations beyond independent-cell marginals, without making them
correct by construction.

Fit transition parameters only to public development-fit observation histories,
using the clear-view conditions and time-gap transition powers. Proposed fitting
is 50 fixed EM iterations with Dirichlet-one smoothing and deterministic starts;
neither true change epochs nor true occupancy may be fitting targets. Configured
sensor noise is in the likelihood. Occluded development-calibration streams test
generalization rather than provide hidden-state supervision. Noisy/missing-data
identifiability and spatial prior initialization need review before implementation.

Filtering proposes from the temporal model, weights the entire returned array
and mask, resamples at effective sample size below M/2, then performs four fixed
local rejuvenation sweeps preserving that posterior target. A future specification
must give exact proposals, initial occupancy prior and tiling-boundary handling
before any development episode. Zero observation support is a model failure,
not permission to consult true occupancy or reset to a truth-derived map.
Log effective sample size, likelihood normalizers and support failures. Thus this
is a bounded model proposal with explicit unresolved interface details, not an
implementation-ready inference claim.

Maintain the Phase 1.4 last-write/age/flip summaries in parallel for legacy gates.
Every scheduler gets access to the same public history; all use the same joint
belief for the common controller. No scheduler receives a private better map.

## 3. A: decision-aware value of sample information

Define Bayes risk and sensor value in the same task-loss units:

```
R(b) = min_a E_b[Q(a,W)]
V_S(b) = R(b) - E_{Y~p_theta(.|H)} R(b(.|Y))
V_PI(b) = R(b) - E_b[min_a Q(a,W)].
```

For a fixed action set, coherent exact inference and the same Q before/after
sensing, 0 <= V_S <= V_PI <= 2.105. The lower bound follows because the
post-observation decision can retain the pre-observation action; the upper
bound follows because perfect state information is at least as informative as
the sensor. This is model EVSI, not information entropy or a guarantee of better
goal completion. It excludes future sensing adaptation beyond Q's short horizon.

Proposed finite-model estimator:

```
particles, weights = common_filter.predict(H)
Q = common_action_loss_table(particles)       # fixed across imaginary observations
r0 = min_action(weighted_mean(Q))
for k in 1..J:
    j = sample(weights, counter_rng(t,k,"world"))
    y = sample_actual_sensor_model(particles[j], counter_rng(t,k,"sensor"))
    post[j'] proportional_to weights[j'] * joint_likelihood(y | particles[j'])
    delta[k] = r0 - min_action(weighted_mean(Q, post))
value = mean(delta)
se = sample_standard_deviation(delta) / sqrt(J)
request = value - 2*se > observation_price
grant only if remaining_cap > 0
if granted: update from real public return; recompute common action decision
else: use current common action decision
```

Imaginary observations come from the agent's finite model, never the evaluator's
future sensor. The same particle bank defines the prior, likelihood and risks.
Individual deltas and Monte Carlo estimates may be negative; store raw values,
do not clamp them to hide numerical/model problems. The two-SE margin is a
computational heuristic, not a certified confidence bound on real-world value.
Use counter-based streams independent of world and observation noise streams.

J is selected from 64,128,256 by the development-only precision/resource gate,
choosing the smallest passing value, not the highest navigation score. J and all
model parameters are locked before assessment. No adaptive assessment increase,
fallback threshold or clipping is permitted. Observation price is .02 task-loss
units in the primary condition, with .005 and .08 predeclared sensitivity values.
No grid-area division is applied to either value or price.

Closest prior art is decision-conditioned sensory value and active measuring;
see [the reviewed primary sources](phase1_5_research_review.md#verified-prior-art-and-overlap).
The proposed difference is a partial/noisy/occluded local-sensor value estimate
with a shared short-horizon grid controller and explicit timing controls. It is
an adaptation whose novelty remains uncertain, not a new definition of VoI.

Falsifiable predictions: irrelevant uncertainty yields zero value; informative
joint observations can change the selected action; high noise/occlusion reduces
value when it makes decisions less distinguishable. These are exact claims only
in controlled finite fixtures. In navigation, A should improve completion beyond
quota timing without a material call-count increase, and improve the exactly
one-call timing assay. Failure of either test limits a task-awareness claim.

Failure modes include underestimated alternative routes, absent particle support,
incorrect visibility, correlated observation errors, myopic progress traps and
poorly scaled hazard loss. Model value can confidently select a wrong action.

## 4. B: multi-cell counterfactual route sensitivity

For an intentionally simpler comparator, use at most eight public 2x2 blocks
within the radius-3 query footprint and remembered route neighborhood. Rank by
public uncertainty times route proximity, with fixed index ties. Enumerate each
block's at most 16 joint states from the common belief. Let M be the last-write
map with fixed optimistic unknown handling and let h=max(1,T-t). Define

```
S_B = sum_blocks E_b[ return_fraction(block,Y)
                     * abs(d(M with block state)-d(M)) / h ] / number_of_blocks.
```

Distances are truncated at h, including unreachable cases; an empty block set
gives zero. Return fraction is estimated under the same modeled sensor, not truth.
The single global threshold is chosen on calibration histories to match A's
noninitial request rate as closely as possible (absolute difference, then larger
threshold tie break); no goal/contact outcome enters this choice. Store the full
threshold/rate curve. Fix this one match before assessment; realized assessment
counts need not match and must be reported. This is not an optimal cost rule.

Multi-cell changes can open a bypass that no individual flip opens. Nevertheless,
route-distance change can be irrelevant to the next decision, groups can overlap
effects, and dependence between blocks can be missed. Thus B is a comparator for
representation versus decision relevance, not the recommended primary method.
Particle/scenario POMDP work already reasons jointly about multiple latent
variables. Expected prediction: B beats a single-cell version in joint-change
fixtures but need not beat A on matched timing. A failure there rejects the
specific grouping rule, not joint reasoning in general.

## 5. C: budget-aware extension

The full objective is
`min_pi E_pi[sum_t ell(W_t,a_t) + c_s * sum_t u_t]`, with
`sum_t u_t <= b_initial`, where u_t is a granted sensing decision. In a
belief-state Bellman equation, let F_t(belief,b) be optimal remaining loss and
G_t(belief,b) the minimum control loss plus predicted F at the next time, without
another observation at this time. Then
`F_t(belief,b)=min{G_t(belief,b), c_s+E_Y[G_t(belief|Y,b-1)]}` for b>0,
and F_t=G_t when b=0. Future observation opportunities create a shadow price.
The earlier Q is a tractable surrogate for G, not its exact solution. Exact
optimization over continuous beliefs and long horizons is outside this proposal.

The declared approximation adds

```
kappa(t,b) = .25 * c_s * max(0, (T-t)/max(1,b) - 1)
request iff Vhat - 2*SE > c_s + kappa(t,b).
```

Log the ungated request even at b=0, but never grant it. The coefficient .25 is a
proposed nonzero convention for review, not selected on assessment. C is not an
optimal budget policy. It may suppress all useful early calls or spend them too
late. Prediction: at scarce budgets C retains more late opportunities and can
improve cost/completion tradeoffs; at abundant budgets its difference from A
shrinks. No improvement or an inactive C is an informative negative result.
The zero-price-extension ablation is already A; do not duplicate it as a new row.
Active measuring and robust active measuring are the closest cost-sensitive
precedents, without transferring their assumptions or guarantees to this model.

## 6. Computational and implementation costs

With M particles, J imaginary observations, N grid cells, K returned-footprint
cells, ray length R and A<=5 actions, common reverse BFS/action-loss work is
O(MN), sensor likelihood work approximately O(JMKR), and posterior decision work
O(JMA). Four fixed rejuvenation sweeps add O(MN) local updates, with constants
depending on occlusion likelihood maintenance. B costs up to O(8*16*N log N)
for route recomputations plus sensor estimates. C adds O(1) to A. A V_PI comparator
uses O(MA) after common Q computation, but can greatly overvalue an occluded query.

For M=64, J=64, K<=29, R=3, N<=625, work is plausibly hundreds of thousands to
millions of primitive operations per decision. That is an operation estimate,
not a Python runtime prediction. Stream imaginary returns; working arrays need
O(MN+MA+M+K) space, excluding fitting, trace buffers and implementation overhead.
Development gates cap incremental scheduler p95 at 100 ms, shared planner/filter
p95 at 100 ms and peak process RSS at 512 MiB on declared hardware. No claim
that these limits are presently achievable is made.

Engineering estimates assume one experienced contributor: 3–5 weeks for A's
shared model/controller and verification; 1–2 further weeks for B and about one
for C, with overlap. Partition generation/audit, independent verification and
evaluation infrastructure can add 2–3 weeks. These are planning ranges, not
commitments. The protocol's full future matrix can require days of CPU time and
hundreds of GB of traces; Phase 1.4 runtime must not be extrapolated blindly.

## 7. Numerical and behavioral safeguards

Before assessment, exact finite development fixtures must establish:

- Zero EVSI for known states, irrelevant uncertainty and a fully uninformative
  sensor; .5 EVSI for equiprobable opposite-action states with losses 0/1 and a
  perfect query. The latter must cross the .02 price.
- A four-state parity fixture: each individual bit has zero decision value,
  while observing both reveals the correct action and has value .5. This tests
  joint versus single-cell reasoning without any navigation outcome.
- Correct missingness likelihood, noise limits, posterior normalization and
  V_S<=V_PI; exact arithmetic comparisons on enumerable small models.
- Invariance to appending irrelevant inaccessible grid cells; finite unreachable
  costs; consistent loss/price rescaling; no hidden grid-area score division.
- Cap exhaustion, denials, deterministic ties and replay after interruption.

Calibration-only histories additionally test sensor-return probabilities,
occupancy prediction, numerical precision, activation and behaviorally different
ablations under the protocol's locked criteria. Legitimately useless observations
must remain declined; activation gates are not a requirement to sense everywhere.
Any failed gate stops the current design before assessment. A revised design
requires a versioned review and fresh development validation, never retrospective
repair of assessment results.

## 8. Humanoid compatibility and unresolved decisions

The interface can later replace five grid actions with candidate body motions
and Q with a locomotion-aware critic. That compatibility is conceptual: continuous
pose uncertainty, foot support, 3-D occlusion, sensor motion, latency, energy and
catastrophic falls are absent here. Sensing may itself change the physical state,
invalidating the fixed-Q, free-instant-query assumption. MuJoCo/G1 will require a
separate preregistration and safety validation.

Review must resolve the initial spatial prior/proposals, whether a new shared
planner is justified, utility coefficients and price scale, practical model
calibration tolerances, code fidelity of any published comparator and resource
budget. These open issues are explicit blockers to an implementation-ready lock.
No method is authorized for implementation by this document.
