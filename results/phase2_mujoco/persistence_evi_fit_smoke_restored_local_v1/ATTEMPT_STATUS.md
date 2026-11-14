# Incomplete FIT smoke attempt (preserved)

This directory is an incomplete attempt and is not a result to interpret. The
runner completed the two requested FIT cases for all five arms and reproduced
Periodic/Age metrics and traces, but exited while trying to recreate
`pairs.csv` exclusively on the second case. At that point `pairs.csv` contained
only the first case's pair rows. The run exposed a checkpoint-publication bug
in `scripts/evaluate_persistence_evi_fit72.py`.

The runner was corrected to publish the aggregate pair table once after all
requested cases complete. The successful rerun is
`persistence_evi_fit_smoke_restored_local_v2/`. No FIT stores or historical
outputs were modified by either attempt.
