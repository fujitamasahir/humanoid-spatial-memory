# H2 Replay Recovery Addendum — Parity Reconciliation

The original Task B indexer did not include plain `.jsonl` historical records and also admitted generic RDAO method labels as model identity. A read-only reconciliation pass compared all 72 RDAO v1 episodes directly with `rdao_v1_phase2_evaluation/primary_records.jsonl`, keyed by exact world identity and schedule; all 72 matched both step traces and metric signatures. Alternative RDAO variants were excluded. The raw replay episodes and the initial parity fields inside them remain unchanged.

The 72 B+Age FIT72 replays remain genuine mismatches against the saved `persistence_evi_fit72_restored_local_v1` episodes. The saved FIT72 provenance pins commit `3d66e54`; this recovery used the active H2 recovery binding. The mismatch is not called a successful reproduction. `fit72_b_age_mismatch_analysis.csv` reports first divergent step, actions, poses, observations, outcomes, and both source hashes. In the first inspected episode, divergence begins at step 4: the historical run turns while the recovery run selects a forward move that the current footprint/safety path rejects. This is a diagnosed source/behavior discrepancy, not evidence that every mismatch has the same cause.

## Current FIT72 reconciliation counts

- Exact historical parity: 2,520 / 3,888
- First-time FIT72 evaluations: 1,296 / 3,888
- Actual mismatch: 72 / 3,888 (all B+Age)
- Uncomparable: 0 / 3,888

Task A remains 864 / 864 exact. The combined archive remains descriptive; this report does not claim complete exact reproduction for Task B.
