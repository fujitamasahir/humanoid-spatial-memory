# Corrected H2 high-frequency analysis v4

This directory is generated from the already saved primary and original-Uncertainty replay files. It does not run the simulator or regenerate any episode. Timings are read from each replay's `diagnostics.timing_ns`; `report.md` describes the timing aggregation and interpretation.

`report.md` is the corrected analysis report. `episodes.csv` contains 936 episode rows; `paired_whole_maze_bootstrap.csv` contains unadjusted exploratory contrasts clustered by the 36 map identities, keeping the two schedules together. `decision_time_quantiles.csv` reports per-call timing quantiles. Figures and the representative comparison GIF are presentation artifacts. `binding.json` records the analysis script hash, source binding hash, replay manifest hash, and bootstrap seed. `artifact_manifest.json` lists SHA-256 and byte count for every file in this directory except itself.

The nearby `analysis/` directory is the first report pass, and `analysis_v3/` is a preserved partial export; neither is authoritative. The corrected v4 outputs supersede both without altering them.
