# H2 High-Frequency Dynamics Protocol v1 — Amendment 1

This prospective clarification is committed before the amended smoke and
primary evaluation. It does not rewrite the original protocol, binding, or
first smoke evidence.

The first 52-episode smoke exposed a distinction in the frozen evaluator:
after a successful navigation episode reaches its goal, an evaluator-only
common-horizon map-error calculation can call `World.advance()` until the
80-step horizon. Those post-terminal accounting steps are not navigation
episode steps. Amendment 1 suppresses high-frequency object transitions once
the robot has reached the goal. The evaluator may continue its already-frozen
truth-only bookkeeping, but it no longer produces unlogged post-termination
objects. For an unsuccessful episode, the navigation episode itself runs to
the original 80-step horizon and every step still gets exactly one attempted
object transition.

No observation controller, parameter, route policy, sensing, safety action,
collision query, episode horizon, observation budget, initial state, schedule,
or random stream changes. The old output remains under `smoke/` and is labeled
`INVALIDATED_FOR_DYNAMIC_EVENT_ACCOUNTING` in
`results/phase2_mujoco/h2_high_frequency_dynamics_v1/validation/initial_smoke_issue.json`.
Valid amended smoke results are written to `smoke_amendment1/`; the amended
source hashes are in `binding_amendment_1.json`.
