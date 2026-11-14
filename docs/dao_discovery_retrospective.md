# DAO discovery retrospective: existing FIT evidence only

Analyzed 360 unique saved episodes (Age4, Age5 and all three CAA variants, 72 each),
with 144 matched Age4/Age5 public-memory frame archives as enrichment. All14
smoke replications are inventoried but not pooled. No new simulation, policy
screen, prediction-threshold fit or supervised model was run.

## Actual scan content (noninitial)

| Arm | Scans | With discovery | With changed-known | Unchanged-only | New-cell quartiles (25/50/75%) |
|---|---:|---:|---:|---:|---|
|age4|778|694|21|83|4/11/19|
|age5|698|630|30|64|4/11/20|
|caa_fast|696|630|30|62|4/11/20|
|caa_full|696|630|30|62|4/11/20|
|caa_slow|698|630|30|64|4/11/20|

Discovery and changed-known categories overlap. Initial scans (72 per arm)
are retained separately in CSV. Discovery counts first-ever readings; changed
known means an endpoint occupancy difference, not a semantic object change.
An unchanged-only reading still verifies remembered occupancy and cannot be
called useless from its immediate map/action effect. Age4 new count spans0–80
cells per scan; Age5/CAA0–69. All distributions/intervals are in summary.json.

## Progress, locations and public route associations

Each CSV scan includes exact pre-action location and heading (frame t-1),
interval since last paid scan, absolute step, scan index and normalized episode
progress. Using post-action frame t as the sensing pose would be wrong.
Last absolute-time bin includes step80; a pre-freeze labeling-only draft is
preserved in retrospective_prefreeze_labels, superseded by retrospective.

| Arm | Mean new cells/scan at steps0–19 |20–39|40–59|60–80|
|---|---:|---:|---:|---:|
|age4|14.214|13.469|8.492|14.600|
|age5|15.762|14.398|9.748|9.980|
|caa_fast|15.762|14.451|10.026|9.980|
|caa_full|15.762|14.451|10.026|9.980|
|caa_slow|15.762|14.398|9.748|9.980|

Late bins have fewer surviving episodes and are policy-conditioned; these
are scan-weighted summaries, not a causal temporal decay estimate. Absolute
and normalized progress are both retained rather than assuming equal exposure.

For1476 Age4/Age5 noninitial scans, exact before/after public maps support
new-cell positions and observed occupancy changes. Counts agree exactly with
saved scan ledgers. Recompute a point-grid optimistic nominal route before
and after the scan at the SAME pre-action pose and public goal. Count newly
observed cells within Manhattan1 of the first5 route moves. This proxy is
not the actual G1 clearance/action plan and is not causal navigation utility.

| Arm | New cells near route | Nominal route changed | Nominal first move changed |
|---|---:|---:|---:|
|age4|3105|319|118|
|age5|3060|298|146|

CAA has2090 noninitial scan records with scalar counts but no saved cell
rasters. Its exact newly discovered positions, route proximity and before/
after nominal routes are MISSING; do not infer them from Age5 or silently
replay a simulator to fill the gap. The public action trace remains available.

## Completion, blocked actions and navigation associations

|Arm|Success/failure episodes|Mean discovery/scan, success/failure|Mean blocked, success/failure|
|---|---|---|---|
|age4|66/6|14.978/7.439|0.303/2.667|
|age5|66/6|16.650/8.848|0.742/2.333|
|caa_fast|66/6|16.707/8.848|0.742/2.333|
|caa_full|66/6|16.707/8.848|0.742/2.333|
|caa_slow|66/6|16.650/8.848|0.742/2.333|

Episode-weighted per-scan discovery is higher in successes and blocked
counts lower, but successful motion exposes new space while stuck/failing
robots repeat views. Episode duration, cap exhaustion, geometry and sensor
occlusion confound the direction. This does NOT prove discovery causes success.
Complete scan content strata retain same-step/next-step blocks and temporal
action changes; an action change from t-1 to t may follow a routine heading/
pose transition. No unobserved counterfactual action or causal utility is
assigned. Route/map changes can matter later even if immediate action is unchanged.

CAA remains frozen: Fast/Full66 successes and768 scans, versus Age5 770, all
savings in one maze/schedule; scan-difference confidence interval includes zero and common-success
distance grows slightly. Nothing in this retrospective upgrades that evidence.

Artifacts: `results/phase2_mujoco/dao_v1/retrospective/` contains scan/episode
CSVs, summary, source inventory, distributions figure and manifest. Exactly
36 reused maze clusters underlie each72-condition arm; schedules and policies
are correlated. These observations motivate a prospectively specified DAO
hypothesis, not a threshold optimization or independent efficacy claim.
