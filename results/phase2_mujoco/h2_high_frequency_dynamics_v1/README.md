# H2 high-frequency dynamic robustness extension

This result contains a descriptive 13-arm evaluation over the existing 36 H2 maps. Start with [`docs/h2_high_frequency_dynamics_protocol_v1.md`](../../../docs/h2_high_frequency_dynamics_protocol_v1.md), [`docs/h2_high_frequency_dynamics_replay_schema.md`](../../../docs/h2_high_frequency_dynamics_replay_schema.md), and the binding files at this directory root.

- `primary/`: 936 primary episode metrics and run journal.
- `replays/primary/`: full step-level replay for each primary episode, with a 936-file SHA-256 manifest.
- `original_uncertainty/` and `replays/original_uncertainty/`: 72 original-transition Uncertainty episode records and full replays.
- `smoke_amendment1/` and `replays/smoke_amendment1/`: valid 52-episode corrected smoke. The older `smoke/` run is retained but invalidated because it continued environment transitions after goal termination during frozen-evaluator common-horizon accounting.
- `analysis_v4/`: final saved-data-only analysis, paired bootstrap, plots, and representative GIF. The earlier `analysis/` and partial `analysis_v3/` are retained and labeled as superseded.
- `maps/`: exact copied map geometry and source map manifest.
- `environment_events/`: deterministic event journals.
- `validation/`: smoke issue/amendment records, frozen-replay parity, and final validation summary.

`artifact_manifest.json` hashes all files in this result directory except itself. The final episode-replay verifier reports 39,730/39,730 primary active steps changed state (100%), no no-ops, no connectivity or exclusion violations, and zero unwanted-contact episodes. Results are descriptive development robustness evidence, not independent validation or a pure causal estimate of event frequency.
