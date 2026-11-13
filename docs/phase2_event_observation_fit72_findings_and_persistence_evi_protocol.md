# Event-triggered Periodic/Age FIT72 findings and B+C next-stage protocol

**Date:** 2026-11-13.
**Decision:** Freeze Event+Periodic / Event+Age v1 as negative development results.
Do not tune thresholds on the repeatedly inspected FIT36 worlds.
**Source:** committed results/phase2_mujoco/event_observation_fit72_v1/
summary.json, event_observation_pairs.csv, event_observation_traces.jsonl.gz.
These are 36 maze layouts x two **correlated** pedestrian schedules; seed42;
horizon80; original 61-ray paid spatial-memory sensor, initial scan counted;
independent emergency safety scan unchanged.

## Main outcomes

| Metric | Periodic | Periodic+Event | Age | Age+Event |
|---|---:|---:|---:|---:|
| Successful goals / 72 | 66 | **64** | 66 | **66** |
| Mean paid memory observations | 11.111 | **11.306** | 11.806 | **11.889** |
| Mean H80-censored steps | 42.208 | **42.931** | 40.486 | **40.569** |
| Mean distance, ALL episodes | 23.042m | **23.469m** | 22.396m | **22.396m** |
| Mean emergency scans | 42.208 | **42.931** | 40.486 | **40.569** |
| Unwanted contact pairs | 0 | 0 | 0 | 0 |

**Memory scan deltas:** +14 (Periodic+Event) / +6 (Age+Event)
across 72 episodes. Every memory scan costs 61 sensor rays; hence
+854 / +366 rays respectively. Emergency scans are a SEPARATE 61-ray
safety channel: do not combine them into the memory-scan counts.
Mean candidate scheduler overhead per episode:
Periodic+Event 0.052ms, Age+Event 0.836ms.

**Periodic+Event policy-specific failure:** Two previously completed
episodes in *the same* BP:80010012 maze (schedules0 and1) changed
67-step success to H80 nonarrival; no failures rescued.
Across 64 paired common successes: 2 faster, 60 unchanged,
2 slower; +26 steps and +18m travel total.

**Age+Event:** No success-to-failure or failure-to-success flips.
Of 66 paired common successes, 0 faster, 64 same steps,
2 slower; +6 steps; same total distance. Increased scan
dose without success gain.

## Significant paired cases (policy-level causal comparison in fixed simulator)

- BP:80010001, both schedules, Periodic+Event: arrival
  **79 -> 67** steps, **43.5 -> 39.0m**, 20 -> 18 memory
  scans. This is a favorable case but one maze layout.
- BP:80010012, both schedules, Periodic+Event: arrival67
  -> failure at H80; scans17 -> 20, extra movement6m.
  The two schedules are correlated and do not constitute
  two independent failure environments.
- R:80000018, both schedules, Periodic+Event:
  **+25 steps, +13.5m, +6 scans**, still reaches.
- BP:80010012, both schedules, Age+Event: +3 steps,
  unchanged distance and total scans, still reaches.
- For Age+Event, BP:80010001, R:80000018 and
  R:80000022 (both schedules each) each use +1
  memory scan, with no route improvement.
- Across all episodes, **48 blocked-action feedback
  events** in Periodic+Event and **38** in Age+Event.
  The diagnostic counts **46 / 23 triggered-or-coincident
  scans** respectively. Some coincide with a baseline
  scheduled scan: this diagnostic should NOT be
  read as 46 / 23 extra memory scans.
- **0 observed-map no-route feedback events** in BOTH
  candidate arms. The second trigger was not exercised
  by the 72-case fit set. Thus these findings directly
  test the selected-action rejection event, NOT the
  full hypothesized range of route-failure signals.

The fact that a late event causes a different trajectory
does not isolate a particular first scan or prove why a
maze became slower. A per-event temporal/counterfactual
mechanism would require a separate controlled replay.
Do NOT infer that "more scans are always worse":
different scan timings alter remembered occupancy and
G1 route decisions. An all-episode mean distance can
be deceptively low if a policy fails to reach the goal.

## Scientific conclusion of candidate A

The tested blocked-action-rejection-triggered
Periodic/Age policies **do not dominate** their
ordinary schedules in completion, sensing cost, or
successful-route efficiency. They add paid scans and
are less efficient on average; Event+Periodic loses
2 successes from one maze.

Retain candidate A code and fixed negative output.
**Do not make A v2 by fitting an event cooldown
to BP:80010012 or R:80000018.**
The negative FIT finding does not prove that *every*
possible event-triggered scheduler is inferior.
A currently unobserved no-route event mechanism
would require a new, appropriate predeclared study.

## Original question and transition to B+C

Main question: When should a humanoid agent with
only partial, time-changing indoor spatial memory
re-observe, such that it safely reaches the goal with
both fewer memory scans and lower movement cost?

RDAO H2 task/route score variants and Event A
were exploratory scheduling attempts. They are
NOT the research objective.

**Next combined candidate: B (persistence-aware
memory) + C (expected value of information).**
Unlike event-after-rejection policies, B+C aims
to anticipate *which stale observations are likely
wrong* AND *whether knowing their true present
state would affect the expected cost to the goal*.

### B: memory state model (preregister before model fitting)

- Do not read simulator geometry or object class
  labels. Input is ONLY sequences of authorized
  public ternary observations and their timestamps.
- Track per-cell probability of occupied, probability
  of temporal change and observed occupancy transitions.
  Distinguish a cell that briefly appears occupied
  from one remaining occupied over successive scans.
- Compare an asymmetric transition-hazard model
  (free-to-occupied and occupied-to-free) against
  ordinary ternary last-write and existing Age
  entropy model. Prevent a time-varying belief from
  secretly accessing unobserved truth.
- Evaluate probability calibration, false-persistent
  occupancy, missed persistent changes, and movement
  efficiency. If a belief changes the public planning
  map without a new scan, log these **inference-only**
  memory changes separately from paid observations.

### C: short-horizon expected value of information

- Public belief and robot pose/heading/goals alone
  must determine candidate sensing actions; the
  actual sensor is called ONLY after authorization.
- Quantify an approximate expected navigation
  regret BEFORE a scan by comparing likely outcomes
  of a proposed sensor reading and the G1 route
  after replanning. Charge sensing, computation,
  and remaining finite observation budget.
- Use actual sensor range/FOV and remember-only
  occlusion estimates to bound expected observable
  cells; never use shadow probes or simulator occupancy
  at decision time.
- Separate uncalibrated expected-regret *heuristics*
  from a mathematically valid/calibrated EVI claim.
  Report expected versus realized information gain
  and how often actual observations change route/action.
- A sensor budget gate must be online and
  independent of specific maze IDs, schedule,
  saved traces or retrospective success labels.
- Preserve the independent emergency safety sensor
  and true-geometry check for the one selected
  G1 action. Do not add shield queries for
  unselected hypothetical actions.

### Experimental arms and design

Predefine B and C using only independent development
data, with four explicitly distinct arms:

1. Frozen **Age** and **Periodic** baselines.
2. **B only**: persistence belief with original
   Age (or Periodic) observation scheduling.
3. **C only**: EVI-based scan scheduling using
   original last-write ternary memory.
4. **B+C**: probabilistic persistence belief and
   EVI scheduler simultaneously.

Keep Event+Age/Periodic A as secondary archived
development comparators; do not use them to
select B+C hyperparameters.

Report for each paired environment:
- success, unwanted contacts, trajectory steps
  (80 horizon), distance among *paired common
  successes*, and all-episode censored statistics;
- memory observations and 61-ray counts,
  independent emergency safety scans/rays;
- false persistent occupancy, missed persistent
  geometry changes, blocked action attempts,
  post-scan action/route changes;
- calibration metrics for probability predictions,
  expected-vs-realized sensing value and scheduler
  wall/computation cost;
- uncertainty grouped by 36 maze identities
  (2 correlated schedules each).

**VERY IMPORTANT:** The same FIT36 worlds have
already been investigated repeatedly and may
serve only as a descriptive engineering screen.
Do not claim independent confirmation based on
FIT72. Do not load held-out/reserved Phase1.5
records or bypass protected admission mechanisms.
A new authorized independent development/evaluation
cohort and a frozen policy/source commitment are
required for a credible hypothesis test.

Current stage: candidate A results COMPLETE;
B+C design PROTOCOL READY; B/C algorithms and
MuJoCo evaluation NOT YET IMPLEMENTED.
RDAO closure causal intervention outputs are not
present in the committed evidence at this date;
do not invent a completed root-cause finding.
