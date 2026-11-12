# RDAO Footprint: first-sensing counterfactuals and second-sensing mechanism test

**Status:** completed FIT-world first-scan intervention for **9 saved episode
schedules, 18 experimental arms** (extra and swap), no unwanted contacts.
This is RETROSPECTIVE development research, not held-out validation
or a deployable schedule. Dynamic G1 walking is not shown.

## Exact committed evidence

- results/phase2_mujoco/rdao_v1_footprint_first_sensing_causes_v1/
  first_sensing_causal_comparison.csv
- results/phase2_mujoco/rdao_v1_footprint_first_sensing_causes_v1/
  first_sensing_causal_traces.jsonl.gz
- results/phase2_mujoco/rdao_v1_footprint_first_sensing_causes_v1/summary.json
- results/phase2_mujoco/rdao_v1_footprint_first_sensing_rescue_pilot_v1/
- results/phase2_mujoco/rdao_v1_footprint_visibility_online_fit72_v1/
- results/phase2_mujoco/rdao_v1_footprint_visibility_online_forensics_v1/

Original full RDAO was replayed with exact semantics. Every first
forced observation used a normally authorized 61-ray sensor at the
identical pre-action pose and heading and produced exactly the same
raw observed cell values and public memory update as the previously
committed Footprint-only policy at that step. The first action and
post-observation route also matched Footprint in ALL 18 runs.
Thus failure to reproduce the full Footprint episode outcome
is NOT attributable to inconsistent first-scan geometry.

## Results (80-step cap)

| Case | Original | Full Footprint | First EXTRA only | First SWAP only |
|---|---|---|---|---|
| R:80000017 S0 | failure H80 | reach58, 29.25m, 10 obs | fail H80, 44.25m, 15 obs | fail H80, 42m, 14 obs |
| M:80030007 S1 | failure H80 | reach66, 34.5m, 16 obs | fail H80, 34.5m, 16 obs | fail H80, 34.5m, 16 obs |
| R:80000022 S0 and S1 | reach55, 31.5m, 10 obs | reach75, 43.5m, 14 obs | reach55, 31.5m, 11 obs | reach75, 43.5m, 13 obs |
| BP:80010001 S0 | reach72 | reach80 | reach80 | reach74 |
| BP:80010004 S0 | reach27 | reach33 | reach27 | reach29 |
| BP:80010013 S0 | reach23, 11.25m, 5 obs | reach17, 9.75m, 4 obs | reach17, 9.75m, 4 obs | reach17, 9.75m, 4 obs |
| M:80030009 S0 and S1 | failure H80 | failure H80 | failure H80 | failure H80 |

"Reach80" means **success=True at Step80**, NOT failure.
There are no newly caused unwanted contacts in these
18 first-intervention arms. The schedules from the same world
are correlated and not independent maze draws.

## Newly constrained causal findings

### R:80000022: timing REPLACEMENT, not initial extra scan, explains detour

Both pedestrian schedules repeat the EXACT result.

Original takes an observation at Step27 and reaches Step55.
Forced-extra observes at Step26 PLUS Step27; it
also reaches Step55 with identical executed travel.
Continuous Footprint observes Step26, not Step27, next at
Step30 and reaches Step75 instead.

The first-scan SWAP observes Step26, suppresses the NEXT
natural scan at Step27, and then observes at Step28.
It also reaches Step75 and travels 43.5m, and its
full executed action/pose trajectory matches Footprint
despite different observation timings (next 28 vs 30).
First 26 scan and immediate action/plan were identical
across forced arms. The difference between extra and
swap was the *Step27 suppression* plus its subsequent
closed-loop consequences.

Thus the first footprint scan alone is NOT enough to
produce the detour, and **early sensing at the price of
displacing a follow-up scan** reproduces it. Whether
the causal difference is absence of information at the
specific Step27 viewpoint, resulting visibility/cooldown
dynamics, or subsequent changed mapped route is NOT yet
identified at cell level.

One important logical qualification: a SWAP includes
later natural scans on the new trajectory, and final
observation count differs, so it does not prove "the only
cause was loss of a particular cell".

### BP:80010013: first earlier scan sufficient for efficiency gain

Original reach23, 11.25m, five scans. Footprint reach17,
9.75m, four scans. First scan alone forced at Step2
replicates reach17, 9.75m, four scans in BOTH extra and
swap. The extra-control scan schedule matches Footprint
exactly: [0,2,7,11]. The later Footprint visibility rule
is not required for this observed world/schedule outcome.
This is a valuable case study of a beneficial early
observation and lower realized sensing dose, NOT a
general runtime predictive rule.

### The TWO rescued failures require more than first scan

**R:80000017 S0:** Original fails H80, Footprint reaches
Step58 at 29.25m (10 obs). First-extra observes Step12
(14 new cells) and still fails H80 (15 obs).
First-swap also fails H80 (14 obs). Its suppressed
natural scan is Step14. Forced-extra diverges in sensing
from Footprint at Step14, but forced-swap follows the
same *executed actions* as Footprint through Step19
and first diverges in sensing/action at Step20.
Footprint observes at Step20 while forced-swap does
not. Step20 is therefore the next specifically identified
candidate for a two-observation mechanism test.

**M:80030007 S1:** Original fails H80, Footprint reaches
Step66 (16 obs) while cutting emergency interventions
14 -> 1. Both first-only interventions at Step23
still fail H80 (16 obs), with 16 emergency interventions
under the original visibility continuation. First-extra
actually matches Footprint's FULL sensing pattern AND
selected actions through Step47; the two arms first
diverge in sensing/action at **Step48**.
Footprint grants an observation at 48; first-extra does
not, then naturally observes at 49. Therefore Step48
is the most controlled second-scanning intervention
candidate for this rescue.

These are differential decision-timing observations,
not evidence that the two earlier scans ALONE are
sufficient until the next counterfactual is run.

### Other weaker cases

- BP:80010001 S0: first extra reproduces Footprint's
  slower Step80 arrival, while swap reaches Step74,
  closer to original Step72. Dose/timing affects path.
- BP:80010004 S0: first extra retains original
  Step27 completion; first swap Step29, full Footprint
  Step33. Additional downstream sensing is needed
  to reproduce the full detour.
- M:80030009 S0/S1: neither first intervention
  rescues the episode, and full Footprint adds six
  observations and 3m travel with failure at H80.
  Observation increase is not synonymous with
  better planning or goal success.

## New second-sensing experiment: fixed public original controller

Implementation:
- [scripts/evaluate_rdao_footprint_second_sensing_interventions.py](../scripts/evaluate_rdao_footprint_second_sensing_interventions.py)
- [tests/test_rdao_footprint_second_sensing_interventions.py](../tests/test_rdao_footprint_second_sensing_interventions.py)

It leaves the full Footprint scheduler AS SAVED reference.
The experimental controller uses the ORIGINAL RDAO
visibility rule throughout. It reproduces the original
frozen run and the first-scan control, then changes
ONE additional observation decision at the already
recorded second step.

Predefined fit cases and arms:

| Case | First forced | One first-control suppression | Second forced |
|---|---:|---|---:|
| R:80000017 S0 | 12 | swap: suppress next natural Step14 | **20** |
| M:80030007 S1 | 23 | none | **48** |
| R:80000022 S0 | 26 | extra: none | **30** |
| R:80000022 S0 | 26 | swap: suppress next natural Step27 | **30** |
| R:80000022 S1 | 26 | extra: none | **30** |
| R:80000022 S1 | 26 | swap: suppress next natural Step27 | **30** |

At the second forced scan, it verifies:
- the original first-only control did NOT observe there,
  while the saved Footprint controller DID;
- the pre-action pose and heading exactly match both
  saved Footprint and newly forced control;
- the raw sensor cell/value list exactly matches
  the saved Footprint sensor at the same step;
- post-memory maps are compared but are not required
  identical when prior scans differed.

Every source artifact is SHA256 checked before/after.
Selected-action emergency/true-geometry safety remains
unchanged and all unexpected unwanted contacts are
recorded as outcomes, never omitted.

### Local reproducible commands

~~~sh
git pull --ff-only origin phase2/mujoco-proxy-pilot

.venv/bin/python -m pytest \
  tests/test_rdao_footprint_second_sensing_interventions.py -q

# 2 rescue cases first:
.venv/bin/python \
  scripts/evaluate_rdao_footprint_second_sensing_interventions.py \
  --max-cases 2 \
  --output results/phase2_mujoco/rdao_v1_footprint_second_sensing_rescue_pilot_v1

# Full 6 predefined arms (including both correlated R:80000022 schedules):
.venv/bin/python \
  scripts/evaluate_rdao_footprint_second_sensing_interventions.py
~~~

Expected new files:
- second_sensing_causal_comparison.csv
- second_sensing_causal_traces.jsonl.gz
- summary.json

**Authoring status:** all new code is GitHub-committed but not
executed on the user's pinned MuJoCo environment.

## Decision implications

Do NOT conclude that footprint visibility alone is an
improved RDAO v2; online full fit screen was 59/72
successes vs RDAO 57/72 and ordinary Periodic/Age
baselines of 66/72 each; the prior matched-dose periodic
post-hoc control instead attained 58/72, with *more* observations and
distance on aggregate. Observational accuracy gains
on route-near cell-pose pairs do not suffice for
online movement efficiency gains.

This new second-sensing intervention tests the
specific, measurable failure/benefit mechanism:
whether one more early observation changes outcome.
If it rescues one or both earlier failures, the
research question moves to **which decision-time
public spatial-memory cues justify those scans**.
If it fails, later closed-loop sensing and
planning changes remain necessary.

All outcomes remain development-only. Predefine
a conservative algorithm before any independent
reserved evaluation; include observation-dose
and actual travel metrics, footprint safety,
calculation cost and simpler periodic controls.
