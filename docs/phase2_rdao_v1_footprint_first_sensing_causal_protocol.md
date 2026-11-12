# Phase 2: Footprint online sensing divergence, implications, and first-scan causal tests

**Date:** 2026-11-12
**Stage:** 36 previously inspected FIT worlds; paired 72 online episodes,
seed42, 80-step horizon; retrospective diagnosis. No independently reserved
held-out run, no dynamic G1 walking claim.

## New forensic evidence

Original evidence and analysis:
- results/phase2_mujoco/rdao_v1_footprint_visibility_online_fit72_v1/
  paired_visibility_online.csv
- results/phase2_mujoco/rdao_v1_footprint_visibility_online_fit72_v1/
  visibility_online_traces.jsonl.gz
- results/phase2_mujoco/rdao_v1_footprint_visibility_online_forensics_v1/
  focus_step_timeline.csv
- results/phase2_mujoco/rdao_v1_footprint_visibility_online_forensics_v1/
  paired_case_diagnostics.csv
- results/phase2_mujoco/rdao_v1_footprint_visibility_online_forensics_v1/
  summary.json

The verified focused timeline has exactly **183 rows**.
Its original and footprint traces were matched against 72 paired
records. 50 episodes change sensing, but only 32 change executed
action/pose; 18 alter sensing with NO executed motion change.

Total across 72 cases: two rescues, no harmed previously-successful
episodes, 57 common successes (8 faster, 42 same steps, 7 slower),
13 remain horizon-80 failures. Observation count increases +59
over 72 episodes; executed distance +42m; H80-censored steps +6.

## First-step causal chain from saved trajectory

The highlighted first-sensing changes are ALL *extra earlier sensing*
on the Footprint arm, not withheld sensing. However the two controllers
often differ again on the next naturally authorized observation;
this causes timing replacement as well as additional observations.

| Identity, schedule | First earlier Footprint observation | First executed divergence | Notes |
|---|---:|---:|---|
| R:80000017, 0 | 12 | 12 | Rescue from H80 failure to Step58 |
| M:80030007, 1 | 23 | 25 | Rescue to Step66 |
| R:80000022, 0/1 | 26 | 31 | Both schedules +20 steps |
| BP:80010001, 0 | 30 | 39 | +8 steps, sensing change without immediate motion change |
| BP:80010004, 0 | 12 | 13 | +6 steps |
| BP:80010013, 0 | 2 | 2 | -6 steps, fewer scans and shorter route |
| M:80030009, 0/1 | 12 | 12 | Both still H80 failures, six additional observations |

### R:80000017 schedule0: the strongest positive example

At Step12 the old RDAO score=0 and refuses to observe.
The footprint model scores 0.333, above threshold ~0.256,
and takes a REAL naturally authorized 61-ray scan
updating 14 memory cells. In that same step, old RDAO
selects a move to [15,9]; the Footprint action is instead
a turn (index1). The original later requests observations
at steps15 and16 but ultimately fails at H80. The
candidate reaches at step58, uses five fewer observations
and travels 14.25m less.

This is evidence of a strong change in the first sensing
and selected action, but the full success improvement
also includes all later closed-loop effects. It does not
establish that the FIRST scan alone is sufficient.

### M:80030007 schedule1: earlier tiny scan, later safety change

At Step23 old RDAO finds zero visible relevant region,
while Footprint's score ~0.429 crosses threshold ~0.238.
Footprint measures a scan changing just 2 cells; Step23
action (turn index3) is the SAME in both.
At Step24 the old RDAO takes its own natural scan,
changing one cell; Footprint does NOT scan. The two
arms still have the same selected action at Step24.
At Step25 they first diverge: old turns index1,
Footprint moves to [11,8]. Candidate subsequently
completes at Step66 whereas original is H80-censored.
Emergency safety interventions drop 14 -> 1, and
turns 24 -> 20, while distance remains exactly 34.5m.

The reduction of emergency interventions is ASSOCIATED
with the altered route/observation feedback. Neither
"two measured cells caused thirteen fewer interventions"
nor a causal mechanism for that later reduction is
established by this comparison alone.

### R:80000022 schedules0 and1: early scan + intermediate additional scan

Footprint first scans at Step26 (12 changed cells,
score ~0.429 vs old zero). The original then scans at
Step27 (29 changed cells) but Footprint does not.
Selected actions and pose match through Step30.
At Step30, Footprint performs another new scan (36
changed memory cells) while old RDAO does not.
At Step31 the actions first diverge: original moves
to [9,10]; Footprint turns index2 and diverts west.
Both Footprint runs reach Step75 instead of Step55
and travel +12m with +4 total observations.

The critical contrast: we cannot assign the worsening
to the Step26 first scan alone without a controlled
counterfactual, because Step30 brought substantial
additional information before motion divergence.
This world also suffered a detour under a distinct
pre-update action Gate, but the two mechanisms cannot
be assumed the same.

### BP:80010001 schedule0: nine-step lag

Footprint first scans Step30, changing 26 cells.
Original scans Step31 (35 cells). Both execute the
same actions through Step38. At Step34 Footprint
scans again, changing 34 cells. They first move
differently at Step39: original moves to [13,13],
Footprint turns index3. Final arrival 72 -> 80,
travel +3m, and four more memory observations.
As in R:80000022, first sensing is not equal to
the unique causal effect of that scan.

### BP:80010004 schedule0 and BP:80010013 schedule0

BP:80010004: Footprint's Step12 scan updates only
2 cells; the ORIGINAL would scan at Step13 and
change 32 cells. Physical action diverges Step13;
candidate arrives 33 rather than 27 with three
more observations and +3m travel.

BP:80010013: Footprint Step2 scan changes one
memory cell and immediately alters action. Original
scans Step3 (3 changed cells). Candidate reaches
at Step17 rather than Step23, travels -1.5m and
uses one fewer observation. The paired schedules
of this world agree but are correlated repeats.

### M:80030009 schedules0 and1: more observations, no rescue

Footprint's Step12 scan changes three memory cells.
Original instead scans at Step13 and changes two.
First action difference is immediately at Step12.
Both fail by the H80 horizon; variant additionally
takes 6 memory observations and +3m travel.
Do not call equal H80-censored steps equal true
completion time.

## Next PROSPECTIVE-STYLE causal intervention within fit worlds

Code:
- [scripts/evaluate_rdao_footprint_first_sensing_interventions.py](../scripts/evaluate_rdao_footprint_first_sensing_interventions.py)
- [tests/test_rdao_footprint_first_sensing_interventions.py](../tests/test_rdao_footprint_first_sensing_interventions.py)

Targets are PRESELECTED from the previously committed
footprint-vs-RDAO paired trace; this is **retrospective
identification**, NOT a deployable policy and NOT
held-out validation.

The experiment replays original RDAO v1 with its
ORIGINAL visibility function, while overriding ONLY
the FIRST missed footprint scan at its recorded
step. The 61-ray sensor is the standard authorized
observation sensor, not the evaluator-only shadow
sensor or emergency sensor. Compare three conditions
alongside saved Footprint outcome:

1. Original RDAO (frozen row and trace exactly reproduced).
2. One forced extra memory observation, normal old
   scheduler thereafter ("extra").
3. One earlier forced observation, suppressing the FIRST
   later naturally requested observation ("swap").
4. Previously saved Footprint policy: continuous
   changed visibility feasibility on ALL future decisions.

For each forced condition, the FIRST raw observed
cell-value list, pre-map and post-map MUST match the
stored Footprint observation exactly, at the identical
pose and heading. This cross-arm same-sensor match
is crucial: otherwise later outcomes may be ascribed
to inconsistent perception rather than different
observation decisions.

The new comparison also records the first later sensing and
action divergence between the forced-first-scan control
and the previously saved continuous Footprint policy.

The two forced conditions keep the ORIGINAL
visibility model for later decisions, and do NOT
update the footprint region's original RDAO
"last attempted" cooldown in the same way as
the Footprint scheduler; this is intentionally
a causal policy-factor separation, not a full
reproduction of the Footprint policy.

The "swap" control is NOT a guaranteed fixed
observation-dose comparison. It removes one
natural observation along the changed trajectory;
record whether a suppression actually happened
and compare realized observation counts.

Both controls preserve the RDAO observation cap=20,
normal G1 planning, unchanged independent Emergency
Safety controller and selected-action collision
shield, explicit reporting of any unwanted contacts, the
Phase1.5 preserved prefix and original results
checksum invariants.

### Run

~~~sh
git pull --ff-only origin phase2/mujoco-proxy-pilot
.venv/bin/python -m pytest \
  tests/test_rdao_footprint_first_sensing_interventions.py -q

# First two saved rescued cases, each with extra and swap:
.venv/bin/python \
  scripts/evaluate_rdao_footprint_first_sensing_interventions.py \
  --max-cases 2 \
  --output results/phase2_mujoco/rdao_v1_footprint_first_sensing_rescue_pilot_v1

# All nine chosen world-schedule pairs:
.venv/bin/python \
  scripts/evaluate_rdao_footprint_first_sensing_interventions.py
~~~

The full run creates first_sensing_causal_comparison.csv,
first_sensing_causal_traces.jsonl.gz and summary.json.
The code and tests have been committed to the Phase2
development branch but have NOT been run in the
authoring environment.

## Interpretation before algorithm design

- If extra and swap REPRODUCE the rescue on the same
  maze, the first changed scan is a plausible
  sufficient intervention for that fitted case.
  It does NOT prove the visibility feature is the
  only cause across all worlds, nor prospective benefit.
- If neither reproduces it, the Footprint policy's
  future repeated decisions, region cooldown or
  timing changes likely contribute. Use per-step
  traces to locate the additional divergence.
- If extra hurts but swap does not, repeated sensing
  and total dose may matter; analyze actual
  observed counts and first action before concluding.
- If a forced scan causes unwanted contacts, report
  it as a failed safety result rather than omitting it.

Do not combine Footprint sensing with the
previous first-only pre-update action Gate until
each effect and their interaction is understood.
Neither variant currently surpasses Periodic/Age's
66/72 developer-world successes, or meets the
simultaneous observation/distance reduction goal.
