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

## Intended portfolio outcome

Reproducible code, clear research question, defensible baselines, ablations, repeated-seed results with uncertainty, failure analysis, and a candid simulation limitations section.
