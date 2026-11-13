# RDAO v2.1 fit72 findings and a frozen decision-protected v2.2 candidate

**Date:** 2026-11-12.
**Evidence:** committed development worlds only, 36 independent maze layouts,
two correlated pedestrian schedules each, seed42, H80, memory cap20.
**No held-out evidence, dynamic G1 walking or deployment.**

## RDAO v2.1 observed results

Sources:
- results/phase2_mujoco/rdao_v21_current_view_quality_fit72_v1/summary.json
- results/phase2_mujoco/rdao_v21_current_view_quality_fit72_v1/paired_v21_vs_v1.csv
- results/phase2_mujoco/rdao_v21_current_view_quality_fit72_v1/paired_v21_vs_v2.csv
- results/phase2_mujoco/rdao_v21_current_view_quality_fit72_v1/v21_traces.jsonl.gz

| Metric | v1 | Footprint-only | v2 viewpoint | v2.1 angular-current-view |
|---|---:|---:|---:|---:|
| Goal successes | 57/72 | 59/72 | 61/72 | 59/72 |
| Mean memory observations | 9.111 | 9.931 | 9.556 | **8.569** |
| Mean H80-censored steps | 44.736 | 44.819 | **44.306** | 45.819 |
| Mean traveled distance | 24.490m | 25.073m | 24.354m | 24.000m |
| Unwanted contacts | 0 | 0 | 0 | 0 |
| Per-episode scheduler total ms | 316.36 | 318.37 | 325.48 | 363.36 |

Ordinary Periodic and Age EACH reached 66/72 in the earlier
same-FIT cohort. The post-hoc matched-dose periodic control was
58/72, a different comparator.

**v2.1 reduces scans by 39 in total relative to v1 (-5.94%) and
by 71 relative to v2 (-10.32%) but harms completion and route
efficiency. It is NOT a demonstrated improvement in the
joint observation/navigation objective.**

Compared to v1:
- Four newly reached episode outcomes from three world layouts:
  M:80030007 S1 (H80 fail -> reach66),
  R:80000000 S0/S1 (H80 fails -> reach62),
  R:80000017 S0 (H80 fail -> reach78).
- TWO previously reached successes are lost:
  R:80000022 S0/S1, originally reach55 but now both
  fail at H80 with 11 vs 10 observations.
- Among the 55 common-success episodes, only 1 shorter,
  38 same elapsed steps, 16 longer: **+80 total steps**.
  Their combined travel distance also INCREASES +12m.
- Mean candidate distance across ALL 72 is lower than v1
  despite this common-success regression. It must not be
  called "improved path length" without accounting for
  different H80-censored noncompletions.

Compared to v2:
- v2.1 rescues R:80000000 S0/S1 from v2's H80
  failure, but harms R:80000018 S0/S1
  (previous reach79 -> fail80) and R:80000022
  S0/S1 (previous reach59 -> fail80).
- Across 57 common successes: +101 steps, +21m travel,
  despite 38 fewer memory observations.
- v2.1 scheduler time increases over v2 by about 38ms
  per episode in this experimental measurement.

The broad full-strength suppression of low-quality FOV-edge
scans indiscriminately removes some observations whose
free/occupied G1 route counterfactual actually changes
the immediate selected action or reachability. Such
scans may be important despite partial angular coverage.

This is a mechanism hypothesis, NOT proven as a specific
causal explanation of either harmed maze. The next
candidate is designed to test it.

## RDAO v2.2: decision-protected current-view quality

Source:
[src/spatial_memory/rdao_v22_decision_protected.py](../src/spatial_memory/rdao_v22_decision_protected.py)

This is a **single, one-variable public-map controller change
relative to frozen v2 viewpoint**. It preserves:
- v2 footprint-extent visibility, original v1 G1 A* planning,
  uncertain cells and temporal observations, candidate-region
  membership, route relevance, next-viewpoint deferral,
  score threshold/budget, observation cap20;
- emergency sensor and actual-model selected-action shield;
- all prior v1/v2/v2.1 result files, no updates or overrides;
- no identity/seed/step allowlists, no hidden occupancy,
  future sensor values or shadow raycasts.

For each candidate region:
1. Reuse the original RDAO's counterfactual public
   G1 A* free/occupied results already calculated
   in v2 for route relevance.
2. If the two scenarios differ on the FIRST selected
   G1 action OR goal reachability, preserve the region's
   FULL original v2 score. It is "decision protected".
3. Otherwise, reduce the score by the ratio between
   current sensor FOV angular-coverage quality and
   the current footprint feasibility. Keep the score
   between zero and the original v2 score.
4. The existing v2 one-step next-viewpoint deferral
   still applies BEFORE this optional quality discount.
5. Do not force any sensor observation. Do not alter
   action selection, planner dynamics or safety shield.

The distinction is **not** an arbitrary maze-specific
hard-coded Step; all inputs are legal, available
at the current decision time. Nonetheless, the
decision-protected heuristic may also miss useful
observations whose effect occurs on LATER path steps
rather than the immediate action.

## Test and evaluation protocol

Implementation:
- [scripts/evaluate_rdao_v22_decision_protected.py](../scripts/evaluate_rdao_v22_decision_protected.py)
- [tests/test_rdao_v22_decision_protected.py](../tests/test_rdao_v22_decision_protected.py)
- [tests/test_rdao_v22_decision_protected_screen.py](../tests/test_rdao_v22_decision_protected_screen.py)

The evaluator:
- individually reproduces the original frozen v1 run
  and complete trace prefix before applying v2.2;
- evaluates precisely the same FIT72 baseline episodes;
- reads saved v1, footprint-only, v2 and v2.1 outcomes
  and compares every matched world/schedule without
  generating additional control-arm rollouts;
- records observed scans, step/distance and goal outcome,
  protected candidate count, discounted candidate
  count, scheduler computation and unwanted contacts;
- refuses to overwrite a pre-existing output directory;
- hashes critical frozen evidence before and after.

### Run locally

~~~sh
git pull --ff-only origin phase2/mujoco-proxy-pilot

.venv/bin/python -m pytest \
  tests/test_rdao_v22_decision_protected.py \
  tests/test_rdao_v22_decision_protected_screen.py -q

.venv/bin/python scripts/evaluate_rdao_v22_decision_protected.py \
  --max-cases 2 \
  --output results/phase2_mujoco/rdao_v22_decision_protected_smoke2_v1

.venv/bin/python scripts/evaluate_rdao_v22_decision_protected.py
~~~

Full results directory:
results/phase2_mujoco/rdao_v22_decision_protected_fit72_v1/
- paired_v22_vs_v1.csv
- paired_v22_vs_footprint.csv
- paired_v22_vs_v2.csv
- paired_v22_vs_v21.csv
- v22_traces.jsonl.gz
- summary.json

These are NOT yet tested on the user's local
pinned Python/MuJoCo environment. If tests or
smoke fail, stop before running the full screen.

## Decision boundary

A satisfactory outcome needs:
- zero unwanted contacts and all original safety
  assertions intact;
- preservation or improvement of v2's 61/72 success,
  with no unacceptable harmed-success regressions;
- lower scans than v1's 9.11, not just lower than v2;
- lower or unchanged travel/steps among common
  successes, not merely reduced distance on failures;
- scheduler cost comparison and sound uncertainty
  counting (36 independent layouts, not 72).

It is possible the candidate fails these criteria.
Do NOT tune multiple FOV weights on these already
repeatedly evaluated fit36 layouts until one appears
to "win". Regardless of v2.2's results, the
next research phase should freeze any viable candidates
and validate them on NEW, independent maze layouts.
Stop treating additional fit-only screens as generalization.
