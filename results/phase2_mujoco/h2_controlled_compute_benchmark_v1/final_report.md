# H2 Controlled Computational Cost Benchmark

**Status:** Complete only if `validation_status.json` reports `COMPLETE_WITH_DECLARED_B_AGE_HISTORICAL_NONPARITY`; this status explicitly records a historical mismatch in the corrected B + Age arm.

Descriptive development timing rerun on the same 36 saved maps and two saved high-frequency schedules. Each of five repetitions contains the same 3,888 model×map×schedule episodes; repeats are not additional independent environments. No experiment policy, parameter, observation budget, safety, map, or schedule was changed.

## Existing anomaly diagnosis

Periodic-4 calls the frozen baseline `ObservationController` periodic interval test. Periodic-5 calls `CadenceController` through `PersistenceEVIController`; its `_score` runs `cadence_decision`, which allocates a full grid index and computes known-cell age fractions before checking the periodic5 mode. The score is not used by the fixed-period grant decision. This unnecessary per-call scoring is confirmed in source at `src/spatial_memory/cadence_age.py`; it explains the larger decision workload. Age-4 uses the age observer and is a separate code path. The timing gap is therefore not explained by observation interval alone. No controller was edited for this benchmark.

Existing measurements used `time.perf_counter_ns()` in the shared `h2_final_common.run_case` wrapper for model initialization, `core.decide`, and `core.refresh`. The 13 historical arms and 41 additional admitted arms both pass through that wrapper. Sensor acquisition, emergency sensing, navigation planning, selected-action shielding, scene updates, event generation, replay capture and I/O are separately timed or outside that scope. Historical bindings show Python 3.12.10, arm64 macOS 26.6.2, MuJoCo 3.17.0, NumPy 2.2.6, and the same hostname as this rerun. Historical CPU contention/thermal state was not logged, so it cannot be ruled out retrospectively.

## Controlled protocol and integrity

- Bound source commit: `fbdd8898dc9b5be4b5c720c8888940b6efbd7ed0`; one sequential process, 8 logical CPUs available.
- One fixed warm-up episode per model; measured model×case tasks shuffled with a seeded PRNG independently for each repetition.
- Timer: `time.perf_counter_ns()`; timer-pair overhead probe is in `binding.json`. Raw measured time is retained, not corrected.
- Per-model compute = initialization + observation decision + spatial-memory update. The three components are reported separately.
- Every measured run is compared by semantic SHA-256 against its existing episode trace, excluding only timing/runtime fields. The 53 unchanged model definitions must pass every repetition. Corrected B + Age is separately classified against its historically mislabeled B + C traces; every mismatch remains in the parity ledger.
- Full hidden occupancy is evaluator/replay data only. Controller inputs are supplied by the frozen runner; the separate microbenchmark captures controller-owned state before a legitimate decision and never passes ground truth.
- Checkpoint journal records are fsynced per episode and hash-checked for safe `--resume`.

## Timing comparisons

| Contrast | Controlled A (ms/episode) | Controlled B (ms/episode) | Ratio B/A |
|---|---:|---:|---:|
| periodic4 vs periodic5 | 0.417197 | 4.210509 | 10.092 |
| age4 vs age5 | 2.107688 | 4.541112 | 2.155 |
| periodic5 vs age4 | 4.210509 | 2.107688 | 0.501 |
| periodic5 vs rdao_v1_footprint | 4.210509 | 494.537757 | 117.453 |
| rdao_v1 vs rdao_v1_footprint | 457.905020 | 494.537757 | 1.080 |
| rdao_v1_footprint vs rdao_v1_gate_every | 494.537757 | 424.582061 | 0.859 |

## Computational cost definition and variability

Episode-level repeated measurements are grouped by model and repetition in `timing_breakdown.csv`. Within-case repetition variation is retained separately from across-case variation; maps are not treated as independent repeated observations. The decision microbenchmark uses three model-specific states reconstructed by executing the saved legitimate history: early (R), middle (BP), late (M). These are not identical cross-model inputs because controller histories diverge. Controller state copying is outside each timed decision. Per-model/state mean, median, standard deviation, P95, P99, and sample count are in `decision_microbenchmark.csv`; tail estimates are descriptive and less stable when the model required fewer samples.

## Pareto and observation break-even

`pareto_frontier.csv` keeps the three axes separate: maximize goal rate, minimize paid observations, minimize model compute. `break_even_analysis.csv` uses Periodic-5 as reference and divides extra fixed model computation by paid observations saved. It is a hypothetical scan-cost crossover, not measured sensor energy, battery use, or end-to-end runtime.

## Results summary

- Repeated episodes: 19,440; semantic parity records: 19,440.
- Detailed model/episode/repetition values and plots are in this directory; poster subset is `poster_10_model_costs.csv` plus its PNG/SVG chart.
- Smoke: six saved map×schedule cases across 54 models, plus eight duplicate executions; see `smoke_gate.json`.
- H2 recovery documented that the old `b_age` episodes enabled EVI and measured B + C; current B + Age disables EVI. This known historical non-parity is recorded, and its old timing is not a valid paired comparison. Other models require exact parity.
- No new maps or schedules were generated. Existing evidence remains unchanged.

## Machine-readable files

- `episode_timings.csv`, `decision_microbenchmark.csv`, `model_summary.csv`, `timing_breakdown.csv`
- `historical_vs_new_comparison.csv`, `parity_validation.csv`, `pareto_frontier.csv`, `break_even_analysis.csv`
- `environment_info.json`, `binding.json`, `runtime_observations.jsonl`, `validation_status.json`
- Figures are supplied in PNG and SVG under `figures/`.

## Repetition and case variability

The five repetitions replay the same 72 fixed map×schedule cases per model; they are repeated measurements, not 360 independent maps. `case_repetition_variability.csv` reports each model×case×component mean, standard deviation, P95 and P99 across the five repetitions. `repeatability_variance_summary.csv` reports average within-case repetition SD separately from the across-case SD of the 72 case means.

## Measurement machine observations

The run used the bound environment in `environment_info.json`; periodic manual system load and `vm_stat` observations are in `runtime_observations_external.jsonl`. The macOS permission policy denied `ps`/`top` process enumeration, and no thermal telemetry was available, so process-specific contention and thermal throttling cannot be ruled out.

## Historical B+Age comparison qualification

All 360 corrected B+Age traces are retained as expected historical non-parity: the old arm labeled B+Age had EVI enabled (B+C). The other 53 models have exact semantic parity for all 19,080 model×case×repetition records.
