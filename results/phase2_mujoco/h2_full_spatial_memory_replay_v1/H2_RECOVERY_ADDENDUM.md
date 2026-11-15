# H2 Replay Recovery Addendum — Parity Reconciliation

The first Task B pass had two audit defects. Its historical scanner omitted plain `.jsonl` records and admitted generic RDAO method labels as model identity. RDAO v1 was compared directly to its primary records by exact world identity and schedule; all 72 matched.

The H2 adapter also mistakenly enabled EVI for `b_age`, so the initial 72 records labeled B+Age actually used B+C. Those original files remain byte-for-byte preserved and are excluded from the authoritative index. The adapter was corrected to `persistence=True, evi=False`; 72 B+Age episodes were recorded in the separate `task_b_b_age_corrected_v2` epoch under append-only `binding_amendment_5.json`. All 72 now match the identity-matched FIT72 traces and metric signatures. The first incomplete correction smoke attempt is retained under `task_b_b_age_corrected/` and excluded.

## Authoritative FIT72 reconciliation counts

- Exact historical parity: 2,592 / 3,888
- First-time FIT72 evaluations with no prior keyed result: 1,296 / 3,888
- Mismatches: 0 / 3,888
- Uncomparable: 0 / 3,888

Task A remains 864 / 864 exact. All comparable historical cases reproduce exactly; the 1,296 cases without historical keyed results are labeled descriptive first-time evaluations. See `replay_index_reconciled.csv`, `parity_reconciliation.csv`, and `fit72_b_age_correction_validation.csv`.
