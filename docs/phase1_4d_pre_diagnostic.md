# Phase 1.4D-Pre: post-assessment diagnostic review

Reviewed 2026-11-06 on `feature/phase1-4c-assessment`, starting from
`20c0f8f662603b2e085a3af2932d29cdab629d89` (also the fetched remote tip).
This is a documentation-only analysis of existing records. No policy, parameter,
historical result, assessment artifact or environment was changed. No assessment,
tuning, held-out or ablation episode was executed for this review.

## Finding and recommendation

The immediate cause of zero requests is **failure of the score threshold on every
saved decision**, not the visibility-mass gate or exhausted sensing capacity.
The selected threshold is 0.6; the maximum recorded score is 0.5. Sparse,
grid-size-normalized single-cell route effects, further attenuated by visibility,
interact with this threshold. Disagreement probabilities are generally large,
so low estimated occupancy disagreement is not the principal explanation.
This is the behavior of the frozen specification, not evidence of a checkpoint
failure or an implementation/protocol mismatch in the checked score arithmetic.

**Recommendation: approve the unchanged Phase 1.4D matrix only as a bounded,
preregistered diagnostic completion, then stop.** It has two potentially useful
manipulations and four controls whose scientific behavior is expected to remain
Static on these realizations. It cannot provide six independent demonstrations
of mechanism importance, repair the negative assessment result, or validate a
new method. If the review requires six behaviorally informative comparisons,
defer execution rather than change this matrix or its locked parameters.
No execution is authorized or started by this report; review is the next step.

## Evidence and integrity audit

Inputs were the [frozen protocol](phase1_4_experimental_protocol.md),
[tuning validation](phase1_4b_validation.md),
[assessment validation](phase1_4c_validation.md), the parameter lock and its
selection artifacts, assessment compact records, raw gzip traces, and local
run/session contracts. A standalone local reader used Python 3.12.10, JSON,
gzip, SHA-256 and NumPy. It did not import or invoke policy/episode runners,
generate scenarios, refresh a policy, or overwrite the existing analyzer outputs.
The temporary audit calculations remain outside versioned results.

The fresh audit passed these checks:

| Check | Result |
| --- | --- |
| Inventory, compact records and actual episode filenames | Exactly 13,440 each; no missing, extra or duplicate IDs |
| Every inventory entry | Compressed size and SHA-256 match its raw file |
| Every raw bundle | Job equals compact job; metrics equal compact metrics; run ID matches |
| Every job ID | Matches canonical SHA-256 of its job fields |
| Complete ordered job plan | Hash matches the recorded frozen plan |
| Configuration in every bundle | Assessment purpose, no ablation, matching replicate, cap and parameters |
| Observation ledgers | Frame grants, requests and denials match saved episode totals |
| Run provenance | All 33 recorded source files match after CRLF-to-LF normalization |
| Parameter lock and sidecar | Match the pinned checksum; every lock-referenced selection artifact also matches |
| Disruption-visible decisions | All 23,166 component sums, visible masses and trigger outcomes agree with their saved fields |
| Route-disruption components | All 633,318 candidate values match the two saved costs and frozen grid-size normalization |

The inventory totals **124,273,381 compressed bytes**. Raw traces are at
`C:/Users/81704/Desktop/fujita/31_humanoid-spatial-memory/humanoid-spatial-memory/results/raw/phase1_4c_assessment/`.
The inventory's absolute Linux path is another view of this same Windows-backed
directory; the audit used its repository-relative root.
The existing independent assessment report records 295,680 reconstructed metric
checks. This review rechecked the inventory, identities and observation ledgers;
it did not rerun that full truth/memory reconstruction or its bootstrap analysis.

SHA-256 anchors for this review:

| Artifact | SHA-256 |
| --- | --- |
| `results/phase1_4b/parameter_lock.json` | `ecdd2f11e0c279bfa6c8557fcc646c4f714d2c7627deb731cbb366138a64d2f1` |
| Assessment manifest | `6335b77dd5838b2ea312d3293c939354e0b7f454eccbc679f0c59d4fe031c822` |
| Assessment `episodes.jsonl` | `4ab0cb0b2175abc5404c9197013c828d1e234a5f7059eecfc4b4cef80a9171bf` |
| Assessment `trace_storage_manifest.json` | `b9056d634cb9d49c600568d00b213cdf6e4646640362c23b0f2b7b2dbecfdb6f` |
| Assessment `run_provenance.json` | `bf0999a88b0c950c0c2a3022761ddfe563ade480e152fc44dd7fba1fb4c27818` |
| Assessment `independent_verification.json` | `85b895a24e30ccf0cfca8abec64bc3d3f0275c172798aca9d65f38d9b5f26ebb` |

## Trigger and component distributions

For each noninitial saved disruption-visible decision, the implemented rule is

```text
D_i = min(N, abs(J_i,occupied - J_i,free)) / N
S   = sum_i V_i * q_i * D_i
M   = sum_i V_i
request = candidates_nonempty and S > theta_D * 1.5 + lambda * h/b_eff and M >= .25
```

The unlimited-cap budget term is zero. The lock selects `theta_D=.4` and
`lambda=0`, so every threshold is mathematically **.6** (stored float
`0.6000000000000001`). Strict `>` is preserved. The current source implements
the protocol's sum, normalization and gates; no score is divided by candidate
count or visible mass. The normalization at issue is within each `D_i`.

All distributions below pool saved decisions, including repeated caps. They are
descriptive exposure summaries, not independent samples or confidence intervals.
Longer failed trajectories contribute more decisions.

| Decision quantity | Mean | Minimum | P25 | Median | P75 | P95 | P99 | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Score S | .029560 | 0 | .011438 | .012963 | .013889 | .135684 | .500000 | .500000 |
| Threshold | .600000 | .600000 | .600000 | .600000 | .600000 | .600000 | .600000 | .600000 |
| Visible mass M | 10.582854 | 6.882063 | 10.125000 | 10.125000 | 10.207773 | 12.558309 | 19.923786 | 19.923786 |
| Eligible candidate count | 27.338254 | 17 | 28 | 28 | 28 | 28 | 28 | 28 |
| Positive-disruption cells per decision | 2.576276 | 0 | 3 | 3 | 3 | 3 | 3 | 7 |

There are **633,318 candidate-cell records** across the 23,166 decisions:

| Candidate quantity | Mean | Minimum | Median | P95 | P99 | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Occupancy disagreement q | .469244 | .092823 | .500000 | .500000 | .500000 | .500000 |
| Predicted visibility V | .387108 | .000200 | .250000 | 1.000000 | 1.000000 | 1.000000 |
| Normalized disruption D | .004380 | 0 | 0 | .014815 | .017094 | 1.000000 |
| Absolute counterfactual route-cost difference | .585080 | 0 | 0 | 2 | 2 | 153 |
| Contribution V*q*D | .001081 | 0 | 0 | .003704 | .007937 | .500000 |

**573,636 candidate disruptions (90.58%) are zero.** Among the 59,682 positive
disruptions, the median is .014815, P95 .027778, P99 .993056 and maximum 1.
Thus most positive effects are small detour-length differences after normalization;
large no-route/sentinel differences exist but are uncommon. There are 2,196
decisions (9.48%) with every disruption zero, hence score zero despite positive
visibility and disagreement. Such counterfactual insensitivity does not establish
that sensing would have no actual task value: single-cell route changes can miss
joint changes or share the same no-route cost in both states.

| Failed condition or capacity diagnostic | Decisions | Interpretation |
| --- | ---: | --- |
| S <= threshold | 23,166 / 23,166 | Sole failed request condition on every decision |
| Visible mass < .25 | 0 / 23,166 | Gate always passes, including the occluded family |
| Empty candidate set | 0 / 23,166 | Candidate availability is not the trigger blocker |
| Request made | 0 / 23,166 | No request was hidden by the budget controller |
| Request denied | 0 / 23,166 | No denial-induced failure to refresh |
| Remaining capacity zero | 3,861 / 23,166 | Exactly the cap-1 decisions; requests are still computed |

Removing visibility *weighting* in arithmetic on these same recorded states gives
`sum(q_i*D_i)` with mean .056448 and maximum .622371. It exceeds .6 at only
24 decisions (0.104%). Removing disruption weighting gives `sum(V_i*q_i)` with
minimum .925888, mean 4.753469 and maximum 5.077760: above .6 on every recorded
decision. These are component-sum diagnostics, not simulated ablation trajectories
or estimates of resulting success. Nothing was changed online.

The evidence identifies a **threshold/normalized-disruption interaction** as the
main bottleneck. Visibility weighting further suppresses scores, but its mass gate
never blocks a request. Disagreement remains near .5 for most candidates and is
not uniformly negligible. Normalization alone is not a causal explanation of
task failure: a different threshold, changed estimator or new trajectory would
require a separate reviewed experiment, and none is evaluated or selected here.

## Family, sensor and cap differences

Each family contributes 120 episodes (ten environments, six caps, two sensors).
Every row below has zero requests and a .6 threshold.

| Family | Decisions | Mean score | Median score | P95 score | Maximum score | Mean visible mass | Zero-score decisions |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| budget | 4,212 | .017631 | .012963 | .014957 | .500000 | 10.255005 | 432 |
| critical | 1,986 | .059898 | .011582 | .500000 | .500000 | 10.332287 | 432 |
| detour | 4,164 | .017715 | .012963 | .014957 | .500000 | 10.918929 | 12 |
| irrelevant | 1,476 | .080910 | .012892 | .500000 | .500000 | 12.240692 | 12 |
| occluded | 4,800 | .024398 | .011582 | .135684 | .455556 | 10.045605 | 864 |
| outdated | 4,164 | .017715 | .012963 | .014957 | .500000 | 10.918929 | 12 |
| reopen | 2,364 | .045478 | .011438 | .256410 | .500000 | 10.249321 | 432 |

| Sensor noise | Episodes | Decisions | Mean score | Median | P95 | Maximum | Mean visible mass | Zero-score decisions |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 420 | 11,238 | .032080 | .012963 | .135684 | .500000 | 10.699237 | 216 |
| .05 | 420 | 11,928 | .027186 | .012153 | .135684 | .500000 | 10.473205 | 1,980 |

These sensor differences describe changed initial noisy memories and subsequent
paths, not an isolated causal estimate of noise's effect on a particular score
component. No subsequent observation is granted in either condition.

Each cap (1, 2, 4, 8, 16, unlimited) contributes **140 episodes and 3,861
decisions**, with identical score distributions: mean .029560, median .012963,
P95 .135684, maximum .5, and 366 zero-score decisions. Saved positions, candidate
components, scores and visible masses match across all six caps in every one of
the 140 environment/sensor groups. A zero budget price and no later observations
explain this cap invariance. The saved assessment diagnostic additionally reports
840/840 trajectories and scientific metric pairs matching Static; its raw inputs
were included in this review's complete checksum/identity audit.

## Comparison with the other eight tuning candidates

Only existing **development tuning** records are used in this section. Each
candidate has 105 episodes: 35 environments at caps 2/4/8, noiseless sensing.
The table recomputes request and observation totals from the locked compact
`results/phase1_4b/episodes.jsonl` and agrees with the saved candidate scores.
The common score definition is unchanged across all nine candidates; only the
base threshold and budget-price term vary. Base thresholds are `1.5*theta_D`;
positive lambda additionally raises the threshold by `lambda*h/max(1,b)`.

| Candidate | theta_D | lambda | Base threshold | Requests | Denied | Post-initial grants | Episodes with later grants | Contact-free /105 | Goal /105 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | .025 | 0 | .0375 | 139 | 31 | 108 | 51 | 36 | 42 |
| 1 | .025 | .1 | .0375 | 90 | 1 | 89 | 47 | 38 | 44 |
| 2 | .025 | .4 | .0375 | 46 | 0 | 46 | 45 | 39 | 45 |
| 3 | .1 | 0 | .15 | 48 | 1 | 47 | 45 | 39 | 45 |
| 4 (default) | .1 | .1 | .15 | 47 | 0 | 47 | 45 | 39 | 45 |
| 5 | .1 | .4 | .15 | 30 | 0 | 30 | 30 | 39 | 45 |
| 6 (locked) | .4 | 0 | .6 | 0 | 0 | 0 | 0 | 39 | 45 |
| 7 | .4 | .1 | .6 | 0 | 0 | 0 | 0 | 39 | 45 |
| 8 | .4 | .4 | .6 | 0 | 0 | 0 | 0 | 39 | 45 |

The compact records demonstrate that the implementation could request observations
under other preregistered settings during tuning. They do not show that those
settings would generalize or justify changing the lock. Candidates 2 through 8
have equal aggregate primary/goal scores. Candidates 6/7/8 also tie on observation
count and elapsed steps; the declared lexicographic tie-break selects candidate 6.
The observation-count criterion favors the inactive candidates over equally
successful, more frequently sensing candidates. This explains the development
selection incentive; it does not prove that the information they acquired was
useless in each paired environment.

**Component-level tuning comparison is limited by unavailable raw traces.**
The Phase 1.4B inventory describes 3,780 full files under
`/Users/masahir0/Desktop/humanoid-spatial-memory/results/raw/phase1_4b_tuning`.
That directory is absent locally; only Phase 1.4C raw traces are available here.
Compact tuning metrics contain totals and feasibility aggregates, not per-decision
S, D, q or visibility-mass distributions. Therefore this review cannot verify or
compare those distributions across the nine tuning trajectories, or independently
rehash the old tuning raw files. The unchanged inventory and prior independent
verification report are provenance evidence, not substitutes for the missing data.
No assessment score was replayed through alternative tuning thresholds, and no
new parameter ranking was made. Recover the original tuning archive for any
further component comparison; do not regenerate episodes for this review.

## Expected informativeness of the six unchanged ablations

The frozen matrix is 70 environments x caps 4/8 x two sensor conditions x six
ablations = **1,680 new executions**, all still pending review. The distinctions
below separate recorded-state arithmetic, source-level deductions and unknown
trajectory/outcome effects.

| Frozen ablation | Evidence available now | Expected information and limitation |
| --- | --- | --- |
| No route disruption: D=1 | `sum(V*q)` exceeds .6 on every saved baseline decision, including step 1 in every episode | Strong request-activation diagnostic. At caps 4/8 the first request would have capacity. Subsequent memories, sensing counts, trajectories and success require actual execution; later saved-state crossings cannot be counted as future grants. |
| No visibility: V=1 in score and mass | `sum(q*D)` exceeds .6 on 24 saved decisions, all at step 1 in four noisy environment/family cases repeated across six caps | Limited possible behavioral contrast: eight of the 280 cap4/8 episode initial decisions would cross. The cases are seed 20000 in budget, critical, occluded and reopen, all noise .05. Remaining trajectories and outcomes are unknown. |
| Fixed rate: r=.05 | No later refresh means flips=0 and exposure=0, so the adaptive prior rate remains .3/6, mathematically .05 | Expected inactive control. Direct arithmetic comparison of stored belief probabilities to the fixed-rate formula differs by at most 1.11e-16. This is far below the score-to-threshold margin; the history adaptation cannot start changing rates without a repeat observation. No ablation run was made. |
| Exclude unknown candidates | Removing a subset of nonnegative contributions cannot raise S; visible mass also cannot rise | By induction along the baseline trajectory it cannot initiate a request. Expect unchanged motion/scientific outcomes, with potentially different diagnostics and runtime. It does not identify unknown cells' importance under an actively sensing policy. |
| No budget threshold: lambda=0 | The locked lambda already equals zero | Algebraically redundant with the selected policy. Useful only as a negative integrity control; no claim about nonzero budget prices follows. |
| No alternative candidates: restrict to current route | This also removes only nonnegative score terms and cannot raise visible mass | Cannot initiate sensing from these baseline states, so the unchanged trajectory remains consistent by induction. A null comparison would not establish that off-route candidates are unimportant under other settings. |

The eight no-visibility crossings are **stored-state algebra**, not eight executed
ablations or predicted successful episodes. Likewise, request activation with
D=1 does not validate task-aware sensing: it removes the proposed route signal
and can expose a substantially different observation rate. The four inactive
controls still incur different computations; motion/metric equivalence does not
imply identical scheduler runtime. Preserve all six rows if the full preregistered
matrix is approved; do not silently drop redundant rows or retune to make them active.

## Interruption, recovery and source review

All completed traces share run ID
`e859042f79b77b6d40369487b6a79751921c4590f48908079507d1c5b4c41e28`.
Its normalized source-manifest hash is
`5fd82dd249ccb36b4effa0140592f5d5fe72b31acfb24f79bf66b249b684702e`.
The local `run.json` equals the published run contract, and its identity hashes
to that run ID. The recorded source commit is the tuning parent with a dirty
working tree, reflecting implementation before the final assessment commit;
the 33 explicit source hashes match the completed assessment checkout.

| Session | Already complete | New executions | Complete afterwards | Recovery actions |
| --- | ---: | ---: | ---: | ---: |
| `session-00000-00002.json` | 0 | 2 | 2 | 0 |
| `session-00002-00002.json` | 2 | 0 | 2 | 0 |
| `session-00002-13440.json` | 2 | 13,438 | 13,440 | 0 |

The chain is contiguous and sums to 13,440 new executions; the zero-new session
is consistent with checkpoint reuse. Staging is empty, no quarantine files or
recovery logs are present, and no duplicate or conflicting complete bundle was
found. There is no stored evidence of partial-checkpoint recovery in this run.
The existing POSIX `fcntl` lease and atomic checkpoint implementation remain
unchanged; this read-only review did not acquire a writer lease or weaken it.

`rejected-initialization-run.json` preserves a distinct earlier contract, run ID
`baafd0f0f05ab071e68e2d7335a3eb9dd20443793b96e7b82d5f2529ec32fd22`.
Only `src/spatial_memory/assessment_spec.py` differs between its source manifest
and the completed run's manifest. No completed trace carries that rejected ID.
This is consistent with the earlier baseline-parameter admission correction,
which now passes `None` to the six historical methods. The file is a run contract,
not an exception traceback or a complete event journal; it cannot independently
prove the precise failure stage or exclude all uncommitted partial computation.
Session summaries and inventories support absence of duplicated *completed*
executions; they are not a tamper-proof proof that no unlogged attempt occurred.
There is no evidence of parameter alteration in completed records.

## Validation, limits and review boundary

The fresh saved-data audit completed successfully with assertions for every raw
checksum, job/run identity, lock-referenced artifact, observation ledger and
disruption-visible score/trigger calculation described above. Git review confirms
this follow-up changes only this report. No new test suite or episode replay was
needed for a documentation-only change; the existing assessment test record
reports 192 passing tests, which are prior results, not newly executed tests.

Distributions reuse six deterministic caps and related layouts (37 global layout
clusters), and many candidate rays share cells and histories. No significance
tests, new inferential intervals or independence claims are made. Predicted
visibility on unsensed decisions has no newly observed revealability label;
positive visible mass is not evidence of calibrated feasibility or actual useful
information. Missing tuning raw traces prevent the requested full cross-candidate
component comparison. Stored-state algebra cannot identify post-observation
outcomes, joint-cell route effects, physical safety or unseen-family behavior.

The locked policy remains effectively Static in the completed assessment. Its
negative result and selection history are preserved. This report recommends no
parameter revision, no new method claim, and no held-out or MuJoCo evaluation.
Stop here for review before any Phase 1.4D execution.
