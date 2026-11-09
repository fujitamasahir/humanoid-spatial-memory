# Phase 2 independent emergency safety sensor

## Scope and result

This is a separate **Static Spatial Memory + Continuous Safety Sensing** condition. It is not the original Static policy. Only the already-saved R / `80000001` / schedule 1 / Static / seed 42 episode was evaluated; the 288-episode benchmark was not run.

The baseline replay matched the saved v3 episode: the G1 did not reach the goal, recorded 6 unwanted-contact states and 234 capsule-proxy contact pairs, used one spatial-memory observation, and ended at step 80 at `(11,4)`. The independent-sensor episode reached the goal at step 76, recorded zero unwanted contacts, and retained exactly one spatial-memory observation. This single result does not establish general pedestrian safety.

Detailed metrics, the baseline/safety timeline, source hashes, and the per-step ray/action trace are in [`episode_comparison.json`](../results/phase2_mujoco/g1_static_independent_safety_R80000001_s1_v5/episode_comparison.json) and [`safety_episode_trace.json`](../results/phase2_mujoco/g1_static_independent_safety_R80000001_s1_v5/safety_episode_trace.json).

## Timing and sensor separation

For each control step the harness performs these operations in order:

1. Advance the simulated world, including the current capsule pose.
2. Scan with the emergency sensor.
3. Ask the original observation scheduler whether to refresh spatial memory.
4. Select the base navigation action from that memory.
5. Allow the safety controller to keep or override that one selected action.
6. Check only the final selected action with the existing MuJoCo collision shield.
7. Apply the kinematic action and record contacts.

The emergency sensor scans once per simulated step with 360-degree horizontal coverage, a 2.0 m range, 181 rays at 2-degree increments, and 0.075 m samples along each ray. It uses MuJoCo first-hit geometry, ignores the G1 body, and returns ray-derived occupied/free cells and proxy classifications. It does not read `World.people()`, proxy centers, route schedules, or future positions. The current simulated pose is placed in MuJoCo as part of the physical sensor backend; the safety controller receives only its measured ray result. The default implementation uses MuJoCo `mj_multiRay` to cast all rays together and vectorized rasterization of measured ray samples; it preserves the 181-ray sensor contract.

The emergency scanner keeps a short-lived track derived from measured hit-cell clusters and maintains its own temporary local grid. Safety scans never call `agent.refresh`, never change the Static controller's cap, and never write into the spatial-memory grid. Unknown or recently changing motion is handled conservatively using the simulator's one-cardinal-cell-per-step movement bound. The action controller uses the public G1 footprint and requires every cell in a lateral/retreat swept footprint to be measured free. It never calls the collision shield for candidate actions. The shield checks only the final selected action.

## Target episode diagnosis

At step 50, with G1 at `(8,4)`, the 2 m sensor sees the proxy in `(10,5)` (6 pedestrian ray hits). At step 51, G1 is at `(9,4)` and the measured proxy hit is `(11,5)` (6 hits). Before the step-52 action, G1 is at `(10,4)`; the sensor again sees `(11,5)` (10 hits). Recent observations show movement followed by a pause, so direction is uncertain. A one-step reachable set from the observed hit cells includes the proposed destination `(11,4)`. The controller waits at `(10,4)` instead of advancing.

At step 53 the proxy is observed at `(11,4)` while G1 remains at `(10,4)`. At step 54, because remaining there is now in the one-step reachable set, the controller selects one lateral move to `(10,5)` after the complete swept footprint is confirmed clear by the independent scan. It waits while the proxy occupies the adjacent corridor, then continues after the observed risk clears. The selected-action shield reports no contact for the escape or later movements.

All seven intervention records (steps 52–58), including position, observed cells, selected and replacement actions, and intervention reason, are in the trace artifact. The 76 safety scans used 13,756 emergency raycasts (181 per scan), with 7,899 total geometry hits and 105 pedestrian-proxy ray hits. The original spatial-memory sensor remained at 61 rays for its one observation, reported separately.

## Comparison

| Metric | Saved baseline replay | Static + safety sensing |
|---|---:|---:|
| Goal reached | No | Yes, step 76 |
| Unwanted-contact states | 6 | 0 |
| Capsule-proxy contact pairs | 234 | 0 |
| Spatial-memory observations | 1 | 1 |
| Emergency scans | 0 | 76 |
| Emergency raycasts | 0 | 13,756 |
| Emergency pedestrian-ray hits | 0 | 105 |
| Forward actions | 33 | 45 |
| Lateral actions | 0 | 1 |
| Backward actions | 0 | 0 |
| Wait actions | 0 | 6 |
| In-place turns | 22 | 24 |
| Selected-action shield checks | 55 | 70 |
| Unselected-action shield checks | 0 | 0 |
| Episode steps | 80 | 76 |

## Reproduction

Run the one-episode software evaluation with:

```bash
.venv/bin/python scripts/evaluate_g1_static_independent_safety.py \
  --output results/phase2_mujoco/g1_static_independent_safety_R80000001_s1_v5
```

The script refuses to overwrite the output directory, checks the baseline replay against the saved episode and its action events, and rehashes the 836 protected Phase 1.5 evidence files before evaluation.

Focused checks:

```bash
.venv/bin/pytest -q tests/test_phase2_emergency_safety.py tests/test_phase2_mujoco.py
```

The safety layer only resolves this target run under the tested model and timing. It uses conservative cell-level reachability and can wait or detour; results for other scenes, pedestrian policies, sensor occlusion, or dynamic interactions remain untested.

## Single-episode implementation optimization

The follow-up behavior-preserving optimization benchmark is saved in [`g1_emergency_safety_optimization_R80000001_s1_v1`](../results/phase2_mujoco/g1_emergency_safety_optimization_R80000001_s1_v1/optimization_report.md). It profiles the prior single-ray implementation and compares it with the default batched implementation, plus experimental 91- and 61-ray variants. In five paired trials on this Mac, the 181-ray scan median fell from 6.127 ms (P95 8.024 ms) to 0.483 ms (P95 0.688 ms); median episode time fell from 665.2 ms to 236.3 ms. The sample-to-grid raster loop dominated the original profile; see the artifact for exact timings, per-step costs, and individual trials.

The optimized 181-ray result reproduced the saved 76-step trajectory and all sensor records exactly, including the step-52 proxy detection and wait intervention, with zero unwanted contacts and one Static spatial-memory observation. This is still one episode and is not a general safety guarantee. Reduced-resolution settings remain experimental and are not the default. Adaptive downsampling is omitted because a low-resolution scan with no return cannot establish that an unseen or occluded proxy is absent.
