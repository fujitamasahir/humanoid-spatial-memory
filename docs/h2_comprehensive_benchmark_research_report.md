# H2 Comprehensive Benchmark — Results Report

## Scope and status

This is a descriptive development comparison, not independent validation. The request covers 57 named models × 72 saved map/schedule cases × two conditions (8,208 model-episodes). Thirteen historical models were reused without rerunning; 41 of the 44 additional models were authorized and evaluated. Three were held by their pre-existing research gates, leaving 54 models and 7,776 records. They were not substituted or bypassed.

| Condition | Historical records | New records | Combined records | Goals |
|---|---:|---:|---:|---:|
| Original | 936 | 2,952 | 3,888 | 2,968 (76.34%) |
| High-Frequency | 936 | 2,952 | 3,888 | 2,949 (75.85%) |

Blocked: C-Route3 and C-RouteK lack authorization under the shared candidate-coverage gate (`REJECTED_BEFORE_FIT72`, no valid no-benefit fixture authorization); C-Topology3-c has an invalid C-v2c gate (`INVALID_STOP_BEFORE_FIT`). This is 432 unavailable model-episodes per condition pair, 5.26% of the requested full set. These are blocked evaluations, not negative results.

## Main results

RDAO v1 Footprint had the highest observed goal rate in both conditions: 61/72 (84.72%). Its paired improvement over Periodic-5 was +1.39 percentage points in Original (95% whole-maze bootstrap CI −6.94 to +11.11 pp) and +5.56 pp in High-Frequency (−1.39 to +13.89 pp). Both intervals include zero. Age-Motion and RDAO v1 Gate Every also reached 60/72 (83.33%) in High-Frequency. Periodic-5 reached 60/72 (83.33%) in Original and 57/72 (79.17%) in High-Frequency.

Static used one paid observation per episode and was the lowest-computation option, but reached only 44/72 (61.11%) in both conditions. B + Age and B+C used 3.46 observations in Original and 3.19 in High-Frequency, with 50/72 (69.44%) goals in each condition. C + Ternary and C0 used 5.03 and 4.54 observations respectively and reached 51/72 (70.83%) in both conditions. Several models save observations at substantial computation cost; the Pareto and break-even tables retain this trade-off rather than declaring one universal winner.

Across all model-episodes, Original produced 2,968/3,888 goals (76.34%) and High-Frequency 2,949/3,888 (75.85%), a descriptive aggregate difference of −0.49 pp. Environment dynamics also changed, so this is not an isolated causal estimate of change frequency. No unwanted contacts were recorded in either combined condition. This does not establish safety outside these saved maps and schedules.

The lowest mean measured decision-computation times were Periodic-4 (0.055 ms/episode Original; 0.043 ms High-Frequency), Static (0.079; 0.047 ms), and Periodic+Event (0.080; 0.086 ms). `mean_compute_ms` additionally includes initialization and memory update as defined by the analysis code. Episode wall time is reported separately and includes simulator overhead; it is not an energy or battery measurement.

| Model | Original goals / 72 | Original paid obs. | Original compute ms | High-Frequency goals / 72 | HF paid obs. | HF compute ms |
|---|---:|---:|---:|---:|---:|---:|
| Periodic-5 | 60 (83.33%) | 9.18 | 3.27 | 57 (79.17%) | 9.43 | 2.66 |
| Age-4 | 59 (81.94%) | 11.22 | 1.55 | 57 (79.17%) | 11.26 | 1.25 |
| RDAO v1 Footprint | 61 (84.72%) | 8.94 | 375.51 | 61 (84.72%) | 8.79 | 353.14 |
| Age-Motion | 57 (79.17%) | 11.19 | 2.70 | 60 (83.33%) | 11.03 | 2.71 |
| CAA-Full | 57 (79.17%) | 10.56 | 4.69 | 55 (76.39%) | 10.58 | 3.89 |

The Pareto table uses three objectives: maximize goal rate, minimize paid observations, and minimize initialization + decision + memory-update computation. It contains 15 models in Original and 14 in High-Frequency. Members are listed without ranking in `analysis/pareto_frontier.csv`; the front is an empirical set, not a statistically selected winner. Break-even costs compare this compute sum plus `paid observations × c` against Periodic-5. Examples: Age-4 crosses at about 0.84 ms/observation in Original and 0.77 ms in High-Frequency; B + Age at 21.02 and 19.05 ms; RDAO v1 Footprint at 1,576.55 and 548.57 ms. Age-4 has lower measured compute but uses more observations, so it is favored only below its crossover. Negative values indicate no useful nonnegative crossover under the observed means.

## Paired analysis and interpretation

Paired comparisons preserve all 36 saved maze identities and both schedules within each whole-maze bootstrap cluster (5,000 draws, seed 20261115). The four prespecified references are Periodic-4, Periodic-5, Age-4, and Age-5. For example, versus Periodic-5, RDAO v1 Footprint had 4 rescues/3 harms in Original and 5/1 in High-Frequency. Its goal-rate confidence intervals still include zero. Across this 57-model exploratory family, confidence intervals are unadjusted; multiplicity makes isolated apparent differences especially tentative. A CI containing zero does not prove equivalence or non-inferiority.

The observed ranking does not support a broad claim that adaptive observation universally beats periodic/age schedules. RDAO v1 Footprint is the best observed goal-rate arm here, but it carries high computation cost (mean compute 375.51 ms/episode Original and 353.14 ms High-Frequency). Periodic-5 and Age-4 remain practical, materially lower-compute alternatives. High-Frequency outcomes are close to Original in aggregate, but model-level changes vary and do not isolate dynamics frequency from the changed transition mechanism.

Some distinct names had identical episode-level outcome, action, observation, contact, and error fields in both conditions: C + Ternary/C0, B + Age/B+C, MS-K/H1-K/H3-K, and MS-Topology/H1-Topology/H3-Topology. Their measured timing fields are not asserted identical. RDAO v1 Gate First and Gate Every differed in 25 Original and 24 High-Frequency episode behavior records, so they are not behaviorally identical in this evaluation.

## High-Frequency transition and replay validation

The 2,952 new High-Frequency episodes contain 132,429 active environment steps, with a valid change on every step (100.00%); event totals are 45,736 additions, 41,853 removals, and 44,840 relocations, with zero no-ops. Replay reconstruction checked contiguous step indices, stable object IDs, before/after state continuity, atomic relocations, object count and wall overlap, event constraint attestations, and packed ground-truth occupancy reconstruction. All checks passed. Existing 936 High-Frequency historical records remain included and were validated through their original verification path.

The representative five-model GIF was selected deterministically by maximizing distinct goal outcomes, then observation-count spread, then lexicographic map/schedule order. It uses saved map `h2-final-generalization-v1-20261114:R:910000017`, schedule 0. Age-4 reached the goal; Periodic-5, Uncertainty, CAA-Full, and RDAO v2 did not. The GIF displays saved ground truth and memory, robot heading, planned path, observation count, and event type/cell/object count. It is a replay visualization, not a new evaluation.

## Limitations

- Three registered models were not run because their existing authorization gates disallow FIT evaluation; the full 57-model/8,208-row completion criterion is therefore unmet.
- The historical 13-model records are reused, not rerun, so per-model execution provenance differs from the 41 new arms and should be read from the episode source paths and registry.
- Results reuse 36 maps and two schedules and are not independent generalization evidence.
- High-Frequency environment transitions depend on robot state, so realized transition sequences vary by model despite common random-number rules.
- Simulator computation and wall times are not hardware energy measurements.
- Paired bootstrap intervals are descriptive, unadjusted across many comparisons; no confirmatory claim is made.

## Validation and provenance status

- Focused regression suite: 155 passed, 0 failed, across the new registry/adapters, H2 runners, and frozen controller/model tests. `PYTHONPATH=.` is required for the repository's `scripts.*` test imports.
- The new runner verifier passed: smoke 328/328, Original 2,952/2,952, High-Frequency 2,952/2,952.
- Combined replay/index validation passed for all 7,776 rows. For the 2,952 new High-Frequency replays, 132,429 environment steps reconstructed with 100% change rate and no recorded no-op, wall overlap, object-count, continuity, relocation-atomicity, occupancy-bitfield, or constraint-attestation failure.
- Preservation audit passed: 836 protected files, 2,907 checkpoint/receipt pairs, 928 CAA artifacts, 25 source-binding files, and 58 G1 assets unchanged; no missing inputs and zero new navigation runs from the audit. Existing Original and High-Frequency artifact manifests also matched all 2,925 and 1,248 listed entries byte-for-byte.
- The older High-Frequency stage verifier's source-binding gate does not accept this checkout because the previously committed logging correction changed the pinned `scripts/h2_final_common.py` hash. Its gate was not bypassed. We used stored artifact-manifest hashes and the new independent row/replay checks; this source-pin limitation remains recorded for reproducibility.

## Artifacts

Machine-readable tables, figures, replay index, and representative visualization are in `results/phase2_mujoco/h2_comprehensive_benchmark_v1/`. Key files are `combined_dataset/episode_metrics.csv`, `combined_dataset/replay_index.json`, `analysis/model_summary.csv`, `analysis/paired_comparisons.csv`, `analysis/bootstrap_intervals.csv`, `analysis/pareto_frontier.csv`, `analysis/break_even_analysis.csv`, `analysis/representative_hf_comparison.gif`, and `analysis/representative_hf_trajectory.png`. Analysis is descriptive development evidence; it does not establish independent scientific validation.
