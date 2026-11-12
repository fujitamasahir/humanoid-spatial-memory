# RDAO v1 online-safe route gate: full 72-episode paired screen and failure analysis

**Status:** Completed development screen; not held out, not evidence of
improvement over Periodic/Age, and **do not yet promote as RDAO v2**.
Date: November 12, 2026.

## Reproducibility

Read from the committed, source-hash-recorded Phase 2 primary RDAO
evidence and these committed artifacts:

- results/phase2_mujoco/rdao_v1_online_safe_gate_fit72_screen_v1/summary.json
- results/phase2_mujoco/rdao_v1_online_safe_gate_fit72_screen_v1/paired_online_gate.csv
- results/phase2_mujoco/rdao_v1_online_safe_gate_fit72_screen_v1/online_gate_traces.jsonl.gz

The original 36 fit worlds each have two related pedestrian schedules
(72 episodes, seed 42). The maximum is 20 authorized memory observations
and horizon 80 steps; independent Emergency Safety and selected-action
actual-geometry collision shields remain unchanged. Zero unwanted
contacts were observed in this development screen.

Only the per-episode CSV and aggregate summary were directly inspected
for the calculations in this report. The uploaded compressed 72-case
screen trace is larger than the remote file-content retrieval limit,
so detailed causal claims about its complete step-by-step action paths
are deliberately not made here. A new READ-ONLY LOCAL forensic analyzer
below performs that verification without MuJoCo reruns.

## Results, without glossing over failure cases

| Metric | Frozen RDAO v1 | Gate first | Gate every |
|---|---:|---:|---:|
| Goal completions | 57/72 | 61/72 | 58/72 |
| Development completion rate | 79.17% | 84.72% | 80.56% |
| Previously failed episodes rescued | — | 4 | 2 |
| Previously successful episodes harmed | — | 0 | 1 |
| Mean memory observations | 9.1111 | 8.8194 | 8.5833 |
| Mean horizon-censored steps | 44.7361 | 44.2639 | 44.6528 |
| Mean traveled distance, m | 24.4896 | 24.4583 | 24.6563 |
| Total unwanted contacts | 0 | 0 | 0 |
| Episodes with a gate override | — | 34 | 34 |
| Total override decisions | — | 34 | 73 |
| Gate evaluation ms per episode, inclusive of ordinary G1 planner work | — | 8.14 | 8.71 |

Periodic and Age both reached **66/72** goals in the frozen fit
comparison; the new gated variants do not match them. The reported
gate evaluation time is a contextual profile, not a clean measurement
of incremental CPU overhead: it includes the newly computed default
G1 planning operation and is hardware/timing-dependent.

### Correct paired breakdown: first

The 4 rescued episodes arise from ONLY **two distinct worlds**,
with both correlated schedules displaying the same effect:

| Fit world | Original | First | Delta observations | Delta distance |
|---|---|---|---:|---:|
| M:80030010 (both schedules) | Failed by 80 | Reached at 28 | -14 per schedule | -26.25 m per schedule |
| M:80030009 (both schedules) | Failed by 80 | Reached at 78 | +3 per schedule | +1.50 m per schedule |

The M:80030009 result is especially **horizon sensitive**: it
arrived only two actions before the 80-step cap, used more
observations, and traveled farther than the baseline's censored path.

For the **57 episodes that reached their goals under both original
RDAO and first**, paired comparison found:

| Measure | Improved | Unchanged | Worsened |
|---|---:|---:|---:|
| Executed steps | 0 | 43 | 14 |
| Traveled distance | 0 | 43 | 14 |
| Memory observations | 0 | 52 | 5 |

These common-success episodes accumulate **+74 steps, +48.0 m,
+7 observations** under first. R:80000022 alone increases by
**+22 steps, +13.5 m, and +2 observations per schedule**, even
though both runs still reach their goals.

Decomposing the apparently favorable average step change for first:

- Rescued episodes: -108 total horizon-censored steps.
- All 57 common successes: +74 total steps.
- The 11 episodes that still failed: 0 net change in censored steps.
- Thus the full 72-episode total is -34 steps or -0.4722
  per episode, principally due to a large benefit in one development
  world and extra delays in many previously successful cases.

The overall mean observation decrease (-0.2917 per episode) is
also affected by shorter episodes and is NOT proof of an improved
observation policy or a better observation rate per executed step.

### Why every is worse

Every rescues M:80030010 only (two correlated schedules). It fails
to rescue M:80030009, which first rescues. It additionally flips
M:80030000 schedule 1 from reaching at step 74 to **failing to
reach by step 80**. This is a horizon-censored loss of success,
not proof that the actual route would have required exactly 6
more steps if the horizon were extended.

Of the **56 episodes successful with both original and every**,
none improves its executed step count: 40 unchanged and 16 worse.
They accumulate **+92 steps and +61.5 m** compared with the
original. Repeated short-horizon action inertia can be costly,
even when each individual forward translation is publicly
observed-safe and is still inspected by the true selected-action
collision shield.

R:80000018 never reaches the goal with either gate, despite
both rules firing. Thus a successful local footprint check does
not imply that the action is beneficial to the global route.

## Interpretation

The controlled single-step intervention in M:80030010 establishes
that an overly reactive replanning response is a plausible local
causal failure mode: observe normally and update memory, but retain
one previously safe forward action, and the 80-step outcome is
rescued. This does NOT mean that step-3 sensor data are incorrect
or that the planning model should ignore newly detected obstacles.

The full online screening demonstrates that a broad safe-action
inertia heuristic is too coarse. **Near-term safety is not the
same as route efficiency or long-horizon task completion.**

These fit-world results were used to design the proposed gate.
Accordingly 61/72 is development screening, not an unbiased
performance estimate; no significance or superiority claim is
appropriate. Two schedules of a single maze are correlated
and should not be counted as independent world replications.

## Next: forensic trace inspection before another algorithm

The new stdlib-only read-only script:

- [scripts/analyze_rdao_online_safe_gate_failures.py](../scripts/analyze_rdao_online_safe_gate_failures.py)
- [tests/test_rdao_online_gate_failures_analysis.py](../tests/test_rdao_online_gate_failures_analysis.py)

reads the saved CSV, saved compressed first/every traces, and frozen
original RDAO traces. It does **not** run MuJoCo or touch held-out
worlds. It checks frozen input SHA256 hashes and focuses on:

1. **M:80030009:** Why first's one override at step 26 yields
   marginal arrival but every loses that rescue.
2. **M:80030010:** Why first and every converge to the same
   successful path despite different ongoing gate opportunities.
3. **M:80030000:** Why every destroys a formerly successful
   schedule while first does not.
4. **R:80000022:** Why just one first override adds 22 steps
   and 13.5 m per schedule.
5. **R:80000018:** Why an early gate fails to rescue the route.

The script outputs a focus per-episode table, every authorized
gate event with its guard and proposed action, and aligned
baseline-vs-gate action/position/sensing timelines.

Execute locally:

~~~sh
git pull --ff-only origin phase2/mujoco-proxy-pilot
.venv/bin/python -m pytest tests/test_rdao_online_gate_failures_analysis.py -q
.venv/bin/python scripts/analyze_rdao_online_safe_gate_failures.py
~~~

After these files are saved and committed, compare precisely the
FIRST divergence between first and every and the specific later
overrides causing harm. No new MuJoCo rollout is needed.

## Design decision gate after forensics

A broadly applied first-action inertia heuristic should NOT be
promoted to RDAO v2 from these results. A successful future rule
must use only information available at decision time and distinguish
when an old safe forward move is tactically beneficial from when it
is merely a long detour. Possible design principles include
observed-route compatibility, local path progress and prospective
viewpoint value, with a strict fail-closed safety gate and low
compute overhead; these are *hypotheses*, not validated rules.

Freeze candidates and evaluation criteria on development data,
then test on an independently protected held-out suite. Do not
open held-out data just to tune the gate. Evaluate not just
successes but matched-pair steps and distance among baseline
successes, observation dose, latency, and all safety regressions.
