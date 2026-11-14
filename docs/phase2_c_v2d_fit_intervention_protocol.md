# C v2.0d FIT72 descriptive intervention protocol

**Conditional and frozen before any FIT-store access.** Execute only if the
v2.0d formal synthetic screen is `PASS` and the independent v2.0d reviewer
returns exactly `ACCEPTED_FOR_FIT`. Otherwise FIT data must remain unopened.
This is a descriptive development screen, not independent validation.

## Fixed comparison

Compare Periodic, Age, original C0, C-K (K=5), and C-Topology3-d. The only
algorithm change relative to C-Topology3-c is deterministic bounded top-three
selection; all v2.0c decisions must remain exactly equivalent. No tuning is
permitted. Use the existing 72 FIT identities, schedules, observation policies,
seed 42, horizon 80, 0.75 m/cell assumption, 20 paid memory observations
including initialization, actual 61-ray memory sensor, independent emergency
safety sensor, selected-action MuJoCo shield, and frozen G1 forward-first
planner. Do not regenerate or mutate any stores.

## Preflight and integrity

Verify the working tree and branch, all three original FIT store locations,
preservation manifests, file/receipt SHA-256 values, historical evidence, and
the committed v2.0c and Phase 1.5 protected prefix. All reads are read-only.
Reproduce the original Periodic/Age baselines exactly and compare saved traces.
Run the predeclared two-case smoke test. Any unavailable store, integrity
mismatch, baseline mismatch, or smoke mismatch stops before the full matrix.
Do not repair, substitute, or regenerate missing data.

## Fixed-state diagnosis and evaluation

Use only the saved public memory state and permitted 61-ray observations to
construct candidate values. Select diagnostic state/cell pairs by the frozen
v2.0c intervention rule: largest positive exhaustive single-cell D minus the
common K=3 cost, then largest positive C-Topology3-d D minus that cost, then
episode identity, step, and coordinate ordering. Require a disagreement in
scan decisions and frozen visibility/probability eligibility. Ground truth
may be used only for retrospective outcomes. Do not access future pedestrian
paths, hidden occupancy for controller decisions, unselected shield queries,
or reserved populations.

Run the matched 72-episode matrix once. Preserve episode records and traces.
Report goals, unwanted contacts, paired rescue/harm, paid memory scans/rays,
emergency scans/rays, combined sensing work, censored steps, common-success
steps/distance, blocked actions, emergency interventions, memory errors,
candidate recall/authorization, graph counters, A* calls, scheduler time, and
episode wall time. Short failed runs are not treated as efficient outcomes.

The 24-lineage pilot and 80/200-lineage cohorts remain unapproved and must not
be generated, admitted, opened, or run. FIT72 remains descriptive and does not
authorize any cohort.
