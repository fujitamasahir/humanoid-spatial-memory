# Phase 2 RDAO — one-shot pilots: results, mechanism and next gate

**Stage:** exploratory Phase 2 development. **Date:** 2026-11-11.
**Sources:** frozen RDAO v1 primary 72-episode metrics/traces, committed
one-shot pilot CSVs, and their committed compressed intervention traces.
**Claim boundary:** preselected development-time interventions; not an
autonomous deployable RDAO improvement; no held-out evidence.

## Outcome results (each row is shared by schedule 0 and schedule 1)

| World | Condition | Reached goal | Steps elapsed | Observations | Distance m | Turns | Unwanted contacts |
|---|---|---|---:|---:|---:|---:|---:|
| M:80030010 | Original RDAO | No (80-step cap) | 80 | 20 | 41.25 | 25 | 0 |
| M:80030010 | Force observation at step 2 (Extra) | Yes | 28 | 7 | 15.00 | 8 | 0 |
| M:80030010 | Force at step 2, suppress next natural (Swap) | Yes | 32 | 8 | 16.50 | 10 | 0 |
| R:80000018 | Original RDAO | No (80-step cap) | 80 | 13 | 43.50 | 22 | 0 |
| R:80000018 | Extra | No | 80 | 14 | 42.75 | 23 | 0 |
| R:80000018 | Swap | No | 80 | 14 | 41.25 | 25 | 0 |

These are **two worlds with two correlated schedules each**, not four
independent worlds. Both M schedules share identical reported results.
The capped episode numbers are horizon-censored steps, not actual
time-to-goal measurements for failures. All four intervention episodes
faithfully reproduced their original episode before forcing observations,
and preservation checking verified the 836 original Phase 1.5 files.

Lower *total* observations in M mostly accompany shorter trajectories:
original 20/80 = 0.25, Extra 7/28 = 0.25, Swap 8/32 = 0.25
observations per executed step. It is incorrect to infer that the
observation *frequency* decreased from these two pilot cases alone.
Swap is not exact dose matching: on R it still used 14 observations
versus 13 in baseline even after suppressing the next natural request.
The outcome is a strong selected-case sensitivity result, not an
established efficiency advantage.

## First branching mechanism, M:80030010

The complete step-level traces were compared.

At step 2 (robot heading west after the selected turn), the forced
ordinary sensor updates exactly two previously unknown cells:

- (7, 8) -> observed free
- (7, 9) -> observed occupied

The RDAO forward-facing nominal A* immediately before and after
this observation is unchanged, with route cost **14.5** and first action
**turn west** (the turn selected on step 2). Therefore the CSV's
forced_selected_astar_action_changed=false is accurate and NOT a
contradiction with the large eventual trajectory change.

At **step 3**, the historical Original RDAO takes an ordinary sensor
observation, which changes **seven** previously unknown cells:

- occupied: (6,7), (7,7), (5,8), (6,9), (7,9)
- free: (6,8), (7,8)

The historical observation changes the forward-A* estimate from
**14.25** to **18.75** and changes its first action from
**move west to (7,8)** to **turn north**. The actual historical
step-3 action is this northward turn.

Both intervention arms instead do **not** observe at step 3, and
execute **move west to (7,8)**. The very first actual
pose/action divergence thus occurs at step 3.

For Extra, at step 4 the normal scheduler observes five newly changed
cells and changes the nominal A* action; the robot turns north.
For Swap, the next natural observation is suppressed at step 4,
so the robot also moves west to (6,8); at step 5 it observes four
new cells, causing an A* change and northward turn.

Both intervention trajectories eventually arrive at step 28 or 32
while the original route fails to arrive by step 80. Importantly,
the step-2 observation did not immediately change the selected
A* action. The major causal ambiguity is **early information at
step 2 versus avoidance of an influential observation at step 3**,
with downstream adaptive sensing/replanning effects.

There is **no basis yet** to call step-3 information erroneous:
it revealed actual occupied/free cells at that time. The observed
effect could be route-selection instability, the interaction of
partial memory and planner safety, or how timing changes later
observations. The independent safety controller stays unchanged.
Do not describe the result as proof that suppressing observations
is preferable.

## Negative comparator, R:80000018

Step 2 forced 25 unknown cells into memory. The nominal A* first action
remained the same; route cost changed from 18.25 to 18.5.
The first actual action/pose difference appeared at step 3. Both
Extra and Swap remained unsuccessful at 80 steps, despite changed
path distances and steering. More revealed cells is not an adequate
observation-value criterion.

## Next experiment: four observation schedules at steps 2 and 3

A new independent experimental runner:
[scripts/evaluate_rdao_timing_factorial.py](../scripts/evaluate_rdao_timing_factorial.py)
with fast contract tests
[tests/test_rdao_timing_factorial.py](../tests/test_rdao_timing_factorial.py)

The 2-by-2 conditions explicitly grant or suppress **ordinary
authorized memory observations** at steps 2 and 3, then restore
unchanged RDAO v1 from step 4:

| Arm | Observe at step 2 | Observe at step 3 | Meaning |
|---|---|---|---|
| 01 | No | Yes | Historical Original |
| 00 | No | No | Suppress historical step-3 observation without early observation |
| 10 | Yes | No | Early-only, similar to Extra on this case |
| 11 | Yes | Yes | Observe early AND retain later observation |

This isolates the two early sensing decisions more cleanly than Extra
vs Swap. It is still an adaptive trajectory experiment, because the
policy after step 3 responds to the new map and resulting position.

Run locally:

~~~sh
git pull --ff-only origin phase2/mujoco-proxy-pilot
.venv/bin/python -m pytest tests/test_rdao_timing_factorial.py -q
.venv/bin/python scripts/evaluate_rdao_timing_factorial.py \
  --world M:80030010
~~~

After the M-case experiment succeeds, the same runner can be used
as a negative-control comparison:

~~~sh
.venv/bin/python scripts/evaluate_rdao_timing_factorial.py \
  --world R:80000018 \
  --output results/phase2_mujoco/rdao_v1_timing_factorial_R80000018
~~~

The runner requires exact saved baseline fidelity, an unchanged
20-observation cap, zero unselected-action shield queries, 836
preserved Phase 1.5 files, and writes a new summary, comparison CSV,
and full compressed intervention traces. The authoring environment
has not executed the runner or its tests.

## Interpretation gate

- If arm **00** succeeds, avoiding the historical step-3 observation
  is sufficient in this case to rescue arrival. Early sensing may
  be unnecessary for that rescue.
- If **10** succeeds but **00** fails, early sensing has evidence of
  additional causal value beyond omitting step 3.
- If **11** also succeeds, step-2 sensing can help even when the
  step-3 observation remains; check exactly which evidence, action
  and occupancy changed.
- If **11** fails while **10** succeeds, *when to integrate map
  evidence* is especially important; do not infer that step-3
  observation is incorrect or universally bad.
- Any safety violation or baseline replay mismatch blocks further
  interpretation.

After resolving this mechanism, run the original one-shot runner
across all 10 outcome-selected priority schedule cases and selected
successful controls, without tuning the subsequent test on them.
Only implement a sensor-aligned or planner-aligned ONLINE RDAO v2
when a defensible decision rule can be specified without hindsight.
