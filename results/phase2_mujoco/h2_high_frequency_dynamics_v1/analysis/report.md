# H2 High-Frequency Dynamic Environment Evaluation

Descriptive robustness extension on the same admitted H2 maps. This is not independent validation.

## High-frequency results

| Arm | Goals / 72 | Rate | Contact episodes | Paid obs. mean (total) | Steps mean | Distance mean (m) | Dynamic changes mean | Change rate | Total rays | Emergency interventions | Blocked actions | Mean decision (ms) | Mean wall (s) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| periodic4 | 54/72 | 0.750 | 0 | 11.29 (813) | 43.19 | 22.78 | 43.19 | 1.000 | 189710 | 26 | 40 | 0.000 | 0.270 |
| periodic5 | 57/72 | 0.792 | 0 | 9.43 (679) | 43.72 | 21.91 | 43.72 | 1.000 | 192028 | 31 | 129 | 0.000 | 0.269 |
| age4 | 57/72 | 0.792 | 0 | 11.26 (811) | 39.81 | 21.48 | 39.81 | 1.000 | 174826 | 30 | 51 | 0.000 | 0.256 |
| age5 | 56/72 | 0.778 | 0 | 10.62 (765) | 42.29 | 22.05 | 42.29 | 1.000 | 185745 | 22 | 78 | 0.000 | 0.265 |
| age6 | 53/72 | 0.736 | 0 | 9.51 (685) | 45.39 | 23.09 | 45.39 | 1.000 | 199348 | 27 | 139 | 0.000 | 0.281 |
| age_route_rescue | 57/72 | 0.792 | 0 | 11.11 (800) | 39.81 | 21.49 | 39.81 | 1.000 | 174826 | 30 | 46 | 0.000 | 0.347 |
| age_route_clock | 56/72 | 0.778 | 0 | 12.51 (901) | 41.51 | 20.92 | 41.51 | 1.000 | 182329 | 28 | 59 | 0.000 | 0.390 |
| rdao_v2 | 57/72 | 0.792 | 0 | 8.64 (622) | 42.15 | 22.28 | 42.15 | 1.000 | 185135 | 26 | 30 | 0.000 | 0.636 |
| rdao_v21 | 56/72 | 0.778 | 0 | 7.40 (533) | 41.14 | 20.81 | 41.14 | 1.000 | 180682 | 31 | 77 | 0.000 | 0.690 |
| caa_fast | 55/72 | 0.764 | 0 | 10.61 (764) | 42.36 | 21.81 | 42.36 | 1.000 | 186050 | 22 | 79 | 0.000 | 0.277 |
| caa_full | 55/72 | 0.764 | 0 | 10.58 (762) | 42.36 | 21.81 | 42.36 | 1.000 | 186050 | 22 | 79 | 0.000 | 0.273 |
| raa_defer | 56/72 | 0.778 | 0 | 10.62 (765) | 42.29 | 22.05 | 42.29 | 1.000 | 185745 | 22 | 78 | 0.000 | 0.291 |
| uncertainty | 52/72 | 0.722 | 0 | 9.47 (682) | 45.78 | 23.00 | 45.78 | 1.000 | 201056 | 27 | 99 | 0.000 | 0.282 |

## Historical H2 final 12-arm reference

These results use the same saved maps but the former scheduled object-change mechanism. They are historical context; the transition mechanism differs, so the comparison does not isolate change frequency.

| Arm | Prior goals / 72 | Prior paid mean | Prior steps mean | Prior distance mean (m) | Prior contacts |
|---|---:|---:|---:|---:|---:|
| age4 | 59/72 | 11.22 | 39.61 | 21.51 | 0 |
| age5 | 57/72 | 10.60 | 42.11 | 22.03 | 0 |
| age6 | 56/72 | 9.62 | 45.76 | 23.46 | 0 |
| age_route_clock | 58/72 | 12.22 | 40.07 | 20.40 | 0 |
| age_route_rescue | 59/72 | 11.06 | 39.61 | 21.53 | 0 |
| caa_fast | 57/72 | 10.58 | 42.11 | 22.02 | 0 |
| caa_full | 57/72 | 10.56 | 42.11 | 22.02 | 0 |
| periodic4 | 55/72 | 11.26 | 43.03 | 22.64 | 0 |
| periodic5 | 60/72 | 9.18 | 42.56 | 21.48 | 0 |
| raa_defer | 57/72 | 10.60 | 42.11 | 22.03 | 0 |
| rdao_v2 | 59/72 | 8.72 | 41.72 | 22.11 | 0 |
| rdao_v21 | 56/72 | 7.64 | 41.44 | 21.05 | 0 |

## Original-condition Uncertainty comparison

Uncertainty completed 53/72 goals; mean paid observations 9.42, mean steps 44.94, mean distance 22.98 m.

## Interpretation and limits

Object transitions are state-dependent. Different policies can realize different event paths despite common random streams; results estimate performance under a shared transition mechanism, not identical realized environments. The change frequency and transition mechanism changed together, so differences cannot be attributed to frequency alone.
The whole-maze bootstrap and family summaries are exploratory, unadjusted comparisons. No independent-test or superiority claim is made. The episode replays contain explicit step states and event histories; inspect their manifests and the replay schema for provenance and reconstruction.

## Artifacts

- Full primary metric rows: `primary/episodes.csv`
- 936 complete primary replays: `replays/primary/`
- 72 original-condition Uncertainty replays: `replays/original_uncertainty/`
- Smoke records: `replays/smoke/`
- Paired whole-maze bootstrap: `analysis/paired_whole_maze_bootstrap.csv`
- Protocol and schema: `docs/h2_high_frequency_dynamics_protocol_v1.md`, `docs/h2_high_frequency_dynamics_replay_schema.md`
