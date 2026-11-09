# Horizon-800 residual episode replays

Three GIFs rendered from the committed horizon-800 traces. No evaluator or environment generation was run. Recorded G1 poses, headings, actions, and timing are replayed as saved; the visual gait is kinematic only. Saved evaluator-only proxy coordinates are used only to place proxies in the retrospective scene.

- `case_A/portfolio_export/portfolio_demo.gif`: BP 80010004, Static, schedule 0.
- `case_B/portfolio_export/portfolio_demo.gif`: BP 80010004, Static, schedule 1.
- `case_C/portfolio_export/portfolio_demo.gif`: M 80030008, Static, schedule 1; reaches the goal at step 479.

In both BP cases, G1 first enters `(1,23)` at step 336 / 316, then spends 124 steps revisiting cells, turning 55 times, and attempting 69 forward moves (41 translations succeed; 28 are blocked). No exact repeated position-heading cycle of period 2–100 was detected. The recorded action stream reaches `no_feasible_forward_route` at step 460 / 440; G1 then remains at `(1,23)` through step 800.

The GIFs are 800×450 at 12 fps. They replay saved traces at 0.10 seconds per recorded action. MP4 masters, representative PNGs, visual-only contact audits, per-case diagnostics, and source hashes are included. The gait is presentation-only, not physical locomotion.
