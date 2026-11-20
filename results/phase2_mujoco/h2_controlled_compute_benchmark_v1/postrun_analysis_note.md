# Post-run verification note

The completed measurement run was inspected before analysis. Its journal, timing CSV, and parity CSV remained unchanged during post-run analysis.

The first analysis attempt exposed a historical-summary path bug: the runner's `HISTORICAL[0]` resolves to `h2_final_generalization_v1`, but the timing summary required for historical comparisons is stored under `h2_comprehensive_benchmark_v1/analysis/high_frequency_environment_summary.csv`. The analysis-only wrapper sets that correct path in memory; it does not change the bound runner, model source, timing protocol, or any measured records.

The legacy `verify` subcommand prints the correct completion status `COMPLETE_WITH_DECLARED_B_AGE_HISTORICAL_NONPARITY` but exits with code 1 because it accepts only the literal status `PASS`. `postrun_verification.json` is the independent zero-exit audit: it validates all journal hashes, dimensions, record coverage, the declared 360 B+Age historical mismatches, the zero unexpected mismatches, all CSV row counts, and the frozen 836-file preservation gate.
