# Case A — M80030007 / Periodic regression

## Verified outcomes and first divergence

The saved baseline reached the goal at step 64 with no unwanted proxy contacts. The 61-ray run did not reach it within 80 steps and also had no unwanted contacts. Comparing the saved per-step records, the first divergence is **step 38**, in: position, action, moved.

At step 38, both runs were at the same pose before action (position `(8, 10)`, heading π). The planner selected a move to `(7, 10)` in both. The safety scan saw the pedestrian at `(6, 10)` and replaced the move with a wait; it repeated that wait at step 39. In the baseline, G1 moved to `(7, 10)` at step 38, then its step-39 move to `(6, 10)` was rejected by the selected-action collision shield as `translation_collision`. No contact was recorded. This block reason is read from the saved baseline episode metrics.

At step 40, both Periodic policies granted an observation on schedule. The baseline observed from `(7, 10)` and selected `dynamic_threat_uncertain_no_safe_retreat`, remaining there until the pedestrian cleared; it then followed the short lower corridor and reached the goal at step 64. The sensor run observed from `(8, 10)`, turned north at step 40, and took a much longer route around the upper/right corridors. The pedestrian schedule was identical at every aligned step (`matching ground-truth proxy positions: True`); only G1's position relative to that schedule changed. Neither trajectory recorded contact.

## Observation timing, route, and horizon

The Periodic observation step schedule is unchanged through the common interval: baseline `[0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56, 60, 64]`; safety run `[0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56, 60, 64, 68, 72, 76]`. The longer safety run therefore has more total observations (17 versus 20) because it continued beyond the baseline goal time, not because the sensor wrote into memory or changed the scheduler. At step 40 the observation occurred at the same time but from a different pose and therefore supplied different local evidence. The safety trajectory used 80 simulated steps and ended at `[2, 12]`; it exceeded the baseline completion time by 16 steps and hit the 80-step horizon before reaching the goal.

## Controlled causal checks

- With all emergency action overrides suppressed but the 61-ray scans still computed, the replay matched the saved no-sensor baseline and again reached the goal at step 64. The sensor measurement alone did not alter the route.
- Suppressing only the step-38 override did not restore success. Suppressing the step-38 and step-39 overrides also did not restore success: after the baseline-like step-39 collision-shield rejection, the enabled controller intervened at step 40 with an observation-based retreat and the episode took another long route. The exact counterfactual rows are in `controlled_replays.json`.

## Causal conclusion

**Verified mechanism:** safety action selection, beginning with the two waits, changed the robot's position at the periodic observation boundary. The altered pose changed the planner's route, and the resulting detour exhausted the 80-step budget. The all-overrides-suppressed replay returning to the baseline outcome establishes that the action overrides, rather than scanning alone, caused the branch change.

**Limit:** the ablations show that the two waits in isolation are not sufficient to explain the failure; the later state-dependent retreat/action branch matters too. The result does not establish that every safe alternative route would fail. It establishes this controller's saved rollout and the bounded counterfactuals above.

## Latest scheduled spatial-memory observation at divergence

The latest scheduled memory observation before step 38 was step 36 in the baseline and step 36 in the 61-ray run. Their raw ray-grid hashes were `d821956b3e5ffcbc730877f36070f03e5454de5397e3dc8dee35d5bd4781c117` and `d821956b3e5ffcbc730877f36070f03e5454de5397e3dc8dee35d5bd4781c117`; same grid: True. At divergence, evaluator-only proxy cell(s) were `[[6, 10]]`; a proxy cell appeared among the latest scheduled ray observation's occupied cells: baseline `False`, 61-ray `False`. This cell matching is retrospective only and was not an online controller input. The independent 360-degree emergency scan runs every step and is recorded separately.
