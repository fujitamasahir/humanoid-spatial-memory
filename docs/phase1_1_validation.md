# Phase 1.1 experimental validity validation

Executed on Windows, Python 3.12.10, 2026-11-06. macOS compatibility is intended
but has not been tested. No reserved held-out configuration was changed or run.
No baseline algorithm, planner, observation model or refresh interval was changed.
No new memory algorithm, RL, MuJoCo or Unitree G1 work is included. Stop for research review.

## Exact reproduction commands

Run from the repository root in Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/run_experiment.py --config configs/development.json --output results/phase1_1/diagnostic --budgets 24 30 40 60 --no-figures
.\.venv\Scripts\python.exe scripts/run_experiment.py --config configs/development_phase1_1.json --output results/phase1_1/development
```

For a fresh Python 3.12 environment, install `requirements.txt` first. On macOS,
use `.venv/bin/python` in the commands above (unverified). Reproduction overwrites
only the Phase 1.1 output directories; use new directories to retain repeated runs.
The runner rejects the existing original representative directory and all held-out
execution. CSV and JSON contain every requested episode metric; JSON additionally
stores realized scenario schedules/hashes, compact per-step traces, full configs,
source/config SHA-256, Git state, platform and installed dependency versions.
Generation shares the same realized Scenario instance across methods and budgets.
Environment randomness has its own stream; it is independent of sensing schedules.

## Checks and artifact preservation

Full suite: **29 passed**, 14 Matplotlib/pyparsing dependency deprecation warnings.
`pip check`: no broken requirements. Tests cover seeded repeatability, equal
underlying truth and initial observations across methods, diversity across the
three selected development seeds and a 20-seed generator check, variation of dwell
and placement, alternative route availability, blocked attempts, newly entering
persistent/pedestrian contacts, continuing overlap, successful distance, sample
sums versus final errors, and runner protections. Original 17 tests still pass.
Baseline memory, navigation and sensor source files are unchanged. The original
`configs/development.json`, `configs/held_out.json`, representative outputs and
`docs/phase1_validation.md` remain unchanged. Preservation is checked with Git diff.

## Original-layout diagnostic sweep

Three seeds (7,19,31) repeat identical noise-free environments here; they are not
three independent environmental samples. Each table row applies to all three.
No original 24-step output was overwritten. Dynamic contacts were zero throughout.

| Budget | Static success | Static steps/distance/blocked | Periodic success | Periodic steps/distance/blocked |
| --- | --- | --- | --- | --- |
| 24 | no | 24 / 1 / 23 | no | 24 / 19 / 5 |
| 30 | no | 30 / 1 / 29 | yes | 25 / 20 / 5 |
| 40 | no | 40 / 1 / 39 | yes | 25 / 20 / 5 |
| 60 | no | 60 / 1 / 59 | yes | 25 / 20 / 5 |

Static initially remembers a pedestrian at (3,3), moves to (2,3), then repeatedly
requests (2,2), an actual wall hidden from its initial sensor view. Frozen memory,
optimistic unknown-cell traversal, deterministic A* and no map correction on
blocked attempts yield the same failed action forever. More budget cannot resolve
this. The initial pedestrian entry remains stale after departure; the baseline has
no way to discover that the direct route has cleared. This is intentional baseline
behavior, not a movement checker bug. It must not be silently repaired for performance.

Periodic reaches (8,3) at step 24 and (9,3) at step 25: a deadline failure rather
than goal detection/off-by-one failure. At step 6 it enters (5,2), then the upper
y=1 passage, makes optimistic blocked attempts toward the wall at y=2, learns that
these exits are closed, backtracks to x=5 and returns through (5,3). The initial
change at (6,3) has cleared by then. Five blocked attempts plus 20 successful moves
consume 25 steps. **Correction to the preserved Phase 1 narrative:** the trace is
through the upper y=1 passage, not the lower y=5 passage described previously.
`diagnostic/results.json` includes next targets/positions for auditing this finding.
Increasing the budget is a diagnostic sensitivity check, not a replacement of the
original failed result or a selected success threshold.

## New development scenarios

Five hand-designed families, seeds 7/19/31, paired methods, 40-step budget chosen
as a development horizon; the original 24-step benchmark remains separately reported.
The empty control intentionally repeats across seeds. Other families vary hidden
conditions: crossing location/direction and dwell/wait durations, and/or persistent
addition location/time. Persistent additions remain through the horizon. Temporary
pedestrians revisit on cyclic paths; temporary means individual cell occupancy
clears, not that pedestrians leave the environment permanently.

- Empty: both 3/3; exactly 8 moves/steps with no blocked attempts or contacts.
- Temporary: both 3/3. Static seed 19 waits through two blocked attempts and travels
  8 cells; periodic takes 10-cell detours for all seeds. Refresh is not uniformly
  more efficient: static seed 7 travels directly in 8 steps.
- Persistent: static 0/3, repeatedly trying the newly occupied route cell;
  periodic 3/3 with 10-cell detours. Placement and appearance time vary by seed.
- Mixed: static 1/3, periodic 3/3. At seed 19 the persistent addition enters the
  robot cell for both methods: each records one dynamic contact. Static can then
  continue on the original route; success does not imply absence of contact.
- Alternative: static 0/3, periodic 3/3. The central 8-cell route is initially
  shortest; an added obstacle makes the upper bypass preferable to the longer
  lower detour around a fixed barrier. Periodic uses a 10-cell bypass. This family
  has different topology but duplicates the persistent family's measured outcomes;
  it is not independent evidence of an additional performance advantage.

### Per-episode task metrics

S=static, P=periodic; distance is successful unit movement. Observation cost includes
initial sensing. Blocked attempts are not physical collisions.

| Scenario | Seed | Method | Success | Steps | Distance | Blocked | Dynamic contacts | Observations | Cost |
| --- | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| empty | 7 | static | True | 8 | 8 | 0 | 0 | 1 | 1.5 |
| empty | 7 | periodic | True | 8 | 8 | 0 | 0 | 5 | 7.5 |
| empty | 19 | static | True | 8 | 8 | 0 | 0 | 1 | 1.5 |
| empty | 19 | periodic | True | 8 | 8 | 0 | 0 | 5 | 7.5 |
| empty | 31 | static | True | 8 | 8 | 0 | 0 | 1 | 1.5 |
| empty | 31 | periodic | True | 8 | 8 | 0 | 0 | 5 | 7.5 |
| temporary | 7 | static | True | 8 | 8 | 0 | 0 | 1 | 1.5 |
| temporary | 7 | periodic | True | 10 | 10 | 0 | 0 | 6 | 9.0 |
| temporary | 19 | static | True | 10 | 8 | 2 | 0 | 1 | 1.5 |
| temporary | 19 | periodic | True | 10 | 10 | 0 | 0 | 6 | 9.0 |
| temporary | 31 | static | True | 10 | 10 | 0 | 0 | 1 | 1.5 |
| temporary | 31 | periodic | True | 10 | 10 | 0 | 0 | 6 | 9.0 |
| persistent | 7 | static | False | 40 | 3 | 37 | 0 | 1 | 1.5 |
| persistent | 7 | periodic | True | 10 | 10 | 0 | 0 | 6 | 9.0 |
| persistent | 19 | static | False | 40 | 2 | 38 | 0 | 1 | 1.5 |
| persistent | 19 | periodic | True | 10 | 10 | 0 | 0 | 6 | 9.0 |
| persistent | 31 | static | False | 40 | 4 | 36 | 0 | 1 | 1.5 |
| persistent | 31 | periodic | True | 10 | 10 | 0 | 0 | 6 | 9.0 |
| mixed | 7 | static | False | 40 | 4 | 36 | 0 | 1 | 1.5 |
| mixed | 7 | periodic | True | 10 | 10 | 0 | 0 | 6 | 9.0 |
| mixed | 19 | static | True | 10 | 8 | 2 | 1 | 1 | 1.5 |
| mixed | 19 | periodic | True | 10 | 10 | 0 | 1 | 6 | 9.0 |
| mixed | 31 | static | False | 40 | 6 | 34 | 0 | 1 | 1.5 |
| mixed | 31 | periodic | True | 12 | 12 | 0 | 0 | 7 | 10.5 |
| alternative | 7 | static | False | 40 | 3 | 37 | 0 | 1 | 1.5 |
| alternative | 7 | periodic | True | 10 | 10 | 0 | 0 | 6 | 9.0 |
| alternative | 19 | static | False | 40 | 2 | 38 | 0 | 1 | 1.5 |
| alternative | 19 | periodic | True | 10 | 10 | 0 | 0 | 6 | 9.0 |
| alternative | 31 | static | False | 40 | 4 | 36 | 0 | 1 | 1.5 |
| alternative | 31 | periodic | True | 10 | 10 | 0 | 0 | 6 | 9.0 |

### Per-episode map metrics

Each entry is **cumulative cell-samples / final-state cell count**. Samples include
step 0 plus every post-action snapshot. These are not change-event counts or
classification labels. `false_persistent_occupancy_updates` retains its old column
name for compatibility, but measures retained pedestrian-sourced occupied entries
after departure while persistent truth is free. Stale errors exclude unknown;
missed changes include unknown cells at locations changed at any elapsed step.

| Scenario | Seed | Method | Stale | False persistent occupancy | Missed persistent changes |
| --- | ---: | --- | ---: | ---: | ---: |
| empty | 7 | static | 0 / 0 | 0 / 0 | 0 / 0 |
| empty | 7 | periodic | 0 / 0 | 0 / 0 | 0 / 0 |
| empty | 19 | static | 0 / 0 | 0 / 0 | 0 / 0 |
| empty | 19 | periodic | 0 / 0 | 0 / 0 | 0 / 0 |
| empty | 31 | static | 0 / 0 | 0 / 0 | 0 / 0 |
| empty | 31 | periodic | 0 / 0 | 0 / 0 | 0 / 0 |
| temporary | 7 | static | 0 / 0 | 0 / 0 | 0 / 0 |
| temporary | 7 | periodic | 7 / 1 | 2 / 0 | 0 / 0 |
| temporary | 19 | static | 0 / 0 | 0 / 0 | 0 / 0 |
| temporary | 19 | periodic | 10 / 2 | 3 / 1 | 0 / 0 |
| temporary | 31 | static | 11 / 1 | 6 / 1 | 0 / 0 |
| temporary | 31 | periodic | 11 / 1 | 2 / 1 | 0 / 0 |
| persistent | 7 | static | 0 / 0 | 0 / 0 | 38 / 1 |
| persistent | 7 | periodic | 1 / 0 | 0 / 0 | 1 / 0 |
| persistent | 19 | static | 39 / 1 | 0 / 0 | 39 / 1 |
| persistent | 19 | periodic | 0 / 0 | 0 / 0 | 0 / 0 |
| persistent | 31 | static | 0 / 0 | 0 / 0 | 38 / 1 |
| persistent | 31 | periodic | 0 / 0 | 0 / 0 | 1 / 0 |
| mixed | 7 | static | 0 / 0 | 0 / 0 | 38 / 1 |
| mixed | 7 | periodic | 4 / 0 | 1 / 0 | 1 / 0 |
| mixed | 19 | static | 7 / 1 | 0 / 0 | 7 / 1 |
| mixed | 19 | periodic | 10 / 2 | 3 / 1 | 0 / 0 |
| mixed | 31 | static | 41 / 1 | 21 / 1 | 37 / 1 |
| mixed | 31 | periodic | 13 / 1 | 4 / 1 | 2 / 0 |
| alternative | 7 | static | 0 / 0 | 0 / 0 | 38 / 1 |
| alternative | 7 | periodic | 1 / 0 | 0 / 0 | 1 / 0 |
| alternative | 19 | static | 39 / 1 | 0 / 0 | 39 / 1 |
| alternative | 19 | periodic | 0 / 0 | 0 / 0 | 0 / 0 |
| alternative | 31 | static | 0 / 0 | 0 / 0 | 38 / 1 |
| alternative | 31 | periodic | 0 / 0 | 0 / 0 | 1 / 0 |

## Visualizations and limitations

Thirty PNG snapshots (initial, step 4, final for first seed of every family/method)
are under `results/phase1_1/development`. Hidden truth and agent memory are separate
panels; successful trajectories, blocked static endpoints and bypass routes can be
compared. The mixed periodic final snapshot was visually inspected for readable
labels and path/map separation. Pedestrians are drawn over objects when co-located;
raw geometry and schedules in JSON resolve this ambiguity. No image-generation
model was used.

The two methods receive only ternary observations, pose/goal and shared unknown
handling. Neither receives persistence labels, future positions, scenario hashes,
hidden maps or change schedules. Evaluator truth attribution never alters memory.
Python architecture is not a security boundary. Dynamic contacts are discrete
occupancy entry events, without physical collision dynamics or human safety meaning.
New occupancy may enter a robot cell, and pedestrians do not react to the robot.

Only three environmental seeds and five simple related layouts are used; no
confidence intervals or population-level superiority claim is justified. Empty
seeds duplicate a control; different nonempty seeds really change conditions.
The broad generator diversity test is not an additional performance evaluation.
The alternative route test verifies route availability with evaluator truth only;
it is not an oracle provided to either agent. Both methods can differ in observed
areas and episode duration, so cumulative map errors confound error rate and time.
Report final counts alongside totals; future research should predefine common
horizon map sampling, contact constraints, latency, topology diversity and a budget
policy. The 40-step horizon is developmental, not an optimized deadline.
False occupancy attribution measures retained writes, not semantic persistence
classification. Sensor noise is zero here; robustness to noise/range/interval and
stronger published baselines still require review. Holding out this very small
reserved suite alone will not establish generalization. Do not run it or begin new
algorithms before research review.

Artifacts record generating HEAD plus dirty state and source hashes rather than
claiming the resulting commit SHA was known before committing. No history rewrite
is needed. Git operations use a per-command safe.directory override because the
sandbox account differs from the owner; global Git configuration is unchanged.
