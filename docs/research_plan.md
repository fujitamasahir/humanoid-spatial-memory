# Research Plan

## Problem statement

Long-term autonomous robots operate in changing indoor environments. Pedestrians may temporarily obstruct corridors or occlude sensors, while objects and furniture may produce persistent changes. Conflating these events can corrupt long-term maps, lead to unnecessary re-observation, and worsen navigation.

## Working hypotheses (not established findings)

**H1 — Persistence modeling:** Explicitly distinguishing transient human occlusions from persistent geometry changes reduces erroneous persistent occupancy updates under partial observability.

**H2 — Task relevance:** Selecting re-observation based on both memory uncertainty and current route/task importance may improve the success-versus-observation-cost tradeoff against uncertainty-only and periodic verification baselines.

**H3 — Biped extension:** Humanoid traversability constraints may change the value of a spatial observation and route choice. Evaluate only after Phase 1 is sound.

## Literature positioning

Memory decay, spatiotemporal exploration, active perception, pedestrian-flow maps, lifelong navigation, and humanoid footstep planning are established areas. **No claim of a new method is justified yet.** The first substantive research milestone is to test whether strong existing approaches actually exhibit the failure mode hypothesized in H1.

Keep a bibliography with verified paper metadata, method assumptions, and reproducibility notes before claiming novelty.

## Three phases

### Phase 1 — Reproducible 2D testbed

- Hidden world state with static walls, movable persistent objects, and dynamic pedestrians.
- Robot receives partial, optionally occluded/noisy observations only; no oracle labels.
- Shared navigation and collision checker across policies.
- Initial sanity baselines: static map, periodic refresh.
- Stronger baselines to add after literature review: change-aware persistence and uncertainty-driven verification.
- Test different pedestrian dwell times, densities, object relocation rates, sensor ranges, and observation costs.
- Log separate train/development/test environment seeds. Freeze test suite before tuning.

### Phase 2 — MuJoCo humanoid scene

- Unitree G1 model in indoor scenes with moving pedestrian proxies.
- Keep spatial memory module largely unchanged to test representation transfer.
- If humanoid pose is kinematically moved, label the evaluation *kinematic navigation*, not physically controlled locomotion.

### Phase 3 — Physically actuated bipedal walking

- Integrate a known compatible pretrained policy.
- Check joint order, actuator interfaces, frame conventions, frequency, and stability.
- Add fall, unsafe foot-placement, collision, and tracking measurements.
- No assumption that macOS M3/8GB is adequate for training a humanoid locomotion policy.

## Decision gate after initial baselines

1. Does naive mapping demonstrably misclassify transient pedestrians as persistent obstacles?
2. Does a strong published persistence-aware baseline still fail under some controlled settings?
3. Are the failures meaningful and attributable to memory, rather than to planner or sensor bugs?
4. Only then implement a task-aware verification method.

## Phase 2 observation-policy status (2026-11-14)

The FIT72 B/C failure analysis is descriptive and complete. A separately frozen
C v2.0 route-candidate ranking proposal was implemented as isolated C-K,
C-Route3, and C-RouteK ablations. Its final public-memory synthetic gate found
that Route3 did not select the unique uncertain chokepoint more often than C0;
the predeclared rule rejected the candidate-ranking mechanism before any new
FIT72 candidate rollout. The FIT72 candidate evaluator is guarded and was not
run. See `docs/c_v2_candidate_coverage_research_report.md`. Do not proceed to
C v2.1/v2.2 without a separately frozen development iteration and, for
independent claims, the lineage-separated cohort approvals in
`docs/independent_cohort_proposal.md`.

The subsequent C v2.0b topology hypothesis produced a nominal synthetic metric
gate pass, but a post-run conformance review found an occupied-cell component
classification defect and structural fixture-label/construction defects. The
formal result is archived as invalid; no causal replay or FIT72 screen was
run. See `docs/c_v2b_topology_research_report.md`; do not treat its numeric
screen as evidence for further FIT work.

C v2.0c is now a separate correctness-first implementation and protocol. An
independent brute-force BFS reference, exhaustive small-grid checks, 1,000
seeded randomized public-grid cases, and pre-policy annotation validation are
required before its 48-case formal mechanism suite. FIT access remains gated
on both the numeric screen and an independent conformance review.

The frozen v2 mechanism screen completed with a numeric rejection: its
topology selector violated the preregistered graph-work bound in 29 of 48
fixtures. The separate review is `INVALID_STOP_BEFORE_FIT`; no causal replay or
FIT access was performed. See `docs/c_v2c_topology_research_report.md`.

## Intended portfolio outcome

Reproducible code, clear research question, defensible baselines, ablations, repeated-seed results with uncertainty, failure analysis, and a candid simulation limitations section.

## Phase 1 foundation implementation

The repository now contains the partial-observation 2D testbed and the static
and periodic sanity baselines only. Explicit JSON layouts separate development
from reserved held-out seeds and layout. The initial comparison is a deterministic
acceptance demonstration, not a test of H1/H2 and not evidence of superiority.
Noise-free seeds repeat the same trajectory and are not independent evidence.
Review `docs/experimental_protocol.md` and the validation record before expanding
the scenario suite or implementing additional algorithms. The simulator uses a
point robot and does not model bipedal traversability or physical walking.

## C v2.1 multi-step observation timing (2026-11-14)

Candidate-ranking development through C v2.0d is frozen. The next separately
scoped hypothesis compares scan-now, bounded delayed-scan and no-information
costs, with and without predicted future sensing opportunity, on matched
C-K and Topology3-d shortlists. See `phase2_c_v21_multistep_protocol.md`,
`c_v21_environment_migration.md` and `c_v21_one_step_delay_audit.md`.
The formal synthetic gate and isolated conformance review must both pass
before any new-policy navigation screen. The original Phase1.5 population and
unapproved independent cohorts remain unchanged. No automatic G1-aware EVI
follow-on is authorized by this task.

C v2.1 v1 completed the numerical synthetic gate and isolated conformance
review, followed by its conditional smoke, 288 new-policy FIT episodes and
two actual-scan schedule contrasts in one maze. All four new policies reached
57/72, with zero unwanted contacts but substantially increased paid sensing.
The joint sensing/navigation objective failed; no independent cohort or
automatic G1-aware follow-on was executed. See
[`c_v21_multistep_research_report.md`](c_v21_multistep_research_report.md).

## Change-aware Adaptive Age (CAA) scope

Age-5 is retained as a frozen simple baseline after the cadence screen:66/72
with770 paid scans. The separately versioned CAA hypothesis adapts only
cell-specific observation deadlines4/5/6 from actual observed transitions and
unchanged-history exposure. It does not change remembered occupancy or use
EVI, topology, future visibility or event triggers. See `caa_protocol.md`,
`age5_frozen_baseline.md` and the pre-implementation audit
`caa_retrospective_analysis.md`. All results remain development-only; new
independent cohorts require approval. No automatic subsequent iteration.

CAA v1 completed 108 passing correctness tests, the 14-episode smoke and
one frozen 504-episode seven-arm matrix. CAA-Fast/Full retain 66/72 goals
and zero unwanted contacts while reducing paid scans from Age-5's 770 to
768 (0.26%). This marginally meets the descriptive primary target, but
common-success movement does not improve; no joint sensing/navigation gain
or independent superiority is established. CAA-Slow exactly matches Age-5
traces; uniform Age-6 loses seven goals. Freeze these development results
and stop FIT tuning. No proposed independent cohort was generated/accessed.
See [`caa_research_report.md`](caa_research_report.md) for all outcomes,
negative findings, paired uncertainty and the proposed independent next step.

## Discovery-aware Observation (DAO) engineering scope

CAA findings remain frozen, including the single-case two-scan saving and
absence of a joint movement benefit. DAO tests public-memory prediction of
never-observed cells, distinct from stale verification and actual changed-known
readings. Frontier predictions stop at the first unknown cell and are compared
with optimistic public-memory rays; neither is a real sensor reading or
calibrated information gain. Four small Age5-anchored variants, fixed controls,
unit tests and a frozen48-public-state mechanism suite are authorized.
See `dao_protocol.md` and `dao_independent_navigation_protocol.md`. Existing
FIT evidence is descriptive only. No new FIT72 screen, proposed navigation
population generation/admission/access or reserved-world read is authorized.

DAO v1 engineering work is complete: 138 focused tests passed; the completed
48-state/432-rule synthetic suite matches independent scalar geometry/count
checks, with cap20 contracts and unchanged original-data/CAA/G1 integrity.
The initial formal artifact serialization failure and harness-only recovery
are preserved. No DAO navigation efficacy is established: formal geometric
fixtures did not activate veto suppression; conservative corridor prediction
can undercount deep discovery. No threshold/fixture tuning or new navigation
cohort/screen was performed. See [`dao_research_report.md`](dao_research_report.md).
The independent proposal remains pending owner decisions and power validation.

## DAO G1 integration and TEST infrastructure (completed engineering task)

Frozen DAO now has a versioned G1 adapter, actual-sensor hand-scene diagnostics,
TEST-only generator/admission logs and synthetic statistical analysis code.
48 completed navigation episodes plus120 separate fixture scans were published;
one incomplete formal attempt and its versioned route-compatibility recovery
are retained.180 integration/regression tests plus18 versioned correction tests
pass. The pedestrian fixture recorded contacts in all four variants: safety
acceptance fails, despite preserved original safety code. No independent
superiority or real DAO winner is established.

Generator v1's off-certificate occlusion treatment disconnected4 TEST layouts;
separate v1.1 preserves original evidence and validates full connectivity.
Approximate CI simulations showed undercoverage; optional conservative finite-
sample bounds trade power/sample size for coverage. Production admission,
opaque prior signatures, independent custody, safety review and approved
statistical/distribution choices remain prerequisites. See
[`dao_integration_research_report.md`](dao_integration_research_report.md) and
[`dao_pilot_v1_protocol.md`](dao_pilot_v1_protocol.md). No production population,
reserved access, full FIT72 screen, DAO retuning or pilot execution occurred.

## Common predictive emergency safety v1 — completed, candidate rejected

The archived DAO pedestrian contacts and Periodic4/Age4/Age5 baselines were
reproduced with exact untreated DAO semantic/metric parity. Stage diagnostics
show contact begins when the discrete pedestrian update is synchronized by
the emergency sensor, before any robot action; directional motion extrapolation
misses reversal. A separately frozen common reachable-set/swept-footprint
candidate was evaluated on416 hand-scene episodes across eight schedulers.
All48 original-safety DAO regression parities pass;216 tests pass.

Reject the candidate: regression contacts12→0 but goals80→72; prospective
contact states25→128 and goals104→80. It creates head-on/narrow contacts and
repeats uncertified waiting; only the first pre-action timing contacts are
proven unavoidable, not later repeated onsets. No thresholds, original planner,
trajectory or update timing changed. Full timelines/figures and all negative
outcomes are in [`predictive_safety_research_report.md`](predictive_safety_research_report.md).
Production pilot readiness remains false; generator/admission/custody/statistical/
power blockers persist. No production generation, reserve access, FIT72 screen,
DAO selection or follow-on iteration occurred.


## Route-Adaptive Age v1 — completed on reused FIT72

The separately frozen Age5-parent Advance/Defer/Joint family was implemented
and evaluated locally:137 passing tests,12 smoke and432 full episodes. Defer
meets the immediate target with66 goals,768 paid scans and0 contacts, compared
with Age5's66/770. Its two savings are terminal scans from one maze lineage;
all72 navigation traces match Age5. Advance and Joint fall to59 goals and are
rejected. Joint sensing/movement improvement and independent generalization
are not established. The first family meets the immediate target, so no
failure-only second revision was run. See [executed report](raa_research_report.md).
No reserved/sealed access, production generation or safety change occurred.
Existing independent admission/custody/statistical and safety blockers persist.


## H2 final36-map evaluation — completed and closed

Owner approval authorized this named final comparison on36 new R/BP/M maps,
two schedules and12 frozen models. It supersedes proposal-only restrictions
solely for this evaluation; the earlier DAO pilot/80/200-lineage populations,
reserved access and safety revisions remain unapproved and unexecuted.

All864 primary episodes completed with0 unwanted contacts. All864 original
FIT replays and864 timing repeats match saved/primary semantics;163 tests pass.
Periodic5 leads observed completion at60/72 with661 paid readings. RDAO v2
reaches59 with628 but adds substantial compute. CAA-Full reaches57/760 versus
Age5's57/763; all three savings occur in two failed episodes. RAA-Defer exactly
matches Age5's72 observable step traces and57/763 total. No robust practical
adaptive superiority or statistical equivalence is established.

H2 observation-scheduling development ends without new models or tuning.
See [final H2 research report](h2_final_research_report.md),
[frozen protocol](h2_final_evaluation_protocol_v1.md) and
[pre-draw backend restoration](h2_backend_recovery_v1_1.md).
The36-map conditional-admission/same-investigator study does not resolve the
earlier independent custody/distribution/safety/statistical readiness blockers.
