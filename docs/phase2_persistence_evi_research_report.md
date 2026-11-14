# Persistence memory B and approximate EVI C: implementation and engineering report

2026-11-13. Branch `phase2/mujoco-proxy-pilot`.
**Status: implemented; synthetic G1 integration executed; FIT72 replay blocked
by missing existing data stores; independent hypothesis evaluation not performed.**
No superiority, calibration, novelty or generalization claim is supported.

## Delivered implementation and safety boundary

- `src/spatial_memory/persistence.py`: asymmetric observation-history occupancy
  prediction, conservative public-grid projection, separate inference ledger,
  endpoint transitions/exposures, pre-observation Brier/log-loss/reliability bins.
- `src/spatial_memory/evi.py`: bounded memory-ray footprint, public-grid
  counterfactual navigation-regret estimate, sensing/compute/scarcity prices,
  explicit defer decision, paid refresh authorization and scan-outcome logging.
- `src/spatial_memory/evaluation.py`: three opt-in lines deliver only the goal,
  current heading and existing unknown-cell planning mode before `decide`.
  Pose already belongs to `decide(step, position)`. Existing controllers do not
  implement the callback and follow their original path.
- `scripts/evaluate_persistence_evi_fit72.py`: five-arm paired runner, exact
  baseline metric/semantic-trace checks, admitted-world loader, preserved-prefix
  verification, exclusive directories, per-episode evidence and source metadata.
- `scripts/smoke_persistence_evi_mujoco.py`: isolated synthetic integration
  harness, explicitly outside the Phase1.5 population and admission process.
- Two test files cover model histories, inference accounting, uncertainty,
  footprint/range/FOV, bounded plans, defer decisions, budget scarcity, refresh
  authorization, callback restoration and actual G1 sensing/shield integration.

The authoritative G1 model, kinematic-root movement, original paid 61-ray
sensor (6m / 120 degrees), independent 61-ray emergency sensor and selected-only
true-geometry shield are unchanged. Counterfactual A* never calls the shield.
The new controllers receive no scene, world, future schedule, hidden occupancy,
object categories, emergency measurement or evaluator-only labels. The shared
cap20 includes the initial scan; inference does not charge an observation.
Original G1 perception/tracking callbacks retain their existing behavior.
No RDAO or Event implementation, frozen result or Phase1.5 population was edited.

## B: assumptions and mathematics

The state is last observed occupancy z and time t, observed endpoint transition
counts n01/n10 and previous-state exposure T0/T1. Hazards per navigation step are

    a = clip((.3+n01)/(30+T0), .001, .35)
    b = clip((.3+n10)/( 6+T1), .001, .35)
    pi = a/(a+b)
    p(s) = pi + (q-pi) exp(-(a+b)(s-t))

q=.95 for an occupied observation and .05 for free. Never observed cells retain
p=.5 and public unknown status. Exposure belongs to the *previous* observed
state, and changes are counted only across two paid observations. Equal
endpoints can conceal multiple flips; these are approximate endpoint hazards,
not an exact continuous-observation estimator. Survival confidence exp(-8b)
measures model occupancy persistence over eight steps, not furniture identity.

Known p<=.2 becomes free, p>=.8 becomes occupied, intermediate belief is unknown.
A cell last observed occupied is conservatively kept occupied while p>.2.
This hysteresis can retain false obstacles. Conversely, the free-biased prior
can eventually erase a real wall without a new observation. Neither behavior
is hidden: inference changes are separate from observed updates. Unknown
handling remains the original optimistic/blocked planner mode and is logged.

B-only composes the ORIGINAL Age scheduler using its independent last-write
history and timestamps. This isolates the belief representation from a change
in sensing schedule. B+C replaces that scheduler with C.

## C: formulation, approximations and costs

The public-memory footprint traces exactly 61 angular hypotheses within the
configured range and FOV, stopping at remembered occupancy. These are arithmetic
ray paths on memory, not actual or shadow sensor calls. Unknown-space occlusion,
site offset, vertical geometry and future visibility are approximated.

At most three visible uncertain cells are shortlisted by uncertainty and route
proximity. For each, two public A* plans correspond to free/occupied revelation.
For route r and cell outcome o, surrogate loss L(r,o) is route length plus an
80-step penalty if an occupied candidate lies on that route; no route costs80.
With current cell probability q,

    V = min_r E_o[L(r,o)] - E_o[min_r L(r,o)].

The implementation computes this two-route value for each shortlisted cell,
selects the greatest delay regret (ties prefer greater V), and does not add
values across dependent cells. A first-action disagreement between outcomes
assigns one-step delay regret D=V*min(q,1-q); otherwise D=0, so scanning waits.
The residual V-D is assumed recoverable later. Scan now iff

    D > .5 + .01*(number of plans) + .5/(remaining paid budget).

At most seven plans are made per scheduler decision. A separate post-scan plan
logs realized route change. These prices are predeclared engineering assumptions,
not empirically calibrated movement/compute equivalences. Wall time is measured
but does not affect decisions. C-only uses the original ternary map and a fixed
symmetric age-decay probability (.95 confidence, rate .05); B+C uses B's p(s).

This is **approximate information value**, not mathematically calibrated EVI.
The action set omits arbitrary G1 actions; public A* uses a point-robot route
proxy, even though the actual planner/shield still use G1 geometry. The model
considers single-cell perfect revelation, and the shortlist can miss important
uncertainties. No-route penalties and cell independence are strong assumptions.
A positive V alone does not trigger a scan: delay regret must exceed costs.

Predictions are linked by step to actual scan outcomes, map changes, public-route
and first-action changes, and the subsequent executed G1 action/outcome trace.
Temporal action changes and route-length changes are explicitly proxies, not
causal realized utility. A no-scan trajectory is not observed in the same run.

## Parameters, protocol and leakage controls

The protocol is `docs/phase2_persistence_evi_protocol.md`, written before any
candidate evaluation. Priors, thresholds, costs and shortlist size were chosen
as simple dimensional assumptions, without FIT-world optimization. Initial
unit-test expectations and serialization/API defects were corrected; no model
threshold or cost was changed in response to navigation outcomes. A later audit
correction connected the existing evaluator-only `map_errors` counters; it did
not change online inputs or policy decisions.

All configuration/source hashes, Python/dependency versions and dirty-source
status are saved. Final smoke algorithm source commit:
`4a9238398abf1466aee83177dfc46511a35f7d5e`.
The preceding implementation commit is `ebf7e06`.

## Executed G1 synthetic integration results

Authoritative output: `results/phase2_mujoco/persistence_evi_synthetic_smoke_v4/`.
One predefined open-room development fixture with a moving pedestrian and one
obstacle; seed42, H80, same G1 setup, five configurations. This is a unit-scale
engineering fixture, **not an admitted maze, independent cohort or baseline
reproduction**. All five reach in 8 steps / 6m, with 0 unwanted contacts,
0 blocked attempts, 0 emergency interventions and 0 unselected shield queries.
Every arm uses 8 independent emergency scans / 488 emergency rays.

| Arm | Paid scans | Memory rays | False-persistent cell-times | Scheduler ms |
|---|---:|---:|---:|---:|
| Periodic | 3 | 183 | 3 | not instrumented |
| Age | 3 | 183 | 3 | not instrumented |
| B + original Age | 3 | 183 | 3 | 0.512 |
| C + ternary | 1 | 61 | 7 | 19.037 |
| B+C | 1 | 61 | 7 | 18.721 |

The original evaluator's false-persistence metric sums occupied memory cells
attributed to an observed pedestrian after it has departed, excluding persistent
geometry. It includes initial-frame accounting and is not an object classifier.
C and B+C retain more stale transient occupancy here despite fewer scans. They
do not improve movement cost in this fixture. B makes no inference-only grid
changes during this short episode and shows no contribution to navigation.
All arms have 0 missed-change cell-times, but the fixture contains no persistent
geometry relocation: that zero does **not** test adaptation to moved furniture.

C-only and B+C each execute 56 counterfactual/nominal plans over 8 decisions,
with 0 noninitial scans. Thus their post-scan realized-value mechanism is NOT
exercised in this fixture; a dedicated controller unit test exercises an actual
authorized refresh when a nearby uncertain bottleneck changes navigation choice.
The synthetic counterfactual computation is around2.3ms/decision here; this is
one run without a performance benchmark distribution. B-only is about0.064ms
per decision. Baseline scheduler overhead was not instrumented, so no precise
overhead ratio is claimed. Total safety sensing is much larger than paid memory
sensing for C here and remains separately reported.

B-only pre-scan calibration has 63 policy-selected cell readings: Brier .082518,
log loss .277782. B+C has no postinitial observations and hence **no calibration
samples**, not perfect calibration. These selected samples do not establish
whole-map calibration or B's superiority to Age/last-write. The paired FIT
runner records all three predictions at identical authorized scan cells for a
future fair descriptive calibration comparison.

## Tests and failures

New tests pass, including actual MuJoCo integration for B-only/C-only/B+C.
The final saved broad regression run has 137 passed / 1 failed; the separate
24-test B/C run passes in full. See the saved validation commands/JUnit/logs for exact counts.
The broad run includes frozen Event and RDAO v1/v2/v2.1/v2.2 tests and G1
sensor/emergency/shield tests. It is not the entire repository test suite.

The pre-existing failure is
`test_multiray_181_matches_saved_sensor_observations_and_reference_intersections`:
its original admitted-world loader raises FileNotFoundError for
`results/raw/phase15_macos_development/fit/records`.
The same failure was reproduced after loading `evaluation.py` from original
commit `9fe33e4d13b526f7ed786772e4821ecab5c5983b` into the test process.
The unchanged loader/test thus fail independently of the new context callback.
No xfail/skip or integrity bypass was added.

Earlier smoke attempts are retained: v1 failed at safety-sensor constructor
argument selection; v2 failed serializing an ndarray after the first episode;
v3 completed before connecting evaluator-only memory error columns. v4 is the
final complete run. Do not treat incomplete attempts as completed studies.

## Restored FIT72 evaluation and independent-evaluation limit

The earlier smoke failure was a checkout-path issue, not FIT data loss. The
failed log came from `/Users/masahiro/Desktop/humanoid-spatial-memory`, a
different checkout that did not contain the ignored `results/raw` stores. The
current execution root is
`/Users/masahiro/Desktop/^/31_humanoid/humanoid-spatial-memory`; all three
original stores are present there. The local evaluator resolves them relative
to its repository root, so no absolute path or loader bypass was needed.

Read-only integrity checks passed for 313 original FIT records, 105 first
continuation records, and 2,489 later store records: **2,907 payloads and their
2,907 receipts** matched identities, canonical payload digests, run IDs,
sequence numbers and empty staging directories. The Phase 1.5 protection
manifest rehashed all 836 protected checkpoint/receipt files to its committed
digest. Admission recovered exactly 36 FIT worlds (12 each R/BP/M). Frozen
Phase 2 baseline artifacts and all 288 episode rows loaded and verified.

The two-case smoke passed after a separate evaluator output bug was fixed. The
first local smoke attempt completed both cases but failed while trying to
create the exclusive `pairs.csv` a second time; that incomplete output is kept
and marked in `persistence_evi_fit_smoke_restored_local_v1/`. The runner now
publishes the pair table once after completion. The successful smoke is in
`persistence_evi_fit_smoke_restored_local_v2/`; both Periodic/Age metrics and
semantic traces reproduced for its two keys.

The full paired FIT72 completed all 72 keys × five arms. It reproduced frozen
Periodic/Age metrics and semantic traces for every key before running B, C or
B+C. Results are in
`results/phase2_mujoco/persistence_evi_fit72_restored_local_v1/`; paired
historical comparisons and the descriptive report are in
`results/phase2_mujoco/persistence_evi_fit72_analysis_restored_local_v2/`.
The historical RDAO v1, v1 footprint-only follow-up, v2, v2.1 and v2.2 records
were joined on the same 72 maze/schedule/seed keys. No historical run was
rerun. No B/C algorithm or hyperparameter changed.

This remains a descriptive development result, not independent confirmation.
The saved report gives episode-paired rescue/harm counts and exploratory
cluster-bootstrap intervals that average both correlated schedules within
each maze. No reserved cohort was opened. Independent tests still require
owner-approved generation/admission, lineage-separated development/evaluation
mazes, and sealed evaluation access after policy/source freeze.

## Reproduction and next experiment

This checkout used `.venv/bin/python` (Python 3.12.10), NumPy 2.2.6,
MuJoCo 3.17.0 and pytest 8.3.5. `.venv312` is not present in this checkout.
The direct dependency versions match `requirements.txt`; the FIT run also
passed exact saved baseline metric and trace reproduction. See the result
provenance for source hashes and environment details. Use fresh output paths;
the evaluation refuses to overwrite existing result directories.

```sh
.venv/bin/python -m pytest tests/test_persistence_evi.py \
  tests/test_persistence_evi_evaluation.py -q

.venv/bin/python scripts/evaluate_persistence_evi_fit72.py --max-cases 2 \
  --output results/phase2_mujoco/persistence_evi_fit_smoke_restored_local_v2

.venv/bin/python scripts/evaluate_persistence_evi_fit72.py \
  --output results/phase2_mujoco/persistence_evi_fit72_restored_local_v1
.venv/bin/python scripts/analyze_persistence_evi_fit72_restored.py
```

The FIT runner reproduces frozen Periodic/Age metrics and semantic traces for
each key before its B/C candidates. It checks cap20, exact scan-log accounting,
selected-only shield calls, evidence hashes and prefix integrity, saves source
hashes, then
writes paired primary metrics/common-success travel, emergency channels,
calibration, memory errors and predicted-versus-realized proxies.

Next: restore the exact FIT stores and run this frozen implementation without
parameter adjustment for a descriptive engineering check. Then authorize an
independent cohort with explicit persistent-change and transient-occlusion
coverage, compare B against Age/last-write at matched scan cells and against
matched observation histories, and assess B/C/combined contributions separately.
Reject C/combined efficacy unless they reduce observations AND common-success
movement cost without sacrificing safety/completion. B's persistence/calibration
hypothesis likewise needs independent labelled evidence. The present results
neither confirm nor reject these scientific hypotheses; they validate limited
implementation paths and expose the sensing-versus-stale-memory tradeoff.
