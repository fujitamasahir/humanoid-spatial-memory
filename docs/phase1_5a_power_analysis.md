# Phase 1.5A power and precision analysis

2026-11-07. **Analytic scenario calculations, not assessment results.** No
Phase 1.4 outcome was used to estimate variance or select a new sample size.
Inputs below are hypothetical. Reproduce using
[audit_phase1_5a.py](../scripts/audit_phase1_5a.py); full precision values are in
[mathematical_audit.json](../results/phase1_5a/mathematical_audit.json).

## Paired binary derivation

For one paired environment let D=Y_A-Y_control in {-1,0,1}, gain probability p+,
loss probability p-, effect delta=p+-p-, discordance q=p++p-. Then
`Var(D)=q-delta^2`, requiring q>=|delta|. With n independent topology clusters
and cluster-level variance v, SE approximately sqrt(v/n). A two-sided alpha=.05
normal approximation gives

```
halfwidth = z_.975 * sqrt(v/n)
power = 1-Phi(z_.975-delta*sqrt(n/v))
        + Phi(-z_.975-delta*sqrt(n/v))
n_80 approximately (z_.975+z_.80)^2*v/delta^2.
```

Counts below round upwards to multiples of four for balanced mechanisms. They
are planning approximations without exact discrete or small-cluster coverage
guarantees. The generic variance/precision relationship and need to plan per
stratum agree with [NIST's sample-size guidance](https://www.itl.nist.gov/div898/handbook/ppc/section3/ppc333.htm);
the paired variance and tables here are our deductions, not NIST's paired-design
formula. At very low discordance, exact paired/binomial calculations would be
needed before a confirmatory lock.

## What 160 clusters can support

Illustration for delta=.05, one independent paired outcome per cluster:

| Discordance q | Variance q-.05^2 | Approximate 95% halfwidth, percentage points | Power, n=160 | n for80% | n for90% |
| ---: | ---: | ---: | ---: | ---: | ---: |
| .05 | .0475 | 3.38 | 82.7% | 152 | 200 |
| .10 | .0975 | 4.84 | 52.6% | 308 | 412 |
| .20 | .1975 | 6.89 | 29.6% | 624 | 832 |
| .40 | .3975 | 9.77 | 17.1% | 1,248 | 1,672 |
| .80 | .7975 | 13.84 | 10.9% | 2,504 | 3,352 |

160 can be credible for precision estimation, or for superiority under unusually
low discordance/variance. It cannot generically support a well-powered five-point
superiority claim. An interval containing zero is not equivalence. The original
rough628 estimate ignored delta^2;624 is the corresponding paired approximation
at q=.2, while628 still applies to the rounded variance .2 scenario.

| q | True gain3 points: n80 | True gain5 points: n80 | True gain10 points: n80 |
| ---: | ---: | ---: | ---: |
| .10 | 868 | 308 | 72 |
| .20 | 1,740 | 624 | 152 |
| .40 | 3,484 | 1,248 | 308 |
| .80 | 6,972 | 2,504 | 624 |

These calculations do not include the chance of meeting an observation-count
noninferiority criterion or a second timing endpoint. Moreover v0.1 also requires
the **point estimate** to be at least .05. At a true effect exactly .05, an
approximately unbiased symmetric estimator exceeds that boundary only about
half the time, even with large n. Superiority power in the tables therefore
overstates power for its composite 'practical success' declaration. Requiring
a lower confidence endpoint above .05 would test a different, stronger claim
and needs a design alternative strictly above .05 for power planning.

For the .25-call noninferiority margin, an illustrative true call difference0
and cluster SD1 imply about `(1.96+.84)^2/.25^2=126` clusters; SD2 implies about
503. This endpoint can be the binding gate independently of completion power.
No call variance is estimated from assessment here.

## Repeats, weighting and topology dependence

The primary cluster outcome should average the two paired dynamics schedules,
after random-control repetitions are averaged within schedule. If each paired
schedule has variance v and within-cluster correlation rho, their mean has
variance `v*(1+rho)/2`. For v=.2 and rho0/.5/1, this is .1/.15/.2, not necessarily
.1. At delta=.05, corresponding n80 is approximately316/472/628. Five random
schedules reduce only the random-control component, not topology or world noise.
Cross-sensor repetition does not increase n for the single primary sensor
condition. Any pooled sensor analysis needs its covariance, not fourfold n.

For four mechanisms with fixed weights w_h=1/4 and n_h independent clusters,
`Var(weighted_effect)=sum_h w_h^2*v_h/n_h`. Equal allocation gives
`mean(v_h)/n` when n_h=n/4. Unequal accepted counts reduce precision and must not
be hidden by counting raw seeds. Correlation between mechanisms through shared
lineage is resolved by unioning the global cluster, not independent per-family
bootstraps. If cross-family clusters remain, use their joint covariance rather
than the simple independent-stratum formula.

| Cluster-level variance v | Halfwidth at160, points | Power for5 points | n80 |
| ---: | ---: | ---: | ---: |
| .025 | 2.45 | 97.9% | 80 |
| .05 | 3.46 | 80.7% | 160 |
| .10 | 4.90 | 51.6% | 316 |
| .20 | 6.93 | 29.3% | 628 |
| .40 | 9.80 | 17.0% | 1,256 |
| .80 | 13.86 | 10.9% | 2,512 |

If an approximate dependence design effect1.5 remains, multiply required
clusters by1.5; do not assert160 certified clusters imply effective n160 without
the topology audit. At v=.2, a target halfwidth5 points requires about308 clusters;
3 points about856. These are precision goals, not superiority powers.

## Recommendation B: estimation-focused first assessment

Retain **160 audited independent clusters,40 per mechanism**, if feasible, but
change the first study's claim to estimation of paired completion, sensing cost
and exactly matched timing effects. Report cluster-aware intervals and all
negative results; make no confirmatory five-point efficacy claim. Do not extend
the sample after inspecting assessment intervals. This is a proposed amendment,
not a retroactive relabeling of an executed study.

For a future confirmatory study,624 clusters is defensible only under v=.1975
and simple-superiority assumptions, not universally. A conservative v=.4 design
would need about1,256, with additional planning for joint call/timing criteria.
Given unresolved model/calibration/generator feasibility, multiplying the entire
16-method matrix to that scale is premature. Use a new independently generated
assessment for any later confirmatory phase; do not promote the estimation data
to a fresh confirmation set or consume final held-out to achieve significance.

Use a fixed final analysis: average random streams then dynamics within topology,
equal mechanism weights, stratified topology-cluster bootstrap with10,000 draws
and seed1505011, plus leave-one-mechanism-out sensitivity and paired discordant
counts. This stratified bootstrap is an explicit amendment to v0.1's global draws
with missing-stratum rejection. Its intervals are descriptive, approximate and
conditional on generator sampling. Do not call a degenerate interval evidence
of equivalence. Retain the untouched final held-out partition for later review.
