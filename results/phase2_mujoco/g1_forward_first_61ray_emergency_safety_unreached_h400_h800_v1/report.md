# Residual 61-ray failures: 400 to 800 steps

This run contains only the three episodes still unsuccessful at step 400. The only changed policy setting is `max_steps: 80 → 800`; source traces match exactly through step 400 for each case.

- Goal reached by step 800: **1/3**
- Contact-free goal completions: **1/3**
- Still not reached by step 800: **2**
- Episodes with unwanted contacts: **0**

| Maze | Schedule | Policy | Result | Goal step | Contacts |
|---|---:|---|---|---:|---:|
| 80010004 | 0 | static | not reached | — | 0 states / 0 pairs |
| 80010004 | 1 | static | not reached | — | 0 states / 0 pairs |
| 80030008 | 1 | static | goal | 479 | 0 states / 0 pairs |
