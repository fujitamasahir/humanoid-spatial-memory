# Phase 1.3 robustness validation

Executed 2026-11-06 on macOS / Apple Silicon, Python 3.12.16. Branch:
`feature/phase1-3-robustness`, created from freshly fetched
`origin/feature/phase1-2-adaptive-baselines`. Research review is required before
any task-aware implementation, held-out execution, MuJoCo or locomotion work.

## Main results

The Phase 1.2 observation-saving advantage does not establish robust superiority.
In the new reference set, Periodic completes 28/28 goals, Age 21/28 and Uncertainty
19/28. Uncertainty uses 5.179 observations on average versus Periodic's 12, but
contact-free completions are 16/28 versus 26/28. Slower periodic interval 5 gives
19/28 completions at 5.786 calls, matching uncertainty's completion count; this
undercuts attributing the original gain specifically to history adaptation.

| Reference method | Goals / 28 | Contact-free goals / 28 | Mean calls | Dynamic contacts |
| --- | ---: | ---: | ---: | ---: |
| static | 12 | 10 | 1.000 | 2 |
| periodic | 28 | 26 | 12.000 | 2 |
| age | 21 | 19 | 7.607 | 2 |
| uncertainty | 19 | 16 | 5.179 | 3 |

All predefined settings are shown below. These are paired repeated measurements,
not independent replications across settings. No winner was selected or tuned.
Every setting contains 28 unique realized environments (four per family), reused
across methods. Many settings share exactly the same environmental realization;
only sensing or scheduler parameters differ. Family-level dependence remains.

| Setting | Static goals | Periodic goals | Age goals | Uncertainty goals | Uncertainty contact-free | Uncertainty mean calls |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| reference | 12/28 | 28/28 | 21/28 | 19/28 | 16/28 | 5.179 |
| cap1 | 12/28 | 12/28 | 12/28 | 12/28 | 10/28 | 1.000 |
| cap2 | 12/28 | 11/28 | 9/28 | 9/28 | 8/28 | 2.000 |
| cap4 | 12/28 | 12/28 | 14/28 | 18/28 | 15/28 | 3.714 |
| radius2 | 14/28 | 28/28 | 20/28 | 18/28 | 17/28 | 5.429 |
| radius5 | 12/28 | 28/28 | 21/28 | 20/28 | 18/28 | 5.429 |
| noise05 | 12/28 | 28/28 | 23/28 | 19/28 | 16/28 | 5.714 |
| clearview | 12/28 | 28/28 | 28/28 | 28/28 | 26/28 | 4.607 |
| early | 12/28 | 28/28 | 20/28 | 17/28 | 14/28 | 5.429 |
| late | 19/28 | 28/28 | 23/28 | 23/28 | 18/28 | 4.179 |
| longdwell | 12/28 | 28/28 | 20/28 | 16/28 | 16/28 | 5.571 |
| entropy65 | 12/28 | 28/28 | 21/28 | 20/28 | 18/28 | 6.893 |
| entropy85 | 12/28 | 28/28 | 21/28 | 17/28 | 15/28 | 3.464 |
| period5 | 12/28 | 19/28 | 21/28 | 19/28 | 16/28 | 5.179 |
| priorSlow | 12/28 | 28/28 | 21/28 | 16/28 | 14/28 | 1.571 |
| priorFast | 12/28 | 28/28 | 21/28 | 28/28 | 27/28 | 11.964 |

Cap1 makes all methods behaviorally static because initialization consumes the
entire budget. Under cap2, periodic gets 11/28 goals and age/uncertainty each 9/28;
more sensing can write an obstruction into memory and worsen a later route when
there is no capacity to correct it. Caps must be studied as constraints, not a
monotone guarantee of performance. Denied requests and budget exhaustion are
recorded separately; exhaustion is not automatically the cause of every failure.

Occlusion off raises both adaptive methods to 28/28. This is a sensitivity result,
not a proposal to remove occlusion from evaluation. Slow/fast uncertainty priors
produce 16/28 versus 28/28 goals with 1.571 versus 11.964 calls. The fast prior's
observation cost is close to reference periodic, so it does not preserve the same
observation-saving claim. Timing and dwell also change completion/contact rates.
No confidence intervals or significance claims are justified by this small set.

The separate corridor diagnostic contains 72 method/prior/timing episodes over
six distinct timing worlds, without duplicated seeds. Default uncertainty succeeds
for removal at 8/9/10 and fails at 11/12/14. Both alternate priors fail all six
corridor conditions. See [diagnostic review](phase1_3_diagnostic_review.md) for
trace-based explanations and [design](phase1_3_task_aware_design.md) for the
unimplemented, explicitly non-novel task-aware candidate and research gates.

## Methods and interpretation

The [fixed experiment plan](phase1_3_experiment_plan.md) specifies all 16 settings,
including an integrity correction for duplicated preliminary family geometry.
Final results supersede the preliminary run. No baseline code was changed to
improve scores. New topology, timing and pedestrian generation is isolated in
`robustness.py`; policies receive only the established robot-accessible inputs.
Persistent-geometry reachability at initial/event/final epochs uses evaluator-only
truth. Final reachability is required. Temporary pedestrians are excluded from
that audit: it does not prove dynamically safe reachability or deadline feasibility.

Seeded variation covers dimensions, start/goal lane, gate positions, wall/room
layouts, side rooms/dead ends, alternate routes, addition/removal times, pedestrian
multiplicity/crossing phase/dwell, and sensor visibility/noise. Layouts are still
small hand-designed families with procedural parameters. A high-entropy off-route
stressor does not ensure entropy concentration at every pose, and the stale-route
family does not force a particular agent belief. Those intentions must not become
post hoc mechanism claims. A constructive matched-history test establishes that
route consequence contains information not encoded by entropy alone; no experiment
here establishes an advantage for an unimplemented task-aware method.

Legacy metrics and termination are preserved. `collision_count` remains the
compatibility sum of blocked attempts and dynamic contacts; it is not physical
collision. Blocked targets reject the motion. Dynamic contacts count new geometry
or pedestrian occupancy entering the pre-move robot cell, with continuing overlap
excluded and at most one event per step. Goal completion is distinct from
`contact_free_success` (goal reached with zero dynamic contacts). Rejected attempts
do not disqualify contact-free success. `dynamic_contact_rate` divides contacts by
elapsed steps (minimum denominator one); summaries pool contacts over elapsed
steps. These counts cannot establish physical safety.

Observation count includes initialization, costs 1.5 per call, and adds no time.
Path length is successful cardinal moves (`travel_distance`); elapsed time includes
waits/blocked attempts. `budget_exhausted` means total calls reached the finite cap,
even if no request was denied. Denied requests are per-step attempted calls.
`persistent_observation_timing` records delay to the first granted call after each
event, null if none before termination; it does not guarantee the cell was visible.
`persistent_change_events_elapsed` counts scheduled events, not independent draws.

Final-state map errors retain the existing definitions. Legacy cumulative errors
sum cell counts from initialization through termination. Common-horizon errors
sum the same evaluator quantities at times 0..40 for every method, freezing memory
after reaching the goal while advancing truth only. This compares residual memory
under an explicit stopped-agent convention, not continued task operation. There
are 41 sampling instants; cumulative cell-time samples are not independent change
events. Common-horizon support does not send any additional input to the agent.

## Reproduction and provenance

Use Python 3.12 and install the unchanged pinned `requirements.txt`. Windows:
substitute `.venv\Scripts\python.exe` for `.venv/bin/python` below. The original
Mac `.venv` was Python 3.9 without dependencies; actual validation used a temporary
Python 3.12.16 environment at `/tmp/phase13-venv`, without replacing that `.venv`.

```bash
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pytest -q
.venv/bin/python scripts/run_robustness_experiment.py
.venv/bin/python scripts/run_corridor_diagnostic.py
.venv/bin/python scripts/run_robustness_experiment.py --output results/runs/phase1_3_repeat --no-figures
```

Actual macOS commands use `/tmp/phase13-venv/bin/python` and set
`MPLCONFIGDIR=/tmp/phase13-mpl`; the repeat output was `/tmp/phase13-repeat`.
Dependency compatibility check used `uv pip check` and passed for all 14 packages.
JSON records full configuration, realized worlds/hashes, topology audits, every
metric, observation/action/error traces, Python/platform, installed package
versions, generating HEAD, dirty state and SHA-256 for every src/script file.
Source hashes normalize CRLF to LF. The generating HEAD is the Phase 1.2 parent
and working tree dirty is true: the results were generated before the final
Phase 1.3 commit. It does not pretend to contain its own final commit SHA.
Corridor JSON additionally stores its original config and all interventions.

Normalized source manifest SHA-256: `932a16abaa4f842255bfd5d3bfb25a18609505f0a9a852a693f4614e096b5aba`.

All 1,792 episodes, summaries, realizations and complete traces matched exactly
on a second independent execution. Stored file hashes were recomputed and match.
The suite passes **98 tests**, with 14 pre-existing Matplotlib/pyparsing deprecation
warnings. New coverage includes sensor-history replay witnessing the intended A/B belief
stressors, seeded diversity, name-independent duplicate
checks, paired truth/noisy initial sensing, topology, budget and metric arithmetic,
independent common-horizon recomputation, timing interventions, actual foreground
occlusion, public-interface isolation, no behavioral changes from evaluator metrics,
held-out/output guards and all 288 historical Phase 1.2 episode metrics. Existing
Phase 1.1 regression coverage also passes. No reserved held-out suite was run.

## Artifacts and preservation

- `results/phase1_3/development/episodes.csv`: all 1,792 per-episode records.
- `summary.csv` and `scenario_summary.csv`: all settings and family summaries.
- `results.json`: configuration, provenance, worlds, topology and traces.
- `robustness.png`: completion versus contact-free completion across settings.
- `occluded_*_final.png`: first-seed reference hidden truth versus agent memory.
- `results/phase1_3/corridor_diagnostic/`: 72 diagnostic episodes and gate traces.

Figures were visually checked. Earlier results, all existing development/held-out
configs, scheduling, memory, sensor, planner and simulator match the Phase 1.2
branch byte-for-byte in Git. Only evaluator reporting adds fields/optional horizon
metrics. No held-out, task-aware policy, MuJoCo or locomotion was implemented.
Stop for research review; remaining limitations include uncalibrated beliefs,
small related topologies, zero sensing latency, scripted periodic pedestrians,
unknown-cell blind spots and absence of physical collision dynamics.
