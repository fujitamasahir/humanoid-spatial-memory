# Phase 1.2 adaptive observation baseline validation

Executed on Windows with Python 3.12.10, 2026-11-06. macOS is intended but not
validated. Branch: `feature/phase1-2-adaptive-baselines`, created from freshly
fetched `origin/develop`. No main/develop merge or direct main push is performed.
No task-aware verification, RL, MuJoCo or humanoid locomotion is implemented.

## Exact reproduction commands

From the repository root, Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/run_adaptive_experiment.py --config configs/development_phase1_2.json --output results/phase1_2/development
```

For a fresh environment first create a Python 3.12 virtual environment and install
`requirements.txt`. On macOS substitute `.venv/bin/python` (not tested). A rerun
may overwrite Phase 1.2 files: use another output directory to retain both runs.
The runner blocks output to Phase 1/1.1 artifact directories (including their
children/ancestors), and rejects any non-development split before executing.

A second complete run was executed without figures:

```powershell
.\.venv\Scripts\python.exe scripts/run_adaptive_experiment.py --config configs/development_phase1_2.json --output results/runs/phase1_2_repeat --no-figures
```

All 288 episode metrics, summaries, realized scenarios and decision traces matched
exactly between runs. An artifact audit also checked every distance/blocked/count
sum, observation cap and cost, cumulative/final map-error accounting, and the
stored source/config hashes. Repeat outputs are ignored local validation files.
Generating normalized source SHA-256:
`be0abc561c36e2acc14b09c3379ee0a2b04a13404d7569404ade2967b54c1960`.

**Tests: 70 passed, 0 failed**, with 14 existing Matplotlib/pyparsing deprecation
warnings. `pip check` reports no broken requirements. Coverage includes per-cell
timestamps/visibility, exact trigger boundaries, pose-local age dependence,
uncertainty evolution without sensing, same-age/different-history decisions,
configured rate bounds, occlusion-induced repeated requests, actual sensor call
counts under caps 1/3/unlimited for all methods, budget denials without resets,
JSON artifact round-trip fidelity, initial-view and paired truth equality, deterministic repeatability, interface and
behavioral ground-truth isolation, successful-only summaries, pre-move sensing
poses, invalid inputs and output protection. Regression tests rerun all 54 stored
Phase 1.1 diagnostic/development episodes and match every historical metric.

## Implementation definitions

The [literature review](phase1_2_baseline_review.md) records verified paper metadata,
assumptions, access limits and the baseline rules written before implementation.
Both new schedules are simplified conceptual controls, not faithful published
method reproductions. The source files for the simulator, sensor, A*, Static and
Periodic remain unchanged. The evaluator now delegates observation requests to a
controller with a shared cap. No baseline receives a Scenario or full experiment
config: only initial ternary observation, sensor radius, public configured model
parameters, time and current pose cross the scheduling interface.

- **Static:** one initialization observation, frozen map, unchanged behavior.
- **Periodic:** requests at positive multiples of interval 2, unchanged behavior.
- **Local cell-age:** timestamp L_i=-1 for unknown cells; visible observations alone
  reset it. In the Euclidean disk of sensor radius 3 around the current pose,
  request when at least 50% of known cells have t-L_i >= 4. Unknown cells are
  excluded. No known cells means no request. This becomes a fixed interval only
  for uniform timestamps and a fixed fully visible footprint. In the corridor,
  requests at steps 24,25,27,28,31 demonstrate its non-global timing.
- **History-adapted uncertainty:** for each known cell accumulate binary sample
  flips F_i and elapsed exposure E_i between successive visible samples. Use
  lambda_i=clip((0.3+F_i)/(6+E_i),0.01,0.35). A visible occupied/free sample resets
  confidence p_i to 0.95/0.05. Without sensing evolve
  p_i(t)=0.5+(p_i(L_i)-0.5)*exp(-2*lambda_i*(t-L_i)). Compute binary entropy in bits;
  request when its mean over the same known footprint >= 0.75. Unknown cells have
  entropy 1 in the estimator but are excluded from the trigger. Rates use only
  observed sequences and configured priors. The estimator evolves with time even
  when budget denies a request. Same-age histories with stable versus flipped
  observations yield different decisions (tested), so it is not generally an age
  threshold in disguise. Homogeneous rates/histories are an explicit limiting
  equivalence. This confidence proxy is not calibrated HMM/Bayesian inference.

All methods retain last-write ternary occupancy for planning. Uncertainty does not
erase or relabel memory. Neither scheduler sees the goal, route, blocked-move
feedback, actual occlusion mask, persistence labels or future schedules. The local
disk is only a potential sensing footprint, computed without hidden geometry. It
may contain occluded cells that cannot be refreshed from this pose. Locality is
not path relevance and does not implement task-aware verification.

Caps are **total** observations, including initialization: unlimited, 3, 5 and 8.
Budget denial prevents a sensor call and leaves timestamps/map/confidence history
unchanged. Denied requests are counted individually per step, not as distinct
unresolved cells. Initial observation is mandatory and costs 1.5, as does each
subsequent granted call. Sensing adds no simulation time; a step advances the
world, decides/senses, replans, then attempts a cardinal movement. Trace
`observation_position` is the pre-move sensing pose; `position` is post-action.
The initial frame records a granted initial call, while request/denial totals
count positive-step requests only. Static can leave its equal maximum cap unused.

Age 4 is twice the fixed interval; entropy 0.75 gives an initial homogeneous
trigger near step 5 with rate 0.05. Rates, pseudocounts and confidence are documented
assumptions, not oracle estimates. The cap settings bracket the earlier periodic
5?7 calls in new families and 13 in the corridor. Parameters were fixed in the
review before evaluation; no outcome-driven parameter search was performed.

## Experiments and metrics

Six development families (five Phase 1.1 families plus original corridor), paired
seeds 7/19/31, 40-step deadline, four methods, four settings: **288 episodes**.
For each family/seed, one realized Scenario is reused across all methods/settings.
Same initial views, range/occlusion/noise, A*, optimistic unknown handling, movement,
goal and deadlines apply. Environmental truth is equal at equal times; methods
can stop at different times. Sensor noise is zero, with the existing per-time RNG
retained. Realized schedules/hashes are evaluator audit records, never agent inputs.

Success means reaching the goal by step 40 regardless of contact. Distance counts
successful unit moves; elapsed steps include waits and blocked attempts. Blocked
attempts are rejected motions, **not physical collisions**. Dynamic contacts count
new occupancy entries into the pre-move robot cell (continuing overlap excluded).
The deprecated compatibility `collision_count` remains their sum.

Stale errors compare known memory with persistent geometry (not pedestrians).
False persistent occupancy counts remembered pedestrian-sourced occupied writes
after departure while geometry is free, not semantic classifications or update
events. Missed changes count ever-changed cells whose current memory is unknown
or mismatches current geometry. Unprefixed totals sum cell counts at initialization
and each post-action sample; `final_` columns count final-state cells only. Unequal
episode lengths confound cumulative totals and error duration. These definitions
and historical compatibility remain as in Phase 1.1.

Files: [episodes.csv](../results/phase1_2/development/episodes.csv) contains every
per-episode metric and failure label; [summary.csv](../results/phase1_2/development/summary.csv)
and [scenario_summary.csv](../results/phase1_2/development/scenario_summary.csv) contain
means and success counts. [results.json](../results/phase1_2/development/results.json)
adds full config, realized scenarios, decision/action/error traces and provenance.
Successful-only observation means exclude failures and are null when there are no
successes. Such means select different episode subsets and are not a paired
performance statistic on their own. No confidence intervals or significance claims.

### Success versus observation cost

Each row aggregates 18 episodes (six families times three seeds). Costs are 1.5
units per observation; changing only this scalar would rescale cost without
changing behavior in these policies. Caps, rather than mere cost rescaling,
produce the distinct sensing constraints evaluated here.

| Setting | Method | Success | Mean observations | Successful-only mean observations | Mean cost |
| --- | --- | ---: | ---: | ---: | ---: |
| unlimited | static | 7/18 | 1.000 | 1.000 | 1.500 |
| unlimited | periodic | 18/18 | 7.056 | 7.056 | 10.583 |
| unlimited | age | 15/18 | 5.389 | 3.067 | 8.083 |
| unlimited | uncertainty | 18/18 | 2.778 | 2.778 | 4.167 |
| cap3 | static | 7/18 | 1.000 | 1.000 | 1.500 |
| cap3 | periodic | 14/18 | 3.000 | 3.000 | 4.500 |
| cap3 | age | 15/18 | 3.000 | 3.000 | 4.500 |
| cap3 | uncertainty | 18/18 | 2.778 | 2.778 | 4.167 |
| cap5 | static | 7/18 | 1.000 | 1.000 | 1.500 |
| cap5 | periodic | 15/18 | 5.000 | 5.000 | 7.500 |
| cap5 | age | 15/18 | 3.389 | 3.067 | 5.083 |
| cap5 | uncertainty | 18/18 | 2.778 | 2.778 | 4.167 |
| cap8 | static | 7/18 | 1.000 | 1.000 | 1.500 |
| cap8 | periodic | 15/18 | 6.222 | 5.867 | 9.333 |
| cap8 | age | 15/18 | 3.889 | 3.067 | 5.833 |
| cap8 | uncertainty | 18/18 | 2.778 | 2.778 | 4.167 |

### Navigation and sensing-denial means

| Setting | Method | Elapsed steps | Distance | Blocked attempts | Dynamic contacts | Denied requests |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| unlimited | static | 27.889 | 4.944 | 22.944 | 0.056 | 0.000 |
| unlimited | periodic | 12.278 | 11.444 | 0.833 | 0.056 | 0.000 |
| unlimited | age | 14.944 | 11.444 | 2.500 | 0.222 | 0.000 |
| unlimited | uncertainty | 10.500 | 9.222 | 1.278 | 0.222 | 0.000 |
| cap3 | static | 27.889 | 4.944 | 22.944 | 0.056 | 0.000 |
| cap3 | periodic | 16.333 | 8.611 | 7.722 | 0.056 | 6.167 |
| cap3 | age | 14.944 | 8.944 | 6.000 | 0.222 | 4.944 |
| cap3 | uncertainty | 10.500 | 9.222 | 1.278 | 0.222 | 0.000 |
| cap5 | static | 27.889 | 4.944 | 22.944 | 0.056 | 0.000 |
| cap5 | periodic | 14.778 | 9.444 | 5.333 | 0.056 | 3.389 |
| cap5 | age | 14.944 | 9.611 | 5.333 | 0.222 | 3.500 |
| cap5 | uncertainty | 10.500 | 9.222 | 1.278 | 0.222 | 0.000 |
| cap8 | static | 27.889 | 4.944 | 22.944 | 0.056 | 0.000 |
| cap8 | periodic | 14.778 | 9.778 | 5.000 | 0.056 | 2.167 |
| cap8 | age | 14.944 | 11.444 | 3.500 | 0.222 | 2.333 |
| cap8 | uncertainty | 10.500 | 9.222 | 1.278 | 0.222 | 0.000 |

### Cumulative versus final map errors

Values are mean **cumulative cell-samples / final cells**, not event counts.

| Setting | Method | Stale | False persistent occupancy | Missed persistent changes |
| --- | --- | ---: | ---: | ---: |
| unlimited | static | 14.444 / 0.444 | 6.167 / 0.111 | 35.333 / 1.000 |
| unlimited | periodic | 6.500 / 0.389 | 1.333 / 0.222 | 9.222 / 0.333 |
| unlimited | age | 14.278 / 0.611 | 6.056 / 0.444 | 16.389 / 0.167 |
| unlimited | uncertainty | 4.111 / 0.444 | 1.889 / 0.222 | 4.833 / 0.333 |
| cap3 | static | 14.444 / 0.444 | 6.167 / 0.111 | 35.333 / 1.000 |
| cap3 | periodic | 10.222 / 0.444 | 2.389 / 0.111 | 19.333 / 0.556 |
| cap3 | age | 14.111 / 0.611 | 6.056 / 0.444 | 18.389 / 0.500 |
| cap3 | uncertainty | 4.111 / 0.444 | 1.889 / 0.222 | 4.833 / 0.333 |
| cap5 | static | 14.444 / 0.444 | 6.167 / 0.111 | 35.333 / 1.000 |
| cap5 | periodic | 9.278 / 0.500 | 1.278 / 0.333 | 17.389 / 0.500 |
| cap5 | age | 14.111 / 0.611 | 6.056 / 0.444 | 18.389 / 0.500 |
| cap5 | uncertainty | 4.111 / 0.444 | 1.889 / 0.222 | 4.833 / 0.333 |
| cap8 | static | 14.444 / 0.444 | 6.167 / 0.111 | 35.333 / 1.000 |
| cap8 | periodic | 9.333 / 0.556 | 1.167 / 0.222 | 17.389 / 0.500 |
| cap8 | age | 14.111 / 0.611 | 6.056 / 0.444 | 18.389 / 0.500 |
| cap8 | uncertainty | 4.111 / 0.444 | 1.889 / 0.222 | 4.833 / 0.333 |

### Scenario-specific successes and observation counts

Each method entry is **successes out of 3; mean observations over all 3**.
All other per-scenario task/map means are in `scenario_summary.csv`, and individual
counts are in `episodes.csv`. The corridor and empty seeds repeat identical
noise-free environments; they are not independent environmental replications.

| Scenario | Setting | Static | Periodic | Age | Uncertainty |
| --- | --- | --- | --- | --- | --- |
| empty | unlimited | 3/3; 1.00 | 3/3; 5.00 | 3/3; 3.00 | 3/3; 2.00 |
| empty | cap3 | 3/3; 1.00 | 3/3; 3.00 | 3/3; 3.00 | 3/3; 2.00 |
| empty | cap5 | 3/3; 1.00 | 3/3; 5.00 | 3/3; 3.00 | 3/3; 2.00 |
| empty | cap8 | 3/3; 1.00 | 3/3; 5.00 | 3/3; 3.00 | 3/3; 2.00 |
| temporary | unlimited | 3/3; 1.00 | 3/3; 6.00 | 3/3; 3.00 | 3/3; 2.67 |
| temporary | cap3 | 3/3; 1.00 | 3/3; 3.00 | 3/3; 3.00 | 3/3; 2.67 |
| temporary | cap5 | 3/3; 1.00 | 3/3; 5.00 | 3/3; 3.00 | 3/3; 2.67 |
| temporary | cap8 | 3/3; 1.00 | 3/3; 6.00 | 3/3; 3.00 | 3/3; 2.67 |
| persistent | unlimited | 0/3; 1.00 | 3/3; 6.00 | 3/3; 3.00 | 3/3; 3.00 |
| persistent | cap3 | 0/3; 1.00 | 3/3; 3.00 | 3/3; 3.00 | 3/3; 3.00 |
| persistent | cap5 | 0/3; 1.00 | 3/3; 5.00 | 3/3; 3.00 | 3/3; 3.00 |
| persistent | cap8 | 0/3; 1.00 | 3/3; 6.00 | 3/3; 3.00 | 3/3; 3.00 |
| mixed | unlimited | 1/3; 1.00 | 3/3; 6.33 | 3/3; 3.33 | 3/3; 3.00 |
| mixed | cap3 | 1/3; 1.00 | 2/3; 3.00 | 3/3; 3.00 | 3/3; 3.00 |
| mixed | cap5 | 1/3; 1.00 | 3/3; 5.00 | 3/3; 3.33 | 3/3; 3.00 |
| mixed | cap8 | 1/3; 1.00 | 3/3; 6.33 | 3/3; 3.33 | 3/3; 3.00 |
| alternative | unlimited | 0/3; 1.00 | 3/3; 6.00 | 3/3; 3.00 | 3/3; 3.00 |
| alternative | cap3 | 0/3; 1.00 | 3/3; 3.00 | 3/3; 3.00 | 3/3; 3.00 |
| alternative | cap5 | 0/3; 1.00 | 3/3; 5.00 | 3/3; 3.00 | 3/3; 3.00 |
| alternative | cap8 | 0/3; 1.00 | 3/3; 6.00 | 3/3; 3.00 | 3/3; 3.00 |
| corridor_change | unlimited | 0/3; 1.00 | 3/3; 13.00 | 0/3; 17.00 | 3/3; 3.00 |
| corridor_change | cap3 | 0/3; 1.00 | 0/3; 3.00 | 0/3; 3.00 | 3/3; 3.00 |
| corridor_change | cap5 | 0/3; 1.00 | 0/3; 5.00 | 0/3; 5.00 | 3/3; 3.00 |
| corridor_change | cap8 | 0/3; 1.00 | 0/3; 8.00 | 0/3; 8.00 | 3/3; 3.00 |

## Actual findings and failure analysis

Unconstrained uncertainty reaches all 18 goals at 2.778 mean observations, versus
periodic's 18/18 at 7.056. That is 60.6% fewer calls in this sample, with mean
elapsed steps 10.5 versus 12.278. This is an observed development comparison, not
evidence that the confidence estimator itself causes a general advantage. Age
uses 5.389 calls overall with 15/18 success; successful episodes alone use 3.067.
Failed long episodes account for much of that difference.

**Empty:** all methods succeed in 8 moves/steps. Static needs only its initial
observation, age uses 3, uncertainty 2, periodic unlimited 5. Adaptive refresh is
still wasteful in an actually static empty world; methods cannot know that truth.

**Temporary:** all methods succeed. Periodic and age take 10-cell detours on all
seeds; uncertainty seed 7 traverses directly in 8 steps, but seed 19 has a blocked
attempt. Static seed 19 waits through two blocked attempts and then succeeds.
More sensing does not uniformly reduce distance.

**Persistent and alternative:** static fails all three seeds in each family by
repeating a newly blocked target. Others all succeed, including under cap3.
Unconstrained periodic averages 10 steps/zero blocked attempts, age 10.333/0.333,
and uncertainty 11/1. Fewer observations trade away early obstacle detection.
The two families have different topology but duplicate performance patterns,
so should not be treated as independent corroboration of the same effect.

**Mixed:** static succeeds only for seed 19, whose new obstacle enters its current
cell and is then behind it. Under cap3 periodic fails seed 31: initialization and
steps 2/4 exhaust its capacity, leaving the new obstacle at (6,3) uncorrected in
its remembered route; it remains at (5,3) with 34 blocked attempts. Larger caps
succeed. Both adaptive methods succeed under every tested setting, but success
alone does not imply no contact or accurate final memory.

**Corridor:** static repeats its unobserved-wall target (2,2) from (2,3), failing
all settings. Unconstrained periodic preserves the Phase 1.1 trajectory and reaches
the goal at step 25 with 13 observations. All its tested finite caps fail after
exhaustion, ending against unobserved walls in the upper passage. Age enters the
upper passage, backtracks and enters the lower dead end; unlimited age ends at
(7,5) with 17 observations, 14 blocked attempts and no remembered route. Its final
map retains occupied (6,3), a removed obstruction, and pedestrian-sourced (4,3).
The retained occupancy cuts the remembered connection to the goal. From steps
35?40 age senses on every step: old occluded known cells remain stale in the
potential footprint despite each refresh. No cooldown or heuristic repair was
added to hide this failure. Capped age exhausts its sensing and fails with repeated
blocked attempts. These are genuine weaknesses of this explicit age rule.

Uncertainty senses at steps 0,5,10 in the corridor, waits through blocked attempts,
and reaches the goal at step 13 with 8 successful moves and 5 blocked attempts.
Its step-10 observation follows the obstruction removal, permitting a direct route.
Its timing also incurs a pedestrian entering the robot cell: one dynamic contact
per corridor episode. In the unlimited aggregate uncertainty and age each have
**4 dynamic contacts**, versus periodic and static each **1**. Three of these are
the repeated deterministic corridor condition. Thus the cheaper successful schedule
is not a safety improvement. Uncertainty still retains final stale/transient entries.

The uncertainty schedules use at most three observations in these short episodes,
so cap3/cap5/cap8 are all nonbinding for it and reproduce identical outcomes.
Those repeated settings are not four independent demonstrations of robustness,
and do not establish its behavior under a binding cap. Tests exercise cap1 denial,
but that is not a performance evaluation. A lower cap and longer, noisier episodes
are future research-design questions, not silently added tuning experiments here.

`failure_reason` labels are terminal symptoms, not causal oracle inputs:
`deadline_no_remembered_route` means final A* returned no route;
`deadline_repeated_blocked_attempts` means the last three actions were blocked;
otherwise `deadline_before_goal` means another deadline failure. The failure
analysis above inspects evaluator traces and truth after execution. Successful
records have null failure labels. Budget exhaustion is recorded separately through
denied requests; it is not automatically declared the cause of every failure.

## Artifacts, integrity and remaining threats

There are 24 final truth-versus-memory PNGs (one first-seed snapshot per
family/method) and [an observation tradeoff chart](../results/phase1_2/development/observation_tradeoff.png).
The chart and representative corridor maps were inspected for readable labels and
separation of hidden truth and agent memory. Co-located people can hide object
colors in the display; saved scenario schedules disambiguate truth. The chart
compares all-episode sensing means with successful-only means to expose selection.

The five papers establish relevant concepts, not the efficacy of our exact rules.
No complete published temporal mapper, calibrated uncertainty model, active view
planner, or proposed task-aware algorithm is reproduced. A slower fixed-period
control (especially interval 5) and a fixed-rate ablation are needed before
attributing any benefit to learned history rather than simply favorable sensing
phase. Most trajectories have too few samples to validate rate adaptation.
Unit tests prove the rules differ; they do not establish which estimator is better.

Layouts are small and related, some seed conditions intentionally duplicate, and
only three seeds are used for genuinely variable families. Priors, thresholds,
noise floor and exposure model are assumptions. Observed flips undercount hidden
multiple transitions and confuse noise with change. Cumulative errors compare
unequal horizons; final errors compare unequal places/times and visibility.
Unknown cells are excluded from both triggers, so a wholly unknown footprint can
fail to request useful sensing. Neither policy reasons about occlusion feasibility
beyond the potential disk. Sensing has zero latency, and short scripted pedestrian
cycles can favor particular refresh phases. No contact threshold constrains success;
point-robot contacts do not establish physical collision dynamics or human safety.

Prior Phase 1/1.1 files and reserved held-out configuration remain unchanged. No
held-out execution or tuning occurred. Regression compares old metric values but
does not regenerate their artifacts. Git preservation checks compare against
`origin/develop` for the historical paths and baseline source. The result provenance
records generating HEAD and dirty state plus normalized source SHA-256 and raw
config hash; it does not pretend to contain the as-yet-unknown final commit SHA.
The source hash includes all Python files under src and scripts and normalizes
CRLF to LF for portable comparison. Exact installed packages/platform are in JSON.

Stop for research review. Review budgets, sensing phase/interval controls,
calibration, broader layouts and horizon-matched map evaluation before any
held-out run, proposed task-aware verification or humanoid simulation.
