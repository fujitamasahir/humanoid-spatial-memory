# C v2.0b Topology-aware Candidate Selection — Mechanism Screen

**Status:** synthetic run archived; FIT and causal evaluation blocked after
post-run protocol-conformance review. Do not interpret the numeric gate as a
validated pass.

## Hypothesis and implementation

`docs/phase2_c_v2b_topology_protocol.md` froze a public four-neighbor graph,
Tarjan articulation/bridge/biconnected analysis, a bounded occupied-cell
shortcut feature, and a lexicographic C-Topology3 ranking before formal
synthetic screening. The implementation is isolated in
`src/spatial_memory/topology_evi.py`; original C remains the default. The
classifier uses only the ternary public grid, current/start cell, goal,
probability map, visible footprint and unknown-cell mode.

## Formal synthetic output

The frozen runner executed 11 fixture/terminal-pair conditions and 44
policy-fixture runs. Its calculated metrics met the numeric gate: C-Topology3
useful-candidate recall 0.95 versus C0 0.50; maximum-D candidate recall 0.95
versus 0.50; common-cost scan-decision agreement improved on two fixtures;
no actual scan was authorized in the no-benefit case; all A* caps and graph
work bounds held; maximum per-fixture graph-analysis p95 was 0.777 ms across
100 repetitions. These are outputs of the frozen run, not navigation outcomes.

The formal result is **not accepted as a gate pass** after checking whether
the implementation matched its frozen structural definitions:

1. In `occupied_cell_clearing_shortcut`, start and goal were already in the
   same public connected component through the detour. The classifier failed
   to require distinct terminal components before labeling the occupied cell
   an `occupied_connectivity_shortcut`; the expected label was a distance
   shortcut. The cell was the only eligible candidate in that fixture, so its
   shortlist membership was unchanged, but the frozen feature implementation
   was not faithfully realized.
2. In `multiple_correlated_uncertain_cells`, the selected annotated cell was
   actually in a cyclic region with an alternate public route, not a unique
   start-goal separator as specified. This is a fixture-construction/label
   defect, and means topology identification accuracy is not valid for that
   case.
3. The fixture named `unique_start_goal_articulation` contains three
   consecutive start-goal-separating vertices in the narrow one-cell throat,
   rather than one unique articulation vertex. The annotated uncertain cell
   is a separator, but the fixture does not represent the frozen unique-point
   mechanism. The parallel `critical_cell_outside_C0_top3` fixture repeats
   that throat geometry.

The raw frozen run is retained byte-for-byte as
`results/phase2_mujoco/c_v2b_topology_v1/synthetic_mechanism_results.json`.
`gate_review.json` records why the nominal `PASS` is superseded by
`INVALID_STOP_BEFORE_FIT`. The protocol, fixtures, ranking, and thresholds
were not changed after observing the formal run, and the run was not repeated.

## Decision and work not performed

No fixed-state FIT replay, scan-swap intervention, FIT72 baseline reproduction,
or FIT72 comparison was performed. A read-only scan of 72 historical Age
episode wall-time fields was used only to estimate the proposed pilot runtime;
no trajectories or FIT outcome fields were analyzed for this task. The FIT
integrity preflight was not run and no FIT store was modified. There are no
causal or navigation claims for C-Topology3.

Focused tests passed before the formal fixture run: 41 tests across
`test_topology_evi.py`, `test_candidate_coverage.py`, `test_persistence_evi.py`,
and `test_persistence_evi_evaluation.py`. These establish code invariants, not
the correctness of the disputed formal labels. After adding the fail-closed
FIT gate-review guard and its tests, the combined focused suite passed 45 tests;
Python compilation and `git diff --check` also passed. The FIT72 runner was also
invoked with the nominal numeric-pass result; it refused at the gate review
before store integrity preflight or environment loading.

## Required next research step

Do not patch this implementation and rerun the same frozen protocol. A future
development iteration must have a new versioned protocol and result directory,
correct the occupied-cell component test, replace or relabel the correlated
fixture before freeze, add an automated annotation-consistency check, and
repeat unit/integration checks before a new formal run. Only a clean new gate
can authorize predefined causal replays and a single descriptive FIT72 screen.

The independent 24-lineage mechanism-pilot proposal is in
`docs/independent_cohort_proposal.md`; it remains a proposal, requires explicit
owner approval, and cannot substitute for an independent sealed evaluation.
