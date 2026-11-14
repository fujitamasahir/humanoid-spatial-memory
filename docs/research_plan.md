# Research Plan

## Problem statement

Long-term autonomous robots operate in changing indoor environments. Pedestrians may temporarily obstruct corridors or occlude sensors, while objects and furniture may produce persistent changes. Conflating these events can corrupt long-term maps, lead to unnecessary re-observation, and worsen navigation.

## Working hypotheses (not established findings)

**H1 — Persistence modeling:** Explicitly distinguishing transient human occlusions from persistent geometry changes reduces erroneous persistent occupancy updates under partial observability.

**H2 — Task relevance:** Selecting re-observation based on both memory uncertainty and current route/task importance may improve the success-versus-observation-cost tradeoff against uncertainty-only and periodic verification baselines.

**H3 — Biped extension:** Humanoid traversability constraints may change the value of a spatial observation and route choice. Evaluate only after Phase 1 is sound.

## Literature positioning

Memory decay, spatiotemporal exploration, active perception, pedestrian-flow maps, lifelong navigation, and humanoid footstep planning are established areas. **No claim of a new method is justified yet.** The first substantive research milestone is to test whether strong existing approaches actually exhibit the failure mode hypothesized in H1.

Keep a bibliography with verified paper metadata, method assumptions, and reproducibility notes before claiming novelty.

## Three phases

### Phase 1 — Reproducible 2D testbed

- Hidden world state with static walls, movable persistent objects, and dynamic pedestrians.
- Robot receives partial, optionally occluded/noisy observations only; no oracle labels.
- Shared navigation and collision checker across policies.
- Initial sanity baselines: static map, periodic refresh.
- Stronger baselines to add after literature review: change-aware persistence and uncertainty-driven verification.
- Test different pedestrian dwell times, densities, object relocation rates, sensor ranges, and observation costs.
- Log separate train/development/test environment seeds. Freeze test suite before tuning.

### Phase 2 — MuJoCo humanoid scene

- Unitree G1 model in indoor scenes with moving pedestrian proxies.
- Keep spatial memory module largely unchanged to test representation transfer.
- If humanoid pose is kinematically moved, label the evaluation *kinematic navigation*, not physically controlled locomotion.

### Phase 3 — Physically actuated bipedal walking

- Integrate a known compatible pretrained policy.
- Check joint order, actuator interfaces, frame conventions, frequency, and stability.
- Add fall, unsafe foot-placement, collision, and tracking measurements.
- No assumption that macOS M3/8GB is adequate for training a humanoid locomotion policy.

## Decision gate after initial baselines

1. Does naive mapping demonstrably misclassify transient pedestrians as persistent obstacles?
2. Does a strong published persistence-aware baseline still fail under some controlled settings?
3. Are the failures meaningful and attributable to memory, rather than to planner or sensor bugs?
4. Only then implement a task-aware verification method.

## Phase 2 observation-policy status (2026-11-14)

The FIT72 B/C failure analysis is descriptive and complete. A separately frozen
C v2.0 route-candidate ranking proposal was implemented as isolated C-K,
C-Route3, and C-RouteK ablations. Its final public-memory synthetic gate found
that Route3 did not select the unique uncertain chokepoint more often than C0;
the predeclared rule rejected the candidate-ranking mechanism before any new
FIT72 candidate rollout. The FIT72 candidate evaluator is guarded and was not
run. See `docs/c_v2_candidate_coverage_research_report.md`. Do not proceed to
C v2.1/v2.2 without a separately frozen development iteration and, for
independent claims, the lineage-separated cohort approvals in
`docs/independent_cohort_proposal.md`.

The subsequent C v2.0b topology hypothesis produced a nominal synthetic metric
gate pass, but a post-run conformance review found an occupied-cell component
classification defect and structural fixture-label/construction defects. The
formal result is archived as invalid; no causal replay or FIT72 screen was
run. See `docs/c_v2b_topology_research_report.md`; do not treat its numeric
screen as evidence for further FIT work.

C v2.0c is now a separate correctness-first implementation and protocol. An
independent brute-force BFS reference, exhaustive small-grid checks, 1,000
seeded randomized public-grid cases, and pre-policy annotation validation are
required before its 48-case formal mechanism suite. FIT access remains gated
on both the numeric screen and an independent conformance review.

The frozen v2 mechanism screen completed with a numeric rejection: its
topology selector violated the preregistered graph-work bound in 29 of 48
fixtures. The separate review is `INVALID_STOP_BEFORE_FIT`; no causal replay or
FIT access was performed. See `docs/c_v2c_topology_research_report.md`.

## Intended portfolio outcome

Reproducible code, clear research question, defensible baselines, ablations, repeated-seed results with uncertainty, failure analysis, and a candid simulation limitations section.

## Phase 1 foundation implementation

The repository now contains the partial-observation 2D testbed and the static
and periodic sanity baselines only. Explicit JSON layouts separate development
from reserved held-out seeds and layout. The initial comparison is a deterministic
acceptance demonstration, not a test of H1/H2 and not evidence of superiority.
Noise-free seeds repeat the same trajectory and are not independent evidence.
Review `docs/experimental_protocol.md` and the validation record before expanding
the scenario suite or implementing additional algorithms. The simulator uses a
point robot and does not model bipedal traversability or physical walking.
