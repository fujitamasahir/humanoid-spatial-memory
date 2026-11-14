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
