# Cadence and motion-aware Age v1: descriptive FIT development screen

Base commit: 1e9b5b708622327b59ed97e4c515266103090055.
Route-Rescue restored 66/72 completion at 11.778 observations, but did not
beat the Periodic 11.111 scan mean. The result is preserved. Route-Clock
had 66/72 at 12.944. The preceding View-Veto timing audit showed the first
grant difference at step 4 in all five changed-outcome episodes; this
does not prove that the missed scan caused those outcomes.

## Hypotheses and fixed matrix

Run Periodic, Age, frozen Route-Rescue and the following four arms once.
Here a is the frozen Age age threshold (4), f its stale fraction, and A
the original Age request computed using the original isotropic radius.
The default periodic interval is 4.

* periodic5: fixed period a+1 (5). This is a simpler cadence control, not
  a novel algorithm.
* age5: original Age with stale threshold a+1 (5), unchanged fraction
  and radius. Another simple control.
* age_gap4: A and at least a steps since the last authorized scan,
  including initial scan at step zero.
* age_motion: retain the first original Age request; after it grant A
  only if either (i) a+1 steps have elapsed since the last scan, or (ii)
  at least a-1 steps have elapsed AND at least a-1 cumulative cardinal
  cell translations have occurred or heading differs modulo 2pi from
  the last-scan heading. The actual scan clock is reset on every
  authorized refresh, including an empty observation. This is a
  viewpoint-change proxy, not an actual visibility prediction.
  Parentheses: condition (ii) requires the time condition in both cases.

The fixed one-step increments and movement threshold are prospective
design choices, not fitted by an interval sweep. Age-motion's first
ordinary request is unchanged. The new arms have no additional route
planning or predicted ray footprint in scoring; shared logging can
still compute its point plan. The actual G1 planner, ternary memory,
sensor, emergency safety, cap20 and shield are unchanged. No hidden
state, future observations, per-maze rules, or reserved world access.
The four arms use the exact same authorized observation infrastructure
as the previous Age variants; periodic5 intentionally uses the
time-based request rather than the original Periodic controller type.

## Gates and reporting

Unit tests and existing navigation integration tests; then two keys
(14 episodes) and the full 72-key seven-arm matrix (504 episodes).
Require frozen Periodic/Age/Route-Rescue semantic and metric parity,
smoke parity, actual sensor-call accounting, original data integrity,
no extra shield checks, cap20, and no unwanted contacts in smoke.
Record all full-run results even if ineffective; stop on invariant
failures. No overwriting previous artifacts or adapting after outcomes.

Report all arms and paired comparisons, success, paid and emergency
sensing, combined rays, common-success steps/distance, H80 steps,
blocked actions, contacts and memory errors. Baseline scheduler times
are not measured in this runner and zero is a placeholder. User target:
zero contacts, >66 goals or 66 with strictly fewer than 11.111... paid
scans. Also assess navigation/total sensing tradeoffs. All FIT72
outcomes remain descriptive, not independent evidence; correlated
schedule pairs are retained in the per-episode table. A successful
simple control would strengthen the baseline, not prove algorithmic
novelty; new cohort generation continues to require owner approval.

Output root: results/phase2_mujoco/age_cadence_v1. Run check, smoke,
full, report using scripts/run_age_cadence_fit72.py. These local tests
and MuJoCo runs are pending.
