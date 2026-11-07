# Phase 1.5 research review

Design review, 2026-11-07. This document, the [method design](phase1_5_method_design.md)
and [proposed protocol](phase1_5_experimental_protocol.md) are documentation only.
No new policy, layout, tuning run or experiment was implemented or executed.
Phase 1.4 remains a negative result. The recommendation below is a research
hypothesis, not a validated method. The protocol is provisional until its topology,
power, resource and model-interface review gates pass.

## Evidence reviewed

The local record comprises the Phase 1.3 [design](phase1_3_task_aware_design.md),
[plan](phase1_3_experiment_plan.md), [validation](phase1_3_validation.md) and
[diagnostic](phase1_3_diagnostic_review.md); Phase 1.4
[literature review](phase1_4_literature_review.md),
[prior-work comparison](phase1_4_prior_work_comparison.md),
[frozen protocol](phase1_4_experimental_protocol.md),
[implementation validation](phase1_4a_validation.md),
[tuning validation](phase1_4b_validation.md),
[assessment validation](phase1_4c_validation.md),
[pre-ablation diagnostic](phase1_4d_pre_diagnostic.md) and
[ablation validation](phase1_4d_validation.md).
The numbers below summarize those stored reports and their linked artifacts;
this design review does not claim a new replay of their trace inventories.

| Supported observation | What it establishes | What it does not establish |
| --- | --- | --- |
| Phase 1.3 reference suite: Periodic completed 28/28 goals, 26 contact-free, with 12 observations; Static completed 12/28 goals, 10 contact-free, with one observation. | Fresh sensing can matter in these scenarios. | Periodic timing is optimal, or more sensing always helps. |
| Phase 1.3 uncertainty and age triggers completed 19/28 and 21/28 goals, respectively. Corridor results depended on removal timing; age triggers could spend calls behind occlusion. | Staleness and uncertainty alone did not reliably express task relevance. | A particular decision-value estimator would solve those cases. |
| Phase 1.4 tuning ran 3,780 episodes on 35 environments but only 22 layout clusters. The selected disruption-visible candidate made no additional request in its 105 selected-candidate executions. | Inactivity was already visible in development. | The assessment alone caused inactivity, or active alternatives were comprehensively disproved. |
| Phase 1.4 assessment ran 13,440 executions on 70 environments, with 37 layout clusters. All 840 disruption-visible episodes matched Static scientifically. | The locked method did not test useful adaptive sensing in this assessment. | Equivalence between every possible task-aware scheduler and Static. |
| Across 23,166 disruption-visible decisions, maximum score was .5 and minimum threshold .6000000000000001; predicted visible mass always exceeded its .25 gate. | The score test prevented all requests. Visibility-mass gating alone was not the binding gate. | Correctly calibrated visibility, or a globally valid mathematical upper bound of .5 for other environments. |
| About 90.58% of candidate route-disruption components were zero; mean occupancy-disagreement probability was about .469. | Disagreement was not uniformly tiny; route sensitivity and its scale deserve scrutiny. | Single-cell counterfactual blindness was the unique causal explanation. |
| No-route-disruption activated all 280 ablation episodes and matched Periodic-1 in all 280 scientific traces. Mean calls rose from 1 to 6; contact-free completion changed from 110/280 to 109/280. | Removing that factor caused sensing, but front-loaded sensing did not improve aggregate performance. | Route awareness is generally harmful, or additional sensing is generally useless. |
| No-visibility activated eight repeated cap/noise settings from four environments in one layout cluster. Contact-free completion rose from 110/280 to 114/280. | That intervention changed a few decisions and outcomes. | General benefit from ignoring visibility; eight settings are not eight independent successes. |
| The other four ablations produced 1,120 exact Static trajectories. | Those frozen comparisons were behaviorally inactive. | Evidence that their underlying conceptual components never matter. |

The original confirmatory contrast remains disruption-visible minus route-weighted
contact-free completion at cap4/noise0: **-1.43 percentage points**, interval
**[-10.05, 8.10]**. This inconclusive interval is not an equivalence test.
The no-route-disruption diagnostic contrast was -.36 points, interval
[-6.24, 5.49]; its 23 gains and 24 losses show heterogeneous effects despite a
small aggregate. No-visibility's +1.43-point interval [0, 4.82] is exploratory
and concentrated in one layout cluster.

Quota-periodic and random-quota controls exceeded disruption-visible in several
descriptive summaries. At cap4/noise0, their contact-free rates were 54.29% and
52.29%, with mean calls 2.56 and 2.82; route-weighted was 42.86% with four calls,
and disruption-visible 41.43% with one. Equal caps did **not** equalize actual
sensing. These results motivate timing controls; they do not identify the causal
value of task awareness.

## Mechanistic interpretation and limits

The most direct explanation of zero sensing is an unfavorable interaction of
score scale and threshold, strongly influenced by route-disruption estimation.
Dividing route effects by grid area gave the score units unrelated to a navigation
loss, while the cost-dependent threshold retained another scale. No-disruption
established that this factor suppressed activation, but simultaneously changed
sensing into Periodic-1. It did not isolate a beneficial timing rule. Visibility
affected the score in rare cases even though the separate visible-mass gate
always passed. Removing visibility is therefore not evidence that visibility
modeling should be abandoned.

Single-cell interventions can miss coordinated occupancy changes, but the stored
trace analysis does not prove that a joint model would improve navigation. The
fixed-rate estimate (.3/6=.05 before refresh), zero selected budget price, and
subset restrictions explain why several frozen ablations offered no active
contrast. Lexicographic selection could prefer an inactive candidate among ties.
That is a selection-design weakness, not evidence for an optimal zero-sensing
policy.

The development archive's compact records remain available, but its original
compressed tuning traces were unavailable at their recorded external path during
the pre-ablation review. Full component-distribution comparisons across all nine
tuning candidates cannot be reconstructed from compact summaries. Do not invent
them or regenerate those episodes. Repeated caps, sensors, seeds within templates
and random-scheduler repetitions do not add independent topology samples.

The Phase 1.4D report records successful integrity checks, all 1,680 episodes,
independent reconstruction, preserved 2,212 historical regression records and
204 passing tests. Its execution took 267.314 seconds and independent verification
533.465 seconds, storing 18,719,485 compressed trace bytes. These are historical
facts, not runtime estimates for the substantially more expensive proposed model.
No evidence in that report establishes altered frozen parameters or duplicated
scientific execution. This review adds no new forensic certification.

## Verified prior art and overlap

Primary sources were inspected for this design on 2026-11-07. This is a targeted
comparison, not an exhaustive systematic novelty search. No absence-of-prior-art
claim follows from it. Code, licenses, weights and reproducibility of the cited
systems have not been independently audited here.

| Work and status | Relevant established idea | Consequence for Phase 1.5 |
| --- | --- | --- |
| Krishna, Hu and Jayaraman, ICLR 2025, [The Value of Sensory Information to a Robot](https://proceedings.iclr.cc/paper_files/paper/2025/file/e1126028d9f1f69c13571ec462084d31-Paper-Conference.pdf) | Value/regret of sensing relative to a controller; mixed-loop execution. Its main formulation uses perfect instantaneous state observations. | Decision-aware sensing is prior art. Local, noisy, occluded observation estimation needs an explicit adaptation, not a claim to have invented sensory value. |
| Krale, Simão and Jansen, ICAPS 2023, [Act-Then-Measure](https://tdsimao.github.io/assets/pdf/Krale2023act.pdf) | Costed optional measurement in ACNO-MDPs and an ATM/QMDP approximation. Complete noiseless measurement differs from the proposed sensor. | Costed measuring and decision-value approximations are established. A partial-sensor grid adaptation is not a faithful reproduction without an interface argument. |
| Krale, Simão, Tumova and Jansen, AAAI 2024, [Robust Active Measuring under Model Uncertainty](https://doi.org/10.1609/aaai.v38i19.30122) | Robust measuring under transition-model uncertainty; uncertainty need not monotonically increase measurement. | A conservative trigger can also collapse into inactivity. Robustness claims require model-error experiments, not just a pessimistic threshold. |
| Silver and Veness, NeurIPS 2010, [Monte-Carlo Planning in Large POMDPs](https://proceedings.neurips.cc/paper_files/paper/2010/file/edfbe1afcf9246bb0d40eb4d8027d90f-Paper.pdf) | Particle beliefs and online Monte Carlo planning with a generative model. | Joint belief scenarios and sampled planning are established. Using evaluator truth as the model would invalidate the proposed comparison. |
| Somani, Ye, Hsu and Lee, NeurIPS 2013, [DESPOT](https://papers.nips.cc/paper_files/paper/2013/file/c2aee86157b4a40b78132f1e71a9e6f1-Paper.pdf) | Scenario-based sparse belief trees and regularized online POMDP planning. | Multi-cell counterfactual planning is not novel merely because it samples complete maps. Finite short-lookahead approximations inherit neither exact optimality nor published guarantees. |
| Yang et al., October 2026 preprint, [ALONE](https://arxiv.org/html/2610.11591v1) | Bayesian spatial prediction/correction and query-relevant perception under intermittent sensing, evaluated for aerial navigation. | Closely overlaps belief-based selective sensing. The Phase 1.4 conceptual query gate was not an ALONE reproduction. Dynamic stale-memory evaluation and explicit cost comparisons are possible distinctions, not verified novelty. |
| Vélez et al., IJCAI 2011, [Active Exploration for Robust Object Detection](https://ijcai.org/proceedings/2011/458) | Task-linked active viewpoints trading information and motion. | Task-aware active perception predates this project. The publisher abstract was verified; this review does not assert a full implementation comparison. |

The older Phase 1.4 review also discusses information-gathering and occupancy
prediction literature. Information gain, occupancy prediction and task loss are
different objectives; success in one does not establish the others. A credible
contribution here would be a reproducible, calibrated, cost-controlled test of a
clearly bounded approximation under changing occupancy and topology separation.
That contribution remains prospective.

## Candidate comparison and recommendation

| Direction | Scientific attraction | Principal risk | Estimated engineering scope, not measured |
| --- | --- | --- | --- |
| A: decision-aware expected value of sample information (EVSI) | Scores the action improvement obtainable from the actual partial sensor, in common loss units; admits analytic null/positive checks. | Biased belief or proxy loss makes a precise value estimate misleading; nested inference is costly. | Roughly 3–5 engineer-weeks for model/controller, estimator, fixtures and provenance, before evaluation. |
| B: multi-cell counterfactual route sensitivity | Addresses correlated changes and single-cell blindness directly. | Larger route changes need not change the best action; grouping, visibility and normalization remain arbitrary. | Roughly 1–2 weeks after a shared joint model exists; model work itself overlaps A. |
| C: budget-aware scheduling | Accounts for the opportunity cost of spending a call early. | Full belief-and-budget dynamic programming is expensive; heuristic shadow prices can dominate useful sensing. | Roughly 1 additional week for a declared approximation; exact long-horizon optimization is outside this proposal. |

Recommend **A as the primary direction**, with a joint multi-cell representation
as necessary model infrastructure and **C as a separately labeled secondary
extension**. Compare B as an explicit heuristic; do not describe adding more cells
to Phase 1.4's score as sufficient novelty. A is preferred because its sensor and
decision dependence can be falsified before navigation outcomes are examined.
C alone cannot fix a zero or mis-scaled value score. B alone lacks a principled
observation-cost comparison. Neither should replace the primary method after
assessment results arrive.

This recommendation changes the common navigation decision model for Phase 1.5;
it does not modify Phase 1.4. All Phase 1.5 scheduler rows must share that new
controller and belief inputs. Legacy scheduler ports then control timing, not
reproduce the old complete navigation stack. This distinction is mandatory in
future tables.

For a humanoid, the eventual decision loss must include collision severity,
balance, traversability, action duration, sensor latency and energy. A grid with
known pose, zero latency and no locomotion instability establishes none of these.
Belief-conditioned action value is compatible in principle with a MuJoCo/Unitree
G1 controller, but transfer requires a new dynamics, sensing and safety study.
No robot integration or physical safety claim is authorized by this design.

## Decisions for research review

Approve or reject the common-controller change, joint belief approximation,
loss/cost units, power/resource proposal and comparator fidelity before coding.
The protocol's conceptual topology audit rejects seed-only independence; an
actual generated-layout audit is still required under separate authorization.
The proposed 160 assessment clusters do not guarantee power for a five-point
gain. A failed feasibility, activation, calibration or independence gate means
stop and document the failure, not tune on assessment. Research review, rather
than implementation, is the next step.
