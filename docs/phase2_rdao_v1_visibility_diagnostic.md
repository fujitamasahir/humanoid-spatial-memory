# RDAO v1 visibility diagnosis — Step 1

Status: **preliminary logged-observation finding; shadow replay implementation added but not yet executed**.

This is development-only diagnostic work on the 36 admitted fit worlds and the
frozen RDAO v1 traces. It is not new held-out or confirmatory evidence.
The original 72-episode evaluations and all Phase 1.5 checkpoints remain read-only.

## Research question

Does the remembered-map visibility heuristic reject spatial-memory
observations even when the actual pinned 61-ray, 120-degree MuJoCo sensor
would reveal previously unknown cells, especially near the planned route?

Separate two questions:

1. **Predictor calibration:** Are cells physically measured by the real sensor
   ever assigned zero predicted visibility by the heuristic?
2. **Decision-level opportunity:** At steps when RDAO *did not* request an
   observation, would a diagnostic-only sensor call reveal unknown route-near
   cells that the heuristic ranked invisible?

The first can be checked from already saved authorized observations. The
second requires a shadow replay; neither by itself establishes a causal
improvement in navigation success.

## Existing-trace audit, three development cases

Derived from the saved case_A/B/C RDAO trace JSONs without rerunning navigation:

| Case | Authorized noninitial observations | Newly observed unknown cells | New cells with center angle outside RDAO's FOV gate | Those within Manhattan distance 1 of the first six nominal-route actions |
|---|---:|---:|---:|---:|
| A | 13 | 233 | 12 | 5 |
| B | 10 | 159 | 12 | 3 |
| C | 4 | 87 | 6 | 2 |
| **Total** | **27** | **479** | **30** | **10** |

This is a **cell-center-versus-ray-rasterization mismatch**: the current
predicted_cell_visibility function immediately returns zero if the candidate
cell *center* lies outside +/-60 degrees; a ray passing through *any part* of
the 0.75 m cell can nevertheless register that cell. Thus there are observed
unknown cells for which the center-angle check alone incorrectly predicts
zero visibility. This also occurs for 10 newly observed cells within one
Manhattan cell of a six-action nominal-route lookahead.

The three-case decision-reason counts were:

- 79/154 decisions: no visible uncertain route-relevant region;
- 48/154 decisions: highest candidate score below the budget-adjusted threshold;
- 27/154 decisions: observation granted.

The counts are descriptive. In particular, **none of the 30 cell-center
mismatches proves that a denied observation caused a failed episode.**

## Next: passive rejected-decision shadow replay

A diagnostic-only implementation is in
[scripts/diagnose_rdao_visibility_replay.py](../scripts/diagnose_rdao_visibility_replay.py).

It reconstructs only the saved trajectory and world clock, using the same
pinned 61-ray memory sensor on the already admitted fit world. It does not
run or modify RDAO, grant additional observations, change actions, use the
independent emergency safety sensor as a policy input, or modify previous
result files. At each rejected decision the replay asks what the sensor
would have measured, then compares this measurement with the *pre-decision*
memory reconstructed solely from the original authorized observations.

**Mandatory validity gate:** At every originally granted noninitial
observation, the replayed raw grid, pre-observation memory and
post-observation memory must *exactly match* the saved trace. Abort on any
mismatch rather than interpreting unvalidated shadow measurements.

Commands (from the existing local environment with pinned G1 assets):

~~~sh
.venv/bin/python scripts/diagnose_rdao_visibility_replay.py --scope cases
.venv/bin/python scripts/diagnose_rdao_visibility_replay.py --scope primary
~~~

The first uses the three saved detailed cases; the second uses the 72
compressed frozen RDAO primary traces. Each command refuses to overwrite
an existing result directory. It writes rejected_decisions.csv and
summary.json under a separate visibility-probe directory.

## Interpretation protocol

- Inspect raw observation fidelity before any visibility result.
- Tabulate denied steps by no-candidate versus below-threshold reasons.
- Count truly measured *new unknown* cells, modeled zero-visibility cells,
  and cells within one Manhattan cell of the next six nominal-route actions.
- Stratify by world, schedule, success/failure and rejection reason.
- Cases where the shadow sensor reveals cells are **missed sensing
  opportunities**, not proof that sensing would have changed the plan or
  the episode outcome.
- Next, on selected pre-divergence steps only, run paired controlled
  observation interventions with identical world and seed, report
  actual movement and outcome changes, and do not tune on held-out worlds.
- Do not loosen the visibility gate or change the RDAO algorithm until
  predictor mismatch, opportunity counts and replay integrity are reviewed.

The script was prepared through the GitHub connector. **Execution and
environment-specific MuJoCo fidelity have not been verified in this chat.**
