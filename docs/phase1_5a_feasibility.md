# Phase 1.5A computational feasibility

2026-11-07. **Measured:** small standalone mathematical kernels and synthetic
compression. **Estimated:** their contribution to future matrices. **Unresolved:**
complete filter/controller/scheduler latency and trace schema. No navigation,
tuning, assessment, held-out, ablation or MuJoCo episode ran. No EVSI policy,
particle filter, sensor or topology generator was implemented.

Reproduction script: [audit_phase1_5a.py](../scripts/audit_phase1_5a.py).
Raw21 timing samples per workload, hardware/runtime details, analytic power
tables, storage sizes/hashes and frozen artifact hashes:
[mathematical_audit.json](../results/phase1_5a/mathematical_audit.json).
The script has no `spatial_memory` imports. It evaluates arbitrary arrays and
finite decision tables, never a robot state or policy action.

From the repository root in Ubuntu WSL, the isolated commands are:

```sh
python3 scripts/audit_phase1_5a.py --test
python3 scripts/audit_phase1_5a.py --output results/phase1_5a
```

The second command regenerates timing evidence with new host-load variability;
it is not necessary to rerun it to inspect the committed measurements. Do not
substitute the full project test suite, which can execute navigation episodes.

## Measured microbenchmark conditions

Ubuntu WSL, Python3.12.3 GCC13.3.0, Intel Core i5-1035G1 as reported by the guest.
Standard-library scalar Python, one process, three warmups and21 measured calls.
No NumPy vectorization, compiled optimization, parallel worker or CPU pinning.
These are wall-clock kernel timings, not CPU profiles; extrapolating them as
CPU-hours assumes one fully occupied core. WSL host scheduling/turbo/load can
change results. The JSON records the OS, logical CPU count and exact script hash.

Synthetic dimensions M=64, N=625,169 tiles, K=29, five action-loss columns.
The dense kernel accumulates29 arbitrary log factors for each draw/particle,
log-normalizes64 weights, and reduces five weighted columns. Factors are not
a normalized physical observation model. A separate Boolean kernel evaluates
short lists of length3, not geometric occlusion rays. The categorical kernel
samples169 tile-state rows per particle from fixed16-entry distributions.
These count important numerical operations while making no filter fidelity claim.

| Workload | Median ms | Empirical p95 ms |
| --- | ---: | ---: |
| 64x169 categorical tile draws | 4.905 | 5.397 |
| 64x29 short Boolean-list checks | .110 | .217 |
| Dense log-factor/weight/loss reduction, J64 | 7.896 | 9.137 |
| Same, J128 | 15.948 | 18.984 |
| Same, J256 | 33.943 | 73.730 |

Empirical p95 from21 repetitions is a noisy upper order statistic, not a stable
tail-latency bound. Peak process RSS across **the entire synthetic audit** was
37,028 KiB (36.16 MiB), including input arrays, gzip buffers and interpreter.
It is not the peak memory of a future scheduler and does not clear the512-MiB gate.

## Operation counts and unmeasured work

For J64/128/256 the dense likelihood factors are118,784/237,568/475,136 and
weighted action products20,480/40,960/81,920 per decision. Computing full mask
compatibility per current particle once costs O(MKR), then reuse it for each
imaginary return where possible. Blindly tracing every ray per pair multiplies
ray work by J unnecessarily. Actual sensor generation still needs correct
supercover geometry and mask grouping; it was not benchmarked here.

The JB-1 [proposal](phase1_5a_design_audit.md) adds observation-adapted per-tile
normalizers O(M*169*16), importance weights, ancestry, ESS/resampling and four
Gibbs sweeps. Each Gibbs tile candidate can affect multiple visible/missing rays;
the original O(MN) estimate omits this likelihood-maintenance cost. Global offset
Gibbs over stored paths costs O(4MtN), roughly12.8 million cell/transition terms
at t80, M64, N625. This may dominate the cheap numerical core. No faithful
runtime estimate is available before the architecture is approved.

P=8 conditional forecasts and five-action losses require up to512 reverse BFS
maps per decision, rather than64. Their graph traversal, distance convention and
forecast generation are unmeasured. Fitting50 EM iterations adds four-offset
16-state forward/backward work on public histories. These omissions prevent
claiming the full scheduler meets100 ms or the matrix fits200 hours.

Array-size deductions, excluding object overhead: two64x625 uint8 occupancy banks
use80,000 bytes;64 paths of81 time slices use3,240,000 bytes. Eight forecast maps
use320,000 uint8 bytes, with512x625 float64 distances another2.56 MB if retained.
Loss/weight matrices are small, but Python objects, cached rays, transition tables,
training arrays and trace buffering can substantially increase RSS. Streaming
forecasts reduces peak arrays; it does not eliminate their computation. None of
these arithmetic sizes proves an implementation's memory ceiling.

## Full-matrix extrapolation, not end-to-end benchmarks

The unchanged v0.1 maximum125,440 episodes x80 decisions is10,035,200 events.
The proposed reduced [recommendation](phase1_5a_protocol_recommendation.md)
is6,720 x80=537,600. Each row below pessimistically applies the dense kernel to
every event, including cheap baselines, but excludes all other work. It is neither
a full runtime forecast nor a rigorous lower bound on an optimized implementation.

| J | Original maximum: kernel-only core-hours | Reduced maximum: kernel-only core-hours |
| ---: | ---: | ---: |
| 64 | 22.01 | 1.18 |
| 128 | 44.46 | 2.38 |
| 256 | 94.62 | 5.07 |

For **total** unmeasured per-decision means10/50/100/200 ms, original maximum
would take27.9/139.4/278.8/557.5 core-hours; reduced maximum1.49/7.47/14.93/29.87.
I/O, fitting, development, verification and failed/recovery jobs are extra.
Two-step sensor conditions or five random replicas do not add independent
topologies, even though they add runtime. No parameter or J is selected using
these synthetic timing differences.

## Synthetic compressed trace sizes

Each synthetic80-frame record holds two bit-packed64-particle25x25 occupancy
banks (79 bytes per particle per slice),64 float64 weights,64x5 float64 losses,
J float64 numerical summaries and2 KiB zero-filled metadata per frame. Compression
is gzip level6 with mtime0. Compare a1%-bit-flip sticky process and independent
random bit banks. Floats are independent random values; no claim is made that
these are realistic filter weights. Metadata filled with zeros is easier to
compress than full public/evaluator arrays.

| J | Raw bytes/episode | Sticky gzip bytes | Independent gzip bytes | Original maximum GB, range | Reduced maximum GB, range |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 64 | 1,259,840 | 495,906 | 1,091,924 | 62.21–136.97 | 3.33–7.34 |
| 128 | 1,300,800 | 536,104 | 1,131,275 | 67.25–141.91 | 3.60–7.60 |
| 256 | 1,382,720 | 620,476 | 1,210,087 | 77.83–151.79 | 4.17–8.13 |

GB is decimal. These are measured synthetic encodings multiplied by episode
counts, not measured experiment archives. They omit eight forecast banks, complete
path ancestry, evaluator truth, fitting histories and potentially imaginary
returns. Logging eight forecast banks would add roughly40,448 raw bytes/frame
before weights/distances, several times the bank payload above. Streaming and
counter-based reconstruction can reduce archives only after an exact replay
test. The original200–500 GB allowance is neither verified nor falsified by this
limited schema. For the reduced study, provision25 GB initially as a planning
allowance, then approve a schema-based storage projection before any assessment.
Stop rather than truncate scientifically required traces to meet that allowance.

## Feasibility disposition

Generic numerical reductions are affordable on this machine; faithful inference,
rejuvenation, forecasts and planning have **not** passed feasibility review.
Do not mistake the7.9-ms J64 kernel for the whole scheduler's latency. Approve
the model architecture first, then benchmark its components on public synthetic
models under Phase1.5B review before navigation development. Retain separate
shared-controller and incremental-scheduler timers, ESS/support diagnostics,
process RSS and complete trace-size measurements. A failed gate is a negative
feasibility result; it does not authorize silently dropping rejuvenation, reducing
J, changing priors or running a smaller favorable assessment.
