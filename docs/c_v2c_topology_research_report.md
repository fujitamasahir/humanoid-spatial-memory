# C v2.0c Corrected Topology Selection — Research Report

## Status

**Rejected at the frozen synthetic mechanism gate. Stop before FIT.** The
corrected implementation passed the independent structural correctness suite
and all 48 pre-policy fixture annotations, and its measured recall/scan
metrics were promising. However, the frozen `20*(V+E)` graph-work limit was
exceeded in 29/48 formal cases. The result must not be used to justify causal
replay or FIT72. No Phase 1.5 generation, FIT store, admitted world, or
independent cohort was accessed.

The original invalid C v2.0b evidence remains unchanged. C v2.0c v1's
pre-screen import failure is preserved separately; v2 was frozen in commit
`d2c92e5` before candidate outcomes. The formal result was produced only from
the frozen v2 source. Neither the fixtures nor limits were changed after
results.

## Correctness and conformance

The independent reference uses a separately built four-neighbor graph and
brute-force BFS after each vertex/edge removal and nontraversable-cell
restoration. The test suite checked all 729 ternary 2x3 maps over both unknown
modes and all valid ordered terminal pairs, plus 1,000 seeded 4x5 maps in both
modes. It reported zero structural mismatches. The 2,500-cell corridor test
confirmed iterative DFS stack safety. The annotation validator independently
accepted all 48 fixtures (six per family) before policy-arm execution.

The focused suite passed **55 tests**. The frozen screen's own correctness
precheck and the separate review rerun also passed. The separate review status
is `INVALID_STOP_BEFORE_FIT`, consistent with the failed numeric gate. Its
`aggregate_denominators_and_values` boolean is false only because the reviewer
currently shares one error list with earlier work-bound failures; it emitted
no aggregate-mismatch detail. A read-only independent recomputation matched
the saved aggregate values and denominators. This reviewer bookkeeping defect
is recorded and must be corrected only in a future versioned protocol.

## Frozen synthetic results

The formal set contained 48 public-grid conditions across eight balanced
families. Twenty-four had at least one useful candidate under the common
K=3 cost; the remaining 24 had empty useful sets and are excluded from recall
denominators. All arms used the same frozen V/D, probability, visibility, and
cost equations. C-Topology3-corrected remained capped at seven A* calls.

| Arm | Macro useful recall | Micro useful recall | Macro max-D recall | Micro max-D recall | Common scan agreement | Authorized scans | FP / FN | Mean scheduler time |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| C0 | 0.500 | 0.586 | 0.556 | 0.625 | 36/48 (0.750) | 12 | 0 / 12 | 0.908 ms |
| C-K | 1.000 | 1.000 | 1.000 | 1.000 | 48/48 (1.000) | 24 | 0 / 0 | 0.895 ms |
| C-Route3 | 0.750 | 0.793 | 0.778 | 0.813 | 42/48 (0.875) | 18 | 0 / 6 | 0.933 ms |
| C-Topology3-corrected | 1.000 | 1.000 | 1.000 | 1.000 | 48/48 (1.000) | 24 | 0 / 0 | 1.040 ms |

Topology3 improved macro useful recall by 0.50 and scan agreement by 0.25
against C0. It had zero mean selected-best-D regret and no authorization in
the six designated no-benefit cases. The aggregate graph-analysis p95 was
0.276 ms, below the frozen 5 ms limit. Every arm respected its A* ceiling.
These passing results do not override the failed work bound.

The work counter includes grid-cell scans and candidate-ranking operations.
The fixed `20*(V+E)` denominator counts traversable graph vertices and edges,
not all grid cells. On the deliberately sparse 17x17 maps, that bound was
therefore exceeded even though measured graph-analysis runtime was low. There
were 29 failures, with work/bound ratios from 1.02 to 1.27; e.g. a serial
separator case recorded 739/580 units and an irrelevant-articulation case
871/780. Because the criterion was frozen and conjunctive, it is a genuine
gate rejection under this protocol. Do not change the bound after the result.

## Gate decisions and next step

- Numeric mechanism gate: **REJECTED** (`graph_work_bound_respected=false`).
- Separate conformance review: **INVALID_STOP_BEFORE_FIT**.
- FIT fixed-state causal diagnostics: **not run**.
- Smoke episodes and FIT72: **not run**.
- Independent 80/200-lineage cohorts: **unexecuted; owner approval remains required**.

The review also exposed a bookkeeping defect: its aggregate-check boolean
inherits unrelated prior row errors. Raw result and review files remain
unchanged; the recomputation described above is a diagnostic note, not an
acceptance override. Any further development must use a new protocol/result
version, predefine a graph-work accounting rule that covers grid scans and
candidate ranking, repair the independent reviewer's error isolation, and
freeze both before rerunning a formal screen. Do not access FIT until both
gates pass under that new version.

## Artifacts and provenance

- Frozen method: `docs/phase2_c_v2c_topology_protocol_v2.md`
- Frozen FIT intervention rules (conditional; never activated):
  `docs/phase2_c_v2c_fit_intervention_protocol.md`
- Raw 48-case result: `results/phase2_mujoco/c_v2c_topology_v2/synthetic_mechanism_results.json`
- Separate review: `results/phase2_mujoco/c_v2c_topology_v2/gate_review.json`
- Artifact manifest: `results/phase2_mujoco/c_v2c_topology_v2/artifact_manifest.json`
- Preserved v1 setup failure: `results/phase2_mujoco/c_v2c_topology_v1/setup_failure.json`
- Pre-screen freeze commit: `368583d`; v2 freeze commit: `d2c92e5`.

The raw result contains source SHA-256 fingerprints, interpreter/platform
details, full per-fixture arm outputs, graph operation counts, timing samples,
and correctness/annotation preflight records. The artifact manifest records
the byte sizes and SHA-256 of the raw result and review.
