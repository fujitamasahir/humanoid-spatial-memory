# Phase 1.3 task-aware observation design — research review required

Status: specification only. No task-aware scheduler, MuJoCo integration, or
humanoid locomotion is implemented. Baselines retain Phase 1.2 rules.

## Falsifiable hypothesis

At equal sensing budgets, prioritizing *observable uncertainty with plausible
route consequences* can improve contact-free goal completion over generic local
entropy. A useful result must survive matched observation-count controls, timing
shifts, noise, priors, occlusion, and strong periodic intervals. Fewer calls alone
is insufficient. Phase 1.3 provides motivation and counterexamples, not evidence
that this unimplemented policy improves performance.

A cell's entropy does not encode its relationship to a goal. Two histories with
identical cell probabilities can require different decisions for different goals.
A high-entropy side-room cell can have zero effect on any competitive route;
a recently observed free bottleneck can have low entropy but high consequence if
wrong. The constructive test `test_offroute_entropy_and_route_disruption_are_distinct_information`
holds histories and generic entropy equal while a hypothetical occupancy change
on versus away from the route changes shortest path length differently. It is
an identifiability example, not an outcome comparison. Family A does not guarantee
entropy is off-route on every trajectory; unknown cells are excluded by baselines.

## Robot-accessible interface

Inputs: goal g, current pose x, current ternary memory M, last observed timestamps
L, observed flip/exposure counts, configured sensor radius/noise assumptions,
remaining total observation capacity b, current time t, and planned route from M.
No Scenario, evaluator, future change times, object identity, true visibility,
truth shortest path, contact labels or persistence labels may cross this boundary.
Robot action feedback could be added only as a separately tested public input;
it is not assumed in the initial design. Output: request observation now, plus
logged score components and reason; shared controller handles budget denial.
Viewpoint movement is outside the first implementation's scope.

## Proposed decision model

Let p_i be the history-based occupancy proxy and H_i its entropy. Let V_i(x,M)
be estimated observation feasibility from remembered ray occlusion and sensor
range: blocked remembered rays get 0; unknown blockers receive a conservative
factor v_unknown in [0,1]. This is a prediction, never the true sensor mask.
Failure to reveal a cell updates its feasibility evidence only through received
ternary observations; no unseen occupancy is inferred from evaluator truth.

For each candidate cell in the potential sensor disk, estimate route disruption
D_i by flipping its remembered occupancy and replanning toward g:

D_i = min(D_max, |J(M with i flipped,x,g) - J(M,x,g)|).

J is shortest remembered route length with a fixed finite no-route penalty above
any simple path length. Occupied cells on promising alternative routes must also
be candidates: restricting candidates to the current route cannot discover a
reopened shortcut. Unknown cells use a declared occupancy prior and two occupancy
counterfactuals; they must not disappear from the policy as they do from baseline
trigger scores. D_i is a one-cell approximation: correlated doorways and multiple
simultaneous changes can invalidate it.

Define disagreement risk q_i as p_i for a remembered free cell and 1-p_i for an
occupied cell. For unknown cells use q_i=.5 as a declared starting approximation.
An inexpensive exploratory score is

S(x) = sum_i V_i(x,M) q_i min(D_i,D_max).

This is expected disruption under single-cell counterfactuals, **not** calibrated
value of information: it can double-count correlated route changes, and observing
a cell need not improve a decision. Entropy can be logged as an ablation feature,
but multiplying by H_i again would count uncertainty twice without justification.
Low q_i can be offset by large D_i, allowing a low-entropy bottleneck to matter.
Predicted feasibility must reduce scores for repeatedly occluded targets rather
than treating every request as useful.

A more defensible, expensive comparator approximates actual decision value:

VOI(x) = min_a E[C(a,Z)|history] - E_Y[min_a E[C(a,Z)|history,Y,x]].

Here actions a include move/wait/replan; Z denotes sampled occupancy under an
explicit history model, Y sampled observations under estimated visibility/noise,
and C includes route cost plus declared discrete-contact loss. Samples are model
beliefs, not hidden world states. This requires an action-cost and transition
model that Phase 1.2 does not have. It is a research comparator, not an assertion
that the cheap S score equals VOI or provides safety guarantees.

Request if b>0, S(x)>tau(b,h), and predicted newly revealable mass exceeds epsilon.
Use h=max(1, estimated remaining path length) and an initial budget opportunity
price tau(b,h)=c_obs+lambda*h/max(1,b). All constants, the occupied/unknown ray
rules, no-route penalty and tie handling must be preregistered before experiments.
Initial sensing remains charged; b excludes it. An empty remembered route uses
a finite h fallback and considers candidate cells along remembered alternatives;
no true recovery route is supplied. If feasibility is zero, the policy abstains,
which can deadlock without future viewpoint planning. Do not silently fall back
to an oracle or add ad hoc repairs after seeing failures.

## Complexity and expected behavior

For N grid cells and K candidates, baseline A* on the grid costs O(N log N) in
the worst case. Naive single-cell disruption costs O(K N log N); visibility ray
checks cost O(K R), R bounded by sensor radius. Retaining one counterfactual grid
at a time requires O(N+K) extra memory. Route-set approximations could reduce
runtime, but would need separate accuracy ablations. Monte Carlo VOI multiplies
planning cost by the number of samples, observations and candidate actions.

Expected benefit: avoid spending scarce calls on irrelevant or currently hidden
changes while checking valuable passages. Expected failures: miscalibrated q,
false remembered occluders, completely unknown passages, multi-cell interaction,
noise mistaken for dynamics, pedestrian cycles aliased by sensing times,
insufficient budget, inaccurate route penalties and inability to move for a view.
No model of physical bodies, momentum, stopping distance or sensor latency exists.
Contact-free grid completion cannot establish human or physical safety.

## Novelty challenge and review gates

The cheap score is an obvious combination of uncertainty, route sensitivity,
visibility and budget price. This phase makes **no novelty claim** for it.
The prior review's active perception, temporal occupancy and occupancy-grid work
already motivates those ingredients; it does not validate our formula. Before
implementation, review published decision-aware sensing / active mapping methods
and select at least one faithful tractable comparator. No new literature search
or claim of comprehensive coverage is made in this phase; the existing
[Phase 1.2 literature audit](phase1_2_baseline_review.md) remains the source record.
If simple weighted heuristics perform equally well, reject any stronger claim.

Future comparisons: unchanged Static/Age/Uncertainty, Periodic intervals 1/2/5,
matched-call periodic schedules, fixed-rate uncertainty, random observation times
with identical caps, and a faithful active-perception baseline after review.
Use development-only tuning splits separated by realized topology/seed from
robustness assessment; lock parameters before fresh assessment. Match budgets
and report both paired per-world completion and contact-free completion, latency,
cost, errors and feasibility calibration. Do not pool repeated settings as trials.

Ablate route consequence (D=1), feasibility (V=1), budget price, unknown-cell
handling, history adaptation versus fixed rate, occupied alternative-route
candidates, and counterfactual S versus Monte Carlo VOI. Also compare a simple
weighted entropy/age/route-distance rule at equal tuning effort. Evidence for task
relevance requires a benefit after matched sensing rates/phases and calibration
controls, not merely improvement over an unlucky fixed interval.

## Later transient/persistent memory

A later model could maintain a slow occupancy component and a transient component,
using repeated occupancy durations, reversals and recurrence under partial
visibility. An unlabeled two-timescale hidden-state model is one option. Fit from
robot observation sequences with censored gaps and explicit noise likelihoods;
never supervise it with pedestrian identities or change-event labels. Mixtures
may be unidentifiable in short episodes; report calibration and posterior ambiguity,
and keep a last-write fallback. Evaluate against fixed-rate and single-timescale
controls. Occlusion is missing data, not evidence of departure. Persistence must
not be inferred simply because an obstacle was observed once or a person departed.

Stop for research review before implementing any of these policies.
