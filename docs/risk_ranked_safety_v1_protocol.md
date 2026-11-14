# Risk-ranked Emergency Safety v1: prospective engineering gate

Base: fe087b6e5f1283447c25a439b4a9cee920c3f02b. Predictive Emergency
Safety v1 is rejected; preserve its source, 416 formal episodes, all contact
timelines and manifests. The most relevant previous failure is an overly
restrictive two-transition endpoint certificate followed by uncertified
waiting. Contact onsets were at actual pedestrian synchronization before a
robot action. Do not change the simulation timing, pedestrian programs,
paid scheduling or shared planner to improve those archived results.

## Fixed factorial mechanisms

All three RES arms copy the frozen predictive controller's observation-only
tracking, reachability, measured static clearance, action catalog, current
swept boxes and deterministic certified-action choice. The original and
unchanged predictive v1 are references. RES-H1 changes endpoint horizon
2 to 1; RES-Risk changes only fallback resolution; RES-Full combines them.
No estimating an actual pedestrian probability, future hidden pose, or
true geometry/shield query for alternatives.

P0 is the union of observed track cells dilated by their age, with the
original two-step expiry and unique reacquisition rule. P1 and P2 are the
one- and two-transition Manhattan dilations of P0. Zero detections with
no retained tracks preserve the base selection, with limited scope.

A conditional certificate requires observed-free static swept cells (the
existing robot cell excepted), no swept box intersection with P0, and no
expanded endpoint intersection with P_h. Translation boxes and conservative
rotation circumradius match v1. Goal ranking among certified alternatives
is unchanged. For the selected-action short circuit and certified alternatives,
RES-H1/Risk/Full do not insert other liveness heuristics.

If no certificate exists, H1 keeps original fallback wait. Risk/Full rank
only candidates with valid bounds, allowed cardinal/turn action, no previous
blocked-action key, measured static-clear sweep, and no newly entered currently
measured pedestrian intersection. An existing measured overlap may be exited
by a translation if ALL intersected measured expanded boxes already contain
the starting point and the endpoint is outside each. Convexity makes each
intersection contiguous; this does not establish noncontact during the exit
or real-world safety. Mark it UNCERTIFIED. The selected actual shield still
may reject the escape. No override of known static occupied or unknown sweep
clearance. If no admissible fallback exists, explicitly record that and wait
without a safety certificate.

For admissible actions rank ascending lexicographically:
  (I[any P0 sweep overlap], I[any P1 endpoint overlap], -m1,
   I[any P2 endpoint overlap], -m2, Manhattan goal distance, catalog ordinal).
Here m_h=min_(q in P_h) max(|end_x-q_x|-expanded_hx,
|end_y-q_y|-expanded_hy), in cells. This is the signed L-infinity
expanded-box margin proxy, not calibrated probability, actual separation or
penetration. A larger margin is preferred. Immediate risk outranks route
goal progress. Risk fallback still checks P1 then P2 even for RES-Full.
This design does not implement route progress/continuity beyond inherited
Manhattan goal distance, and may still oscillate. Current track uncertainty
and unknown static clearance may make every escape inadmissible.

## Stage 0: retrospective and correctness gate

Check immutable old matrix/forensics manifests, original 2,907 pairs and
836 protected files via the frozen DAO integrity routine. Audit recorded
no-certificate cases in the designated prior scenes using the saved public
alternatives (including their original blocked-action eligibility) and an
independent cardinal endpoint proxy for H1. This is a partial retrospective
certificate audit, not an executed counterfactual or a full action feasibility
reconstruction. No future truth inputs are added. New unit fixtures cover
horizon isolation, reversal, overlap exit, unknown static clearance, absence
of tracks, H2-wait action parity and fallback ranking; reuse the old independent
geometry and safety/DAO/G1 tests. A passing check is correctness only.
All definitions and code are committed before compact navigation execution.

## Stage 1: compact matrix

Twelve prespecified hand scenes: original regression pedestrian; old crossing,
head-on, narrow, sudden stop, alternating, unavoidable first transition,
no-pedestrian and no-pedestrian turn; three new engineering scenes (head-on
and empty shifted one row, new crossing with pause at x=9). These close
variants are not independent samples. Preserve their original or declared
engineering role. Original scenarios and old references are unchanged.

Periodic4, Age5, DAO-Veto x 5 safety variants x 12 scenes =180 episodes.
The inherited stage-instrumented runner records actual contact onsets,
separation, selected actions, emergency calls and paid last-write accounting.
Require exact untreated original and predictive-v1 archived semantic/metric
parity for all old scenes. Actual sensor call counts/cap20 and no unselected
shield calls are checked in the reused runner. New scenes are not given
untreated success expectations. Any error preserves partial output; do not
delete it to rerun. The first-transition fixture uses the original timing:
only contact at step1 is classified as proven first-transition unavoidable.

For each RES candidate require ALL:
- No new contacted case relative to original.
- No additional other-than-proven-first onsets per paired case; total such
  onsets strictly lower than original.
- Head-on and narrow entirely contact-free.
- Exact semantic trace parity for all no-pedestrian scenes.
- At least original total goals and original contact-free goals across the
  compact matrix. Report goal harms/individual paired rows as well.
- No recorded uncertified wait despite an admissible translation with lower
  risk key (or an inadmissible wait). This engineering proxy does not
  establish actual avoidability and is not a proof of liveness.

If more than one of the new candidates passes, choose by fewer other onsets,
more contact-free goals, fewer combined rays, then fixed order H1/Risk/Full.
If none passes, reject progression; do not tune or run the full benchmark.
The compact comparison is correlated engineering evidence, not independent
efficacy or physical safety. The selected candidate is a safety component,
not selection of a DAO scheduler.

## Stage 2: conditional expansion

Only if Stage 1 passes, replay all 26 previous scenes x all8 schedulers x
(original and the single selected RES candidate) =416 episodes. Apply exactly
the same gate criteria, old original parity and full accounting; preserve
regression/prospective scene labels and report per case. A failed expanded
gate rejects replacement. The runner must not start another candidate
iteration. This is an engineering gate even if passed, not production pilot
approval. No production/held-out cohort creation/admission/access, no FIT72
policy navigation re-evaluation, and no algorithm changes after outcomes.

Output root results/phase2_mujoco/risk_ranked_safety_v1; all stages exclusive.
Run check, compact, report, expand, report-expand. Expansion automatically
skips if no candidate passed. Commit output only after the stages finish;
preserve error evidence. The report includes paired common successes and
contact timelines as saved staged ledgers, not new exported per-incident
figures. Runtime and local correctness/navigation tests remain pending.

Remaining blockers: simulation timing/occlusions, generator width bias,
admission scalability and unavailable prior signatures, independent custody,
statistical coverage and power/margin approval. No inference about physical
human safety follows from this experiment.
