# H2 Comprehensive Benchmark Replay Schema

New replay files use the committed H2 high-frequency replay structure and
retain the `steps` array, initial state, outcome, metrics, source model ID,
condition, map identity, schedule, seed, and environment-engine specification.
The saved event row at every active navigation step includes event type,
persistent object IDs, before/after cells and object sets, counts, robot pose,
pedestrians, connectivity/exclusion validation, RNG stream identifiers, and
candidate rejection counts. A no-change Original schedule step is represented
explicitly as a no-op/scheduled-state record rather than omitted.

Each navigation frame preserves robot pose before/after, heading, planned path
when emitted by the evaluator, selected/executed actions, observation request
and grant, cumulative paid count, public spatial memory, ground-truth state in
an evaluator-only field, dynamic object IDs, pedestrians, emergency scan and
intervention, shield result, contact data, and terminal state. Model diagnostics
are stored only when emitted by the unchanged controller implementation.
Missing historical fields are represented as unavailable; they are never
reconstructed from outcomes.

The replay index binds every file's relative path, byte length, and SHA-256.
Serialization round-trip, event reconstruction, pose/action and observation
count consistency, termination, cap/shield constraints, and source/map binding
are mandatory validation checks.
