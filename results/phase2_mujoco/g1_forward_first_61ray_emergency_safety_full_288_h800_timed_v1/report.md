# 800-step matched Phase 2 evaluation

- Episodes: **288**; goals: **286**; contact-free goals: **286**.
- Unwanted-contact episodes: **0**.
- Compared with the 80-step matrix: **61** additional goals by step 800.
- Still unreached at 800: **2** episode(s).
- Exact 80-step prefix match: **288/288**.
- Exact prior 400-step cohort prefix match: **63/63**.
- The 400-step run covered only its saved failure cohort; the remaining episodes have no prior 400-step trace for direct comparison.
- Added timers measure the observation decision, `plan_g1_forward_facing` A* body, and `Memory.update` separately. Per-call nanoseconds are in `phase_timings.jsonl.gz`.
- Existing sensor, selected-action collision-check, and episode wall-time measurements are retained in `episodes.csv` and summarized in `summary.json`.
- No environment, source trace, experiment condition, controller, policy, or protected Phase 1.5 file was changed.
