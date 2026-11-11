# Route-Decision-Aware Observation v1 — Phase 2 validation

## Research question and algorithm

RDAO v1 requests a spatial-memory observation when a currently sensor-reachable, uncertain map region can change the actual orientation-aware, forward-motion G1 A* route, with a timing weight favoring near-term decisions and a threshold increased by remaining-path cost per remaining observation budget. The score is `V × U × D × T`; it is a deterministic heuristic, not calibrated value of information.

Candidate regions are 2×2 grid blocks containing unknown or stale cells near the nominal route. For each, the scheduler plans the current route and counterfactual routes with the region set free and occupied. Route relevance is based on reachability, normalized G1 action-cost difference, and first-action changes. It uses no hypothetical MuJoCo shield calls.

## Development cases and smoke check

- RDAO made 27 noninitial observations across the three diagnostic episodes, with 27 requests over 154 decisions and 0 budget denials.
- Observation activation warning: False; near-every-step request warning: False.
- Periodic and Uncertainty target-case replays were compared to saved traces and episode rows before RDAO runs.
- Case timelines, first-divergence rows, full diagnostic traces, and map/route snapshots are in this result directory.

## Full matched comparison

- RDAO: 57/72 goals, 57/72 contact-free goals, 0 episodes with unwanted contact.
- Mean observations: 9.11; mean arrival/horizon steps: 35.46 among successes (paired tables also use horizon-censored steps for every episode).
- The historical 288 baseline records are reused; only the 72 new RDAO episodes are simulated for the primary comparison.
- Paired 95% intervals resample world identities stratified by R/BP/M, averaging the two schedules within a world. This small development set does not support generalization claims.

### Paired estimates

| Baseline | Metric | RDAO − baseline | Cluster bootstrap 95% CI |
|---|---|---:|---:|
| static | success | 0.278 | [0.153, 0.417] |
| static | contact_free_success | 0.278 | [0.153, 0.417] |
| static | horizon_censored_arrival_steps | -17.125 | [-22.833, -11.847] |
| static | observation_count | 8.111 | [6.833, 9.458] |
| static | travel_distance_m | 3.031 | [0.188, 6.125] |
| static | turns | -10.306 | [-12.750, -7.917] |
| static | blocked_attempts | -10.569 | [-12.361, -8.819] |
| static | safety_interventions | -0.292 | [-1.167, 0.389] |
| static | scheduler_ms | 316.304 | [217.928, 425.425] |
| periodic | success | -0.125 | [-0.250, -0.014] |
| periodic | contact_free_success | -0.125 | [-0.250, -0.014] |
| periodic | horizon_censored_arrival_steps | 2.528 | [-1.597, 7.528] |
| periodic | observation_count | -2.000 | [-2.958, -0.903] |
| periodic | travel_distance_m | 1.448 | [-0.688, 4.146] |
| periodic | turns | 0.958 | [-0.542, 2.569] |
| periodic | blocked_attempts | -0.472 | [-0.778, -0.167] |
| periodic | safety_interventions | 0.167 | [0.000, 0.500] |
| periodic | scheduler_ms | 316.317 | [217.945, 425.435] |
| age | success | -0.125 | [-0.236, -0.028] |
| age | contact_free_success | -0.125 | [-0.236, -0.028] |
| age | horizon_censored_arrival_steps | 4.250 | [0.583, 8.917] |
| age | observation_count | -2.694 | [-3.611, -1.639] |
| age | travel_distance_m | 2.094 | [0.146, 4.594] |
| age | turns | 1.639 | [0.528, 2.972] |
| age | blocked_attempts | -0.319 | [-0.528, -0.125] |
| age | safety_interventions | 0.194 | [0.000, 0.569] |
| age | scheduler_ms | 315.482 | [217.142, 424.523] |
| uncertainty | success | 0.014 | [-0.111, 0.139] |
| uncertainty | contact_free_success | 0.014 | [-0.111, 0.139] |
| uncertainty | horizon_censored_arrival_steps | -1.417 | [-5.347, 2.903] |
| uncertainty | observation_count | 0.792 | [-0.097, 1.819] |
| uncertainty | travel_distance_m | 1.010 | [-0.448, 2.865] |
| uncertainty | turns | -0.542 | [-2.153, 1.111] |
| uncertainty | blocked_attempts | -2.181 | [-3.167, -1.361] |
| uncertainty | safety_interventions | -0.056 | [-0.583, 0.417] |
| uncertainty | scheduler_ms | 314.366 | [216.345, 423.212] |

## Ablations and dose control

| Condition | Goals / 72 | Mean observations | Mean scheduler ms/episode |
|---|---:|---:|---:|
| Full RDAO v1 | 57 | 9.11 | 316.364 |
| rdao_v1_no_route_relevance | 66 | 14.79 | 71.482 |
| rdao_v1_no_visibility | 66 | 12.33 | 466.067 |
| rdao_v1_no_timing | 57 | 8.96 | 409.081 |
- Matched periodic control: exact achieved count in 60/72 episodes; mean target 9.11, actual 8.56. It is post hoc and descriptive.
- Matched control outcomes: 58/72 goals and 8.56 mean observations.

## Inputs, integrity, and limitations

- The scheduler receives ternary memory, observed-cell timestamps, pose/heading, goal, public G1 footprint, blocked-action feedback, sensor geometry, and observation budget. It does not receive `World`, true occupancy, future pedestrian positions, change schedules, evaluator contacts, or privileged visibility labels.
- Emergency Safety and selected-action MuJoCo collision checks are unchanged and remain independent. No unselected action shield query is used.
- The 36 previously admitted fit worlds, 0.75 m/cell assumption, 61-ray sensors, seed 42, schedules, and 80-step horizon are retained. No environment is generated and no held-out test suite is loaded.
- The earlier Phase 1 `disruption-visible` gate became inactive and matched Static; RDAO is a separate algorithm and no prior result is reinterpreted.
- This is kinematic navigation with prescribed pedestrian proxies, not physically controlled humanoid locomotion. A single seed and development data limit causal and statistical claims.

## Reproduction

```sh
.venv/bin/python -m pytest tests/test_rdao.py -q
.venv/bin/python scripts/evaluate_rdao_phase2.py --stage cases
.venv/bin/python scripts/evaluate_rdao_phase2.py --stage primary --resume
.venv/bin/python scripts/evaluate_rdao_phase2.py --stage ablations --resume
.venv/bin/python scripts/evaluate_rdao_phase2.py --stage matched --resume
```
