# C v2.0d FIT72 descriptive development evaluation

Status: completed once after the synthetic `PASS` and independent `ACCEPTED_FOR_FIT` review. This is descriptive development evidence, not independent validation. The 72 keys cover 36 saved mazes × 2 schedules.

## Outcomes

| Arm | Goals / 72 | Unwanted-contact episodes / pairs | Paid scans | Emergency scans | Combined rays | H80 steps | Blocked actions | Emergency interventions | False persistent updates | Missed persistent changes | Mean scheduler ms/episode | Mean episode seconds |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Periodic | 66/72 | 0 / 0 | 800 | 3039 | 234179 | 3039 | 47 | 7 | 64 | 5850 | 0.0 | 0.159 |
| Age | 66/72 | 0 / 0 | 850 | 2915 | 229665 | 2915 | 36 | 5 | 62 | 5611 | 0.0 | 0.148 |
| C0 | 46/72 | 0 / 0 | 387 | 3838 | 257725 | 3838 | 511 | 40 | 19 | 8072 | 125.8 | 0.298 |
| C-K | 54/72 | 0 / 0 | 453 | 3682 | 252235 | 3682 | 434 | 40 | 19 | 7626 | 125.4 | 0.296 |
| C-Topology3-d | 52/72 | 0 / 0 | 606 | 3577 | 255163 | 3577 | 331 | 17 | 23 | 7102 | 246.2 | 0.422 |

## Paired goal and navigation comparisons

| Candidate vs reference | Goals ref→candidate | Rescues / harms | Mean scans ref→candidate | Common-success steps ref→candidate | Common-success distance ref→candidate (m) | Maze sign test, success p |
|---|---:|---:|---:|---:|---:|---:|
| C0 vs periodic | 66→46 | 0 / 20 | 11.11→5.38 | 32.93→38.22 (46) | 18.41→18.90 | 0/11 clusters, p=0.001 |
| C0 vs age | 66→46 | 0 / 20 | 11.81→5.38 | 31.54→38.22 (46) | 17.95→18.90 | 0/12 clusters, p=0.000 |
| C-K vs periodic | 66→54 | 2 / 14 | 11.11→6.29 | 34.27→40.92 (52) | 19.00→19.89 | 1/8 clusters, p=0.039 |
| C-K vs age | 66→54 | 1 / 13 | 11.81→6.29 | 33.08→41.23 (53) | 18.71→20.04 | 1/8 clusters, p=0.039 |
| C-Topology3-d vs periodic | 66→52 | 0 / 14 | 11.11→8.42 | 33.29→38.02 (52) | 18.48→19.08 | 0/8 clusters, p=0.008 |
| C-Topology3-d vs age | 66→52 | 0 / 14 | 11.81→8.42 | 31.67→38.02 (52) | 17.90→19.08 | 0/9 clusters, p=0.004 |
| C-Topology3-d vs C0 | 46→52 | 6 / 0 | 5.38→8.42 | 38.22→37.76 (46) | 18.90→18.90 | 3/0 clusters, p=0.250 |
| C-Topology3-d vs C-K | 54→52 | 1 / 3 | 6.29→8.42 | 40.16→38.35 (51) | 19.56→19.21 | 1/2 clusters, p=1.000 |

The sign tests use one paired delta per maze (the two schedules are grouped together); they are descriptive, with no multiple-comparison adjustment. FIT72 must not be interpreted as a held-out test.

## Computational workload

| Arm | Scheduler ms/episode | Wall s/episode | Total A* calls | Counterfactual A* | Graph analysis ms total | Candidate visits | Top-K comparisons | Grid reads | Graph edge inspections | Copy reads |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Periodic | 0.0 | 0.159 | 0 | 0 | 0.0 | 0 | 0 | 0 | 0 | 0 |
| Age | 0.0 | 0.148 | 0 | 0 | 0.0 | 0 | 0 | 0 | 0 | 0 |
| C0 | 125.8 | 0.298 | 26824 | 22992 | 0.0 | 0 | 0 | 0 | 0 | 0 |
| C-K | 125.4 | 0.296 | 40370 | 36694 | 0.0 | 0 | 0 | 0 | 0 | 0 |
| C-Topology3-d | 246.2 | 0.422 | 24857 | 21306 | 10048.9 | 195785 | 251183 | 2219375 | 8148350 | 13316250 |

C0 and C-K do not execute the new topology graph stage, so their topology-only counters remain zero; comparisons of total scheduler and wall time are more meaningful than comparing unlike graph-operation counts.

## Fixed-state scan swap

The frozen public-memory selection rule chose `phase1.5-v0.4-BPRIME-1:fit:R:80000007` schedule 0, step 9. C0 granted a scan and C v2.0d did not; 60 same-prefix decision disagreements were eligible, and 60 passed the exhaustive-D/common-cost state filter. The highest exhaustive D was 3.500 versus common K=3 cost 0.595; the C v2.0d selected-cell D was 0.256.
A paired scan/no-scan replay from that state kept the preceding trace identical. Both branches reached the goal at step 50 with zero unwanted contacts. The no-scan branch used 18 memory observations; the scan branch used 20. This single intervention shows no goal-step benefit for this chosen state; it does not establish general scan utility.

## Historical RDAO context

These are earlier descriptive FIT72 screens against their stated references, not re-executions in this v2.0d run.

| Historical version | Goals | Rescues / harms | Mean scans | Mean H80 steps | Mean distance (m) | Contacts |
|---|---:|---:|---:|---:|---:|---:|
| RDAO v1 | 59/72 | 2 / 0 | 9.93 | 44.82 | 25.07 | 0 |
| RDAO v2 | 61/72 | 2 / 0 | 9.56 | 44.31 | 24.35 | 0 |
| RDAO v2.1 | 59/72 | 2 / 2 | 8.57 | 45.82 | 24.00 | 0 |
| RDAO v2.2 | 59/72 | 0 / 0 | 9.58 | 44.54 | 24.48 | 0 |

## Interpretation

C-Topology3-d completed 52/72 versus 46/72 for C0 and 54/72 for C-K, with zero unwanted-contact episodes in all three candidate arms. It used 606 paid memory scans versus 387 for C0 and 453 for C-K. Relative to C0, C-Topology3-d's matched outcome changes were 6 rescues and 0 harms; relative to C-K they were 1 rescues and 3 harms.
The C-Topology3-d mean scheduler time was 246.2 ms per episode versus 125.4 for C-K and 125.8 for C0. The navigation result is a descriptive trade-off, not a clean efficiency win: the method raises goal completion over C0, but costs more scheduler time and more paid observations; against C-K it has fewer goals despite the topology ranking and more scheduler work.

## Integrity and limitations

- Periodic/Age baseline metrics and semantic traces reproduced; C0 matched the saved C0 replay exactly.
- All three raw FIT stores, 2,907 payloads/receipts, 836 protected Phase 1.5 files, and 363 original FIT72 artifacts revalidated read-only.
- No world regeneration, reserved cohort access, or store writes occurred.
- Memory error totals are retrospective evaluator metrics. They are not online inputs.
- Two schedules within a maze are correlated. No independent-validation claim is made.
