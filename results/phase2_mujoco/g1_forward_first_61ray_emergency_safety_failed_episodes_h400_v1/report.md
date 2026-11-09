# Failed 61-ray episodes with 400-step horizon

Replayed the 63 episodes marked unsuccessful in the saved 288-episode 61-ray evaluation. The only policy configuration change was `max_steps: 80 → 400`. The 288-episode source run and all successful episodes were not rerun.

- Reached goal by step 400: **60/63**
- Contact-free goal completions: **60/63**
- Still not reached by step 400: **3**
- Contact episodes in the extended cohort: **0**
- Mean goal step among new completions: **151.73**

The per-episode `elapsed_steps` is the goal step for completed episodes; `goal_step` is blank for episodes that did not complete. `failed_episodes_horizon400.csv` lists every result. The trace file stores each full rerun.

| World | Schedule | Policy | Original 80-step end | Horizon-400 result | Goal step | Unwanted contacts |
|---|---:|---|---:|---|---:|---:|
| 80010001 | 0 | static | 80 | goal | 202 | 0 states / 0 pairs |
| 80010001 | 0 | uncertainty | 80 | goal | 93 | 0 states / 0 pairs |
| 80010001 | 1 | static | 80 | goal | 202 | 0 states / 0 pairs |
| 80010001 | 1 | uncertainty | 80 | goal | 93 | 0 states / 0 pairs |
| 80010004 | 0 | static | 80 | not reached | — | 0 states / 0 pairs |
| 80010004 | 1 | static | 80 | not reached | — | 0 states / 0 pairs |
| 80010012 | 0 | static | 80 | goal | 215 | 0 states / 0 pairs |
| 80010012 | 1 | static | 80 | goal | 215 | 0 states / 0 pairs |
| 80030000 | 0 | age | 80 | goal | 88 | 0 states / 0 pairs |
| 80030000 | 0 | periodic | 80 | goal | 101 | 0 states / 0 pairs |
| 80030000 | 0 | static | 80 | goal | 283 | 0 states / 0 pairs |
| 80030000 | 0 | uncertainty | 80 | goal | 93 | 0 states / 0 pairs |
| 80030000 | 1 | periodic | 80 | goal | 89 | 0 states / 0 pairs |
| 80030000 | 1 | static | 80 | goal | 270 | 0 states / 0 pairs |
| 80030000 | 1 | uncertainty | 80 | goal | 93 | 0 states / 0 pairs |
| 80030002 | 0 | static | 80 | goal | 132 | 0 states / 0 pairs |
| 80030002 | 1 | static | 80 | goal | 132 | 0 states / 0 pairs |
| 80030003 | 0 | static | 80 | goal | 82 | 0 states / 0 pairs |
| 80030003 | 1 | static | 80 | goal | 82 | 0 states / 0 pairs |
| 80030004 | 0 | static | 80 | goal | 379 | 0 states / 0 pairs |
| 80030004 | 0 | uncertainty | 80 | goal | 95 | 0 states / 0 pairs |
| 80030004 | 1 | static | 80 | goal | 287 | 0 states / 0 pairs |
| 80030004 | 1 | uncertainty | 80 | goal | 95 | 0 states / 0 pairs |
| 80030005 | 0 | static | 80 | goal | 102 | 0 states / 0 pairs |
| 80030005 | 1 | static | 80 | goal | 102 | 0 states / 0 pairs |
| 80030007 | 0 | static | 80 | goal | 152 | 0 states / 0 pairs |
| 80030007 | 1 | age | 80 | goal | 93 | 0 states / 0 pairs |
| 80030007 | 1 | periodic | 80 | goal | 89 | 0 states / 0 pairs |
| 80030007 | 1 | static | 80 | goal | 166 | 0 states / 0 pairs |
| 80030008 | 0 | static | 80 | goal | 241 | 0 states / 0 pairs |
| 80030008 | 1 | age | 80 | goal | 166 | 0 states / 0 pairs |
| 80030008 | 1 | periodic | 80 | goal | 194 | 0 states / 0 pairs |
| 80030008 | 1 | static | 80 | not reached | — | 0 states / 0 pairs |
| 80030008 | 1 | uncertainty | 80 | goal | 138 | 0 states / 0 pairs |
| 80030009 | 0 | age | 80 | goal | 90 | 0 states / 0 pairs |
| 80030009 | 0 | static | 80 | goal | 135 | 0 states / 0 pairs |
| 80030009 | 0 | uncertainty | 80 | goal | 115 | 0 states / 0 pairs |
| 80030009 | 1 | age | 80 | goal | 90 | 0 states / 0 pairs |
| 80030009 | 1 | static | 80 | goal | 135 | 0 states / 0 pairs |
| 80030009 | 1 | uncertainty | 80 | goal | 115 | 0 states / 0 pairs |
| 80030010 | 0 | static | 80 | goal | 252 | 0 states / 0 pairs |
| 80030010 | 1 | static | 80 | goal | 252 | 0 states / 0 pairs |
| 80000000 | 0 | age | 80 | goal | 121 | 0 states / 0 pairs |
| 80000000 | 0 | periodic | 80 | goal | 90 | 0 states / 0 pairs |
| 80000000 | 0 | static | 80 | goal | 350 | 0 states / 0 pairs |
| 80000000 | 0 | uncertainty | 80 | goal | 99 | 0 states / 0 pairs |
| 80000000 | 1 | periodic | 80 | goal | 90 | 0 states / 0 pairs |
| 80000000 | 1 | static | 80 | goal | 354 | 0 states / 0 pairs |
| 80000000 | 1 | uncertainty | 80 | goal | 99 | 0 states / 0 pairs |
| 80000003 | 1 | static | 80 | goal | 216 | 0 states / 0 pairs |
| 80000003 | 1 | uncertainty | 80 | goal | 177 | 0 states / 0 pairs |
| 80000007 | 0 | static | 80 | goal | 99 | 0 states / 0 pairs |
| 80000007 | 1 | static | 80 | goal | 99 | 0 states / 0 pairs |
| 80000014 | 0 | static | 80 | goal | 125 | 0 states / 0 pairs |
| 80000014 | 1 | static | 80 | goal | 161 | 0 states / 0 pairs |
| 80000017 | 0 | static | 80 | goal | 110 | 0 states / 0 pairs |
| 80000017 | 0 | uncertainty | 80 | goal | 154 | 0 states / 0 pairs |
| 80000017 | 1 | static | 80 | goal | 110 | 0 states / 0 pairs |
| 80000017 | 1 | uncertainty | 80 | goal | 114 | 0 states / 0 pairs |
| 80000018 | 0 | static | 80 | goal | 212 | 0 states / 0 pairs |
| 80000018 | 0 | uncertainty | 80 | goal | 82 | 0 states / 0 pairs |
| 80000018 | 1 | static | 80 | goal | 212 | 0 states / 0 pairs |
| 80000018 | 1 | uncertainty | 80 | goal | 82 | 0 states / 0 pairs |
