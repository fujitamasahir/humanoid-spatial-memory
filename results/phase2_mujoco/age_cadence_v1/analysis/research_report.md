# Cadence and motion-aware Age sensing: descriptive FIT72

|Arm|Goals/72|Paid scans|H80 steps|Combined rays|Contacts total|
|---|---:|---:|---:|---:|---:|
|periodic|66|11.111|42.208|3252.49|0|
|age|66|11.806|40.486|3189.79|0|
|age_route_rescue|66|11.778|40.653|3198.26|0|
|periodic5|59|9.306|43.167|3200.81|0|
|age5|66|10.694|42.278|3231.31|0|
|age_gap4|66|11.111|42.208|3252.49|0|
|age_motion|64|10.917|41.528|3199.11|0|

|Candidate vs reference|Rescues/harms|Common successes|Common steps delta|Common distance delta (m)|User target met?|
|---|---:|---:|---:|---:|---|
|periodic5 vs periodic|0/7|59|-0.220|-0.559|False|
|periodic5 vs age|0/7|59|1.441|0.076|False|
|periodic5 vs age_route_rescue|0/7|59|1.373|0.076|False|
|age5 vs periodic|2/2|64|0.391|0.305|True|
|age5 vs age|3/3|63|2.254|1.000|True|
|age5 vs age_route_rescue|3/3|63|2.127|0.976|True|
|age_gap4 vs periodic|0/0|66|0.000|0.000|False|
|age_gap4 vs age|2/2|64|1.656|0.586|True|
|age_gap4 vs age_route_rescue|2/2|64|1.531|0.586|True|
|age_motion vs periodic|0/2|64|-0.922|-0.516|False|
|age_motion vs age|0/2|64|0.734|0.070|False|
|age_motion vs age_route_rescue|0/2|64|0.609|0.070|False|

Primary target (both baselines): {'periodic5': False, 'age5': True, 'age_gap4': False, 'age_motion': False}

This is a reused FIT development screen, not independent validation. Positive cost deltas are worse.
