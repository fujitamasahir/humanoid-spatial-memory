# Frozen DAO v1 G1 engineering integration protocol

Base d04db45472c7c28e91c0753f4271190c87bcc52a. All prior DAO/CAA algorithms,
parameters and evidence remain untouched. Dedicated compatibility adapter
`dao_navigation_v1.py` consumes only current last-write public memory, authorized
timestamps, pose, heading, goal and original optimistic unknown rule. It ignores
legacy age4 constructor parameters in favor of the EXACT frozen DAOParameters.
No policy correction or new variant is introduced.

DAO-Route adds ONE point-grid public-memory A* per decision, then supplies its
first5 moves to the frozen rule. No hidden geometry or unselected shield query.
Route-plan calls/ns and total scheduler ns (including route planning) are
recorded; other DAO variants add zero scheduler plans. A separate diagnostic
point plan on each authorized scan supplies comparable route-discovery metrics
for all variants; it is not a policy input. Route's current plan is reused.
Current diagnostic implementation times the route preparation boundary and
can report reuse; it must not be mistaken for extra actual sensing.

Legacy G1 planner, paid61-ray sensor (6m,120degrees), independent61-ray emergency
sensor (2m,360degrees), selected-only shield, original last-write memory and
cap20 including initialization remain unchanged. The harness temporarily
supplies an explicit hand-defined Scenario and controller through existing
callbacks, restores all module bindings on exit, and labels metadata
ENGINEERING_HAND_SCENE, never a Phase1.5 admitted world. It writes no FIT store.
Each actual paid reading has a prediction BEFORE observe() returns and before
refresh; initial prediction uses all-unknown memory. Sensor wrappers independently
count memory/emergency calls; selected checker count must match evaluator
selected-action count. Reconstructed memory must equal only actual authorized
readings at every frame. No sensor is queried at other decision times.

## Prospective scene matrix and separate fixture scans

Twelve explicit15x15 hand-defined scenes in `dao_engineering_scenes_v1.py`:
straight3-cell corridor, unknown obstacle, door/open room, in-place turn toward
goal, repeated view against a separating wall, explored surrounding space,
known-stale region, object addition at6, object removal at6, transient pedestrian
crossing, discovery away from goal route and low-discovery obstacle view.
All use cell0.75m and original G1. Four frozen DAO variants each run once,
horizon24:48 navigation episodes. No efficacy acceptance threshold or winner
selection. Some scenes may be unreachable by design; failures/contacts are
reported, never erased or converted into short-route efficiency gains.

Additionally each scene has10 explicitly authorized fixture readings at
steps0/1/2/3/4/5/10/11/12/13 and fixed headings east/north/west/south/east…,
stationary at start. These120 readings diagnose geometry and reobservation;
they are NOT DAO policy-paid observation counts or navigation episodes.
They never update the memory of the separate navigation runs. Probe reads
also use the actual61-ray sensor, with at most10 inclusive calls per fixture.
No hidden scene occupancy initializes public memory or predictions. Fixture
labels are descriptive intended mechanisms, not proof that all surroundings
were actually explored or a mechanism activated. Actual coverage is reported.

Record full optimistic/frontier sets, actual observed cell/value lists, unknown
predictions, actual new and changed-known cells, actual stale verification,
route-relevant discovery, precision/recall and signed/absolute count error.
For count/set agreement exclude current robot cell from BOTH comparable new
sets (the frozen predictor excludes it); also retain complete actual readings.
Precision/recall with zero denominator are undefined/null, never perfect.
Unknown occlusion and3D sensor offset can invalidate raster bounds: no physical
upper/lower bounds or calibrated information gain claims.

Checking rules: exact cap/sensor-step/selected-shield accounting, no extra query,
ternary authorized-only memory, finite valid predictions and timestamps, zero
frozen-source changes. Geometry prediction mismatch is a MEASURED result,
not a conformance failure. Record same-state Age5-veto suppression and fallback
requests followed by no discovery/verification/change, without calling them
causally useless. Do not tune scenes/thresholds after results. Retain failures.

## Other engineering infrastructure

TEST-only generator/admission details are in `dao_generator_admission_v1.md`.
Twelve explicit TEST payloads (four families × dimensions25/33/41, seed101)
are construction/schema/clearance tests, not production lineages or navigation
cohorts; none is run as a navigation efficacy sample. Production entry points
raise PermissionError. No pilot/dev/sealed/reserved access.

Prospective statistical code uses synthetic outcome tables only. Whole lineages
include BOTH schedules; completion differences, normal-approximate intervals
and cluster bootstrap are separate; zero-variance completion intervals use a
bounded Hoeffding fallback. Contacts use lineage any-contact exact binomial
upper bounds. Paid/combined sensing, conditional common-success movement,
missing denominators and failure-penalized sensitivity are separate. Holm
handles additional hypotheses; fixed-sequence proposed joint gates stop
inferential eligibility on first failure while reporting every endpoint.
The original owner's descriptive target is zero contacts and higher completion
or equal completion/fewer paid scans. NI.03,10% joint costs and compute thresholds
are PROPOSED, not approved scientific requirements or the owner's original goal.

Synthetic selection/confirmation checks validate code behavior only; no actual
DAO winner is selected. Sealed partitions are rejected by selection APIs.
Power/coverage simulation: n80/200/800 × schedule correlation0/.8 × discordance
.05/.2 × true completion loss0/.03,1000 Monte Carlo repeats each (24 conditions).
Report actual coverage/NI power/null-boundary error with Monte Carlo uncertainty;
do not certify nominal coverage if simulations disagree. No sealed n is fixed.
Cost/contact/conditional-outcome power still require their own scenarios and
owner-approved assumptions; normal planning alone cannot justify joint power.

## Gate and commands

Run new infrastructure plus relevant existing tests; freeze exact scene JSON,
this protocol, source fingerprints and passing gate in git BEFORE formal
engineering runs. Execute actual-sensor suite and TEST/statistical checks once,
preserving any failure. Correct engineering serialization/accounting defects
only through documented versioned recovery; never change frozen DAO equations.

    .venv/bin/python scripts/run_dao_integration_v1.py prepare
    # commit source/scene/binding/gate
    .venv/bin/python scripts/run_dao_integration_v1.py formal
    .venv/bin/python scripts/check_dao_infrastructure_v1.py

Existing2-step integration unit probe first exposed missing legacy row metadata;
its failure note is retained before formal freeze. The fix supplies dedicated
engineering metadata only. Unit probes are separate from formal48 episodes.
All outputs are exclusive/create-once. No new full FIT72 screen is authorized.
