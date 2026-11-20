# RES-H1 certified rotation-cycle escape: engineering protocol

Base ead01326a09d622404364fa492e8b5628b073339. Preserve previous
risk-ranked safety matrix and rejection decision. 92 tests passed and
180 compact episodes completed. H1 and Full each had 35/36 goals, 32
contact-free goals, and zero nonfirst onsets (3 proven first-transition
contacts remain). Both missed only Periodic4/alternating; 28 decisions,
1.5m translation, no waits, no sidesteps, no retreats, no rejected actions.
This motivates a stationary rotation-cycle hypothesis; aggregate metrics
are not themselves evidence of a precise pose/heading pattern.

## Frozen mechanism

Keep H1 tracking, one-transition reachability, geometry, budget, sensing,
planner, world timing, pedestrian paths, action catalogue and ordinary
fallback unchanged. The wrapper reads only the original public pose,
current emergency measurement, public geometry and blocked-action
feedback. A repeat of a cardinal heading after a heading change at the
same cell marks a rotation cycle. Reset when the observed cell changes.
A sequence A,B,C is not a repeated heading; A,B,A is. If the H1 choice
would be a conditionally certified turn in a marked cycle with observed
or retained tracks, consider the four existing one-cell translations.
Apply the identical H1 static measured-free sweep, current hazard sweep,
one-transition endpoint exclusion, bounds and blocked-action rules.
Only certified alternatives qualify; minimize Manhattan goal distance,
then existing forward/left/right/retreat order. If none qualifies, retain
the H1 choice. Do not override waits, uncertified choices, translations,
no-track decisions, or ordinary turns without a cycle. No extra sensing,
hidden state, actual alternative-shield checks, A*, relaxed clearance or
uncertified risk-ranked escape. The selected action retains the shared
actual shield. This is a deterministic liveness heuristic, not a proof of
eventual progress or safety; it may move away from the goal.

## Ordered execution

1. Read-only old-manifest and original FIT integrity check. Reconstruct
   the failed saved trace's public pose/heading and selected-action
   sequence; record actual action types and archived assessments.
   Stop before navigation if no observed-track cycle followed by turn
   is present. This is retrospective association, not a forced-action
   intervention. Run unit tests including 160 same-state randomized
   translation certificate parity checks against H1, cycle trigger,
   ordinary half-turn, missing tracks and blocked translations.
2. Compact: original 12 hand scenes plus two hand-specified translated/
   phase-offset alternating crossing stress variants. These are targeted
   engineering fixtures, NOT independent evaluation. 14 scenes x
   Periodic4/Age5/DAO-Veto x original/H1/H1-cycle =126 episodes. Exact
   original and H1 trace and metric parity required for all 12 archived
   scenes; preserve old predictive-matrix original parity as applicable.
3. Preserve all original gate conditions from risk_ranked_safety_v1.
   Additionally require no increased nonfirst onsets, no goal or
   contact-free goal harm in any paired H1 case, increased goals across
   the original 12 scenes relative to H1, and at least one cycle escape
   activation. Record all failures rather than tune.
4. Only if both gates pass, run the same old 26-scene / eight-scheduler
   matrix with original and H1-cycle (416 episodes) and the original
   expanded gate. Failure rejects replacement. No new efficacy claim
   or production cohort permission even if passed.

Store read-only audits, all actual staged contacts and sensor accounting,
paired common-success deltas, per-case activation records and source
bindings in a new exclusive output directory. No overwrite or automatic
retuning. Preserve old algorithms/results and original 2907 pairs,
836 protected files and G1 assets. Use the inherited actual sensor and
selected-shield accounting. No production/dev/sealed cohort generation,
reserved-world access or FIT72 rerun. Generator/admission/custody and
statistical blockers stay open. No continuous or physical safety claim.

Commands: scripts/run_res_cycle_escape_v1.py check, compact, report,
expand, report-expand. Real local tests and simulations pending.
