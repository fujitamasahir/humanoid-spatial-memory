# C v2.1 audit of the original one-step delay assumption

Descriptive mechanism audit of existing FIT72 evidence, not an independent test. H=3 was fixed before this audit. Saved decisions from C0, C-K and Topology3-d were counted in full. For detailed reconstruction, the first two positive-V/zero-D decisions per arm/episode were chosen without navigation-outcome selection. The original policies were replayed through authorized sensors with exact saved semantic-trace parity; only public memory/probability snapshots were captured. No retrospective diagnostic was an online controller input.

| Reference | Decisions | V=0 | V>0,D=0 | V>0,D>0 | Noninitial scans |
|---|---:|---:|---:|---:|---:|
|c0_audit|3838|2594|140|1104|315|
|c_k|3682|2242|148|1292|381|
|c_topology3d|3577|1788|227|1562|534|

The fixed sample has233 states. Of these,225 retain visibility after a shared first move;2 have a predicted decision within H with no future shared-prefix observation opportunity. These are public-map point predictions, not actual future readings. They suggest most immediate-action agreements should NOT automatically trigger earlier sensing. Six remaining sampled states do not fall in either simple category.

An offline independent finite-prefix supplement isolates movement costs with zero scan price. It finds 4 states with positive minimum predicted postponement regret; the complete per-state numbers also include committing three blind moves before observing. Those costs are model-dependent surrogates, not realized movement or causal evidence.

Candidate selection and timing are different mechanisms. A missed high-value cell outside the shortlist is a selection failure; a shortlisted V>0 cell suppressed only by first-action agreement is a timing/value opportunity. Even expanded C-K/Topology selection yields many V=0 decisions. That does not establish global absence of useful information: the shortlist and point planner can both miss consequences. The audit does not tune a horizon, alter ranking or diagnose G1 feasibility using unselected shields.

Detailed public routes, shared-prefix lengths, headings, future visibility and selected cells are in `results/phase2_mujoco/c_v21_multistep_v1/one_step_audit/`. The supplemental reference compares now/delay/no-information on the declared restricted path catalog; it cannot prove which unexecuted scan would improve a real episode. The new prospective protocol defines the hypothesis tests independently of these descriptive outcomes.
