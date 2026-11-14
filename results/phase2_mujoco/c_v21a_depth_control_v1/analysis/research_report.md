# C v2.1a new-objective depth control

Descriptive FIT72 only. Positive deltas mean higher candidate costs.

|Arm|Goals/72|Paid scans|H80 steps|Combined rays|Scheduler ms|
|---|---:|---:|---:|---:|---:|
|periodic|66|11.111|42.208|3252.49|0.069|
|age|66|11.806|40.486|3189.79|1.166|
|c0|46|5.375|53.306|3579.51|152.482|
|c_k|54|6.292|51.139|3503.26|151.501|
|c_topology3d|52|8.417|49.681|3543.93|288.359|
|h1_k|57|15.708|45.194|3715.07|95.758|
|h3_k|57|15.708|45.194|3715.07|98.759|
|h1_topology|57|15.792|44.333|3667.62|204.916|
|h3_topology|57|15.792|44.333|3667.62|202.440|

|Candidate vs reference|Rescues/harms|Common successes|All-scan delta|Common-step delta|Common-distance delta (m)|
|---|---:|---:|---:|---:|---:|
|h1_k vs c_k|4/1|53|9.417|-4.868|-1.047|
|h3_k vs h1_k|0/0|57|0.000|0.000|0.000|
|h1_topology vs c_topology3d|5/0|52|7.375|-4.096|-1.038|
|h3_topology vs h1_topology|0/0|57|0.000|0.000|0.000|
|h1_k vs age|1/10|56|3.903|3.429|0.402|
|h1_k vs periodic|2/11|55|4.597|1.873|-0.027|
|h3_k vs age|1/10|56|3.903|3.429|0.402|
|h3_k vs periodic|2/11|55|4.597|1.873|-0.027|
|h1_topology vs age|1/10|56|3.986|2.339|0.080|
|h1_topology vs periodic|2/11|55|4.681|0.782|-0.355|
|h3_topology vs age|1/10|56|3.986|2.339|0.080|
|h3_topology vs periodic|2/11|55|4.681|0.782|-0.355|
