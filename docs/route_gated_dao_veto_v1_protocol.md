# Route-gated DAO-Veto v1: prospective mechanism ablation

Base f7fce26c603bb01f141f66e33e6c469a2b88b32b. The fixed attenuation
comparison completed 61 tests and 416 episodes with 260 reference
parities. All three factors yielded the same aggregate results: 110 paid
scans versus 104 for original DAO-Veto under each safety version, same
23/26 goals and 23 paired common-success step/distance deltas all zero.
The six additional scans were in turn, off_route, rotation and
no_pedestrian_turn. This supports investigating whether discovery is
navigation relevant; it does not prove that these scans were causally
unnecessary. Freeze this negative result.

## Hypothesis and isolated rules

Retain original DAO-Veto as the reference, with original frontier geometry,
Age5 anchor A, discovery predicate D (at least5 frontier unknown cells),
verification predicate V (at least3 stale known footprint cells or stale
fraction at least.5 with nonempty known footprint), fallback F (oldest local
known age at least10). Original request is F OR (A AND (D OR V)).

Calculate a public nominal point-grid A* route with the existing occupied-start
compatibility guard. R means a usable prefix exists, N_R is the number of
frontier unknown cells within Manhattan1 of its next five moves, S is the
original frontier stale known count, T is the number of steps since the
last paid scan. These route length/band and time constants are inherited
from DAO, not tuned to the observed cases. The point-grid route is not the
actual footprint-aware G1 action sequence. It may be wrong or uninformative.

- Route Gate: replace D by D AND (NOT R OR N_R>0).
- Deadline: replace F by F AND (NOT R OR S>0 OR T>=10).
- Joint: apply both substitutions.

Age5 anchor and verification predicate are unchanged. Unavailable route
preserves the original policy. The fallback gate addresses the known
possibility of repeatedly requesting scans for invisible old cells,
not a demonstrated cause of the six attenuation-associated extra scans.
Its deadline limits deferral of an active original fallback based on
time since the last actual paid scan; it does not ensure each cell becomes
visible or recollected. Do not infer mapped occupancy from emergency
measurements. No additional real sensing. Each variant is a same-state
subset of original DAO-Veto requests, not necessarily fewer episode
scans. Joint is a subset of each individual gate but not necessarily
their exact Boolean intersection.

All variants add one public point-route plan per decision. Report this
overhead and scheduler time; no actual alternative collision query.
Do not change frozen safety, G1 planner, sensor geometry, cap20, or memory
semantics. Do not tune thresholds or automatically select a winner.

## Frozen comparison

Reuse the exact 26 hand scenes and previous 2 common safety versions
(original and RES-H1 Phase Wait), with Periodic4, Age4, Age5, CAA-Full,
DAO-Veto and three new arms. 416 episodes, 260 reference parities.
Phase Wait is not approved common safety infrastructure. These are
reused engineering scenes, not independent efficacy data, and not
an additional FIT72 screen. Report each safety condition separately.
All actual contacts count; the proven unavoidable first-transition
classification applies only to designated prior timing fixture.
No new population/reserved access or production-pilot authorization.

Test the pure rule, no-route control, same-state subset, isolation of
verification, original fallback deadline, combined rule and authorized
controller/cap behavior. Run preceding regression suite. Recheck prior
manifests, original 2907 receipt/checkpoint pairs, 836 protected files,
CAA artifacts and G1 assets. Record all episodes, failures, actual paid
and emergency ray counts, selected-only shield checks, paired common
success steps and distance, contact-free completion, suppressed request
and grant counts, gate predicate activations, public route-plan calls,
scheduler runtime where measured and wall time. Do not use total
distance of failed paths as efficiency evidence.

Run scripts/run_route_gated_dao_veto_v1.py check, run, report. Write
exclusive results/phase2_mujoco/route_gated_dao_veto_v1 outputs.
Local correctness and navigation runs are pending at source freeze.
The current production generator/admission/custody/statistical blockers
remain unresolved. This empirical mechanism comparison cannot establish
independent generalization or authorize pilot execution.
