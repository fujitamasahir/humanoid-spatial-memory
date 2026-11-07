# Phase 1.2 baseline review and preregistered implementation definitions

Reviewed before implementation, 2026-11-06. These are **simplified conceptual
observation-scheduling baselines**, not faithful reproductions of the papers below,
not novel mapping algorithms, and not the proposed task-aware verification method.
The existing research plan/protocol, Phase 1/1.1 validation reports, all simulator,
sensor, memory, planner, evaluator and visualization modules, tests/configuration,
and Phase 1.1 episode results were reviewed. Static freezes its initial map;
periodic refreshes every two steps. Earlier results show repeated blocked requests,
a 25-step periodic corridor traversal, and unequal map-error sampling horizons.

## Verified literature

Metadata and concepts checked against primary papers or author/institution pages.
URLs are direct sources, not inferred or invented citations. Access was available,
although some direct PDF fetches timed out or returned unsupported content types;
those cases are explicitly qualified below. No reference supplies the exact rules
implemented here.

| Work | Verified metadata and source | Assumptions and applicable concept | Reproduction boundary |
| --- | --- | --- | --- |
| Using occupancy grids for mobile robot perception and navigation | Alberto Elfes, 1989, Computer 22(6):46–57. [Paper](https://www.cs.cmu.edu/~motionplanning/papers/sbp_papers/integrated4/elfes_occup_grids.pdf), [DOI](https://doi.org/10.1109/2.30720) | Probabilistic cell states, sensor models and incremental Bayesian estimation; a foundation for representing uncertainty under partial observations. | Repository planner still receives ternary last-write memory, not a reproduced Bayesian occupancy mapper. Paper search text was accessible; direct PDF open timed out. |
| Temporal Occupancy Grids: a Method for Classifying the Spatio-Temporal Properties of the Environment | Daniel Arbuckle, Andrew Howard, Maja J. Mataric, 2002, IROS:409–414. [Author paper](https://citeseerx.ist.psu.edu/document?doi=15041b9b405bffa7c7344340efbc2eb4cd4975b0&repid=rep1&type=pdf), [author publication record](https://robotics.usc.edu/~maja/mataric-cv-sep2020.pdf) | Multiple temporal windows distinguish occupancy patterns; requires repeated calibrated measurements. Temporal history can inform cell dynamics without semantic labels. | No multi-timescale classifier or persistence label is implemented. |
| FreMEn: Frequency Map Enhancement for Long-Term Mobile Robot Autonomy in Changing Environments | Tomas Krajnik, Jaime Pulido Fentanes, Joao M. Santos, Tom Duckett, 2017, IEEE Transactions on Robotics 33(4):964–977. [Author publication page](https://fel.cvut.cz/cs/fakulta/lide/698-tomas-krajnik/publikace), [DOI](https://doi.org/10.1109/TRO.2017.2665664), [author manuscript](https://raw.githubusercontent.com/wiki/gestom/fremen/papers/fremen_2017_TRO.pdf) | Uses temporal frequency structure, assuming some processes are periodic; long histories support prediction of changing states. | Short episodes do not support spectral fitting. No future-state predictor or FreMEn reproduction. Manuscript search text and author metadata were accessible; direct PDF open unsupported. |
| A physics perspective on lidar data assimilation for mobile robots | Yann Berquin, Andreas Zell, 2022, Robotica 40:862–887. [Publisher paper](https://www.cambridge.org/core/services/aop-cambridge-core/content/view/C8F53EC66CB56B9282E744CE360F005A/S0263574721000850a.pdf/physics_perspective_on_lidar_data_assimilation_for_mobile_robots.pdf), [DOI](https://doi.org/10.1017/S0263574721000850) | Section 4.5 discounts past lidar evidence exponentially: uncertainty can grow without new observations. It uses a mean-free-path likelihood and lidar ray statistics. | Our binary confidence relaxation is only conceptually related; it is not that likelihood or an implementation of its equations 28–30. |
| Revisiting Active Perception | Ruzena Bajcsy, Yiannis Aloimonos, John K. Tsotsos, 2016 preprint version. [Author preprint](https://arxiv.org/abs/1603.02729), [DOI](https://doi.org/10.48550/arXiv.1603.02729) | Reviews control of sensing as part of perception. Choosing when to sense is a policy decision distinct from state estimation. | Broad framing, not evidence for our specific entropy threshold or a claim to reproduce an active-perception system. |

This review covers memory decay, temporal mapping and active sensing. The
uncertainty threshold below is a deliberately explicit engineering baseline;
none of the reviewed papers validates that threshold. Strong published-method
reproductions remain future research work. No unsupported literature claim is
needed to call these stronger controls than static/fixed-period scheduling.

## Definitions frozen before running Phase 1.2 experiments

All methods use the same initial observation, last-write ternary memory, A*,
unknown handling, sensor, world realization, time convention and deadline.
Schedules use current pose and the public sensor radius to form a Euclidean disk
clipped to map dimensions. This is a *potential* sensing footprint: true occlusion
is never queried. Only previously observed cells in that disk enter the score;
unknown cells are excluded, not assigned a fictitious age. There is no route,
goal, action feedback, hidden dynamics, semantic identity or value-of-information
input to either adaptive policy. Pose locality is generic sensing feasibility,
not path relevance. Do not call it the proposed task-aware method.

### A. Local cell-age threshold (`age`)

Store last-observed step L_i for known cells, with -1 meaning never observed.
Only actually visible ternary observations update timestamps. At time t compute
a_i=t-L_i. Request sensing when at least half of the known cells in the potential
footprint have a_i >= 4 steps. No known cells means no request. A denied request
does not reset timestamps. This is not a global timer: cells seen from earlier
poses retain distinct timestamps, footprint membership changes with motion, and
occluded cells remain stale. In a stationary, fully visible, uniformly timestamped
map it does reduce to a four-step interval; that limiting case must be reported.
Four steps is twice the existing two-step periodic interval, selected as a simple
lower-sensing comparator, not selected for outcome performance.

### B. History-adapted confidence decay with entropy trigger (`uncertainty`)

Estimator: per known cell count observed flips F_i and exposure E_i, the sum of
step gaps between consecutive *visible* observations. Estimate a rate
lambda_i=clip((0.3+F_i)/(6+E_i), 0.01, 0.35) per step. Initial rate is 0.05.
These pseudocounts, exposure and bounds are configured modeling assumptions,
not true change rates. Undetected even-numbered changes and noise bias this proxy.
Each visible sample resets p_i to 0.95 for occupied or 0.05 for free. Between
samples, use p_i(t)=0.5+(p_i(L_i)-0.5)*exp(-2*lambda_i*(t-L_i)).
This is symmetric binary-state relaxation; entropy H_i=-p_i log2(p_i)
-(1-p_i)log2(1-p_i) increases toward one without new observations. Rates are
updated only from observed binary sequences. It is not a calibrated posterior:
there is no full HMM inference, Bayesian measurement fusion, or persistence model.
The confidence 0.95 is an assumed model floor even for the noiseless sensor.
Planner memory remains the last observed binary state; no automatic map erasure.

Decision: request sensing when mean entropy over known footprint cells >= 0.75
bits. No known cells means no request. At the initial rate a uniform cell crosses
this around step 5, in the same rough range as the age comparator; stable repeated
samples lower rate, while observed flips raise it. No outcome tuning is planned.
At equal age, different binary histories yield different uncertainty/decisions;
tests must demonstrate this. With identical homogeneous histories entropy can
reduce to an age threshold, but the implemented history-adapted rate prevents a
general equivalence. Estimation continues when sensing is denied by budget.

## Budget and evaluation plan

Four settings: unlimited observations and maximum total counts 3, 5, 8. Initial
sensing consumes one; the remaining 2/4/7 calls span severe/intermediate/loose caps
relative to Phase 1.1 periodic's 5–7 calls in new families and 13 in the corridor.
Budget gating is shared: requests without capacity are denied, with no sensor
call or memory/timestamp/confidence reset. No observations are free. Sensing adds
cost but consumes no simulation time. Unit cost remains 1.5 in all settings;
changing that scalar alone cannot affect these cost-unaware policies.

Use the five Phase 1.1 families plus the original corridor development scenario,
seeds 7/19/31, 40 steps, existing sensor radius 3/occlusion on/noise zero,
periodic interval 2, all four methods in every setting. Preserve previous files.
Report every requested metric, final and cumulative errors separately, successful
observation counts (null if no successes), terminal behavior and budget-denial
counts. Outcomes are developmental, not statistically significant findings.
The held-out suite remains untouched and unexecuted.
