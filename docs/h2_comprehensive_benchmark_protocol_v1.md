# H2 Comprehensive Benchmark Protocol v1

## Purpose and status

This is a retrospective descriptive comparison of the 57 named H2 observation
models on the existing 36 admitted maps. It is not a held-out validation. The
13 models already evaluated under H2 are reused from their committed Original
and High-Frequency result stores. No world, schedule, seed, or policy parameter
is regenerated or tuned.

The primary matrix is 44 additional models × 36 saved maps × 2 saved schedules
in each of two conditions (Original and High-Frequency). Each episode uses
seed 42, H80, a 20-observation cap including the initial scan, 61 memory rays
(120°, 6 m), the existing 61-ray 360° emergency sensor (2 m), unchanged G1
forward-first planning, selected-action MuJoCo shield, and emergency safety.
The grid scale remains 0.75 m/cell.

The protocol is frozen before new primary episodes. Individual model gates in
their source protocols remain binding. A model without its required prior
FIT authorization is reported as blocked; no gate is bypassed and no surrogate
policy is substituted. In particular, the current C-v2c review is
`INVALID_STOP_BEFORE_FIT`, and the current shared C-candidate mechanism gate is
`REJECTED_BEFORE_FIT72`; C-Topology3-c, C-Route3, and C-RouteK therefore remain
blocked unless their own existing prospective authorization is valid. The
C-v2d gate is `ACCEPTED_FOR_FIT`; its scope and arm list still control what it
authorizes. Gate status is recorded in the registry and binding.

## Conditions and randomness

Original uses the exact 36 map payloads and two previously saved schedules.
High-Frequency uses the final engine and event namespace from commit
`015ae8d3f17d9bd9839254eabe4dafa145d09491`, with one feasible change per active
navigation step, the saved constraints and object limits, and model-independent
common random streams. Ground truth is used only by the evaluator and dynamic
transition engine, never as an observation-policy input. Each model's own
robot trajectory determines its state-dependent feasible transitions.

## Integrity, checkpointing, and replay

Inputs are hash-verified before evaluation. The 836-file protected integrity
audit and prior H2 manifests are rechecked before and after each stage. Each
new episode is stored under a new versioned directory with exclusive creation;
resume may accept only a matching protocol/source/map binding and must never
replace a completed episode. A full per-step replay and exact environment
event trace are required for every new episode. The established H2 replay
schema is extended only in the new output namespace. Existing 13-model replays
are linked by path and hash; missing historical fields are left missing.

## Validation and execution stages

1. Audit all source and arm definitions; freeze the model registry and binding.
2. Run relevant non-generative unit tests and controller/API integration tests.
3. Reproduce representative saved baseline episodes under both conditions and
   compare semantic traces and metrics before primary evaluation.
4. Run a smoke matrix on two prespecified maps and both schedules, for each
   eligible additional model and both conditions. Blocked models stay recorded
   as blocked and are not run.
5. Run eligible Original and High-Frequency primary episodes with atomic
   per-episode checkpointing and progress/ETA output.
6. Verify all episode, replay, event, sensor-cap, shield-query, and dynamic
   constraint invariants before analysis.

The task's requested 352-episode smoke count and 6,336 new primary count assume
all 44 arms are eligible. Any gate-blocked arm reduces actual executed counts;
the report must show the exact denominator and incomplete count.

## Analysis

Reuse all 13 historical models and combine only metrics whose definitions and
timing scopes are compatible. Report incompatible or unavailable measures
explicitly. Compare success, contact-free goal, observations/rays, steps,
distance, memory errors where available, safety events, and separated timing
components. Failure distance/steps are not described as efficiency gains.
Use paired whole-maze bootstrap (5,000 draws, fixed seed, 36 clusters, both
schedules kept together) for prespecified contrasts against Periodic-4,
Periodic-5, Age-4, and Age-5. Label the 57-model comparisons exploratory and
describe multiple-comparison limitations. Include break-even cost curves and
Pareto sets without a single weighted winner score. Do not infer real-world
power savings from simulator timing.

## Non-goals and stop rules

Do not change algorithms, parameters, protocols, sensors, safety systems,
maps, schedules, or historical evidence. Do not access reserved or newly
generated navigation populations. Do not update the game or portfolio. Stop
the affected arm if its gate, source binding, replay integrity, or safety
invariants fail; preserve valid partial checkpoints and report them. A partial
matrix must never be labeled complete.
