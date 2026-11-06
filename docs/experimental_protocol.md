# Phase 1 Experimental Protocol (Draft — Freeze Before Final Evaluation)

## Purpose

Test the *failure mode first*, without assuming that a proposed method improves results.

## Environment

- Small 2D indoor grid with fixed walls and corridors.
- Pedestrians move and may wait, temporarily blocking cells and occluding sensors.
- Persistent obstacles can be added, removed, or relocated between episodes/days.
- The simulator tracks ground truth separately from robot-accessible observations.
- Robot sensing is limited by range, field of view if configured, line-of-sight occlusion, and noise.
- Avoid giving the robot true pedestrian/object class, lifetime, or future positions unless explicitly testing an oracle upper bound.

## Baselines in order

1. Static memory (sanity baseline).
2. Periodic map refresh (sanity baseline).
3. Change-aware occupancy persistence model from a defensible existing formulation.
4. Uncertainty-triggered re-observation.
5. Only after these: any proposed task-aware method.

Use the same planner, action constraints, observation model, initial states, and paired random episode seeds for every method. Avoid oracle leakage through initial maps.

## Evaluation dimensions

- Temporary obstruction duration and pedestrian density.
- Persistent object relocation rate.
- Observation frequency, range, noise, and occlusion.
- Map layouts and unseen layouts.
- Observation costs and task deadlines, if modeled.

## Metrics (final operational definitions to be frozen in code)

- **Task success:** reached goal within allowed steps without exceeding safety constraints.
- **Collision:** contact with an occupied ground-truth cell during attempted movement, counted separately from a near miss.
- **Travel cost:** executed movement length and elapsed simulation steps (report separately).
- **Observation cost:** number and/or explicit simulated cost of extra observation actions.
- **False persistent occupancy:** temporary pedestrian-occupied cells incorrectly committed to persistent map after pedestrian departure.
- **Stale memory:** mismatch between robot's long-term persistent occupancy belief and actual persistent geometry.
- **Map-update error:** false additions and missed persistent changes, each reported separately.

A collision-free result may follow simply from the motion checker; explain whether movement is physically blocked or collisions are actually possible.

## Reproducibility

- Store random seed, scenario ID, configuration, method version, and commit SHA for each run.
- Preserve development and held-out evaluation scenarios.
- Run paired seeds across methods; report distributions/intervals rather than a single best run.
- Save CSV summaries and machine-readable configs, but do not commit huge generated files.

## Research-validity checks

- Does the robot ever access true lifetime or semantic labels?
- Are map updates and sensor errors distinguishable from navigation errors?
- Do all policies share the same planner and obstacle-handling rules?
- Are enough hard scenarios included without cherry-picking?
- Are new-method results compared against meaningful existing baselines?

## First acceptance test for Codex

A small deterministic scenario with a pedestrian temporarily blocking a corridor and a persistent obstacle appearing elsewhere must show: (i) different hidden truth and observable map; (ii) a reproducible rollout; (iii) a simple saved visualization; (iv) output metrics and passing tests. No RL and no G1 integration at this step.

## Implemented Phase 1 semantics

These definitions apply to `phase1-v0.1`. Final research evaluation is still
pending review; the held-out configuration has not been used for tuning.

**Boundary:** only ternary occupancy arrays (`-1` unknown, `0` free, `1` occupied)
reach baseline memory. The planner receives that map, pose, goal and the shared
unknown-cell rule. Neither receives obstacle types, schedules, identities or
ground-truth geometry. The experiment harness owns the simulator and evaluator.
Grid dimensions, start and goal are public. Collision outcomes block movement
but do not correct either baseline's map. Python isolation is architectural,
not a security sandbox.

**Time and sensing:** the initial observation is at step 0. Each subsequent step
advances pedestrians/objects, optionally observes, replans, then attempts one
cardinal move or waits. Periodic refresh happens at positive multiples of the
interval. Sensing has no duration; its configurable cost is a separate resource.
No continuous or free collision-triggered sensing occurs. Range is Euclidean;
occlusion uses conservative supercover rays with the first occupied cell visible
and cells behind it unknown. Noise independently flips visible binary occupancy
after visibility is computed; unknown cells remain unknown. A seed/time-indexed
RNG pairs noise across methods when their observations occur at the same time.

**Task metrics:** success is reaching the goal within the step budget (no extra
collision threshold). Success rate is the arithmetic mean of episode success.
Travel distance counts successful unit moves. Elapsed steps counts advances,
including waits and blocked attempts. Collision count sums blocked move attempts
and one contact per step when dynamic occupancy enters the robot's current cell;
both can happen in one step. There is no physical penetration during movement,
injury model, or near-miss metric. Observation count includes the initial call;
observation cost is count times the configured scalar cost.

**Map metrics:** truth for map comparison is static walls plus current persistent
objects, never pedestrians. Metrics are sampled at step 0 and after each action.
Unprefixed error columns sum cell counts over these snapshots (cell-samples);
`final_` columns give only final snapshot cell counts. Thus long-lived errors
cost more and episode length affects totals; they are not distinct-event counts.

- Stale-map errors: known map cells disagreeing with persistent truth; unknown
  cells are excluded.
- False persistent occupancy updates: currently remembered occupied cells whose
  most recent write was an actual pedestrian-only occupied observation, after
  the pedestrian departs and while persistent truth is free. Evaluator-only
  attribution tracks writes and resets on every observed overwrite, so noise
  false positives and unrelated formerly visited cells are excluded. These are
  retained transient commitments, not semantic classification predictions.
- Missed persistent changes: cells touched by a persistent occupancy change at
  any elapsed step for which memory is unknown or disagrees with current truth.
  Additions, removals and both ends of relocations count. A later reversion that
  matches memory is no longer missed. This is a cell-state metric, not latency
  or the number of unrecognized change events.

**Limits:** occupancy mapping cannot identify persistence. The static baseline
may repeatedly collide or wait forever against its frozen initial map; this is
intentional baseline behavior. Optimistic unknown traversal permits exploration
but also collisions; conservative traversal can stall. Pedestrians follow fixed
paths and do not react to the robot or enforce crowd avoidance. Persistent
objects can overlap pedestrians or enter the robot cell. Geometry changes that
occur after early goal completion are outside that episode's measured horizon.
The small scenario set does not support statistical generalization, confidence
intervals over layouts, novelty, or claims about locomotion. Reserve held-out
execution until the research design is reviewed.
