# C v2.1a: depth-only control, descriptive protocol

Base result: 63e2debae7376b88ef0d391a0ab3bf93438aec16.
This is a follow-up ablation on repeatedly inspected FIT72, not independent validation.
No new admitted worlds or reserved records are permitted.

## Question

C v2.1 changed both the decision objective and lookahead depth. Its four arms
reached 57/72 but used 15.71-15.79 paid scans per episode. Explicit predicted
future visibility added compute without a material navigation benefit. Freeze
those findings. Before investigating G1-aware value, isolate whether extending
the new objective from one to three conceptual point moves changes decisions
and navigation. This is not a horizon search, and cannot establish an optimal H.

## Fixed policy matrix

* h1_k, h3_k: frozen C-K shortlist (up to five).
* h1_topology, h3_topology: frozen Topology3-d shortlist (up to three).

The no-future-visibility assumption, public ternary memory, probabilities,
two outcome routes, recovery catalog, price and original sensor/shield/planner
are identical. H=1 and H=3 are the only allowed horizons. No future A* or
actual sensor calls in scoring. At a fixed state the H=3 delayed-options set
contains H=1, so its scan-now net value cannot exceed H=1 (up to roundoff).
Consequently H=1 is not inherently a cheaper sensing policy: the comparison
tests the mechanism rather than promising improvement. Trajectories may differ,
so this pointwise ordering need not hold for total episode observations.

Compare H1 vs the matching archived C-K/Topology3-d (objective factor),
H3 vs the matching H1 (depth factor), and all new arms vs Periodic and Age.
The archived C0 and matching controls are displayed for context. H3 is
rerun and must reproduce the previous frozen H3 no-visibility trajectories.
The original one-step D proxy and new H1 are distinct objectives; H1's
same scan-now/min(no-info, delayed) criterion is unchanged from H3.

## Local execution sequence and gates

1. Pull the implementation and protocol; run the dedicated correctness stage.
   It runs the existing C v2.1 tests plus new deterministic 120 selector-state
   comparisons against the independent finite-prefix enumerator, frozen H3
   semantic output parity (excluding timing), the nesting inequality, and
   resource bounds. These are regression/correctness tests, not a new
   synthetic efficacy gate. Do not tune by their outcomes.
2. Require current source hashes, a passing local gate, and the archived
   C v2.1 prospective gate/review and manifests. Verify the original data
   through the frozen read-only integrity routine.
3. Two-key smoke: eight episodes. Require zero unwanted contacts in smoke,
   actual paid sensor count parity, cap20 including initialization, no
   unselected shield queries, no future visibility calls, and 7/11 A* caps.
   Require exact H3 semantic/metric parity with archived trajectories.
4. Full 72-key matrix once, 288 episodes. Require smoke parity for its first
   two keys, H3 parity for all keys, original data revalidation. Record any
   contacts without excluding episodes. Stop on failed integrity/parity.
5. Report all arms, paired rescues/harms, all-episode cost and common-success
   step/distance differences; positive deltas are higher candidate costs.
   Retain per-episode paired rows. Two schedules per maze are correlated;
   no independent inference or multiplicity-adjusted significance claim
   is made by this descriptive report.

Compare actual paid and emergency rays separately, total rays, H80 steps,
common-success movement, blocked actions, emergency interventions and memory
errors from the saved rows. Same-host archived reference timings are context;
timing between separate sessions is not a controlled latency benchmark.
No cost, ranking, horizon or threshold changes based on FIT outcomes.
No new efficacy claim from the old synthetic fixtures.

The previous results and source files must not be overwritten. New exclusive
output root: results/phase2_mujoco/c_v21a_depth_control_v1. A failed stage is
evidence; preserve it and use a new versioned path if another run is needed.
No automatic next policy, no independent cohort generation or reserve access.

## Commands

From the original library Mac checkout with verified FIT stores and .venv:

    .venv/bin/python scripts/run_c_v21a_depth_ablation.py check
    .venv/bin/python scripts/run_c_v21a_depth_ablation.py smoke
    .venv/bin/python scripts/run_c_v21a_depth_ablation.py full
    .venv/bin/python scripts/run_c_v21a_depth_ablation.py report

The implementation was added via GitHub; the local correctness and navigation
runs are explicitly pending until these commands are executed.
