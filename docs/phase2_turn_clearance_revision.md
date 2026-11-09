# Phase 2 forward-first turn-clearance revision

The forward-facing A* planner no longer rejects an in-place turn using the
rotated public-footprint AABB. The AABB around the footprint can overlap a
diagonal occupied-cell box even when the articulated G1 model clears that
turn. Instead, A* selects its best turn using the observed occupancy map, and
the evaluator checks only that selected turn with the pinned G1 MuJoCo
collision model. A blocked turn is recorded as attempted-action feedback and
removed from subsequent plans until relevant local observation evidence
changes. The planner does not query hidden occupancy or probe unselected
turns. Translation clearance remains unchanged.

This is a prospective Phase 2 navigation-policy implementation change. It
does not change Phase 1.5 evidence, the prior forward-first 288-episode output,
or the fitted maze identities. The new evaluation uses the same 36 saved
identities, two schedules, four observation methods, seed, 0.75 m/cell
assumption, observation budget, and episode horizon as the prior comparison.
The output is saved separately at
`results/phase2_mujoco/g1_forward_first_shield_turns_v1_full_288/`.

The run completed 288 episodes. Goal completion increased from 21/288 in the
prior forward-first output to 225/288. Contact-free completions were 21/288
and 224/288, respectively. Two episodes recorded pedestrian contacts; one
was successful but therefore not contact-free. The new run executed 3,964
turn actions; three selected turns were rejected by the MuJoCo shield. It
made zero unattempted collision queries. This outcome supports removing the
AABB turn prefilter, while the pedestrian-contact result remains a navigation
safety issue to address separately.

Focused regression tests: `tests/test_phase2_mujoco.py` (50 passed).
