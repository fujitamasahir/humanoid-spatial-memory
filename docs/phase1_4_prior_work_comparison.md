# Phase 1.4 closest-prior comparison and reproduction decision

Documentation only, 2026-11-06. Evidence labels and nine paper records are in the
[literature review](phase1_4_literature_review.md). Candidate definitions and
assessment rules are in the [protocol](phase1_4_experimental_protocol.md).

## ALONE: direct competition, not a novelty baseline to ignore

**Verified P1 details:** learned VQ occupancy prediction/correction and supervised
reliability support the sensing gate; §V-A also forces observation after five
observation-free inference updates. Runtime uses single-camera depth; dense
occupancy supervises training, with lidar mentioned as a possible supervisory
source. No released checkpoint was verified. These facts come from
[ALONE §§III–V](https://arxiv.org/html/2610.11591v1), not a reproduced experiment.

**Our transfer assessment:** faithful full-system reproduction is not presently
feasible *inside the unchanged grid-world stack*. Ternary local observations
cannot exercise the published neural sensor encoder. Replacing the estimator,
action space, data pipeline and training targets would change the experiment
from scheduler attribution to a new system comparison. This is a scope/dependency
assessment, not proof that reproduction is impossible in another simulator.
Pretrained artifacts are not established as publicly available requirements;
training compatible components ourselves would require a separate authorized
project. No additional runtime sensor should be assumed from a training modality.

| Question | Current decision | Required before a stronger claim |
| --- | --- | --- |
| Faithful full-system grid reproduction? | No verified path within current interfaces | Obtain artifacts/details, establish compatible training and sensing, reproduce published sanity checks |
| Equal observation budgets? | A capped adaptation is possible, not an unchanged published evaluation | Count initialization and mandatory fallback calls; define denial behavior and match information per call |
| Already task-aware/selective? | Yes; see P1 | Do not claim those ingredients as our novelty |
| Visibility and route relationship? | Direct conceptual overlap | Compare against a simple public-belief gate, not only generic entropy |
| Performance transfer? | Unknown | No comparison between paper success percentages and our grid scores |

A shared cap can deny a required refresh; that is a new intervention, not a
faithful replication. Paper time, grid steps, successful-only sensing summaries
and all-episode averages cannot be equated. Cost matching requires common sensor
content and action semantics, not simply the same numeric observation count.

## Frozen substitute: `query-gate-conceptual`

This is our **simplified conceptual comparator inspired by P1**, never “ALONE”,
“ALONE reproduction”, or a validated implementation of its equations. It uses the
same last-write map and decay-derived confidence as all new grid heuristics;
there is no learned spatial completion or supervised reliability. It requests
sensing when a public-memory confidence mask changes the remembered route's next
move and sufficient low-confidence nominal-route cells are predicted visible.
After a granted observation it replans using the unchanged movement controller.
It does not reliability-filter executed movement. Its exact formula, fallback,
thresholds, budget and complexity are in the protocol.

This sacrifices a joint sensing/motion mechanism to isolate the observation
schedule. A result against it supports only comparison with that abstraction,
not superiority to P1. A reviewer may reject this surrogate; in that case the
prior-work comparison remains unresolved rather than silently relabeling it.

## Other closest alternatives and feasibility

| Prior | Why it matters | Faithful comparator in present scheduler experiment? |
| --- | --- | --- |
| P6 sensory-value execution | Task-return loss from missing sensing is a useful competing objective | No verified online port: mapping accessible histories to suitable profiles would need new training/model assumptions. Evaluator-only diagnostic feasible after separate specification |
| P5 decision-cost active viewpoints | Sensing cost and decision consequences are already coupled | No: object detector likelihoods, correlated viewpoint evidence and motion detours are absent |
| P4 clarity/perceivability | Information acquisition depends on actuation/sensing feasibility | No: our binary rays and cardinal A* do not implement its continuous estimation/control problem |
| P3 iMASP | Adaptive information-gathering has substantial prior theory | No: field belief and sensing-path objective differ from changing-occupancy navigation |
| P8 occlusion-aware MPC | Can move for visibility while pursuing a goal | No: changes motion policy/action space; partial paper access also prevents a faithful claim |
| P7 dynamic occupancy / P9 FreMEn | Stronger temporal models may dominate a scheduling heuristic | Separate estimator study, not a faithful scheduler-only control under last-write memory |

These are transfer judgments (I), referring to the source facts in P3–P9; they do
not assert that those algorithms cannot be implemented at all. No faithful
published end-to-end scheduler comparator is currently verified. The frozen
matrix includes an explicit conditional slot, excluded from numeric sample-size
counts. It may be filled only by a reviewed protocol amendment **before** assessment
access, with equations, artifacts, licenses, training provenance, data boundaries,
resource limits and common-input checks. Otherwise report “not available” and
limit claims to the twelve specified conceptual/baseline methods. Do not invent
an extra method merely to fill a table.

## Recommended research positioning

The combined score is a weighted heuristic using established ingredients. The
strongest question is whether an inexpensive, untrained schedule preserves useful
navigation performance when memory becomes stale under changing occupancy,
occlusion and binding budgets, beyond rate matching and confidence calibration.
It is not “is task-aware active perception new?”. The simplest sufficient control
is a precommitted quota schedule, followed by route-weighted entropy and the
public query gate. Failure to beat these controls falsifies the need for the more
expensive disruption calculation in this setting.

Ready for research review: yes. Ready to implement without review: **no**. Review
must accept the common-estimator scope, surrogate limitation, frozen parameter
search and assessment plan, and decide whether a faithful published comparator
is required before proceeding. No missing publication detail is silently replaced
by an oracle, pretrained asset, or new sensor assumption.
