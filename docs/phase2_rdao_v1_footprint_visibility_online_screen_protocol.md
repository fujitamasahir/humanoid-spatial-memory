# RDAO v1 footprint visibility: measured tradeoff and online A/B test protocol

**Date:** 2026-11-12.
**Evidence:** completed saved 72-episode, 36-fit-world, 584-authorized-observation
read-only audit, 61 rays, 120 degree FOV, 6 m range, 0.75 m cells.
This is NOT held-out data and does NOT establish better navigation.

## Reproducible public evidence

- results/phase2_mujoco/rdao_v1_visibility_extent_audit_v1/summary.json
- results/phase2_mujoco/rdao_v1_visibility_extent_audit_v1/per_observation_confusion.csv
- results/phase2_mujoco/rdao_v1_visibility_probe_primary/summary.json
- scripts/analyze_rdao_visibility_extent_audit.py

The frozen RDAO v1 input trace SHA256 exactly matches the earlier
sensor-fidelity shadow replay. Each saved authorized raw observation
reproduces its pre/post memory transition, and no policy is rerun in
this *offline* diagnostic.

The binary classification question is "would the 61-ray sensor report
this previously unknown cell at the naturally selected pose?".
Cells are admitted to the shared candidate pool by the same
conservative footprint FOV/range envelope; 29 measured unknown
cell-pose positives were OUTSIDE even this envelope and are
explicitly excluded from both predictors' confusion matrices.
Conditional precision/recall below are not full-scene probabilities.

## Full candidate envelope: recall gains but extensive false positives

| Metric | Original v1 visibility | Proposed footprint visibility |
|---|---:|---:|
| TP | 6328 | 7006 |
| FP | 9512 | 13143 |
| FN | 2229 | 1551 |
| TN | 22329 | 18698 |
| Recall | 73.95% | 81.87% |
| Precision | 39.95% | 34.77% |
| False-positive rate | 29.87% | 41.28% |

The relaxed footprint gate adds **678** correctly predicted visible
cell-pose pairs but **3,631** false predictions across the envelope.
Only 15.73% of its ADDITIONAL positive predictions are correct.

## Public route-near cells: more favorable tradeoff

The original RDAO's _regions() ALREADY filters eligible
candidate cells to Manhattan distance <=1 of the first
six nominal route actions plus starting cell, when
use_route_relevance=True (the default).

On this same public route-near subset:

| Metric | Original v1 visibility | Proposed footprint visibility |
|---|---:|---:|
| TP | 3394 | 3558 |
| FP | 2027 | 2043 |
| FN | 1174 | 1010 |
| TN | 1139 | 1123 |
| Recall | 74.30% | 77.89% |
| Precision | 62.61% | 63.52% |
| False-positive rate | 64.02% | 64.53% |

Among 180 NEWLY predicted-positive route-near cell-pose pairs,
164 were actually measured, while 16 were not: 91.11%
incremental precision. The 4,129 newly predicted positive pairs
outside the route-near subset have only 514 TP and 3,615 FP,
or 12.45% incremental precision.

The initial OFFLINE improvement is therefore substantially
more relevant to the default RDAO's candidate selection than
whole-map metrics might suggest. But the already high
route-near false-positive rate (64%) remains problematic:
a strictly >0 heuristic score is not a calibrated probability
of the sensor measuring a cell.

### Across independent maze identities (not 72 independent worlds)

Detailed per-world and 584-row audit CSV grouping confirms:
- 32 of 36 distinct worlds have at least one additional
  correct route-near prediction.
- 31 of 36 have ZERO new false-positive route-near predictions.
- 27 worlds show route-near TP gains with ZERO FP gains.
- Only five worlds show any additional route-near false positives.
- Per architecture family, incremental route-near TP/FP:
  - R: +81 / +14 (12 worlds)
  - BP: +45 / +2 (12 worlds)
  - M: +38 / +0 (12 worlds)

This is broad descriptive within-fit coverage, not replicated
generalization. Results may depend on the old RDAO's selected
poses, local geometry and ray rasterization.

## Why this is NOT yet a validated RDAO improvement

1. Original observations were selected using the old
   predictor. Running a changed predictor may produce
   different observations and route trajectories, and
   change the future map and the candidate cell population.
2. The audited candidates are previously UNKNOWN cells;
   stale previously observed cells also enter the real
   RDAO scheduler with time-dependent uncertainty.
3. RDAO uses visibility values alongside route relevance,
   uncertainty, threshold, region cooldown and remaining
   budget; binary score>0 is not the actual decision rule.
4. Only 584 naturally granted observations across 36
   development-world layouts were measured; no independent
   random viewpoints or held-out outcome test was performed.
5. Even more useful observations may increase total
   measurement count and the number of in-place turns.
   Path length, completion and mean observation use
   must be evaluated jointly.
6. The candidate retains the original centerline occlusion
   heuristic and can still miss partially visible cells.
   The 29 observed cells outside the conservative
   FOV/range envelope indicate a remaining sensor-grid
   discrepancy worth tracking separately.

## New online A/B experiment (ONE changed input)

- [scripts/evaluate_rdao_footprint_visibility_online.py](../scripts/evaluate_rdao_footprint_visibility_online.py)
- [tests/test_rdao_footprint_visibility_online.py](../tests/test_rdao_footprint_visibility_online.py)

The new candidate changes ONLY the function called from
RDAOController._regions: public-memory angular/radial
visibility to an expanded footprint model. Because route
relevance is unchanged, this tests the feasibility correction
in the already-route-limited RDAO scheduler. No route-inertia
Gate first/every, no new thresholds, no oracle occupancy,
no shadow sensing, no future labels.

For EACH selected fit-world episode:
- Reproduce the frozen original baseline with exactly
  matching row signature and per-step action/observation/safety
  semantics.
- Run one candidate with identical world, seed, schedule,
  sensor budget, RDAO score threshold and G1 planner.
- Record first sensing and action/pose divergence
  independently, and fail if executed action changes before
  the first change in authorized observation timing.
- Preserve independent emergency sensor, selected-action
  true-geometry shield and total unwanted contacts=0.
- Restore the original global visibility function after each
  candidate even if an exception interrupts execution.
- Protect the original Phase1.5 prefix and checksum all
  frozen primary input artifacts. Do not overwrite old runs.
- Compare rescues/harms, step/distance on paired original
  successes, observation count and RDAO scheduling latency.
- Compare Periodic/Age (66/72 fit successes), but do not
  claim independent held-out improvement.

### Local execution

~~~sh
git pull --ff-only origin phase2/mujoco-proxy-pilot
.venv/bin/python -m pytest tests/test_rdao_footprint_visibility_online.py -q

# Two-case smoke test; does NOT overwrite the 72-case full output:
.venv/bin/python scripts/evaluate_rdao_footprint_visibility_online.py \
  --max-cases 2 \
  --output results/phase2_mujoco/rdao_v1_footprint_visibility_online_smoke2

# Full 72-episode screen:
.venv/bin/python scripts/evaluate_rdao_footprint_visibility_online.py
~~~

The proposed run writes paired_visibility_online.csv,
visibility_online_traces.jsonl.gz, and summary.json.
Its logic and tests have been committed but have NOT been
executed with the user's pinned local MuJoCo environment
in this authoring session.

## How to decide what comes next

- If navigation success and contact-free path efficiency
  improve, preserve the original score/threshold and test
  a frozen variant on independent held-out worlds.
- If recall improvements do NOT change observation timing,
  report a sensor-prediction result without claiming
  navigation gains.
- If the variant grants more observations but does not
  improve routes, test a predeclared matched-dose control
  and report the observation price / compute tradeoff.
- If it harms performance, do not attempt many fit-tuned
  thresholds. Investigate whether the binary geometry
  prediction remains miscalibrated, especially false-positive
  occlusion and expected viewpoint value.
- The earlier online safe route Gate on its own has not
  beaten Periodic or Age (first=61/72 vs their 66/72);
  do not combine candidate changes until each factor has
  been independently characterized.
