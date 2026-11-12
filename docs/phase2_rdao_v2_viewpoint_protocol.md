# Experimental RDAO v2: next-viewpoint observation competition

**Status:** implemented, pushed, and ready for local tests / first matched
online FIT72 evaluation. NOT yet executed on local pinned MuJoCo,
NOT validated for superiority and NOT deployed. 2026-11-12.

## Motivation from verified causal evidence

Existing Phase 2 fit72 observations:

- Original RDAO v1: 57/72 completion, 9.11 observations/episode,
  H80-censored mean 44.74 steps, mean 24.49m, 0 unwanted contacts.
- Unmodified footprint-extent visibility (online): 59/72,
  9.93 observations, 44.82 H80-censored steps, 25.07m, 0 contacts.
- Ordinary Periodic and Age: 66/72 successes each.
- The post-hoc matched-dose periodic comparator is not the same
  as the ordinary periodic baseline: it reached 58/72.
- Footprint can improve recall of observable route-near unknown
  cells, but produces extra scans and navigation regressions.
- First-scan-plus-second-scan counterfactuals established both
  useful and harmful timing cascades:
  - R:80000017 S0 force12, suppress14, force20 -> rescue to58.
  - M:80030007 S1 force23, force48 -> rescue to66.
  - R:80000022 S0/1 force26+30 even while keeping normal27
    -> 55-to-75-step regression. Suppressing27 is not necessary.
- The exact intervention times were selected AFTER inspection
  and are not allowable online v2 triggers.

The research hypothesis is that **observing at the current
pose competes with obtaining a more informative view from the
NEXT already-planned public-memory viewpoint**. The original
RDAO does not explicitly price this opportunity cost.

## Frozen candidate algorithm (no fitted case-specific steps)

Implementation:
[src/spatial_memory/rdao_v2.py](../src/spatial_memory/rdao_v2.py)

The opt-in RDAOv2ViewpointController inherits the original v1
controller. It changes observation SCORING ONLY.

1. Keep all original v1 public ternary memory, G1 footprint-aware
   optimistic A*, route-conditioned candidate regions, free/occupied
   counterfactual costs, region cooldown, uncertainty, timing and
   budget-adjusted threshold.
2. Use the already-evaluated footprint angular/radial feasibility
   predictor for candidate visibility. It retains the original
   center-line known-occupied occlusion and unknown penalty.
3. For each currently visible candidate region, use ONLY the
   FIRST nominal planned action to estimate the next viewpoint.
   A turn updates yaw but not position. A move updates position
   ONLY IF its next cell is ALREADY KNOWN FREE, rather than unknown.
   Other actions and an absent route never cause deferral.
4. For the SAME candidate region's cells, compare current and
   next geometric view quality computed exclusively from the
   public memory. The quality proxy multiplies visibility feasibility
   by a field-of-view EDGE-COVERAGE ratio; this is necessary since
   the footprint feasibility score is otherwise almost binary with
   respect to turn orientation.
5. If next quality >= 1.25 * current quality AND improves by at
   least 0.10 in absolute units, halve THAT region's score.
   Other regions retain their scores; the original best-region
   selection and v1 adaptive budget threshold apply unchanged.
   If the deferred score still wins and beats threshold, the
   observation is allowed. No extra hard-coded "turn" rule.
6. The next viewpoint is hypothetical, not promised by shield,
   and the v2 scheduler NEVER executes an action or changes
   actual sensor memory except through inherited authorized
   observation/refresh. The next step can still be denied a scan
   due to cooldown/budget; this is a falsifiable approximation.

These constants (relative=1.25, absolute=0.10, multiplier=0.5)
are frozen as a FIRST exploratory hypothesis, not optimized
against R:80000022, the two rescue worlds or fit72 outcomes.

**Danger of taking results too far:** A conservative public
geometric quality metric is not a calibrated observation
probability and does not predict pedestrian motion, shield
rejection or actual ray-cell hits perfectly. Reducing current
scans might lose useful observations. The user research target
requires simultaneous lower observation count AND lower
travel steps/distance while preserving success and no unwanted
contacts, not just fewer observations alone.

## Implementation boundaries

- Original src/spatial_memory/rdao.py remains UNCHANGED.
- The v2 module uses a temporary single-threaded visibility
  function hook while v1 candidate regions are computed,
  restores it in a finally block, and does not replace
  the production controller. Do not use concurrent multithreaded
  evaluations with this experimental hook.
- Independent Emergency Safety sensor is untouched.
- Selected-action actual-model geometry collision shield
  and the observed-map G1 action planner are untouched.
- Max memory observations=20; sensor geometry 61 rays,
  120 degree FOV, 6m range, 0.75m/cell.
- No hidden occupancy, shadow observations, frame-ahead
  true world state, fixed episode IDs, fit-selected steps,
  or holdout evaluations are used by the algorithm.
- Scoring diagnostics include v2_base_score,
  v2_current_view_quality, v2_next_view_quality,
  v2_deferred, and v2_next_view_action.

## Matched development evaluation

Runner:
[scripts/evaluate_rdao_v2_viewpoint.py](../scripts/evaluate_rdao_v2_viewpoint.py)

Unit contracts:
- [tests/test_rdao_v2_viewpoint.py](../tests/test_rdao_v2_viewpoint.py)
- [tests/test_rdao_v2_viewpoint_screen.py](../tests/test_rdao_v2_viewpoint_screen.py)

The evaluator strictly:
- Reproduces original RDAO v1 frozen row and action/sensor
  semantics for each matched FIT case BEFORE running v2.
- Runs v2 with the same world layout, pedestrian schedule,
  seed42, cap20 and actual-model safety shield.
- Compares all 72 cases to frozen v1 AND previously saved
  footprint-only run. Separately reports 0->1 rescues,
  1->0 harmed successes and paired common-success
  step and travel distance changes.
- Records actual observation count, cumulative scheduling
  latency, step of first changed sensing, and first changed
  action/pose.
- Saves the entire v2 trace for diagnostic replication;
  writes to a new output directory, never overwriting
  protected primary/footprint evidence.
- Records unwanted contacts as outcome values, rather
  than silently dropping an unsuccessful safety result.

Commands (run local with original pinned venv and MuJoCo):

~~~sh
git pull --ff-only origin phase2/mujoco-proxy-pilot

.venv/bin/python -m pytest \
  tests/test_rdao_v2_viewpoint.py \
  tests/test_rdao_v2_viewpoint_screen.py -q

.venv/bin/python scripts/evaluate_rdao_v2_viewpoint.py \
  --max-cases 2 \
  --output results/phase2_mujoco/rdao_v2_viewpoint_smoke2_v1

.venv/bin/python scripts/evaluate_rdao_v2_viewpoint.py
~~~

Full new output:
results/phase2_mujoco/rdao_v2_viewpoint_fit72_v1/
- paired_rdao_v2_viewpoint.csv
- paired_footprint_vs_v2.csv
- v2_traces.jsonl.gz
- summary.json

## Prespecified research decision

Keep this as an experiment, do not promote as RDAO v2 success
without measurement.

1. Safety: preserve original shield/query-budget invariants
   and explicitly report ANY nonzero unwanted contacts.
2. Compare v2 goal completion to v1 57/72, footprint-only
   59/72, ordinary Periodic/Age 66/72. Censored failure
   steps must not be called true arrival times.
3. Report mean observation use, mean distance, mean H80
   censored steps, and paired distance/step change among
   shared successes. A low observation number caused by
   early failure is NOT an efficiency win.
4. Report computation cost and whether a view-ahead
   deferral actually fired. The lookahead metric costs
   additional public-map calculations.
5. If scores/deferred count almost never change, this
   v2 hypothesis is not active enough. Do not call
   behavior unchanged an improvement.
6. If v2 worsens progress, retain the negative result;
   avoid tweaking thresholds repeatedly on these
   inspected 36 development maze layouts.
7. If promising, freeze parameters and run NEW independent
   held-out mazes with observation-dose-matched periodic
   controls, reporting independent maze-count uncertainty
   and kinematic-root-only scope.

No test or rollout from this new v2 implementation has
been executed by the authoring GitHub connector.
