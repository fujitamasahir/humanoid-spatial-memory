# Phase 1.4A implementation validation

Executed 2026-11-06 on macOS / Apple Silicon with Python 3.12.16 and the existing
pinned requirements, using `/tmp/phase13-venv`. Branch:
`feature/phase1-4a-implementation`, from freshly fetched
`origin/feature/phase1-4-research-design` (`1a15213208df83bf0e025977d643b6a9a056968b`).
The user's Phase 1.4A instruction authorizes implementation of the three frozen
research documents; their earlier review-gate statements remain archival and
unchanged. This phase stops before tuning, assessment, held-out evaluation or MuJoCo.

## Implemented scope

All twelve method IDs: `static`, `age`, `uncertainty`, `periodic1`, `periodic2`,
`periodic5`, `fixed-rate`, `random-quota`, `quota-periodic`, `route-weighted`,
`disruption-visible`, `query-gate-conceptual`. The last is a simplified conceptual
control, **not a faithful ALONE reproduction**. No thirteenth published-method
slot was invented. No performance, novelty or physical safety claim is made.

All six disruption-visible ablations are implemented as single switches:
`no-route-disruption`, `no-visibility`, `fixed-rate`, `exclude-unknown`,
`no-budget-threshold`, `no-alternative-candidates`. Unit tests compare candidate
components, counterfactual costs, risks, visibility, thresholds and unchanged memory
against the parent policy. Smoke uses frozen defaults for parent and ablations;
no parameters were selected or retuned. A future selected parameter object can
be supplied unchanged to the same public controller.

`task_policies.py` accepts only initial ternary observations, goal, radius, public
model parameters, observation cost, cap and precommitted own schedule. Subsequent
inputs are time, pose and returned observations. Root environment seeds are used
only by the evaluator to create the random schedule with
`SeedSequence([seed,1404,replicate])`, then withheld from policy objects. Sensor
noise retains the original per-time `SeedSequence([seed,time])`. No World,
Scenario, future event, actual revealability label or manifest is a policy input.

Legacy schedules delegate to unchanged `ObservationController`/baseline code.
New heuristics use strict `>` for score thresholds, including fixed-rate under
protocol §2; historical Age/Uncertainty retain `>=`. Query confidence masking uses
`<`, its visibility fraction uses `>=`, and disruption visible mass uses `>= .25`.
A cap includes initialization. Requests are still calculated after exhaustion;
denial never invokes the sensor or resets timestamps. Candidate enumeration is
lexicographic (x,y); float64 score accumulation, unique supercover intervening
cells, N+1 no-route penalties, two forced occupancy states and current-cell
exclusion follow the frozen definitions. Unknown ray blockers remain .5 in the
exclude-unknown ablation. No route repair, cooldown, learned model, forced refresh,
physical collision rule or method-specific motion controller was added.

## Evaluation and data boundaries

The existing episode harness has optional injected controller/planner and an
observer callback; default calls preserve all previous behavior. `protocol_evaluation.py`
passes an allow-list into the public controller and records only actual granted
noninitial observations for feasibility labels. Callback labels are retained by
the evaluator, never appended to policy inputs or decisions. Complete traces
include pre-sensing components, nominal/masked routes, per-candidate risks/costs,
predicted visibility, reasons, score/threshold, budget, grants/denials, received
observations, remembered maps, evaluator truth, movement and legacy errors.
Truth and labels are explicitly evaluator-side fields, separate from `policy_details`.

Per-decision monotonic wall-clock timing records scheduler latency, scheduler A*
calls/time, and common motion-planner calls/time (including initialization).
Episode totals, medians and 95th percentiles are included. Visibility diagnostics
for historical, quota, fixed-rate and route-weighted policies are timed separately
so diagnostic ray calculations do not inflate their scheduler complexity. Full
synthetic runtime estimates include that overhead. Neither timing nor instrumentation
changes simulated time, map writes or observation decisions.

Feasibility metrics include Brier score, MAE, fixed five-bin calibration, and
unknown-versus-all-known ray-blocker strata. Labels are the returned observation's
nonnegative-cell mask, independent of observed occupancy noise. No sensor is called
at denied/unsensed steps for hypothetical accuracy labels. Empty groups are reported
as absent; no samples gives null error. Sensed-only calibration is selection-biased,
and cell samples are not independent experimental units. No inferential comparison
is made from the smoke data.

`manifests.py` canonicalizes static cell sets and hashes geometry, start/goal,
obstacles, ordered pedestrian paths and events, excluding family/name/seed/split
labels. Layout hashes include dimensions/walls/start/goal only. Historical development
realizations/seeds are excluded; no reserved held-out file is read. The ascending
10000/20000 seed searches, 10,000-candidate limits, evaluator-only persistent
reachability audits and logged rejection reasons implement the frozen protocol.
Thirty-five tuning and seventy assessment records were generated, validated,
and stored **without executing any policy on them**. Full manifests have 105
unique environment hashes and disjoint partitions; their hashes/topology reproduce.
They contain no policy outcomes or selected parameters. Related topologies may
remain, as permitted by the protocol; this is realization separation, not a new
claim of topology-disjoint generalization.

The CLI exposes only manifest generation and bounded smoke. Manifest records
marked tuning/assessment are rejected by the smoke loader; the protocol episode
entry point rejects those purposes, held-out splits and reserved seed namespaces.
A future authorized matrix runner, parameter lock and clustered outcome analysis
remain outside this phase. These are application execution guards, not a claim
of a security sandbox against arbitrary Python callers who rewrite labels/code.

## Tests and regression

**175 tests passed, 0 failed**, with 14 existing Matplotlib/pyparsing deprecation
warnings. The complete suite includes independent formula checks, exact threshold
boundaries (including .25 visible mass), fixed versus adapted rates, every method
under cap1, cap accounting and refresh denial, reproducible quota schedules,
unknown/no-route/occupied-goal counterfactuals, occlusion predictions, ablation
isolation, runtime and A* count accounting, feasibility arithmetic, canonical
hashes, manifest uniqueness/topology, partition guards, paired noisy initial
views, deterministic non-timing traces, explicit public-input checks and hidden
changes outside sensing range producing identical public decisions.

Every stored metric in **2,212 historical episode records** is checked:
Phase 1.0 representative 6; Phase 1.1 development/diagnostic 54; Phase 1.2 288;
Phase 1.3 robustness 1,792 and corridor diagnostic 72. These are regression replays
of already observed development data, not new tuning/assessment evidence or
independent research samples. All historical result/configuration files, frozen
Phase 1.4 documents and baseline/sensor/planner/simulator source match the base
branch byte-for-byte in Git. Only evaluator injection hooks affect an existing
source file. Wrapper-specific tests additionally match historical movement and
metric behavior for all six legacy method IDs.

## Limited smoke execution

Final retained smoke: **36 episodes** = two development realizations × (twelve
core methods + six ablations), cap4, radius3, occlusion on, noise .05, T=40,
random replicate0, default parameters only. Families/seeds: occluded/6101 and
 detour/6102. The exact config is `configs/development_phase1_4a_smoke.json`.
There were **72 smoke episode executions total** across an initial debugging run
and the final rerun after instrumentation/serialization changes; only the final
36 are retained. Synthetic unit-test episodes and historical regression replays
are counted separately, not represented as smoke replications.

All methods and ablations execute, costs/caps and traces reconcile. Smoke outcomes
are debugging artifacts only; there is no success leaderboard, parameter selection,
confidence interval, novelty conclusion or general performance claim. The runner
limits smoke to two worlds/40 steps and prohibits the tuning/assessment namespaces.

## Computational feasibility: measured synthetic decisions

Six public-memory workloads: known open, partly unknown, two passages, no route,
cluttered and a separately labeled larger-map/radius5 stress case. Grid shapes
range from 13×9 to 31×21. Frozen-matrix cases use radius3. Three age/budget
contexts (step1/cap4, step10/exhausted cap1, step30/unlimited), eight timed fresh
controllers each, all twelve methods/six ablations. One untimed synthetic warm-up
per method/ablation, single process, no rendering. No policy ever observes a
synthetic future event or assessment state.

The final benchmark contains **2,592 timed decisions**; two benchmark executions
totaled 5,184 timed decisions, with only the final run retained. Each table cell
below is median / 95th-percentile **scheduler milliseconds** across 24 repeated
synthetic samples. These percentiles describe runtime variability, not confidence
intervals over independent navigation tasks.

| Public-memory workload | Route-weighted ms | Disruption-visible ms | Query-gate-conceptual ms |
| --- | ---: | ---: | ---: |
| known-open | 0.056 / 0.063 | 1.006 / 1.066 | 0.139 / 0.156 |
| partly-unknown | 0.066 / 0.077 | 1.261 / 1.349 | 0.148 / 0.162 |
| two-passages | 0.158 / 0.166 | 5.957 / 6.072 | 0.242 / 0.343 |
| no-route | 0.140 / 0.144 | 5.222 / 5.327 | 0.213 / 0.306 |
| cluttered | 0.119 / 0.128 | 2.637 / 2.787 | 0.204 / 0.236 |
| large-radius-stress | 0.148 / 0.178 | 5.598 / 5.743 | 0.418 / 0.485 |

Scheduler A* invocation counts: Route-weighted **1** per decision; conceptual
query gate **2**; Disruption-visible **57** at full radius3 disks (1 nominal +
2×28 candidates), **161** for radius5 stress (1 + 2×80). Each has one additional
common motion-planner invocation after the decision, plus one at initialization.
Denied budget requests still incur the frozen decision computation. No caching,
pruning, approximate planning or other acceleration was introduced.

Full 18,900-episode workload accounting is explicit: 3,780 tuning + 13,440
assessment + 1,680 ablations. Method-specific episode counts in benchmark JSON
include five random replicates per assessment condition, rather than treating
all twelve methods as having equal repetition counts. The estimate weights each
method/ablation's measured outer decision plus common A* time, with extra per-step
world/observation/metric overhead measured from smoke. No assessment outcome or
parameter winner was used to estimate runtime.

| Runtime scenario | Assumptions | Estimated minutes |
| --- | --- | ---: |
| short-episode-scenario | 8 decisions/episode; workload percentile 50 | 1.80 |
| full-horizon-median-workloads | 40 decisions/episode; workload percentile 50 | 8.99 |
| full-horizon-p95-with-radius5-stress | 40 decisions/episode; workload percentile 95 | 18.83 |

These are **scenario estimates, not statistical bounds or a guaranteed maximum**.
Six synthetic maps cannot identify future workload frequencies, tuned policies'
trajectories, or A* expansion distributions. The short scenario assumes eight
steps, not the assessment's observed durations; the full-horizon scenarios assume
forty. Radius5 stress exceeds the matrix and is labeled separately. CPU contention,
thermal throttling, sensor/capture overhead differences and cold starts add uncertainty.
The estimates exclude future file I/O and full-result JSON serialization.

Complete smoke JSON is approximately 9.9 MB for 1,419 decisions. At the same
logging density, a full forty-step matrix could produce roughly **5 GB of plain
JSON**, before indexing or retained repeats. This is a rough storage extrapolation,
not a proposed new artifact requirement. Serialization/storage throughput must
be reviewed before a large run; any logging/storage change should preserve full
trace semantics. No full matrix was executed merely because the synthetic timing
looks affordable. No algorithm acceleration is proposed or silently applied.

## Reproduction and artifacts

Python 3.12 with unchanged `requirements.txt`. From repository root:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python scripts/run_phase1_4a_validation.py manifests --output results/runs/phase1_4a_manifests
.venv/bin/python scripts/run_phase1_4a_validation.py smoke --output results/runs/phase1_4a_smoke
.venv/bin/python scripts/benchmark_phase1_4a.py --output results/runs/phase1_4a_benchmark --smoke results/runs/phase1_4a_smoke/results.json
```

Actual validation substituted `/tmp/phase13-venv/bin/python` and used
`MPLCONFIGDIR=/tmp/phase13-mpl`, with retained output at `results/phase1_4a/`.
Windows substitutes `.venv\Scripts\python.exe`. Use fresh ignored `results/runs/`
paths to preserve retained artifacts. The runner protects earlier phase paths
and ancestors. Both commands are development-only; neither provides a tuning or
assessment execution mode.

Retained artifacts:

- `manifests/tuning.json`, `manifests/assessment.json`: full evaluator-only data,
  exclusion hashes, topology audits and rejection records, no outcomes.
- `smoke/episodes.csv`, `smoke/results.json`: all 36 final debugging episodes,
  full traces, feasibility samples and source/config provenance.
- `benchmark/latencies.csv`, `benchmark/results.json`: synthetic inputs, all
  2,592 timings/counts, summary percentiles, method-weighted runtime estimates.

Provenance records normalized per-file source SHA-256, a combined source manifest
hash (src/scripts and frozen Phase 1.4 documents), canonical configuration hash,
parameters/configuration, Python/platform and exact installed package versions,
generating HEAD and dirty state. Artifacts were generated before this phase's
final commit; generating HEAD is the research-design parent and dirty=true.
They do not pretend to contain their own final commit SHA. All recorded source
file hashes were recomputed successfully after the final run.

Combined normalized source manifest SHA-256: `b685d2737293bbce6efdbd83cdf17c6cb600d9b72bb835d0e658db6ee7a4f30e`.

Remaining limitations: no faithful ALONE/published-system reproduction; independent
visibility and confidence proxies remain uncalibrated; related topology clusters
may reduce future inferential power; no tuning, assessment or future cluster-CI
analysis has been executed. Full trace storage and actual end-to-end matrix runtime
need review. Known zero sensing latency, point-robot contacts, stale last-write
memory, missing action-feedback inputs and no viewpoint planning are intentional
protocol limits, not physical safety or locomotion evidence.

Stop for review before tuning, assessment, held-out experiments or MuJoCo.
