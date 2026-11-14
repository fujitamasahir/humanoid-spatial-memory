# C v2.0c FIT72 Intervention Selection Protocol

**Frozen before any FIT data access.** This protocol is conditional: it may be
used only if the C v2.0c synthetic numeric gate is `PASS` and the independent
conformance review is exactly `ACCEPTED_FOR_FIT`. A failed or invalid gate
means no FIT access under this protocol.

## Scope and fixed policy matrix

This is a descriptive development evaluation, not independent validation.
The fixed comparison is Periodic, Age, C0, C-K (the already-frozen K=5
candidate-count control), and C-Topology3-corrected. No weights, thresholds,
sensing rules, or hyperparameters may be tuned from FIT outcomes. The existing saved FIT identities, schedules,
observation policies, seed 42, horizon 80, 0.75 m/cell assumption, observation
cap 20 including initialization, 61-ray memory sensor, independent emergency
safety sensor, selected-action MuJoCo shield, forward-first planner, and
forward-first collision behavior are fixed.

## Integrity and parity gates

Before reading episode data, verify repository/source fingerprints, all
Phase 1.5 preservation manifests, the original FIT store identities and
receipt hashes, and the frozen baseline implementation. Reads must be
read-only. Do not call a protected generator or regenerate/replace any store.
Run untreated replay parity on the exact saved identities before evaluating
interventions. Any integrity failure or parity mismatch stops the evaluation
without repair or substitution.

## Fixed-state diagnostic and intervention selection

At each saved decision state, replay the frozen controller and record all
eligible single-cell candidate values from the public memory state. Rank
interventions before looking at outcomes by (1) greatest positive exhaustive
single-cell D minus the common K=3 cost, (2) greatest positive corrected
Topology3 D minus that same cost, then (3) fixed episode identity, step, and
cell-coordinate order. Retain only a candidate where C0 and corrected
Topology3 make different scan decisions, the selected cell is visible under
the frozen 61-ray memory-only footprint, and the public probability satisfies
the frozen .05 < q < .95 eligibility rule. Do not use future pedestrian
trajectories, hidden occupancy, simulator state, evaluator contact labels,
unselected shield queries, or episode outcome labels to choose interventions.

The fixed-state causal diagnostic uses paired scan/no-scan swaps from the same
saved pre-decision state, with every other state and action rule held fixed.
It reports outcomes without tuning and is not used to redefine the matrix.
The two-case smoke uses the predeclared regression and improvement cases from
the 61-ray safety-sensor comparison. FIT72 runs once, only after both gates,
integrity checks, untreated replay parity, fixed-state diagnostics, and both
smoke cases pass. No retries with altered settings are permitted.

## Required paired outcomes

Report goal completion; rescued/harmed pairs; unwanted contacts; paid memory
observations and rays; emergency safety observations and rays; total sensing
workload; H80-censored navigation steps; common-success movement steps and
distance; blocked actions; emergency interventions; memory errors; candidate
value recall; graph/scheduler work; and episode wall time. Preserve all
episode-level outcomes and distinguish descriptive contrasts from causal
effects. FIT72 must not be used to tune C v2.0c. Independent cohort work stays
unexecuted pending explicit owner approval.

## Stop rule

Do not access FIT if either synthetic gate fails, any integrity manifest is
invalid, or untreated replay parity fails. Preserve the failure record. Any
change to the matrix or selection rule requires a new versioned protocol
committed before FIT access.
