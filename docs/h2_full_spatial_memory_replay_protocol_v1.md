# H2 Full Spatial Memory Replay Recovery Protocol v1

## Purpose and provenance

This versioned recovery records complete H2 Original-condition replays without
changing observation controllers, navigation, the saved maps, or schedules. It
uses the committed research state `e2d244583c8c832d6af137c2d93c848e6bf3136a`
as its parent. It is a descriptive replay-recovery evaluation, not an
independent validation or an algorithm comparison.

## Frozen conditions

- Task A: 36 saved unseen H2 maps (12 each R/BP/M), both saved schedules,
  seed 42, old 12 H2 models; 864 episodes.
- Task B: the 36 admitted saved FIT72 maps, both saved schedules, seed 42,
  Original condition only, all 54 registry models with eligible or historical
  status; 3,888 episodes. Existing blocked models remain excluded.
- Existing map geometry, starts/goals, object/pedestrian schedules, 25x25 grid,
  0.75 m cells, 80-step horizon, 20 paid-observation cap, 61-ray memory
  sensor, 61-ray emergency sensor, selected-action shield, and planner are
  loaded from their frozen sources and saved data.
- No maps or schedules are generated. Existing results are read-only. Output
  files are exclusive-create, deterministic gzip JSON; a journal binds each
  committed file by byte count and SHA-256.

## Replay semantics

Each episode has an s0 state and one state per active transition through
termination (therefore `elapsed_steps + 1` frames). For active step *t*, the
record distinguishes memory immediately before the observation decision,
immediately before a granted observation is applied, immediately after that
update, and at end of step. An ungranted observation leaves the before/after
memory equal. At s0 the controller is initialized from the initial observation;
there is no pre-controller memory state, and this is represented as unavailable
rather than fabricated. Observed cells/values, full ternary memory, model
internal state snapshots, ground truth, events, pedestrians, poses, selected
action, shield outcome, executed movement, and terminal state are retained.

Controller snapshots are evaluator-side serialization only. They are never
passed to a policy or used to choose actions. Ground truth remains evaluator-only.

## Parity and classification

Task A is compared episode by episode with the saved H2 final Original result,
including outcome, counters, and trace. Task B is compared with any historical
FIT72 result whose key and protocol can be established; absence of a compatible
historical result is labeled first-time FIT72 evaluation, not exact reproduction.
Missing spatial-memory fields are never inferred from the final map or outcome.
The three research-gate-blocked models are reported as blocked and are not run.

## Resume and validation

Resume is permitted only when every existing episode file has one matching
journal entry and matching SHA-256. A completed replay must have an s0 record,
one record per active step, 25x25 ternary grids, a monotonic paid-observation
count no greater than 20, a valid final outcome, and unchanged source/map
hashes. See `h2_full_spatial_memory_replay_schema.md`.
