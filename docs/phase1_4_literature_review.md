# Phase 1.4 literature review

Research date: 2026-11-06. Documentation only, based on Phase 1.3 commit
`df1617739c300ec671b40cfe608b851be7aaa6f2`. Nine works reviewed: eight primary
research works and one explicitly identified survey. This is a targeted search,
not a systematic or exhaustive novelty assessment. No paper result is reproduced.

## Evidence conventions and search

**V** means supported by the linked primary paper, publisher or author page.
**I** means our interpretation or transfer inference. **U** means unverified or
not established in inspected material; it never means a feature does not exist.
A code link is evidence of availability only, not an audited working implementation,
license compatibility, released weights or successful reproduction.

Searched exact mandatory titles/identifiers, then navigation + selective sensing,
value of information, occlusion, dynamic occupancy and stale maps. Followed primary
paper references, author repositories and institutional manuscripts. Excluded
AI-generated paper reviews and third-party summaries as technical evidence.
ALONE and other web HTML were read through relevant method/experiment sections;
PDF text was inspected for the other accessible works. FreMEn direct PDF retrieval
failed (unsupported content type); indexed author-manuscript text and author lab
page were available. Higgins publisher text was unavailable; author publication
record and indexed thesis chapter were inspected. Those two are partial-access
reviews; neither supports an equation-level reproduction decision.

## P1 — closest intermittent-navigation prior

**V:** Feihong Yang, Xiang Long, Jincheng Yu, Jianfei Zhang, Guangjun Ge,
Chao Wang, Yu Wang. *Acting from Belief, Looking When Needed: A Bayesian Spatial
World Model for Navigation under Intermittent Perception*. 2026, arXiv preprint
2610.11591v1; peer-reviewed venue not established.
[Primary paper](https://arxiv.org/html/2610.11591v1).

**V:** Task/decision: selective depth sensing when reliability impedes navigation
and relevant evidence is expected visible. Memory: learned structured categorical
belief with prediction/correction. Intermittent: yes. Occlusion: predicted visibility.
Dynamic environments: future work (§VI). Cost: observation opportunity cost, not our
hard caps. Evaluation: Flightmare Lattice/Trap and indoor drone flights. **U:** no
author code/weights release verified. **I:** closest conceptual competition; grid
port feasibility is assessed separately, without claiming reproduction.

## P2 — mandatory survey, not a competing algorithm

**V:** Marija Popović, Joshua Ott, Julius Rückin, Mykel J. Kochenderfer.
*Learning-based methods for adaptive informative path planning*. 2024,
Robotics and Autonomous Systems 179, 104727,
[DOI](https://doi.org/10.1016/j.robot.2024.104727),
[author-hosted full text](https://www.ipb.uni-bonn.de/wp-content/papercite-data/pdf/popovic2024jras.pdf).

**V:** Unified adaptive information-gathering formulation with action sequences,
information utility and resource limits; beliefs and mechanisms vary across
surveyed methods. Intermittent sensing, task relevance, occlusion and dynamics
are method-dependent, not properties of one survey algorithm. Applications include
monitoring, exploration, semantic mapping and active SLAM; no single evaluation
system or observation budget applies. [Paper catalog](https://dmar-bonn.github.io/aipp-survey/)
indexes implementations. **I:** useful discovery taxonomy; entropy reduction and
navigation utility must be distinguished. It is not a primary-method reproduction
candidate, and a catalog entry does not verify any particular repository.

## P3 — adaptive environmental sensing

**V:** Kian Hsiang Low, John M. Dolan, Pradeep Khosla.
*Information-Theoretic Approach to Efficient Adaptive Path Planning for Mobile
Robotic Environmental Sensing*. 2009, ICAPS, pp. 233–240.
[Proceedings](https://ojs.aaai.org/index.php/ICAPS/article/view/13344),
[author manuscript](https://www.cs.cmu.edu/~bryanlow/pubs/icaps2009e.pdf),
[DOI](https://doi.org/10.1609/icaps.v19i1.13344).

**V:** iMASP chooses adaptive measurement paths for environmental hotspot fields;
GP/log-GP beliefs and information-theoretic rewards support sequential decisions.
Path/sampling constraints matter. Task relevance is field mapping, not avoiding
stale navigation obstacles. Evaluation compares environmental-sampling policies.
Intermittent: discrete adaptive measurements, not necessarily switching off a
navigation sensor. Occlusion and moving-obstacle navigation are not established
in the inspected formulation. **U:** author implementation not verified.
**I:** strong warning against treating global entropy as synonymous with task value;
substituting Bernoulli occupancy for its field model would be a conceptual adaptation.

## P4 — sensing feasibility through dynamics

**V:** Devansh R. Agrawal, Dimitra Panagou.
*Sensor-based Planning and Control for Robotic Systems: Introducing Clarity and
Perceivability*. 2023, IEEE Control Systems Letters; author also lists CDC 2023.
[Paper](https://arxiv.org/html/2304.02578),
[author publication record](https://dev10110.github.io/).

**V:** Clarity quantifies information quality; augmented robot/information dynamics
and HJB reachability characterize attainable information. HJB/CBF controllers
plan sensing motion. Memory: estimator uncertainty/clarity, not ternary last-write
occupancy. Examples include information/energy tradeoffs and coverage in simulation.
Dynamic uncertainty is modeled. Intermittent camera scheduling and grid occlusion
are not established as its evaluated task. Budget concerns energy/time/information,
not our call caps. Author code is cited as
[Active-Exploration-Via-Clarity](https://github.com/dev10110/Active-Exploration-Via-Clarity)
(the connector returned a repository redirect; code contents not verified).
**I:** motivates feasibility, but our ray visibility estimate is not perceivability
and inherits none of its guarantees.

## P5 — decision costs and active viewpoints

**V:** Javier Vélez, Garrett Hemann, Albert S. Huang, Ingmar Posner, Nicholas Roy.
*Active Exploration for Robust Object Detection*. 2011, IJCAI, pp. 2752–2756.
[Proceedings and paper text](https://ijcai.org/proceedings/2011/458),
[author PDF](https://groups.csail.mit.edu/rrg/papers/velezj_ijcai11.pdf).

**V:** Online planning trades detour motion cost against expected object-decision
error; Bayesian object-existence beliefs include approximate correlated observations.
Perception fields model viewpoint informativeness. Task relevance is explicit:
reach a destination while making useful detections. Selective viewpoints: yes;
complete navigation-sensor shutdown: not established. Occlusion/viewpoint effects
motivate the observation model; persistent/moving occupancy is not the studied
memory problem. Cost: travel and terminal detection error, rather than a matched
call cap. Evaluation: simulation and robotic wheelchair door detection.
**U:** author code release not verified. **I:** cost-aware active perception is
established prior art; our cell-flip score is a cheaper navigation-specific proxy.

## P6 — value of sensory information

**V:** Arjun Krishna, Edward S. Hu, Dinesh Jayaraman.
*The Value of Sensory Information to a Robot*. 2025, ICLR.
[Official paper](https://proceedings.iclr.cc/paper_files/paper/2025/file/e1126028d9f1f69c13571ec462084d31-Paper-Conference.pdf),
[author project](https://sites.google.com/view/vosi-robotics/).

**V:** Measures task-return regret when sensing is withheld for a window; studies
mixed-loop execution of fixed controllers and a greedy observation strategy using
statewise sensory-value profiles. Task relevance and intermittent sensing are
explicit. Belief/model representation depends on controller. Evaluation includes
robotic tasks and four-rooms; model error/stochasticity and noisy-sensing extensions
are examined. Budget: tolerated task regret, not an observation-call cap. General
occlusion-aware occupancy memory is not established. Paper promises code on its
website; an available release was not verified. **I:** faithful online use here
would require profiles conditioned on accessible histories, not lookup by hidden
world state. An evaluator-only regret diagnostic is more feasible than a faithful
scheduler port, and must never supply labels to an assessment policy.

## P7 — dynamic occupancy estimation

**V:** Dominik Nuss, Stephan Reuter, Markus Thom, Ting Yuan, Gunther Krehl,
Michael Maile, Axel Gern, Klaus Dietmayer. *A Random Finite Set Approach for Dynamic
Occupancy Grid Maps with Real-Time Application*. Preprint 2016; journal version
2018, International Journal of Robotics Research 37(8), 841–866.
[Preprint full text](https://arxiv.org/html/1605.02406),
[journal DOI](https://doi.org/10.1177/0278364918775523).

**V:** PHD/MIB filtering estimates dynamic occupancy/velocity using random finite
sets and particles; a real-time approximation fuses laser/radar evidence. Dynamic
obstacles and unobserved areas are represented. Evaluation uses real sensor data
for estimation/consistency, not sensing-schedule navigation outcomes. Intermittent
observation policy, route value and observation-call budget are not established.
**U:** original author code not verified; third-party implementations are not
accepted as author releases. **I:** useful later memory-model comparator, but
introducing velocities/measurement models would change the present common-estimator
comparison and confound scheduler attribution.

## P8 — observation planning around occlusion (partial access)

**V:** Jacob Higgins, Nicola Bezzo. *Negotiating Visibility for Safe Autonomous
Navigation in Occluding and Uncertain Environments*. 2021, IEEE Robotics and
Automation Letters; [author record](https://www.bezzorobotics.com/publications),
[DOI](https://doi.org/10.1109/LRA.2021.3068701).
[Author thesis, chapter 2](https://libraetd.lib.virginia.edu/downloads/9880vs50z?filename=1_Higgins_Jacob_2024_PHD.pdf)
provides accessible indexed method context; direct rendered text unavailable.

**V, chapter-level:** MPC balances goal progress and geometric visibility with
uncertain traffic occupancy; simulation and ground-vehicle experiments are
reported. Representation includes projected occupancy uncertainty. Occlusion and
possible moving actors are explicit. **U:** selective sensor shutdown, fixed call
budget, released code and exact published implementation details not verified.
**I:** viewpoint choice is a strong competing mechanism, but our first-stage
scheduler cannot move for a view. Comparisons must label this action-space mismatch
rather than presenting fixed-pose ray filtering as equivalent MPC.

## P9 — stale memory through temporal mapping (partial access)

**V:** Tomáš Krajník, Jaime Pulido Fentanes, João M. Santos, Tom Duckett.
*FreMEn: Frequency Map Enhancement for Long-Term Mobile Robot Autonomy in Changing
Environments*. 2017, IEEE Transactions on Robotics 33(4), 964–977.
[Author manuscript](https://raw.githubusercontent.com/wiki/gestom/fremen/papers/fremen_2017_TRO.pdf),
[DOI](https://doi.org/10.1109/TRO.2017.2665664),
[author lab](https://chronorobotics.fel.cvut.cz/open-science/fremen).

**V:** Harmonic temporal models predict binary environment states from histories,
with periodicity assumptions. Reported long-term experiments span months/years
and support localization/navigation. This concerns changing memory, not a dedicated
route-triggered observation switch. Occlusion-specific observation planning and
our hard caps are not established. [Author-linked code](https://github.com/gestom/fremen)
is accessible (repository metadata verified; no build performed). **I:** related
to stale-map prediction, but fitting meaningful periodicity from forty-step
histories is questionable; replacing the common last-write map would introduce
another experimental factor.

## Synthesis and evidence boundary

ALONE, sensory-value execution and decision-cost viewpoint planning are closer
than generic information-gain exploration. Dynamic mapping addresses a distinct
estimation problem. There is no defensible claim that task-relevant intermittent
sensing or combining uncertainty and visibility is new. A narrower question is
whether cheap, history-only disruption/visibility scores remain useful under
unseen dynamic changes and limited budgets without a trained spatial completion
model. This is our research question, not an assertion that no prior work solves it.
See [comparison](phase1_4_prior_work_comparison.md) and
[frozen candidate protocol](phase1_4_experimental_protocol.md).

Search/access audit: ALONE HTML/abstract fetched; no author code release found by
paper-ID repository search or inspected links (not proof of absence). Mandatory
survey publisher fetch returned 403, but institutional full text succeeded. Low
publisher page and author manuscript succeeded. Clarity HTML/PDF succeeded;
repository content retrieval failed after redirect. VoSI official proceedings
succeeded after OpenReview browser challenge; project page has no verified code
release. Nuss publisher timed out, preprint succeeded. Higgins author metadata
succeeded; publisher exposed no usable text. FreMEn author manuscript was indexed
but direct tool open failed; lab page and code repository metadata succeeded.
These limits remain explicit prerequisites for any faithful reproduction claim.

## Documentation validation record

All 23 unique external link targets in the three deliverables were attempted via
web access or the GitHub connector. Fourteen supplied readable primary content
or repository metadata. Nine could not be fully retrieved: the five DOI resolver
links, MIT author PDF, FreMEn raw PDF, Clarity repository contents, and the rendered
Higgins thesis download. Retain DOI identifiers because primary metadata supports
them; a retrieval failure is not evidence that an identifier is invalid. Accessible
publisher/author alternatives are linked beside them. No inaccessible text is
represented as read in full. The arXiv GitHub “Report Issue” UI is not author code.

All relative document links resolve locally. The twelve method rows, nine-point
parameter grids and execution-count arithmetic were checked for consistency.
The only repository changes are the three Phase 1.4 Markdown documents; src,
scripts, tests, configs and Phase 1.3 results are unchanged against the branch
base. No algorithm tests, simulation experiments or held-out evaluation were
executed for this documentation-only task. `git diff --check` passes. Source
regression results remain the Phase 1.3 record; they are not presented as a fresh
Phase 1.4 test run.
