# RAA descriptive FIT72 results

|Policy|Goals/72|Paid scans|H80 steps|Blocked|Combined rays|Contacts|
|---|---:|---:|---:|---:|---:|---:|
|periodic|66|800|3039|47|234179|0|
|age|66|850|2915|36|229665|0|
|age5|66|770|3044|63|232654|0|
|raa_advance|59|800|3058|42|235338|0|
|raa_defer|66|768|3044|63|232532|0|
|raa_joint|59|800|3058|42|235338|0|

|Candidate vs reference|Rescues/harms|Common successes|Step delta|Distance delta m|Primary target|
|---|---:|---:|---:|---:|---|
|raa_advance vs periodic|0/7|59|-2.1864406779661016|-0.8389830508474576|False|
|raa_advance vs age|0/7|59|-0.3050847457627119|-0.1016949152542373|False|
|raa_advance vs age5|0/7|59|-1.4915254237288136|-0.5084745762711864|False|
|raa_defer vs periodic|2/2|64|0.390625|0.3046875|True|
|raa_defer vs age|3/3|63|2.253968253968254|1.0|True|
|raa_defer vs age5|0/0|66|0.0|0.0|True|
|raa_joint vs periodic|0/7|59|-2.1864406779661016|-0.8389830508474576|False|
|raa_joint vs age|0/7|59|-0.3050847457627119|-0.1016949152542373|False|
|raa_joint vs age5|0/7|59|-1.4915254237288136|-0.5084745762711864|False|

Immediate and stronger targets: {'raa_advance': {'immediate_task_target': False, 'beats_periodic_and_age': False, 'also_beats_age5': False, 'strong_joint_all_three': False}, 'raa_defer': {'immediate_task_target': True, 'beats_periodic_and_age': True, 'also_beats_age5': True, 'strong_joint_all_three': False}, 'raa_joint': {'immediate_task_target': False, 'beats_periodic_and_age': False, 'also_beats_age5': False, 'strong_joint_all_three': False}}

Reused development FIT72,36 correlated maze clusters. Conditional travel metrics use only common successes. No independent superiority claim.
