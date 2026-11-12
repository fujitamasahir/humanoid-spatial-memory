# RDAO Footprint: second-sensing causal results and revised mechanism

**Date:** 2026-11-12.
**Status:** completed and committed retrospective FIT-world, two-decision
intervention, all six arms, **zero unwanted contact pairs**. All 36
Phase 2 fit worlds and their two correlated pedestrian schedules have
already been inspected repeatedly. No held-out or walking-dynamics
conclusions are drawn.

## Primary reproducible evidence

- results/phase2_mujoco/rdao_v1_footprint_second_sensing_causes_v1/
  second_sensing_causal_comparison.csv
- results/phase2_mujoco/rdao_v1_footprint_second_sensing_causes_v1/
  second_sensing_causal_traces.jsonl.gz
- results/phase2_mujoco/rdao_v1_footprint_second_sensing_causes_v1/
  summary.json
- results/phase2_mujoco/rdao_v1_footprint_first_sensing_causes_v1/
  first_sensing_causal_comparison.csv
- results/phase2_mujoco/rdao_v1_footprint_visibility_online_fit72_v1/
  paired_visibility_online.csv

Results were saved on branch phase2/mujoco-proxy-pilot in commit
c0eb00a0de2a2c33e25f72027dac64f4bbb0b2db.
The new audit verified the original frozen baseline,
the first-only intervention trace, unchanged safety mechanism,
and identical pre-action sensor pose and raw 61-ray values
for the **second** forced scan. Memory grids can differ between
arms if earlier sensing differed, and are recorded separately.
The preserved Phase 1.5 prefix was unchanged.

## Outcome table

An entry "fail80" means not reached within the horizon,
not necessarily never reachable. "Reach80" from earlier
experiments instead means success=True at exactly the cap.

| Fit case | Original | Continuous Footprint | First-only control | +Second forced scan |
|---|---|---|---|---|
| R:80000017 S0: first Step12 *swap* (suppresses Step14), second Step20 | fail80 | reach58 | fail80 | **reach58** |
| M:80030007 S1: first Step23 *extra*, second Step48 | fail80 | reach66 | fail80 | **reach66** |
| R:80000022 S0: first Step26 *extra* (keeps Step27), second Step30 | reach55 | reach75 | reach55 | **reach75** |
| R:80000022 S0: first Step26 *swap* (suppresses Step27), second Step30 | reach55 | reach75 | reach75 | **reach75** |
| R:80000022 S1: first Step26 *extra*, second Step30 | reach55 | reach75 | reach55 | **reach75** |
| R:80000022 S1: first Step26 *swap*, second Step30 | reach55 | reach75 | reach75 | **reach75** |

All 6 two-decision interventions had zero unwanted contacts
and passed the observation-budget/shield-query checks.

## Findings

### A. R:80000017 S0: precisely targeted two-decision rescue

First-only "swap": force ordinary observation Step12,
suppress the next natural observation Step14.
That first-only control failed by Step80 with 14 memory
observations and 42m travel.

Adding ONE second ordinary observation at Step20 produces
**reach58, 29.25m, 10 observations**, exactly the
continuous-Footprint outcome on these three scalar metrics.
The saved comparison also reports NO later executed action/pose
difference against Footprint. Recorded second sensor:
29 raw visible cells, 4 newly changed cells, identical
pre-observation and post-observation memory to Footprint,
and identical selected action.

Thus the entire ongoing changed visibility scoring rule
is NOT necessary to reproduce this fitted case; the
Step12/Step14/Step20 observation-timing intervention
is sufficient for the observed successful trajectory.
The Step14 suppression is PART OF the intervention,
so it is incorrect to call this merely "two additional
observations". Two FORCED observations and one
intervening suppressed opportunity are involved.

### B. M:80030007 S1: a second scan changes outcome despite same distance

First-only extra at Step23 fails by Step80, with
16 memory observations, 34.5m travel and
16 emergency safety interventions.

Adding the Step48 scan produces **reach66,
34.5m, 15 memory observations, 1 emergency
safety intervention**. Continuous Footprint also
reaches Step66 and travels 34.5m, but uses
16 observations. The executed action/pose trajectory
does NOT differ from continuous Footprint even
though the later observation schedule is not identical
(the extra control scans Step63 rather than the
Footprint's Steps62 and66). The Step48 raw
measurement contained four visible cells and updated
two unknown cells, with identical before/after
public memory at the intervention step.

This demonstrates a fitted case in which the original
RDAO with TWO selected sensing interventions reproduces
the continuous-Footprint successful navigation trajectory
while using ONE FEWER observation overall. It does not
show how to predict the useful timing prospectively.

### C. R:80000022 S0/S1: revised interpretation; Step27 suppression is NOT required

This corrects the earlier first-sensing interpretation.

- Original RDAO: scan Step27, arrival55.
- Force only Step26 extra, RETAIN natural Step27:
  arrival55 (no path regression).
- Force Step26, SUPPRESS Step27 (first-only swap):
  arrival75 (full regression).
- Crucially, **force both Step26 and Step30 while still
  RETAINING Step27** (extra+second): arrival75,
  43.5m, 14 memory observations, the SAME
  executed navigation trajectory as Footprint.
- First-only swap+forced Step30 also arrives at75.

Therefore loss of the Step27 scan is **one sufficient
development-world timing route**, but is definitively
**NOT A NECESSARY CONDITION** for the 20-step detour.
The independent Step30 forced-scan intervention,
conditioned on already having Step26 and still retaining
Step27, also reproduces the detour.

At Step30 the original continuous-Footprint scan
has 36 raw visible cells and changes 36 memory cells;
the forced control also measures 36 raw visible cells
but changes only 14, because prior memory differed.
The raw sensor and pre-action pose/heading agree;
memory_before and memory_after DO NOT agree.
The selected Step30 action nevertheless agrees,
and the resulting executed trajectory matches.
For the earlier first-only swap control, the forced
Step30 scan changes only four cells, but the detour
was ALREADY present in that control. Do not assert
a single changed cell or observation count as cause.

This is a more precise mechanism hypothesis: the
timing and contents of **route-altering memory updates
near Step30** can make the navigation planner select
an expensive alternative route. Comparing which
newly occupied/free cells and selected route first
action changed at Step30 is the next read-only
diagnostic. No prospective online rejection rule
has been justified yet.

## What these interventions DO and DO NOT prove

- These deterministic, controlled same-world
  counterfactuals establish conditional causal
  intervention effects for the selected fitted cases.
- The two scans were chosen AFTER looking at full
  Footprint trajectories, so they cannot be called
  independent validation or a proposed deployable
  online observation scheduler.
- "Same trajectory despite different scans" shows
  that some downstream observations are redundant
  for those case-specific action sequences; it does
  not tell us which future scan is safe to omit
  in another world or pedestrian schedule.
- Mean observation count across censored failures
  and successes conflates scheduling intensity
  with episode survival duration.
- All 72 original Phase 2 episodes remain a
  MuJoCo kinematic-root G1 navigation proxy,
  not end-to-end dynamic walking.

## Research next step

Do a READ-ONLY map-and-route diagnostic at Step20,
Step48 and Step30 for the original, first-only,
two-intervention, and saved continuous-Footprint traces.
Compare at each chosen pose:
- memory_before/after and exact newly changed cells;
- selected G1 navigation action and route-before/after;
- route-relevant blocked/free changes;
- whether a candidate online rule has access to this
  information WITHOUT the observation having already
  occurred (otherwise it would leak future sensing).

Do NOT tune a rule solely for these three fit mazes.
Only after a rule is specified using available
decision-time public information and safety constraints
can further prospective tests inform RDAO v2 design.
