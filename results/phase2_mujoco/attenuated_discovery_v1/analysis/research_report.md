# Attenuated discovery: retrospective actual-scan audit

|Safety|Role|Estimator|Noninitial scans|MAE|Signed error|Threshold mismatches|
|---|---|---|---:|---:|---:|---:|
|original|all|frontier|700|11.879|-11.176|72|
|original|all|q50|700|9.126|-8.160|28|
|original|all|q80|700|5.964|-4.538|34|
|original|all|optimistic|700|2.896|-0.233|39|
|original|original_regression|frontier|235|11.132|-9.294|33|
|original|original_regression|q50|235|8.983|-6.544|17|
|original|original_regression|q80|235|6.382|-3.063|23|
|original|original_regression|optimistic|235|3.753|1.174|26|
|original|prospective_benchmark|frontier|465|12.256|-12.127|39|
|original|prospective_benchmark|q50|465|9.198|-8.977|11|
|original|prospective_benchmark|q80|465|5.753|-5.283|11|
|original|prospective_benchmark|optimistic|465|2.462|-0.944|13|
|res_h1_phase_wait|all|frontier|745|10.953|-10.515|55|
|res_h1_phase_wait|all|q50|745|8.263|-7.661|18|
|res_h1_phase_wait|all|q80|745|5.211|-4.259|24|
|res_h1_phase_wait|all|optimistic|745|2.267|-0.224|37|
|res_h1_phase_wait|original_regression|frontier|225|10.800|-9.431|21|
|res_h1_phase_wait|original_regression|q50|225|8.218|-6.519|5|
|res_h1_phase_wait|original_regression|q80|225|5.219|-2.908|11|
|res_h1_phase_wait|original_regression|optimistic|225|2.329|1.396|18|
|res_h1_phase_wait|prospective_benchmark|frontier|520|11.019|-10.985|34|
|res_h1_phase_wait|prospective_benchmark|q50|520|8.283|-8.155|13|
|res_h1_phase_wait|prospective_benchmark|q80|520|5.208|-4.844|13|
|res_h1_phase_wait|prospective_benchmark|optimistic|520|2.240|-0.925|19|

Fixed q=.5 and .8 are heuristic transmission factors, not fitted/calibrated probabilities.
Only actual previously authorized observations are assessed. Initial scans are saved separately in the CSV, excluded from the main comparison.
No new controller or navigation policy is evaluated; no safety promotion or production cohort permission.
