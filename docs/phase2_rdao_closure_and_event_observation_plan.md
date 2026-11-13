# RDAO closure, event-triggered observations, and B+C research roadmap

**Date: 2026-11-13. Status:** eight factual comparison failures identified and
confirmed from saved CSV results. A paired-trace forensic script, optional
real-sensor counterfactual script, and Event+Periodic / Event+Age controllers
are committed but have NOT been run on the user's local pinned MuJoCo.

No RDAO v2.3 is proposed. The existing RDAO policies remain frozen.

## Research question

When should a humanoid robot re-observe changing indoor space so that
it reaches goals safely, using as FEW paid spatial-memory observations and
as FEW movement steps / meters as possible? Preserve high goal completion,
zero unwanted contacts, and realistic computation costs.

RDAO explored H2 (route/task relevance), but is not the research goal.
H1 (persistence-aware memory) is still open, and H3 (actual physically
actuated biped locomotion) is not established on the current kinematic
G1-root model.

## Verified development results

36 repeatedly inspected FIT maze layouts x two correlated pedestrian
schedules, seed42, 80-step horizon, capped spatial-memory scans:

| Method | Goal successes | Mean observations | Mean H80-censored steps |
|---|---:|---:|---:|
| Periodic | 66/72 | 11.111 | 42.208 |
| Age | 66/72 | 11.806 | 40.486 |
| RDAO v1 | 57/72 | 9.111 | 44.736 |
| Footprint | 59/72 | 9.931 | 44.819 |
| RDAO v2 | 61/72 | 9.556 | 44.306 |
| RDAO v2.1 | 59/72 | 8.569 | 45.819 |
| RDAO v2.2 | 59/72 | 9.583 | 44.542 |

Original v1 ablations without route relevance reached 66/72 with 14.79
observations; without visibility reached 66/72 with 12.33 observations.
This cautions against assuming the strict four-factor score is a useful
selective scan gate. None of the RDAO variants dominates Periodic/Age.

## Eight RDAO v2 failures where a simpler control succeeds

Verified via original saved H80 episodes and v2 paired CSV:

| World suffix | Schedule | RDAO v2 | Periodic | Age |
|---|---|---|---|---|
| BP:80010012 | 0, 1 | fail80 | reach67 | reach73 |
| M:80030009 | 0, 1 | fail80 | reach75 | fail80 |
| M:80030010 | 0, 1 | fail80 | reach28 | reach28 |
| R:80000000 | 1 | fail80 | fail80 | reach56 |
| R:80000017 | 1 | fail80 | reach36 | reach36 |

Most striking: M:80030010 consumes **all 20 RDAO memory scans**
while Periodic arrives in28 using8 and Age arrives in28 using9.
This refutes the simple explanation "RDAO just observed too little".
Specific cause(s) are still being investigated, not proven.

## Closure forensic analysis and optional causal intervention

Source:
- scripts/diagnose_rdao_vs_periodic_age_closure.py
- tests/test_rdao_vs_periodic_age_closure.py

Read original 288 baseline traces and all 72 saved v2 traces, then:
1. Locate first observation-schedule difference and first actual
   action/pose difference for each successful-baseline/RDAO failure pair.
2. Restrict candidate missed scans to the *initial common action prefix*
   with identical PRE-ACTION pose, meaning frame step t-1 (not t).
3. Report RDAO score, threshold, reason, route and visibility estimates
   at each common or mismatched scan step. Distinguish correlations from
   causal findings.
4. Optionally replay at most two such shared-pose missed scan steps
   per failed case, with one real authorized 61-ray MuJoCo memory scan.
   Extra preserves the next natural scan; Swap suppresses the first
   subsequently requested scan. The original 20-scan cap always applies.
5. Verify normal v2 reproducibility and all preserved source hashes,
   never read the successful baseline's scan values into the controller.
6. Report whether goal completion changes and whether real memory
   cells actually changed. A no-rescue result does NOT prove that
   better scheduling cannot rescue the episode. Post-hoc target
   steps are NOT deployable timing rules.

Run:
~~~sh
git pull --ff-only origin phase2/mujoco-proxy-pilot
.venv/bin/python -m pytest tests/test_rdao_vs_periodic_age_closure.py -q

# Offline only, no new MuJoCo replay:
.venv/bin/python scripts/diagnose_rdao_vs_periodic_age_closure.py

# Optional local MuJoCo single-scan counterfactuals:
.venv/bin/python scripts/diagnose_rdao_vs_periodic_age_closure.py \
  --intervene --max-interventions-per-case 2 \
  --output results/phase2_mujoco/rdao_closure_periodic_age_interventions_v1
~~~

New outputs:
- results/phase2_mujoco/rdao_closure_periodic_age_forensics_v1/
- results/phase2_mujoco/rdao_closure_periodic_age_interventions_v1/

No retrospective RDAO "success" should be reported as online policy
generalization. If the cause remains partly unknown, document that
uncertainty and close RDAO policy development anyway.

## Candidate A: Event + Periodic and Event + Age

Sources:
- src/spatial_memory/event_observation.py
- scripts/evaluate_event_observation_fit72.py
- tests/test_event_observation.py
- tests/test_event_observation_fit72.py

**Not RDAO:** no A* free/occupied counterfactual scan scoring is used.
Baseline Periodic/Age is the starting controller. Two event signals
are permitted, both from PREVIOUS executed public navigation feedback:

- the single selected G1 action was rejected by the unchanged
  actual-model action shield;
- normal observed-map G1 planner had no route.

An event is eligible at the next decision if at least two steps since
the last memory observation and three steps since the last event scan.
The ordinary Age stale-fraction score remains unchanged. Periodic
checks the original interval (4 steps in baseline FIT) since the most
recent real memory observation, so a new event scan may replace a
later periodic tick rather than adding one.

Existing 61-ray observation, cap20 (initial scan included),
actual G1 planner, independent Emergency Safety sensor, and
selected-only action shield are unchanged. No hidden truth,
shadow sensor, evaluator object labels, future pedestrian schedule,
or world-specific fit IDs are used to request scans.

First exploratory hypothesis frozen BEFORE running these two
variants. Do not tune thresholds on repeatedly inspected FIT36.

Commands:
~~~sh
.venv/bin/python -m pytest \
  tests/test_event_observation.py \
  tests/test_event_observation_fit72.py -q

.venv/bin/python scripts/evaluate_event_observation_fit72.py \
  --max-cases 2 \
  --output results/phase2_mujoco/event_observation_smoke2_v1

.venv/bin/python scripts/evaluate_event_observation_fit72.py
~~~

Output:
- results/phase2_mujoco/event_observation_fit72_v1/event_observation_pairs.csv
- results/phase2_mujoco/event_observation_fit72_v1/event_observation_traces.jsonl.gz
- results/phase2_mujoco/event_observation_fit72_v1/summary.json

Check successful baseline reproductions, paired rescue AND harm counts,
observations + 61-ray costs, H80-censored steps, distance among COMMON
successes, separate emergency scan rays, compute overhead and contacts.
An earlier failure may itself reduce distance; that is not improvement.

## Follow-on Candidate B+C (NOT YET IMPLEMENTED)

**B: Persistence-aware Spatial Memory**: learn a dual-timescale
occupancy belief (transient blockage versus persistent change) from
only authorized histories of remembered occupancy. Not privileged
simulator labels. Quantify calibration, time to discover a persistent
change, false long-term occupancy updates and missed moving obstacles.

**C: Expected Value of Information**: replace the heuristic score
with a probabilistic estimate of the expected REDUCTION in goal
movement/time cost from observing now versus postponing, less the
real sensing and planning cost. Begin with 1-step or short-horizon
public-map belief-state approximations, not an assumed oracle.

Required ablations: Frozen Periodic/Age, A, B only (with ordinary
scheduler), C only (with original ternary memory), and B+C combined.
Model probability and decision cost must be calibrated on development
data only; no outcomes or hidden state from independent evaluation
worlds may be read before freezing the method. Literature grounding
is needed before making novelty claims.

**Research decision:** end further RDAO score engineering. Run the
closure forensic then A. Regardless of whether A wins, proceed to
B+C as a separate testable hypothesis subject to approved data access.
Do not circumvent existing Phase1.5 protected population constraints.
