# Change-aware Adaptive Age (CAA) v1 — research report

**Completed descriptive result: CAA-Fast and CAA-Full meet the owner's primary
target, but only by two paid scans across72 cases. Simultaneous sensing and
navigation improvement is not demonstrated.** No novelty, independent
superiority, semantic classification or generalization claim is made.

Starting commit `b4fa534bfbcf6944766af743cbe5bc56cbdaffe5`; pre-outcome source/protocol freeze `6dea670c4794be2c4d5e67e50115f5f463e24f25`;
branch `phase2/mujoco-proxy-pilot`, university-library Mac, Python3.12 `.venv`.
All new policy outcomes were produced after that prospective commit. No
threshold, history constant or arm was tuned after outcomes.

## Implemented scheduling hypothesis and equations

`src/spatial_memory/change_aware_age.py` implements observation-history-only
cell deadlines. Unlike the earlier persistence B model, it never predicts,
erases or rewrites occupancy between observations. The actual planner sees
only the original ternary last-write memory, updated by authorized readings.
No EVI, topology, predicted visibility, event trigger, hidden category or
unselected shield input is used.

A cell stores last observed occupancy z, last observed time l, repeated-reading
count, endpoint transition count, last transition detection time d,
consecutive unchanged reobservations u, and run start b. Initial readings are
not transitions. Unknown sensor outputs change none of those cell statistics.
An actual empty scan still consumes one paid observation. All timestamps are
monotonic; refresh must consume the current grant.

After each authorized reading: differing known occupancy increments the
transition count, sets d=b=t and resets u. Equal occupancy increments u only
if the previous actual reading is at most6 steps old; a gap>6 restarts the
run instead. Stability exposure is l-b, never current time minus an old
reading. Equal endpoints can conceal intervening changes: this is a scheduling
heuristic, not continuous monitoring or calibrated persistence inference.

Classification priority is changing > stable > intermediate; unknown is
excluded from the score. Changing means a detected transition within10 steps
(two nominal5-step intervals). Stable requires at least3 actual consecutive
unchanged reobservations spanning at least12 steps (two6-step intervals),
each link gap<=6, current reading age<=6, and no recent-change priority.
Elapsed time alone cannot promote stability; freshness expiration removes
stable classification without changing memory.

For the ORIGINAL Age radius/known-cell set S, use

    score(t) = sum_(i in S) I[t-last_observed_i >= tau_i] / |S|,
    or zero if S is empty.

Request when t>0 and score reaches the original stale-fraction threshold;
apply the initial-inclusive cap20 afterward. Fast uses4 for changing and5
otherwise; Slow uses6 for stable and5 otherwise; Full uses4/5/6. Equality is
due, with no random tie break. The parameters were justified prospectively
by actual reobservation/exposure semantics, not a FIT performance sweep.

## Prior analysis and frozen controls

The required pre-implementation audit replayed all144 Age/Age-5 episodes with
exact saved metric/semantic parity. The owner-specified3 rescues and3 harms
were verified. All6 first scan/memory divergences were at4; the earlier Age
readings there revealed new cells and no changed-known cells. First action
changes occurred at4 except M80030009's two schedules at8. These are
associations, not forced-scan causal evidence. Full case contents, stale
occupied/free raster counts, blocked actions, emergency interventions and
budget exhaustion are in `caa_retrospective_analysis.md` and `retrospective/`.

Across72 keys, Age4 had778 noninitial scans:694 with new cells,21 with changed
known cells,83 unchanged-only. Age5 had698:630 new,30 changed-known,64
unchanged-only. New and changed categories overlap; no empty scans occurred.
Most observations explore new cells; repeated endpoint changes are rare.
This limits what FIT72 can establish about change-aware deadlines.

Age-5 is explicitly frozen as an additional strong baseline from the original
cadence source/artifacts:66 goals,770 paid scans,3044 H80 steps. All72 Periodic
replays also passed before CAA navigation. Periodic/Age4/Age5 were reproduced
again in the actual seven-arm matrix, not substituted by their historical
timing placeholders. Old RDAO/EVI/route/motion/persistence algorithms and
results remain unchanged.

## Execution and correctness gates

Final focused correctness: **108 tests passed,0 failed**, including26 new CAA
history/integration tests. Coverage includes stable/alternating states,
change-after-stability, aging without evidence, long gaps, unknown/empty scans,
atomic timestamp validation, changing/stable transitions, exact uniform5
reference behavior, budget denial, authorized-only updates,300 independently
computed scalar-history events, cropped/full-mask equivalence, deterministic
replay and a no-truth/no-planning import guard.

A constructor-local diagnostic radius reference was caught in pre-freeze
code review and covered by an executed-wrapper test. Earlier103/106-test
setup gates and their Periodic replays were preserved as superseded setup
artifacts. Extra paired ablation contrasts and priority/replay tests were
added BEFORE the final binding. No CAA navigation had run at either revision;
no policy constants or CAA outcomes were adjusted.

The committed binding covers25 source/protocol files. Smoke:2 keys ×7 arms
(14 episodes), all pass; full:72 keys ×7 arms (504 episodes), executed once.
The first two full keys match smoke. Every fixed baseline matches saved
metric signatures and semantic traces at all72 keys.

Original data verification:2,907 exact checkpoint/receipt pairs, filenames,
payload digests, run/sequence pairings, old inventories and836 protected files.
G1 XML/STL assets and old cadence evidence also match their committed hashes.
Post-run checks cover878 stored audit/setup/smoke/full episodes; all518 formal
smoke/full episodes independently count actual memory sensor calls. No extra
or unselected shield query, budget violation or scan-accounting discrepancy
was found. There were no missing local inputs or pre-existing failures in the
focused test run. Font-cache permission warnings did not prevent plot output.

## Full seven-arm descriptive results

All arms have0 unwanted contacts; contact-free completion equals goals. The
72 conditions are36 reused mazes with two correlated schedules, not72
independent environments.

| Policy | Goals/72 | Paid total | Mean paid scans | Mean H80 steps | Mean combined rays | Primary target |
|---|---:|---:|---:|---:|---:|---|
|age4|66|850|11.805556|40.486111|3189.792|False|
|age5|66|770|10.694444|42.277778|3231.306|False|
|age6|59|707|9.819444|48.361111|3549.014|False|
|caa_fast|66|768|10.666667|42.277778|3229.611|True|
|caa_full|66|768|10.666667|42.277778|3229.611|True|
|caa_slow|66|770|10.694444|42.277778|3231.306|False|
|periodic|66|800|11.111111|42.208333|3252.486|False|

The target is zero contacts and >66 goals, or66 goals with mean scans<10.694.
Fast/Full have768/72=10.666667 versus Age5's770/72=10.694444: a0.2597% paid
scan reduction. The exact integer rule avoids a rounding-based claim. They
save32 scans (4%) versus Periodic and82 (9.647%) versus Age4, but have no new
goal successes versus Age5. This is a small descriptive result, not a strong
new algorithmic contribution or a deployment recommendation.

### Paid/emergency workload and retrospective memory metrics

Memory rays are actual paid calls ×61; emergency scans/rays are independently
logged. Combined workload is their sum, not a replacement for either count.
Memory-error figures are the unchanged evaluator-only cell-time sums.

| Policy | Paid rays | Emergency scans/rays | Combined rays | Blocked attempts | Emergency interventions | False-persistent cell-times | Missed-change cell-times |
|---|---:|---:|---:|---:|---:|---:|---:|
|age4|51850|2915/177815|229665|36|5|62|5611|
|age5|46970|3044/185684|232654|63|21|70|5588|
|age6|43127|3482/212402|255529|143|35|81|6873|
|caa_fast|46848|3044/185684|232532|63|20|46|5588|
|caa_full|46848|3044/185684|232532|63|20|46|5588|
|caa_slow|46970|3044/185684|232654|63|21|70|5588|
|periodic|48800|3039/185379|234179|47|7|64|5850|

### Paired common-success navigation and rescues/harms

Only paired COMMON successes contribute to step/distance deltas below;
positive cost deltas are worse. Failed short paths are never treated as an
efficiency improvement. All17 prespecified contrasts, paired keys, common
means and2,000 whole-maze bootstrap intervals (seed2026111403) are retained.
Both schedules remain together in each resampled maze. The intervals are
exploratory/unadjusted on reused development data, not independent tests.

| Candidate vs reference | Rescues/harms | Common successes | Step delta | Distance delta (m) | Joint paid+navigation gain |
|---|---:|---:|---:|---:|---|
|age6 vs periodic|0/7|59|3.694915|0.483051|False|
|age6 vs age4|2/9|57|5.350877|1.105263|False|
|age6 vs age5|2/9|57|5.263158|1.289474|False|
|caa_fast vs periodic|2/2|64|0.390625|0.328125|False|
|caa_fast vs age4|3/3|63|2.253968|1.023810|False|
|caa_fast vs age5|0/0|66|0.000000|0.022727|False|
|caa_slow vs periodic|2/2|64|0.390625|0.304688|False|
|caa_slow vs age4|3/3|63|2.253968|1.000000|False|
|caa_slow vs age5|0/0|66|0.000000|0.000000|False|
|caa_full vs periodic|2/2|64|0.390625|0.328125|False|
|caa_full vs age4|3/3|63|2.253968|1.023810|False|
|caa_full vs age5|0/0|66|0.000000|0.022727|False|
|caa_fast vs age6|9/2|57|-5.263158|-1.263158|False|
|caa_slow vs age6|9/2|57|-5.263158|-1.289474|False|
|caa_full vs age6|9/2|57|-5.263158|-1.263158|False|
|caa_full vs caa_fast|0/0|66|0.000000|0.000000|False|
|caa_full vs caa_slow|0/0|66|0.000000|0.022727|False|

No CAA arm improves sensing AND navigation jointly against Periodic, Age4 or
Age5. Fast/Full preserve Age5's exact success/failure set, but shared-success
steps are unchanged and distance increases1.5m across66 successes. Relative
to Periodic and Age4, their common-success steps/distance are worse. Age6's
lower scan count accompanies7 fewer goals and worse common-success movement;
its failed trajectories do not count as efficiency gains.

## Where the two-scan signal occurs

All savings occur in **R:80000021 schedule1**, one maze and one schedule.
Age5 uses13 scans; Fast/Full use11. Both reach at45 steps, but distance grows
20.25→21.75m. At step14, two recently changing cells in a19-cell local known
set raise the score from uniform5's0.421053 to0.526316, crossing0.5. The
subsequent observation/path histories differ. This demonstrates a same-state
deadline-trigger attribution, not a controlled causal effect of that isolated
scan or a general pattern across independent environments.

A second key, **M:80030007 schedule1**, changes scan timing but not the20-scan,
H80-failure outcome. Full advances54→53; Fast also changes late-budget timing.
Both changed keys, including the failure, are plotted in `verification/`.
The original generic trajectory plot is retained; changed-clock plots are the
more informative representation. No favorable case was substituted for the
complete matrix or used for parameter revision.

The paid-scan difference versus Age5 has a maze-cluster95% bootstrap interval
[-0.083333,0] scans/episode. It includes zero, and the tiny effect depends on
one extensively inspected lineage/schedule. The primary numerical target is
met, but independent superiority/generalization is not established.

## Classification activation and ablation interpretation

The following are cumulative **cell-decision counts**, not numbers of distinct
objects, cells, semantic walls or independent observations. Baseline classes
are diagnostic shadows only; they are never baseline decision inputs.
Unknown cells are excluded from deadline distributions. Periodic uses a clock.

| Policy | Changing | Intermediate | Stable | Unknown | Effective deadlines4/5/6 |
|---|---:|---:|---:|---:|---|
|age4|227|276335|737|1544576|277299/0/0|
|age5|334|280619|168|1621379|0/281121/0|
|age6|321|285348|108|1890473|0/0/285777|
|caa_fast|333|280590|166|1621411|333/280756/0|
|caa_full|333|280586|166|1621415|333/280586/166|
|caa_slow|334|280619|168|1621379|0/280953/168|
|periodic|295|279852|390|1618838|clock|

| CAA arm | Same-state advanced requests / paid scans | Same-state deferred requests | Budget-exhausted decisions |
|---|---:|---:|---:|
|caa_fast|3/3|0|86|
|caa_slow|0/0|0|84|
|caa_full|2/2|0|84|

Fast advances3 requests; Full advances2. These can nevertheless yield fewer
FINAL scans because sensing updates timestamps, visibility/discovery, paths
and later requests. A same-state superset is not an episode-dose ordering.
Slow produces **identical full semantic traces to Age5 in all72 cases** and
no actual deferral. Stable cells exist, but their score contributions do not
cross the decision threshold in this screen. Full and Fast have equal primary
and common-success outcomes, though some late scan clocks differ. There is
no demonstrated added navigation benefit from combining stable-cell delay
with recent-change acceleration on this cohort.

Fast/Full have630 new-cell scans,30 changed-known scans and62 unchanged-only
noninitial scans, versus630/30/64 for Age5. These are net category counts,
not evidence that two specific scans could be deleted without other effects.
Classes and exposure are policy-conditioned; endpoint equality can hide
intervening changes. Do not infer true stable/dynamic object frequencies.

## Computation, memory and same-machine timing

Let N be grid cells, W the cropped Age-radius window (at most49 here), J paid
observations (<=20), and T decisions (<=80). Initialization and each authorized
history update are O(N); each core decide is O(W), including its local
uniform5 attribution score. Total policy work is O(JN+TW), with0 scheduler
A* calls and0 predicted raycasts. The actual G1 planner and sensors are the
unchanged common pipeline.

History state is O(N): six int64 arrays plus public int8 occupancy, about49N
array bytes before Python overhead. Scoring temporaries are O(W). The supplied
research controller also retains a compact decision ledger O(T), so its total
retained auxiliary/output memory is O(N+T), not literally only O(N). The shared
full-map diagnostic observer costs O(TN+JN) outside scheduler time, and the
existing evaluator frame archive/audit snapshots can retain O(TN). None of
those logs is a new observation or an online scheduling input.

All7 arms use the same outer core-decide/authorized-refresh timer boundaries.
Global class/scan logging is timed separately. The frozen Age5 compatibility
controller retains its historical unused probability and post-scan logging
work; API timing differences are not purely the mathematical age-score cost.
Per-update values below are pooled over actual NONINITIAL authorized refreshes;
initialization and external diagnostic time are not folded into that number.

| Policy | Mean scheduler ms/episode | Pooled ms/decision | Pooled ms/refresh | Mean diagnostic ms/episode | Mean episode seconds |
|---|---:|---:|---:|---:|---:|
|age4|1.019079|0.025171|0.048765|4.339106|0.157896|
|age5|2.513600|0.059454|0.101702|4.399223|0.163154|
|age6|1.348508|0.027884|0.048102|4.750711|0.184407|
|caa_fast|4.036250|0.095470|0.055643|4.637059|0.163577|
|caa_full|4.086316|0.096654|0.056457|4.704174|0.165071|
|caa_slow|4.196240|0.099254|0.056107|4.650818|0.163984|
|periodic|0.056714|0.001344|0.022110|4.419312|0.164035|

The full504-episode process took88.80 seconds; peak process RSS was856,555,520
bytes on macOS. These include MuJoCo model/evaluator/storage, not just CAA
arrays. There are no cross-Mac speedup claims. Fixed arm order, shared logging,
OS activity and one run limit wall-time interpretation. CAA's extra history/
classification work does not yield a CPU advantage over these simple controls.
The two saved scans should not be equated to reduced total computational cost.

## Integrity, limitations and next independent experiment

The original G1 model,0.75m kinematic-root setup, actual61-ray memory sensor,
independent emergency safety channel, selected-action shield and initial-
inclusive20-observation cap were preserved. Memory is ordinary last-write,
with no free inference updates. All prior policies/results and original FIT
stores remain unchanged. Additional input transfers are not needed.

This result is limited by heavily reused FIT layouts,36 correlated clusters,
a single-lineage small paid-scan signal, unadjusted comparisons, very sparse
observed changes/stable local revisits, uncalibrated history heuristics,
interval-censored endpoints, sensor projection/occlusion effects and kinematic
rather than physically actuated navigation. Reduced false-persistent error
sums are retrospective schedule/path outcomes, not proof of semantic
persistence inference. The prior Age5 rescue/harm audit is associational;
no new controlled causal-scan experiment was claimed here.

**Freeze this result and stop FIT tuning.** Retain Age5 as the strong simple
baseline. If the owner approves a new lineage-separated cohort, preregister
CAA Fast/Slow/Full, fixed Age6 and Periodic/Age4/Age5; vary stable/dynamic
exposure, actual revisit frequency, long gaps and occlusion with exogenous
changes and unchanged controls. Use a custodian-held sealed evaluation set,
maze-level inference and jointly reported safety/completion/sensing/movement/
compute criteria. Do not transfer a66/72 count target to another cohort size.
The24-lineage pilot and80/200-lineage proposals remain unapproved, ungenerated
and unopened. No reserved world was accessed. No next algorithm iteration,
threshold sweep, EVI/topology/visibility feature or G1-aware extension was run.

## Artifacts and reproducibility

- Policy: `src/spatial_memory/change_aware_age.py`; tests:
  `tests/test_change_aware_age.py`, `tests/test_caa_integration.py`.
- Prospective rules: [CAA protocol](caa_protocol.md); baseline:
  [Age5 freeze](age5_frozen_baseline.md); pre-implementation analysis:
  [retrospective audit](caa_retrospective_analysis.md).
- Root: `results/phase2_mujoco/caa_v1/`. Final `correctness/` and
  `protocol_binding.json` authorize the experiment; `*_prefreeze_v1/v2` are
  preserved superseded setup records, not additional CAA policy screens.
- `smoke/`, `fit72/`: actual14/504 episode ledgers and unchanged-source hashes.
- `analysis/`: complete17 paired comparisons, means/intervals, class/deadline
  distributions, sensor/memory/compute metrics and figures.
- `verification/`: deep pair/artifact/safety checks and ALL changed-clock keys.

[Seven-arm outcomes](../results/phase2_mujoco/caa_v1/analysis/outcomes.png) ·
[History/deadline distributions](../results/phase2_mujoco/caa_v1/analysis/history_deadlines.png) ·
[M80030007 changed clock](../results/phase2_mujoco/caa_v1/verification/changed_key_040.png) ·
[R80000021 scan saving / distance cost](../results/phase2_mujoco/caa_v1/verification/changed_key_068.png)

Executed sequence after the retrospective audit and pre-freeze checks:

```sh
.venv/bin/python scripts/run_caa_fit72.py check
# Commit prospective source, protocol, binding and passing check artifacts.
.venv/bin/python scripts/run_caa_fit72.py smoke
.venv/bin/python scripts/run_caa_fit72.py full
MPLCONFIGDIR=/private/tmp/caa-matplotlib .venv/bin/python scripts/run_caa_fit72.py report
MPLCONFIGDIR=/private/tmp/caa-matplotlib .venv/bin/python scripts/verify_caa_results.py
```

All output creation refuses overwrite. A future unchanged-policy replication
can use a fresh `--output-root results/phase2_mujoco/caa_replication_v1` on each
check/smoke/full/report command; commit its new binding before smoke. This is
an example command recipe, not a second full experiment executed here. The
original retrospective and frozen cadence evidence must remain available and
unchanged. Do not delete or rewrite the original output to rerun v1. The
current task ran the full seven-arm matrix once and did not start a subsequent
research iteration after outcomes.
