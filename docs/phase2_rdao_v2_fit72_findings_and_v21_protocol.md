# RDAO v2 viewpoint FIT72 results and frozen v2.1 current-view quality candidate

**Date:** 2026-11-12.
**Status:** v2 viewpoint evaluation COMPLETE and committed on FIT72;
v2.1 current-view angular quality IMPLEMENTED but NOT TESTED/RUN
on the user's pinned MuJoCo environment at authoring time.

These are 36 previously inspected developer-world layouts with two correlated
pedestrian schedules each (72 episodes, horizon80, seed42). There is NO
independent held-out or dynamic biped walking evidence in this document.

## Ground-truth committed v2 online development evaluation

- results/phase2_mujoco/rdao_v2_viewpoint_fit72_v1/summary.json
- results/phase2_mujoco/rdao_v2_viewpoint_fit72_v1/paired_rdao_v2_viewpoint.csv
- results/phase2_mujoco/rdao_v2_viewpoint_fit72_v1/paired_footprint_vs_v2.csv
- results/phase2_mujoco/rdao_v2_viewpoint_fit72_v1/v2_traces.jsonl.gz

| Metric | Original RDAO v1 | Footprint-only | Viewpoint v2 |
|---|---:|---:|---:|
| H80 goal completions | 57/72 | 59/72 | **61/72** |
| Mean memory observations | **9.111** | 9.931 | 9.556 |
| Mean H80-censored steps | 44.736 | 44.819 | **44.306** |
| Mean traveled distance | 24.490m | 25.073m | **24.354m** |
| Unwanted contact pairs | 0 | 0 | 0 |
| Mean RDAO scheduler cumulative time per episode | 316.364ms | 318.367ms | 325.482ms |

Ordinary Periodic and Age each reached **66/72** goal
completions on these fit episodes, not to be confused
with the earlier **58/72** post-hoc matched-dose
periodic control.

The public next-viewpoint multiplier actually fired:
310 deferred candidate-region scores across
240 decision steps; 57/72 episodes contain at least
one such region. Observation timing changed in 44/72
episodes, executed action or pose in 23/72.

### Compared to v1

- Four rescued failure episodes across only **three
  distinct maze identities**; no previously successful
  episode became a horizon failure.
- R:80000017 S0: fail H80 -> reach58,
  15 -> 10 observations, 43.50 -> 29.25m.
- M:80030007 S1: fail H80 -> reach66,
  17 -> 17 observations, distance unchanged34.5m.
- R:80000018 S0 and S1: fail H80 -> reach79,
  13 -> 13 observations, unchanged43.5m. These
  are marginal one-step successes at a horizon of80,
  NOT robust evidence of improved completion.
- Among the **57 paired common successes**, five
  are faster, 46 same steps, six slower; total
  steps **+7** and distance **+1.5m**. This is
  NOT a general route-speed improvement among
  episodes that would already complete.
- Overall across 72, there are 32 ADDITIONAL
  memory observations vs v1 (+0.444 per episode).
  On common successes alone +29 observations.
- Family changes (24 episodes per family):
  R 18->21 successes; BP22->22; M17->18.
  The same maze identity repeated under two
  schedules is NOT an independent replication.

Compared to footprint-only:
- +2 successes, both the same maze R:80000018
  across two correlated pedestrian schedules.
- -27 total memory observations, -37 total H80
  censored steps, and -51.75m total travel.
- For the **59 paired common successes**: eight
  episodes faster, 42 same steps, nine slower
  (total -35 steps), and six distance-better,
  51 distance-same, two distance-worse
  (total -33m).
- These contrasts suggest a benefit from
  one-step prospective observation competition
  relative to naïve footprint-extent feasibility.

### Main decision

The observation-timing improvement is REAL in the
frozen deterministic FIT development cases, but
DOES NOT MEET the user's original simultaneous
objective vs RDAO v1 because mean observations
increase from9.11 to9.56. Nominal v2 steps/distance
improve on average, but most gains come from
rescued H80 failures; conditional common-success
movement efficiency slightly deteriorates.

Do NOT call v2 a superior robust scheduler or
promote to production. Do NOT tune its constants
based on these inspected world identities.

## One-variable v2.1 candidate: current-view angular quality

Code:
- [src/spatial_memory/rdao_v21_quality.py](../src/spatial_memory/rdao_v21_quality.py)
- [scripts/evaluate_rdao_v21_quality.py](../scripts/evaluate_rdao_v21_quality.py)
- [tests/test_rdao_v21_quality.py](../tests/test_rdao_v21_quality.py)
- [tests/test_rdao_v21_quality_screen.py](../tests/test_rdao_v21_quality_screen.py)

The v2 lookahead was already comparing two poses
using a geometric FOV angular-coverage proxy.
But v2 candidate regions used the MORE PERMISSIVE
binary footprint feasibility score for the
CURRENT pose, potentially authorizing low-quality
partial-FOV scans. v2.1 changes this ONE aspect:
use **the same public angular-coverage quality
for the current region's visibility score**.

The model uses only decision-time public
orientation, public ternary memory and configured
61-ray sensor FOV/range; it does not read hidden
actual occupancy or shadow scans. The angular
coverage factor is a heuristic, NOT a calibrated
sensor hit probability.

Everything else stays the same as v2:
- original v1 counterfactual free/occupied
  observed-map G1 route relevance;
- existing nominal lookahead and candidate regions;
- existing threshold0.22, budget price,
  confidence and visibility attenuation;
- next-view gain factor >=1.25 and absolute>=0.10,
  score multiplier0.50;
- max20 authorized spatial-memory scans;
- original emergency sensor, selected-action true-
  geometry shield and G1 planner;
- no world/step IDs, no failure trace fingerprints,
  no oracle or future sensor data.

A v2.1 scan could lose useful information at the
FOV boundary; reduced memory observations alone
are NOT success, and harming existing successful
episodes is a major regression. This is only a
simple frozen *first* v2.1 exploratory hypothesis,
not tuned fit72 optimization.

The v2.1 runner individually reproduces each v1
original frozen metric and semantic trace; executes
v2.1 once; and compares the result with all
three saved reference arms (v1, footprint-only,
v2 viewpoint). It refuses to overwrite any
existing output and hashes protected evidence.

### Commands on the pinned local environment

~~~sh
git pull --ff-only origin phase2/mujoco-proxy-pilot

.venv/bin/python -m pytest \
  tests/test_rdao_v21_quality.py \
  tests/test_rdao_v21_quality_screen.py -q

# Independent two-case smoke output directory:
.venv/bin/python scripts/evaluate_rdao_v21_quality.py \
  --max-cases 2 \
  --output results/phase2_mujoco/rdao_v21_current_view_quality_smoke2_v1

# Complete 72-episode comparison with frozen prior arms:
.venv/bin/python scripts/evaluate_rdao_v21_quality.py
~~~

Complete output in a NEW directory:
results/phase2_mujoco/rdao_v21_current_view_quality_fit72_v1/
- paired_v21_vs_v1.csv
- paired_v21_vs_footprint.csv
- paired_v21_vs_v2.csv
- v21_traces.jsonl.gz
- summary.json

**Authoring status:** new test suite and 72-case
runner are GitHub-committed but not locally run.
If a test or pilot fails, stop the full run;
do not treat the candidate as validated.

## Prespecified interpretation

A useful candidate must at minimum:
1. Not worsen the zero-unwanted-contact outcome;
2. Preserve or improve actual goal completion
   relative to earlier arms;
3. Reduce realized observation count relative to
   v1 **and** v2, without simply failing earlier;
4. Improve route distance and H80-censored steps
   not only through the new rescue episodes,
   but also examine paired common-success
   efficiency and total observation dose;
5. Keep runtime scheduling overhead reasonable.

If v2.1 reaches fewer goals or deteriorates
observed routes, retain that negative
development result; do not retroactively
select fit-world-dependent thresholds. If it
does well, FREEZE the hypothesis and validate
on independently generated maze layouts,
reporting paired world-level variability
rather than treating two pedestrian schedules
as 2 independent worlds.

These FIT worlds cannot establish novelty,
generalization or physical Unitree G1 motion.
