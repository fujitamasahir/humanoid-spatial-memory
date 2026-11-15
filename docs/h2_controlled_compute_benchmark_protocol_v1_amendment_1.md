# H2 Controlled Compute Protocol v1 — Amendment 1

## Reason

The prior H2 replay recovery audit found a model-definition error in the
historical H2 Comprehensive output: the 72 High-Frequency records named
`b_age` were produced by `PersistenceEVIController` with both Persistence and
EVI enabled. The admitted model is **B + Age** (Persistence enabled, EVI
disabled). The immutable historical outputs remain preserved, but their
`b_age` trajectories are not valid behavior-parity targets for the corrected
controller. The recovered `H2_RECOVERY_ADDENDUM.md` and
`binding_amendment_5.json` document that correction and its separate FIT72
validation.

## Prospective handling

- Benchmark the corrected, registered B + Age implementation as currently
  defined (`persistence=True`, `evi=False`). No policy or parameter is changed
  by this benchmark.
- Compare the new `b_age` results to historical traces and record every
  semantic mismatch. Label these as expected historical implementation
  non-parity, never as timing-only parity.
- Preserve exact historical semantic parity as a hard gate for the other 53
  models. Any mismatch outside `b_age` stops the run.
- Report old `b_age` timing for context, but mark it non-comparable because it
  measured a different controller composition. No historical/new ratio or
  break-even inference is made for that model.
- Keep the corrected B + Age episodes from FIT72 as evidence of the current
  model definition, while explicitly stating they are not the same H2 unseen
  maps/schedules and cannot substitute for per-case high-frequency parity.

This amendment changes only the parity classification for one previously
misimplemented historical arm. It does not change case order, repetitions,
timing scope, model parameters, environments, safety, or the measured
implementation. The number and exact identity of non-parity cases remain
reported in the new parity ledger.
