# Phase 2 safety outcome diagnostics

This directory compares the saved no-sensor and optimized 61-ray outcomes for M80030007/Periodic and R80000001/Static. The 288-episode results are not modified.

- `case_A_trace_comparison.csv`, `case_B_trace_comparison.csv`: aligned saved poses, headings, selected/executed actions, observations, pedestrian states, interventions, and contacts. Ground-truth pedestrian cells are explicitly evaluator-only and used retrospectively.
- `case_A_analysis.md`, `case_B_analysis.md`: first divergence, causal interpretation, and controlled action-override ablations.
- `M80030007_periodic_before_after_safety_sensor.gif`, `R80000001_static_before_after_safety_sensor.gif`: synchronized 1600×450 side-by-side MuJoCo replays. Panels start together; the shorter panel freezes at its final frame; the GIF loops after the longer run.
- `case_A_first_divergence_closeup.gif`, `case_B_first_divergence_closeup.gif`: short synchronized windows around the first meaningful divergence.
- `controlled_replays.json`: small, diagnostic override ablations. They are not part of the 288-episode evaluation.
- `observation_grid_diagnostics.json`: raw ternary ray-grid hashes and cell counts from matched deterministic replays; each replay was checked against its saved episode signature.
- `render_validation.json`, `metadata.json`: GIF dimensions, duration, frame counts, source hashes, and rendering settings.

The G1 gait and camera are display-only. Pedestrian locations shown in frames are saved evaluator diagnostics, never online controller inputs.
