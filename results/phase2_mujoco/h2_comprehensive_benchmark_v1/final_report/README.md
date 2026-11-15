# H2 Comprehensive Evaluation — Artifact Guide

This is a partial, descriptive development evaluation. The 13 prior models were reused and 41 authorized additional models were evaluated in each condition. Three models remain blocked by their owning research gates; see `research_report.md`. Thus the available combined dataset is 7,776 rows (54 models), not the requested 8,208 rows (57 models).

## Key outputs

- `../protocol/model_registry.json` and `.csv`: all 57 names, fixed arms, provenance, gate status.
- `../combined_dataset/episode_metrics.csv`: combined episode-level metrics.
- `../combined_dataset/replay_index.json`: 7,776 source paths and hashes.
- `../analysis/`: per-model and condition summaries, paired comparisons, whole-maze bootstrap intervals, safety/environment summaries, failure cases, Pareto and break-even tables, figures, and representative saved-replay GIF/PNG.
- `../original_environment/episodes/` and `../high_frequency_environment/episodes/`: new checkpoint/replay records with resume journals.
- `research_report.md`: interpreted development findings and limitations.

## Reproduction/verification

```sh
.venv/bin/python scripts/run_h2_comprehensive_benchmark.py verify
MPLCONFIGDIR=/private/tmp/h2mpl .venv/bin/python scripts/analyze_h2_comprehensive_benchmark.py
MPLCONFIGDIR=/private/tmp/h2mpl .venv/bin/python scripts/finalize_h2_comprehensive_benchmark.py
```

The analysis script refuses duplicate or unpaired episodes and uses 5,000 paired whole-maze bootstrap draws (seed 20261115). The finalizer verifies hashes, frame counts, the observation cap, selected-action shield records, and step-by-step high-frequency event reconstruction. Re-running the benchmark stages is unnecessary for report review.

The representative comparison GIF uses the saved High-Frequency replay for map `h2-final-generalization-v1-20261114:R:910000017`, schedule 0. Its selection rule and source hashes are in `../analysis/representative_selection.json` and `../combined_dataset/replay_index.json`.
