# Age / Age-5 retrospective mechanism audit (before CAA implementation)

All144 actual G1 replays match saved metric signatures and semantic traces. Only existing admitted FIT worlds were used. This is descriptive association, not a controlled scan intervention. The audit source/adapter snapshots are preserved with its artifacts.

| Arm | Noninitial scans | With new cells | With changed known cells | Only unchanged known | Empty |
|---|---:|---:|---:|---:|---:|
|age4|778|694|21|83|0|
|age5|698|630|30|64|0|

New-cell and changed-known categories can overlap. The table excludes the72 initial scans per arm; complete initial/noninitial cell ledgers are saved. Age revealed27 changed-known cell readings versus37 for Age-5, and10175 versus9672 new cell readings. Most scans reveal new cells; observed endpoint changes are relatively rare, constraining how strongly this cohort can test a change-history mechanism. A repeated reading can change because of occupancy or sensor occlusion/projection, not a known object class.

| Outcome under Age-5 | Maze/schedule | First scan / memory / action / position / heading differences | Age→Age5 steps | Scans | Blocked |
|---|---|---|---:|---:|---:|
|Harm|BP:80010012 /0|4 / 4 / 4 / 4 / 4|73→80|20→19|1→2|
|Harm|BP:80010012 /1|4 / 4 / 4 / 4 / 4|73→80|20→19|1→2|
|Harm|M:80030000 /1|4 / 4 / 4 / 4 / 4|76→80|20→20|0→1|
|Rescue|M:80030009 /0|4 / 4 / 8 / 8 / 8|80→76|20→20|3→1|
|Rescue|M:80030009 /1|4 / 4 / 8 / 8 / 8|80→76|20→20|3→1|
|Rescue|R:80000000 /0|4 / 4 / 4 / 5 / 4|80→57|20→15|2→1|

All six first scan and memory divergences are at4, while the first Age-5 scan is5. The step4 Age readings in those cases reveal new cells and zero changed previously known cells. BP80010012 and M80030000 immediately change action/heading; M80030009 delays action divergence until8. R80000000 first changes action/heading at4 and position at5. Thus a later scan plausibly changes discovery/route choice and budget timing; it is not evidence that uniform aging missed a known-cell transition in that first scan.

All six cases have zero emergency interventions in both arms. BP80010012 retains more stale occupied raster cell-times under Age-5 (58→71 each schedule); R80000000 succeeds under Age-5 despite0→29 stale occupied cell-times. The other changed-outcome cases have0 stale occupied cell-times in both arms. All six have0 stale free raster cell-times. Full72 audit details, budget-exhausted decisions and per-scan contents are retained, not inferred from episode totals.

Age4 versus Age5 has172 versus84 budget-exhausted decisions across all72 cases. M80030009 uses20 scans in both arms yet changes from H80 failure to step76 arrival. BP80010012 loses arrival despite using fewer scans. M80030000 uses20 in both and loses completion. These are timing/content associations; neither fewer nor more scans alone establishes causality. No forced now/later scan, hidden measurement or policy tuning was performed for this audit. Two schedules of a maze are correlated.

The CAA constants are specified prospectively from observation-history and elapsed-exposure semantics in `caa_protocol.md`; no maze-specific rule is derived from these cases.
