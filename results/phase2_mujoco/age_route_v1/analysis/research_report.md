# Route-aware Age sensing: descriptive FIT72

|Arm|Goals/72|Paid scans|H80 steps|Combined rays|Contacts total|
|---|---:|---:|---:|---:|---:|
|periodic|66|11.111|42.208|3252.49|0|
|age|66|11.806|40.486|3189.79|0|
|age_view_veto|63|10.708|44.264|3353.31|0|
|age_route_rescue|66|11.778|40.653|3198.26|0|
|age_route_clock|66|12.944|40.292|3247.40|0|

|Candidate vs reference|Rescues/harms|Common successes|Common steps delta|Common distance delta (m)|User target met?|
|---|---:|---:|---:|---:|---|
|age_route_rescue vs periodic|2/2|64|-1.531|-0.586|False|
|age_route_rescue vs age|0/0|66|0.182|0.023|True|
|age_route_rescue vs age_view_veto|4/1|62|-2.952|-0.581|True|
|age_route_clock vs periodic|2/2|64|-3.438|-1.266|False|
|age_route_clock vs age|3/3|63|-1.460|-0.524|False|
|age_route_clock vs age_view_veto|6/3|60|-5.750|-1.625|True|

Primary target (both baselines): {'age_route_rescue': False, 'age_route_clock': False}

This is a reused FIT development screen, not independent validation. Positive cost deltas are worse.
