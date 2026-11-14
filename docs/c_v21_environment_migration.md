# C v2.1 environment migration and integrity verification

2026-11-14, university library Mac, repository `/Users/masahir0/Desktop/humanoid-spatial-memory`, branch `phase2/mujoco-proxy-pilot`. Clean starting commit `b6cb1fa`; `git pull --ff-only` reported already up to date.

Python3.12.16 in `.venv`, NumPy2.2.6, MuJoCo3.17.0, matplotlib3.10.3, pytest8.3.5 and pynauty2.8.8.1 exactly match requirements. Hardware: Mac13,1 / Apple M1 Max /32GiB /10 physical and logical CPUs; macOS26.5.1 (25F80), arm64. Hardware was read with sysctl outside the sandbox; metadata includes OS/interpreter paths. No inference about speed versus the previous Mac is made.

All original stores passed read-only full hash inventories, checkpoint payload digests, identity/receipt/run/sequence pairing and empty-staging checks:

| Store | Checkpoint/receipt pairs |
|---|---:|
| `results/raw/phase15_macos_development/fit` |313|
| `results/raw/phase15_bprime_fit_recovery_1/store` |105|
| `results/raw/phase15_bprime_fit_recovery_2/store` |2489|

Total2,907 pairs,36 admitted FIT maze identities and836 exact protected prefix files. No raw file was regenerated, written or substituted. All G1 XML/STL assets were compared against the starting commit; verified asset count: 58. All original FIT72 artifacts and C v2.0d frozen result manifests passed byte-size/SHA checks. No additional untracked input files are required. Reserved worlds and unapproved cohorts were not accessed.

All360 same-machine reference episodes reproduced their saved metric signatures and semantic traces exactly. Baseline sensor, budget, selected-shield and independent safety behavior remained unchanged.

| Reference | Goals/72 | Mean scheduler ms | Mean episode seconds |
|---|---:|---:|---:|
|age|66|1.166|0.1532|
|c0_audit|46|152.482|0.3400|
|c_k|54|151.501|0.3336|
|c_topology3d|52|288.359|0.4761|
|periodic|66|0.069|0.1823|

Scheduler times were measured on this Mac, including formerly uninstrumented Periodic/Age decisions. They are not zero-cost baselines. Evidence and commands: `results/phase2_mujoco/c_v21_multistep_v1/environment/` and `reference_replays/`; verification scripts are read-only and refuse output overwrite.
