# Failure and change analysis

Retrospective proxy coordinates below come only from the evaluator trace. They were not inputs to the online planner or safety controller.

- New evaluation unwanted-contact episodes: 0.
- Baseline-to-sensor gained goal completions: 1.
- Baseline-to-sensor lost goal completions: 1.

## New contact events

No episode recorded unwanted G1 contact. Contact states and proxy contact pairs are both zero in the saved episode rows. This is limited to the tested development benchmark.

## Goal changes versus the saved baseline

- Gained successes (1): phase1.5-v0.4-BPRIME-1:fit:R:80000001 s1 static.
- Lost successes (1): phase1.5-v0.4-BPRIME-1:fit:M:80030007 s1 periodic.
  - `phase1.5-v0.4-BPRIME-1:fit:M:80030007` schedule 1 periodic: new run used 2 safety waits at [38, 39] and 0 safety lateral escapes at []; baseline reached goal in 64 steps, new ended at [2, 12] after 80.

## Interpretation

Contact counts represent MuJoCo geometry contact pairs and per-step contact states, not distinct human collisions. A proxy may move into an occupied robot footprint between actions; sensor visibility, intervention records, action choice, and post-step contacts are reported separately. No collision-shield queries for unselected actions were made.
