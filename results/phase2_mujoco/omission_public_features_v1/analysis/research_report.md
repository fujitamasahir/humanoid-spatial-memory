# Pre-scan public omission features: retrospective audit

|Safety|Rule|Selected|No-worse savings|Goal/contact harms|Movement harms|Paid increases|
|---|---|---:|---:|---:|---:|---:|
|original|all|73|23|5|9|11|
|original|frontier_no_new|19|0|1|1|1|
|original|fully_known_route|21|11|0|0|2|
|original|known_prefix|49|15|2|5|6|
|original|known_prefix_no_visible_unknown|39|11|1|4|5|
|original|previous_no_change|54|16|2|3|3|
|original|stable_prefix|38|11|0|0|2|
|original|stable_prefix_high_overlap|26|6|0|0|2|
|original|stable_prefix_later|31|9|0|0|2|
|original|stable_prefix_later_previous_no_change|25|7|0|0|0|
|original|stable_prefix_same_pose|17|0|0|0|0|
|res_h1_phase_wait|all|76|26|1|3|8|
|res_h1_phase_wait|frontier_no_new|20|1|0|1|1|
|res_h1_phase_wait|fully_known_route|45|16|0|1|4|
|res_h1_phase_wait|known_prefix|52|18|1|3|7|
|res_h1_phase_wait|known_prefix_no_visible_unknown|43|16|1|2|6|
|res_h1_phase_wait|previous_no_change|62|20|1|2|4|
|res_h1_phase_wait|stable_prefix|41|13|1|0|4|
|res_h1_phase_wait|stable_prefix_high_overlap|27|7|0|0|3|
|res_h1_phase_wait|stable_prefix_later|33|12|0|0|3|
|res_h1_phase_wait|stable_prefix_later_previous_no_change|31|12|0|0|1|
|res_h1_phase_wait|stable_prefix_same_pose|17|0|0|0|0|

All masks are retrospective diagnostics; none is selected for rollout.
A mask with no observed harms is not a safety guarantee. Repeated scans and scenes are correlated.
Realized omitted scan content is joined only after public features were written; no sensing or navigation was rerun.
Multiple omissions are not additive. New independent development environments remain necessary.
