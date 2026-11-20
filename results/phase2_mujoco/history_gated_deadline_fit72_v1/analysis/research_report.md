# Direct FIT72 development comparison

|Arm|Goals/72|Paid scans total|Paid scans mean|H80 steps mean|Combined rays total|Contact pairs|
|---|---:|---:|---:|---:|---:|---:|
|periodic|66|800|11.111|42.208|234179|0|
|age|66|850|11.806|40.486|229665|0|
|age5|66|770|10.694|42.278|232654|0|
|deadline|52|577|8.014|49.417|252235|0|
|deadline_stable|51|571|7.931|49.639|252845|0|
|deadline_stable_quiet|51|571|7.931|49.639|252845|0|

|Candidate vs reference|Rescues/harms|Common successes|Common steps delta|Common distance delta m|Target met?|
|---|---:|---:|---:|---:|---|
|deadline vs periodic|0/14|52|4.884615384615385|0.8653846153846154|False|
|deadline vs age|0/14|52|6.480769230769231|1.4423076923076923|False|
|deadline vs age5|0/14|52|6.038461538461538|1.2692307692307692|False|
|deadline_stable vs periodic|0/15|51|4.431372549019608|0.5588235294117647|False|
|deadline_stable vs age|0/15|51|6.0588235294117645|1.1470588235294117|False|
|deadline_stable vs age5|0/15|51|6.333333333333333|1.3823529411764706|False|
|deadline_stable vs deadline|0/1|51|0|0.0|False|
|deadline_stable_quiet vs periodic|0/15|51|4.431372549019608|0.5588235294117647|False|
|deadline_stable_quiet vs age|0/15|51|6.0588235294117645|1.1470588235294117|False|
|deadline_stable_quiet vs age5|0/15|51|6.333333333333333|1.3823529411764706|False|
|deadline_stable_quiet vs deadline|0/1|51|0|0.0|False|

Original target and stronger Age5 comparison: {'deadline': {'beats_original_periodic_and_age': False, 'also_beats_age5': False}, 'deadline_stable': {'beats_original_periodic_and_age': False, 'also_beats_age5': False}, 'deadline_stable_quiet': {'beats_original_periodic_and_age': False, 'also_beats_age5': False}}
Reused FIT development evidence only; no independent efficacy or safety claim.
