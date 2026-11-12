# RDAO v1 — one-shot observation intervention protocol (development only)

## Motivation and the next falsifiable hypothesis

The saved 72-episode RDAO visibility shadow replay exactly reproduced 584
authorized noninitial measurements. At the 2,637 rejected decisions, the
ordinary 61-ray memory sensor would have revealed 23,922 unknown cell-step
observations, including 6,288 within one Manhattan cell of the next six
nominal forward-A* actions.

The follow-up decision-level analysis found:
- At 971/1,113 **below-threshold** decisions (87.2%), the counterfactual
  ordinary sensor would reveal at least one unknown route-near cell.
- At 552/1,524 **no-candidate** decisions (36.2%), the same was true.
- For the first 20 steps, the share of rejected decisions with at least
  one shadow-visible route-near cell predicted zero visibility was
  40.805% in the 57 RDAO-success episodes and 62.288% in the 15 failures.
- RDAO failed while Periodic succeeded in 10/72 episode/schedule pairs.
  All ten priority rows have a first logged opportunity at **step 2**.
  These correspond to only five world identities, each with two
  schedules, not ten independent worlds.

These are exploratory, outcome-conditioned observations, NOT a proof that
more memory observations increase arrival success.

**Testable hypothesis:** a single ordinary spatial-memory observation
shifted to the first rejected route-near opportunity can change subsequent
navigation and, for some failed episodes, improve goal completion or
horizon-censored arrival efficiency. A second condition tests whether this
effect survives a deliberately replaced later observation rather than
simply increasing sensing dose.

## Implementation

- Script: [evaluate_rdao_one_shot_interventions.py](../scripts/evaluate_rdao_one_shot_interventions.py)
- Contract tests: [test_rdao_one_shot_interventions.py](../tests/test_rdao_one_shot_interventions.py)
- Original implementation and frozen results remain untouched.

Each chosen scenario/schedule is loaded solely from the 36 admitted Phase
1.5 fit worlds; the independent Emergency Safety sensor, selected-action
collision shield, G1 model, horizon 80, seed 42, and maximum 20 memory
observations remain unchanged.

First, the script replays the exact original RDAO episode and checks its
metrics and every saved action/pose/observation/contact frame. It refuses to
interpret intervention outcomes if this fidelity check fails. The
intervention then replays from the identical initial state with one new
**authorized** observation at the pre-selected step. The online scheduler
does not see the diagnostic-only shadow raycast or hidden occupancy.

Two conditions are compared with the original replay:

1. **extra**: grant one normal memory observation at the selected step;
   subsequent online decisions are RDAO v1, and the original 20-observation
   cap still applies.
2. **swap**: grant the same observation and deliberately suppress the
   first subsequent *naturally requested* RDAO observation (if one
   occurs). This is a timing-replacement / observation-dose sensitivity
   condition, NOT guaranteed exact total-dose matching; record final
   observation counts and whether suppression actually occurred.

Record original and changed outcomes, step counts (80-step censoring),
travel distance, turns, blocked attempts, safety interventions, unwanted
contacts, actual observation count, first action/pose divergence, and
whether the forced observation changed the memory, forward-A* action,
or estimated A* route cost.

## Local reproduction

First run fast contract tests:

~~~sh
.venv/bin/python -m pytest tests/test_rdao_one_shot_interventions.py -q
~~~

Then a two-schedule pilot for the previously identified M:80030010 case.
Use an isolated output directory to avoid masking any earlier experiment:

~~~sh
.venv/bin/python scripts/evaluate_rdao_one_shot_interventions.py \
  --cohort priority --world M:80030010 --output \
  results/phase2_mujoco/rdao_v1_one_shot_M80030010_pilot
~~~

If the exact baseline replay is accepted, expand to all ten RDAO-failed
but Periodic-successful development cases (five world identities):

~~~sh
.venv/bin/python scripts/evaluate_rdao_one_shot_interventions.py \
  --cohort priority
~~~

Optionally run a fixed deterministic set of ten RDAO-success controls,
separately:

~~~sh
.venv/bin/python scripts/evaluate_rdao_one_shot_interventions.py \
  --cohort controls
~~~

The default output directory is cohort-specific, and an existing
directory is never overwritten. Each run writes
episode_intervention_comparison.csv, summary.json, and a compressed
intervention_traces.jsonl.gz containing the complete step-wise RDAO
and navigation divergence diagnostics.

## Decision rules

1. **No improvement:** If forcing an early observation has no action or
   outcome benefit, the visibility misses alone do not justify broader
   RDAO v2 observation activation. Study route relevance and actual
   G1/trajectory decision alignment first.
2. **Extra improves, swap does not:** More observations may matter, but
   the experiment does not support a *timing advantage at matched dose*.
   Compare against online dose-controlled Periodic/Age.
3. **Both improve, including cases with comparable final dose:**
   Evidence for a **within-case causal timing effect** on these selected
   development worlds; still no independent generalization claim.
4. **Some improve, some worsen:** Analyze the precise first decision
   divergence. Optimize a selectivity rule rather than triggering on
   all newly observable unknown cells.
5. **Any unwanted contacts or failed fidelity assertions:** Do not
   promote the intervention; investigate safety or replay integrity.

Do not tune to the five selected worlds and then claim they are
independent validation. Freeze an online RDAO v2 candidate, measure
scheduler milliseconds and dose-matched baselines across all 36
admitted development worlds, and only then consider an independently
protected held-out gate.

**Execution status:** The runner and tests are committed, but MuJoCo
interventions and tests have not been run in the authoring environment.
Results must be supplied from the local pinned development environment.
