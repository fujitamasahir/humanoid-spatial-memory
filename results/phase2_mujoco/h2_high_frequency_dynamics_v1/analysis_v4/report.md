# H2 High-Frequency Dynamic Environment Evaluation — Corrected Analysis

Descriptive extension using the same 36 H2 maps. It is not independent validation. The prior analysis pass is preserved separately; this v4 analysis sources timing measurements from the per-episode diagnostics and corrects its zero-valued decision-time column.

| Arm | Goals / 72 | Rate | Contact episodes | Paid mean (total) | Steps mean / success-only | Distance mean / success-only (m) | Changes mean | Change rate | Combined rays | Emergency interventions | Decision mean (ms) | Wall mean (s) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| periodic4 | 54/72 | 0.750 | 0 | 11.29 (813) | 43.19 / 30.925925925925927 | 22.78 / 17.47222222222222 | 43.19 | 1.000 | 189710 | 26 | 0.043 | 0.270 |
| periodic5 | 57/72 | 0.792 | 0 | 9.43 (679) | 43.72 / 34.175438596491226 | 21.91 / 18.473684210526315 | 43.72 | 1.000 | 192028 | 31 | 1.831 | 0.269 |
| age4 | 57/72 | 0.792 | 0 | 11.26 (811) | 39.81 / 29.228070175438596 | 21.48 / 16.69736842105263 | 39.81 | 1.000 | 174826 | 30 | 0.756 | 0.256 |
| age5 | 56/72 | 0.778 | 0 | 10.62 (765) | 42.29 / 31.517857142857142 | 22.05 / 17.558035714285715 | 42.29 | 1.000 | 185745 | 22 | 1.973 | 0.265 |
| age6 | 53/72 | 0.736 | 0 | 9.51 (685) | 45.39 / 32.9811320754717 | 23.09 / 17.816037735849058 | 45.39 | 1.000 | 199348 | 27 | 0.828 | 0.281 |
| age_route_rescue | 57/72 | 0.792 | 0 | 11.11 (800) | 39.81 / 29.228070175438596 | 21.49 / 16.69736842105263 | 39.81 | 1.000 | 174826 | 30 | 91.915 | 0.347 |
| age_route_clock | 56/72 | 0.778 | 0 | 12.51 (901) | 41.51 / 30.517857142857142 | 20.92 / 17.25 | 41.51 | 1.000 | 182329 | 28 | 82.085 | 0.390 |
| rdao_v2 | 57/72 | 0.792 | 0 | 8.64 (622) | 42.15 / 32.19298245614035 | 22.28 / 18.223684210526315 | 42.15 | 1.000 | 185135 | 26 | 356.158 | 0.636 |
| rdao_v21 | 56/72 | 0.778 | 0 | 7.40 (533) | 41.14 / 30.035714285714285 | 20.81 / 16.875 | 41.14 | 1.000 | 180682 | 31 | 407.978 | 0.690 |
| caa_fast | 55/72 | 0.764 | 0 | 10.61 (764) | 42.36 / 30.727272727272727 | 21.81 / 17.113636363636363 | 42.36 | 1.000 | 186050 | 22 | 3.386 | 0.277 |
| caa_full | 55/72 | 0.764 | 0 | 10.58 (762) | 42.36 / 30.727272727272727 | 21.81 / 17.113636363636363 | 42.36 | 1.000 | 186050 | 22 | 3.384 | 0.273 |
| raa_defer | 56/72 | 0.778 | 0 | 10.62 (765) | 42.29 / 31.517857142857142 | 22.05 / 17.558035714285715 | 42.29 | 1.000 | 185745 | 22 | 22.702 | 0.291 |
| uncertainty | 52/72 | 0.722 | 0 | 9.47 (682) | 45.78 / 32.61538461538461 | 23.00 / 17.942307692307693 | 45.78 | 1.000 | 201056 | 27 | 1.890 | 0.282 |

## Original-dynamics Uncertainty comparison

The original-condition rerun completed 53/72 goals. Paired rows are in `uncertainty_original_vs_dynamic.csv`; environments differ in transition mechanism and can differ by controller path.

## Timing breakdown

The corrected timing table separates initialization, policy/observation decision, map update, paid memory sensing, emergency sensing, navigation planning, point-plan diagnostics, safety decision, dynamic transition generation, MuJoCo frame update, replay logging, and end-to-end episode wall time. Decision-call median/p95/p99/max are in `decision_time_quantiles.csv`. These are simulator/software timings, not energy or real-robot latency.

## Historical reference

The previous H2 final scheduled-dynamics values are retained in `historical_h2_final_reference.json`. Same-map comparisons are descriptive because the dynamic object transition mechanism changed along with frequency; they do not identify a pure frequency effect.

## Interpretation

All 39,730 active primary navigation steps recorded an environmental change (100%). There were no no-op events, connectivity violations, or exclusion-zone violations. The twin-run CRN test verifies that identical public states and random inputs produce identical events; realized paths can still diverge as robot states diverge. Bootstrap contrasts keep both schedules within 36 map clusters, use 5,000 exploratory draws, and are unadjusted. Do not interpret the smallest numerical differences as confirmed superiority.

## Artifacts

- Primary episode metrics: `episodes.csv`
- Paired whole-map bootstrap: `paired_whole_maze_bootstrap.csv`
- Outcome and family summaries, failures, original/dynamic uncertainty pairs, corrected figures, and representative comparison GIF are included alongside this report.
