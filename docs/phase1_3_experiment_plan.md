# Phase 1.3 development experiment plan

Fixed before the first robustness run, 2026-11-06. No configuration is selected
for deployment or held-out use from these outcomes. This is a sensitivity study,
not tuning; every setting will be reported, including unfavorable results.

Seven families, seeds 101/211/307/419, four unchanged baseline methods, 40 steps,
optimistic unknown handling, cost 1.5 per call, initialization charged. Reference:
radius 3, occlusion enabled, noise 0, interval 2, unlimited observations, Phase 1.2
adaptive assumptions. Sixteen one-factor settings (1,792 episodes): reference;
caps 1/2/4; radius 2/5; independent binary noise probability .05; occlusion off;
event/crossing timing -2/+3 steps (clamped to positive steps); pedestrian dwell
+4; entropy thresholds .65/.85; periodic interval 5; prior flips .06/.9 with prior
exposure 6. Other settings remain fixed. A timing shift changes both persistent
and pedestrian schedules where present, so it is a joint phase intervention,
not an isolated estimate of either mechanism. All realized schedules are saved.

Each family/seed/setting is generated before method execution and shared by all
four methods. Noise streams are seeded by realization seed and time. Settings
reuse environments intentionally; static outcomes repeated across nonbinding
controls are not independent trials. Report unique scenario hashes per setting;
noise creates distinct sensor realizations, not new environmental topology.
There are four draws per family, insufficient for statistical superiority claims.
No inference treats method, setting, or repeated deterministic seeds as independent.

Families: irrelevant side-room activity (A); newly blocked remembered direct route
(outdated, B); pedestrian dwell in passage (C); permanent obstacle with alternative
routes (D); initially occupied route cell removed (E); foreground occlusion and
hidden downstream addition (F); longer mixed-change route with cap sweeps (G).
These are controlled stressors, not a guarantee each trajectory encounters its
intended failure. In particular A tests dilution by off-route known-cell entropy,
not an oracle injection of high uncertainty. B creates a stale remembered-free
cell that may still have low entropy, rather than setting an agent confidence.
Seeded dimensions, lane, gates, changes and pedestrian multiplicity vary; all
families have connected outer alternatives, narrow interior lanes where specified,
and side branches/dead ends. Evaluator-only audits record persistent-geometry
shortest paths at initial, event and final epochs; temporary pedestrians excluded.
Final reachability is mandatory; this does not prove time-dependent safe reachability.

Additional diagnostic: replay original corridor removal steps 8/9/10/11/12/14,
with default priors and slow/fast priors, all methods. One deterministic realization
per condition, no repeated seeds masquerading as independent worlds. Inspect
sensing timing, dynamic contacts, and remembered obstruction recovery.

Primary endpoints: goal completion, contact-free completion, observation counts,
blocked attempts, dynamic occupancy contacts. Contact-free completion means goal
reached with zero dynamic contacts; blocked movements are rejected and distinct.
Common-horizon error sums use times 0..40 and freeze memory after termination,
while advancing evaluator truth only. They measure unattended residual memory,
not how a continuously operating agent would update after reaching the goal.
Legacy error sums stop at termination; final maps have unequal terminal times.
Cumulative cell-time samples and persistent event counts must not be conflated.
Timing from an event to the next granted observation does not imply visibility
of that event. Initial observation is step 0; denied requests are per-step attempts.
No physical safety claim or movement/collision semantic change is authorized.

Integrity correction after the preliminary run: code inspection found that the
`outdated` and `detour` generators had identical geometry/dynamics apart from
name. Before final reporting, detour was corrected to a two-passage room divider
with a longer bypass, and a name-independent duplicate test added. All 16
settings are rerun and retained; no setting or seed was removed or selected.
Preliminary results are superseded, not treated as additional evidence.
