# Phase1.5B-0.2 production backend validation

2026-11-07. The approved [v0.3-CANON-1 amendment](phase1_5b02_canonicalization_amendment.md)
is implemented in a development-only [parent](../src/spatial_memory/phase15_nauty.py)
and [isolated worker](../src/spatial_memory/phase15_nauty_worker.py). The old
literal backend, all old specification documents and prior evidence remain
unchanged. Correctness and enforceable-resource preflight passed before the
new artifact audit began. Population readiness is a separate question addressed
in the [artifact audit](phase1_5b02_development_artifact_audit.md).

## Exactness, version separation and reproducibility

[Preflight](../results/phase1_5b02/preflight.json) verifies all1,215 original
fixtures through the actual production supervisor/worker:1,099 simple labeled
graphs through five vertices,90 seeded loop/multiedge graphs,26 symmetric and
near-operation fixtures. The unchanged independent exhaustive oracle supplies
literal reference bytes. Production C3 suffixes agree with the prior pinned
prototype; equivalence across C2/C3 is a bijection on124 represented reference
classes. After removing the namespace prefix,444 matrix serializations differ
from the literal minimum; all complete C3 keys also carry that new prefix.
There are zero relation disagreements and reverse-label checks on every fixture.
Exact group/canonical-label contracts
and the proved encoding support general correctness; finite fixtures alone do
not prove it for every possible large graph.

All709 historical self/near calls agree in class relation with the immutable
literal backend under its original five-second/100,000-node guard. Historical
keys are regenerated from permitted stored matrices into a fresh namespace;
no v0.2 key is inserted into the new index. Full arrays, not checksum equality,
decide relation. Original loop/parallel, cycle, doorway/room, corridor suppression,
nonisomorphic equal-degree, transitive lineage and cross-partition tests are
retained. Production bridge fixtures also merge two fit components and reject
a cross-partition relation using new keys.

The preserved R and M graphs each reproduce their new key after reverse and
cyclic relabeling in fresh worker processes (four checks). The dedicated test
also compares a loop/parallel graph across three fresh processes and a nontrivial
permutation. Outputs carry a version namespace, request identity, valid original
vertex permutation, timings and resource evidence. Invalid framing, values or
resource claims return no key. No policy-facing data or private seed/mechanism
information enters graph colors.

| Preflight full near set | Calls | Distinct exact keys | Parent wall seconds |
| --- | ---: | ---: | ---: |
| Preserved R,11 vertices |18 |8 |0.00591 |
| Preserved M,75 vertices |119 |80 |0.51437 |

Every call's parent wall time, worker CPU time, worker elapsed time and process
peak RSS is saved in preflight and audit measurements. Full near costs include
variant generation/suppression and IPC, not just native labeling. The maximum
reported preflight worker RSS for these137 calls was85,516 KiB (83.51 MiB).
Worker process high-water marks include runtime/import history; they are not
isolated incremental nauty allocations. Native search-node count is null.

## Resource enforcement on this WSL environment

Seven dedicated production/resource tests passed before source freeze. Actual
Linux hard/soft RLIMIT_AS limits were536,870,912 bytes. A fresh same-interpreter
touched-page probe allocated520,093,696 bytes before MemoryError; peak RSS was
518,460 KiB (506.31 MiB), below512 MiB. This verifies a conservative address-space
ceiling on the actual environment, rather than relying on RLIMIT_RSS or sampling.
The resulting stricter virtual-memory overhead is explicitly part of the
approved implementation's feasibility behavior.

The parent killed and reaped an actual native `libc.sleep` call and a partial-JSON
stall. Observed complete teardown times were5.015 and5.025 seconds: the five-second
decision deadline plus process-kill/reaping latency. A crash with exit7, malformed
JSON and an explicit memory-exhaustion reply also produced the expected failure,
without approximate output or retry. The memory allocation probe is a real
exhaustion test; the explicit-reply test separately checks reporting, rather than
pretending a synthetic reply proves kernel enforcement. Initial and final suite
probes are retained separately in compact preflight/delivery evidence.

The kernel refuses virtual allocation beyond the limit, bounding resident mapped
memory conservatively. The worker reports both hard/soft limits and peak RSS on
every success, and the parent checks them. Native allocation failures can produce
either a memory exception or a crash; absent an explicit exception, the report
classifies a crash without inventing its cause. The parent deadline can terminate
native execution without waiting for Python signal delivery. Input writes and
output reads are nonblocking, and partial output cannot bypass the deadline.

No old100,000-node compliance claim is made for nauty. The literal backend and
its old guard are retained solely for historical mathematical verification.
No timeout or memory ceiling was increased following a candidate result.

One preliminary **verification-only** attempt eagerly loaded all4,534 decompressed
artifact bodies, then failed the worker's resource-evidence check before candidate
reconstruction. The verifier was changed to stream one body at a time; the frozen
backend and audit were not changed or rerun. A standalone WSL probe confirms that
`ru_maxrss` can retain pre-exec parent high-water accounting: a child with current
RSS10,424 KiB and virtual size15,568 KiB reported575,168 KiB high-water after a
large parent allocation. Thus this guard can conservatively reject a worker
launched from a large caller even when its post-exec resident set is small.
The kernel address-space ceiling remains enforced; no oversized reported peak
is ignored. Streaming avoids the verification harness's unnecessary allocation.
The incident and probe are retained in delivery evidence; they are not a new
canonicalization or sampler result.

The final complete suite passed **243 tests, zero failures/errors/skips**, with
14 existing Matplotlib/Pyparsing warnings. Recorded suite time was84.793 seconds;
it overlapped the initial independent-verification read stage, whereas the artifact
audit itself had completed before those checks. These are verification timings,
not policy computational-cost results.

## Reproduction and provenance

Use Ubuntu WSL and the existing `.venv-wsl/bin/python` (Python3.12.3, NumPy2.2.6).
Restore/install the exact pinned pynauty2.8.8.1 artifacts in the isolated ignored
dependency directory; all hashes in the config must match, including the compiled
extension. A different wheel/build is not silently accepted. In a separate output
workspace containing the preserved raw inputs and no new audit outputs:

```sh
.venv-wsl/bin/python -m pytest tests/test_phase1_5b02.py -q -p no:cacheprovider --junitxml=results/runs/phase1_5b02_resource_tests.xml
.venv-wsl/bin/python scripts/validate_phase1_5b02.py
.venv-wsl/bin/python scripts/audit_phase1_5b02.py
.venv-wsl/bin/python scripts/pack_phase1_5b02.py
.venv-wsl/bin/python -m pytest -q -p no:cacheprovider --junitxml=results/runs/phase1_5b02_full_suite.xml
.venv-wsl/bin/python scripts/verify_phase1_5b02.py
```

The first preflight and audit refuse overwrite. Do not execute these over delivered
evidence; use the prior base plus new source/config/docs in a separate checkout,
with preserved archive paths resolved. The audit checks its preflight source
hashes before any candidate, uses POSIX flock, and atomically flushes/fsyncs/replaces
each candidate checkpoint and artifact. A stopped audit is preserved, not resumed
by skipping its last seed or silently rerunning candidates. Source/configuration,
dependencies, tests and all historical-result checksums are committed as compact
provenance; raw gzip artifacts, checkpoints and JUnit stay outside Git.

The final full-suite result, storage checksums, independent topology reconstruction
and all2,212 unchanged historical records are recorded in
[independent verification](../results/phase1_5b02/independent_verification.json) and
[delivery verification](../results/phase1_5b02/delivery_verification.json).
No assessment/final worlds, G filter, navigation controller, EVSI scheduler or
MuJoCo work was implemented or run. Existing regression navigation replays are
solely the previously authorized verification exception.
