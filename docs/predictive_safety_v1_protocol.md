# Predictive emergency safety v1 — prospective engineering protocol

Base1671e26f9b1360a4f061c5a04934a1374c789f83. The completed contact audit
`predictive_safety_contact_audit.md` precedes candidate implementation. Its four
archived DAO trajectories have exact untreated semantic/metric parity. All
Periodic4/Age4/Age5 baselines share advance/synchronization-induced contacts.
Original algorithms, timing, sensor configuration and failed evidence remain.

## Candidate and assumptions (frozen before benchmark outcomes)

A common safety infrastructure candidate applies identically to all8 observation
policies. No DAO/CAA/Age/EVI threshold, planner, pedestrian trajectory or simulation
update order changes. Candidate stores only public dimensions/footprint and
independent emergency measurements. Actual/shadow geometry and future programs
are evaluator-only; no candidate call to sensor, A*, scene or collision shield.

Constants: one cardinal grid cell/transition maximum proxy speed, stopping and
reversal allowed;2-transition final-footprint lookahead; maximum stale track age2;
public capsule radius0.19m; original grid scale0.75m, G1 half extents from pinned
model. Discrete proxy centers lie at integer cell centers. A measured first-hit
surface cell therefore identifies its proxy cell under this specific radius<
0.5cell/grid-centered model. This is NOT a human localization model. Visibility,
unseen entries/occlusion and arbitrary continuous motion are not certified.

For measured cells C at time s, current possible cells at t are C dilated by
Manhattan radius(t-s), clipped to public map bounds (never hidden wall pruning).
Retain stale possibilities through age2. Unique single-cell reacquisition within
motion bound replaces its prior unique sample; ambiguous multiple/missing tracks
retain possibilities. Beyond2, tracks expire and the class explicitly reports
no-observed-track scope, not global safety. Measured motion direction never
removes stopping, reversal or lateral possibilities.

Let P0 be current possibilities; P2=P0 dilated by2. During the unchanged discrete
action phase pedestrians are stationary; at the NEXT world advance they may
move. Certify an action conditionally iff: (a) its entire current swept public
G1 AABB avoids P0 expanded by capsule radius; (b) its endpoint oriented footprint
avoids P2 expanded by that radius; (c) all static swept occupancy cells except
the public current robot cell are free in this actual emergency reading; and
(d) map bounds and selected-action rejection feedback allow it. No cell is
written/inferred free. Static squares use existing0.505*cell_size half-width.

Translation uses exact segment/expanded-box slab intersection. Rotation uses a
circumradius box covering ALL intermediate yaw angles; endpoint uses target yaw.
Wait is checked as a stationary sweep/endpoint, never presumed safe. This is
conservative2D geometry, not actual3D shield inference or continuous pedestrian
motion. First-advance contacts before ANY robot action may be unavoidable under
this unchanged timing model; candidate cannot retroactively prevent them.

If the original selected action is conditionally certified, preserve it. Otherwise
consider selected action, forward, left/right sidestep, retreat, left/right turn,
wait, each at most once. Only measured/public clearance is used; no alternative
MuJoCo shield calls. Choose certified alternative minimizing goal Manhattan
distance, ties by catalogue order. If none certifiable, explicitly log the
condition and choose an UNCERTIFIED fallback wait; this is not a safety guarantee.
With no observed/stale tracks preserve original action and record limited scope,
not certainty that no hidden pedestrian exists. The unchanged real shield checks
only the final selected executable action. Log full risks/certificates/cost.

No parameter fitting to the archived failure. Independent reference tests enumerate
5^H stay/cardinal paths, test continuous translation against dense independent
samples and rotation bounds against1001 yaw samples; explicit stop/reversal,
missing/multiple tracks, no-escape, wait-risk and no-pedestrian controls.

## Frozen comparison matrix

Original safety versus PredictiveV1 × Periodic4, Age4, Age5, CAA-Full, DAO-Veto,
DAO-Trigger, DAO-Route, DAO-Combined. Original12 engineering scenes are regression
only; new14 hand-defined17x17 scenes are separate prospective mechanisms:
crossing/head-on/overtaking/stop/reversal/alternating/occluded/multiple/narrow/
rotation/stationary/no-person/unavoidable-first/no-person-turn. Total26*8*2=416
formal episodes, one run each. Horizons are original24 and new28; seed42; original
memory cap20 inclusive; paid61-ray6m120degrees and independent61-ray2m360degrees
unchanged. No extra actual sensing or production/FIT cohort screen.

The unavoidable-first scene puts a proxy into the start cell at transition1,
before any possible robot action. It is a proven timing lower bound, not an
avoidable-case success target. Other contact cases are NOT automatically labeled
physically unavoidable merely because the candidate could not certify escape.
Record actual inability/observability and leave unproved avoidability unresolved.

## Predeclared acceptance and metrics

Before interpreting interventions require untreated archived DAO parity on
all48 regression episodes (same metric signatures and semantic traces). The
initial7-case forensic audit is additional evidence, not substituted matrix data.
Require exact actual memory/emergency calls, inclusive cap, last-write memory,
selected-only shield counts, immutable original sources and unchanged scenarios.
Geometry probes have zero ray calls and are separately tagged evaluator-only.

Report post-action contacts/pairs/states AND actual sensor-sync contact onsets,
contiguous contact-step episodes, selected rejected hypotheses separately,
minimum signed MuJoCo geometry distance, advance versus action/sweep initiation,
goals/contact-free goals, blocks, waits/sidesteps/retreat, no-certifiable-action,
interventions, paid/emergency/total rays, steps/distance/common-success deltas,
safety CPU and instrumented wall time. Do not confuse39 pairs with39 incidents.
Sweep sample count/geometry probes are diagnostics, not additional actual sensing.

Unnecessary-intervention PROXY: offline public-AABB check of original selected
sweep against evaluator current proxy centers plus endpoint at actual next2
centers. If that proxy check is clear but override occurred, count it; this is
not proof of causal necessity/utility and never an online input. Also report
no-pedestrian negative-control interventions. Missing selected actions use wait.
No hidden actual alternative shield query or future actual sensor is allowed.

Safety acceptance requires no new actual contacts in negative controls and no
new contacts in any otherwise contact-free matched case; report all residual
contacts and unavoidable timing cases separately. Improved avoidance does NOT
establish acceptance if liveness collapses: flag loss of goal completions or
indefinite horizon waiting and report paired common-success costs. Do not claim
real-world safety, independent efficacy or superiority from these fixtures.
No automatic parameter/scene retuning on failures. Freeze sources, JSON scenes,
tests and criteria in git BEFORE formal execution; preserve any failed run.

## Scope boundary

Original2907 pairs/836 protected files, CAA/DAO evidence/G1 assets are reverified.
Generator width bias/occlusion coverage, duplicate-admission scaling, missing
opaque signatures, independent custody, approximate interval undercoverage,
scientific margins and power/sample size remain UNAPPROVED blockers. No production
population, reserved access, full FIT72 screen, DAO winner or further DAO iteration.
