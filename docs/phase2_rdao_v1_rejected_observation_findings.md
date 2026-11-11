# Phase 2 RDAO v1 — rejected-observation shadow replay findings

**Stage:** development-only follow-up to the visibility diagnostic protocol.
**Date:** 2026-11-11.
**Status:** user-reported local execution completed; raw CSV/JSON outputs are local, not committed here.
**Do not modify or reinterpret the preserved Phase 1.5 or historic Phase 2 results.**

## Verified replay output reported

| Scope | Episodes | Rejected decisions with passive shadow probes | Accepted noninitial observations exactly reproduced |
|---|---:|---:|---:|
| Three diagnostic cases | 3 | 127 | 27 |
| Full primary development run | 72 | 2,637 | 584 |

On the 72-episode primary development run:

| Shadow measurement across rejected decisions | Total (cell-steps, not independent cells) |
|---|---:|
| Previously unknown cells actually revealed by the sensor | 23,922 |
| Of those, free | 15,428 |
| Of those, occupied | 8,494 |
| Newly revealed cells within Manhattan distance 1 of next six nominal A* route actions | 6,288 |
| Revealed but predicted visibility equals zero | 9,651 |
| Revealed, route-near, but predicted zero | 2,643 |
| Revealed with cell center outside the +/-60 degree FOV test | 2,198 |
| Revealed with cell center beyond the 6 m range test | 1,704 |
| Revealed and predicted zero for other reasons (including map occlusion) | 5,810 |

The heuristic predicted zero visibility for 40.3% (9651/23922) of the
actually newly visible **cell-step** observations, and for 42.0%
(2643/6288) of the route-near newly visible cell-steps. These are
conditional on the shadow sensor seeing a cell; they are *not* a
false-negative rate over all possible map-cell predictions. The
angular/range/other counts are not mutually exclusive; the first two
categories overlap.

**Interpretation:** At rejected decisions the true pinned MuJoCo sensor
could often have revealed unknown map cells, including cells near the
nominal route. This supports a sensor-model calibration problem. It
does not show which rejected decisions were navigation-relevant, nor
does it establish that an extra observation would improve success.

## Additional architectural hypothesis from source inspection

RDAOController._plan evaluates plan_g1_forward_facing while the
frozen movement controller uses plan_g1_default_policy, which may
choose pedestrian-aware sidestep/retreat/wait and obstacle sidesteps;
an independent Emergency Safety controller can further override the
selected action. Therefore RDAO's nominal-route/action-change heuristic
may disagree with the actual executed action even when its base A*
computation is correct. This is a separate potential mechanism to test,
not a confirmed explanation for the failures.

## Step 1b: turn cell counts into decision-level evidence

Run the new offline analyzer on the saved CSVs:

~~~sh
.venv/bin/python scripts/analyze_rdao_visibility_probe.py
~~~

It refuses to overwrite its own output directory and produces:

- results/phase2_mujoco/rdao_v1_opportunity_analysis/summary.json
- results/phase2_mujoco/rdao_v1_opportunity_analysis/decision_reason_summary.csv
- results/phase2_mujoco/rdao_v1_opportunity_analysis/episode_opportunity_summary.csv
- results/phase2_mujoco/rdao_v1_opportunity_analysis/priority_failure_cases.csv

The analyzer validates the shadow-probe row counts and totals, joins
each episode to frozen RDAO and Periodic/Age/Uncertainty outcomes,
reports the fraction of rejected decisions with actually newly visible
route-near cells (including a first-20-step restriction), and prioritizes
cases in which RDAO failed while simpler baselines succeeded. Per-step
opportunities, not raw cell totals, are the main unit for selection.

## Step 2: prospective intervention replay — proposed, not run

Using only exploratory development cases and a frozen baseline,
choose the earliest high-priority rejection preceding the first
movement divergence from a successful comparator. With the same saved
world, pedestrian schedule, and seed, introduce exactly one additional
authorized observation at that step, drawn from the usual sensor,
then continue the real navigation/safety controller. Keep the RDAO
observation cap unchanged and report actual counts. Include a
matched-dose condition: an extra early observation must not secretly
receive a larger total budget. Report whether the post-intervention
observation changes memory, next action, total path, time to goal,
success, blocked attempts, and unwanted contact.

The shadow sensor used to find opportunities remains evaluator-only:
never use its readings to decide when the intervention policy should
observe. Selection of pre-registered intervention steps is a
development-only diagnostic tool, not an online deployable policy.

## Potential RDAO v2 hypotheses (not yet changes)

1. Predict visibility by finite cell geometry and remembered-map ray
   traversal, not by center-angle and center-distance zero gates.
2. Evaluate the actual decision context (observed pedestrian and
   static obstacle feedback) or explicitly measure the mismatch
   with the simplified A* heuristic.
3. Use a cheap route-near/uncertainty prefilter before expensive
   counterfactual A*, then budget observations against online,
   dose-controlled Periodic/Age schedules.
4. Hold independent safety and selected-action collision checks fixed;
   report runtime and route efficiency separately from observations.
5. Freeze method and thresholds before using any held-out suite.

**No claim of RDAO superiority or improved success is made by this diagnostic.**
