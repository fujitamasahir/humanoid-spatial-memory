# Phase 1.5 proposed experimental protocol

Version 0.1, 2026-11-07. **Design only; provisional preregistration for research
review.** No layouts were generated, no policy was implemented and no episodes
were run for this document. The [review](phase1_5_research_review.md) and
[method specification](phase1_5_method_design.md) define the evidence and proposed
algorithms. This is not authorization for development, assessment, held-out or
MuJoCo execution. An actual topology audit and the open design decisions below
must be resolved before a final preregistration can be locked.

## 1. Questions and claim boundaries

Primary hypothesis: decision-aware EVSI (A) improves contact-free goal completion
over quota-periodic timing at cap8, radius3, occlusion on, noise .05, price .02,
without materially increasing actual sensing. The primary method is A, not the
best of A, B and C after evaluation. Budget extension C and joint route heuristic
B are secondary diagnostic methods.

Three claims require separate evidence:

1. **Activation:** a component changes requests/grants. Numerical and trace
   evidence suffices; success need not improve.
2. **Sensing benefit:** extra sensing improves navigation, possibly at higher cost.
   Equal caps alone do not establish useful timing.
3. **Task-aware timing:** navigation improves at controlled observation count,
   including the exactly matched one-call assay below, beyond strong baselines.

No result changes Phase 1.4's confirmatory conclusion or selects new Phase 1.4
parameters. A positive result for A would validate only this bounded grid study,
not general novelty, optimality, physical safety or humanoid transfer.

## 2. Entirely new partitions

All Phase 1.3/1.4 environments and their assessment outcomes are now design
context, not independent Phase 1.5 evaluation data. The reserved old held-out
suite remains untouched. Seeds alone are insufficient separation.

| Partition | Accepted topology/lineage clusters | Generator balance | Use |
| --- | ---: | --- | --- |
| Development-fit | 48 | 12 per mechanism, four mechanisms | Fit public-history transition model only |
| Development-calibration | 24 | 6 per mechanism | Calibration, numerical/activation gates, B's rate match |
| Development-selection | 24 | 6 per mechanism | Locked design go/no-go; never assessment selection |
| Assessment | 160 | 40 per mechanism | One fixed prospective assessment |
| Final held-out | 96 | 16 per mechanism, six mechanisms | Untouched external generalization check under later review |

The four principal mechanisms are independently sampled room/corridor graphs,
BSP partitions, irregular planar room graphs, and mazes with sampled chords.
Final held-out additionally includes cellular free-space and random-geometric
corridor graph mechanisms. These names are specifications for new generators,
not existing templates to relabel. Independence is within and across partitions,
not merely a different grammar label. Cross-grammar graph matches are prohibited.

Allocate seed namespaces 50,000,000–50,999,999 to development,
60,000,000–60,999,999 to assessment and 70,000,000–70,999,999 to final held-out.
Development-fit/calibration/selection use disjoint first/second/third 100,000-seed
subranges. Use separate counter-based namespaces for graph, rasterization,
start/goal, dynamics, sensor noise, algorithm sampling and random schedules.
Never pass these identities to a policy. Accepted counts refer to audit clusters,
not attempted seeds. Rejections are logged without policy outcomes.

Each cluster has one accepted raster geometry/start-goal instance and two
independently sampled dynamics schedules; all methods share them. Use odd grid
sizes 21,23,25, approximately 12–24 abstract regions and initial shortest-path
distances 12–40. Rasterization must preserve abstract connectivity. Initial/final
static connectivity checks may reject malformed geometry, but no policy outcome
may be used to filter worlds. No translations, rotations or goal relocations are
counted as additional topologies.

### Topology audit before finalization

The conceptual audit identifies a real risk: different seeds, corridor lengths,
dimensions, goal placements or graph subdivisions can still instantiate the same
topology. For example, paths of six and ten cells contract to the same corridor;
subdividing a cycle does not create a new route choice. A seed-separated version
of the old template families would therefore fail this protocol.

The required future artifact-only audit, **not performed in this design phase**:

1. Preserve generator lineage, abstract graph and raster. Extract a connectivity
   graph from the raster, merge junction regions, contract degree-two corridors,
   handle pure cycles explicitly, and verify agreement with generator connectivity.
2. Compute exact unlabeled canonical graph certificates, ignoring start/goal,
   coordinates and edge lengths. Canonicalize raster symmetries separately.
   Hashes/Weisfeiler–Lehman signatures are filters, not isomorphism proofs.
3. Union all common-lineage, isomorphic and conservative near-variant records.
   Near variants include equality after one leaf pruning or edge contraction;
   retain transitive components. Compute a coarse block-cut/degree signature
   and reject its cross-partition reuse as an additional conservative guard.
4. Compare against historical topology certificates derived without executing
   historical worlds. Reject historical matches and all cross-partition components.
   Never open or generate reserved old held-out worlds for this comparison;
   audit their already available non-experimental identity hashes if present.
   If necessary metadata is unavailable, record the uncertainty and block the
   independence claim until a reviewed non-experimental solution exists.
5. Allocate complete audit components to one partition. Count only those
   components as clusters. Inspect all certificates and a preselected 20% visual
   sample blind to policy outcomes. Report generator acceptance rates, component
   sizes, graph descriptors, exclusions and descriptor balance.

Canonical nonidentity is necessary, not a proof of stochastic independence.
Independent graph draws and complete lineage clustering are also required.
Coarse signatures may over-collapse worlds; do not relax them after seeing
outcomes. Stop if the target cannot be filled within 10,000 graph proposals per
mechanism. Amend the design before any policy execution rather than substitute
seed-level sample counts. Final held-out audit can be performed by a separate
curator, exposing only counts/certificates and an integrity commitment to the
researcher; its layouts, observations and outcomes remain sealed.

**Audit status today: not empirically verified.** Only the construction plan and
failure criteria have been audited conceptually. Consequently this document is
not a finalized independent-topology preregistration. Generating and auditing
layouts requires the next separately authorized stage; it is not silently done
under a design-only instruction.

## 3. Dynamics, sensors and shared semantics

Horizon T=80; known pose; cardinal moves/wait; step0 observation mandatory and
charged; observation has zero simulated latency. Total caps are 1,4,8, including
initialization. Radius is 3. Cross noise 0/.05 with occlusion off/on, four sensor
conditions. Price is .02 task-loss units primarily; sensitivity prices .005/.08.
Counter-based sensor streams are indexed by environment, time and cell so one
method's call count cannot alter another's possible sensor noise.

Specify dynamics before manifest lock: 20% no-change schedules, balanced within
mechanism; the remaining schedules cross persistent additions/removals,
coordinated 2–4-cell changes, moving temporary occupancy with nonperiodic dwell,
and off-route distractors. Schedule categories may coexist. Event positions and
times are sampled independently of a policy's trajectory. No semantic event
labels are agent inputs. Publish exact sampling distributions in the final
generator specification; they remain an open prerequisite, not an invitation to
choose successful scenarios. Include model-misspecification stress (long dwell
and larger coordinated changes) in final held-out, without inspecting its results.

Retain shared world advancement/contact accounting and observation noise
semantics. The proposed common belief/planner is new and shared by every row.
Log actual contacts and failed attempts in the evaluator only. No policy gets
future occupancy, truth visibility or evaluator labels. Define and test public
interface serialization to prevent accidental access. No navigation feedback
channel is added privately to A.

## 4. Baselines and fixed execution matrix

| Core scheduler rows | Count | Definition |
| --- | ---: | --- |
| Static, Age, Uncertainty, Periodic-1, Periodic-2, Periodic-5 | 6 | Historical timing equations, ported to shared Phase 1.5 controller |
| Fixed-rate, random-quota, quota-periodic, route-weighted, disruption-visible, conceptual query gate | 6 | Frozen Phase 1.4 gate definitions; random-quota has five schedule streams |
| Joint block route sensitivity B | 1 | Method-design block score; one development-calibrated rate threshold |
| Perfect-information decision comparator V_PI | 1 | Gate V_PI>c_s using common particle Q table |
| Sensor EVSI A | 1 | Primary; actual partial-sensor likelihood |
| Budget extension C | 1 | A plus declared nonzero shadow-price approximation |

There are 16 methods, 15 deterministic and five random-quota executions per cell:
20 executions in total. V_PI is a model-based decision-aware comparator inspired
by active measuring/QMDP, **not** a faithful ATM, ALONE or sensory-regret
reproduction. No published-performance claim can be made from that adaptation.
If research review requires a faithful external implementation, revise this
matrix before lock; do not add it selectively after results.

Legacy gates retain their original feature scales, thresholds and internal
legacy observation-price constant 1.5 where their formulas require it. Every
actual call is nevertheless charged the common Phase 1.5 c_s in the new ledger.
For example disruption-visible retains theta=.4, lambda=0 and its legacy .6
base threshold, rather than receiving .02 as an undocumented rescaling. These
are frozen timing controls under a new controller, not optimized Phase 1.5
competitors or exact historical trajectory reproductions. Publish this distinction
in every comparison. The parameter lock itself is never edited.

| Future assessment component | Arithmetic | Executions |
| --- | --- | ---: |
| Core, price .02 | 160 clusters x 2 schedules x 4 sensors x 3 caps x 20 | 76,800 |
| Cost sensitivity: A,C,V_PI only | 160 x 2 x 4 x caps4/8 x 3 methods x 2 extra prices | 15,360 |
| Four informative ablations of A | 160 x 2 x 4 x caps4/8 x 4 | 10,240 |
| Fixed matrix subtotal | | 102,400 |
| Exact one-call assay, at most two snapshots/cell | 160 x 2 x 4 x 2 x 9 branches, maximum | 23,040 |
| Total assessment maximum | | 125,440 |

Final held-out is not included in this execution authorization or count. A future
held-out manifest and approval must precede any access; it is not a reserve for
adding significance to a failed assessment.

### Informative ablations

Keep the real controller, real sensor, public history and actual sensing cost
unchanged; alter only the query-value computation:

1. **Goal relevance removed:** use a deterministic public phantom goal (farthest
   in-bounds cell by Manhattan distance from real goal, index tie break) for the
   gate's Q, while executing the real-goal controller.
2. **Joint dependence removed:** compute the gate's counterfactual belief using
   independent cells with the same occupancy marginals; retain the common joint
   filter/controller for executed actions.
3. **Occlusion prediction removed:** query gate assumes all footprint cells return;
   actual occlusion and real sensor remain unchanged.
4. **Best single-cell value:** replace full-observation EVSI with the maximum EVSI
   of one footprint cell's possible {missing,free,occupied} return. A granted
   query still returns the actual full sensor array at the same price.

Compare each with A, not Static by default. A is already C's zero-extension
control. Each ablation must change scores and requests on development fixtures
and calibration histories before lock. Do not drop an inactive row once locked;
report the negative result. Removing dependence can change many beliefs, so a
positive contrast does not uniquely diagnose one physical correlation mechanism.

### Exact observation-count timing assay

Same cap is not actual count matching. The mandatory assay forks identical public
histories and identical simulator states, with no cross-branch future information.
Take snapshots from the already prescribed quota-periodic cap8 core executions
at post-initialization t=0 and post-move t=16. Eligibility is determined before
forking: not at goal, remaining capacity >=1, and public Manhattan goal distance
>W=4. With at most one-cell movement per decision, no branch can reach the goal
before its four-decision query window ends. Never filter on future outcomes.

Every branch takes **exactly one** additional full observation during that window,
then none thereafter, and continues the shared controller to goal/T. Compare A,
V_PI, frozen route-weighted gate, fixed window midpoint (second decision), and
five uniform-random window times: four deterministic plus five random branches.
Value gates may choose an earlier time; if they have not requested by the last
decision, force that call and label it. Prefix calls, one additional call and
price are identical across branches, without post-goal padding. No method may
look up another policy's realized future call count. Record forced fractions.

This tests local timing conditional on quota-prefix eligibility, not the full
adaptive sensing policy in every state. Average random streams, snapshots and
dynamics within topology before uncertainty estimation. Require at least 80
eligible topology clusters and 20 per generator mechanism for inferential timing
claims; otherwise label it descriptive. Development A must choose at least 25%
of its assay calls before the forced deadline, or the timing assay is not a
credible test of its value gate and the design stops for review.

## 5. Development-only checks and locking

Proposed future development budget: fit 48 x 2 schedules x 4 sensors x two
predeclared public schedules =768 episodes; calibration 24 x 2 x 4 x 2=384;
selection core 24 x 2 x 4 x 3 caps x 20=11,520. Total 12,672, plus at most
96 enumerable analytic fixtures (not assessment environments). The two fitting/
calibration schedules are Periodic-1 and quota-periodic cap8. Replaying stored
public histories for numerical checks does not generate new environmental runs.

All of the following gates must pass **before** assessment opens:

- Analytic zero, positive, parity, scale and missingness checks in the method
  design pass against exact enumeration. The positive fixture must exceed price;
  no denominator or threshold can make all possible scores unreachable.
- J uses the smallest of 64/128/256 with two-SE halfwidth <=.01 in at least 90%
  of eligible calibration queries, checked with independent numerical streams.
  Preserve raw negative estimates, quantiles, bounds violations and Monte Carlo
  variability. Failed precision is not repaired by score clipping.
- Sensor-return probabilities beat a constant-return-frequency Brier baseline,
  with expected calibration error <=.10 in fixed ten probability bins having
  at least 100 samples. Occupancy Brier must be no worse than the historical
  fixed-rate public-history proxy. Report bin coverage and topology-clustered
  uncertainty; sparse bins are unverified, not silently omitted as successes.
  Truth may score development predictions in the evaluator but never fit or
  update agent parameters. Report distance, known/unknown and occlusion strata.
- On predeclared informative calibration opportunities, A makes noninitial
  requests on at least 5%, declines at least 90% of exactly uninformative fixture
  opportunities, and does not reproduce Periodic-1 on over 95% of informative
  calibration decision sequences. Preserve legitimate no-change null cases.
- Each ablation changes its gate score in >=10% and request in >=5% of the
  applicable calibration opportunities (all opportunities for rows1/2/4;
  occlusion-on opportunities for row3). Require at least 30 opportunities from
  six clusters for each applicability stratum, plus its analytic positive fixture.
  Failure stops review of the matrix; it does not justify assessment-time dropping.
- No zero-support filter failures; effective sample-size distributions and
  resampling counts are published. Runtime/memory gates in the method design
  pass on declared hardware and full-matrix projection fits the resource ceiling.
- Freeze B's request-rate match using calibration only. No navigation outcome
  selects its threshold, A's price, C's coefficient or primary method.

Definitions of an informative calibration opportunity and fixture membership
must be set in the final fixture manifest before executing these gates: use
enumerated decision-changing sensor outcomes under the fitted model, not realized
navigation successes. Publish opportunity denominators for each gate. Selection
development reports every candidate row; a scientifically unpromising design can
be stopped, but cannot be switched to the apparent winner without a new reviewed
development design. No finite threshold search optimizes assessment outcomes.

After passing, lock topology certificates/partitions, generator/dynamics rules,
model parameters, controller loss, method configurations, fixtures, J, costs,
random namespaces, job identities, analysis code, software/platform and full
source SHA-256 inventory. A reviewer approves a versioned final protocol and
signed/hash-committed manifests before assessment. Reject any resume with a
changed lock. Discovering a design defect after assessment requires reporting
that failure and a new phase with new data, not revision of this assessment.

## 6. Outcomes and analysis

Primary outcome: contact-free goal completion by T, with any dynamic contact
making an episode non-contact-free. Goal completion alone is secondary. Count
initial and subsequent calls separately and together. Report cost c_s*n,
requests/denials, dynamic contacts, blocked attempts, elapsed steps, path length,
cumulative and terminal known/unknown memory errors, and common-horizon memory
errors without conditioning on success. Preserve the historical error definitions
for last-write memory; add belief Brier/log scores separately rather than silently
change what 'memory error' means.

Also report observation times, remaining cap at each call, scores/SE/thresholds,
visibility prediction calibration, action-switch frequency, value prediction
versus model-realized loss reduction, filter support/ESS, scheduler runtime,
common planner/filter runtime, model samples, BFS/A* calls and peak RSS. Model
loss reduction is not true causal goal benefit; only paired navigation/assay
contrasts address that. Evaluator truth used for scoring must be separated from
the public trace consumed by the agent.

### Primary inference and task-awareness criterion

Compare A minus quota-periodic in the single primary condition. Report paired
contact-free rate difference and paired actual mean-call difference with 95%
intervals. The predeclared practical target is at least +5 percentage points.
A primary positive result requires the contact-free interval lower endpoint >0,
point difference >=.05, and the call-difference interval upper endpoint <=.25
calls. This is a joint success criterion; equal caps alone do not pass it.
Separately report the corresponding observation cost difference.

Only after that joint gate passes, test the exact one-call assay A minus fixed
midpoint contact-free contrast pooled over its four sensor conditions at price
.02, with lower 95% endpoint >0 required for a task-aware timing claim. This
fixed sequence limits confirmatory claims; do not select the most favorable
assay comparator. V_PI, route-weighted and random assay contrasts remain
secondary. If primary navigation improves but calls increase beyond tolerance,
report possible increased-sensing benefit, not established task-aware advantage.
If timing fails, retain the navigation result and explicitly limit interpretation.

### Clustering, multiplicity and power

The resampling unit is the complete topology/lineage audit component. Average
five random-quota streams within environment first, then the two dynamics
schedules within cluster. Use equal generator-mechanism weights. Globally
resample clusters with replacement 10,000 times, RNG seed 1505001, preserving
all methods, conditions, schedules and assay snapshots jointly. Redraw samples
missing a mechanism, with 100,000-attempt limit. Report percentile intervals,
paired discordant counts and leave-one-generator-out estimates. Never bootstrap
episode rows as independent. If audit merges reduce assessment below 80 clusters
or any mechanism below 20, inferential claims stop; report descriptive results.

The assay averages eligible snapshots within each topology, then uses the same
mechanism weighting and clustering over eligible clusters; report selection
rates and its conditional population. Secondary methods, costs, sensors and
ablations have descriptive paired intervals, not a collection of new confirmatory
tests. Publish all contrasts including exact zeros. Any broad multiple-testing
claim needs a new predeclared correction, not selective p-values.

The proposed 160 clusters are a resource proposal, **not demonstrated adequate
power**. For illustration, paired discordance .2 gives SE approximately
sqrt(.2/160)=.0354 and a 95% halfwidth near .069 before any schedule-averaging
benefit. Detecting .05 with 80% power under that approximation needs about
(1.96+.84)^2*.2/.05^2=628 clusters. Actual clustering may worsen this.
A development-only power/simulation audit must justify an approved target or
label the study estimation-focused before final lock. Increasing N requires
review before assessment, not a sample-size extension after seeing its interval.
Failure to resolve this is a stop condition for a confirmatory protocol.

## 7. Reproducibility, execution and cost ceilings

Future execution must use POSIX locks, exact job identities, atomic per-episode
checkpoints, immutable SHA-256 trace inventory, duplicate/missing detection and
independent metric reconstruction. Source/configuration hashes cover the common
model, sensor, generator, scheduler, analysis and runtime dependencies. No
assessment/held-out path is admitted by development entry points. Final held-out
needs a distinct access gate and cannot be opened by the assessment runner.

Store full public observations, actions, last-write state, decision scores,
loss tables, weights/ESS, bit-packed joint belief checkpoints, numerical draw
summaries and RNG counters outside Git, with compact metrics/manifests in Git.
Imaginary sensor returns may be deterministically reconstructed from model,
checkpoint and counters only after a byte/hash replay test proves this exact
compression scheme; otherwise retain them too. Keep evaluator truth in a separate
audit stream unavailable to agents. Record atomic checkpoint/recovery events;
resume cannot count an existing valid job twice. Independently reconstruct all
metrics and verify every trace checksum before publication.

At the maximum 125,440 assessment executions and 80 decisions, the upper bound
is 10,035,200 decision events, excluding development. Hypothetical total means
of 10/50/100 ms per decision imply about 27.9/139.4/278.8 CPU-hours, before
verification and I/O. These are scenarios, not benchmarks. With complete joint
belief traces, plan approximately 200–500 GB of compressed storage provisionally;
measure development traces and revise this estimate before lock. Do not assert
that Phase 1.4's small traces predict these costs.

Proposed resource ceiling is 200 CPU-hours plus separately budgeted verification,
512 MiB peak RSS per worker and 500 GB trace storage. Development projections
must fit these limits; otherwise stop for a scope/resource amendment before
assessment. A hard one-second per-decision deadline is a computational failure,
not permission to substitute a cheap successful action. Record such failures
as failures in intent-to-evaluate results; if >1% of decisions exceed deadline,
abort the matrix and publish its incomplete status. Do not lower J or omit rows
mid-assessment. Hash/support failures, changed parameters, duplicate identities
or broken access boundaries stop immediately pending research review.

No interim outcome peeking, early significance stopping, repeated primary tests,
assessment-driven calibration, cost selection, cap selection or favorable-family
exclusion is allowed. An integrity repair may restore exact execution of an
unchanged job; a scientific change requires a new version and new independent
assessment. Publish attempted/completed/missing counts and every failure reason.

## 8. Review gates and future deliverables

Before implementation review: resolve the model prior/proposals, loss/cost scale,
shared-controller decision, exact dynamics distributions, comparator fidelity,
statistical power and resources. Before finalized preregistration: perform and
publish the actual artifact-only topology audit under separate authorization.
Before assessment: pass development checks, source/parameter lock, reviewed
power plan and reproducibility rehearsal on development only.

Future reports must include complete paired metrics, activation diagnostics,
cost/performance plots, topology/lineage audit, all controls and ablations,
runtime/storage, source provenance, trace inventory, independent verification,
limitations and failed criteria. Negative results are valid deliverables. No
implementation, new parameters, held-out evaluation or MuJoCo work follows
automatically from approval of these documents.

Current deliverable is this reviewable design, with actual topology independence,
power and computational feasibility explicitly unresolved. Stop for research
review before implementation.
