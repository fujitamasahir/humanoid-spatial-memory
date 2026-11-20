# Route-Adaptive Age v1: frozen FIT72 development protocol

Starting commit9333928aa52acb24d42b739549bcaaa8a2180dbc. Existing algorithms and
results remain unchanged. This task explicitly authorizes a direct admitted
FIT72 comparison, not population generation/reserved access or a safety change.
Parent is frozen Age5; original Periodic4/Age4/Age5 are strong references.

## Prior failure mechanism and difference from rejected variants

The saved latest Deadline family loses14/15/15 parent successes. Ten harms per
arm first diverge at step5 (the parent's FIRST noninitial observation). Deadline
harm cases have149 blocked actions including24 repeated same-pose/heading/action
rejections; Stable/Quiet have140/142 and23 each. First action differences range
from5 to21, so a scan difference is not immediate causal proof. Omitted reading
contents and per-cell before/after maps are missing in these traces; no hidden
read or future scan is inferred. See prior_audit/harm_divergences.json.

Single-omission public-feature masks were retrospective hand-scene associations;
zero selected harms did not establish a composable rollout policy. Latest
history variants preserve the first *Deadline* scan but their DAO parent already
suppresses necessary Age5 requests and can wait to10 steps. RAA instead preserves
the FIRST AGE5 scan and every ordinary Age5 request except a certified single-
decision delay, followed by a compulsory grant independent of route/score.

Old Route-Clock uses View-Veto/Age4, occupied route-neighbor scores and half-
interval2-step proactive scans even before Age4. It reached66 goals with932
scans and did not solve the target. RAA advances ONLY an eligible Age4 request
while Age5 is false, gap>=4, first parent scan already served, and observable
uncertainty in actual public swept route cells. It has no event/no-route
trigger, occupied-neighbor rescue, learned utility, EVI counterfactual or
future-footprint prediction. Old Age-Motion changed cadence using displacement/
heading; RAA tests map freshness/route information, not a motion cooldown alone.
These differences are hypotheses, not an established novelty/generalization claim.

## Exact prospective v1 rule

Original radius3, stale fraction0.5; a4/a5/a6 are exact local known-cell age
fractions at ages4/5/6. Unknown cells never enter their denominators. Authorized
last-write memory and known endpoint change timestamps update only after paid
readings; unknown outputs update nothing. Initial-inclusive cap20.

At an eligible decision use ONE public point-grid A* with the configured unknown
rule and ONE current public-memory optimistic61-ray footprint (range6m, scale
0.75m,120degrees). No actual sensor/shield access or future observations. An
occupied current cell invalidates the optional route without clearing memory.
For next4 and next5 route moves, conservatively rasterize public G1 translation
AABBs and intervening rotation circumradius boxes, using pinned public half
extents(.218954831277208,.3279970912029507)m and existing0.505-cell wall half-size.
A nominal point route is a proxy, not a G1 traversability guarantee.

Changing means an ACTUAL known endpoint change detected within5 steps. A new
unknown cell being discovered is not a known change. All equalities/ties below
are literal; no randomness or continuous parameter tuning.

- **RAA-Advance**: Age5 OR advance. Advance requires Age4 AND NOT Age5, at least4
  steps since actual paid scan, used>=2, usable route and a currently predicted
  visible unknown OR recent-known-change cell in next4 moves' swept region.
  First noninitial observation stays at ordinary Age5. No repeated half-gap scan.
- **RAA-Defer**: preserve Age5, except after first noninitial scan allow one-step
  delay when: usable route; scan gap<6; ALL next5 swept cells are known FREE
  and younger than5; ALL predicted view cells (excluding robot cell) are known
  and younger than5; no recent-known change anywhere in next5 swept cells.
  Empty route/view fails certificate. No deferral with exhausted budget.
- **RAA-Joint**: combine exactly the advance and deferral conditions above.
- **RAA-Off** is a unit-test control with both mechanisms disabled. Valid API
  decisions, map/timestamp history, budget behavior and observation_score match
  historical CadenceController Age5 exactly, including cap-stop behavior.

If a request is delayed at t, the NEXT decision must be t+1 and must request
regardless of changed pose/route/Age5 score, if budget remains and episode has
not ended. It cannot be delayed again. A new later request may independently
qualify; repeated one-step delays are not assumed episode-wise harmless.
The promise is about a request, not guaranteed freshness of invisible cells.
No omission,10-step fallback, occupancy inference or unselected geometry query.

## Engineering bounds and preservation

At most4096 public grid cells. Score uses bounded radius3 crop. Feature calls
occur only on relevant Age4/Age5 decisions after the first scan and while budget
remains; max1 extra public A*,1 current footprint (61*81 arithmetic samples),
next5 moves with <=200 swept-cell visits by construction. Decision work
O(N log N +4941) including point planning/validation, memory/history O(N),
retained compact logs O(T). Actual observations remain full original61-ray calls.
Baseline timers use the same outer decide/refresh boundaries; Age5 retains
historical unused probability/logging work, so comparisons are API timings.

Original G1 forward-first planner, seed42, H80, paid cap20, emergency safety,
selected-only shield, sensor geometry and original admitted36 mazes×two schedules
are unchanged. New safety candidates from earlier tasks are NOT used. Correctness
covers exact disabled Age5 parity, early guard conditions, one-step promise,
first-scan protection, authorization/empty reads/cap, deterministic replay,
bounded computation and no forbidden input dependencies.

## Prospective matrix, gates and analysis

Six arms: Periodic4, Age4, frozen Age5, RAA-Advance, RAA-Defer, RAA-Joint.
Run two original sorted FIT cases×6 arms (12 smoke episodes), require all three
reference semantic/metric parities, zero contacts, actual memory calls exactly
matching trace grants, cap/shield invariants. Then72×6=432 full episodes once,
with first-two smoke parity and216 exact reference reproductions. The full
matrix records ALL negative outcomes. No reserved or sealed access.

Freeze source/protocol/gate fingerprints in git BEFORE new-policy navigation.
Only saved prior evidence informs this initial rule; no candidate sweep.

Primary owner's target: zero contacts and either >66 goals OR66 goals with paid
scans below both Periodic800 and Age850. Additional immediate task target:
>=67 goals OR66 with <=769 scans (stronger than frozen Age5's770). Explicitly
report both. Desired stronger joint outcome: completion preserved/improved,
fewer paid AND combined rays, and non-increased paired common-success steps/
distance (at least one strict movement improvement). Failure-shortened paths
never count as better navigation. No novelty/superiority/generalization claim
from this repeatedly reused development set.

Report goals/contact-free goals, rescue/harms versus each reference, paid and
actual emergency calls/rays, combined rays, H80, blocked/rejected actions,
interventions, memory errors, common-success steps/distance, scheduler/update
and wall time, advance/defer/forced counts and invariants. Predeclare comparisons
of each3 candidate versus each3 references (9). Report whole-maze bootstrap2000
resamples, seed2026111602, keeping both schedules together; intervals are
exploratory development descriptions, not independent efficacy inference.

If no first-family candidate meets the immediate target, the user explicitly
authorizes ONE bounded revision based on saved failure/activation evidence,
with separate source/protocol/output and a fresh prospective freeze before
smoke/full. No maze-ID features, arbitrary threshold sweep or third iteration.
Retain v1 even if rejected. An immediate-target success ends algorithm revision;
stronger negative findings remain visible. Production cohorts and safety
protocol changes remain outside this task.
