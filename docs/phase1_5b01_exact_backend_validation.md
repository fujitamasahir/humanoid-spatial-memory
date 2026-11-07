# Phase 1.5B-0.1 exact backend validation

2026-11-07. **Correctness passes on tractable reference cases. Literal v0.2
scalability fails. The nauty representation remains a benchmark-only proposal.**
See the [equivalence proof and amendment](phase1_5b01_canonicalization_review.md).

## Independent verification

[Correctness evidence](../results/phase1_5b01/correctness.json) records1,215 graph
fixtures: all1,099 simple labeled graphs on one through five vertices,90 seeded
random multigraphs on one through six vertices (loops and multiplicities0–2),
and26 symmetric/near fixtures. A separate all-permutations serializer, without
production pruning or serializer calls, supplies the reference. Original and
branch-and-bound bytes equal that oracle in every case. The proposal's bytes
form a bijection with the124 reference classes represented in this fixture set:
no isomorphic split or nonisomorphic merge. Each fixture's reverse relabeling
has the same proposed key. The original random-permutation, room-contraction,
suppression, doorway, pure-cycle, loop/parallel, collision, lineage and boundary
tests remain unchanged and pass.

The additional historical check covers709 self/near variant calls over all110
stored physical-raster interpretations. Both literal implementations agree,
and the proposed keys preserve the exact class relation. Full near sets on the
star, cycle and loop/parallel fixtures are independently checked against exhaustive
labeling. A synthetic bridge merges two fit components and its subsequent
cross-partition relation is rejected using proposal keys. Original tests also
cover common-lineage merges. The six-cycle versus two triangles demonstrates
that equal degree summaries cannot replace exact equivalence.

There are444 canonical-byte disagreements in the1,215 fixtures. This is expected
for a different exact canonical form and explicitly prevents claiming byte
compatibility. The small-graph oracle cannot independently certify literal75-node
bytes; none were produced. Exactness at larger sizes relies on the backend's
canonical-labeling contract plus the proved lossless encoding, not on exhaustive
enumeration. Finite tests supplement that proof rather than prove all inputs.

The complete regression suite passed **236 tests, zero failures/errors/skips**
(231 retained + five new mathematical tests), with14 existing dependency warnings.
The new tests include all1,099 simple graphs, the original seeded90 multigraphs,
relabelings, near/symmetric graphs, empty graphs and guard failure. A preliminary
test incorrectly expected a path fixture to exercise prefix pruning; the result
was still oracle-correct. That implementation-detail assertion was replaced by
an empty-graph correctness case before the passing full run. No research data
was changed to satisfy tests.

## Bounded mathematical benchmarks

[48 benchmark records](../results/phase1_5b01/benchmarks.json) cover13 deterministic
fixtures, three backends, plus full near-set attempts for M, R and a six-vertex
loop/parallel graph. Preserved M/R matrices are read from checksum-verified old
archives; synthetic fixtures are graphs only, never generated navigation worlds.

Ubuntu WSL, Python3.12.3, Intel Core i5-1035G1 host; pinned isolated
pynauty2.8.8.1/nauty2_8_8. Each measurement uses a fresh Python subprocess;
wall/CPU intervals include encoding and certificate work but exclude interpreter
startup. Peak RSS is the whole worker high-water mark, including imports. Per-call
five-second alarms supplement existing literal100,000-node/five-second guards.
The native API exposes no search-node count; null is recorded rather than zero.
Its success is consequently **wall-time feasibility**, not verification of the
unchanged node guard. A parent timeout prevents an indefinitely stuck benchmark;
Python alarms alone do not reliably interrupt arbitrary long-running C calls.
No production guard was changed.

| Preserved M workload | Status | Wall s | CPU s | Peak KiB | Search nodes |
| --- | --- | ---: | ---: | ---: | ---: |
| Old self | Guard |5.0004 |5.0000 |148756 |16853 |
| Branch-and-bound self | Guard |5.0005 |4.9544 |77864 |13595 |
| nauty proposal self | Exact proposal key |0.000628 |0.000628 |77864 |Unavailable |
| Old near attempt | Guard on self |5.3086 |5.3023 |152352 |16553 |
| Branch-and-bound near attempt | Guard on self |5.3164 |5.3152 |77864 |15336 |
| nauty proposal complete near set |119 calls,80 unique keys |0.4816 |0.4814 |77864 |Unavailable |

Near timings include enumerating/normalizing variants, explaining totals above
five seconds when the first certificate itself hits its five-second limit.
Branch-and-bound's self run completed112 leaves and pruned1,376 prefixes without
proving the global minimum; a partial incumbent is never returned as a key.
For R, old/branch-and-bound/proposal self times were4.53/2.67/0.18 ms; full near
times28.8/24.1/2.8 ms, with eight unique keys for each representation. Absolute
tiny timings are noisy; these are single measurements, not confidence intervals.

| Synthetic graph | Old self ms | Branch-and-bound ms | Proposal ms |
| --- | ---: | ---: | ---: |
| Path8 /16 /32 /75 |0.60 /1.91 /15.07 /279.35 |0.68 /1.86 /13.39 /300.20 |0.14 /0.37 /0.51 /0.79 |
| Cycle8 /16 /32 |1.40 /25.76 /352.91 |1.98 /16.48 /311.99 |0.17 /0.56 /0.50 |
| Cycle75 |Guard |Guard |0.75 |
| Clique16 |0.60 |0.61 |1.13 |
| Star32 |2.33 |3.10 |0.70 |
| Loops/parallel6 |0.43 |0.46 |0.21 |

True-twin pruning makes cliques/stars easy despite their symmetry. The sparse
cycle and almost asymmetric M show why symmetry alone is not a runtime predictor.
All timed intervals sum to32.51 seconds; subprocess startup, correctness checks,
historical checks and profiling add overhead. A preliminary mathematical pytest
run overlapped part of the benchmark session; it was not a navigation workload.
CPU versus wall values are retained so hardware/load limitations are visible.
No resource ceiling was increased, and no scaling exponent is inferred.

## Reproduction and provenance

Run in the existing Ubuntu WSL checkout:

```sh
.venv-wsl/bin/python -m pip install --target results/runs/phase1_5b01_dependencies pynauty==2.8.8.1
.venv-wsl/bin/python scripts/benchmark_phase1_5b01.py
.venv-wsl/bin/python -m pytest -q -p no:cacheprovider --junitxml=results/runs/phase1_5b01_benchmarks/full_suite.xml
.venv-wsl/bin/python scripts/verify_phase1_5b01.py
```

The benchmark refuses existing output directories. To reproduce, use a separate
checkout of the recorded base commit and copy in the four source/test files
listed in provenance plus this verifier, leaving the new result directories
absent. Run the benchmark and tests there, then copy these three reports before
the delivery verifier. Do not delete or overwrite the delivered run.
Dependencies remain outside Git in an isolated ignored directory and do not
change project requirements or the existing environment's installed packages.
The [provenance inventory](../results/phase1_5b01/provenance.json) pins source,
installed Python/native dependency files, fixture hashes, archived inputs and
all original result hashes. The [verification report](../results/phase1_5b01/verification.json)
pins JUnit evidence, final documentation, script hashes, historical counts and
bulk storage. Raw graph JSON, cProfile data, dependency files and JUnit XML stay
under ignored `results/runs/phase1_5b01_*`; compact measurements remain in Git.
There are no new episode traces. Cross-platform stability, native node-budget
instrumentation and a full population audit remain review gates.
