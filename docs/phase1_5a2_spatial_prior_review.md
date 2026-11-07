# Phase 1.5A-2 spatial-prior decision

2026-11-07, proposal v0.2. Conclusions below are **mathematical deductions and
hand-built finite fixtures**, not navigation results. No prior was selected using
Phase 1.4 assessment performance. The earlier Bernoulli(.5)/JB-1 proposals remain
unchanged as historical design records; this report explicitly recommends a
replacement for review.

## What Bernoulli(.5) does and does not imply

An independent occupancy prior with p=.5 has full map support but no corridors,
rooms, wall persistence or connectivity preference. Full support is not useful
finite-sample coverage. For a unique corridor requiring11 unknown cells free,
its prior open probability is `2^-11=1/2048`. Sixty-four iid maps all miss that
route with probability `(2047/2048)^64`, about .9692. This is an exact corridor
example, **not** a measured probability for the proposed25x25 layouts or a
percolation theorem. Conditioning on an initial local return can improve matters;
the example concerns still-unobserved cells.

If every current sample has no route, v0.1 gives every resulting position the
same capped distance penalty1. In a zero-hazard example, wait costs1.005 and a
forward action blocked with probability1/2 costs1.055. If a perfect query says
forward is free, its cost only ties wait at1.005; with wait-first ties, observing
still changes no action. EVSI is exactly zero. A physically open but absent
route would not be represented. Different loss coefficients or hazard samples
can instead produce arbitrary waiting/moving differences: this is not evidence
that the .5 prior always makes EVSI zero.

Three separate failures must be distinguished:

- Map sampling misses plausible connected routes: prior/finite representation.
- Unreachable-distance saturation erases every local progress contrast: controller.
- The sensor cannot change the best action under the declared loss: possibly
  legitimate zero EVSI, even with a calibrated posterior.

Changing the occupancy rate alone cannot solve all three. For illustration only,
p=.1 makes the same corridor's free probability .9^11=.3138; that is an optimistic
assumption, not evidence that .1 is the correct world occupancy rate. A prior can
also give positive value to nonexistent shortcuts. Correct model-EVSI algebra
does not make that value real.

## Alternatives considered

| Prior | Public information it can use | Advantage | Limitation / decision |
| --- | --- | --- | --- |
| iid Bernoulli(.5) | Grid dimensions only | Transparent full-support reference. | Severe route-coverage risk; reject as the default. |
| Fixed optimistic iid occupancy | Declared scalar such as .1 | Fewer disconnected samples. | Arbitrary optimism and risky wall shortcuts; do not select the scalar for navigation success. |
| Public-data fitted iid scalar | Noise-aware counts in development observations | Cheap; avoids selecting .5 by convention. | No local spatial dependence, and view-selection bias remains. |
| Global density mixture | Public development distributions | Represents occupancy-rate uncertainty. | Spurious long-range correlation; density particles can collapse; not selected. |
| Learned categorical2x2 tile law | Public noisy2x2 patches only | Small, normalized, full-support, local multi-cell patterns; analytical refresh forecasts. | No global connectivity or object semantics; selected bounded first model. |
| Layout grammar / connected-map prior | Would need a public structural model | Can represent long routes. | An evaluator's hidden layout/family/seed is forbidden; fitting a legitimate public grammar is a separate research project. |

Recommend the **learned categorical tile law**, together with the controller's
finite soft routing potential. This is a tractability decision, not a novelty
claim or evidence that2x2 is sufficient. The controller amendment, rather than
optimistically forcing sampled maps to be connected, removes distance saturation.

## Complete prior and learning rule

Use25x25 cells, fixed offset(0,0), tiles indexed by `(floor(x/2),floor(y/2))`,
row-major bit order in each2x2 tile. All four generators publicly guarantee an
occupied outer ring and free start/goal at all times. Every method receives these
generic guarantees; no internal wall, event or topology label is revealed.
The goal/start guarantee is a domain restriction, not an inference from truth.

Let B(v)>0, v=0,...,15, be a categorical full-tile law. Before data B(v)=1/16.
Learn B from **development-fit only**, never calibration, selection, assessment
or held-out outcomes:

1. Use the initial radius3, occlusion-off, noise .05 public observation from each
   of the two schedules in each of48 fit clusters. This is96 initial returns,
   not extra independent topologies. No hidden occupancy label is a training input.
2. Retain complete fixed-alignment2x2 tiles entirely returned, with no protected
   cell. Each of the two returns in a cluster has weight1/2, divided equally
   among its retained patches. A zero-patch return contributes zero and is logged.
   Require at least24 contributing clusters and96 complete patches; otherwise
   stop for insufficient public fitting coverage, without requesting truth.
3. For observed noisy pattern y, use
   `f(y|v)=.95^(4-Hamming(y,v))*.05^Hamming(y,v)`.
   Run50 deterministic EM iterations starting from uniform B. E-step
   `r_pv=B(v)f(y_p|v)/sum_u B(u)f(y_p|u)`; C_v is its weighted count.
4. Impose dihedral symmetry: Csym_v is the average C of the eight square
   rotations/reflections of v (count repeated transforms too). Update
   `B(v)=(1+Csym_v)/(16+sum_u C_u)`. This is the constrained Dirichlet(2) MAP
   M-step, not Dirichlet(1) MAP or truth-count smoothing. Publish all iterations.

This is an explicitly weighted local-pattern objective. Patches and neighboring
cells are not independent physical samples; the weights do not create that
independence. Start-centered views overrepresent reachable local space, and
occlusion-off fitting does not establish occluded calibration. B is a proposed
predictive model fitted to that public distribution, not a certified global
occupancy posterior. Its uncertainty is not captured by outer Monte Carlo SE.

For a boundary/protected tile, **marginalize off-grid bits**, condition on all
in-grid protected bits, and normalize. In symbols, if U are unprotected in-grid
bits and C fixed bits,
`B_C(s)=sum_{v:v_U=s,v_C=c}B(v)/sum_{v:v_C=c}B(v)`.
No off-grid bit is sampled; no hidden perimeter is queried. Positive B guarantees
a positive denominator. This deliberately replaces JB-1's off-grid-zero
restriction. In-grid protected bits are fixed at every time.

Initial occupancy is the product over B_C tiles. Tile law learning can capture
local correlations:16 noiseless illustrative patches,12 all-free and4 all-occupied,
give the unsymmetrized/symmetrized add-one solution
`B(0000)=13/32`, `B(1111)=5/32`, all other patterns1/32.
Marginal occupancy is3/8, but all-free probability13/32 differs from the iid
value `(5/8)^4=625/4096`. This is an exact example of the rule, **not fitted data**
or the noisy EM solution used in a future study.

## Transition and time gaps

Use a whole-tile refresh kernel

```
T_C(u,v) = (1-r)*I[u=v] + r*B_C(v)
T_C^d(u,v) = (1-r)^d*I[u=v] + (1-(1-r)^d)*B_C(v).
```

A refresh can change several cells jointly. The kernel has stationary B_C,
positive support and a closed-form gap evolution. For a free unprotected cell,
next-entry probability is `r*B_C(bit=1)`, not a single sampled future state.
It cannot represent translating bodies, spatially varying wall certainty or
heavy-tailed dwell times; these are acknowledged model errors.

Fit one r from {.01,.03,.07,.15} by public development-fit predictive likelihood,
not completion/contact/observation counts. Data collection is explicitly staged:
learn B from the96 initial returns first; then continue those same96 future fit
episodes using the common controller with provisional r=.03 and Periodic-1,
occlusion off, noise .05, no sensing cap, horizon80. These would be later
authorized development episodes; none was executed here. The provisional r is
a fixed data-collection convention, not an assessed candidate or a fitted result.

For each candidate r, evaluate exact16-state tile forward likelihoods over the
stored public histories, with noise emissions, missing emissions1, protected
cells and pose-derived movement constraints on their proper time slice. Sum
tile log likelihoods and average the two histories per topology, then topologies
equally. The observation mask is deterministic footprint in this fitting condition;
no occlusion-truth labels are available or needed. Choose maximum likelihood,
ties toward smaller r; publish all four scores. No refit after calibration or
assessment. Because B/r are empirical model fits, not posterior integration over
their uncertainty, report that limitation explicitly.

## Required checks and limitations

Check B normalization/positivity/symmetry, protected-cell conditioning, T row sums,
stationarity, gap formula and noise likelihood before development. In development,
report visible/missing-mask and occupancy calibration, known/unknown strata,
filter support and reject attempts. Evaluate a fixed iid .5 predictive reference
on stored histories without additional navigation episodes, not as a menu from
which to choose a navigation winner. Calibrated local predictions do not prove
global map correctness. Failure of these gates stops the proposal.

The selected prior does not prove progress; the [controller specification](phase1_5a2_controller_specification.md)
provides finite examples separately. No generator topology, hidden future or
Phase 1.4 assessment outcome enters B, r, prior selection or posterior input.
Review these conventions before implementation.
