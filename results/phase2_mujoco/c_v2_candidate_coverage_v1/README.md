# C v2.0 candidate coverage investigation

This directory records the bounded candidate-selection hypothesis screen. The current selection hypothesis failed its pre-FIT72 synthetic gate, so no C-K/C-Route3/C-RouteK navigation rollout or full FIT72 candidate evaluation was executed. The runner enforces this gate before loading FIT72.

- `candidate_selection_audit.json` and the copied candidate audit CSVs quantify excluded nominal-route cells' point-plan changes, V/D, threshold crossings, and exact replay parity. These are diagnostic public-grid A* calculations, not selected-action shield queries or causal real-sensor effects.
- `synthetic_fixture_frozen_v2/` through `v6/` retain prior runs; `synthetic_fixture_frozen_v7/` is authoritative. It has distinct critical geometries, direct C0 shortlist membership, per-call timing, and C0/C-K parity; all preserve the same seven-fixture negative gate. `mechanism_gate.json` is authoritative. Two earlier fixture-construction trials are retained and explicitly excluded from the formal gate.
- `fig_critical_fixture_shortlists.png` visualizes the unique-bottleneck fixture.
- `fig_candidate_selection_audit.png` separates candidate-instance metrics from decision-step counts. Historical C0 outcome, EVI, and sensing figures remain in `../persistence_evi_failure_analysis_v1/`; they are not results for the new arms.
- `../persistence_evi_failure_analysis_v1/` contains the original frozen FIT72 traces and prior causal sensor interventions. Its episode 63 B+C mismatch remains excluded from causal contrasts.

No protected world was generated or modified. See [`phase2_c_v2_candidate_coverage_protocol.md`](../../../docs/phase2_c_v2_candidate_coverage_protocol.md), [`c_v2_candidate_coverage_research_report.md`](../../../docs/c_v2_candidate_coverage_research_report.md), and [`independent_cohort_proposal.md`](../../../docs/independent_cohort_proposal.md).
