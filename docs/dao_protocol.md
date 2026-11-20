# DAO v1 prospective engineering protocol

Starting point: `5cb40fce42e8791b1406245684be5d0df0964b93` on
`phase2/mujoco-proxy-pilot`. CAA and all earlier controllers/results are frozen.
This protocol authorizes saved-evidence analysis, unit tests and a public-state
synthetic mechanism suite only. No new FIT72 navigation screen, pilot,
development, sealed or reserved population generation/admission/access.

## Hypothesis and five separate information concepts

Unknown memory is -1 and means never observed; occupancy 0/1 is ordinary
last-write memory. Discovery is a first reading of a never-observed cell.
Verification reobserves a known stale cell; changed-known occupancy is an
actual endpoint difference, unavailable before sensing. Navigation relevance
is a proxy based on a supplied public nominal route, not semantic importance.
An unchanged-only reading still verifies knowledge and is not called useless.
Observed predominance of discovery in prior scans motivates this hypothesis;
it neither identifies a causal benefit nor calibrates an information value.

Age excludes never-observed cells from its radius-3 stale fraction. Unknown
space cannot by itself request an Age scan, even at an unexplored turn. Limited
120-degree FOV, remembered occluders and actual 3D occlusion separate local
age from observable information. DAO explicitly counts unknown cells.

## Public geometry, counts and uncertainty

Use the original public range6m, scale0.75m, 61 angular hypotheses spanning
120 degrees, at most81 distance samples/ray (0.1-cell sampling convention
in `evi.visible_cells`). Stop optimistic rays at remembered occupied cells
or the map boundary; include the hit cell. Exclude the robot's current cell.
Conservative frontier rays additionally stop at the first unknown cell,
including that cell once. Duplicate cell sightings are unioned, never summed
as independent information. Frontier is a subset of optimistic under this
public raster model, NOT a certified lower bound on real sensor visibility.
Unknown occluders, sensor-site offset, height and projection can invalidate
both geometric estimates. No probabilities, entropy gain or bits are claimed.

For estimate F, define U={i in F: memory_i=-1}; S={i in F: last_i>=0 and
 t-last_i>=5}; K={i in F: last_i>=0}. D=|U|, V=|S| and Q=V/|K| (0 if empty).
Report both frontier/optimistic counts separately. Decisions use frontier;
optimistic is a diagnostic comparator, not a separately selected candidate.
A public nominal point-route is supplied (no scheduler A*); truncate to the
next5 moves. D_R counts U within Manhattan distance1 of that prefix. Missing,
empty or short-at-goal routes yield D_R=0, without truth-based substitution.
The route proxy is distinct from the actual G1 traversability planner.

## Prospective constants and request equations

Age5 anchor A uses the exact original radius3, due-age5 and stale fraction0.5.
Let H=(D>=5), W=(V>=3 OR (|K|>0 AND Q>=0.5)). Five discovered cells are an
interpretable one-new-cell-per-nominal-Age-interval design scale, not a fitted
utility equivalence. Three verified cells are a small multi-cell support
criterion; the fractional alternative preserves dense stale verification.
All choices are engineering assumptions requiring independent development.
Cooldown is ceil(5/2)=3 actual elapsed steps. E=(gap>=3 AND H), E_R=E AND D_R>0.
Tie equality qualifies; there is no randomized selection or learned model.

Fallback B is ANY known cell in the original local radius with age>=10
(two Age5 intervals), even when A is false. This guarantees a scan opportunity
for sufficiently old local known cells while budget remains. It is not a
guarantee for cells outside the current radius, change detection, visibility,
or operation after cap exhaustion. A fallback scan can reset a cell only if
the actual sensor observes it; invisible old cells may request repeatedly
until the cap, a limitation to report rather than silently infer freshness.

For t>0, before cap:

- DAO-Veto: B OR (A AND (H OR W)).
- DAO-Trigger: B OR A OR E.
- DAO-Route: B OR A OR E_R (isolate route relevance from Trigger).
- DAO-Combined: B OR (A AND (H OR W)) OR E.

Combined is the union of the justified veto/trigger components; it does not
silently add route gating. At an identical state Veto is a subset of Combined,
and Combined a subset of Trigger. B can cause Veto to exceed Age5: it is a
bounded safety-of-knowledge exception, explicitly logged. These inclusions
do not imply ordering of total paid scans on diverged trajectories.

Controls: unchanged production Periodic4, fixed Periodic5, Age4, frozen Age5,
Age6; frozen CAA-Fast/Slow/Full are strong future navigation controls. The
prototype provides mathematical fixed-clock/age controls for synthetic
comparisons; it does not replace the historical implementations in navigation.
DAO-Trigger versus Route separates route weighting. Fixed-clock/age controls
and future development dose summaries distinguish discovery from frequency;
no post-hoc outcome-matched clock is introduced as an unbiased comparator.

Unlike previous Route-Rescue, DAO does not gate solely on Age4/View-Veto and
a due route cell: it counts all predicted never-observed frontier cells,
separates stale verification and permits discovery triggers without Age.
Route only restricts that discovery trigger; no known occupied route-neighbor
score, no no-route event trigger, no counterfactual planning or EVI prices.
Novel algorithmic status and navigation benefit remain unestablished.

## Authorization, resource bounds and integration boundary

`DiscoveryController` accepts initial actual observation and counts it as1.
Each increasing decision needs fresh public heading/goal/optional route context.
Only a current grant permits refresh at that timestamp; invalid observations
are rejected atomically. Unknown outputs do not update timestamps/occupancy;
an empty authorized scan consumes budget/time. Denial never authorizes sensing.
Initial-inclusive cap<=20. No inference between readings. Public goal is
validated/provenance context, not a hidden route/visibility source.

At most4096 grid cells, range<=8 cells, 61 rays,81 samples/ray and route5 moves.
No scheduler A*, actual/shadow sensor, real geometry or shield call. Complexity
O(N+61*81+|F|*5) per assessment including validation, O(N) per actual refresh;
O(N+|F|) working memory, plus O(T) retained decision logs. Both estimates share
one bounded arithmetic ray traversal. Timing instrument counts these costs.
Fixed controls in this synthetic harness share diagnostic geometry overhead;
this is not a CPU benchmark of native production baselines.

The existing G1 planner/model, 61-ray paid sensor, independent emergency channel,
selected-only shield and last-write ternary memory are unedited. No DAO
MuJoCo adapter is activated; synthetic controller contract tests are the only
execution authorized here. Actual navigation efficacy/integration remains
pending approved independent engineering/navigation work.

## Freeze and formal synthetic acceptance

Hand-defined `scripts/dao_fixtures.py` creates48 public states:12 families at
ages3/5/9/10. Families: explored, corridor, new room, turn, repeat view,
unknown occluder, irrelevant discovery, important stale cells, addition,
removal, temporary occlusion and no-route/no-benefit. These are not new
navigation lineages, seeded population samples, or copied FIT worlds.
Persistent/temporary fixture labels are evaluator annotations only: online
inputs contain no actual event schedule or true category. Hypothetical unknown
occluder is evaluated outside the controller and never written into memory.

Prepare fixtures, run focused correctness tests, and commit the source/protocol/
fixture hashes BEFORE formal suite execution. Formal gate verifies identical
committed source and inputs. Execute the48-state suite once; save all results
and failures; no outcome-dependent threshold changes/reruns. Nine rules per
state give432 same-state decisions (four DAO plus five controls), not432
navigation episodes. Only hand-defined followup readings exercise occupancy
updates; no true simulator calls.

Required acceptance: all frontier/optimistic sets and count fields match the
independent scalar reference, frontier subset property, exact legacy optimistic
parity (excluding current cell), deterministic decisions, cap/authorization
checks, no memory modification by prediction, bounds<=4941 sample visits,
zero scheduler planning/sensing calls. Analytic narrow-FOV ray certificates and
160 independent seeded random public states are covered by unit tests, separate
from formal fixtures. Formal fallback must authorize old local cells at10;
unknown must never enter known-stale verification; fully explored states have
zero discovery. Log how often each mechanism actually activates, including
negative/identical variants. A pass establishes engineering conformance only,
not calibrated visibility or better navigation.
