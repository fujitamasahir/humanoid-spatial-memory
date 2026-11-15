# H2 High-Frequency Dynamic Environment Extension

## Purpose and status

This is a descriptive development robustness extension over the existing 36 H2 maps. It tests the unchanged navigation arms under a new, frequently changing object environment. It is not an independent scientific validation and does not establish that higher transition frequency alone caused any outcome differences.

The experiment is bound to frozen H2 base commit `12dc945c7da496e6cfc5dd79d6977b4c48d705c1`; the primary run used the separately committed extension binding `binding_amendment_3.json`. The original H2 algorithms, historical evaluation outputs, Phase 1.5 evidence, and 836 protected files were left unchanged. Existing 36 map assets are copied byte-for-byte and individually hashed in the new result.

## Conditions

- 13 frozen methods × 36 existing maps × 2 schedules = 936 primary episodes.
- Seed 42, 80-step navigation horizon, 20 paid-observation cap, and 0.75 m/cell.
- On every active navigation step, the environment performs exactly one feasible addition, removal, or relocation. A transition is selected from equal-probability feasible event classes. Each event is model-independent under a common random stream keyed by map, schedule, seed, step, and purpose.
- Object count is 0–4. Candidate cells respect walls, 3×3 robot/pedestrian/goal exclusion regions, actual G1 collision geometry using conservative cell extents, and start-goal grid connectivity. Connectivity uses an articulation-point check. No controller receives generator state, future pedestrian positions, or unobserved occupancy.
- The sensor, memory, navigation policy, action selection, and MuJoCo safety shield remain the frozen H2 implementations.

The full replay records object identifiers and before/after states, event decision and feasibility, map truth, pedestrian state, robot state, observation/memory state, selected and executed actions, shield outcomes, contacts, and per-component timings. Episode files are compressed JSON and are accompanied by artifact manifests.

## Primary results

The 936 episodes completed without interruption. There were 39,730 active navigation steps and 39,730 non-no-op environment changes (100%). The integrity verifier reconstructed all event chains, replay lengths, object IDs, and event rates. It found no connectivity or exclusion-zone violations. No arm recorded an unwanted-contact episode.

| Method | Goals / 72 | Mean paid observations | Mean steps (all episodes) | Mean distance (m, all episodes) | Decision time (ms/episode) | Mean wall time (s/episode) |
|---|---:|---:|---:|---:|---:|---:|
| Periodic 4 | 54 | 11.29 | 43.19 | 22.78 | 0.043 | 0.270 |
| Periodic 5 | 57 | 9.43 | 43.72 | 21.91 | 1.831 | 0.269 |
| Age 4 | 57 | 11.26 | 39.81 | 21.48 | 0.756 | 0.256 |
| Age 5 | 56 | 10.62 | 42.29 | 22.05 | 1.973 | 0.265 |
| Age 6 | 53 | 9.51 | 45.39 | 23.09 | 0.828 | 0.281 |
| Age route rescue | 57 | 11.11 | 39.81 | 21.49 | 91.915 | 0.347 |
| Age route clock | 56 | 12.51 | 41.51 | 20.92 | 82.085 | 0.390 |
| RDAO v2 | 57 | 8.64 | 42.15 | 22.28 | 356.158 | 0.636 |
| RDAO v2.1 | 56 | 7.40 | 41.14 | 20.81 | 407.978 | 0.690 |
| CAA fast | 55 | 10.61 | 42.36 | 21.81 | 3.386 | 0.277 |
| CAA full | 55 | 10.58 | 42.36 | 21.81 | 3.384 | 0.273 |
| RAA defer | 56 | 10.62 | 42.29 | 22.05 | 22.702 | 0.291 |
| Uncertainty | 52 | 9.47 | 45.78 | 23.00 | 1.890 | 0.282 |

The timing values are sums of instrumented decision calls within an episode; they are measured software/simulator time on this machine, not real-time or energy guarantees. Detailed components, call-time quantiles, episode metrics, paired contrasts, failure reasons, and figures are in [`analysis_v4`](../results/phase2_mujoco/h2_high_frequency_dynamics_v1/analysis_v4/README.md).

The original-condition Uncertainty rerun reached 53/72 goals versus 52/72 under the high-frequency transition environment. This descriptive pair changes both the transition mechanism and the realized controller path, so it does not isolate a frequency effect.

## Paired analysis and interpretation

Paired contrasts resample the 36 map identities as clusters and keep each map's two schedules together. The analysis uses 5,000 deterministic bootstrap draws and reports unadjusted 95% percentile intervals. For example, Periodic 5 minus Periodic 4 has a goal-rate contrast of +0.042 with a 95% interval of [-0.028, +0.125]; it is not a clear improvement. Several paired paid-observation contrasts favor lower observation counts, but their operational value must be considered alongside completion, distance, and timing. The complete contrasts are in `analysis_v4/paired_whole_maze_bootstrap.csv`.

No best-method or superiority claim is made. The results show that all methods were contact-free in this finite development set, while goal completion ranged from 52/72 to 57/72. The shared random stream is model-independent, but event feasibility is state-dependent: after paths diverge, the realized events need not match. Higher event frequency and the changed state-dependent transition mechanism are therefore not separable causes in this experiment.

## Validation and preserved initial smoke issue

An initial 52-episode smoke stage exposed that the wrapper continued generating events during a post-goal accounting tail used by the frozen evaluator to fill its common 80-step horizon. That initial smoke was sealed, retained, and explicitly invalidated; none of its measurements entered the primary run. The wrapper was corrected so no navigation environment transition occurs after a goal-terminal state, while the frozen evaluator's common-horizon accounting remains intact. The corrected 52-episode smoke was rerun and passed event-count, cap, connectivity, and replay checks. Amendment notes document the sequence; the initial files were not removed.

The final primary replay verifier passed for 936/936 episodes. All 864 previous H2 FIT entries also reproduced their frozen episode outputs exactly before the new evaluation. The non-generative analysis reads saved replay and diagnostic data only. See the machine-readable binding and manifests under `results/phase2_mujoco/h2_high_frequency_dynamics_v1/`.

## Limitations

- This is a descriptive development evaluation on the same 36 maps, not independent validation.
- The transition mechanism and rate changed together relative to the historical scheduled-dynamics runs.
- Bootstrap intervals are unadjusted across the many exploratory method/metric comparisons.
- Zero contact episodes in 936 episodes does not prove zero risk outside this evaluated set.
- Simulator timings are machine-specific and should not be interpreted as deployment latency.
