# H2 implementation optimization report

The original `src/spatial_memory/cadence_age.py` remains byte-for-byte identical to the 840b0e2 source, preserving prior CAA/H2 source commitments. The optimized implementation is separately versioned at `src/spatial_memory/cadence_age_optimized_v1.py`; it contains the exact implementation code used for parity and timing measurements.

## Audit of 54 admitted models

`implementation_audit.csv` records all 54 model definitions, source hashes, identified redundant work, applied changes and parity status. We did not find proven safe optimization opportunities for the other 52 models and made no changes to them.

## Changes

- **Periodic-5:** return from fixed-period logic before constructing `np.indices`, the known-cell mask, or the unused age score. Grant remains `step > 0 and step % (age + 1) == 0`. Scan history diagnostics are preserved.
- **Age-5:** remove the duplicate fraction(age) computation that only populated diagnostic `age_request`; retain fraction(age+1), which determines the grant.
- **Behavioral state:** the 432 paired episode comparisons passed including state snapshots at initialization, every observation decision and each memory update. Only diagnostic-only cadence scores and measurement time fields were excluded. All meaningful observations, headings, actions, spatial memory, events, shields, contacts and later controller states matched.

## Performance

Same-session direct before/after measurements are in `episode_timings.csv` and `decision_microbenchmark.csv`. A larger same-session, five-repetition 54-model measurement is the authoritative cost matrix in `all_model_episode_timings.csv`. The older 19,440-row timing run is preserved and compared in `historical_vs_optimized_comparison.csv`; material anchor variation was the reason for the additional full matrix. Poster figure C uses a horizontal computation-cost axis on a logarithmic scale.

## Source-binding correction

An initial in-place source edit conflicted with a previously frozen CAA source hash. Before finalization, the old file was restored exactly and the optimized bytes were moved to the separate versioned file. Append-only parity/timing binding amendments identify the moved source and preserve all prior journals and measured records. The protected-file verifier now passes.
