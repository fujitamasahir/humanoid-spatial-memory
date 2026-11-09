# Emergency Safety Sensor optimization report

Scope: one saved R/80000001, schedule 1, Static, seed 42 episode. No world was generated.

## Profile findings

The original scan called `mj_ray` once for each of 181 beams, then rasterized about 35,000 sample points per scan through repeated Python `world_to_grid` calls. The Python sample rasterization dominated the profiled work; individual intersection calls were secondary. The optimized scanner batches rays in `mj_multiRay` and vectorizes sample coordinate conversion. First-hit geometry classification, wall occlusion, range, ray origins/directions, and sampling interval are preserved.

## Measured configurations

| Configuration | Rays | Total rays | Scan median / P95 (ms) | Episode median (ms) | Loop median (ms) | Goal / step | Contacts (states/pairs) | F/L/B/W/T actions | Interventions | Static obs | step 52 detect/override |
|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---|
| Original 181 single ray | 181 | 13756 | 6.127 / 8.024 | 665.20 | 623.75 | True / 76 | 0/0 | 45/1/0/6/24 | 7 | 1 | True ([[11, 5]]) |
| Optimized 181 | 181 | 13756 | 0.483 / 0.688 | 236.25 | 187.52 | True / 76 | 0/0 | 45/1/0/6/24 | 7 | 1 | True ([[11, 5]]) |
| Experimental 91 | 91 | 6916 | 0.317 / 0.363 | 218.15 | 170.82 | True / 76 | 0/0 | 45/1/0/6/24 | 7 | 1 | True ([[11, 5]]) |
| Experimental 61 | 61 | 4636 | 0.267 / 0.307 | 213.28 | 166.64 | True / 76 | 0/0 | 45/1/0/6/24 | 7 | 1 | True ([[11, 5]]) |
| No emergency sensor | 0 | 0 | — | 160.71 | 124.01 | False / 80 | 6/234 | 33/0/0/0/22 | 0 | 1 | n/a |

The step-52 saved sensor observation detected the proxy at `(11,5)` before the selected move into `(11,4)`; the safety controller changed the action to wait. The 181-ray optimized trace and all recorded measured cells, hit categories, selected actions, interventions, and episode counters match the committed safety result exactly.

## Recommendation and limits

Keep 181 rays as the default. The behavior-preserving implementation change is the recommended optimization. 91- and 61-ray variants are experimental even if the target episode completes, because sparser angular sampling can miss an unseen or occluded proxy. Adaptive sensing was not enabled: absent detections do not prove absence of danger, and this single episode cannot justify downsampling safely. Zero contacts in this target run is not a general safety claim.

See `profiling.json`, `benchmark_comparison.json`, and `episode_comparison.json` for timing samples, profiles, metrics, trial ordering, and provenance.
