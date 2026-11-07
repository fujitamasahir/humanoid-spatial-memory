# Phase 1.5A design and mathematical audit

2026-11-07. Review of the unchanged Phase 1.5 [research review](phase1_5_research_review.md),
[method design](phase1_5_method_design.md) and [protocol](phase1_5_experimental_protocol.md).
Labels below distinguish **verified** source/finite-table checks, **deductions**,
and **proposed amendments requiring review**. No scheduler, filter or navigation
experiment was implemented. Mathematical audit code and synthetic measurements
are in [the standalone audit](../scripts/audit_phase1_5a.py) and
[evidence JSON](../results/phase1_5a/mathematical_audit.json).

## Findings and disposition

The original proposal is not implementation-ready. Exact EVSI is well defined,
but its finite-bank estimator, real observation update, forecast handling and
controller must be reconciled. A precise joint-belief proposal is given below;
it is a new scientific proposal, not an interpretation silently applied to v0.1.
Topology generation remains blocked by missing definitions. Power favors an
estimation-focused first study. Synthetic kernel timings do not clear the full
model's runtime gate. See the [topology audit](phase1_5a_topology_audit.md),
[power analysis](phase1_5a_power_analysis.md),
[feasibility report](phase1_5a_feasibility.md) and
[recommendation](phase1_5a_protocol_recommendation.md).

| Issue in v0.1 | Finding | Proposed disposition |
| --- | --- | --- |
| Four offset tilings | Global versus per-time/per-tile mixture is unspecified. | One latent offset per environment history; posterior mixture weights evolve. |
| Boundary tiles and spatial prior | No distribution or padding transition was defined. | Explicit restricted-state boundary kernel below; no truth-derived walls. |
| Dirichlet-one smoothing + EM | Uniform Dirichlet MAP has no add-one smoothing. | Explicit Dirichlet-two MAP/add-one update; this changes the proposal. |
| Bootstrap initialization | A noiseless 29-bit return can miss all 64 iid particles. | Observation-adapted tile proposal, with importance correction and explicit residual mask failure. |
| Rejuvenation | Target and updated variables missing. | Conditional current-tile Gibbs plus optional exact offset Gibbs on stored paths, defined below. |
| Fixed W=(Z_t,Z_t+1) table | Valid finite decision problem, but one forecast per state can make future dynamics spuriously inferable from a query. | Integrate conditional forecasts; distinguish current-state from future-perfect information. |
| Real observation refresh | Rebuilding particles/losses before acting can change the controller that imaginary queries evaluated. | Choose a coherent architecture explicitly; no exact-EVSI claim for an unmatched approximation. |
| Two-SE gate | Conditional outer Monte Carlo error only, not filter/model/forecast error. | Precision diagnostics and an explicitly limited uncertainty statement. |
| Difference-of-risks sampling | Samples can fluctuate even when the same action is optimal after every observation. | Consider posterior advantage over the prior-optimal action, defined below. |
| Initial observation/timing | Initialization is t=0; ordinary decisions occur after the next world advance. | Declare states and assay fork times exactly, below. |
| Resource/deadline gate | Logging a failure is not a defined controller continuation; 'all rows deterministic' ignores estimator RNG. | Lock RNG in method identity; abort/support/deadline behavior must be preregistered. |

## Exact decision-theoretic identities

Let p(w) be a normalized belief, A a fixed finite action set, L(a,w) a bounded
loss, and K(y|w) a normalized observation channel including missingness. Define

```
r(p) = min_a sum_w p(w)L(a,w)
m(y) = sum_w p(w)K(y|w)
p(w|y) = p(w)K(y|w)/m(y), only for m(y)>0
V_S = r(p) - sum_y m(y)r(p(.|y))
V_PI = r(p) - sum_w p(w)min_a L(a,w).
```

**Deduction:** 0 <= V_S <= V_PI <= L_max-L_min. Taking the prior-optimal
action after every y proves the first inequality; revealing w can emulate any
decision based on y, proving the second. Zero-mass observations contribute zero
to the expectation, but conditioning on one is undefined. There is no posterior
repair by dividing by epsilon or substituting a uniform distribution.

For the original loss, [0,2.105] is a safe bound, although its terms need not
simultaneously attain their maxima. If a common optimal action exists for every
positive-probability posterior, EVSI is zero even when entropy is large. Action
switching among tied minimizers is not positive value. A finite-table test gives
EVSI .5 for a perfect binary query, .45 at bit-error .05, zero for an uninformative
query, and zero individual-bit/.5 joint-bit value in the parity example. Two
hundred synthetic random decision tables also satisfy the bounds within 1e-12.
These checks validate identities and examples, not navigation usefulness.

Higher noise decreases value only when the new channel is a garbling of the
old one with the same prior/actions/loss (a Blackwell ordering). 'More occlusion'
need not be ordered this way: changed missingness itself can convey information.
Replace v0.1's informal monotonicity prediction with that conditional statement.

### Finite estimator and uncertainty

Conditional on fixed particles w_j, normalized weights, fixed L_j(a) and exact
K, sampling iid Y from their own predictive mixture gives an unbiased outer
estimate of **that finite decision problem's EVSI**. Posterior normalization
uses log-sum-exp; a sampled Y must have finite support at least at its generating
particle. Weight underflow is numerical failure, not model evidence.

This does not make the estimator unbiased for the underlying continuous/full-map
belief. Self-normalized importance weights, filtering, fitted transitions, finite
forecasts and minimization introduce approximation error. No simple universal
sign of the resulting total bias is available. Reusing a fixed Q bank avoids
one source of inconsistent nested minimization; it does not remove model error.

**Explicit estimator amendment for review:** let a0 be the prior-optimal action,
and sample `g(y)=E[L(a0,W)|y]-min_a E[L(a,W)|y]` instead. The tower property
gives `E[g(Y)]=V_S` for the same coherent model. Each g is nonnegative and is
exactly zero when a0 remains optimal; it avoids artificial Monte Carlo activation
from a fluctuating posterior baseline in that null case. This is an algebraically
equivalent finite-model target, not a new method or a guarantee of uniformly
smaller variance. It requires the same fixed loss and posterior consistency.
Do not clamp the original deltas and call that this estimator: that would bias
the estimate. Retain distinct diagnostic names for original delta and proposed g.

Individual deltas can be negative even though exact EVSI is nonnegative.
`sample_sd(delta)/sqrt(J)` estimates conditional iid outer Monte Carlo SE; it
does not cover estimated parameters, particle depletion, common forecast errors
or navigation sampling uncertainty. With a rare informative event of probability
.001, J=64 misses it with probability .999^64=.9380; the empirical SE can be
zero while value is not. A two-SE lower margin has no reliable small-sample
coverage in that case. Do not describe it as a confidence interval for true value.
As a distribution-free but pessimistic numerical alternative, deltas lie in
[-2.105,2.105], giving Hoeffding halfwidth
`4.21*sqrt(log(2/alpha)/(2J))`, about .715 at J=64, alpha=.05. This cannot meet
the .01 precision goal at those J values in the worst case. The precision gate
therefore needs distribution-specific validation, not an assumed guarantee.
For the proposed g estimator the bounded range halves, but rare-event failure
remains: a perfect query about a .01-probability opposite-action state with
loss2.105 has value .02105, above price .02, yet64 samples miss that state with
probability .99^64=.5256 and then report g=SE=0. No finite-sample precision gate
may treat zero empirical SE as sufficient evidence of correctness.

**Amendment proposal:** retain raw estimates and SE for diagnostics, freeze J
using development-only replicated numerical error, and label the margin a
heuristic. Test rare-event cases explicitly and report missed positive values.
Do not silently increase J or change price after assessment.

## Source-verified observation and transition semantics

Read-only inspection of [Sensor](../src/spatial_memory/observation.py),
[world transitions](../src/spatial_memory/simulation.py) and
[episode ordering](../src/spatial_memory/evaluation.py) establishes:

- At t=0, the initial map is observed. At each ordinary step the world advances,
  then sensing is decided, then planning/motion occurs. New-entry contacts at the
  pre-move pose are scored for that already advanced world, not prevented by
  sensing at the same step. A contact can therefore be unavoidable by a query now.
- The radius footprint is an in-bounds Euclidean disk, at most 29 cells. A cell
  is returned iff occlusion is off or every intermediate cell of the existing
  supercover list `line_cells(position,target)[1:-1]` is free. Side cells at
  diagonal corners matter. Endpoints do not block their own returns.
- Noise flips only returned bits, independently; it does not randomize the mask.
  Outside the footprint is always missing. Missingness is not an occupancy bit.

Radius3 is not maximum ray-list length3: the diagonal target displacement(2,2)
has five intermediate supercover cells. In complexity expressions use actual
ray-list length (maximum5 for this footprint), not the sensor-radius constant.

Let v_i(z,x) be that deterministic return mask, D the footprint and O the returned
set in y. The exact likelihood proposed for the agent's model is

```
K(y|z,x) = I[observed mask equals v(z,x)]
          * product_{i in O} [(1-epsilon) if y_i=z_i else epsilon].
```

Outside-D entries must be missing. If occlusion is disabled, every D entry must
return. The product assumes the configured independent flips; correlated noise
would be model misspecification. Visibility cannot be computed from evaluator
occupancy. No semantic static-wall/temporary-object labels enter K.

Use p_t^- for the belief in Z_t **after world advancement, before an optional
query**; use p_t^+ after it. Motion a_t encounters Z_t. A forecast Z_t+1 concerns
the next advancement at the resulting pose. Q's next-entry term anticipates one
future hazard but does not equal the current contact outcome. At T, do not charge
a Z_T+1 hazard after the episode ends. Define its coefficient as zero there.
If the action reaches the goal now, suppress both the remaining-distance and
next-entry terms: the actual episode terminates. These are proposed corrections.

The original assay's post-initialization fork must not permit a second query at
t=0. Snapshot after initialization, first window decision at t=1 after world
advance; 'post-move t=16' first acts at17. Include t+W<=T in eligibility. Keep the
public Manhattan distance>W guarantee against goal termination before the query.

## Implementation-ready joint-belief proposal JB-1 (unapproved)

The following completely specifies a bounded model/filter for review, including
its failure behavior. It does not establish feasibility or authorize code. The
choices are amendments to v0.1, not existing locked parameters.

### Prior, alignments and transitions

Use cell coordinates (x,y), zero-based, and offset o=(o_x,o_y) in {0,1}^2 with
prior probability1/4, fixed throughout an environment's history. Tile index is
`(floor((x-o_x)/2),floor((y-o_y)/2))`; within-tile bit order is row-major. Intersect
tiles with grid bounds. Off-grid bits are fixed zero and never sensed; they are
not sampled outside walls. No perimeter wall or free-space connectivity prior
is inferred from hidden geometry.

Initial in-grid bits are iid Bernoulli(.5), conditioned on the declared free
initial robot cell only. This prior is deliberately weak and can assign enormous
mass to disconnected maps; it is a scientific risk needing review. A structural
prior conditioned on generator topology would leak unavailable information and
is not an automatic fix. Alternative public-map priors require a new proposal.

In particular, if every sampled map has no route to the goal, all capped distance
terms can equal1. With equal hazard predictions, wait then weakly dominates
actions with positive blocked cost. A local query may not repair any sampled
global route, giving zero EVSI despite useful real-world information. This is a
constructive degeneracy risk, not an empirical finding about JB-1. Review a
public-development-learned spatial prior or a less saturated terminal surrogate
as explicit alternatives; do not fix it by optimistically reading the true map.
The common controller needs its own activation/progress fixtures before the
scheduler's activity can be interpreted.

For a full tile u,v in {0,...,15}, use a strictly positive row-stochastic matrix
T. Initialize `T_uv=.95*I[u=v]+.05/16`. For a boundary tile's valid bit subset B,
embed its state with other bits zero and use
`T_B(u,v)=T(embed(u),embed(v))/sum_{r valid}T(embed(u),embed(r))`.
This is conditioning at **every step**, not simply marginalizing a 16-state
chain; the distinction is intentional. Initial states are uniform on valid bits.
Tiles transition independently conditional on o. At gap d use `(T_B)^d`, not
`normalize(T^d restricted to B)`. For filtering across d steps sample every
intermediate state in the path; forecasts never depend on events in the evaluator.

Fit only T from public development-fit streams with occlusion off, including
configured noise and missing outside-footprint cells. For training, full tiles
have exact 16-state forward/backward inference; use all integer times and missing
emissions1. Marginalize the four offsets using whole-stream responsibilities;
for the fitting objective omit boundary-tile likelihoods consistently. Pose-derived
move evidence is a unary occupancy constraint at the prior action's target/time,
added to that slice's tile emission. Adaptive action choices themselves add no
likelihood beyond their public outcomes. This is a specified surrogate fitting
objective, not maximum likelihood of every occluded deployment observation.

Run 50 fixed EM iterations from the declared T, with update
`T_uv=(expected_count_uv+1)/sum_r(expected_count_ur+1)`.
This is a Dirichlet(2) MAP regularized M-step, **not** Dirichlet(1) MAP. Offsets are
integrated, not estimated by revealing the generator. Fit data cannot change the
prior, loss coefficients, tile size, number of offsets, noise or query price.
Publish the likelihood curve and final T; identifiability is not guaranteed.

### Initialization and importance update

Store M=64 paths `(o,Z_0,...,Z_t)` with normalized weights. Initial offsets use
systematic allocation (16 of each), then the observation-adapted proposal below
with the initial prior in place of T. Importance weights include offset prior
versus allocation probability (both1/4). Each cell belongs to exactly one tile
within a path, not four overlapping independent updates.

For a real y, form F, the union of intermediate ray cells of every returned
target, all necessarily free. For each tile k and ancestor j define

```
g_k(s) = I[s respects F] * product_{returned cells in k} noise_bit_likelihood
q_jk(s) = T_B(prev_jk,s)*g_k(s)/c_jk
c_jk = sum_s T_B(prev_jk,s)*g_k(s)
C_j = product_k c_jk.
```

Enumerate at most16 states per tile; sample each tile from q_jk. With no query,
g=1 and C=1. Let h(z,y) check all **missing** in-footprint targets have at least
one occupied intermediate blocker. The incremental importance weight is
`w_j_old * C_j * h(z_j,y)`, computed in log space. Returned-bit likelihood and
returned-ray constraints were already in q and must not be multiplied again.
This corrects the proposal exactly before finite-particle normalization. It
still can lose all samples to missing-mask constraints; it is not a fully adapted
proposal for the complete sensor. A bootstrap proposal is a separate inferior
alternative: 64 iid uniform maps miss a specific noiseless 29-bit return with
probability `(1-2^-29)^64 > .9999998` even without occlusion.

At the next decision, the executed cardinal action and resulting public pose
give a hard occupancy constraint on its target in Z_t (free on success, occupied
on an in-bounds failed move). Reweight stored paths by this evidence **before**
propagating Z_t+1. Wait supplies no such constraint; do not assume the current
robot cell is free after a dynamic entry. Ignoring this feedback is an alternative
reduced-information model that must be labeled, not called the full H_t posterior.

### Resampling, rejuvenation and support

Normalize by log-sum-exp. ESS is `1/sum_j w_j^2`; if ESS<M/2, systematic resample
with one uniform in [0,1/M), inverse CDF in ascending particle index, then weights
1/M. Retain ancestry and all path slices to make the target explicit.

After each real observation update, perform four deterministic row-major sweeps
of Gibbs updates of each **current** tile. Conditional on o, Z_t-1 and other
current tiles, the target for state s is proportional to its T_B entry (initial
prior at t=0) times the **complete** K(y|Z_t), including mask and noisy bits.
At a no-query time use K=1. Recompute every affected supercover mask; enumerate
all valid states, retain the current state if all other states have zero mass.
This kernel preserves the conditional target but cannot repair an absent past
trajectory or disconnected hard-constraint modes. Four sweeps do not guarantee
mixing. Unequal weighted paths retain weights when moved conditionally.

Then one Gibbs update of the global offset samples its four probabilities
proportional to `.25 * p_o(Z_0) * product_{r=1..t,k} T_{B_o,k}(Z_r,k|Z_r-1,k)`.
Sensor and pose likelihoods depend on cell maps, not their tiling, so cancel.
Retile every stored slice without changing occupancy. This step costs O(4tN)
per path and is missing from the original O(MN) claim. It could be deferred as
an explicitly frozen-offset approximation, with degeneration monitored, but not
silently removed to meet a timing target.

If any tile normalizer is zero, all weights vanish, arithmetic is nonfinite or
pose feedback has no supporting path, stop the run with an integrity/model-support
failure checkpoint. Do not epsilon-floor a physically impossible mask, consult
truth, regenerate a favorable episode, or relabel an arbitrary reset as Bayes.
Report particle-support failure separately from a logically inconsistent return.
Public-only prior restart is a possible different algorithm requiring review;
it is not included in JB-1. Thus JB-1 is precisely specifiable but **not yet a
feasible validated model**, especially with noiseless observations and M=64.

### Deterministic randomness

Propose Philox raw 64-bit draws with a recorded NumPy version/build and golden
vectors; [NumPy documents counter/key stream separation](https://numpy.org/doc/stable/reference/random/parallel.html).
Key = first128 bits of SHA-256 of a length-prefixed UTF-8 serialization of
`(phase, model-lock-hash, public-run-opaque-id, purpose)`. Counter packs t(32),
particle(16), sweep(8), tile(16), subdraw(32), retry(16), lane(8), with reserved
remaining bits zero; reject overflow. World, sensor, filter, forecast and EVSI
purposes are disjoint. Algorithm keys never expose environment seeds to policies.
Use four-byte unsigned little-endian byte lengths for each UTF-8 field; hexadecimal
hashes are lowercase, phase/purpose strings are fixed in the lock. Interpret the
digest prefix and counter bit fields little-endian, with t in the least-significant
bits. Record allocation of any forecast/imaginary-draw subindices in subdraw.
Convert raw integers to U=(raw>>11)*2^-53 and inverse-CDF sample with fixed state
ordering. Never use Python's randomized hash, worker order or shared mutable RNG.
Store counters/keys and platform manifests; identical keys across methods may
couple common noise but do not make their different posteriors identical.

## Controller and EVSI amendments still requiring architectural choice

Use the same mathematical L(a,Z_t,Z_t+1), action set and tie order before/after
hypothetical y. Do not replace only the gate's loss with true goal success, use
particle-specific feasible action sets or invent truth-based reachable goals.
Specify occupied departure distances by one legal outgoing edge to a free
neighbor, with goal distance0 only on actual immediate goal arrival. Otherwise
use the same capped BFS distance; no path gives remaining-distance penalty1.
The constant .005 cancels out of one-step EVSI and action choice; it is not an
elapsed-step objective. At the final step the distance proxy can favor partial
progress without completion. Blocked cost .1 and hazard1 are arbitrary utilities,
not a formal scalarization of the primary contact-free completion endpoint.

**Proposed forecast correction:** for each Z_t particle, average L over P=8
independent conditional future draws, obtaining Qbar_j(a). Hypothetical y depends
only on Z_t. Never associate a single future atom with a perfectly identifying
current query and call that physically revealing Z_t+1. The current-state-perfect
comparator is `V_PC=r(b)-sum_j w_j min_a Qbar_j(a)`. The original future-perfect
V_PI remains a mathematical upper bound but is a clairvoyant comparator. Increasing
P trades computation against an additional minimization bias; development P=4/8/16
stability checks would need approval and a lock, not assessment adaptation.

Two explicit architecture alternatives must be reviewed:

- **F, fixed finite bank:** real and imaginary queries reweight exactly the same
  bank and Qbar; take the immediate action from that posterior, rejuvenating only
  afterwards for the next time. Finite-bank EVSI identities hold exactly. Real
  returns may have zero bank support, particularly with noise0; stop rather than
  silently replace the policy. This may be scientifically impractical.
- **G, generative belief target (recommended for further design):** JB-1 real
  updates replenish support; exact EVSI is defined for its generative model, and
  a finite-bank computation is explicitly an approximation to it. Same loss
  function is retained but replenished samples need not equal old atoms. Validate
  value bias against independent posterior integration on small public synthetic
  models. If instead evaluating the actual approximate update/control algorithm,
  use policy-conditioned expected loss reduction on independent evaluation draws;
  that quantity can be negative and has no automatic nonnegative-EVSI guarantee.

Neither architecture has been implemented here. Do not claim that an unbiased
finite-bank estimator plus an arbitrary real refresh validates the generative
EVSI decision problem. Approval of architecture, approximation checks and support
failure behavior is necessary before Phase 1.5B.

## Budget and protocol audit

The Bellman equation is valid only when the no-query continuation includes the
next belief update and future sensing, observation is zero-latency, and at most
one observation is permitted per time. Distinguish belief beta from integer
budget b. The .25 shadow-price rule is not a Bellman solution. It prices budget
scarcity while the reported primary endpoint omits sensor cost except via a
separate condition. Defer C until A's value approximation and cost units survive
development; a zero coefficient is not an informative ablation.

Other explicit inconsistencies: pre-assessment 'informative opportunity' membership
was left to a later manifest; exact zero SE is not proof of precision; skipping
sparse calibration bins cannot certify calibration; a family-balanced 20%
no-change allocation cannot be exact in every tiny two-schedule subgroup; a
500-GB ceiling has no full-schema evidence yet. The [recommendation](phase1_5a_protocol_recommendation.md)
proposes separate amendments, leaving the original documents unchanged.

## Verification scope

18 standalone audit tests passed in Ubuntu WSL Python3.12.3, including 200 finite
random tables. No project policy module is imported by the audit script. These
are mathematical checks, not development/tuning or navigation episodes. Historical
tracked files are unchanged; frozen lock and assessment-manifest SHA-256 match
the values recorded in Phase 1.4D. No claim is made to have replayed the historical
traces in this review. Stop for scientific review of the amendments above.
