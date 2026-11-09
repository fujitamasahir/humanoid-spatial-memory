# Case B — R80000001 / Static improvement

## Verified outcomes and first divergence

The saved baseline failed by step 80, with 6 contact states and 234 pedestrian-proxy geometry pairs. The 61-ray run reached the goal at step 76 with zero contacts. The first trace divergence is **step 52**, in: position, action, moved.

Both trajectories match through step 51: G1 is at `(10, 4)`, heading 0, and Static spatial memory has only its initial observation (step 0). At step 52 the planner selects a move to `(11, 4)`. The independent scan observes the proxy at `(11, 5)`; the measured reachable set includes the planned destination, so the controller waits at `(10, 4)`. In the baseline, G1 enters `(11, 4)` at step 52. At step 53 the prescribed proxy moves into `(11, 4)`, where it overlaps the robot. The baseline accumulates 39 contact pairs on each of six states (steps 53–58), totaling 234. Subsequent selected moves are blocked while the overlap persists.

In the safety run, step 53's scan observes the proxy at `(11, 4)`. At step 54 the controller replaces the planned forward move with a one-cell lateral sidestep to `(10, 5)` after its measured reachable set marks `(11, 4)` as unsafe. It waits through step 58 while the proxy traverses the occupied cell, then resumes at step 59 and reaches the goal at step 76. The Static memory observation schedule remains `[0]` in both runs; emergency measurements do not refresh the memory.

## Controlled causal checks

- With scans retained but all emergency action overrides suppressed, the replay matches the saved baseline: no goal by step 80, 6 contact states, 234 pairs.
- Suppressing only the step-52 wait causes the same 6 contact states and 234 pairs to recur, although the robot eventually reaches the goal at step 79. Thus that wait was decisive for avoiding this contact in the tested rollout, but not strictly necessary for binary goal completion if contact is allowed.
- Suppressing the step-54 sidestep leaves the base move selected; the collision shield blocks it. The sensor then sidesteps at step 55, and the robot still reaches the goal at step 76 with zero contacts. Therefore the *exact timing* of the step-54 lateral move is not necessary; avoiding `(11, 4)` and moving laterally once clearance is observed is the effective mechanism.

## Causal conclusion

**Verified mechanism:** step-52 sensing changes the action before G1 enters the proxy's next occupied cell. The step-54 sidestep (or its safe step-55 alternative) keeps the robot out of that cell until the proxy passes. The controlled bypass reproduces the contact episode; no-overrides reproduces baseline. The saved safe trajectory reaches the goal.

**Limit:** this establishes the contact mechanism and outcomes for this fixed schedule and seed. The counterfactual that reaches the goal with contact shows the changed trajectory was necessary for the contact-free result in that intervention ablation, not for goal completion in every possible policy rollout.

## Latest scheduled spatial-memory observation at divergence

The latest scheduled memory observation before step 52 was step 0 in the baseline and step 0 in the 61-ray run. Their raw ray-grid hashes were `a883cc5d84648534433a38a4c3dac5fc95cc4cd1c54ea82c5df58cbc5571e1fe` and `a883cc5d84648534433a38a4c3dac5fc95cc4cd1c54ea82c5df58cbc5571e1fe`; same grid: True. At divergence, evaluator-only proxy cell(s) were `[[11, 5]]`; a proxy cell appeared among the latest scheduled ray observation's occupied cells: baseline `False`, 61-ray `False`. This cell matching is retrospective only and was not an online controller input. The independent 360-degree emergency scan runs every step and is recorded separately.
