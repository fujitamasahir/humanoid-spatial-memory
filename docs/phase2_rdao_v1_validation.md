# Phase 2 RDAO v1 validation

Implementation and saved evaluation: [`results/phase2_mujoco/rdao_v1_phase2_evaluation/validation_report.md`](../results/phase2_mujoco/rdao_v1_phase2_evaluation/validation_report.md).

RDAO v1 is a deterministic, route-decision-aware observation scheduler. It combines remembered-map visibility, map staleness, counterfactual G1 route/action relevance, and timing/budget weights. It is separate from the existing Static, Periodic, Age, and Uncertainty policies. The controller uses only robot-accessible memory, pose, goal/configuration, and blocked-action feedback; Emergency Safety and selected-action collision checks remain independent.

The evaluation uses the existing 36 admitted worlds, two schedules, seed 42, 0.75 m/cell, unchanged sensors, and an 80-step horizon. No environment generation or held-out suite access occurred. Historic baseline results are read-only; the new RDAO, ablation, and descriptive matched-dose results are in the new result directory. Phase 1.5 preservation verification was performed before and after evaluation.

RDAO reached 57/72 goals (zero unwanted contacts) using a mean 9.11 memory observations. Periodic and Age each reached 66/72; Uncertainty reached 56/72; Static reached 37/72. Thus v1 did not outperform Periodic/Age on this matched development set. RDAO scheduler computation averaged 316 ms per episode (p95 1065 ms), a substantial runtime cost. The post-hoc matched periodic control reached 58/72 with mean 8.56 observations; it is descriptive and not an online policy. Ablation results are reported in the result report. These are one-seed development findings, not confirmatory evidence.

The no-route-relevance ablation reached 66/72 but requested 14.79 observations on average; no-visibility also reached 66/72 at 12.33 observations. No-timing reached 57/72 with 8.96 observations. These ablations do not isolate a clear benefit from the full scoring formulation; the matched periodic control was close in both dose and success (58/72). The current results therefore do not establish that RDAO's route/timing model adds value over simpler scheduling.

The diagnostic cases reproduce saved baseline traces before RDAO execution. Divergence timelines and case analyses distinguish observation timing from first movement/action divergence; they are observational and do not claim causal proof.

## Recommendation for Version 2

Do not promote v1 as the default observation policy based on this development set. A prospective v2 should first reduce counterfactual-planning cost and pre-register an independent evaluation; it should compare against dose-matched periodic scheduling and retain the same safety/memory separation. The three diagnostic cases used for v1 design cannot serve as independent confirmation.

Focused regression command:

```sh
.venv/bin/python -m pytest tests/test_rdao.py tests/test_phase1_4a_policies.py tests/test_phase1_4a_evaluation.py tests/test_phase2_final_61ray_eval.py -q
```

The focused command passed **86 tests** (14 dependency deprecation warnings). A full repository run completed with **519 passed and 26 failed**. The failures are in legacy Phase 1.5 native-backend/resource tests: this checkout lacks the pinned native build file at its recorded path, and several tests require Linux enforcement semantics; frozen-source commitment checks also flag the already-existing `evaluation.py` state. No RDAO test failed. These failures are recorded rather than masked or treated as evidence about RDAO.

Full experiment reproduction commands and artifact hashes are recorded in the result directory's validation report and experiment manifest.
