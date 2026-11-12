# RDAO v1 safe post-observation action gate: causal finding and 72-episode protocol

**Status:** exploratory Phase 2 development, NOT a proven RDAO v2 improvement.
**Evidence:** committed 72-episode frozen RDAO primary matrix and two selected-world safe-gate pilot results including compressed step-level traces.

## Verified experiment outcomes

The safe prior-action gate leaves the ordinary authorized spatial-memory
observation at step 3, including the resulting memory update, intact.
It permits the previous forward first action for *one step* only when
the newly observed target is free, the swept public G1 footprint is clear
of remembered occupied cells, and blocked-action feedback permits it.
The independent emergency sensor/controller and selected-action actual
collision shield are unchanged.

Each line below occurred for both pedestrian schedules; these are two
distinct WORLD identities, not four independent worlds.

| World | Original | Gate | Original steps | Gate steps | Observations original/gate | Distance original/gate (m) | Contacts |
|---|---|---|---:|---:|---|---|---|
| M:80030010 | failed | reached | 80 censored | 28 | 20 / 6 | 41.25 / 15.00 | 0 / 0 |
| R:80000018 | failed | failed | 80 censored | 80 censored | 13 / 13 | 43.50 / 43.50 | 0 / 0 |

The public-map guard was triggered and the override applied for both
schedules in BOTH worlds. For M at step 3, seven newly changed memory
cells made the normal G1 policy choose a northward turn instead of its
earlier westward forward step to (7,8). With the same observed cells
in memory, the gate preserved that earlier forward step, and the
episode reached its goal by step 28 with no unwanted contacts. This
isolates an important role of **how observed data are converted to
immediate actions**, rather than missing observation alone.

For R, a safe forward action to (14,13) instead of a turn was allowed;
it changed the immediate action but did not improve the horizon-80
outcome. Therefore, merely satisfying public safe-forward conditions
does NOT establish that a gate helps the global route.

Even for M, the reduced total observations are mainly a shorter
trajectory effect: 6/28 observations per executed step vs 20/80 in
the original. The per-step rate did not improve.

## World-agnostic development-only screening design

A new candidate-screening runner:
[scripts/evaluate_rdao_online_safe_gate_screen.py](../scripts/evaluate_rdao_online_safe_gate_screen.py)

Fast unit tests:
[tests/test_rdao_online_safe_gate_screen.py](../tests/test_rdao_online_safe_gate_screen.py)

Rather than invoking a gate at a hand-picked step 3, the new rule is
evaluated at every **naturally granted** RDAO observation on all
36 admitted fit worlds and their two schedules, without a fixed
trigger step, world identity, hidden occupancy, evaluators, success
flags, future data, or unselected action collision queries.

Rule:
1. After an authorized real sensor observation, compare the
   immediately pre-refresh and post-refresh observed ternary maps.
2. If map content changed and the updated default G1 action is a
   TURN, compute the old default G1 policy's action on the
   pre-refresh memory, using the SAME current observed pedestrian
   and static feedback context.
3. Override the new TURN only if the old action is one FORWARD move,
   its target is explicitly observed free after update, the swept
   footprint clears all occupied cells in the updated observed map,
   and the action is not prohibited by attempted-action feedback.
4. Run the existing independent Emergency Safety controller and
   actual-model collision shield on the selected action as usual.

Two predeclared variants:
- first: gate at most one qualifying observation per episode.
- every: gate every qualifying observation event.

The aim is to TEST a hypothesis rather than claim that this
simple rule is already good. Gate-overridden actions can be harmful
to long-term navigation even if immediately observed-safe.
Compute overhead is not free: the old default G1 plan must be
evaluated on some post-observation steps.

The runner reproduces and verifies every original episode against
frozen metrics and complete saved action/pose/observation/contact
trace, checks the 836-file Phase 1.5 preservation evidence, and
writes full traces and paired outcomes in new directories only.
Records must include both rescued failures and newly harmed
successes, unwanted contacts, total observations, arrival and
horizon-censored steps, traveled distance and runtime costs.

## Local commands

Run fast tests:

~~~sh
git pull --ff-only origin phase2/mujoco-proxy-pilot
.venv/bin/python -m pytest tests/test_rdao_online_safe_gate_screen.py -q
~~~

Targeted pilots, one world (both schedules) each:

~~~sh
.venv/bin/python scripts/evaluate_rdao_online_safe_gate_screen.py \
  --world M:80030010 --policies both \
  --output results/phase2_mujoco/rdao_v1_online_gate_M80030010_pilot

.venv/bin/python scripts/evaluate_rdao_online_safe_gate_screen.py \
  --world R:80000018 --policies both \
  --output results/phase2_mujoco/rdao_v1_online_gate_R80000018_pilot
~~~

If both run and preserve baseline fidelity, the full 72 fit episodes:

~~~sh
.venv/bin/python scripts/evaluate_rdao_online_safe_gate_screen.py \
  --policies both
~~~

No local MuJoCo execution has been performed in the authoring
environment. Do NOT claim held-out or real humanoid walking results.
The frozen baselines remain RDAO 57/72, Periodic 66/72 and Age
66/72 successes; direct paired comparisons and matched observation
dose must be considered before selecting an RDAO v2 design.

## Decision gate

- Any new unwanted contacts or substantial regression from formerly
  successful episodes requires redesign; do not promote the rule.
- Evaluate per-world, not only per-schedule; the two schedules are
  correlated and do not constitute independent proof.
- If fit results are promising, preregister an adjusted rule and
  compare on genuinely held-out worlds without tuning.
- Keep the opportunity and action gate hypotheses separate from the
  intrinsic quality of the observed sensor data. Evidence for a
  route-inertia effect does not show that the step-3 observation was
  erroneous or should always be skipped.
