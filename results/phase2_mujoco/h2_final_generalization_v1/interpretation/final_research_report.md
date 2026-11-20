# H2 final research report: adaptive observation scheduling

## Abstract

We conclude H2 with a prospectively frozen comparison of twelve previously developed observation schedulers on36 freshly generated R/BP/M map lineages, two schedules each. The864 primary policy episodes are accompanied by864 exact FIT reproduction episodes and864 timing repeat runs. Repeats are not independent navigation samples. All candidate parameters and original G1/safety/sensor settings remained fixed. This is new-map generalization under a documented conditional generator, not an independently custodied sealed superiority trial.

| Model | Goals | Contacts | Paid scans | H80 steps | Distance m | Combined rays | Decision ms/case | Wall s/case |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Periodic-4 |55/72|0|811|3098|1629.75|238449|0.0549|0.1730|
| Periodic-5 |60/72|0|661|3064|1546.50|227225|2.2843|0.1632|
| Age-4 |59/72|0|808|2852|1548.75|223260|0.9864|0.1570|
| Age-5 |57/72|0|763|3032|1586.25|231495|2.5424|0.1649|
| Age-6 |56/72|0|693|3295|1689.00|243268|1.0936|0.1740|
| Age-Route-Rescue |59/72|0|796|2852|1550.25|222528|110.9628|0.2676|
| Age-Route-Clock |58/72|0|880|2885|1468.50|229665|98.5002|0.3031|
| RDAO v2 |59/72|0|628|3004|1592.25|221552|433.5457|0.6098|
| RDAO v2.1 |56/72|0|550|2984|1515.75|215574|490.9934|0.6671|
| CAA-Fast |57/72|0|762|3032|1585.50|231434|4.0629|0.1654|
| CAA-Full |57/72|0|760|3032|1585.50|231312|4.0766|0.1654|
| RAA-Defer |57/72|0|763|3032|1586.25|231495|28.0492|0.1888|

The best observed completion is Periodic-5 (60/72,661 paid readings,0contacts). RDAO v2 reaches59/72 with628 readings but incurs much higher compute. CAA-Full's three-scan aggregate saving over Age5 occurs only in two FAILED episodes; there is no successful-episode sensing or movement gain. RAA-Defer exactly matches Age5's observable traces in all72 cases and saves no scans. Thus the small FIT adaptive benefit does not establish a practically superior adaptive policy. A simple periodic clock is the leading practical default on this sample, with uncertainty and map-family tradeoffs.

## Motivation and research questions

Paid memory observations trade freshness and discovery against sensing and computation. H2 asked whether public spatial memory, route relevance, observed change history and viewpoint timing can improve goal completion or reduce paid observations without sacrificing safety; whether those effects transfer to fresh maps; and whether added decision cost is justified. The final benchmark addresses success, sensing, movement, compute and map-family tradeoffs without reducing them to one arbitrary weighted score.

## Previously developed hypotheses and implementations

Periodic clocks and local stale-fraction Age rules provide simple baselines. Cadence controls separate longer intervals/deadlines from adaptive mechanisms. Directional/view/route Age variants ask whether stale local information is relevant to the upcoming path. Age-Route-Rescue adds a public-route rescue to a directional veto; Route-Clock also proactively refreshes relevant route neighbors. RDAO models visible uncertain route regions with a V×U×D×T heuristic, a remaining-budget threshold and viewpoint competition; v2.1 changes current-view angular quality. These are heuristics, not calibrated value of information. CAA classifies cells using authorized repeated readings/endpoint-change history: Fast and Full use fixed age4/5/6 priorities, with no simulator change labels. RAA uses an Age5 parent and conservative public route/view conditions: Defer postpones a narrowly certified request exactly one decision and protects the first noninitial scan.

H2 also tested persistence/EVI and topology/multistep candidates, unconditional event/route triggers, DAO history/deadline suppression, and predictive safety engineering. More detailed hypotheses frequently failed to translate into better rollouts. The latest DAO Deadline/Stable/Quiet screens achieved52/51/51 goals on FIT72, below66 for simple references; no revision of those weak parents was admitted here. Predictive safety was rejected after contacts and lost completions in hand scenes; it was never substituted into this benchmark. RAA Advance/Joint reached59 goals on FIT72 and were rejected. RAA-Defer and historical CAA-Full each reduced Age5 scans770→768 at66 goals, an extremely small development signal. These negative results remain preserved, not erased by final model selection.

## Development benchmark and exact reproduction

| Model | Reproduced FIT72 goals | FIT paid | New goals | New paid | Goal-rate change pp |
|---|---:|---:|---:|---:|---:|
|Periodic-4|66|800|55|811|-15.28|
|Periodic-5|59|670|60|661|+1.39|
|Age-4|66|850|59|808|-9.72|
|Age-5|66|770|57|763|-12.50|
|Age-6|59|707|56|693|-4.17|
|Age-Route-Rescue|66|848|59|796|-9.72|
|Age-Route-Clock|66|932|58|880|-11.11|
|RDAO v2|61|688|59|628|-2.78|
|RDAO v2.1|59|617|56|550|-4.17|
|CAA-Fast|66|768|57|762|-12.50|
|CAA-Full|66|768|57|760|-12.50|
|RAA-Defer|66|768|57|763|-12.50|

All twelve arms were re-executed on all72 historical keys before unseen generation. Existing metric signatures and semantic traces match exactly; RDAO archives expose a smaller saved metric projection, which was compared in full along with all saved navigation/sensing semantics. New and FIT sets are not paired maps. Computation comparisons use the new unified FIT replay instrument, not historical zero placeholders or differing timer scopes.

## Independent map generation and admission methodology

The original frozen25×25 R/BP/M construction, ordered start/goal sampling and two original dynamics laws were reused through a separate H2 stream adapter. Seeds start910000000(R),910010000(BP),910030000(M), sequentially within each family; independent framed SHA256/Philox streams use h2-final-generalization-v1-20261114. First12 admitted lineages per family are retained. Geometry, objects, pedestrian paths and schedules are freshly sampled; schedules may legitimately draw no dynamics or identical categories. There is no outcome-based balancing, seed search, repair or case removal.

Admission counts: `{"admitted": 36, "exact_normalized_topology_duplicate": 1, "near_D4_raster_duplicate": 19}`. Every attempted candidate, reason, stream counter, accepted hash and static witness is saved. Accessible authorized FIT checkpoint geometries (including related/rejected attempts) and newly accepted maps were checked for exact D4 raster copies, free-space Jaccard distance<=0.05 and exact normalized raster-quotient topology equality using the existing monitored macOS nauty backend. No reserved or sealed evaluation world was opened. Historical FIT evidence was consulted read-only for duplicate exclusion and integrity, not reused as a new case. Opaque protected signatures were unavailable; complete near-topology/graph-edit exclusion is not established.

Static G1 geometry admission checks the deterministic shortest point path using the original sampled MuJoCo G1 move/turn checker, east initial heading, at initial and every persistent-event occupancy state in each schedule. These offline truth-based admission queries are separate from runtime selected-action-only shield accounting. They never enter a scheduler. Persistent occupied cells use static wall-box proxies for this witness, conservatively taller than the runtime persistent objects. A witness is sufficient for its sampled static path only: dynamic pedestrian safety, continuous geometry and H80 completion are not guaranteed. Conditioning on duplicate separation and a specific static witness changes the admitted population; this limits claims of an identical unconditioned FIT difficulty distribution. Structural coverage is saved in structural_coverage.csv.

This named36-map evaluation was explicitly approved by the owner, superseding previous proposal-only restrictions solely for this final H2 population. The disabled DAO production generators,24-lineage pilot and80/200-lineage proposals remain disabled/unexecuted. Same-investigator local generation is not independent custody. No sealed/reserved evaluation dataset was accessed.

![All36 maps](../results/phase2_mujoco/h2_final_generalization_v1/analysis/figures/01_map_atlas.png)

## Frozen evaluation and computational measurement

The prospective protocol and source binding were committed before unseen generation. Original Unitree G1 MuJoCo navigation, ternary last-write memory, emergency safety and selected-action shield,61-ray120-degree6m memory sensor, seed42,H80 and cap20(initial included) remain unchanged. Algorithms receive only their original public inputs. Twelve public FIT warmups precede each stage. Cyclic arm order balances every arm across twelve execution positions in72 cases; the timing repeat reverses per-case order. Forty-eight smoke runs precede primary evaluation and are required to match the corresponding primary semantics.

Core decide, refresh, initialization, authorized memory provider, emergency sensor, G1 navigation callback, evaluator point-plan diagnostics and safety choice are timed separately with perf_counter_ns. Sensor/refresh work is outside decide. Inherited policy planning and policy diagnostic computations remain inside the original API timings; these are executable API costs rather than stripped score kernels. Refresh includes historical after-observation bookkeeping/planning. The actual sensor callback and navigation plan costs are not inferred from ray counts. Per-call vectors retain median/p95/p99/max; complete primary/repeat metrics and two-run per-key median times are saved. These are instrumented single-machine costs with remaining OS/order effects, not hardware latency/energy estimates.

## Overall results and generalization

| Model | Goals | Contacts | Paid scans | H80 steps | Distance m | Combined rays | Decision ms/case | Wall s/case |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Periodic-4 |55/72|0|811|3098|1629.75|238449|0.0549|0.1730|
| Periodic-5 |60/72|0|661|3064|1546.50|227225|2.2843|0.1632|
| Age-4 |59/72|0|808|2852|1548.75|223260|0.9864|0.1570|
| Age-5 |57/72|0|763|3032|1586.25|231495|2.5424|0.1649|
| Age-6 |56/72|0|693|3295|1689.00|243268|1.0936|0.1740|
| Age-Route-Rescue |59/72|0|796|2852|1550.25|222528|110.9628|0.2676|
| Age-Route-Clock |58/72|0|880|2885|1468.50|229665|98.5002|0.3031|
| RDAO v2 |59/72|0|628|3004|1592.25|221552|433.5457|0.6098|
| RDAO v2.1 |56/72|0|550|2984|1515.75|215574|490.9934|0.6671|
| CAA-Fast |57/72|0|762|3032|1585.50|231434|4.0629|0.1654|
| CAA-Full |57/72|0|760|3032|1585.50|231312|4.0766|0.1654|
| RAA-Defer |57/72|0|763|3032|1586.25|231495|28.0492|0.1888|

![Success](../results/phase2_mujoco/h2_final_generalization_v1/analysis/figures/02_success.png)
![Sensing](../results/phase2_mujoco/h2_final_generalization_v1/analysis/figures/03_paid.png)
![Movement](../results/phase2_mujoco/h2_final_generalization_v1/analysis/figures/04_movement.png)
![Combined rays](../results/phase2_mujoco/h2_final_generalization_v1/analysis/figures/05_combined_rays.png)
![FIT versus unseen](../results/phase2_mujoco/h2_final_generalization_v1/analysis/figures/12_fit_vs_unseen.png)

Failure-inclusive H80 steps/distance are distinct from success-only means in overall.csv. A shorter failed path is not an efficiency benefit. Goals and contact-free goals are both recorded; any contact prevents calling a method safe or recommending it solely on efficiency. The final data identify descriptive tradeoffs, not a universal winner.

## Paired comparisons and uncertainty

| Candidate vs Age5 | Rescue / harm | Common success | Paid delta/case | 95% cluster interval | Common-success step delta | Common-success distance delta m |
|---|---:|---:|---:|---|---:|---:|
|Periodic-4|1 / 3|54|+0.6667|[-0.06979166666666656, 1.4166666666666667]|+0.5000|+0.5000|
|Periodic-5|4 / 1|56|-1.4167|[-1.9305555555555556, -0.9302083333333384]|+0.7143|+0.0804|
|Age-4|4 / 2|55|+0.6250|[-0.013888888888888888, 1.2777777777777777]|-2.6364|-0.9000|
|Age-6|5 / 6|51|-0.9722|[-1.8611111111111112, -0.125]|+3.8431|+1.5294|
|Age-Route-Rescue|4 / 2|55|+0.4583|[-0.2777777777777778, 1.1666666666666667]|-2.6364|-0.9000|
|Age-Route-Clock|3 / 2|55|+1.6250|[0.8888888888888888, 2.3333333333333335]|-1.9818|-0.5727|
|RDAO v2|3 / 1|56|-1.8750|[-2.9027777777777777, -0.8472222222222222]|-0.3036|+0.2411|
|RDAO v2.1|1 / 2|55|-2.9583|[-4.013888888888889, -1.9583333333333333]|-0.9636|-0.2727|
|CAA-Fast|0 / 0|57|-0.0139|[-0.041666666666666664, 0.0]|+0.0000|+0.0000|
|CAA-Full|0 / 0|57|-0.0417|[-0.1111111111111111, 0.0]|+0.0000|+0.0000|
|RAA-Defer|0 / 0|57|+0.0000|[0.0, 0.0]|+0.0000|+0.0000|

Full paired tables include all eleven nonself contrasts against each of Periodic4/Age4/Age5, rescue/harm/common failure, sensing/movement/compute and common-success costs. Bootstrap5000 draws with seed2026111401 resamples36 whole lineages, preserving each pair of schedules. Intervals are exploratory, unadjusted across many comparisons and conditional on this admitted sample; lack of significance does not prove equality/noninferiority. Small samples, family counts12 and retrospective development selection limit power and external inference.

The posthoc case-wise oracle succeeds on67/72. This uses future outcome labels and is only an unattainable reference upper bound, not an implemented adaptive policy. failures.csv and success_matrix.csv retain every failure and all72×12 outcomes.

![All outcomes](../results/phase2_mujoco/h2_final_generalization_v1/analysis/figures/13_success_heatmap.png)

## Map-family effects

| Family | Model | Goals /24 | Paid scans | Combined rays |
|---|---|---:|---:|---:|
|R|Periodic-4|17|289|85705|
|R|Periodic-5|19|252|87718|
|R|Age-4|19|294|82045|
|R|Age-5|17|287|88023|
|R|Age-6|16|251|92110|
|R|Age-Route-Rescue|19|291|81862|
|R|Age-Route-Clock|16|325|90402|
|R|RDAO v2|17|198|78446|
|R|RDAO v2.1|17|177|77836|
|R|CAA-Fast|17|287|88023|
|R|CAA-Full|17|285|87901|
|R|RAA-Defer|17|287|88023|
|BP|Periodic-4|23|195|55327|
|BP|Periodic-5|22|164|54961|
|BP|Age-4|23|195|54229|
|BP|Age-5|23|176|55937|
|BP|Age-6|23|141|54839|
|BP|Age-Route-Rescue|23|193|54107|
|BP|Age-Route-Clock|23|227|57340|
|BP|RDAO v2|23|129|51789|
|BP|RDAO v2.1|22|113|51728|
|BP|CAA-Fast|23|175|55876|
|BP|CAA-Full|23|175|55876|
|BP|RAA-Defer|23|176|55937|
|M|Periodic-4|15|327|97417|
|M|Periodic-5|19|245|84546|
|M|Age-4|17|319|86986|
|M|Age-5|17|300|87535|
|M|Age-6|17|301|96319|
|M|Age-Route-Rescue|17|312|86559|
|M|Age-Route-Clock|19|328|81923|
|M|RDAO v2|19|301|91317|
|M|RDAO v2.1|17|260|86010|
|M|CAA-Fast|17|300|87535|
|M|CAA-Full|17|300|87535|
|M|RAA-Defer|17|300|87535|

Family differences are descriptive interaction evidence, not posthoc license to dispatch on hidden family IDs. Object/pedestrian categories and structural coverage are retained for interpretation without causal attribution from observed correlations.

![Family comparison](../results/phase2_mujoco/h2_final_generalization_v1/analysis/figures/11_family_success.png)

## Computational efficiency and break-even

| Model | Mean decide ms/step | Median / p95 / p99 / max ms | Update total ms | Actual memory sensor total ms | Emergency sensor total ms | G1 plan total ms | Primary / repeat wall s |
|---|---:|---|---:|---:|---:|---:|---|
|Periodic-4|0.00128|0.00112 / 0.00196 / 0.00254 / 0.06438|16.576|473.506|1204.701|3991.876|12.455 / 12.282|
|Periodic-5|0.05368|0.04271 / 0.10521 / 0.18833 / 0.43458|65.306|383.610|1163.305|3317.532|11.749 / 11.667|
|Age-4|0.02490|0.02300 / 0.03579 / 0.04771 / 0.14463|36.000|470.349|1088.010|3274.284|11.302 / 11.156|
|Age-5|0.06037|0.04863 / 0.13115 / 0.25465 / 0.53729|80.790|443.980|1164.357|3432.711|11.873 / 11.785|
|Age-6|0.02390|0.02271 / 0.03318 / 0.04342 / 0.09379|30.159|401.843|1256.971|3623.759|12.525 / 12.467|
|Age-Route-Rescue|2.80131|2.74267 / 5.51943 / 6.17654 / 14.03208|80.517|477.148|1106.316|3266.459|19.271 / 19.267|
|Age-Route-Clock|2.45824|2.50246 / 4.95324 / 6.08324 / 33.36067|112.888|525.776|1142.288|6611.049|21.823 / 21.687|
|RDAO v2|10.39124|3.23050 / 36.46711 / 107.16307 / 238.31612|712.297|399.231|1195.738|3725.034|43.906 / 43.695|
|RDAO v2.1|11.84702|4.52115 / 41.69527 / 106.99653 / 236.19146|626.755|349.557|1196.655|3849.339|48.033 / 48.152|
|CAA-Fast|0.09648|0.09217 / 0.11825 / 0.15341 / 0.37300|38.578|458.198|1170.341|3377.892|11.909 / 11.823|
|CAA-Full|0.09681|0.09287 / 0.11826 / 0.15472 / 0.33596|38.403|439.794|1156.533|3398.062|11.905 / 11.844|
|RAA-Defer|0.66607|0.04721 / 2.73931 / 3.17759 / 9.03625|31.826|451.460|1153.393|3387.408|13.595 / 13.639|

Fixed full-matrix repeat timings and primary/repeat ratios are in summary.json, with paired median timing CSV. Repetitions add no independent maps or navigation evidence. Highly variable microsecond costs and single-machine order effects should not support precise cross-platform claims.

![Decision costs](../results/phase2_mujoco/h2_final_generalization_v1/analysis/figures/06_decision_cost.png)
![Decision quantiles](../results/phase2_mujoco/h2_final_generalization_v1/analysis/figures/15_decision_quantiles.png)
![Wall times](../results/phase2_mujoco/h2_final_generalization_v1/analysis/figures/07_episode_wall.png)

Observation-related hypothetical cost is decision_ms+refresh_ms+initialization_ms+paid_count×c_ms (also provide requested form without initialization). It excludes navigation/emergency and is not an end-to-end runtime or energy model. Crossover conditions follow fixed-cost difference divided by observations saved; with no saving, an extra-compute method cannot break even by increasing sensing cost.

| Candidate | Reference | Observations saved | Extra fixed ms | Positive crossover ms/scan |
|---|---|---:|---:|---|
|CAA-Full|Periodic-4|51|315.0182|6.1768273725490195|
|CAA-Full|Age-4|48|226.1378|4.711203208333333|
|CAA-Full|Age-5|3|67.9925|22.664174|
|RAA-Defer|Periodic-4|48|2031.7610|42.328354895833336|
|RAA-Defer|Age-4|45|1942.8806|43.17512428888889|
|RAA-Defer|Age-5|0|1784.7354|candidate never cheaper for nonnegative observation cost|

The measured pooled simulator observation is0.59430ms/scan. It is only a plotted reference. Real robots may have very different latency/compute/power costs. Energy was not measured; no power-saving claim is made.

![Break-even](../results/phase2_mujoco/h2_final_generalization_v1/analysis/figures/14_break_even.png)

## Contact-aware Pareto analysis

Zero-contact full-axis nondominated set: Periodic-4, Periodic-5, Age-4, Age-5, Age-6, Age-Route-Rescue, Age-Route-Clock, RDAO v2, RDAO v2.1, CAA-Fast, CAA-Full. Two-axis success/paid frontier: Periodic-5, RDAO v2, RDAO v2.1.
A high-dimensional frontier can retain many methods, particularly with noisy wall time; this is not proof they are equally useful. The CSV exposes all axes and paired common-success costs. Practical recommendation must prioritize reliable completion and absence of contacts before savings in scans or CPU.

![Success-paid](../results/phase2_mujoco/h2_final_generalization_v1/analysis/figures/08_success_paid.png)
![Success-compute](../results/phase2_mujoco/h2_final_generalization_v1/analysis/figures/09_success_compute.png)
![Pareto](../results/phase2_mujoco/h2_final_generalization_v1/analysis/figures/10_pareto.png)

## Representative trajectories

Examples follow the predeclared first outcome contrast / largest absolute paid difference rule, not a favorable-case selection. Cyan circles indicate actual paid readings. These are outcome/path associations, not isolated causal interventions.

![Case13: largest_paid_difference](../results/phase2_mujoco/h2_final_generalization_v1/analysis/figures/trajectory_13_caa_full_largest_paid_difference.png)
![Case1: largest_paid_difference](../results/phase2_mujoco/h2_final_generalization_v1/analysis/figures/trajectory_01_raa_defer_largest_paid_difference.png)

## Discussion, negative results and original contributions

Complex observation decisions do not automatically dominate clocks. Public memory contains only authorized first-hit observations, so predicted visibility can miss newly discoverable cells; a geometric score is not expected goal benefit. An earlier scan changes route/timing and consumes scarce budget, while a deferred reading can conceal changes before a later forced observation. Long-lived transient occupancy and G1 turning/rejected-action feedback complicate point-route heuristics. These mechanisms are supported by the preserved earlier trace analyses; final aggregate associations alone do not identify a unique causal explanation.

Contributions are the implemented public-information scheduling families, explicit authorization/budget/history semantics, controlled ablations and negative findings, reproducible original-G1 integration, and this frozen twelve-model new-lineage/cost benchmark. Distinct implementation mechanisms and a useful reproducibility artifact do not establish globally novel algorithms or calibrated value-of-information theory. Report practical tradeoffs without manufacturing a superior winner.

## Limitations and integrity

Only36 conditionally admitted maps and two correlated schedules each; same investigator and machine, no independent custody, no opaque protected signatures, incomplete near-topology proof, static shortest-path admission bias, original discrete kinematic environment and horizon80. Safety/contact results are confined to these scenes and do not reverse archived pedestrian contacts or prove physical humanoid safety. Multiple models/metrics are exploratory; FIT was repeatedly reused in development. No new algorithms, parameter fitting, thresholds, outcome exclusions or safety changes were made. Only the newly approved H2 final36-map population was generated; earlier DAO pilot/production populations remain ungenerated.

Related tests:163 passed in final pre-freeze gate (15 benchmark plumbing cases plus frozen-model/safety regressions). An initial incorrect test filename ran no tests; its original log is preserved. The historical native-build directory was missing, so a separately committed pre-draw restoration pinned the existing local pynauty2.8.8.1/nauty2_8_8 build and reproduced all51 available archived exact graph keys before any unseen draw. Original sources, seed/admission laws and failed setup evidence were preserved; the new native hash differs from the missing old binary. See h2_backend_recovery_v1_1.md. Pre-freeze harness representation/timing and geometric-admission design corrections are documented in setup_notes.md, with no unseen outcome access. Baseline parity gates all864 FIT replays. Actual sensor authorization, cap20 and selected-only shield accounting are checked per episode; timing repeat exact semantics are required. Known20 pre-existing historical archive issue entries are recorded separately, never silently repaired. Final verification and recursive manifest are stored alongside the evidence.

## Direct answers and practical recommendation

Highest observed completion is60/72: Periodic-5. Among the completion leaders with the best available contact status, Periodic-5 has the lowest measured primary decision cost. This is a descriptive practical default for this sample, not proof of universal optimality.

CAA-Full vs Periodic-4: goals +2, paid -51, total decision cost +289.563ms, episode wall -0.550s. It meets the point-estimate same-or-higher-success/fewer-scans criterion with zero contacts. This does not constitute a noninferiority test.
CAA-Full vs Age-4: goals -2, paid -48, total decision cost +222.497ms, episode wall +0.603s. It does not meet the joint point-estimate same-or-higher-success/fewer-scans criterion. This does not constitute a noninferiority test.
CAA-Full vs Age-5: goals +0, paid -3, total decision cost +110.462ms, episode wall +0.033s. It meets the point-estimate same-or-higher-success/fewer-scans criterion with zero contacts. This does not constitute a noninferiority test.
Development transfer for CAA-Full vs Age5: FIT goal difference +0, paid difference -2; unseen goal difference +0, paid difference -3.
RAA-Defer vs Periodic-4: goals +2, paid -48, total decision cost +2015.587ms, episode wall +1.140s. It meets the point-estimate same-or-higher-success/fewer-scans criterion with zero contacts. This does not constitute a noninferiority test.
RAA-Defer vs Age-4: goals -2, paid -45, total decision cost +1948.522ms, episode wall +2.293s. It does not meet the joint point-estimate same-or-higher-success/fewer-scans criterion. This does not constitute a noninferiority test.
RAA-Defer vs Age-5: goals +0, paid +0, total decision cost +1836.487ms, episode wall +1.722s. It does not meet the joint point-estimate same-or-higher-success/fewer-scans criterion. This does not constitute a noninferiority test.
Development transfer for RAA-Defer vs Age5: FIT goal difference +0, paid difference -2; unseen goal difference +0, paid difference +0.

### Movement transfer (unpaired map-set means)

| Model | FIT / new mean H80 steps | FIT / new mean distance m | FIT / new success-only steps |
|---|---|---|---|
|Periodic-4|42.208 / 43.028|23.042 / 22.635|38.773 / 31.600|
|Periodic-5|43.167 / 42.556|22.781 / 21.479|35.051 / 35.067|
|Age-4|40.486 / 39.611|22.396 / 21.510|36.894 / 30.712|
|Age-5|42.278 / 42.111|23.146 / 22.031|38.848 / 32.140|
|Age-6|48.361 / 45.764|24.375 / 23.458|41.390 / 35.982|
|Age-Route-Rescue|40.653 / 39.611|22.438 / 21.531|37.076 / 30.712|
|Age-Route-Clock|40.292 / 40.069|22.521 / 20.396|36.682 / 30.431|
|RDAO v2|44.306 / 41.722|24.354 / 22.115|37.869 / 33.288|
|RDAO v2.1|45.819 / 41.444|24.000 / 21.052|38.288 / 30.429|
|CAA-Fast|42.278 / 42.111|23.167 / 22.021|38.848 / 32.140|
|CAA-Full|42.278 / 42.111|23.167 / 22.021|38.848 / 32.140|
|RAA-Defer|42.278 / 42.111|23.146 / 22.031|38.848 / 32.140|

The final conclusion is to retain the measured tradeoffs and end H2 without another model revision. rankings.csv documents relative-rank changes; success/paid evidence, common-success movement and actual CPU/wall costs must be considered together.

## Final H2 conclusion and future directions

**H2 ends with no robust practical dominance of the complex adaptive schedulers.** Periodic-5 has the highest observed completion (60/72 versus59 for Age4/RDAO v2,57 for Age5/CAA-Full/RAA-Defer), with661 paid readings and zero contacts. Its success advantage over Age5 is only3 cases; the whole-lineage95% success-difference interval[-0.02778,0.125] includes zero. Its paid-reading difference interval[-1.93056,-0.93021] per case favors fewer readings on this conditional sample. This is a practical descriptive recommendation, not a general superiority/noninferiority proof.

Age4 remains useful where lower elapsed steps, combined rays and local runtime matter:59 goals,808 paid,223260combined rays and2852H80 steps versus Periodic5's60/661/227225/3064. The extra completion and fewer paid readings do not imply that Periodic5 dominates total sensing/movement cost. RDAO v2 is the sensing-oriented alternative (59 goals/628 paid/221552combined rays), but its primary decision cost31.215s and wall43.909s across72 cases far exceed Periodic5's0.164s and11.754s. RDAO v2.1 reduces paid readings further to550 while falling to56 goals and adding computation; it is a tradeoff, not the winner.

CAA-Full's57 goals/760 readings versus Age5's57/763 is only an aggregate count saving in two failed cases; common-success paid/steps/distance deltas are zero. Its paired paid95% interval[-0.11111,0] includes zero. Its higher fixed observation-related cost requires an assumed scan latency above22.664ms to break even against Age5, compared with a pooled measured simulator scan0.5943ms. No robust end-to-end advantage or energy saving is established. RAA-Defer's development terminal-saving signal vanishes: all72 step traces equal Age5,763 readings each, with extra decision cost and no nonnegative scan-price break-even against Age5. These are valuable negative generalization results.

Family results favor no hidden-family oracle: BP has23/24 goals for several models, while M is harder; Periodic5 and RDAO v2 reach19/24 M goals versus17 for Age4/Age5. In R, Periodic5/Age4 reach19/24 while RDAO v2/Age5 reach17. These small12-map family strata are descriptive, not a validated routing rule. The posthoc all-model success union67/72 is unattainable without outcome labels.

Freeze these outcomes and close H2 without model improvement, retuning or additional seed exploration. Further studies of calibrated visibility/value, longer continuing routes, independent custody or real-robot latency/energy would be separate future work requiring a new protocol. The current36-map, admission-conditioned, same-investigator/same-machine study does not prove equivalence, physical humanoid safety or universal generalization.

## Artifacts and reproduction

`results/phase2_mujoco/h2_final_generalization_v1/` holds source binding, tests,prior preservation,maps/admission,full FIT replay,smoke,primary,timing_repeat,analysis tables/figures,verification and final manifest. Protocol: docs/h2_final_evaluation_protocol_v1.md. Runner stages: run_h2_final.py freeze / fit_replay; h2_generate_maps.py; run_h2_final.py smoke / primary / timing_repeat; report_h2_final.py. Frozen stages refuse overwrite; partial stages retain exclusive episodes and a hash journal for validated resume. Portfolio unchanged.

## Final trace audit and illustrative additions

The finalized trace audit was performed after the frozen primary/repeat matrix, without executing or modifying a scheduler. RAA-Defer and Age5 have exactly equal full observable step traces in72/72 cases. CAA-Full differs only in cases13(R:910000017,s0) and48(BP:910010012,s1), both failures for both policies: paid18→16 and20→19. CAA-Fast differs only in case48. All57 common successes preserve the same scan counts and movement; Full's0.75m all-case distance difference also comes from failures. The data therefore do not support successful-task improvement from CAA's tiny aggregate saving.

The two original prospectively selected CAA/RAA illustrations remain in analysis/. RAA's first case is an explicit null example because every paid difference is zero. Additional images below use a POSTHOC first-discordant-case rule for Periodic5/RDAO comparisons, to make the observed navigation differences visible. These figures illustrate, rather than establish causality or improve, the frozen aggregate findings.

![Descriptive case1](../results/phase2_mujoco/h2_final_generalization_v1/interpretation/contrast_01_periodic5_vs_age5.png)
![Descriptive case1](../results/phase2_mujoco/h2_final_generalization_v1/interpretation/contrast_01_rdao_v2_vs_periodic5.png)
![Descriptive case1](../results/phase2_mujoco/h2_final_generalization_v1/interpretation/contrast_01_rdao_v21_vs_periodic5.png)

Measured observation-related cost differences (decision+refresh+initialization+actual memory sensing; primary totals):

| Candidate | Reference | Delta ms | Wall delta seconds |
|---|---|---:|---:|
|caa_full|periodic4|+281.3068|-0.5500|
|caa_full|periodic5|+158.7628|+0.1564|
|caa_full|age4|+195.5832|+0.6032|
|caa_full|age5|+63.8067|+0.0326|
|raa_defer|periodic4|+2009.7150|+1.1399|
|raa_defer|periodic5|+1887.1709|+1.8463|
|raa_defer|age4|+1923.9913|+2.2931|
|raa_defer|age5|+1792.2148|+1.7224|

The original automatic analysis/report is retained byte-for-byte. This finalized report is stored in interpretation/final_research_report.md and docs/h2_final_research_report.md. Reproduction adds interpret_h2_final.py after report_h2_final.py. The separate backend-restoration amendment and failed setup are retained; the restoration was committed before any new draw.
