# Attenuated discovery v1: frozen retrospective measurement protocol

Base 99f004fc6ff2de576479b2756beb57f83ae23a9f. Close the current safety
heuristic sequence. Phase Wait passed 144 compact episodes (48/48 goals,
45 contact-free goals, 3 proven first-transition contacts) and then failed
the unchanged expanded gate: original 184/208 goals, 151 contact-free
goals, 37 onsets; Phase Wait 180/208, 172 contact-free goals, 8 onsets,
all eight at proven unavoidable first transitions. Four goal harms:
alternating DAO-Trigger/Combined and multiple Periodic4/Age4. No new
nonfirst contacts in these hand scenes. Do not promote Phase Wait as
accepted common safety infrastructure, claim physical safety, or continue
tuning the same crossings. Production pilot remains unready.

## Hypothesis

Earlier DAO predicted optimistic and frontier footprints. In actual
engineering navigation, frontier count MAE 26.293 versus optimistic 7.784;
frontier tended to underpredict, optimistic to overpredict. These are
retrospective selected-scan measurements, not independent efficacy.
Investigate an intermediate raster estimator without changing navigation.

Use exactly the legacy 61-ray public-memory point-grid sampling geometry.
Known occupied cells stop a ray; exclude current robot cell. For each
unknown target, let k be the minimum number of DISTINCT preceding unknown
cells on any ray reaching it. Repeated sample visits do not increase depth.
The target itself does not increase its own depth. Assign q^k to the cell;
sum over distinct unknown targets. Max weight across rays is equivalent
to min depth for q in [0,1]; no independence assumption between intersecting
rays. q=0 recovers the frontier count (0^0=1); q=1 optimistic count.
Use fixed q=.5 as the primary intermediate hypothesis and .8 as sensitivity.
These factors are design assumptions, not calibrated probabilities or
fitted occupancy estimates. No parameter fitting or automatic selection.
No actual ray calls, true geometry, future proxy paths or hidden map inputs.

## Read-only assessment

Use exactly the completed 416 navigation episodes from Phase Wait expansion
(26 scenes, eight observation schedulers, two safety versions), total
1861 authorized paid scans including 416 initial scans. Audit initial
and all subsequent readings separately. Reconstruct public ternary memory
from paid readings only, using recorded pre-action emergency-decision poses
and initial trace pose/heading. Predict before applying each saved reading.
Compare actual first-observed cells excluding the robot's current cell.
Check legacy optimistic/frontier footprint parity at every recorded scan.
Verify archived manifests before processing; never open new populations.
Exclude initial scans from the main summary because initial memory is all
unknown and the observation is mandatory. No pooling of compact reruns.

Report absolute and signed count error, threshold-5 disagreement, actual
new cells outside predicted optimistic footprint, empirical depth counts,
and per-scene paired absolute-error differences against optimistic.
Separate safety version and original-regression/prospective scene role.
The empirical depth fractions are descriptive and not used to fit q.
Observations are correlated and selected by existing policies; this
cannot establish prediction performance at denied decisions, a calibrated
probability, navigation relevance or reduced sensing. No new controller
is evaluated. Do not choose a factor for rollout merely because it looks
best here.

Test independently specified axial cases, repeated unknown samples, known
free gaps, invalid factors and 80 randomized states against old footprints.
Freeze code/tests/this protocol before processing. Exclude all production
cohorts, reserved worlds and any FIT72 navigation rerun. No changes to
DAO, CAA, G1 planner, safety, real sensors or stored data. Output exclusive
results/phase2_mujoco/attenuated_discovery_v1. Run check, audit, report.
Local tests and saved-reading processing remain pending.
