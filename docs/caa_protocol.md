# Change-aware Adaptive Age (CAA) v1: prospective FIT development protocol

Starting commit b4fa534bfbcf6944766af743cbe5bc56cbdaffe5; university-library Mac,
Python3.12 `.venv`. Freeze this source/protocol/matrix in a committed binding
before new-policy navigation outcomes. No threshold sweep, outcome-based
selection, new iteration or post-run policy adjustment. FIT72 is repeatedly
inspected development material, not independent validation.

## Prior evidence and additional frozen baseline

Age-5 is fixed as an additional strong baseline:66/72 goals,770/72 paid scans,
3044/72 H80 steps,0 unwanted contacts in the latest saved screen. It improves
paid sensing against Periodic/Age, not novelty or both sensing/movement costs.
Preserve the original `cadence_age.py`, its parameters and archived artifacts.
Use that exact historical controller for Age-5 replay and evaluation.

Before implementing CAA, replay Age/Age-5 and match all144 saved metric/semantic
traces. Audit all72 keys for initial versus noninitial scan content (new cells,
changed known cells, unchanged known cells and empty readings). Characterize
all6 outcome flips, first scan/memory/action/pose/heading differences, observed
changes, stale occupied/free raster counts, blocked attempts, emergency
interventions and exhausted budgets. Newly known and changed-known categories
may overlap; unchanged-only and empty are separate. Retrospective labels and
saved outcomes never enter the policy. Do not infer causal scan benefit from
associations or optimize thresholds on these traces.

## State and update semantics

For each cell i retain the last authorized observed state z_i∈{0,1}, timestamp
l_i, repeated observation count r_i, observed endpoint transition count c_i,
last transition DETECTION timestamp d_i (initially absent), current consecutive
unchanged reobservation count u_i, and run-start timestamp b_i. Unknown cells
have l_i=-1; no evidence of stability is assigned to them. The public map is
ordinary ternary last-write memory. No probability, inference update, semantic
object label, simulator state, goal/path feature or sensor-footprint prediction
is used in scheduling.

On an authorized ternary reading o at time t, update ONLY cells o_i>=0:

* First observed: z_i=o_i, l_i=b_i=t, r_i=c_i=u_i=0, d_i absent.
* Reobserved: increment r_i. If o_i differs from the LAST OBSERVED z_i,
  increment c_i, set d_i=b_i=t, u_i=0. This is an interval-censored endpoint
  change detected now, not knowledge of the true transition time.
* If unchanged and t-l_i<=6, increment u_i and keep b_i. If unchanged after a
  gap>6, restart b_i=t,u_i=0: a long unobserved interval is not evidence of
  continuous stability. r_i still counts the actual reobservation.
* Store z_i=o_i,l_i=t. Unknown outputs change no cell history or memory.

An empty authorized scan consumes one paid observation and advances only the
scan-level clock, not any cell statistic. Initialization is the first paid
scan at time0. Later refreshes must consume a current decision grant and use
strictly increasing scan timestamps; decisions use monotonic integer time.
Invalid observations/times are rejected before mutation.

## Classification, priorities and deadlines

All constants below follow observed-history semantics and the declared
4/5/6-step deadlines, NOT FIT optimization:

1. **Changing:** known, with a detected transition and 0<=t-d_i<=10. The recent
   detection window is two nominal5-step intervals, allowing reobservation
   after an observed change without assuming its semantic cause.
2. **Stable:** not changing; u_i>=3 consecutive actual unchanged reobservations,
   l_i-b_i>=12 (two6-step intervals), and t-l_i<=6. Every unchanged link in that
   run has gap<=6. Thus at least four actual readings span the run; elapsed
   time alone cannot promote stability. Freshness expiration removes stable
   classification rather than inventing evidence through an unobserved gap.
3. **Intermediate:** other known cells. Unknown is a separate excluded class.

Changing takes priority over stable if conditions ever coincide. Detection
window/freshness boundaries are inclusive. Stable exposure is l_i-b_i, not
current time minus run start. Endpoint equality can conceal intervening changes;
these classes are scheduling heuristics, not calibrated environmental labels.

Deadlines: CAA-Fast uses4 for changing,5 otherwise; CAA-Slow uses6 for stable,
5 otherwise; CAA-Full uses4/5/6 for changing/intermediate/stable. Original local
set S is the known cells in the unchanged Age isotropic radius. The score is

    score(t)=sum_(i in S) 1[t-l_i >= tau_i] / |S|, or0 if S is empty.

Request iff t>0 and score>=the existing Age stale-fraction threshold. Apply the
original remaining budget afterward (cap20 includes initial scan). Equality at
a deadline/threshold is due; there are no randomized tie breaks. Goal, heading,
route, blocked feedback, hidden categories and future schedules are unused.
Cell classifications may expire with time but never write occupancy or count
as observations. No recent-change event alone forces a scan outside this score.

## Frozen matrix and computational scope

Exactly7 arms: Periodic, Age-4, frozen Age-5, fixed Age-6, CAA-Fast, CAA-Slow,
CAA-Full. Preserve original Periodic/Age/Cadence sources. Age-6 changes only
original AdaptiveParameters.age_steps to6. No EVI, topology, future visibility,
new events, persistence occupancy inference, G1-aware counterfactuals or sweep.

CAA uses NumPy masks and incremental history updates. N=map cells and
W<=min(N,(2*ceil(radius)+1)^2) local window cells. History update/initialization
is O(N) per actual observation, auxiliary state O(N). Classification and score
inside decide are O(W) using a cropped circular mask, with O(W) temporary
memory. No extra A*, predicted raycast or real sensor call by the scheduler.
Updates do not iterate over trajectories or replay hidden data.

Instrument EVERY arm with the same outer timing boundaries: core decide,
core authorized refresh, and episode wall time. Record diagnostic/logging time
separately; global class/deadline counts are an O(N) observer outside core
scheduling time. A shadow authorized-history ledger is used identically for
all7 arms for diagnostics, never as a baseline decision input. The frozen
Age-5 compatibility controller retains historical unused probability/logging
work; its API runtime is not a pure mathematical score-kernel benchmark.
Existing post-scan logging may use the common point planner in that frozen
controller. CAA itself has zero planning; normal G1 planning/safety remains.
Do not present omitted/zero-placeholder prior timings as measured baselines.

## Correctness, data and execution gates

Require tests for stable/alternating histories, new change after stability,
long gaps, insufficient history, unknown/empty observations, monotonic times,
changing/stable transitions, original last-write identity, exact uniform5
score/decisions, cap exhaustion, authorized-only updates and deterministic
replay. Add independent scalar history/reference checks on seeded histories
and guard tests proving no world/sensor/planner access in the new module.
No formal synthetic efficacy/population claim is made.

Verify read-only all2,907 checkpoint/receipt pairs and836 protected files,
original admitted36 FIT mazes, original G1 assets, fixed dependencies and old
result manifests. Before any full run, commit source fingerprints/protocol,
pass correctness, and execute first2 sorted keys ×7 arms (14 episodes).
Require Periodic/Age/Age-5 saved metric and semantic parity, actual61-ray paid
sensor-call timestamps/counts, emergency channel accounting, selected-only
shield calls, cap20 and0 unwanted contacts in smoke. Then run exactly72 keys
×7 arms (504 episodes) once. Require baseline reproduction at all72 keys and
first2 full keys identical to smoke. Stop on any invariant failure, preserve
partial results and do not repair/rerun in this version after outcomes.

Use seed42, H80, original0.75m grid/G1 kinematic root, original sensor/FOV/range,
independent emergency safety and selected-action collision shield unchanged.
No raw store writer/generator, reserved read or new cohort is authorized.

## Metrics, attribution and decisions

Report goals/contact-free goals, contacts, actual memory scans/rays, actual
emergency scans/rays, combined rays, H80 steps, blocked actions, emergency
interventions and original evaluator-only memory-error sums. Report new,
changed/unchanged scan content; global/local changing/intermediate/stable/
unknown counts; deadline counts; scheduler/history-update/logging/episode time.
At each CURRENT public history, compare the CAA request with uniform5 and the
other CAA ablation scores. Label advanced/deferred decisions as SAME-STATE
counterfactual attribution, not a causal episode/scan effect. A denied request
is never a paid observation. Global diagnostics do not affect the core.

Pair every candidate with Periodic/Age-4/Age-5. Report rescues/harms, common-
success mean steps/distance and all-episode H80 censoring. Use36 maze-cluster
means (both schedules together), plus exploratory2,000 whole-maze bootstrap
intervals, seed2026111403. No iid-schedule or independent validation claims.
Report the complete7-arm matrix and all ablations, not a selected winner.

Primary descriptive target:0 unwanted contacts AND (>66 goals OR66 goals with
mean paid scans<10.694). Since the historical Age-5 total is770 across72 keys,
beating that rounded threshold requires a total<=769, the same integer rule
as improving on exact770/72. Also evaluate simultaneous paid-sensing AND
common-success step/distance reduction without losing completion/contact-free
completion against each of Periodic, Age and Age-5; separately report combined
ray workload. Shorter failed paths are never an efficiency benefit.

A negative result is valid. A positive FIT result is not novel algorithmic
contribution or independent generalization. Freeze the outcome; do not tune
CAA or start a new iteration automatically. Update the independent cohort
proposal with Age-5 and CAA comparisons, but leave24/80/200-lineage proposals
unapproved, ungenerated and unopened. Recommend independent evaluation through
an explicitly approved process instead of continued FIT search.

## Outputs and commands

Dedicated root `results/phase2_mujoco/caa_v1/`; refuse overwrite. Preserve old
results and the retrospective adapter source snapshot. Commands are provided
by `scripts/run_caa_fit72.py check|smoke|full|report`; `audit_caa_history.py`
is the pre-implementation audit. Source binding must be committed before
smoke. Save dependency/platform, source commit/hashes, config, raw traces,
class/deadline/scan ledgers, manifests, figures and actual command receipts.

The paired analysis also includes each CAA arm versus fixed Age-6 and Full
versus Fast/Slow, so the ablations are evaluated on matched common successes,
not only compared through aggregate means. These contrasts are fixed before
new-policy navigation. All17 contrasts are exploratory and unadjusted.
