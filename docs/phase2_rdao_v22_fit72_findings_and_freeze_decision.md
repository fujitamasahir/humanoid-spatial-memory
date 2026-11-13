# RDAO v2.2 fit72 findings and freeze-for-independent-evaluation decision

**Date:** 2026-11-12. Development-only result.
**Repository branch:** \`phase2/mujoco-proxy-pilot\`.
**Worlds:** 36 repeatedly inspected Phase 1.5 B' FIT maze identities,
2 correlated pedestrian schedules each, horizon80, sensor cap20, seed42.
**Status:** v2.2 results saved and verified, not promoted to the default
RDAO controller. The original G1 proxy, external action shield, and
independent emergency sensor remain unchanged.

## Frozen evidence

- results/phase2_mujoco/rdao_v22_decision_protected_fit72_v1/summary.json
- results/phase2_mujoco/rdao_v22_decision_protected_fit72_v1/paired_v22_vs_v1.csv
- results/phase2_mujoco/rdao_v22_decision_protected_fit72_v1/paired_v22_vs_v2.csv
- results/phase2_mujoco/rdao_v22_decision_protected_fit72_v1/paired_v22_vs_v21.csv
- results/phase2_mujoco/rdao_v22_decision_protected_fit72_v1/v22_traces.jsonl.gz

| Outcome | RDAO v1 | Footprint alone | v2 viewpoint | v2.1 angular current quality | v2.2 protected quality |
|---|---:|---:|---:|---:|---:|
| H80 goal completions | 57/72 | 59/72 | **61/72** | 59/72 | 59/72 |
| Mean memory scans | **9.111** | 9.931 | 9.556 | 8.569 | 9.583 |
| Mean capped steps | 44.736 | 44.819 | **44.306** | 45.819 | 44.542 |
| Mean distance | 24.490 m | 25.073 m | 24.354 m | 24.000 m | 24.479 m |
| Mean per-episode RDAO scheduler time | 316.36 ms | 318.37 ms | 325.48 ms | 363.36 ms | 344.68 ms |
| Unwanted contact pairs | 0 | 0 | 0 | 0 | 0 |

**Other comparators:** ordinary Periodic and Age each reached
**66/72** in this same fit cohort; the separately constructed
post-hoc periodic matched-dose control reached **58/72**.
These are not interchangeable baselines.

## v2.2 did not meet its prespecified objective

v2.2 protects a decision-critical region if the existing
public A* free/occupied counterfactual changes immediate
route action or reachability. The read-only diagnostics
show **1,336 protected region scores**, **1,242 discounted
region scores**, and 318 next-viewpoint-deferred region
scores across 245 decision steps. The mechanism is active,
not a no-op.

However, versus v2 viewpoint:
- completions decline **61/72 -> 59/72**;
- mean memory scans **9.556 -> 9.583** (+2 scans total);
- mean capped steps **44.306 -> 44.542** (+17 steps total);
- distance **24.354 -> 24.479m** (+9m total);
- mean per-episode scheduler time **325.48 -> 344.68ms**;
- among the **59 common successes**, 0 faster, 58
  same steps, 1 slower; distance 0 better, 58
  same, 1 worse.

The three meaningful relative-to-v2 changed cases are:
1. \`R:80000017\`, schedule0: still reaches, but arrival
   **58 -> 73**, distance **29.25 -> 36.75m**, and
   memory scans **10 -> 12**.
2. \`R:80000018\`, schedule0: reach79 -> H80 failure.
3. \`R:80000018\`, schedule1: reach79 -> H80 failure.

The two R:80000018 schedule outcomes are correlated
because they share the same maze layout. They
were marginal reach-at-step79 cases under v2,
not robust independent replications.

Compared with v1, v2.2 still rescues **two** failures
(R:80000017 schedule0 and M:80030007 schedule1),
with no harmed previously successful v1 episode.
But it requires **34 extra scans total** relative to v1,
rather than reducing the original 9.11 scans/episode.
Among the **57 v1/v2.2 common successes**, the
aggregate route changes are **+7 steps and +1.5m**.
Consequently, the original joint objective of
*fewer scans and shorter goal-reaching routes*
has NOT been achieved.

The lower average distance on all 72 than
footprint-only is not sufficient: failure episodes
are H80-right-censored, and all-episode mean distance
is not completion-conditioned travel efficiency.

## Interpretation

Protecting candidate regions based ONLY on a
counterfactual change in the immediate first
action did not improve the full v2 policy. Such
a binary rule may protect observations that are
not actually urgent; conversely, a scan that
matters later in the route may not change the
immediate first action. Neither hypothesis is
proved causal by the 72-run aggregate; the
aforementioned deterministic changes are evidence
from already inspected fit mazes only.

The current v2 candidate (one-step next-viewpoint
competition) is the best of the tested RDAO
development variants **for goal completion and
capped steps**, not for scans. v2.1 achieves the
fewest scans of the tested RDAO variants here,
but loses completions and worsens common-success
route steps; it is therefore not a Pareto dominance
over v2.

**Decision:** reject v2.2 as a replacement for v2;
keep v1, v2, v2.1 and v2.2 code/results immutable
for reproducibility; do not make a post-hoc v2.3
threshold/cooldown/FOV search on this same repeatedly
used 36-maze dataset.

## Next scientific milestone: independent test, not another fit-only tweak

Before generating or opening a new evaluation cohort,
freeze in a separate protocol:
1. The tested source commit SHA for each policy
   (including Periodic, Age, original v1, v2, v2.1).
2. Independent maze-identity level partitions with
   no layout or dynamics leakage into calibration.
   The two schedules of one maze are a correlated pair.
3. At least the original 3 mechanism classes R/BP/M,
   comparable fixed horizon, same sensor and G1
   kinematic-root world/robot parameters and seed
   policies; no cherry-picked worlds.
4. All metrics: completion, H80-censored steps,
   steps/distance among common successes, realized
   memory observations and total sensing rays,
   unwanted contacts, emergency interventions,
   planner/scheduler compute, and paired differences.
5. Predeclared rejection/gating rules prioritizing
   safety and goal completion before optimizing
   observations or travel distance.
6. A valid independent distribution generator and
   lineage-aware admission mechanism. DO NOT peek
   into previously reserved selection, calibration or
   assessment materials, or circumvent the guarded
   Phase1.5 population generation/access constraints.
7. A truly new untouched independent test set must
   remain sealed until all policy choices are frozen.
   Exploring an unexposed new development set is
   possible only through an approved data path and
   should not be misrepresented as final holdout.

**Access note:** Phase1.5 B' code intentionally
restricts admitted worlds to the existing FIT store:
\`scenario_from_bprime\` requires a validated FIT
payload; the coordinator's production generator is
disabled unless separately authorized. It is not
appropriate to directly synthesize records that
pretend to be admitted held-out B' worlds, or bypass
these integrity checks. A new legitimate
evaluation cohort requires a separate approved
protocol/data-generation path.

The user-facing RDAO research claim therefore
remains modest: public-map, route-conditioned
observation scheduling can induce specific
per-episode route improvements and reduce
observations in select cases, but has NOT yet
demonstrated general joint superiority over
simpler schedulers.
