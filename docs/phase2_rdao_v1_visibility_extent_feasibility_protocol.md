# Phase 2 RDAO: simple gate feature non-identifiability and next visibility audit

**Status:** fitted/development-world analysis only. No new RDAO v2
runtime change or held-out evaluation has been performed.

## What the most recent separability audit establishes

Committed results:
results/phase2_mujoco/rdao_v1_gate_feature_separability_audit_v1/

The original online screen has 72 RDAO development episode schedules
from 36 admitted worlds. The first-only gate was applied in 34 of those
episode schedules, representing 19 distinct worlds. Each selected
event executes just one override:

| Paired original-vs-first effect | Episodes |
|---|---:|
| A failed by horizon80, first reached goal | 4 (two worlds x two schedules) |
| Both succeeded, first took more steps | 14 |
| Both succeeded, same arrival step | 5 |
| Both failed by horizon80 | 11 |
| Original succeeded, first failed | 0 |

These are paired episode outcomes, not individually trained classifier
labels for every gate in the repeatedly-applied every arm.

The audit found three separate THREE-FEATURE signature collisions
across different world identities:

1. (cost increase .5; old-path first blocker translation 3;
   one observed-free nonbackward neighbor):
   M:80030004 unchanged vs M:80030005 +2 steps.
2. (cost increase 12.5; blocker 2; one free neighbor):
   BP:80010001 +2 steps vs M:80030008 still a horizon-censored failure.
3. (cost increase 4.5; blocker 3; one free neighbor):
   M:80030010 is rescued (80 censored -> 28),
   while M:80030000 and M:80030007 remain failures.

**Negative result:** This feature triple cannot deterministically
distinguish the last rescue from the unchanged failures.
This does NOT show that richer features cannot help.

An additional important observation from the committed 107-event
feature CSV is that nonbackward UNKNOWN neighbors at the immediately
gated destination were ZERO in every one of the 34 first-only
overrides. This indicates that the simple adjacent-cell count is
insufficient to describe the possible information advantage of
moving; visibility beyond immediate cardinal neighbors and sensor
geometry may be more relevant.

## A directly established underlying issue: visibility mismatch

The existing, frozen original observation-opportunity evidence is
already unusually strong as a measurement validity gate:

- 584 ordinary authorized sensor observations reproduced EXACTLY
  by the Phase 2 visibility shadow replay in 72 fit episodes.
- 2,637 rejected decisions were evaluated with a separate
  evaluator-only shadow MuJoCo raycast WITHOUT changing memory,
  scheduler decisions or any actions.
- 23,922 newly measurable unknown-cell/step instances occurred at
  rejected decisions. Of these, 9,651 received predicted visibility
  ZERO from the v1 public-map visibility heuristic.
- 2,643 of the predicted-zero-but-measured instances were route-near.
- A cell-center FOV/range cutoff can reject a cell partly intersected
  by the real 61-ray, 120-degree, 6-meter sensor. But other
  mismatches can result from center-line occlusion approximations.

Counts are highly correlated and repeat both cells and steps.
They do NOT imply that a new observation changes route or
rescues navigation. Also, a more permissive visibility model
may create FALSE POSITIVES: predictions that cells will be
measured when rays do not reach them.

Evidence:
results/phase2_mujoco/rdao_v1_visibility_probe_primary/summary.json
results/phase2_mujoco/rdao_v1_opportunity_analysis/summary.json

## New controlled, read-only diagnostic: footprint-aware feasibility

The proposed assessment (NOT a policy change) compares:

- **legacy:** the exact existing predicted_cell_visibility function,
  including hard center-angle and center-range gates.
- **footprint:** a candidate using the half cell diagonal to
  relax angular/range cutoffs, the same discretized 61-ray spacing,
  and the same public-map center-line occlusion/unknown penalty.

These are FEASIBILITY SCORES, not calibrated observation
probabilities. Predictions are classified positive only when
score > 0. This simple candidate is **not** an exact ray-to-cell
intersection predictor. It could easily increase false positives.

The evaluator reads all 72 committed primary RDAO v1 traces and
at each naturally granted noninitial observation:

1. Validate the frozen raw observation exactly reproduces the
   pre/post ternary memory maps.
2. Treat each previously unknown cell actually measured by the
   memory ray sensor as a positive *measured at this pose* label.
3. Treat previously unknown cells NOT measured as negatives
   for that specific pose.
4. Consider the same conservative cell-footprint FOV/range envelope
   for both predictors. Explicitly account for observed positive
   cells outside this envelope rather than quietly dropping them.
5. Record confusion counts TP/FP/FN/TN, precision, recall,
   false-positive rate and route-near subset, plus separate
   per-world summaries and raw-observation integrity checks.
6. Verify the original primary trace SHA256 matches the earlier
   completed 584-observation visibility replay; verify fixed
   sensor parameters (61 rays, 120 degrees, 6 m, 0.75 m/cell).

The resulting numbers can show whether the geometric change
recovers real observations without excessive overprediction.
Because the observations were SELECTED by the old scheduler,
the sample is selection-biased and not proof of all-pose or
held-out calibration. Per-cell counts must not be interpreted
as independent experiments.

### Files added

- [scripts/analyze_rdao_visibility_extent_audit.py](../scripts/analyze_rdao_visibility_extent_audit.py)
- [tests/test_rdao_visibility_extent_audit.py](../tests/test_rdao_visibility_extent_audit.py)

No RDAO controller, navigation planner, MuJoCo model, or frozen
experiment has been changed. Output is a separate append-only
directory.

### Local run

~~~sh
git pull --ff-only origin phase2/mujoco-proxy-pilot
.venv/bin/python -m pytest tests/test_rdao_visibility_extent_audit.py -q

# Optional short smoke-test on two frozen episode schedules.
.venv/bin/python scripts/analyze_rdao_visibility_extent_audit.py \
  --max-cases 2 \
  --output results/phase2_mujoco/rdao_v1_visibility_extent_smoke2_v1

# Full 36-world, 72-episode observational feasibility audit.
.venv/bin/python scripts/analyze_rdao_visibility_extent_audit.py
~~~

Expected full-run invariant: **584** naturally authorized,
noninitial memory observations. Outputs:
per_observation_confusion.csv and summary.json.

**Execution status:** the authoring environment has written and
pushed the code and tests but has NOT executed either. Review local
test results before trusting computed accuracy numbers.

## How to use the results responsibly

- If footprint recall improves but false-positive rate rises
  sharply, do NOT deploy the relaxed visibility gate.
- If both recall and false-positive rate improve sufficiently,
  that supports a better sensor feasibility model on these
  known fit observations, NOT that RDAO goal completion improves.
- If recall remains low, center-line occlusion/ray-rasterization
  disagreement is likely important and an actual discrete-ray
  rasterizer should be explored, still using ONLY observed memory.
- If a candidate is useful, freeze it and separately test the
  effect on observation scheduling and subsequent action planning
  in matched paired experiments. Preserve 20-observation budget,
  independent emergency sensor and selected-action shield.
- Do not tune on held-out worlds. Periodic and Age are still
  66/72 successful in original fit evaluation, compared with
  RDAO first-gate 61/72.
