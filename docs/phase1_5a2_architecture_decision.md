# Phase 1.5A-2 architecture decision

2026-11-07. Amendment proposal v0.2; **design decision for scientific review,
not implementation approval**. Read with the [prior review](phase1_5a2_spatial_prior_review.md),
[controller](phase1_5a2_controller_specification.md),
[generators](phase1_5a2_generator_specification.md) and
[protocol amendment](phase1_5a2_protocol_amendment.md). All earlier reports remain
unchanged. Exact deductions below concern a declared model; no navigation benefit,
novelty or real-world calibration is established.

## Decision: G with a generative predictive mixture

Select **G**, using identical observation-conditioning procedures for hypothetical
and actual observations. Select a policy-conditioned expected loss reduction as
the implemented approximation's estimand. Reserve 'exact EVSI' for the Bayes-optimal
finite/model reference. This resolves the earlier ambiguity rather than attaching
an exact-EVSI claim to a mismatched real filter.

| Criterion | F: fixed current-state bank | Selected G |
| --- | --- | --- |
| Real versus hypothetical update | Consistent only if both reweight identical atoms and take the same immediate action. | Both condition the same generative mixture by the same full mask/bit likelihood and sampling routine. |
| Posterior | Exact for the finite bank, not the underlying occupancy model. | Exact conditioning of the current predictive mixture by rejection; parent/history approximation remains. |
| Support | An unseen real mask can have zero probability in the bank. | Positive tile refresh supports all unprotected current maps; bounded rejection can still fail computationally. |
| Future uncertainty | One future atom per current state can imply false foresight. | Integrate the tile transition analytically; observations never reveal a future draw. |
| Cost | Cheap weight updates. | Nested local posterior sampling is costlier; avoid nested full-map BFS/filtering. |
| Approximation/replay | Simple but severe support and finite-bank bias. | Explicit model, historical-mixture and finite-control errors; fixed keyed draws permit replay. |

F remains a useful exact finite-table oracle in fixtures. It is rejected as the
navigation architecture because inconsistent real-return support would force
either failures or an undeclared change of update rule. G is not automatically
more accurate; it makes the approximation and support contract explicit.

## 1. Model and state representation

Use the [learned tile law B and refresh kernel](phase1_5a2_spatial_prior_review.md),
a fixed offset(0,0), and public protected cells. These explicitly replace JB-1's
four-offset latent mixture, full16x16 learned transition matrix, path Gibbs and
Dirichlet ambiguity. This smaller model is chosen for tractable conditioning and
analytical forecasts, not because it has won an experiment. Cross-tile dynamics,
moving-object identity and long-lived wall certainty remain misspecified.

At t, after incorporating the previous action's public pose result, store
M=64 previous-map components `(z_j,w_j)`. The **predictive law**, not a sampled
current bank, is

```
P_t(j,z) = w_j * product_tiles T_Ck(z_jk,z_k).
```

At initialization replace the mixture by the product of B_C over tiles. T_C has
positive probability on every allowed tile state. Known border/start/goal cells
are constrained by public domain rules, not evaluator truth. The mixture over
previous maps carries dependence across tiles; current tiles are independent
only conditional on their ancestor component. Numerical parent weights are
normalized; retained posterior samples have weights1/M.

This predictive mixture is exactly specified **conditional on its parent
approximation**. It is not the exact posterior of the entire observation history.
Particle ancestry and resampling can discard historical modes. Do not call
positivity of current transitions a cure for history/model error.

## 2. Exact sensor likelihood inside the model

Use the existing radius3 Euclidean footprint D, supercover intermediate cells,
deterministic occlusion mask v(z,x), and configured independent bit noise epsilon.
For returned set O in y:

```
K(y|z,x) = I[mask(y)=v(z,x)]
          * product_{i in O} ((1-epsilon) if y_i=z_i else epsilon).
```

Outside D is always missing; epsilon changes returned bits, never masks. A
returned occupied endpoint is allowed; intervening occupied cells block returns.
The diagonal(2,2) ray has five intermediate supercover cells. Missingness itself
is evidence. Policies never read evaluator visibility or hidden geometry.

For the single-cell ablation use the **marginal** channel of that cell's
{missing,free,occupied} return, summing over all other outputs. It is not the
full-array likelihood with unqueried cells set to missing. The complete query
row and actual sensor use the full channel above.
For a scalar returned bit, constrain only its ray's intermediate free cells and
its noisy bit. For scalar missingness, constrain only the existence of a blocker
on that ray. Other cells' return masks/bits are absent evidence, not additional
missingness constraints. The same conditioning algebra applies to that channel.

## 3. One conditioning operator for real and imagined data

Let E be optional public movement evidence about current occupancy: target free
on a successful in-bounds cardinal move, occupied on a failed one; wait adds no
constraint. Let F be all intermediate cells of returned rays, necessarily free.
For ancestor j and tile k define

```
g_k(s) = I[s respects F and E]
         * product_{returned cells in k} noise_bit_likelihood
c_jk = sum_s T_Ck(z_jk,s) g_k(s)
C_j = product_k c_jk; Z_g = sum_j w_j C_j
q(j) = w_j C_j / Z_g
q_k(s|j) = T_Ck(z_jk,s)g_k(s)/c_jk.
```

At t=0 use B_C instead of T_C. Only constrained/observed tiles require enumeration;
unaffected c_jk=1. Draw j from q and relevant tile states independently from q_k.
Accept iff every missing in-footprint target has an occupied intermediate
blocker. That is the residual indicator h(z,y). The proposal density is
`P_t(j,z)*g(z)/Z_g`; rejection by h therefore produces iid samples from
`P_t(j,z|y,E)`. No returned-bit likelihood is multiplied twice. This is a
deduction from rejection sampling, not a measured acceptance claim.

Sample S=64 accepted states, at most4096 candidate proposals per invocation.
Use logarithmic c/Z_g calculations and fixed-state-order inverse CDFs. A zero
Z_g, nonfinite arithmetic or insufficient acceptances is a **failure**, not
permission to floor likelihoods, return fewer samples or consult truth. Keep
attempt/acceptance counts and abort the affected run for review. No claim is
made that4096 attempts will suffice for all masks.
The ideal mathematical conditioning operator uses an unbounded iid proposal
stream and terminates almost surely when the conditioning event has positive
probability. The4096 bound is an execution-abort rule, not a different posterior.
No numerical estimate is returned for an aborted invocation.

For hypothetical queries sample only tiles needed by the footprint, mask and
five-action loss. Conditional forecasts require the complete tile containing a
possible resulting pose; include these tiles too. Unconstrained others integrate
to1 and are not materialized. For a stored posterior component, materialize all
remaining tiles from their conditional transition given its accepted ancestor.
This is marginalization, not a different posterior or a private better map.

### Delayed pose evidence without a finite-bank support reset

Keep the unconditioned predictive mixture P_t, the actual optional y_t, and a
snapshot of its parents until action a_t's resulting pose is known. Before
constructing P_t+1, re-run the **same** conditioning operator on P_t with y_t
(if any) and the new E_t. Draw64 full current maps as the next parents. Do not
merely discard the prior64 samples if none happen to satisfy E_t; reconditioning
the retained generative law replenishes current support. No future event or
contact label is used. At t0 there is no move before the first ordinary step.

This defines a streaming approximate filter without rejuvenation, offset Gibbs
or an arbitrary restart. It preserves an explicit one-step generative anchor;
it does not retroactively recover modes missing from older parent mixtures.
Boundary/pose contradictions stop; they are not explained away by noise in
movement. The physical model assumes known pose and deterministic blocked moves.

## 4. Controller evaluation and forecast marginalization

Freeze the public routing potential D_t and scale s_t **before** deciding whether
to query, as specified in the controller report. Every hypothetical and real
decision at this time uses that same potential, current action set and loss
function. Update the potential only at the next time. Thus an imaginary query
cannot change a different planner than the real query changes.

For current map z, integrate future-state loss analytically:
`Lbar_t(a,z)=sum_z' P(z'|z)L_t(a,z,z')`.
Only entry at the action's resulting cell depends on z'; for a currently free
unprotected cell in tile k, that probability is `r * B_Ck(bit_i=1)`.
It is zero for protected cells, immediate goal arrival and t=T. No single
sampled future map, finite-P forecast bank or perfect-future observation enters
the decision. Posterior uncertainty about **current** occupancy remains joint.

For S draws from a prior or posterior, the approximate controller d chooses the
action minimizing the sample mean Lbar, with the fixed tie rule. The no-query
action a0 uses a separate64-draw prior-control bank. A real query uses64 draws
from the conditioning operator. The hypothetical a_y uses that identical operator
and algorithm. The outer evaluation state below is never a control-training draw.

## 5. Exact EVSI reference versus the chosen estimator

For an exactly enumerable current model p and exact optimal actions:

```
R(p)=min_a E_p Lbar(a,Z)
V_S=R(p)-E_Y min_a E[Lbar(a,Z)|Y]
V_PC=R(p)-E_Z min_a Lbar(a,Z).
```

For the controller's loss range2.5, `0<=V_S<=V_PC<=2.5`. The posterior-advantage
form relative to an exact prior-optimal action is also exact and nonnegative.
These are finite-model identities, verified in standalone tables. They do not
say the real world obeys B/T or that the64-draw controller is Bayes optimal.

For the **implemented approximation proposed here**, condition on locked
algorithm random keys U and define a_y=d(P_t(.|y),U_y), a0=d(P_t,U_0). Target

```
V_alg = E_{Z,Y~P_t K} [Lbar(a0,Z)-Lbar(a_Y,Z)].
```

This is policy-conditioned expected loss reduction. It may be negative: a noisy
finite posterior decision can be worse than retaining a0. It approaches model
EVSI only as control integration becomes accurate under additional convergence
assumptions. Do not assert nonnegativity or an exact V_PC bound for its numerical
estimate. Do not clamp negative values.

Proposed mathematical algorithm (not implemented):

```
freeze predictive mixture P_t, potential D_t, action set and loss
draw 64 prior-control states with purpose='control-prior'; choose a0
for k=1,...,J (J=64):
    draw current state Z_k from P_t with purpose='outer-state'
    draw Y_k from the modeled real sensor at Z_k with purpose='outer-sensor'
    sample 64 independent posterior-control states conditional on Y_k
    choose a_Yk with the same routine used for a real Y_k
    delta_k = Lbar(a0,Z_k)-Lbar(a_Yk,Z_k)
value_hat = mean(delta); numerical_se = sd(delta)/sqrt(J)
request iff value_hat > .02; common cap decides grant
if granted: observe real Y, run the identical conditional-control routine, act
else: act a0
retain P_t and real public evidence for next step's pose reconditioning
```

Given the fixed generative mixture and keyed decision function, independent outer
pairs make the **untruncated mathematical estimator** unbiased for V_alg, not
for exact EVSI or navigation completion. Conditioning analysis on invocations
that happened to finish within4096 can introduce selection bias; do not claim
unbiasedness for a complete-case summary of failed runs. The protocol records
aborts and missing-outcome sensitivity instead. A query's real posterior-control
key is the same as its hypothetical
key: it includes canonical observed-array bytes, public history identity, t and
purpose. Repeated identical y can cache the identical action. Counterfactual
control draws do not depend on k or the evaluation state. This prevents seeing
the generating state through a random seed. Distinct outer pairs remain iid
conditional on the fixed keyed action function.

**Explicit amendment:** remove the two-SE gate from the primary candidate. Use
the fixed mean threshold above; SE is a conditional numerical diagnostic, not
a confidence guarantee. Rare-event Monte Carlo error and finite-control errors
are measured in development and can reject the design. J=S=64 and the4096 limit
are reviewable computational conventions, not tuned navigation winners. Failure
of their numerical/resource gates requires another reviewed amendment, not an
assessment-time increase or silent fallback.

## 6. Reproducibility, costs and limitations

Use the Phase 1.5A audit's length-prefixed Philox key/counter specification;
record software versions and golden vectors. Add distinct purposes for outer
state, outer sensor, prior control, posterior control, posterior materialization
and delayed pose conditioning. Canonical observations include dimensions, int8
row-major values and missing entries. Hash these bytes into the posterior-control
key. Public opaque replay-stream identifiers are supplied by the runner, never
raw seed/partition information. No policy random draw advances a world/sensor stream.
Use a public opaque **paired replay stream ID**, shared across methods for the
same world, in common-control keys. It carries no readable seed or topology;
the distinct trace/job ID is not used as a private control RNG salt. Identical
public histories, model and goal must yield identical control samples/actions,
independent of scheduler name. Gate-only ablation keys include their declared
virtual goal/channel, keeping that difference explicit.

Computing D_t requires one Dijkstra pass, not a BFS for every map/forecast. For
J outer queries, conditioning costs roughly O(J*S*R_a*K_t*16), where R_a is the
measured rejection overhead and K_t the number of touched tiles; mask work is
additional. It can still exceed the resource ceiling. The earlier scalar-kernel
benchmarks do **not** benchmark this algorithm. Numerical/control banks, model
version, rejected proposals/counters and scores must be reproducible from traces.

The selected architecture resolves mathematical consistency, not empirical
feasibility. Support, acceptance, learned-prior coverage, approximate-history
bias, finite-sample action errors and the myopic frozen potential remain failure
modes. The model cannot identify all transient versus permanent occupancy.
No exact Bayes/optimal-navigation claim or new-method validation follows. Stop
for review before implementing any of these routines.
