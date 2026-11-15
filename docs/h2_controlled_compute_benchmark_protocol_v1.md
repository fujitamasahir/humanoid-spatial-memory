# H2 Controlled Computational Cost Benchmark Protocol v1

## Purpose and scope

This descriptive development benchmark remeasures the 54 admitted H2
observation models on the exact 36 saved unseen mazes and two existing
high-frequency schedules. It does not create maps or schedules and does not
change policy source, parameters, seed, observation budget, safety logic,
collision shield, navigation, or the 0.75 m/cell assumption. Five repetitions
are paired reruns of the same 3,888 model×map×schedule cases, not new
independent environments.

## Existing timing anomaly

The frozen shared adapter in `scripts/h2_final_common.py` times model
initialization, `core.decide`, and `core.refresh` with
`time.perf_counter_ns()`. Both the 13 historical models and 41 additional
eligible models use this wrapper. It separately times sensor acquisition,
emergency sensing, navigation planning, point planning, and safety decisions;
the High-Frequency engine separately times transition, scene update, and
replay logging. Those components are excluded from Total Model Computation.

Periodic-4 uses `ObservationController.needs_observation`'s interval check.
Periodic-5 uses `CadenceController` and calls `cadence_decision` through the
Persistence-EVI wrapper. `cadence_decision` constructs grid index arrays and
computes known-cell age fractions before its `periodic5` branch checks the
fixed interval; the computed age score does not determine the periodic grant.
This code path can explain the observed excess work. Age-4 uses a different
age-observer path, so it is not simply Periodic-5 with another interval. The
cause is confirmed in source; prior CPU contention and thermal pressure were
not recorded and cannot be excluded as contributors to historical variance.
No implementation is modified in this benchmark.

## Frozen episode conditions

- 54 admitted models from the existing registry; the three blocked models
  remain excluded.
- Exact hashes of the 36 saved map payloads and both saved schedule indices.
- Seed 42, 80-step horizon, 20 paid memory observation cap, existing 61-ray
  spatial memory sensor and independent emergency safety sensor.
- Existing forward-first G1 navigation, selected-action MuJoCo shield, and
  High-Frequency transition engine.
- One worker, one Python process, sequential calls; randomized case/model
  order uses a deterministic PRNG seed recorded in `binding.json`.
- One fixed warm-up episode per model is discarded from measured repetitions.

## Measurement scope

`Total Model Computation = Model Initialization + Observation Decision +
Spatial-Memory Update`. The existing wrapper's array of per-call
`perf_counter_ns()` samples is retained. Sensor acquisition and ray casting,
navigation planning outside the observation model, emergency safety,
selected-action collision checks, dynamic transition generation, MuJoCo scene
updates, replay construction, and file I/O are excluded. Any route search
performed inside the observation decision remains included.

The timer's back-to-back `perf_counter_ns()` cost is measured before the run
and retained as a diagnostic. Raw timings are not corrected. A separate
decision microbenchmark copies a model's controller state outside the timed
region, then times only a single `decide` call. It captures valid early, middle,
and late states from each model's own saved R, BP, and M replay histories. Since
the models' histories diverge, these microbenchmark states are not identical
cross-model inputs; this limitation is reported. Repeated calls begin from a
restored copy of the same state, and no ground-truth occupancy is supplied.

## Warm-up, order, resume, and parity

The smoke stage runs all 54 models on six prespecified existing map×schedule
cases plus eight duplicate tasks. Every result must match the corresponding
existing high-frequency replay semantically before the full run is allowed.
For each of five repetitions, all 3,888 tasks are independently shuffled with
a deterministic seed. Per-episode timing records are journaled and `fsync`ed
before progress advances. A SHA-256 and unique key protect each record;
`--resume` skips only verified completed keys.

The parity digest covers scalar behavior and the full normalized replay,
including goal, paid observations, steps, distance, robot trajectory and
heading, selected/executed actions, observations and memory, environment event
history, emergency interventions, shield rejections, pedestrian/object states,
contacts, and termination. Only timing/runtime fields and the duplicated
replay metrics object are omitted. Each of all 19,440 measured episodes must
match its stored historical semantic digest. A mismatch stops the run and is
recorded; it is never silently removed.

## Resource estimates and machine controls

The prior 2,952-episode additional-model High-Frequency run took 1,323 seconds
(0.448 s/episode on average). This suggests roughly 29 minutes for one
3,888-episode repetition and about 2.4 hours for five repetitions before warm
up, hashing, and analysis. The smoke stage updates this estimate from its
observed rate. Timing journals and CSV summaries should require less than
250 MB; no full duplicate replay set is stored. The run is sequential and
prints progress/ETA at least every minute, saves resumable records per episode,
and samples `vm_stat` plus high-CPU processes at start, completion, and
15-minute intervals. macOS thermal telemetry is not available without
privileged tools and is recorded as a limitation.

## Analysis

Report component timings, episode-level mean/median/standard deviation/P95/P99,
and decision-call distributions. Repetition variation on the same 72 cases is
kept distinct from case variation. Historical comparison is paired by model
and uses the existing High-Frequency summary. The Pareto set has three
unweighted axes: maximize goal rate, minimize paid observations, and minimize
model computation. Break-even observation price versus Periodic-5 is the extra
fixed model compute divided by paid observations saved. This is a hypothetical
scan-price crossover, not energy or end-to-end runtime. The 10-model poster
table and plot contain Static, Periodic-4, Periodic-5, Age-4, B + Age,
C + Ternary, C-K, RDAO v1, RDAO v1 Footprint, and RDAO v1 Gate Every.

## Execution

```sh
.venv/bin/python scripts/run_h2_controlled_compute_benchmark.py prepare
.venv/bin/python scripts/run_h2_controlled_compute_benchmark.py smoke
.venv/bin/python scripts/run_h2_controlled_compute_benchmark.py run
# After interruption:
.venv/bin/python scripts/run_h2_controlled_compute_benchmark.py run --resume
.venv/bin/python scripts/run_h2_controlled_compute_benchmark.py analyze
.venv/bin/python scripts/run_h2_controlled_compute_benchmark.py verify
```

Output is exclusive to `results/phase2_mujoco/h2_controlled_compute_benchmark_v1/`.
Existing H2 results, bindings, model implementations, and evidence are read-only.
