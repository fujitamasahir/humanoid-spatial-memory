# Deadline single-scan omission v1: prospective causal engineering audit

Base 1a8870c1d42da6e7ec9cfc988c3d36e6346d37f9.
Freeze the previous route-gated comparison (68 tests,416 episodes,
260 reference parities). Route Gate had no scan suppression. Deadline
and Joint produced identical aggregates; compared with DAO-Veto, Deadline
reduced paid scans104 to99 (original safety) and104 to102 (Phase Wait),
with same23/26 goals and zero common-success step/distance differences.
Phase Wait remains an unapproved engineering safety condition; original
safety has actual pedestrian contacts. No independent superiority claim.

## Research question

Which of the remaining actual Deadline observations affect navigation?
Prior associations of scan content, information estimates or same-state
grants do not demonstrate causal usefulness. Use a stipulated one-scan
intervention on already-used deterministic hand scenes. The intervention
is an evaluator experiment, not a deployable scheduler or hindsight rule.

Freeze the full target census: each of26 old scenes and each of two
safety versions, every actual noninitial paid scan of Deadline. The
archive has99+102 paid scans including52 mandatory initial readings,
so149 interventions and52 untreated replays =201 episodes. No target
selection using effects; no FIT72 navigation, no new cohort, no reserved
access, no threshold tuning. No assumptions of independence across
interventions, scenes or safety versions.

## Intervention and correctness

Run the frozen Deadline from the initial state. Exactly reproduce the
archived semantic trace, metrics (excluding the established timing
fields), paid readings, and scheduler decisions in each untreated replay.
For each target step use a separate fresh full replay; require identical
pre-target trace, actual paid readings and scheduler decision ledger.
Require matching granted decision and matching remaining decision fields
at the target, then cancel only that grant before any actual paid ray.
Cancel its request bookkeeping and outstanding authorization; do not
change memory, timestamps, last scan, cap, emergency observation,
planner or world timing. Normal policy resumes on the next decision;
a subsequent grant can shift the original observation rather than
reduce total sensing. The target is selected only by the evaluator;
the original online observation code is not given actual hidden state,
future pedestrian programs or omitted actual sensor readings. No actual
unselected shield calls or extra observations inside an episode.
The same frozen instrumented runner validates real sensor calls,
last-write memory and selected-action-only shielding.

Tests exercise cancellation, later authorized refresh, wrong target
and initial-scan rejection; prior route gate and safety regressions.
Verify archive and original-data manifests and use exclusive output
folders, keeping failure evidence. The schedule is determined by the
already frozen archive, and all rules, code and tests are committed
before executing any intervention.

## Evaluation

For each pair record realized omitted-reading new/changed-known counts
from the untreated recorded reading (evaluator only), public decision
features including discovery, verification, fallback, predicted route
discovery, first action/pose divergence, next authorized paid reading,
goal outcome, contacts, paid and combined rays, elapsed steps and paired
common-success distance. Report by safety condition. The descriptive
"no-worse common-success observation saving" requires both goals,
nonincreased total/nonfirst contact onsets and contact pairs,
nondecreased contact-free completion, fewer total paid scans,
nonincreased combined rays, and no increase in steps or distance.
Retain all negative effects and goal rescues separately. Non-goal
cases cannot qualify through early termination. A single deletion's
effect is conditional on its unique untreated prefix; effects need not
be additive or persist when several scans are removed. Retrospective
content may inform future hypotheses but may never enter online policy.
No automatic policy selection, no efficacy inference, no safety
promotion or production cohort approval.

Output results/phase2_mujoco/deadline_single_omission_v1.
Run scripts/run_deadline_single_omission_v1.py check, run, report.
Local tests and simulations remain pending at source freeze.
