# DAO independent navigation protocol — proposal v1, NOT approved

No population, seed list or world payload is produced by this document. The
48 hand-defined DAO public states are engineering fixtures, not cohort samples.
This detailed DAO proposal supersedes the older four-arm pilot and informal
200-lineage power rationale in `independent_cohort_proposal.md` for future DAO
work. It grants no generation, admission or access authorization.

## Frozen findings and purpose

Keep Age5 and CAA sources/results frozen at their recorded commits. CAA's two
saved scans in one reused FIT case do not justify more FIT optimization.
Discovery-based prediction needs independent navigation evidence, including
unknown-space occlusion failures and periods of low discovery with important
known-cell changes. The objective remains a meaningful safety/completion,
sensing AND movement improvement, with computation included.

## Proposed schema `dao-nav-v1`

Each immutable lineage payload must record schema_version, partition,
lineage_id, parent_seed_commitment, generator/admission commit, family,
dimensions, cell_size_m, base ternary-independent true occupancy, start,
goal, start_heading, static-object cells, persistent change program, two
pedestrian schedule programs, mechanism strata, canonical geometry/graph
signatures, admission decisions and parent roots. Occupancy truth and schedule
programs are custodian/evaluator inputs, NEVER policy inputs. Controller
observations remain the existing paid61-ray MuJoCo sensor plus the independent
emergency safety channel; the scheduler cannot inspect payload truth.

Proposed width/height independently uniform over {25,33,41} cells, scale0.75m;
wall boundary, axis-aligned cells and fixed original G1 collision geometry.
Maximum41²=1681 cells fits DAO's4096-cell bound. Uniform start-heading among
four cardinals; choose start/goal uniformly from accepted traversable endpoints
with public-geometry baseline geodesic between12 and60 cells. Admission uses
layout-only traversability certificates with the fixed G1 footprint; no
controller success, number of scans or policy route enters admission.
Keep horizon80 for comparability, and report geometry path-length distributions
so difficulty-induced censoring is visible. Do not reject hard layouts based
on policy performance. Predeclare at most100 generation attempts/lineage;
quarantine failure and stop for protocol review if the quota cannot be met.

Four structural families, equally allocated:

1. Tree corridors: randomized spanning-tree rectangular room/corridor graph;
   corridor width sampled from {1,2,3} cells; no added graph cycle.
2. Loop corridors: same construction plus independent non-tree connectors,
   10–30% of eligible edges, uniformly sampled probability per lineage.
3. Rooms/connectors: rectangular rooms with side lengths4–8 cells and1–2-cell
   doors; connected room graph; 0–20% extra connectors.
4. Mixed open/narrow: room construction with20–40% interior area left open,
   narrow connectors of width1–3; fixed boundary and connected free component.

Ranges are proposed design choices, not estimated from FIT. The generator
implementation must specify exact integer rounding/placement and be reviewed
on additional hand-defined fixtures BEFORE approval. No production generator
is implemented or silently substituted in this task.

Cross family with two predeclared discovery/revisit strata in equal allocation:
long straight sightlines/frequent reversible junctions versus occluded turns/
rooms with rare returns. Layout construction knobs encode straight segments
of4–8 versus1–3 cells and loop/cul-de-sac depths2–8. These are environment
geometry strata, not labels computed from a candidate's achieved route.
Record realized structural descriptors for coverage; report mismatches, do
not replace samples based on controller-specific discovery.

Persistent condition is independent categorical unchanged/add/remove/relocate,
each probability1/4. For changed conditions sample1–3 eligible object cells,
start times uniformly from integer steps10–50 and durations through80. At
admission ensure the static base and post-change map retain at least one
start/goal G1-traversable route; retain temporary blocked alternatives.
Removal candidates are preregistered movable objects, not structural walls.
Relocation pairs independent removal/addition cells in a single event. Events
are indexed by global episode step, not triggered by a policy's entry.

Both schedules share layout, persistent changes and pedestrian path geometry.
Choose0,1 or2 pedestrians uniformly; trajectories use predefined free-space
waypoint loops, 4–12 waypoints, speed0.25–0.75 cell/decision and pause0–3 steps.
Schedule0 is a uniformly sampled starting phase; schedule1 uses a separately
sampled phase and pause stream on the same geometry. Include explicitly
balanced static/no-person and moving/temporarily occluding conditions via a
predeclared stratum table (one third each), not rejection after sensing.
Track occlusion potential from geometry/programs for coverage only. Motion
must be exogenous and reproducible across policies with original contact
shield/safety handling, not reveal a future schedule to the controller.

## Namespaces, streams, sealing and admission

Proposed partition sizes: pilot24×2 schedules (six lineages/family), dev80×2
(20/family), sealed200×2 (50/family) initially. The sealed size is provisional
and must be revised BEFORE generation if the power calculation below demands
more. Assign strata cyclically from a public table, not efficacy outcomes.
The same lineage's schedules always remain in one partition.

Custodian samples a secret256-bit master per partition. Derive each named
stream via HMAC-SHA256(master_partition,
 `dao-nav-v1|partition|lineage_index|stream_name`). Stream names are layout,
objects, persistent, start_goal, pedestrian_geometry, phase0, phase1, admission.
Lineage IDs contain partition plus an independent digest commitment. No FIT
root, seed or geometry is a generator input. Commit salted inventory/root
hashes before authors can access development; keep evaluation masters and
payloads inaccessible to authors. Public source must never embed sealed
master seeds. Log all runner/store reads and approvals.

Admission independent of policy outcomes:

- Verify payload schema, deterministic streams, family quotas and base/changed
  geometry connectivity/physical clearance. Record attempted and admitted IDs.
- Canonical map hash: crop empty exterior padding; enumerate all8 square-grid
  dihedral transforms, include transformed start/goal/object geometry, serialize
  lexicographically and SHA256 the minimum. Also store occupancy-only hashes
  so moving endpoints cannot conceal an exact structural duplicate.
- Build a corridor graph by suppressing degree2 chains; label nodes with room
  size/degree and edges with corridor length/width profile. Require exact
  labeled graph-isomorphism checking after hash/WL prefilter; hash/WL agreement
  alone is not a proof of isomorphism.
- Near-duplicate flag if optimally aligned binary occupied/free Jaccard distance
  <=0.05 OR normalized corridor-graph edit distance<=0.10 with matching family
  and dimensions. Bound graph matching work; unresolved matches quarantine,
  never automatic acceptance. These thresholds require owner approval.
- Compare within/across newly proposed partitions and against all admitted FIT
  geometry signatures available to the custodian. Do not open protected or
  existing reserved stores to construct comparison signatures. A custodian may
  supply approved opaque prior hashes; absent such authority, admission is
  incomplete, not a reason to access reserved data.

Keep immutable rejection/quarantine logs. Replace only by the next deterministic
attempt under the same predeclared stratum; never inspect navigation outcomes.
Pilot checks generator coverage/admission/provenance/sensor contracts only.
Pilot efficacy results cannot choose DAO weights or select a winner.

## Development decisions and frozen candidate selection

After separate approval, development data may support model selection. Use
fixed dev lineage split40 selection/40 confirmation, with all schedules grouped.
Only the four predeclared DAO variants are initially eligible. No continuous
threshold search; at most one separately preregistered engineering revision
on selection data, with source/config/reason recorded before opening the40
confirmation lineages. A revision is not implicitly authorized by this proposal.
No return to FIT as the efficacy selector.

Before opening confirmation, select one candidate by the following fixed order:
reject any candidate with contact increase; require selection completion not
below Age5 by >3 percentage points (descriptive engineering gate, not a powered
NI test); among eligible candidates minimize combined rays, then paid scans,
then common-success steps, then distance; exact tie order Veto, Trigger, Route,
Combined favors less mechanism complexity. If none qualifies, select NONE.
On confirmation apply the same safety/completion gate and require both combined
sensing and common-success movement directionally better. No candidate swap
or threshold repair after confirmation; failure closes this candidate study.

Freeze the chosen candidate, generator/environment, analysis scripts, full
source hashes, output schema, statistical margins, sample size and matrix
before any sealed runner read. Sealed results may never select the candidate.
Mandatory sealed controls: native Periodic4, fixed Periodic5, Age4, frozen
Age5, Age6 and frozen CAA-Fast/Slow/Full (8 controls) plus the single selected
DAO candidate (9 arms); run no other DAO winner search in sealed data.
If no candidate qualifies, no DAO sealed efficacy run. Full DAO ablations
belong to development; any sealed ablation is prespecified secondary only.

Use identical paired worlds/schedules and balanced Latin-square arm order for
runtime measurement; fresh simulator reset each episode. Never use a
post-hoc matched-dose clock chosen from sealed outcomes. Descriptive dose bins
and interscan counts reveal whether changes are just frequency changes;
they do not causally separate frequency and content. Any causal forced-scan
or randomized schedule contrast needs a separate approved protocol.

## Estimands, margins and analysis proposal

The independent unit is lineage, not schedule. For each lineage compute the
mean over two schedules of paired candidate-minus-control metrics. Primary
reference is Age5; other strong controls are mandatory comparative evidence.
One candidate only. Use a fixed-sequence gate at one-sided alpha0.025:

1. Safety: any increased unwanted-contact count is an engineering rejection.
   Report per-lineage any-contact risk difference and exact conservative
   zero-event bounds; absence of contacts is not proven equal safety.
2. Goal completion: lower one-sided97.5% bound on paired lineage goal-rate
   difference >-0.03 (proposed NI margin). Three percentage points is a maximum
   acceptable completion loss needing owner scientific justification, NOT
   chosen because200 happens to be affordable. Also report superiority bounds.
3. Combined paid+emergency rays: demonstrate at least10% mean paired reduction
   (upper bound on mean lineage [candidate-0.9*control] <0).
4. Paid scans: demonstrate at least10% reduction by the same contrast.
5. Common-success steps AND distance: each at least10% reduction, with upper
   bounds on paired means of [candidate-0.9*control] <0. Use the paired common
   success subset, report numerator/denominator and per-lineage missingness.
   No common successes => undefined, never zero improvement; less completion
   cannot masquerade as short travel. Report H80 alongside, plus a composite
   goal/failure-penalized sensitivity analysis to show conditioning effects.
6. Compute: proposed scheduler overhead <=5ms/decision and <=10% episode wall
   time increase, assessed with same-machine balanced order and paired bounds.
   These are provisional engineering tolerances, not FIT-derived evidence.

Require all designated components; intersection-union and fixed sequence mean
no success claim if an earlier gate fails. A total10% sensing/movement reduction
is an aspirational meaningful effect, not justified by current synthetic data.
Report all endpoints regardless of gates. Owner may approve different margins
only prospectively before generation and analysis freeze.

For completion propose a lineage-level paired mean CI with t critical value
and a custodian-run null simulation checking coverage/type-I error for the
bounded {-1,-.5,0,.5,1} lineage differences; supplement with whole-lineage paired
bootstrap20,000 draws with a committed independent analysis seed. For ratio
benefits use paired difference contrasts above with whole-lineage bootstrap
bounds; account for varying common-success counts by recomputing the conditional
estimand in each resample. No resampling schedules independently. Degenerate
or sparse data require conservative exact/sensitivity results, not automatic
zero-width intervals. Analysis implementation/coverage validation is pending
and is a prerequisite to cohort approval, not claimed complete here.

All additional comparisons against the other7 controls use Holm correction
within the prespecified endpoint family or simultaneous max-statistic cluster
intervals, specified in frozen analysis code. A claim of superiority over ALL
controls requires every corresponding joint gate; an Age5-only win is not
such a claim. Report paired rescues/harms, blocked actions, all ray channels,
memory errors, class/discovery diagnostics and runtime unconditionally.

## Revisited sample size (planning, not an efficacy result)

For lineage difference D with SD sigma_D, assuming true completion difference0,
normal-approximate NI size is

    n = ceil(((z_(.975)+z_(.8))*sigma_D / .03)^2).

This is not the earlier10-percentage-point superiority calculation. With
z values1.959964 and0.841621, sigma_D=.50 requires2181 lineages, .30 requires785,
.20 requires349, .15 requires197, .10 requires88 (verify exact values in the
saved planning table).200 only suffices under approximately sigma_D<=.1514
and true difference0 before conservative/multiplicity adjustments. With true
loss1 point, replace denominator.03 by.02: required size multiplies2.25.
A true3-point loss lies on the null boundary; larger n does not make it a win.
Schedule correlation and discordance determine sigma_D; two schedules do not
double the independent sample size. No variance estimate from reused FIT is
used to claim adequate independent power.

For a10% cost benefit, power depends on the variance of the paired cost
contrast and the true benefit beyond10%, NOT on the completion NI calculation.
Require joint-power simulation with plausible lineage/schedule dependence,
completion discordance, conditional navigation sample size, contact prevalence
and skewed sensing/runtime costs.80 development lineages may estimate variance
imprecisely; use a conservative upper bound and a blinded custodian review,
never evaluation outcomes. Approve a larger sealed n before generation if
needed, or label the affordable200 study descriptive/inconclusive for NI.
Do not widen the margin after results or imply200 is sufficient by default.

With zero contact lineages out of200, one-sided95% binomial upper risk is
1-.05^(1/200)≈1.49% for the population/condition distribution, not a guarantee
of zero physical risk. Two correlated schedules are not400 independent
trials. Rare-contact safety claims may need much larger samples or separate
stress testing; no ad hoc safety margin is silently inferred from zero counts.

General statistical principle: NI margin and adequate power must be justified
before outcomes; see [FDA NI design guidance](https://www.fda.gov/regulatory-information/search-fda-guidance-documents/non-inferiority-clinical-trials).
This is a statistical design analogy, not a clinical/regulatory framework for
robot navigation. Numerical tables are our explicit normal-approximation
calculations, with their assumptions stated here.

## Exact owner decisions still required

Approve (1) schema/algorithms and family/dimension/event distributions;
(2) duplicate checks, thresholds, prior-hash access and quarantine policy;
(3) pilot24/dev80 scope and proposed9-arm/control budget; (4) a power-justified
sealed size rather than automatically200; (5) safety criteria,3-point NI and
10% benefit/compute margins, estimands and multiplicity/analysis implementation;
(6) independent custodian, sealed infrastructure, seed commitments and read
logs; (7) development selection/confirmation rules and revision budget;
(8) final frozen winner/environment/source/matrix before sealed access.

These are pending decisions for the NEXT experiment, not a permission request
to finish the currently authorized DAO engineering work. Stop here: generate,
admit and access none of these navigation populations or existing reserves.
