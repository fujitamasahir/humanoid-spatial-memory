# Phase 2 RDAO v1: second-gate causal ablation and observed-route mechanisms

**Date:** 2026-11-12.
**Status:** two selected development-world counterfactuals completed and verified
from committed CSV and compressed full traces; NO held-out evaluation.
One deterministic world is repeated under two correlated schedules.

## Compared gate-step ablations

Reference files:
- results/phase2_mujoco/rdao_v1_gate_ablation_M80030009/step_ablation_comparison.csv
- results/phase2_mujoco/rdao_v1_gate_ablation_M80030009/step_ablation_traces.jsonl.gz
- results/phase2_mujoco/rdao_v1_gate_ablation_M80030000/step_ablation_comparison.csv
- results/phase2_mujoco/rdao_v1_gate_ablation_M80030000/step_ablation_traces.jsonl.gz

M:80030009, BOTH schedules identical:

| Allowed override steps | Actually applied | Reached within 80? | Executed steps | Observations | Distance |
|---|---|---|---:|---:|---:|
| none | none | no | 80 censored | 14 | 36.75 m |
| 26 | 26 | yes | 78 | 17 | 38.25 m |
| 26, 50 | 26,50 | no | 80 censored | 15 | 39.75 m |
| 26, 55 | 26 only | yes | 78 | 17 | 38.25 m |
| 26,50,55 | all 3 | no | 80 censored | 13 | 39.75 m |

In the counterfactual conditioned on the Step-26 gate, *enabling*
the Step-50 gate suffices to change a Step-78 completion into
noncompletion by 80. Step 55 is not necessary for this observed
loss. The [26,55] experiment did NOT actually fire at 55; it
cannot identify Step-55's independent effect.

M:80030000, SCHEDULE 1 only (schedule0 remains a failure under
all reported variants):

| Allowed override steps | Actually applied | Reached within 80? | Executed steps | Observations | Distance |
|---|---|---|---:|---:|---:|
| none | none | yes | 74 | 17 | 41.25 m |
| 13 | 13 | yes | 78 | 18 | 42.75 m |
| 13,17 | 13,17 | no | 80 censored | 18 | 42.75 m |
| 13,50 | 13 only | yes | 78 | 18 | 42.75 m |
| 13,17,50 | all 3 | no | 80 censored | 18 | 42.75 m |

Conditioned on the Step-13 gate, enabling Step 17 suffices to
change arrival from 78 to noncompletion by 80; Step 50 is not
necessary. In the [13,50] counterfactual, the Step-50 gate
did NOT fire, so this is not proof that Step 50 is harmless.

All these interventions retain natural authorized observations,
observed-map update, max-20 memory observation budget and the
independent emergency/selected-action collision safety checks.
Zero unwanted contacts occurred in these runs.

## Newly verified observation-map evidence

The compressed traces preserve each RDAO nominal A* route before
and after an observation and its **observed ternary memory**,
including sensor-updated occupied cells. The following facts
were read directly from those traces. The nominal RDAO A* is
not necessarily the same as the evaluator's executed G1
forward-first/pedestrian-aware policy.

### M:80030009 Step 26: one useful gate despite newly revealed blocker

Pre-observation nominal route: first move [20,16], then [19,16].
Observation reveals **[19,16]: unknown (-1) -> occupied (1)**.
Nominal route cost changes **21.25 -> 24.25**.

The single gated first move to [20,16] is observed-safe.
In the gate run, the next action turns south and the robot
then proceeds via [20,17], [20,18]. Thus keeping the first
move does not entail continuing into [19,16]; the move changes
the reachable subsequent branch/viewpoint and rescues the
episode, but only at Step 78, with MORE observations and
distance than the censored original path.

### M:80030009 Step 50: harmful gate enters obsolete north corridor

With the Step-26 gate already in force, the robot is at
[10,18]. The original unrefreshed nominal route first goes
[10,17] -> [10,16] -> [10,15] -> [10,14] -> [10,13].
The authorized observation identifies **[10,13]: unknown -> occupied**,
while the immediate target [10,17] remains free.
The nominal cost changes **12.25 -> 16.75**.
New nominal route first action is a turn west (index2),
with a route via [9,18], [8,18], [7,18], [6,18].

Without the Step-50 gate, the robot adopts that new western
route and completes by Step78. With the Step-50 gate,
the robot follows the northern corridor as far as [10,14],
then turns and walks back to [10,18] by Step59. This
identifies a *longer-horizon wasteful segment*, not an
immediate collision or incorrect observation.

### M:80030000 Step 17: harmful gate enters a short rejected branch

After the Step-13 gate, at [14,8], the old nominal route
would start [13,8], [12,8], turn south, then [12,9].
The new observation identifies **[12,9]: unknown -> occupied**,
with the first action target [13,8] still free.
The cost changes **17.50 -> 18.00**.
The updated nominal policy turns south instead.

When Gate17 is allowed, the robot goes [14,8] -> [13,8],
then turns twice and returns to [14,8] by Step20.
This is a local detour; subsequently the run does not
reach by Step80. The no-second-gate condition reaches
in 78 steps.

### M:80030000 Step 13: FIRST gate was already inefficient

An observed obstacle **[17,8]: unknown -> occupied** lies
along the old eastward nominal route. Cost changes
**13.25 -> 18.00**. A single Step-13 gate moves to
[15,8], but the robot then turns twice and returns
to [14,8] by Step16. The already-successful original
74-step route becomes a 78-step success.

### Why a trivial blocker or return veto does not work

Both the BENEFICIAL Step-26 gate in M:80030009 and
the HARMFUL Step-50 and Step-17 gates have occupied
cells newly revealed farther down their former route.
The beneficial Step26 gate reaches a newly discovered
blocker after only the SECOND planned translation;
the harmful Step50 gate's blocker is after the FIFTH.
Thus "reject if old route meets a new obstacle soon"
can paradoxically reject the positive case first.

The successful M:80030010 Step3 gate also returns
to its pre-gate position by Step6, so "reject if it
would return to the origin within 3 steps" is not a
valid online rule and would improperly require future
knowledge anyway.

**Mechanism hypothesis:** The value of a short forward
commitment may depend on the route alternatives
available *from the new pose*, not just whether the
next 1 cell is free and not just nominal old-route
A* cost. This remains a hypothesis. A corridor may
be safe to enter but expensive to reverse out of.

## Next measurement before any new algorithm

A [read-only gate feature extractor](../scripts/analyze_rdao_gate_route_features.py)
and [fast tests](../tests/test_rdao_gate_route_features.py)
were added. They use the frozen ONLINE FIRST/EVERY
development traces and compute across all 107 applied
override events (34 first, 73 every):

- Old nominal A* route's FIRST now-known occupied
  cell, counted by translation index rather than turns.
- Nominal route cost change before/after sensor update.
- Already observed free and UNKNOWN branch neighbors
  at the first gated destination (excluding return cell).
- Number of newly detected occupied/free cells.
- Gate proposed action versus actual selected action.
- Observed returns to the starting cell within six
  steps, explicitly POST-HOC and not an allowed input
  to an online decision.
- Episode outcome transition, reported as an association
  (NOT a causal label for any single gate when >1 applied).

These measurements test whether there is a plausible
decision-time differentiator for a conservative gate.
They are exploratory, not automatically fitted
thresholds, since this fit cohort has been inspected
repeatedly.

~~~sh
git pull --ff-only origin phase2/mujoco-proxy-pilot
.venv/bin/python -m pytest tests/test_rdao_gate_route_features.py -q
.venv/bin/python scripts/analyze_rdao_gate_route_features.py
~~~

No MuJoCo or new world evaluation is required for this
read-only analysis. The script writes a separate CSV and
summary JSON without overwriting prior experiments.

**Important:** The authoring environment has NOT run the
new analysis or its local tests. Interpret measurements
only after the saved run succeeds.

## Research decision

Do not label the current first/every gate RDAO v2:
although first increases completion from 57/72 to
61/72 in development data, it lengthens 14 of 57
originally successful episodes and never shortens a
paired success. Periodic and Age each remain 66/72
on these development worlds.

A next deployable rule should be defined from only
decision-time public observed memory, actual selected
action feedback, and public pose/goal, with an explicit
budget for one-step counterfactual planning and strict
safety invariants. Freeze an online criterion before
using independently reserved held-out scenarios.
