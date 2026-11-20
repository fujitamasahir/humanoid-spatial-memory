# H2 final benchmark reconciliation

## Scope

This is a descriptive development evaluation using 54 admitted models, the 36 existing FIT72 maps and 36 existing H2 generalization maps, two schedules, seed 42, and existing transition schedules. No environment was generated. Historical files were preserved.

The final dataset contains 11,664 unique episodes: known low-frequency 3,888, unseen low-frequency 3,888, unseen high-frequency 3,888. Its replay index reuses the H2 replay schema fields and adds condition/source annotations.

## Semantic optimization

Periodic-5 now returns before the unused age-grid allocation and score calculation in the separately versioned `cadence_age_optimized_v1.py`. Age-5 computes only the age+1 fraction used by its grant rule. The frozen `cadence_age.py` file was restored byte-for-byte to preserve prior source commitments. All 432 paired case comparisons passed, including controller state after each decision and update. The 52 other models were audited but not modified.

## Computational cost

The first selected-model remeasurement found material anchor variation relative to the immediately preceding timing batch, so all 54 models were measured in one new controlled epoch (19,440 episodes, five repetitions). See `all_model_timing_v1/summary.json`, `all_model_episode_timings.csv`, and `decision_microbenchmark.csv`. Existing 19,440 timing artifacts are retained.

## Corrected B + Age

Known FIT72 uses the verified corrected v2 72-case epoch. Unseen low/high conditions use a new 144-case full-replay epoch. The old misconfigured B+Age records are preserved but excluded; correct B+C remains unchanged. See `b_age_correction_report.md`.

## Results and interpretation

See `final_model_summary.csv`, paired comparisons, whole-maze bootstrap intervals, Pareto fronts, break-even thresholds, poster tables and figures. Break-even is a hypothetical scan-cost model, not measured sensor energy. Safety counts are recomputed from the selected episode metrics.

Aggregate input-manifest caveats and preservation checks are documented in `validation_report.md`. The stale historical manifests were not silently refreshed.

The computational-cost figure uses a logarithmic horizontal axis. A new artifact manifest hashes every file in this reconciliation directory (excluding the manifest itself).

Artifact hashes: replay index `c0bad3abbea022370bc078d92f1a9e92af3033781eca8f7b40818092c2652edc`, episode metrics `f6b095d505f5414e5f3177958c3f93a78e3915eef28ae75165ef55687789339d`, model summary `d0795b1bc9835d574b383e64a066f3fdeb562624d05767ff8671d75ceebbf318`.
