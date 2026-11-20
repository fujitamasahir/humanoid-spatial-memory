# H2 High-Frequency Dynamic Environment Protocol v1

Status: prospective protocol for a descriptive robustness extension. Frozen
source base: `12dc945c7da496e6cfc5dd79d6977b4c48d705c1`. The prior H2 final
protocol and its outputs remain read-only. This extension reuses the same 36
admitted maps, two saved schedules per map, initial object placements, start,
goal, pedestrian paths, G1 model, sensor, safety system, selected-action
shield, 80-step horizon, 20-observation budget, and seed 42. It changes the
persistent-object transition mechanism to one attempted change per navigation
step. It is not an independent generalization evaluation.

## Arms and conditions

The 13 frozen arms are Periodic-4, Periodic-5, Age-4, Age-5, Age-6,
Age-Route-Rescue, Age-Route-Clock, RDAO v2, RDAO v2.1, CAA-Fast, CAA-Full,
RAA-Defer, and the prior `ObservationController(mode="uncertainty")` with its
unchanged defaults. No policy implementation or parameter is changed. The
primary matrix is 36 maps × 2 schedules × 13 arms = 936 episodes. The
Uncertainty-only original-dynamics comparison adds 72 episodes. A two-map,
two-schedule, 13-arm smoke is a separate validation stage (52 episodes).

## High-frequency object transition

At s0, use the saved schedule's original object positions. Then, once after
the pedestrian schedule advances at each navigation step and before emergency
sensing, memory-observation decision, planning, or action, select exactly one
feasible operation uniformly among Addition, Removal, and Relocation. Object
count stays in [0,4]. Additions/relocation destinations must be outside the
robot-centered Chebyshev-radius-1 exclusion zone, walls, current objects,
current pedestrian cells, and goal; MuJoCo G1 public collision-geometry
footprint bounds must also be disjoint. Removal has no proximity restriction.
Relocation is atomic and keeps its object ID. Candidate object states are
accepted only when 4-connected ground-truth occupancy retains a path from the
current robot cell to the goal. This connectivity check belongs only to the
environment generator. It is not visible to the observation model, memory,
planner, safety controller, or action shield.

For every step, enumerate candidate operations deterministically. Select the
operation type uniformly among types with at least one legal candidate, then
select one legal candidate uniformly. If no type has a legal candidate,
record an explicit `no_op` with reason and all rejection counts. Never silently
skip an event. Relocation source and destination are one transition.

## Common random numbers

The per-step random stream is keyed by the UTF-8 fields
`h2-high-frequency-dynamics-v1`, map identity, decimal schedule, decimal seed,
decimal step, and purpose. Each field is length-prefixed by unsigned
little-endian 32-bit length; SHA-256's first 16 bytes seed NumPy Philox. Purpose
streams for type and candidate selection are independent. Model identity is
excluded. Candidate enumeration and tie order are sorted lexicographically.
Robot-state-dependent feasible sets may produce different realized events;
the estimand is a shared state-dependent transition mechanism, not identical
realized event traces.

## Execution order

Initial observation is at s0 on the saved initial object placement. For step
1..80: advance the saved pedestrian path; generate and apply one object
transition; synchronize the MuJoCo mocap scene; run emergency sensing; decide
and, if granted, perform the paid memory observation; plan and apply the
existing safety/controller and selected-action shield; record the complete
post-action state. Existing navigation and sensing implementations are
unchanged.

## Replay schema

See `docs/h2_high_frequency_dynamics_replay_schema.md`. Each episode is a
standalone gzip-compressed JSON replay with explicit s0, all events, all object
IDs and placements, pedestrians, robot poses/actions, planned paths, memory,
observed cells, truth grids, safety/shield feedback, contacts, and outcome.
Seeds alone are not a replay. Each output is published exclusively and
atomically; a journal records its SHA-256. Resume verifies completed episodes
before skipping them.

## Analysis and limits

Report the previous 12-arm H2 final results as historical context. The only
matched original-dynamics rerun in this extension is Uncertainty on the same
72 map/schedule keys. Keep the two schedules linked within each of 36 map
clusters for exploratory paired whole-maze bootstrap (5,000 draws, seed
2026111401). Report full-horizon failures without success-only efficiency
credit. Separate policy decision/update/sensing/safety/navigation timing from
dynamic candidate generation, scene update, and replay logging. No CPU-energy,
real-robot latency, independent validation, or causal attribution to change
frequency alone is claimed.

The grid is 25×25 at 0.75 m/cell. Connectivity is 4-connected raster
connectivity. The actual G1 collision model is used for runtime safety and for
the generator's conservative public-geometry exclusion check; connectivity
does not certify all continuous dynamic motion. This experiment does not alter
the frozen H2 algorithms, previous reports, map files, or historical outcomes.
