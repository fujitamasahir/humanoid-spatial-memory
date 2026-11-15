# H2 Full Spatial Memory Replay Recovery v1

This is a descriptive recovery/replay evaluation. Controllers and frozen navigation conditions were not changed.

## Task A — unseen H2 maps

864/864 episodes have exact step-trace and metric-signature parity with the saved H2 final Original results. All 12 models match the frozen expected goal and paid-observation totals; see `model_metrics_summary.csv`.

## Task B — known FIT72 maps

3,888/3,888 Original-condition episode replays are present. Each indexed episode records whether a historical FIT72 trace was found and the result of direct parity comparison. A first-time FIT72 run is labeled distinctly from exact reproduction. Three gate-blocked arms were excluded.

## Data completeness

Each replay has s0 plus every active step, full ternary memory, observation-before/update/after state, observed cells, serialized controller state, environment events, robot pose/heading, pedestrians, ground truth, selected/executed action, safety evidence and outcome. Validation checks frame sequence, memory encoding, observation cap, journal hashes and outcome consistency.

## Integrity

- Source bindings are epoch-specific; exact paths and SHA-256 values are listed in `summary.json` under `binding_epochs`. The corrected B+Age epoch uses append-only amendment 5.
- Protected Phase 1.5 gate: `PASS`.
- Historical H2 manifest entries verified: 8206.
- Historical results and blocked research gates were not modified or bypassed.

See `historical_replay_audit.csv`, `replay_index.csv`, `summary.json`, and the append-only validation attempt records for details.

## Parity reconciliation addendum

Task A is exact for 864/864. After identity-matched FIT72 reconciliation, Task B has 2,592 exact historical matches and 1,296 first-time cases. The first Task B pass misconfigured B+Age as B+C; those 72 source records remain preserved and are superseded by the separately bound corrected B+Age epoch. Combined index v3 preserves the previous 7,776 entries exactly and points to the 4,752 authoritative recovery records. See `H2_RECOVERY_ADDENDUM.md`, `game_schema_compatibility.md`, `parity_reconciliation.csv`, and `fit72_b_age_correction_validation.csv`. The current website reader still requires its original index schema and is not directly compatible with v3.
