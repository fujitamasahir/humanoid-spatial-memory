# Proposal: independent Phase 2 observation-policy cohort

**Status: proposal only. No environment population was generated, admitted, or
opened for this work. Owner approval is required before any execution.**

## Purpose and estimand

Estimate whether a frozen observation policy improves the joint goal-completion,
safety, paid-sensing, and navigation-cost tradeoff over Periodic/Age on new
lineage-disjoint indoor layouts. A maze is the independent sampling unit;
schedule variants within a maze are paired repeated conditions, not independent
samples. The policy and implementation commit must be frozen before the sealed
evaluation partition is made accessible.

## Generator and distribution

Use a new, versioned Phase 2 layout generator with a published schema and
deterministic seed derivation, not the protected Phase 1.5 generator/store.
Generate indoor grid mazes over a predeclared distribution of dimensions,
branch density, loop density, dead ends, corridor widths, start/goal separation,
and start/goal orientation. Include multiple structural families: tree-like
corridors, loop-rich layouts, rooms with narrow connectors, and mixed open/
narrow regions. Keep cell scale and G1 footprint assumptions fixed at the
declared Phase 2 values.

For each layout lineage, independently sample persistent object changes
(additions, removals, relocations, and unchanged controls) and transient
pedestrian schedules (static, periodic, and seeded stochastic trajectories).
Keep schedule pairs linked to the same base layout and change realization where
the protocol calls for a paired comparison. The generator may use a fixed set
of public, preregistered distributions; it must not copy FIT72 topology or
change frequencies.

### Smaller mechanism-development pilot (proposal only)

Before the larger development cohort, a **24-lineage pilot** could check the
generator and topology instrumentation without serving as an efficacy test.
Allocate six lineages to each of four preregistered families: tree-like
corridors, loop-rich layouts, rooms with narrow connectors, and mixed
open/narrow regions. Pair two schedules per lineage (48 map-schedule cases).
The suggested four arms are Periodic, Age, frozen C0, and the then-frozen
candidate, for 192 policy-episodes. Do not select weights or claim efficacy
from pilot navigation outcomes; any algorithm change requires a new protocol
and untouched evaluation partition.

Pilot parent seeds and lineage IDs must occupy a separate namespace from the
80-lineage development and 200-lineage sealed-evaluation partitions. Use the
same exact-map, rotation/reflection/translation, graph-isomorphism,
corridor-profile, and near-topology duplicate checks. Quarantine duplicates;
do not replace them according to outcomes. Admission records source payload
hashes, seed derivations, family labels, duplicate signatures, generator
commit, and custodian approval before controller access. The protected Phase
1.5 population is never an input or fallback source.

For a rough runtime budget only, the local historical FIT72 store has 72 Age
episode records with median wall time 0.123 s (mean 0.145 s, maximum 0.403 s).
At the median, 192 pilot episodes imply about 23 seconds of episode runtime,
before generator startup, logging, integrity checks, and analysis. Budget at
least 10 minutes locally and report measured elapsed time. This estimate is
machine/configuration dependent and is not a performance guarantee.

## Lineage partition and duplicate checks

Create disjoint generator parent-seed namespaces and lineage IDs for development
and evaluation. No parent seed, map-generation RNG stream, object-change stream,
or pedestrian stream may cross partitions. Before admission, check exact
canonical-map hashes, rotations/reflections/translations, graph-isomorphism
signatures, corridor-width profiles, and near-duplicate topology distances.
Keep connected component, dead-end, loop, junction, and start/goal-distance
summaries to verify distribution coverage. Quarantine duplicates and record
their hashes; do not replace them based on policy performance.

Proposed initial allocation: 80 development maze lineages and 200 sealed
evaluation lineages, with two paired schedules per layout. The 200 evaluation
lineages target approximately 80% power for a 10 percentage-point paired
completion difference if the standard deviation of the maze-level paired
difference is no more than 0.50:

    n ≈ ((1.96 + 0.84) * 0.50 / 0.10)^2 = 196.

This is a planning approximation, not a guarantee. Use development-only blinded
variance estimates to confirm or increase the evaluation count before the
evaluation partition is sealed. Never reduce sample size based on observed
evaluation outcomes. Report cluster-level confidence intervals and all paired
maze deltas; schedules are averaged/clustered within maze.

## Development, policy freeze, and access control

Development worlds can be inspected by the implementation team. Use them for
debugging and preregistered engineering decisions only; document any iteration
and freeze a new protocol before any evaluation access. The sealed evaluation
store should be owned by a separate custodian or a gated runner. Policy authors
receive only schema and aggregate validation status before freeze. After freeze,
an automated runner admits each evaluation world, runs the predeclared matrix,
and publishes metrics with provenance. Raw evaluation maps and per-step
trajectories remain read-only and unopened until all arms complete and the
analysis script is committed. No selective reruns or parameter updates after
opening results.

Hash the generator, admission code, source environment payloads, schedules,
policy sources, config, and result artifacts. Preserve an immutable inventory
for each partition. Require explicit access logs for evaluation-store reads.

## Primary outcomes and decision rules

Primary outcomes: goal completion, unwanted contacts, paid memory observations
and rays, total paid plus independent emergency-sensor rays, and steps/distance
among paired common successes. Secondary outcomes: H80-censored steps,
blocked actions, emergency interventions, false-persistent occupancy, missed
persistent changes, EVI V/D and authorization reasons, A* calls, scheduler
time, and wall time.

Predeclare a joint improvement rule: no increase in unwanted contacts; completion
not inferior by more than 3 percentage points; and a paired reduction of at
least 10% in **both** total sensing rays and common-success navigation cost,
with maze-cluster 95% intervals excluding zero for both designated benefits.
Report each component even if the joint rule fails. Reject the policy if safety
is worse, completion crosses the non-inferiority margin, either cost reduction
is unsupported, or results depend on a small subset of lineages. Exact margins
and multiplicity handling require approval before generation.

## Required owner approvals

Before any cohort work, the repository owner must approve: (1) the new generator
schema and version; (2) distribution ranges and environment families; (3) the
24-lineage pilot scope, if desired, and 80/200 allocation or a justified
alternative; (4) the seed/lineage partition
and duplicate-admission rules; (5) the primary benefit, safety/non-inferiority
margins, and multiplicity plan; (6) the independent custodian/access mechanism;
and (7) the frozen policy/source commit and exact evaluation matrix. This
proposal itself performs none of these actions.

## Multi-step sensing extension (C v2.1; proposal only)

The same unapproved 24-lineage pilot and 80/200-lineage partitions could also
measure whether a sensing opportunity disappears before a later navigation
choice. This addition grants no generation, admission or access permission.
Predeclare coverage of shared route prefixes, delayed branch decisions,
revisitable versus one-time viewpoints, turns/FOV loss, long/short sight lines,
persistent occluders and pedestrian-induced temporary occlusion. Cross these
mechanisms with unchanged controls and persistent additions/removals/relocations;
keep layout, persistent-change and pedestrian RNG streams lineage-separated.
A future generator must sample these conditions independently of FIT examples,
not copy the hand-built C v2.1 public-memory fixtures.

The candidate matrix should freeze selector (C-K versus Topology3-d), one-step
versus bounded multi-step value and explicit future visibility separately.
Track predicted and realized later observability only from authorized actual
scans, along with missed opportunities, computation, total ray workload and
common-success navigation cost. Missing subsequent observations are missing
evidence, not confirmed visibility predictions. A custodian may retain hidden
labels for retrospective evaluation, never online inputs. Update pilot sample
allocation and runtime budget before approval to account for the additional
arms and future-footprint computation; historical Mac timings must not be used
as same-machine benchmarks. All existing lineage, sealing, duplicate and
owner-approval requirements above remain in effect.

## Fixed-age and CAA scheduling extension (proposal only)

Age-5 is an additional mandatory frozen strong baseline, alongside unchanged
Periodic and Age-4. Include fixed Age-6 and CAA-Fast/Slow/Full to distinguish
history-dependent acceleration, stable-region delay, their combination and a
uniformly longer deadline. The CAA hypothesis concerns scheduling only; keep
ternary last-write memory and the original G1/sensing/safety pipeline fixed.
No EVI/topology/visibility or persistence inference is required for this test.

Before any new cohort generation, predeclare distributions with independently
varying stable/dynamic region exposure, authorized revisit frequency, long
unobserved gaps, transient occlusion and persistent additions/removals. Changes
must be exogenous to policy decisions. Include no-change and sparse-revisit
controls: a method cannot infer stability merely because a cell was not seen.
Sample new lineages rather than copying FIT examples or the six retrospective
Age/Age-5 flips. Keep both schedules paired and analyze by maze cluster.

Choose primary independent criteria and the comparison with Age-5 before
opening outcomes; do not transfer an absolute66/72 FIT goal threshold to a
differently sized cohort. A gain over Age-4 alone is insufficient if it does
not improve on Age-5. Report paired safety/completion, paid and total sensing,
common-success navigation cost and computation together. Freeze exact CAA
source/history semantics before sealed evaluation; no FIT-derived tuning.
The24-lineage pilot and80/200-lineage cohorts remain unapproved, ungenerated
and unopened; all owner/custodian/admission requirements above remain.

## Concrete DAO prospective design (proposal only)

The detailed [DAO navigation protocol](dao_independent_navigation_protocol.md)
now specifies layout/event distributions, partitioned streams, exact/near-
duplicate admission, custodian access, candidate selection/confirmation,
strong Periodic/Age/CAA controls and proposed joint endpoints. For DAO it
supersedes the older four-arm pilot suggestion and informal200-lineage power
rationale above.200 independent lineages do NOT automatically justify a
3-percentage-point completion noninferiority margin: with paired-lineage
SD0.50 the stated approximation needs2181, not200. Size, margins and analysis
validation require explicit prospective approval. The24 pilot and80 development
lineages and provisional200 sealed lineages are all ungenerated, unadmitted
and unopened. No reserve access is authorized by this update.

## DAO integration follow-up and exact pilot proposal (still NOT approved)

The [exact pilot plan](dao_pilot_v1_protocol.md) specifies24 lineages (six/family),
two schedules and12 Periodic/fixed-age/CAA/DAO controls:576 proposed episodes.
The [integration report](dao_integration_research_report.md) records actual
pedestrian contacts, generator connectivity correction and approximate-CI
undercoverage. These are production-readiness blockers, not independent
validation. New generator/admission/statistical infrastructure is TEST/SYNTHETIC
only; no independent custody or complete prior-signature admission exists.
The80 development and sealed evaluation populations remain ungenerated;
sealed n is undecided. Approve distributions, safety engineering, admission/
custody, analysis coverage/margins and scope before ANY production payload.

## Safety readiness update after prospective common-safety benchmark

The common predictive safety v1 candidate is rejected after416 hand-defined
engineering episodes: it removes archived regression contacts but loses goals
and introduces new contacts elsewhere. See
[`predictive_safety_pilot_readiness.md`](predictive_safety_pilot_readiness.md).
This does not approve the24-lineage pilot or any production generation. All
previous distribution/admission/opaque-signature/custodian/statistical/margin/
sample-size approvals remain pending. No DAO winner or new population was created.
