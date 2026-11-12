# RDAO footprint-only online fit72: paired outcomes, tradeoffs and forensic next step

**Status:** completed 72-episode DEVELOPMENT result; all 36 existing fit worlds,
two correlated schedules, seed 42, 80-step horizon, original independent
emergency sensor and selected-action collision shield unchanged.
**No held-out or dynamic biped walking claim.** This single-variable
intervention changes only the RDAO public-map visibility predictor, not
the online safe-action Gate from the earlier study.

## Reproducible committed sources

- results/phase2_mujoco/rdao_v1_footprint_visibility_online_fit72_v1/summary.json
- results/phase2_mujoco/rdao_v1_footprint_visibility_online_fit72_v1/paired_visibility_online.csv
- results/phase2_mujoco/rdao_v1_footprint_visibility_online_fit72_v1/visibility_online_traces.jsonl.gz
- results/phase2_mujoco/rdao_v1_phase2_evaluation/primary_traces.jsonl.gz

The online experiment verified each original frozen outcome and
per-step semantics before testing the visibility-only candidate.

## Overall results

| Metric | Original RDAO v1 | Footprint visibility only |
|---|---:|---:|
| Goal completions | 57/72 | 59/72 |
| Successful rescue | - | 2 episodes, 2 distinct worlds |
| Newly failed original successes | - | 0 |
| Average observations | 9.1111 | 9.9306 |
| Average H80-censored steps | 44.7361 | 44.8194 |
| Average executed distance | 24.4896 m | 25.0729 m |
| Unwanted contacts | 0 | 0 |
| Mean episode RDAO scheduler cumulative timing | 316.36 ms | 318.37 ms |

The 59/72 development goal count is BELOW simple Periodic and
Age baselines (66/72 each). This intervention is not an established
improvement in the user goal of fewer observations AND fewer
navigation steps/distance. Observation count and distance increase.

The 2 development rescues are DIFFERENT worlds from the earlier
first-only Gate rescues (M:80030009, M:80030010). That does not
justify combining the two rules without a separate controlled
interaction/factorial analysis.

## Paired decomposition

| Original/candidate goal status | Episodes | Total H80-censored step change | Total executed distance change | Total observation-count change |
|---|---:|---:|---:|---:|
| Failed -> success | 2 | -36 | -14.25 m | -6 |
| Success -> success | 57 | +42 | +34.50 m | +49 |
| Failed -> failed | 13 | 0 (both H80-censored) | +21.75 m | +16 |
| **Overall** | 72 | **+6** | **+42.00 m** | **+59** |

Among the 57 common-success episodes,
eight shorten, 42 are same arrival step, seven lengthen.
This is not broad robust speedup of completed routes.

Only 50/72 episodes change realized observation timing.
Only 32/72 change action/pose. A further 18 change
observation timing WITHOUT changing any executed action/pose:
in those cases the variant raises the total observation
count by 21 in aggregate without changing step count or
distance. Another 22 cases preserve observation timing and
executed navigation completely.

This shows why offline sensor recall does NOT automatically
produce useful navigation benefit.

### Two distinct rescued cases

1. **R:80000017 schedule0:** original fails at H80,
   candidate reaches Step58, 43.50 -> 29.25 m, and
   15 -> 10 observations; first sensing and executed-action
   divergence both at Step12. A promising joint outcome,
   but fewer observations might be a consequence of
   early completion and better route rather than intrinsically
   lower scheduler frequency. Same-world schedule1 is not
   rescued: this underscores the scheduler's sensitivity
   to the correlated pedestrian schedule.
2. **M:80030007 schedule1:** original fails at H80,
   candidate reaches Step66, 34.50 -> 34.50 m,
   17 -> 16 observations, 24 -> 20 turns, and
   emergency safety interventions 14 -> 1. The first
   sensing divergence is Step23, first action divergence
   Step25. The relationship between sensing and later
   emergency safety cannot be concluded from total
   intervention counts; a per-frame trace audit is needed.

### Largest recurring regressions

- **R:80000022 schedules0/1:** 55 -> 75 steps,
  31.50 -> 43.50 m, 10 -> 14 observations in EACH
  schedule. First sensing divergence at Step26, first
  action divergence at Step31. This SAME world was
  sensitive to the very different first-action Gate
  experiment (+22 steps); do not confuse those distinct
  interventions or their causal mechanisms.
- **BP:80010001 schedules0/1:** 72 -> 80 steps,
  43.50 -> 46.50 m, 12 -> 16 observations in each
  schedule. These are REACHED at Step80 according
  to the committed success field; do not mistakenly
  treat all Step80 terminations as failures. They are
  common-success cases, but close to the horizon.
- **BP:80010004 schedules0/1:** 27 -> 33 steps,
  14.25 -> 17.25 m, 6 -> 9 observations.

### An improved previously successful case

**BP:80010013 schedules0/1** is a stronger paired
efficiency example: 23 -> 17 arrival steps, 11.25 ->
9.75 m, and 5 -> 4 observations. Still only one
unique world repeated under two schedules.

## Why a causal timeline, not another fitted threshold

Some variant episodes get MORE observations with
identical physical actions. Others get new map data,
then change route only several steps later. The
resulting additional interventions and turns can
raise path distance despite more frequent sensing.

The original and variant trajectories are already
committed in full. The next read-only analysis is
[scripts/analyze_rdao_footprint_visibility_online_forensics.py](../scripts/analyze_rdao_footprint_visibility_online_forensics.py)
with
[tests/test_rdao_footprint_visibility_online_forensics.py](../tests/test_rdao_footprint_visibility_online_forensics.py).

It checks full 72-case pairing, frozen source fingerprints,
step/observation counts and first sensing vs action
divergence, and outputs:

- paired_case_diagnostics.csv: episode status, observations,
  distance, turns, emergency intervention difference,
  exact first divergent sensing/action steps, and full
  observation step sequences.
- focus_step_timeline.csv: for both trajectories around
  the first observation divergence, recorded pose,
  action, RDAO score/threshold/reason, selected candidate
  region count, accepted observation memory updates,
  and emergency intervention fields.
- summary.json: the verified paired totals and
  exploratory limitations.

A successful forensic audit DOES NOT isolate a single
observation's independent causal effect: after the
first changed sensing decision, all future memory,
selected actions and sensor timings may diverge.
Only controlled follow-up interventions at a fixed
decision point can establish that.

### Run locally (no MuJoCo or new policies)

~~~sh
git pull --ff-only origin phase2/mujoco-proxy-pilot
.venv/bin/python -m pytest tests/test_rdao_footprint_visibility_online_forensics.py -q
.venv/bin/python scripts/analyze_rdao_footprint_visibility_online_forensics.py
~~~

New output directory:
results/phase2_mujoco/rdao_v1_footprint_visibility_online_forensics_v1

**Authoring status:** scripts and tests were committed, but
the new local forensic script and its test suite have not
been run with the user's environment in this writing turn.

## Next research decision

The footprint visibility adjustment has an encouraging
sensor-feasibility diagnostic restricted to route-near
candidate cells, and rescues two developer-world episodes.
But it does not improve both spatial memory observation
dose and path efficiency across the 72-case development
screen. Do not combine it with the first-only route Gate
yet or promote to RDAO v2.

First isolate the first changed observations in the rescued
and severe-detour cases, then test a conservative
decision-time online hypothesis such as information
utility of an alternative *viewpoint* rather than
simply increasing all predicted visibility values.
Include matched realized observation-dose controls
and count extra planning computation separately.
Only a frozen hypothesis should be evaluated on
independent held-out mazes.
