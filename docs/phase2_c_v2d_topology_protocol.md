# C v2.0d topology mechanism and computational screen

**Version:** 1.0, frozen before the 80-case policy screen.  The frozen
implementation preserves C v2.0c's exact topology priority, lexicographic
ranking key, EVI equations, visibility, probability thresholds, sensing costs,
scarcity cost, and observation budget.  The sole online ranking change is
bounded deterministic top-three selection instead of a complete sort.

## Population and provenance

The formal synthetic population is 80 seeded public-grid cases in eight
predeclared families, ten cases per family.  Seed namespace: `2026111600`.
Families: sparse unique separators; serial separators; irrelevant
articulations; loop-rich maps; occupied connectivity-restoring cells;
occupied distance-only shortcuts; no-benefit topology controls; and dense
competing ties.  Templates are augmented deterministically across dimensions
from 17x17 through 49x49, terminal placements, probabilities, and sensor
footprints. The target annotations are checked independently with the
brute-force topology reference before any policy arm runs. At least 60 fixtures
must have M>5 and at least 20 must have M>20. The fixtures are public synthetic
maps; no admitted or reserved navigation cohort is used.

The former 48 v2.0c cases are regression material only. They are not counted
as new evidence. Their result directory and gate remain unchanged.

## Correctness and selection equivalence

Before formal execution, the frozen test command runs the independent
structural reference suite, 729 ternary 2x3 maps over valid ordered terminals
and both unknown modes, at least 1,000 deterministic random maps, v2.0d
full-sort/top-K equality, v2.0c decision parity, all 48 v2.0c cases as
regression, fixture annotation checks, and isolated reviewer fault-injection
tests. The required result is zero unexplained structural or decision
mismatches. The top-K implementation keeps exactly the prefix/order of the
v2.0c key `(class, -severity, -distance_gain, -q*(1-q), y, x)`.

## Arms and outcomes

The fixed arms are C0 (original three-candidate audit semantics), C-K (K=5
uncertainty ranking control), C-Route3, and C-Topology3-d (v2.0c ranking with
bounded top-three extraction). All arms share the same public fixture, start,
goal, heading, unknown-cell convention, and observation footprint. An
independent exhaustive single-cell EVI reference supplies useful-candidate
and maximum-D denominators. The frozen common scan cost is
`0.5 + 0.01*7 + 0.5/20 = 0.595`; each arm's actual cost uses its actual
counterfactual A* call count. Empty denominators are represented as null and
excluded from macro means; micro denominators are explicit totals.

Report per-family and overall macro/micro useful recall, macro/micro maximum-D
recall, best-D regret, common-cost scan agreement, actual authorization,
false-positive and false-negative counts, candidate counts, plan calls,
stage counters, scheduler time, graph-analysis time, and runtime samples.

## Frozen numerical gates

All conditions below are conjunctive. A valid failure is `REJECTED`; malformed,
missing, or inconsistent evidence is `INVALID`. No threshold may be revised
after outcome inspection.

* C-Topology3-d macro useful recall gain over C0 is at least 0.10.
* C-Topology3-d micro useful recall does not decrease from C0.
* C-Topology3-d macro maximum-D recall does not decrease from C0.
* Common-cost scan-decision agreement improves by at least 0.05 (fixture
  proportion) over C0.
* C-Topology3-d's actual false-positive authorizations versus the exhaustive
  common-cost decision do not exceed C0's count.
* All ten designated no-benefit controls have no actual C-Topology3-d scan
  authorization.
* C-Topology3-d uses at most seven A* calls; C-K uses at most eleven.
* All stage-specific theoretical operation bounds and top-K comparison bounds
  hold; no unlike operation categories are collapsed into a scalar score.
* The reference-scale 17x17 graph-analysis p95 is at most 5 ms under 10 warm-up
  and 100 measured calls per 17x17 case. Larger maps are characterized without
  applying this latency threshold.

There are no retries, threshold tuning, fixture replacement, or reruns after
the formal policy outcomes are observed. Any implementation or protocol change
requires a new version and a new prospective binding.

## Review and stop rule

After the one formal run, an independently invoked reviewer recomputes row
invariants, denominator semantics, aggregates, numeric gates, operation
bounds, A* limits, runtime p95, source fingerprints, artifact hashes, and
data-access restrictions. Fault-injection tests verify isolated categories.
FIT is authorized only by the exact status `ACCEPTED_FOR_FIT` and numeric
`PASS`. `VALID_REJECTED_STOP_BEFORE_FIT` and `INVALID_STOP_BEFORE_FIT` both
block all FIT reads. No result in this protocol authorizes independent
navigation cohorts.

The FIT intervention matrix and integrity checks, if authorized, are frozen in
[`phase2_c_v2d_fit_intervention_protocol.md`](phase2_c_v2d_fit_intervention_protocol.md).

## Computational accounting

Operation definitions, stage bounds, full-pipeline complexity, A* bounds, and
runtime protocol are specified in
[`c_v2d_computational_complexity.md`](c_v2d_computational_complexity.md).
Stage limits are derived from source loops and graph degree, separately for
grid, graph, terminal, candidate, top-K, route, and counterfactual stages.

## Frozen source binding

The prospective SHA-256 binding and canonical fixture-population digest are
stored in `results/phase2_mujoco/c_v2d_topology_v1/protocol_binding.json`.
The runner verifies that binding before policy execution. It binds the
protocol, intervention protocol, complexity derivation, generator, annotation
validator, runner, reviewer, implementation, independent reference, EVI,
candidate controls, navigation planner, and relevant tests. The binding must
be committed before the formal runner is invoked.
