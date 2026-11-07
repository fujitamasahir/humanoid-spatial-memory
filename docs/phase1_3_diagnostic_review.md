# Phase 1.3 diagnostic review

Reviewed Phase 1.2 scheduling, sensor, memory, A*, world, evaluator, stored decision
traces, validation report and literature audit. Baseline algorithms, motion,
collision semantics and earlier results/configurations remain unchanged. The
existing literature review covers occupancy grids, temporal occupancy, confidence
decay and active perception; these are conceptual foundations, not faithful
implementations or support for a novelty claim. No new paper claim is made here.

## Corridor mechanism and timing sensitivity

The original corridor is deterministic: seeds 7/19/31 repeat the same world with
no sensor noise. It is one environmental condition, not three independent trials.
At initialization a pedestrian at (3,3) is written occupied and occludes cells
beyond it. Optimistic planning routes through unknown (2,2), actually a wall.
Uncertainty moves to (2,3), then repeats blocked attempts at steps 2–4. Its first
refresh at step 5 clears the departed pedestrian memory and exposes enough of
the corridor to proceed. At step 7 a pedestrian blocks movement into (5,3);
at step 9 the persistent obstacle at (6,3) blocks movement. Truth advances before
observation: removal at step 10 is visible to the step-10 refresh from (5,3),
allowing the direct passage. Goal completion is step 13, eight moves and five
blocked attempts. The initial homogeneous rate .05 and entropy threshold .75
produce the initial step-5 trigger; this is a model assumption, not learned
knowledge that the passage will clear at step 10.

The single-seed timing diagnostic varies only the removal epoch (8/9/10/11/12/14)
and uncertainty prior flips (.3/.06/.9), retaining all other corridor conditions.
Default uncertainty succeeds for removals 8/9/10 with calls at [0,5,10], but fails
for 11/12/14, observing at [0,5,10,15,22,26,32,38]. In those later cases step 10
writes the obstruction occupied; ensuing route choices and occlusion prevent
recovery by the deadline. It is therefore false that the original advantage is
robust to a small removal-time shift. These are repeated-measure diagnostics,
not 72 independent environmental samples. Raw episodes and gate-memory traces:
`results/phase1_3/corridor_diagnostic/`.

## Dynamic contacts and age thrashing

Uncertainty's original corridor trace incurs one dynamic contact: a new pedestrian
entry into the pre-move robot cell. A rejected motion into an occupied target is
only a blocked attempt; it does not count as that contact. Delayed sensing leaves
stale free/occupied memory and can keep the robot waiting in the pedestrian cycle.
Sensing has no time cost and does not itself avoid a pedestrian entering the robot
cell before the observation; the world has already advanced. This model does not
simulate physical collisions, human reactions, braking or body overlap geometry.

The Phase 1.2 total of four uncertainty contacts includes the same corridor
contact three times, plus another condition; periodic has one total. Aggregate
success did not require contact-free completion. This is an observed schedule
interaction, not proof that entropy causes more physical danger.

Age refreshes at 4/8/12/16/20, then 24/25/27/28/31 and every step 35–40, ending
at (7,5) with no remembered route. Its potential-radius score includes known cells
hidden behind occluders. Refresh changes only visible timestamps, so those hidden
cells remain old and keep triggering requests. The route retains removed (6,3)
and pedestrian-sourced (4,3) as occupied. No cooldown, truth mask, map repair or
baseline modification was introduced to suppress this failure.

## Prior assumptions

The rate proxy (prior_flips + observed_flips)/(prior_exposure + observed_exposure)
assumes binary symmetric relaxation, clips rates to [.01,.35], and resets observed
confidence to .95 even for noiseless sensing. Multiple hidden transitions alias;
noise becomes apparent flips; unknown cells never enter the baseline trigger.
The model is not a calibrated posterior or persistent/transient classifier.

In the corridor, slow prior flips .06 gives [0,23] observations and fails every
removal condition, with three contacts each. Fast .9 senses much more frequently
and also fails all six conditions, though it has zero contacts in these runs.
More observations alone do not guarantee a useful trajectory. The broader
predefined prior sweep is reported alongside every other setting in validation;
no preferred prior is selected from those outcomes.

## What task relevance can and cannot establish

Local entropy averages known cells without a goal or route. It can spend budget
on side-room changes and miss the consequence of a low-entropy stale free gate.
The new families test those opportunities, occluded passages, temporary dwell,
permanent detours and reopened gates. The paired constructive unit test holds
histories/entropy equal and shows an occupancy flip on the route changes shortest
path cost, while the same flip off-route does not. Thus task location carries
information absent from the generic score. This does not demonstrate predictive
benefit, safe behavior or novelty for any proposed policy. Family A's high-entropy
concentration and B's low-entropy stale route cells are stressor intentions, not
assertions true at every pose; traces must be checked before claiming a mechanism.
Sensor-history replay tests confirm at least one generated uncertainty episode
with majority high-entropy known footprint cells off its remembered route (A),
and at least one on-route stale-free addition below the entropy threshold (B).
These are existence checks across the fixed seeds, not claims about every run.
A future study should preregister conditional subsets using robot-accessible
features and assess them on new seeds, without selecting favorable episodes here.

Robustness results, fixed matrix, exact commands, duplicate checks, safety metric
definitions and limitations are in [validation](phase1_3_validation.md) and the
[experiment plan](phase1_3_experiment_plan.md). Proposed task-aware sensing remains
[design only](phase1_3_task_aware_design.md), pending research review.
