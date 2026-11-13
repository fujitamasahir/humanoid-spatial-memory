# Persistence memory B and approximate navigation information value C

Protocol frozen before candidate execution, 2026-11-13. Engineering hypotheses,
not calibrated EVI or evidence of novelty. No FIT outcome fitting is permitted.

## Audit and interfaces

`evaluation.run_episode` owns real observations, observation accounting and the
selected-action shield. `ObservationController` owns a last-write grid and the
frozen Age observer. The new controller composes that observer rather than
changing its timestamps or thresholds. A new optional public navigation-context
callback passes pose, heading, goal and unknown-cell planning mode before decide;
no world, sensor, emergency measurement, evaluator labels or future events pass.
The original G1 model, planner, emergency sensor and shield stay authoritative.
Counterfactual planning uses the public grid only and never calls a shield.
Existing RDAO/Event code and frozen evidence are immutable comparators.

## B state and equations

Each cell retains last observed ternary state z, timestamp t, counts n01,n10,
and endpoint-conditioned exposure T0,T1. Between observations, a two-state
continuous-time Markov approximation predicts

    a=(0.3+n01)/(30+T0), b=(0.3+n10)/(6+T1)
    p(s)=a/(a+b)+(q-a/(a+b))*exp(-(a+b)*(s-t))

where q is .95 for observed occupancy and .05 for observed free space. Rates
are clipped to [.001,.35] per navigation step. Endpoints do not identify all
intervening flips: these are approximate rate estimates, not likelihood-exact
continuous monitoring. Exposure uses the PREVIOUS observed state and elapsed
time; flips require two actual observations. No inference increments counts,
timestamps or paid observations. Unknown cells remain p=.5 and explicitly -1.
Persistence confidence is exp(-b*8), interpreted only as model survival of
occupancy for eight steps, not a semantic probability of furniture. No class
labels or transient/persistent ground truth can be inferred from this sensor.
Public grid: known cells p<=.2 free, p>=.8 occupied, otherwise unknown.
Uncertain cells last observed occupied remain occupied until p<=.2 (conservative
hysteresis); this delays clearing and must be tested for false persistence.
The existing unknown planning mode remains explicit and unchanged. Inference
map changes are logged separately from observed changes.

Priors and thresholds above are hand-set dimensional assumptions; no fit-world
search. Isolated synthetic sequences test behavior, not estimate parameters.
B-only uses the ORIGINAL Age scheduler on its independent last-write history.

## C approximation and bounded computation

A ray footprint is estimated on public memory with 61 rays, actual configured
range, FOV and cell size. Rays stop at remembered occupied cells, including the
first-hit cell; unknown cells do not create invented occluders. This is an
optimistic visibility approximation, not an actual or shadow sensor scan.
C-only derives symmetric age-decayed probabilities from last-write timestamps
(fixed rate .05, confidence .95); B+C uses B probabilities.

A bounded shortlist (at most three visible uncertain cells) is ranked by
uncertainty and proximity to the nominal public-map route. For each cell,
public-map free/occupied plans define two possible observation outcomes.
For each resulting route r and outcome o, loss L(r,o) is path length plus a
fixed 80-step failure penalty if r crosses the occupied candidate. No-route
cost is 80. Expected regret is

    V = min_r E_o L(r,o) - E_o min_r L(r,o).

The selected cell's nonnegative V (maximum, never sum of overlapping values)
is a heuristic navigation information value. Postponing one step costs the
predicted first-action disagreement fraction times V; the remaining V is
assumed recoverable later. Compare this avoidable delay regret against scan
price .5 step, fixed compute price .01 per counterfactual plan and a scarcity
surcharge .5/(remaining budget). At most seven A* calls per decision (nominal
plus two per candidate), no Monte Carlo or hidden queries. Measured wall time
is logged, but never affects decisions/reproducibility. Uncertainty alone cannot
request a scan: positive decision regret and delay risk are both required.
The shortlist, point-robot public A* proxy, endpoint probability model and
perfect single-cell revelation assumptions preclude a calibrated EVI claim.
Actual G1 planning still uses its original full footprint and safety stack.

Log predicted V/delay regret, compute, scan decision, realized map changes,
public route and first-action changes. Realized route shortening is a proxy,
not realized causal utility: true causal value needs matched replay. No-scan
counterfactual navigation outcomes are unobserved.

## Evaluation and rejection

Arms: frozen Periodic, frozen Age, B+Age, C+ternary, B+C. Reproduce baseline
metrics AND semantic traces before running candidates for each matched key.
Cap20 includes initial scan; memory rays=61*paid scans; emergency scans/rays
remain separate. H80 and seed42 frozen. Never overwrite result directories.
Save source commit, dirty diff hash, parameters, dependency versions and evidence
hashes. Verify preserved Phase1.5 prefixes before/after. Admit FIT payloads only.

Primary: completion, unwanted contacts, paid observations, H80-censored steps,
and steps/distance restricted to paired common successes. Secondary: memory
rays, emergency scans/rays/interventions, blocked attempts, calibration (Brier,
log loss and reliability bins BEFORE observations), inference changes, scheduler
compute, predicted versus route-change proxies. Calibration at observed cells
is policy-selected; it cannot establish global calibration. False persistent
occupancy and missed persistent geometry require evaluator-only labelled
longitudinal geometry, never online inputs; without it report unavailable,
not zero. Sensor hits do not identify persistent classes. Adaptation is tested
with known synthetic transient and sustained histories.

Reject B if it does not reduce false persistence/missed changes and improve
calibration against last-write/Age on independent labelled evaluation; reject C
if it fails to reduce paid scans AND common-success movement cost without
losing completion or safety; reject combined hypothesis under the same joint
gate. No claim of success based on shortened failed trajectories. Report all
paired rescue/harm counts. On an authorized independent cohort, bootstrap paired
maze-level means (both schedules sampled together), report intervals and all
primary outcomes, never treating two schedules as independent layouts.

FIT72 is descriptive engineering evidence only, not confirmation or tuning.
No legitimate independent cohort is currently authorized. A next study requires
owner-approved population generation/admission with lineage-disjoint development
and sealed evaluation maze IDs, frozen policies/source before opening evaluation,
and separate approved access controls. Do not synthesize admitted payloads,
open reserved material, or modify the Phase1.5 population. Independent hypothesis
tests remain blocked until that process exists.
