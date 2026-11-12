# Phase 2 RDAO v1 — 2x2 timing factorial outcomes and next mechanism test

**Status:** exploratory development-only, reported results committed and source-verified.
**Date:** 2026-11-12. The simulator is a kinematically moved MuJoCo G1,
not validated physical walking. The two schedules of each world are
correlated repeats of the same environment.

## 2x2 observation intervention summary

Step 2 / step 3 observation indicators are 0=no and 1=yes.
Every row is the same for schedule 0 and schedule 1 of its world.

| World | Arm | Success at horizon 80 | Steps | Memory observations | Distance (m) | Unwanted contacts |
|---|---|---|---:|---:|---:|---:|
| M:80030010 | 01 (original) | No | 80 (censored) | 20 | 41.25 | 0 |
| M:80030010 | 00 (skip step3) | Yes | 28 | 6 | 15.0 | 0 |
| M:80030010 | 10 (step2 only) | Yes | 28 | 7 | 15.0 | 0 |
| M:80030010 | 11 (both) | No | 80 (censored) | 20 | 41.25 | 0 |
| R:80000018 | 01 (original) | No | 80 (censored) | 13 | 43.5 | 0 |
| R:80000018 | 00 | No | 80 (censored) | 14 | 42.75 | 0 |
| R:80000018 | 10 | No | 80 (censored) | 14 | 42.75 | 0 |
| R:80000018 | 11 | No | 80 (censored) | 14 | 43.5 | 0 |

All rows were loaded from the committed factorial comparison CSV.
Additional trajectory inspection decompressed the committed compressed
factorial trace evidence, checking every **executed action and pose**:

- In M:80030010, arms 00 and 10 have identical action/pose sequences
  across all 28 steps, despite one additional step-2 observation in 10.
- In M:80030010, arms 01 and 11 have identical action/pose sequences
  across all 80 steps, despite one additional step-2 observation in 11.
- These equalities also hold for both environment schedules.
- In R:80000018, arms 01 and 11 again share executed actions throughout;
  arms 00 and 10 do NOT share every action, and both still fail.

**Identified causal contrast for M (selected world, fixed intervention):**
Suppressing the natural **step-3** spatial memory observation is sufficient
to switch goal completion from 0/2 to 2/2 within horizon 80. Forcing
step-2 sensing alone does not change the executed trajectory or outcome
at all in this particular world. The first action difference is at
step 3, and the subsequent trajectory differences extend throughout.

The original Step 3 sensor reading is not shown to be incorrect or unsafe.
Its seven newly resolved cells change the forward-facing A* cost from
14.25 to 18.75 and the initial action from westward move to northward
turn. With the step-3 observation suppressed, the robot first moves
west to (7,8), **then observes at step 4 from a changed viewpoint**,
updating seven cells and replanning. Both M arms that skip step 3 use
the same 28-step action path. Thus suppression changes not only whether
and when information enters memory but also **WHERE the next memory
observation happens**, creating a downstream viewpoint-selection effect.
The data do not isolate the longer-term contribution of replanning
stability from this viewpoint change.

The normal RDAO goal completion baseline remains 57/72 vs Periodic
66/72 and Age 66/72 in the saved Phase 2 development matrix. A
single selected-world diagnostic does not overturn those results and
does not establish RDAO v2 superiority, an improved decision rule, or
generalization.

## Decision hypothesis and controlled next test

**Hypothesis:** The harmful part of step-3 timing may be *the immediate
choice of a different A* action*, rather than acquiring the seven
new cells. This is not yet shown by the 2x2 observation test.

A follow-up [safe prior-action gate experiment](../scripts/evaluate_rdao_safe_prior_action_gate.py)
keeps the original step-3 authorized sensor reading and updates RDAO
memory normally. For the immediately subsequent G1 policy call only,
it also computes the **original default G1 action on the pre-observation
map**, with the same currently observed pedestrian/static context.
It chooses that old action only if:

1. The previously recommended action is exactly one forward translation.
2. The destination has been explicitly observed free in the new memory.
3. The old action does not conflict with public blocked-action feedback.
4. The swept G1 footprint is clear of observed occupied cells in the
   UPDATED map (no hidden geometry; only the observed ternary memory).
5. The revised planner would otherwise choose a different first action.

The original independently timed emergency sensor, emergency
intervention policy and actual-model collision shield still process
the **selected** action normally. No unselected-action shield is
invoked. No historical code or results are changed. This is an
*experimentally imposed one-step route-inertia diagnostic*, not a
deployment-ready rule and not a recommendation to disregard obstacles.

If preserving the safe westward step with the real Step 3 observation
rescues M, it will demonstrate that the immediate planner reaction
can be causally important, *even with the same sensor information
available*. If it does not, the observation's downstream memory and
scheduler effects and/or subsequent observation viewpoint remain
important candidates.

## Local commands

~~~sh
git pull --ff-only origin phase2/mujoco-proxy-pilot
.venv/bin/python -m pytest tests/test_rdao_safe_prior_action_gate.py -q
.venv/bin/python scripts/evaluate_rdao_safe_prior_action_gate.py \
  --world M:80030010
~~~

Then a negative-world comparison:

~~~sh
.venv/bin/python scripts/evaluate_rdao_safe_prior_action_gate.py \
  --world R:80000018 \
  --output results/phase2_mujoco/rdao_v1_safe_prior_action_gate_R80000018
~~~

The runner reproduces the exact frozen RDAO baseline, compares all
pre-intervention behavior, validates memory-update counts, preserves
the 20-observation cap and public selected-action shield contract,
verifies all 836 protected Phase 1.5 source artifacts and frozen
primary evidence, and writes a new CSV, JSON and compressed full trace
without overwriting existing results.

**Execution status:** These new tests and experimental replay have NOT
yet been run in the local pinned MuJoCo environment. A subsequent
gated result is needed before deciding whether route inertia is a
plausible component of RDAO v2.

## What RDAO v2 would need, if gate works

- Online-only decision signals, not known-good intervention times.
- Better route stability/consistency and observation impact
  estimation, specifically distinguishing actionable new obstacles
  from observations that merely trigger unnecessary local detours.
- Safe, fresh occupancy integration with no blind path continuation,
  robust pedestrian timing and independent emergency overrides.
- A computationally cheap trigger/prefilter rather than expensive
  two-A* per candidate region at every step.
- Hold-out protocols and dose-matched Periodic/Age comparison before
  claiming improvement.

A route-stability method and a sensor-value method must be tested
separately; these diagnostic outcomes alone establish neither one.
