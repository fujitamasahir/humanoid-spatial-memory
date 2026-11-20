# Route-aware Age v1: frozen descriptive development protocol

Base commit: 3e381a8d32a966a02f697020e063e35c1098855d.
Age-View-Veto reached 63/72 with 10.708 paid scans versus Age 66/72 with
11.806; it rescued one case and harmed four. Age-View-Clock reached 61/72.
In the harmed pair R:80000000 schedule 1, three more scans did not restore
completion; both R:80000018 schedules had two fewer scans. M:80030000
schedule 1 had the same scan count. Counts alone do not establish causality.
No maze identity, saved success label, or true geometry enters the policy.

## Hypothesis and frozen variants

The directional veto can suppress an Age request despite a stale or unknown
cell on the immediate public path. Augment rather than replace that veto.
Let A be the original Age request, V the frozen Age-View-Veto decision, and
R a nonempty set of due route cells. Obtain the nominal point-grid A* path
from the public ternary memory using the actual configured unknown rule.
Consider the next age_steps moves, clipped to the original Age radius and
the current predicted 61-ray visible footprint. Include direct path cells
and remembered occupied cardinal neighbors of the path prefix. A candidate
is due if never observed or at least age_steps old. The neighbor feature is
only a proxy for clearance/alternative routes, not physical G1 traversability.
Never count the robot's current cell. Let N indicate no public point path
when not at the goal.

* age_route_rescue: V OR (A AND (R OR N)).
* age_route_clock: the above OR (R AND time since latest observed cell
  >= ceil(age_steps/2), at least one step).

The original cap is applied afterward. The first variant is a superset of
View-Veto and subset of Age at an identical eligible state; the second can
request before Age. These inclusions do not imply episode-wise count ordering.
The half-interval cooldown is a prospective design choice to distinguish
the proactive arm, not fitted to episode outcomes. The original radius,
age thresholds, fallback, ternary last-write memory, G1 planner, actual
paid and independent emergency sensors, selected-only shield, seeds and
initial-inclusive cap20 are unchanged. No counterfactual plans beyond the
one nominal point A* for this scheduler, no physical sensor query in
scoring. For frozen V parity this version makes two predicted footprint
computations per scored decision; measure the cost rather than assuming it
is free. Latest observed timestamp approximates latest nonempty scan.

## Evaluation

Use the five arms Periodic, Age, frozen Age-View-Veto, age_route_rescue and
age_route_clock. The old FIT72 cohort is reused and is not independent.
Unit/fixture correctness and old integration tests gate the two-key smoke
(10 episodes) and then the full 72-key matrix (360 episodes) once. No
numerical synthetic efficacy gate is claimed. Require exact baseline and
View-Veto metric/semantic trace parity, exact smoke parity, actual paid
sensor count verification, zero extra shield calls and cap20. The original
data and prior manifest are verified read-only. Preserve all output on
failure. A safe smoke does not imply general physical safety.

Report per-arm results and paired comparisons against all three references:
goals, rescues/harms, paid/actual emergency rays, combined rays, H80 steps,
paired common-success steps and distance, contacts, blocked actions, memory
errors and compute. Baseline scheduler times are not instrumented here;
zero is explicitly a placeholder, not a measured runtime. Main target:
zero unwanted contacts and >66/72 goals OR 66/72 with <11.111... mean paid
scans, compared with both baselines. Also examine whether total sensing and
navigation costs improve jointly; a higher success rate with higher cost
is a tradeoff. Two schedules per maze are correlated. No independence or
statistical superiority claim.

Do not retune on these outcomes or modify any old result. Subsequent
hypotheses must be separately versioned; independent cohort creation and
restricted populations remain unapproved. New exclusive result root:
results/phase2_mujoco/age_route_v1.

## Commands

    .venv/bin/python scripts/run_age_route_fit72.py check
    .venv/bin/python scripts/run_age_route_fit72.py smoke
    .venv/bin/python scripts/run_age_route_fit72.py full
    .venv/bin/python scripts/run_age_route_fit72.py report

Local tests and actual MuJoCo runs are pending.
