# RES-H1 single certified phase wait: prospective engineering protocol

Base f8314410cae300d18c189e5700bbb31d9a45681e. Preserve previous
risk-ranked and cycle-escape source and artifacts. Cycle escape completed
97 tests and 126 compact episodes; goals fell 40 to 36 out of42 relative
to H1, no additional nonfirst onsets. Reject that candidate.
The archived Periodic4 alternating case has two moves and26 turns in28
steps. H1 rejects the nominal eastward move at odd steps, chooses a
certified turn, and accepts a return turn at even steps. Its logged
same-state alternatives include a certified wait. Repeated cycle-escape
interventions at the same cell/heading show that a sidestep alone need
not resolve the local liveness issue. The hypothesis is phase locking
between pedestrian motion and robot orientation, not a demonstrated
causal counterfactual.

## Mechanism

Wrap the frozen RESH1. Maintain public pose dwell, visited cardinal
headings since the last change of cell, a repeat-heading cycle flag
and a one-use flag. Mark a cycle on return to a previously visited
heading after an actual heading change at the same cell. At a marked
cycle, if the base planner requests a translation that H1 rejects and
H1 selects a turn instead, and an existing H1 alternative wait is
conditionally certified, select that certified wait in place of the turn.
Require observed or retained track evidence, no no-certificate state
and no previous phase wait in this stationary dwell. Reset the one-use
flag only on an observed position change. Never replace a planned
certified turn, translation or uncertified H1 choice. This does not
assume waiting is always safe. No prediction horizon, clearance or
tracking change. No new sensor, planning or actual shield query.
The next ordinary decision uses the updated actual independent
measurement and unmodified H1. The phase wait may not improve progress.

The single-wait bound is a design choice to prevent repeated stationary
phase-delay interventions, not a parameter fitted to navigation outcomes.
The mechanism is intentionally narrow and reuses the logged certificate
rather than reimplementing wait geometry.

## Frozen experiment

Check old manifests and original integrity via the DAO verifier.
Before any simulation require archived same-state evidence of a
phase-wait eligibility state, then synthetic tests and shared regression
tests. The synthetic phase contract verifies a cardinal crossing in which
the one certified wait preserves heading for the following allowed move,
the one-use bound/reset, ordinary turns, no-track and uncertified states.
This is a mechanism example, not evidence of navigation effectiveness.

Use all14 previous compact scenes plus two hand-defined crossing programs:
longer crossing (y=6,7,8,9,10,9,8,7) and paused crossing
(y=7,8,8,9,8,8), both at x=7 on the same alternating geometry.
These prospective close variants are engineering stress controls, not
independent efficacy worlds. Do not modify any old scenario. Compare
Periodic4/Age5/DAO-Veto x original/H1/H1-phase-wait x16 =144 episodes.
Require exact old original/H1 replay parity, recorded actual sensing,
cap20, selected-only shield checks and ordinary last-write accounting.
Record all actual contacts, including initial unavoidable first
transitions. Preserve each output and failure.

Apply unchanged original gate plus paired H1 preservation:
no added nonfirst onsets, no per-case goal or contact-free-goal harms
versus H1, a strict net goal gain in the previous14 compact scenes,
and observed phase mechanism activation. An unsuccessful candidate
is rejected, not silently retuned. Run the old26-scene x8 scheduler
x2 version expansion (416 episodes) only if both gates pass, and
require original expansion gate again. No physical or independent
safety claim even if expansion passes.

This is a final narrow liveness hypothesis for the current engineering
sequence; if it fails, recommend freezing H1 as an unqualified engineering
candidate and reporting the current timing/planning limitation rather
than repeatedly changing local heuristics against the same crossings.
Do not generate any production/test population beyond the explicit
hand scenes, access reserved sets, run FIT72 navigation, change DAO
thresholds or use sealed outcomes. Generator, admission, custody,
simulation timing and statistical blockers remain unresolved.

Output results/phase2_mujoco/res_phase_wait_v1, exclusive stages check,
compact, report, expand, report-expand. Source/protocol files committed
before execution. Local tests and actual navigation are pending.
