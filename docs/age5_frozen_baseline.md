# Additional frozen strong baseline: Age-5

Frozen from b4fa534bfbcf6944766af743cbe5bc56cbdaffe5 and `results/phase2_mujoco/age_cadence_v1/fit72/`. Original cadence controller/source and all72 episode artifacts remain unchanged. Age-5 uses the original local known-cell radius/stale fraction, age threshold5, ternary last-write memory, cap20 including initialization, actual61-ray memory sensor and unchanged G1/safety pipeline.

Saved results:66/72 goals,0 unwanted contacts,770 paid scans (10.694444/episode),3044 H80 steps (42.277778/episode). This is a strong simple descriptive baseline, not a novel algorithm or independent validation. It does not establish simultaneous sensing and movement improvement. CAA must be compared to this baseline rather than only the older Age4/Periodic controls.

The current task replays Age-5 with its historical `CadenceController` implementation. No baseline algorithm change or post-hoc tuning is permitted.
