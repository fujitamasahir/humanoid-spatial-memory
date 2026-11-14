# FIT72 B/C and historical RDAO comparisons

Descriptive development evaluation only. All methods use the same 72 FIT keys (36 mazes × two correlated schedules, seed 42). Historical RDAO values were reused; no historical run was rerun or changed.

The five-arm runner reproduced every saved Periodic/Age metric row and semantic trace before running B/C. All 72 paired keys completed.

## Policy-level results

Mean H80 steps and distance include every episode; failures contribute their 80-step censored horizon and partial path. The final columns give means among successful episodes only. All successful episodes were contact-free in this cohort.

| Policy | Goals/contact-free | Mean observations | Mean H80 steps | Mean distance m | False persistence total | Missed changes total | Safety interventions | Unwanted contact pairs | Blocked attempts | Scheduler ms/episode | Wall ms/episode | Successful mean steps | Successful mean distance m |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Periodic | 66/66 | 11.11 | 42.21 | 23.04 | 64.00 | 5850.00 | 7.00 | 0.00 | 47.00 | n/a | 154.38 | 38.77 | 21.39 |
| Age | 66/66 | 11.81 | 40.49 | 22.40 | 62.00 | 5611.00 | 5.00 | 0.00 | 36.00 | n/a | 145.02 | 36.89 | 20.77 |
| B only (Persistence + Age) | 66/66 | 11.81 | 40.49 | 22.40 | 62.00 | 5604.00 | 5.00 | 0.00 | 36.00 | 2.22 | 145.35 | 36.89 | 20.77 |
| C only (EVI + Ternary Memory) | 46/46 | 5.38 | 53.31 | 21.04 | 19.00 | 8072.00 | 40.00 | 0.00 | 511.00 | 123.46 | 290.70 | 38.22 | 18.90 |
| B+C (Persistence + EVI) | 46/46 | 3.64 | 53.69 | 21.26 | 20.00 | 8215.00 | 39.00 | 0.00 | 513.00 | 127.86 | 298.98 | 38.83 | 19.22 |
| Initial RDAO v1 | 57/57 | 9.11 | 44.74 | 24.49 | 38.00 | 6093.00 | 19.00 | 0.00 | 13.00 | 316.36 | 508.63 | 35.46 | 19.86 |
| RDAO v1 footprint-only follow-up | 59/59 | 9.93 | 44.82 | 25.07 | n/a | n/a | 6.00 | 0.00 | 13.00 | 318.37 | n/a | 37.07 | 20.85 |
| RDAO v2 viewpoint | 61/61 | 9.56 | 44.31 | 24.35 | n/a | n/a | 6.00 | 0.00 | 13.00 | 325.48 | n/a | 37.87 | 21.05 |
| RDAO v2.1 current-view quality | 59/59 | 8.57 | 45.82 | 24.00 | n/a | n/a | 6.00 | 0.00 | 81.00 | 363.36 | n/a | 38.29 | 20.52 |
| RDAO v2.2 decision-protected | 59/59 | 9.58 | 44.54 | 24.48 | n/a | n/a | 6.00 | 0.00 | 14.00 | 344.68 | n/a | 36.73 | 20.42 |

## Paired outcomes against Periodic and Age

Success deltas show rescued/harmed episode pairs. The 95% intervals resample 36 maze identities, average both schedules within a maze, and stratify by R/BP/M. They are exploratory and unadjusted for multiple comparisons.

| Candidate vs reference | Goals ref→candidate | Rescued/harmed | Δ observations CI | Δ H80 steps CI | Δ distance CI | Δ missed changes CI | Δ false persistence | Δ safety interventions |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| B only (Persistence + Age) vs Periodic | 66→66 | 2/2 | 0.69 [0.33, 1.07] | -1.72 [-3.14, -0.44] | -0.65 [-1.40, 0.07] | -3.42 [-8.61, 0.89] | -0.03 [-0.08, 0.00] | -0.03 [-0.07, 0.00] |
| B only (Persistence + Age) vs Age | 66→66 | 0/0 | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | -0.10 [-0.97, 0.61] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] |
| C only (EVI + Ternary Memory) vs Periodic | 66→46 | 0/20 | -5.74 [-7.96, -3.61] | 11.10 [5.94, 16.71] | -2.00 [-4.30, 0.19] | 30.86 [13.65, 49.46] | -0.62 [-1.62, 0.03] | 0.46 [0.00, 1.08] |
| C only (EVI + Ternary Memory) vs Age | 66→46 | 0/20 | -6.43 [-8.62, -4.31] | 12.82 [7.76, 18.33] | -1.35 [-3.62, 0.74] | 34.18 [18.29, 51.67] | -0.60 [-1.57, 0.03] | 0.49 [0.01, 1.11] |
| B+C (Persistence + EVI) vs Periodic | 66→46 | 0/20 | -7.47 [-9.22, -5.85] | 11.49 [6.49, 17.00] | -1.78 [-4.07, 0.36] | 32.85 [16.94, 50.60] | -0.61 [-1.58, 0.03] | 0.44 [0.00, 1.06] |
| B+C (Persistence + EVI) vs Age | 66→46 | 0/20 | -8.17 [-9.89, -6.57] | 13.21 [8.29, 18.60] | -1.14 [-3.39, 0.96] | 36.17 [21.22, 53.04] | -0.58 [-1.53, 0.03] | 0.47 [0.01, 1.08] |

## New B/C arms paired against saved RDAO generations

These are same-key, maze-cluster paired descriptive comparisons; RDAO rows are read from historical evidence and were not rerun.

| Candidate vs historical RDAO | Goals ref→candidate | Rescued/harmed | Δ observations CI | Δ H80 steps CI | Δ distance CI | Δ safety interventions |
|---|---:|---:|---:|---:|---:|---:|
| B only (Persistence + Age) vs Initial RDAO v1 | 57→66 | 9/0 | 2.69 [1.62, 3.60] | -4.25 [-8.75, -0.56] | -2.09 [-4.51, -0.09] | -0.19 [-0.57, 0.00] |
| B only (Persistence + Age) vs RDAO v1 footprint-only follow-up | 59→66 | 8/1 | 1.88 [0.88, 2.69] | -4.33 [-8.89, -0.51] | -2.68 [-5.09, -0.62] | -0.01 [-0.04, 0.00] |
| B only (Persistence + Age) vs RDAO v2 viewpoint | 61→66 | 6/1 | 2.25 [1.26, 3.10] | -3.82 [-8.10, -0.35] | -1.96 [-4.20, -0.12] | -0.01 [-0.04, 0.00] |
| B only (Persistence + Age) vs RDAO v2.1 current-view quality | 59→66 | 9/2 | 3.24 [2.19, 4.18] | -5.33 [-10.12, -1.28] | -1.60 [-4.08, 0.55] | -0.01 [-0.04, 0.00] |
| B only (Persistence + Age) vs RDAO v2.2 decision-protected | 59→66 | 8/1 | 2.22 [1.22, 3.08] | -4.06 [-8.54, -0.39] | -2.08 [-4.43, -0.15] | -0.01 [-0.04, 0.00] |
| C only (EVI + Ternary Memory) vs Initial RDAO v1 | 57→46 | 0/11 | -3.74 [-6.01, -1.44] | 8.57 [4.40, 13.35] | -3.45 [-6.40, -0.70] | 0.29 [-0.14, 0.89] |
| C only (EVI + Ternary Memory) vs RDAO v1 footprint-only follow-up | 59→46 | 0/13 | -4.56 [-6.92, -2.22] | 8.49 [3.85, 13.53] | -4.03 [-7.19, -1.09] | 0.47 [0.00, 1.10] |
| C only (EVI + Ternary Memory) vs RDAO v2 viewpoint | 61→46 | 0/15 | -4.18 [-6.44, -1.90] | 9.00 [4.76, 13.83] | -3.31 [-6.20, -0.64] | 0.47 [0.00, 1.10] |
| C only (EVI + Ternary Memory) vs RDAO v2.1 current-view quality | 59→46 | 2/15 | -3.19 [-5.25, -1.10] | 7.49 [2.93, 12.35] | -2.96 [-5.76, -0.43] | 0.47 [0.00, 1.10] |
| C only (EVI + Ternary Memory) vs RDAO v2.2 decision-protected | 59→46 | 0/13 | -4.21 [-6.49, -1.92] | 8.76 [4.50, 13.61] | -3.44 [-6.39, -0.70] | 0.47 [0.00, 1.10] |
| B+C (Persistence + EVI) vs Initial RDAO v1 | 57→46 | 0/11 | -5.47 [-7.22, -3.78] | 8.96 [4.81, 13.68] | -3.23 [-6.23, -0.42] | 0.28 [-0.17, 0.89] |
| B+C (Persistence + EVI) vs RDAO v1 footprint-only follow-up | 59→46 | 0/13 | -6.29 [-8.14, -4.51] | 8.88 [4.26, 13.86] | -3.81 [-7.03, -0.82] | 0.46 [0.00, 1.08] |
| B+C (Persistence + EVI) vs RDAO v2 viewpoint | 61→46 | 0/15 | -5.92 [-7.65, -4.24] | 9.39 [5.12, 14.15] | -3.09 [-6.05, -0.34] | 0.46 [0.00, 1.08] |
| B+C (Persistence + EVI) vs RDAO v2.1 current-view quality | 59→46 | 2/15 | -4.93 [-6.47, -3.42] | 7.88 [3.42, 12.67] | -2.74 [-5.60, -0.16] | 0.46 [0.00, 1.08] |
| B+C (Persistence + EVI) vs RDAO v2.2 decision-protected | 59→46 | 0/13 | -5.94 [-7.68, -4.25] | 9.15 [4.89, 13.93] | -3.22 [-6.24, -0.42] | 0.46 [0.00, 1.08] |

## Interpretation and limitations

- B-only reproduced Age’s success count (66/72), observation count, steps, distance, safety counts, and trajectory metrics exactly. It changed the aggregate missed-change error by only −7 cell-time units over 72 episodes (cluster interval includes zero).
- B-only versus Periodic rescued two and harmed two episodes, so completion was unchanged. Its all-episode H80-censored step delta was −1.72 [−3.14, −0.44], while the observation count rose by 0.69 [0.33, 1.07]. The distance interval crossed zero.
- C-only and B+C each harmed 20 Periodic/Age successes and rescued none (46 vs 66 goals). Their paid observations fell by about 5.7 and 7.5 per episode versus Periodic, but missed-change error and blocked attempts rose; emergency interventions were 40 and 39 compared with 7 Periodic and 5 Age.
- C-only/B+C measured scheduler cost averaged 123/128 ms per episode. Mean episode wall time was about 291/299 ms versus 145/154 ms for Age/Periodic in this same run. B-only scheduler cost was 2.22 ms. Wall-time differences include scene/runtime overhead.
- All new and historical arms recorded zero unwanted contacts in these saved episodes. This does not establish safety beyond FIT72.
- Both the initial RDAO v1 and its footprint-only follow-up are listed separately because they are distinct saved v1 results. RDAO v1/v2/v2.1/v2.2 all use the same 72 keys. Most historical RDAO tables lack memory-error fields; those values remain unavailable.
- FIT72 is descriptive development evidence, not independent validation. The two schedules per maze remain clustered. No B/C parameter was tuned.

Per-episode traces and provenance are in persistence_evi_fit72_restored_local_v1/. Policy summaries, paired deltas, cluster intervals and input hashes are in this analysis directory.

Reproduction:

    .venv/bin/python -m pytest tests/test_persistence_evi.py tests/test_persistence_evi_evaluation.py -q
    .venv/bin/python scripts/evaluate_persistence_evi_fit72.py --output results/phase2_mujoco/persistence_evi_fit72_restored_local_v1
    .venv/bin/python scripts/analyze_persistence_evi_fit72_restored.py
