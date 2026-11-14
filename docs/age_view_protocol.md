# Directional Age sensing v1: frozen descriptive pilot

Base: dad7e8c78aedaa2f00bb2472e006dddf2ac08f96.

The H1/H3 study reported identical aggregate completion, sensing and movement
for matched selectors. Explicit future visibility previously added computation
without useful navigation changes. The EVI branch is frozen for now.

Hypothesis: the original Age score counts stale known cells in an isotropic
radius even when they are outside the current predicted sensing footprint.
Restricting this trigger to observable cells might save paid scans without
reducing completion. The prediction uses remembered occupancy, not actual
sensor results; imperfect 3D observability and excluded unseen cells may harm
navigation. No effectiveness is claimed before testing.

## Frozen policy matrix

Periodic and Age are unchanged. Two new variants use the exact original Age
radius, age threshold and stale-fraction threshold. Let A be the original
fraction of stale known cells in the local radius, and F the same fraction
restricted to the existing 61-ray public-memory visibility approximation.
An empty denominator gives zero. Both exclude never-observed cells.

* age_view_veto: scan when Age requests AND F meets its original fraction
  threshold, or when the original Age requests after two age intervals since
  the latest observed-cell timestamp.
* age_view_clock: scan when F meets the original fraction threshold, or when
  the original Age requests after two age intervals since the latest
  observed-cell timestamp.

The fallback is conditional on the original Age request, not an unconditional
periodic scan. The two-interval factor is a design choice, not optimized.
Latest observed timestamp is a proxy for last nonempty scan; no guarantee
that each episode uses fewer scans follows from same-state veto inclusion.

The original sensor, full ternary memory update, G1 planner, independent
emergency sensing, selected-only shield, seed and 20 inclusive scan cap are
unchanged. No hidden observations, future world states or reserve access.
No policy tuning based on this screen.

## Evaluation

First run deterministic unit tests and existing navigation integration tests.
Require the archived same-machine reference evidence and data integrity
before smoke. Two-case smoke requires no unwanted contacts and original
baseline parity. Full matrix runs once with smoke parity, all baseline
semantic and metric parity, actual paid sensor accounting, cap and shield
invariants. Verify original stores again afterward; preserve output on error.

Primary descriptive target per user: zero unwanted contacts and more than
66/72 goals, or 66/72 with mean paid observations strictly below both
Periodic (11.111) and Age (11.806). A higher-success result with higher cost
is a tradeoff, not a joint efficiency win. Report paired rescue/harm,
common-success steps and distance, combined actual rays and memory errors.
Baseline scheduler overhead is not measured in this runner; zero is explicitly
a placeholder, not a measured runtime. Two schedules per maze are correlated.
No claim of independent validation or statistical superiority.

The next scientific stage requires a separate authorized development and
sealed evaluation population; FIT72 remains a reused descriptive pilot.
No generation or access to protected/held-out populations in this task.

Outputs: results/phase2_mujoco/age_view_v1, exclusive directories; archive
any failures rather than overwrite. Commands: check, smoke, full, report
using scripts/run_age_view_fit72.py. Local execution is pending.
