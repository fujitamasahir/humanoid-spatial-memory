# Pedestrian contact audit BEFORE candidate implementation

Base1671e26f9b1360a4f061c5a04934a1374c789f83. Seven untreated forensic episodes
completed: all four DAO archived semantic traces and non-timing metric signatures
match EXACTLY, followed by Periodic4/Age4/Age5 on the identical hand scene.
Original source, sensor configuration, environment timing and trajectories are
unchanged. Full staged evaluator-only geometry is under
results/phase2_mujoco/predictive_safety_v1/forensics/.

| Scheduler | Recorded post-action contact steps | Pedestrian pair sum |
|---|---|---:|
| DAO-Veto |5,7,9|117|
| DAO-Trigger |11|39|
| DAO-Route |5|39|
| DAO-Combined |11|39|
| Periodic4 |5,7|78|
| Age4 |5,7|78|
| Age5 |5|39|

All seven share the failure mechanism; pair sums are not distinct incidents.
The source World.advance changes the discrete trajectory index but leaves the
MuJoCo mocap poses untouched. Before the emergency scan, actual model contacts
still reflect the previous step. A SEPARATE MjData copy synchronized to the
current World index shows the incoming overlap without modifying the real
model. The original sensor.observe then calls _sync_environment and mj_forward;
at this actual synchronization all39 robot/pedestrian geometry pairs appear
before any safety choice/action. The final frame retains them. This is proxy
teleportation at sensor synchronization, not sensing physically causing a
collision or a translation/rotation executed into the pedestrian at that step.

At the preceding step4(Veto/Route/Age5), the measured hit is(6,6) with estimated
velocity(0,-1). The original reachable set is{(6,6),(6,5)}; it permits movement
from(5,7) to(6,7). At step5 the program reverses to(6,7), already overlapping
the stationary robot before the robot can respond. Trigger/Combined repeat
this at10→11 with the reverse velocity sign. Veto stays there and the alternating
program creates new onsets at7 and9; they are separated by contact-free steps,
not continuing contact counted three times. No future schedule enters any
online component. Sensor visibility is present; missed detection/occlusion is
not the initiating mechanism in these archived cases. Motion extrapolation
is overconfident about reversal. At onset there is no observed-clear escape;
a wait does not certify safety and a later action cannot erase that past onset.

Selected-action sweep probes are tagged separately as accepted or REJECTED
hypotheses and excluded from executed-state contact episodes. Their counts
are never added to actual frame contact sums. Pure evaluator geometry probes
make no ray call and never pass their data to the scheduler or safety class.
Actual raw versus synchronized-copy stages prevent assuming that source call
order equals physical model synchronization. Intermediate continuous pedestrian
motion between discrete cells is NOT simulated; no continuous-time avoidance
claim follows. Exact minimum MuJoCo collision-geometry distances are logged.

Justified candidate hypothesis: replace single-direction next-position certainty
with a bounded all-direction/stopping reachable set derived only from emergency
hit cells/timestamps and a declared one-cardinal-cell/transition speed bound.
Check selected and alternative action sweeps against CURRENT uncertainty and
final occupancy against the next environment transition (with a second-transition
lookahead as a conservative engineering design). Include rotation geometry,
missing/stale tracks and explicit no-certifiably-safe-action status. The next
stage must freeze a separate multi-mechanism benchmark before outcomes and
report liveness; it must not tune to this one archived reversal. No DAO or
planner change is justified by this audit.
