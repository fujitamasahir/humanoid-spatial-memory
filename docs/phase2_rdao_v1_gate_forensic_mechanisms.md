# RDAO v1 online safe-gate: five-world forensic mechanisms and follow-up ablation

**Status:** Detailed forensic results verified from committed CSV; gate-step
counterfactuals NOT YET RUN. These are development-world, retrospective
diagnostics and do not imply a deployable online RDAO v2 policy.

## Evidence

The committed artifacts in
results/phase2_mujoco/rdao_v1_online_safe_gate_forensics_v1
contain: focus_episode_comparison.csv, focus_gate_events.csv,
focus_action_timeline.csv and summary.json.

These derived outputs were compared at the per-step action and pose
level, not only the summary success counts. Baselines are the saved
original Phase 2 RDAO v1 runs, not new environment configurations.
The two pedestrian schedules remain correlated repetitions of one
world, not independent maze samples.

## Exact first action divergence and causal hypotheses

### R:80000022: severe detour despite one safe gate

In both schedules the frozen original RDAO succeeded in 55 steps,
31.5 m. The online first gate succeeded in 77 steps, 45.0 m:
**+22 steps and +13.5 m**, with no unwanted contact.

At Step 20 (original location [5,5]), a normal authorized
observation changed 31 remembered cells. The default G1 planner
would turn north (index 3). The gate instead allowed westward
forward travel to [4,5] because the updated observed footprint
was clear. Subsequent gated actions turn twice, then return
eastward to [5,5] at step 23; original RDAO has already reached
[7,5] at the same step. This provides a concrete example of
a physically safe but tactically wasteful immediate action.

However, returning to the previous cell after three steps
CANNOT itself be used as a reliable automatic rejection rule:
the successfully rescued M:80030010 ALSO returns to the initial
position by Step 6 after its Step-3 gate. Future observation
viewpoint, route choice and pose matter.

### M:80030009: later gate overrides potentially cancel rescue

Both schedules: baseline fails by horizon80; online first
(with ONE gate at step26) succeeds at Step78, with +3
observations and +1.5 m compared with the original censored
trajectory. The online every policy fires at steps26, 50, 55
(schedule0), then fails by horizon80.

The step26 gate at [21,16] retains a move to [20,16] in place
of a turn. The first and every variants share their executed
trajectory up to step49; they FIRST DIVERGE at step50 when every
keeps the prior move from [10,18] to [10,17] rather than turn.
At step55 every overrides another turn to move [10,14] -> [11,14].
It returns to [10,14] by step58. The available comparison
identifies the combination of later overrides as suspicious,
but does NOT independently establish whether step50 or step55
is responsible for the final failure.

### M:80030000: repeated gate turns a success into failure

Schedule1: original RDAO reaches in 74 steps; online first
gates at step13 and still reaches in 78 steps; every gates at
steps13,17,50 but fails to reach by horizon80. The first
and every policies FIRST DIVERGE at step17. In every,
the robot moves from [14,8] to [13,8] despite an updated
planner turn request; after subsequent turns it returns to
[14,8] at step20. The extra step50 gate may also matter.
Step17 alone is not yet proven to be the sole cause.

Schedule0 in the same world starts with first/every gate
at step37 and remains a failure under either condition;
the correlation within a world should not be ignored.

### M:80030010: genuine but narrow positive control

Both schedules: only one online gate (step3). The actual
authorized observation changes seven memory cells, the
original new plan says turn north, and the gate takes one
observed-safe west step from [8,8] to [7,8]. Despite
returning to [8,8] by step6, the gated episode completes
at step28 instead of failing at horizon80. This shows
that **immediate reversal alone is not a sufficient predictor
of harmfulness**.

### R:80000018: safe gate does not solve all failed paths

Both schedules: first and every remain unsuccessful at
horizon80. In schedule0 the first gate is step3, while every
allows further overrides at 22,42,63. The same terminal
success status is not evidence that all those interventions
were neutral in path quality; the distance and observations
also must be considered.

## Why the gate is not yet a viable v2 policy

The 72-episode online fit screen found:

- first: 57/72 -> 61/72 successes, 4 rescued (2 maze identities),
  0 success-to-failure flips, zero unwanted contacts.
- every: 57/72 -> 58/72 successes, 2 rescued (1 maze identity),
  1 success-to-failure flip, zero unwanted contacts.
- Among 57 episodes successful under both original and first,
  0 shortened, 43 unchanged, 14 lengthened (+74 steps and +48 m total).
- Most of the improvement in horizon-censored average steps is driven
  by the dramatic rescue of M:80030010, not broad gains across mazes.
- Periodic and Age still outperform the online gate on raw
  development completion count: 66/72 each.

A safety-valid continuation action is not necessarily globally
beneficial. The next question is not simply whether observations
are useful, but under which conditions the planner should accept
or delay a new route decision after a real observation.

## Next diagnostic: isolate additional overrides

A new exact-baseline-verified [gate step ablation
runner](../scripts/evaluate_rdao_gate_step_ablation.py) adds
an **optional allowlist ONLY for retrospective experiments**
to the existing [online screen runner](../scripts/evaluate_rdao_online_safe_gate_screen.py).
The original online first/every default (no allowlist)
remains unchanged. An allowed gate still passes all original
observed-memory footprint, forward step, blocked action and
independent selected-action collision checks.

For each saved world/schedule, candidate gate steps are taken
from the COMMITTED every-policy trace (not generated new
environments). This is an outcome-guided causal diagnostic,
not an online rule. It compares:

- none: suppress all gate overrides (original RDAO);
- first: allow only the first saved gate step (reproduce first);
- first_second: allow the first TWO saved override steps;
- first_third: allow the first and third saved override steps;
- all: allow all saved every-policy steps (reproduce every).

The runner independently reproduces and validates the frozen
baseline, existing online first/every outcomes, and exact every
gate-step sequence before accepting the new intervention results.
It also checks all protected Phase1.5 artifact hashes, existing
source hashes, 20-observation cap, selected-only collision shield,
and absence of unwanted contacts. Results are written into a new
directory, never replacing existing data.

**Critical identification caveat:** After suppressing an earlier
gate, the robot's future trajectory and natural observations may
change, causing later saved gate steps NOT to be eligible. For
example, first_third cannot automatically be interpreted as
isolating a fixed third event if the event never occurs on that
counterfactual route. Record ACTUAL applied override steps and
interpret only interventions that occurred.

### Local run commands

~~~sh
git pull --ff-only origin phase2/mujoco-proxy-pilot
.venv/bin/python -m pytest tests/test_rdao_gate_step_ablation.py -q
.venv/bin/python scripts/evaluate_rdao_gate_step_ablation.py \
  --world M:80030009 \
  --output results/phase2_mujoco/rdao_v1_gate_ablation_M80030009
.venv/bin/python scripts/evaluate_rdao_gate_step_ablation.py \
  --world M:80030000 \
  --output results/phase2_mujoco/rdao_v1_gate_ablation_M80030000
~~~

Then explore the detour case, if helpful:

~~~sh
.venv/bin/python scripts/evaluate_rdao_gate_step_ablation.py \
  --world R:80000022 \
  --output results/phase2_mujoco/rdao_v1_gate_ablation_R80000022
~~~

The runner outputs step_ablation_comparison.csv, a full gzipped
trace, and summary.json. The code/tests are committed but **have
not been executed with local pinned MuJoCo in this authoring turn**.

The five-world fact pattern supplies sufficient grounds for
further diagnosis, NOT for adapting gate thresholds from known
outcomes and calling that a validated RDAO v2. Any learned
online rule must subsequently undergo independent held-out
evaluation, including episode-level path quality and matched
observation-dose controls.
