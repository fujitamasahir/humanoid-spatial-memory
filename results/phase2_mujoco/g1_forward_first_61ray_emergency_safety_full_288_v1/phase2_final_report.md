# Phase 2 final evaluation: optimized 61-ray Emergency Safety Sensor

## Executive summary

Across 288 matched episodes, the 61-ray independent emergency sensor produced 225/288 goal completions and 225/288 contact-free goal completions. It recorded 0 contact episodes, 0 contact states, and 0 proxy contact pairs. The sensor does not write to spatial memory; the policies retain their existing observation schedules.

## Setup

36 already-saved Phase 1.5 development mazes × two saved pedestrian schedules × Static, Periodic, Age, and Uncertainty × seed 42; 80-step maximum, 0.75 m/cell assumption, existing forward-first navigation and selected-action-only MuJoCo shield. No worlds or schedules were regenerated. All four policies used the same 61-ray, 360°, 2 m, 0.075 m emergency scanner once per simulation step.

## Overall results

| Metric | Prior matched baseline | 61-ray sensor | Difference |
|---|---:|---:|---:|
| Goal completions | 225/288 | 225/288 | +0 |
| Contact-free goal completions | 225/288 | 225/288 | +0 |
| Episodes with unwanted contact | 1 | 0 | -1 |
| Contact states | 6 | 0 | -6 |
| Proxy contact pairs | 234 | 0 | -234 |
| Spatial-memory observations | 2314 | 2321 | +7 |
| Emergency scans / rays | 0 / 0 | 13731 / 837591 | — |

## Policy comparison

| Policy | Goals baseline → 61-ray | Contact episodes baseline → 61-ray | 61-ray contact-free goals | Memory observations mean baseline → 61-ray | Memory rays total baseline → 61-ray | Emergency scans / rays | Interventions (wait / lateral) | Mean path m baseline → 61-ray | Success step mean baseline → 61-ray | Median runtime ms baseline → 61-ray |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Static | 36 → 37 / 72 | 1 → 0 | 37/72 (51.4%) | 1.00 → 1.00 | 4392 → 4392 | 4454 / 271694 | 40 (36 / 4) | 21.42 → 21.46 | 43.69 → 44.70 | 177.72 → 206.86 |
| Periodic | 67 → 66 / 72 | 0 → 0 | 66/72 (91.7%) | 11.07 → 11.11 | 48617 → 48800 | 3039 / 185379 | 7 (7 / 0) | 22.90 → 23.04 | 39.10 → 38.77 | 117.54 → 132.59 |
| Age | 66 → 66 / 72 | 0 → 0 | 66/72 (91.7%) | 11.79 → 11.81 | 51789 → 51850 | 2915 / 177815 | 5 (5 / 0) | 22.38 → 22.40 | 36.86 → 36.89 | 114.40 → 117.35 |
| Uncertainty | 56 → 56 / 72 | 0 → 0 | 56/72 (77.8%) | 8.28 → 8.32 | 36356 → 36539 | 3323 / 202703 | 23 (18 / 5) | 23.29 → 23.48 | 35.70 → 36.48 | 104.64 → 120.76 |

## Runtime and sensing costs

- Emergency scans: 13731 total; 47.68 mean and 43.0 median per episode.
- Emergency raycasts: 837591 total; 61 rays per scan verified.
- Measured emergency scan processing time: 4452.1 ms total.
- Per-episode scan-time summaries: median of episode medians 0.289 ms; median of episode P95 values 0.367 ms.
- Spatial-memory rays: 141581 total, separate from emergency rays.
- Spatial-memory ray counts are exactly derived as each logged authorized observation count × the frozen 61-ray spatial-memory scanner configuration; the original append-only episode log is unchanged. See `metric_derivation.json`.

- Spatial-memory observations: baseline 2314 (8.03/episode); 61-ray 2321 (8.06/episode).
- Spatial-memory processing: 1250.3 ms total; per-episode totals median 3.86 ms.
- Episode-timed execution total: 52.44 s (mean 182.10 ms, P95 361.44 ms); evaluation-loop total 37.58 s; scene-construction total 14.79 s.
- The initial matrix command completed and durably recorded all 288 episodes, then stopped at a post-run validation assertion that incorrectly required adaptive policies to retain baseline observation counts after their paths changed. The run resumed from the preserved records. Its first-process wall-clock total was not persisted; paired episode wall timings below were separately measured on this machine.
- Actions (forward / lateral / backward / turn / wait): baseline 9669 / 2 / 0 / 3964 / 5; 61-ray 9693 / 10 / 0 / 3962 / 66.
- Matched per-episode runtime medians: baseline 122.85 ms, sensor 136.48 ms; paired median delta 13.17 ms (10.6% median paired overhead).

## R / 80000001 target episode

For R / 80000001 / schedule 1 / Static, the 61-ray scan at step 52 observed the proxy at cell (11, 5), rejected the planned move into (11, 4), and waited; it sidestepped safely at step 54 and reached the goal at step 76 with zero contact pairs. The prior baseline episode had 234 proxy geometry pairs across 6 contact states and did not reach the goal. Preflight status: `PASS_TARGET_EPISODE_PREFLIGHT`. Full trace and evaluator-only contact diagnostics are saved in `episode_traces.jsonl.gz`.

## Failure analysis

See `failure_analysis.md` for every contact step, same-step sensor observation, action/intervention, and baseline-to-sensor gained/lost successes.

## Limits and conclusions

This is a development-set simulation using one seed, prescribed non-reactive capsule pedestrians, and kinematic G1 root translation. A 0.75 m/cell scale is an assumption, not calibration. Results do not establish safe physical locomotion or real-world pedestrian safety. Sensor ray processing cost is additional to spatial-memory observation cost; a higher safety scan count must not be reported as an increase in the agent’s memory observation budget.

## Reproducibility

The run manifest pins the commit, source hashes, saved-world identities, baseline hashes, policy configuration, and software versions. `episodes.csv`, traces, comparison tables, timing pairs, figures, and artifact hashes are in this directory.
