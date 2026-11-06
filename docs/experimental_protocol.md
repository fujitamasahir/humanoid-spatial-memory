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
