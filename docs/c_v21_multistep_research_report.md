# C v2.1 bounded multi-step EVI — research report

2026-11-14, `phase2/mujoco-proxy-pilot`, university-library Mac.
**Completed: migration, correctness, synthetic and conformance gates, smoke, full FIT72 and two real-scan contrasts. Joint sensing/navigation improvement was not achieved.**

Algorithm/protocol source was frozen and committed as
`c504a8c7486eb27136fed4ddba8585253a62eb87` before formal synthetic execution.
No policy source, model price, horizon, ranking or fixture was changed after
formal outcomes. This is a kinematic-root G1 study, not physical walking.

## Research question and implemented approximation

The question is when to re-observe so that safety and completion are preserved
while both observation and movement cost decrease. C v2.0d's ranking branch is
closed and preserved. This study tests observation timing on its unchanged
shortlists, rather than another topology-ranking adjustment.

For every shortlisted uncertain cell, use its existing public probability and
two counterfactual public A* routes. Compare now, a fixed blind route prefix
followed by a scan, and continuing without that information. H=3 conceptual
point-grid moves was fixed before the mechanism audit; no FIT horizon sweep.
A future pose/heading and a virtual memory-ray footprint are predictions, never
actual sensor readings. No A* is invoked at future states.

Let L(r,o) be the frozen route-length/80-step failure surrogate. With q the
current public occupancy probability, N=min_r E[L(r,o)] is the no-information
cost and I=E[min_r L(r,o)] the informed movement cost. V=N-I is retained.
For each of two blind routes and h∈{1,2,3}, simulate the prefix in both occupancy
hypotheses, including a blocked-candidate stop. The route/time pair is chosen
before the outcome. If a later scan can reveal the candidate, recover along
reversed prefix edges and the precomputed outcome-optimal route; otherwise
retain the original no-information route loss. This restricted recovery
catalog is exhaustively evaluated, not a global belief-space optimizer.

One scan costs C=.5+.01*(actual scheduler A* calls)+.5/remaining budget.
A=I+C is scan-now cost; B is the minimum delayed movement cost+C.
Authorize now iff min(N,B)-A>0. A zero tie postpones. Thus information with
positive V can still wait if it can be acquired later without extra expected
cost. Values across candidates are never added; the best single net value is
used. Correlated cells remain marginal hypotheses, not an assumed independent
joint distribution. Future probabilities and the rest of memory are frozen
within the lookahead.

The four new arms are the factorial C-K/Topology3-d selector × assumed/predicted
future visibility: `ms_k`, `ms_k_visibility`, `ms_topology`,
`ms_topology_visibility`. Frozen C0, C-K, Topology3-d, Periodic and Age remain
comparators. B/persistence, G1-aware counterfactual planning, event triggers,
new ranking formulas and independent cohort generation are outside scope.

## Interfaces and safety

Dedicated implementations are `multistep_evi.py`, `multistep_reference.py` and
`multistep_review.py`. A scoped factory adapter uses the existing
`PersistenceEVIController.evi_function` hook with persistence disabled. No
existing controller, sensor, planner, shield or G1 asset was edited. Candidate
selection calls the exact frozen uncertainty or Topology3-d selector.

Only public ternary memory/probabilities, authorized timestamps, pose/heading,
goal, sensor geometry and budget enter online decisions. The 61-ray memory
sensor, initial-inclusive cap20, separate independent emergency sensor and
selected-action true-geometry shield are unchanged. Predicted visibility does
not call a sensor; counterfactual plans do not query the shield. Evaluator
memory-error labels and saved comparison trajectories are retrospective only.

## Environment migration and original-assumption audit

The migration report is `c_v21_environment_migration.md`. Python3.12.16 in
`.venv` and all direct pins matched. Mac13,1 / M1 Max /32GiB /10 CPU cores,
macOS26.5.1 were recorded. All 2,907 original checkpoint/receipt pairs, all 836
protected prefix files,36 admitted FIT identities, original evidence manifests
and G1 XML/STL assets passed read-only integrity checks. No additional local
research files were missing or regenerated.

All 360 existing-reference episodes reproduced their saved semantic traces and
metric signatures on this Mac. Baseline schedulers were explicitly timed;
Periodic/Age should not be treated as zero-compute algorithms. Old Mac wall
clock numbers were not used as direct comparators.

The descriptive audit counted140/148/227 positive-V, zero-D decisions in
C0/C-K/Topology3-d respectively. A fixed first-two-per-arm/episode sample had
233 states:225 retained predicted visibility after a shared first move and2
were last-opportunity cases within H. An independent model-only supplement
found4 states with positive minimum modeled postponement movement regret.
These observations motivate distinguishing deferable information from lost
opportunities; they do not justify scanning every stale/uncertain region or
prove that any unexecuted scan rescues navigation. Candidate omission and a
shortlisted value/timing failure are separate mechanisms. See
`c_v21_one_step_delay_audit.md` and its saved public-state evidence.

## Correctness, prospective fixtures and conformance

145 focused tests passed, with0 failures. These include1,296 exhaustive small
public-grid conditions, independent ray arithmetic and BFS path certificates,
randomized exact frozen-selector parity, existing G1/emergency regressions,
cap checks, integration restoration and isolated reviewer fault injections.
The new C v2.1 test files contain22 tests; no formal fixture was used to develop
policy behavior. The test command/JUnit are saved under `correctness/`.

The 96 prospective public-memory fixtures cover12 families ×8 conditions:
immediate divergence, shared prefixes, future branches, last chance, continued
visibility, permanent occlusion, occupied shortcut, irrelevant uncertainty,
no benefit, correlated cells, competing candidates and size/heading/range
variation. Padding/rotations, probabilities, ranges and annotations were frozen
before formal policy execution. Two pre-policy annotation artifacts are kept:
the second adds stronger valuable-information/continued-visibility checks and
full state diagnostics. The fixture population digest is unchanged between
them. The binding commits the second artifact; no fixtures were replaced.

The formal run executed all 7 synthetic arms once under the declared protocol,
including predeclared timing repetitions. Numeric gate: PASS. A new process
independently reconstructed the reference values, delayed poses/headings,
visibility, selector parity, counters, source/artifact hashes and annotations:
ACCEPTED_FOR_FIT. Maximum scalar difference was0. Both visibility-aware arms
scanned in all16 designated last-chance/shortcut positive cases; matched
no-visibility arms scanned in 0. No postpone/no-benefit/occluded control scan
was authorized. All four new arms had 0 reference false positives and0 reference
false negatives in this finite suite. This validates the intended restricted
mechanism, not calibrated EVI, independent navigation benefit or global
candidate-selection adequacy.

The independent reference/reviewer uses separate code and a separate process;
it is not external human peer review. It shares only frozen planner semantics
and a separately implemented numerical footprint. Its oracle exhausts the
specified two-route/prefix catalog, not every possible belief-state action.

## Resource limits and measurement scope

With K=5 or3, H=3, each EVI decision uses at most11/7 A* calls (one nominal,
two per candidate), and0 future-state A* calls. Footprint computations are at
most61/37 including the current view. Prefix visits are at most120/72;
recovery membership checks at most180/108. Counterfactual copying is2KN cell
reads. All named counters stayed within their declared bounds; unlike work
categories were not combined into an invented scalar.

The full scaling includes grid validation, ranking, A*, grid copies, paths and
ray samples: O((1+2K)A(N)+selector(N,V,E,M,L)+(1+4KH)RS+KN+KH²), using the
conservative frozen A* bound A(N)=O(N² log(N+1)). The K5 rank stage uses a
one-cell fallback when its nominal path is empty; equivalently write its term
as O(M*max(1,L)+M log(M+1)). O(RS) also covers the visible candidate filter.
Hash lookup costs use the ordinary expected O(1) coordinate-key assumption.
Auxiliary memory includes O(N+E+M+KN+KH*min(N,RS)), not merely O(KH).

Scheduler timings exclude sensing/refresh and normal G1 planning; episode wall
time includes the whole pipeline. One existing post-scan point plan for logs
is outside the scheduler A* ceiling. Per-call Python allocation peaks and
macOS process peak RSS are separate measures. Untraced synthetic timing calls
are used for latency; the first formal calls were allocation-instrumented.
The future-visibility CPU cost is bounded/measured but has no additional fitted
price in the preserved A*-based cost proxy. Fixed arm order, OS/browser load,
thermal state and one-host measurements limit timing interpretation.

## Same-machine synthetic computation and reporting caveat

| Arm | Median ms | p95 ms | Peak traced bytes |
|---|---:|---:|---:|
|C-K|0.710|0.894|5124|
|C-Topology3-d|0.821|1.018|33243|
|C0|0.708|0.911|5069|
|ms_k|0.742|0.926|12221|
|ms_k_visibility|3.300|5.138|15591|
|ms_topology|0.855|1.050|26308|
|ms_topology_visibility|3.435|5.252|23340|

The no-visibility ablations correctly defer when they assume later information is
available. Their zero false-negative counts against that ASSUMED-availability
oracle must not be compared directly with a visibility-aware oracle. The
frozen analysis retains those per-ablation diagnostics, but its first plot
panel is not an apples-to-apples cross-ablation comparison. An additive,
explicitly post-run reporting supplement uses the same future-visibility
reference for every arm: C0/C-K/Topology3-d and both no-visibility multi-step
arms miss36/96 authorizations; both visibility-aware arms miss0/96. All have
zero false positives. See `reporting_checks/common_visibility_oracle.json` and
`synthetic_common_reference.png`. This reporting correction changes neither
the formal gate, fixtures, policy source nor navigation results; original
artifacts are preserved. No calibrated real-world optimality follows.

Some generic legacy CSV columns (`evi_*`, or a zero fallback for copy reads)
were designed for one-step C and are not valid interpretations of the new
formula. The direct multi-step decision fields and the additive
`reporting_checks/verification.json` counters are authoritative. This is a
reported schema limitation, not a policy or outcome repair.

## Executed descriptive navigation results

The 2-key smoke passed all 8 new-arm episodes. Its metrics/semantic traces were
reproduced by the first two keys of the single full 72-key ×4-arm run. All
references are the360 exact same-machine replays above. Contact-free goals
equal goals and unwanted contacts are0 for every arm. These 36 reused mazes
with two correlated schedules are development material, not independent tests.

| Policy | Goals/72 | Mean paid scans | Mean H80 steps | Mean combined rays | Scheduler ms/episode | Wall seconds/episode |
|---|---:|---:|---:|---:|---:|---:|
|periodic|66|11.111|42.208|3252.5|0.07|0.182|
|age|66|11.806|40.486|3189.8|1.17|0.153|
|C0|46|5.375|53.306|3579.5|152.48|0.340|
|C-K|54|6.292|51.139|3503.3|151.50|0.334|
|C-Topology3-d|52|8.417|49.681|3543.9|288.36|0.476|
|ms_k|57|15.708|45.194|3715.1|99.35|0.272|
|ms_k_visibility|57|15.778|45.153|3716.8|603.97|0.775|
|ms_topology|57|15.792|44.333|3667.6|212.34|0.384|
|ms_topology_visibility|57|15.792|44.333|3667.6|712.34|0.885|

Every arm preserves cap20 including initialization. The ray counts below are actual authorized paid-memory rays and independently logged emergency rays; they are never conflated. Memory errors are the unchanged evaluator-only cell-time sums, not online class labels.

| Policy | Memory scans/rays | Emergency scans/rays | Blocked actions | Emergency interventions | False-persistent cell-times | Missed-change cell-times |
|---|---:|---:|---:|---:|---:|---:|
|periodic|800/48800|3039/185379|47|7|64|5850|
|age|850/51850|2915/177815|36|5|62|5611|
|C0|387/23607|3838/234118|511|40|19|8072|
|C-K|453/27633|3682/224602|434|40|19|7626|
|C-Topology3-d|606/36966|3577/218197|331|17|23|7102|
|ms_k|1131/68991|3254/198494|247|22|23|6669|
|ms_k_visibility|1136/69296|3251/198311|250|22|23|6711|
|ms_topology|1137/69357|3192/194712|225|19|8|6253|
|ms_topology_visibility|1137/69357|3192/194712|223|19|8|6252|

### Paired comparisons and correlated schedules

The following means use only episodes where BOTH policies reach the goal. Rescue/harm counts include all 72 paired keys. Bootstrap intervals resample whole maze clusters2,000 times (seed2026111402), with both schedules together and common-success denominators recomputed. They are exploratory descriptive intervals on reused FIT data, without multiplicity adjustment or a generalization claim.

| Candidate vs reference | Rescues/harms | Common successes | Mean steps ref→new | Mean distance ref→new (m) |95% cluster interval, step delta |
|---|---:|---:|---:|---:|---|
|ms_k vs C-K|4/1|53|40.792→35.925|19.868→18.821|[-8.467,-1.722]|
|ms_k_visibility vs C-K|4/1|53|40.792→35.849|19.868→18.821|[-8.543,-1.754]|
|ms_topology vs C-Topology3-d|5/0|52|38.019→33.923|19.082→18.043|[-7.064,-1.695]|
|ms_topology_visibility vs C-Topology3-d|5/0|52|38.019→33.923|19.082→18.043|[-7.064,-1.695]|
|ms_k_visibility vs ms_k|0/0|57|36.035→35.982|18.829→18.829|[-0.222,0.051]|
|ms_topology_visibility vs ms_topology|0/0|57|34.947→34.947|18.513→18.513|[0.000,0.000]|

All four new arms fail the predeclared joint navigation-benefit criterion.
K-based multi-step adds678/683 paid scans relative to C-K while rescuing4 and
harming1 episode. Topology-based multi-step adds531 scans while rescuing5 and
harming0 episodes relative to Topology3-d. Common-success steps and distance
improve versus those frozen selectors, but completion remains below the
66/72 Periodic/Age baselines and sensing workload rises. The larger scan dose
is not evidence of better selective efficiency.

Adding future visibility to ms_k changes no goal outcomes, adds 5 paid scans,
reduces total H80 steps by 3 and changes common-success distance by0. Combined
rays increase 122. Adding visibility to the topology arm changes no goal,
common-success step or distance outcomes and no total scan/ray workload;
minor failed-trajectory differences must not be promoted as route-efficiency
gains. Future visibility adds roughly0.5 seconds of scheduler CPU per episode
in both selectors. Synthetic accuracy did not translate into a useful joint
navigation benefit in this reused cohort.

## Actual information diagnostics and computational workload

The following counts use scored decisions only for V/delay means; budget-skipped
decisions are not treated as zero-valued observations. `A*` counts are the
scheduler, excluding the existing normal G1 and post-scan logging planners.

| Arm | Scored/budget-skipped decisions | Scheduler A* calls | Current+future footprint calls | Future calls | Grid-copy cell reads | Mean V / movement delay |
|---|---:|---:|---:|---:|---:|---|
|ms_k|2555/699|27981|2555|0|15891250|1.7707/0.2112|
|ms_k_visibility|2550/701|27926|19894|17344|15860000|1.7790/0.1254|
|ms_topology|2586/606|18102|2586|0|9697500|1.6707/0.2107|
|ms_topology_visibility|2583/609|18081|20351|17768|9686250|1.6624/0.1579|

Authorization categories and actual selected-target observations are preserved:

- **ms_k**: {"budget_exhausted": 699, "no_information_is_cheaper": 1313, "postpone_without_extra_expected_cost": 183, "scan_avoids_lost_opportunity_or_delay": 1059}. Of1059 real postinitial scans, the predicted target was observed at988 and returned unknown at71.
- **ms_k_visibility**: {"budget_exhausted": 701, "no_information_is_cheaper": 1313, "postpone_without_extra_expected_cost": 173, "scan_avoids_lost_opportunity_or_delay": 1064}. Of1064 real postinitial scans, the predicted target was observed at983 and returned unknown at81.
- **ms_topology**: {"budget_exhausted": 606, "no_information_is_cheaper": 1333, "postpone_without_extra_expected_cost": 188, "scan_avoids_lost_opportunity_or_delay": 1065}. Of1065 real postinitial scans, the predicted target was observed at978 and returned unknown at87.
- **ms_topology_visibility**: {"budget_exhausted": 609, "no_information_is_cheaper": 1336, "postpone_without_extra_expected_cost": 182, "scan_avoids_lost_opportunity_or_delay": 1065}. Of1065 real postinitial scans, the predicted target was observed at971 and returned unknown at94.

The selected-target misses show that the current public-memory footprint is
already imperfect under the actual3D sensor/occlusion geometry. They do not
validate or falsify future visibility where no actual reading exists. Unknown
future observations remain missing evidence. V/net values are not calibrated
realized utility; actual map/route/action changes are logged separately.

The full288-episode new-policy process took186.96 seconds, peak process RSS
857,948,160 bytes; the smoke took6.34 seconds with peak796,934,144 bytes.
These include model loading/pipeline/storage and are not algorithm-only memory
or latency. Baseline whole-episode compute differences can reflect different
trajectory lengths and early budget exhaustion, not intrinsic algorithm speed.
Same-state untraced synthetic timing is the cleaner algorithm comparison.

## Predeclared actual-scan timing intervention

The lexicographic rule selected BP:80010004, schedules0 and1, step10, K-based
visibility arm, with7 paid observations already used. They are ONE maze with
two correlated schedules, not two independent replications. The untreated
replays matched the entire saved traces. Suppressing the step10 grant and
forcing one actual61-ray scan at step11 preserved the entire predecision
trace and the original sensor, cap and safety pipeline. Both contrasts were enacted.
No hidden occupancy or readings from another trajectory were injected.

In both schedules, scan-now reached at step25 and delayed-scan at27, both
using20 total paid scans,14.25m travel,0 blocked actions,0 interventions and
0 unwanted contacts. The first action/pose/heading difference was step12.
Combined rays were2745 now versus2867 later because the delayed trajectory
required two extra emergency scans. Thus sensing timing causally changes
navigation steps in this selected maze, but does not rescue a failure or
reduce movement distance here. It does not prove that future loss of the
specific target's visibility caused the effect: target-matched future readings
were not collected for every hypothetical option. The intervention is small,
selected and descriptive; it cannot validate a generalized online schedule.

## Gate decisions, limitations and recommended next step

- Environment integrity and all360 frozen reference replay checks: PASS.
- Correctness:145 tests passed,0 failed; no pre-existing failures remained after
  the original stores were transferred.
- Formal96-case,7-arm synthetic numerical gate: PASS.
- Independently invoked conformance/reference review: ACCEPTED_FOR_FIT.
- Two-key new-policy smoke: PASS; full matrix:288 episodes completed once.
- Real-scan causal study:2 enacted schedule contrasts from1 maze, full untreated
  and predecision trace parity, actual paid scans and preserved cap/shield.
- Post-run sensor/safety/artifact checks:660 main/reference/smoke/intervention
  episodes verified,0 extra/unselected shield queries or count discrepancies.
- Joint sensing AND navigation benefit: rejected for all four new arms on
  descriptive FIT72. Independent scientific validation: NOT performed.

The main navigation change is already present without explicit future
visibility. The new now/delay/no-information objective also changes how a
future scan's price competes with scanning now; it is not merely deeper rollout
of the old V*min(q,1-q) proxy. No preregistered H=1 version of the NEW objective
was included, so improvements versus frozen C-K/Topology cannot be uniquely
attributed to H=3 depth. Do not infer that future-opportunity modeling caused
the whole gain, or add a post-hoc horizon sweep.

Other limitations: hand-built finite fixture families and shared frozen A*
semantics; marginal rather than joint uncertain-cell outcomes; point-robot
paths and instantaneous heading changes; uncalibrated probabilities/prices;
perfect single-cell revelation assumptions; current-map future occlusion;
restricted prefix reversal rather than optimal replanning; map-to3D sensor
mismatch; fixed benchmark order and uncontrolled OS load; and heavily reused
FIT layouts. Additional observations themselves can explain much of the
success/cost change. The two-schedule cluster treatment does not remove
repeated-development leakage.

Retain the valid negative joint result. Do not adjust costs, horizon, ranking
or event thresholds on FIT72 to improve appearances. A future separately
approved, frozen study should first isolate cost/objective change from depth
with a one-step new-objective control and evaluate calibrated observability
assumptions on independent development material. The24-lineage pilot and
80/200-lineage cohorts remain unapproved, ungenerated and unopened. Their
proposal was updated for future-opportunity coverage only. No automatic
G1-aware EVI development follows this task.

## Evidence, figures and reproducible commands

All artifacts are under `results/phase2_mujoco/c_v21_multistep_v1/` with source
fingerprints, independent annotation population digest, per-stage manifests,
raw sensor/decision/trajectory logs and a final recursive inventory.

- `environment/`, `reference_replays/`: migration and same-machine reference
  replays; `one_step_audit/`: saved-state mechanism audit and model supplement.
- `protocol_binding.json`, `prepolicy_annotation_validation_v2.json`,
  `correctness/`: committed pre-outcome prospective evidence.
- `synthetic/`, `gate_review.json`: immutable formal run and separate review.
- `fit_smoke2/`, `fit72/`, `interventions/`: actual authorized G1 executions.
- `analysis/`: navigation outcomes, hypothesis trajectories, actual trajectories,
  clustered pairs/intervals and untraced timing; `reporting_checks/`: additive
  common-oracle comparison, direct counters and full-trace safety checks.

Representative figures: `analysis/navigation_outcomes.png`,
`analysis/representative_actual_trajectory.png`,
`analysis/future_opportunity_public_predictions.png`, and
`reporting_checks/synthetic_common_reference.png`. The original mixed-oracle
panel is retained for provenance, with the caveat above.

```sh
.venv/bin/python -m pytest tests/test_c_v21_multistep.py \
  tests/test_c_v21_review.py tests/test_c_v21_navigation.py -q
.venv/bin/python scripts/verify_c_v21_environment.py
.venv/bin/python scripts/benchmark_c_v21_references.py
.venv/bin/python scripts/audit_c_v21_delay_assumption.py
.venv/bin/python scripts/validate_c_v21_annotations.py \
  --output prepolicy_annotation_validation_v2.json
# Only from a fresh output checkout with the prospective binding committed:
.venv/bin/python scripts/run_c_v21_synthetic.py
.venv/bin/python scripts/review_c_v21_synthetic.py
# Only if both gates pass (the runner enforces this):
.venv/bin/python scripts/evaluate_c_v21_fit72.py --smoke
.venv/bin/python scripts/evaluate_c_v21_fit72.py
.venv/bin/python scripts/intervene_c_v21_timing.py
MPLCONFIGDIR=/private/tmp/c-v21-matplotlib .venv/bin/python scripts/report_c_v21.py
MPLCONFIGDIR=/private/tmp/c-v21-matplotlib .venv/bin/python scripts/check_c_v21_reporting.py
```

Scripts refuse to overwrite existing output. These commands document the
executed sequence; a fresh prospective replication needs a new output checkout
or a new versioned binding, not deletion of committed evidence. Do not rerun
the formal v1 in place. The source bindings and actual test/command artifacts,
not a future refactored implementation, define this result.

For an exact same-Mac policy replication without touching the archived result,
a detached worktree at the **pre-outcome source commit** has the committed
inputs/reference receipts but no formal/smoke/full/intervention outputs:

```sh
git worktree add --detach /private/tmp/c-v21-replica c504a8c7486eb27136fed4ddba8585253a62eb87
mkdir -p /private/tmp/c-v21-replica/results/raw/phase15_macos_development
mkdir -p /private/tmp/c-v21-replica/results/raw/phase15_bprime_fit_recovery_1
mkdir -p /private/tmp/c-v21-replica/results/raw/phase15_bprime_fit_recovery_2
cp -R results/raw/phase15_macos_development/fit /private/tmp/c-v21-replica/results/raw/phase15_macos_development/fit
cp -R results/raw/phase15_bprime_fit_recovery_1/store /private/tmp/c-v21-replica/results/raw/phase15_bprime_fit_recovery_1/store
cp -R results/raw/phase15_bprime_fit_recovery_2/store /private/tmp/c-v21-replica/results/raw/phase15_bprime_fit_recovery_2/store
ln -s /Users/masahir0/Desktop/humanoid-spatial-memory/.venv /private/tmp/c-v21-replica/.venv
cd /private/tmp/c-v21-replica
.venv/bin/python scripts/run_c_v21_synthetic.py
.venv/bin/python scripts/review_c_v21_synthetic.py
.venv/bin/python scripts/evaluate_c_v21_fit72.py --smoke
.venv/bin/python scripts/evaluate_c_v21_fit72.py
.venv/bin/python scripts/intervene_c_v21_timing.py
```

This recipe is documented, not executed as a second formal experiment here.
Copy only the three authorized FIT stores, not other partitions. They must be
real byte-preserving copies inside the replication root: symlinking raw stores
outside that root would correctly fail the preserved-prefix containment check.
No new data is generated, admitted or substituted. Use a new path if the replica
exists. On another machine, create a newly versioned migration/reference record
before interpreting any timing; the copied same-Mac reference timings cannot be
rebranded as measurements of the other host.

### Figure links

- [Same-machine FIT72 outcomes](../results/phase2_mujoco/c_v21_multistep_v1/analysis/navigation_outcomes.png)
- [Representative actual G1 paths](../results/phase2_mujoco/c_v21_multistep_v1/analysis/representative_actual_trajectory.png)
- [Public future-opportunity predictions](../results/phase2_mujoco/c_v21_multistep_v1/analysis/future_opportunity_public_predictions.png)
- [All arms against the common visibility reference](../results/phase2_mujoco/c_v21_multistep_v1/reporting_checks/synthetic_common_reference.png)
