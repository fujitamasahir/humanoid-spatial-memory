# FIT72 B/C failure analysis artifacts

This directory contains read-only forensic analysis of the saved 72-key,
five-arm FIT72 evaluation. No environment or frozen controller was changed.
The source evaluation is
`results/phase2_mujoco/persistence_evi_fit72_restored_local_v1/`; per-episode
paired source analysis is
`results/phase2_mujoco/persistence_evi_fit72_analysis_restored_local_v2/`.

## Main files

- `paired_episode_diagnostics.csv`, `paired_failure_key_sets.json`: matched outcomes and exact failure-key comparisons.
- `failure_decision_chronology.csv`, `first_divergence_by_failure.csv`, `evi_shadow_*.csv`: read-only decision/EVI replay diagnostics.
- `b_probability_timeseries.csv.gz`, `memory_state_snapshots.jsonl.gz`: B and ternary-map state evidence.
- `counterfactuals/`, `frozen_counterfactual_case_selection.json`: prespecified real-sensor diagnostic interventions and controls.
- `actual_spatial_memory_scan_counts.csv`: direct paid-sensor call/ray counts for all 360 arm episodes.
- `sensing_and_computation_*.csv/json`: separated memory and emergency sensing, timing, and paired common-success costs.
- `fig*.png`: aggregate plots.
- `M80030004_s0_age_C_early_scan.gif`, `BP80010001_s0_age_C_early_scan.gif`: synchronized explanatory replays. Dynamic hidden occupancy is omitted; the panels show admitted wall geometry and saved/replayed agent state only.
- `analysis_completion.json`: completion status, trace validations, and the one counterfactual replay mismatch excluded from causal contrasts.
- `artifact_manifest.json`: SHA-256 and byte size for delivered artifacts (regenerated last after finishing files).

The experiments are descriptive. Retrospective counterfactual timing is not a deployable online policy. Ground truth is not passed to controllers. See [`docs/persistence_evi_fit72_failure_analysis.md`](../../../docs/persistence_evi_fit72_failure_analysis.md) for the findings and limits.
