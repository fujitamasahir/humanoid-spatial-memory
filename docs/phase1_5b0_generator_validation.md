# Phase 1.5B-0 generator validation

2026-11-07. Branch `feature/phase1-4c-assessment`, reviewed base
`8ba55a8abd8df663e1aeeb86cc6a1b4664161ec2`. Implementation target is the approved
[v0.2 generator specification](phase1_5a2_generator_specification.md), read with
the [protocol](phase1_5a2_protocol_amendment.md),
[architecture](phase1_5a2_architecture_decision.md),
[prior](phase1_5a2_spatial_prior_review.md) and
[controller specification](phase1_5a2_controller_specification.md).

**Result: implementation and mathematical tests pass, but the development audit
is incomplete and not ready for Phase 1.5C.** Exact canonicalization stopped on
the first75-vertex maze quotient. No approximate certificate, larger resource
limit, modified sampler or replacement candidate was used to bypass it.
See [independence findings](phase1_5b0_topology_independence_audit.md) and
[manifest review](phase1_5b0_development_manifest_review.md).

## Scope, authorization and clarified choices

Only new evaluator-side geometry, dynamic artifact construction, mathematical
topology checks and audit/verification tools were implemented. No G filter,
navigation controller, EVSI scheduler or policy was implemented. No new policy
experiment, assessment/held-out world generation, research episode matrix or
MuJoCo run occurred.

The user explicitly resolved two specification ambiguities during this task:

- V follows the **lexicographic(y,x) coordinate-sequence** shortest path rule.
  The conflicting north/east/south/west BFS statement is not used for V ties;
  expansion order north/west/east/south implements the selected coordinate order.
  A golden2x2 path witness demonstrates that the two original rules differ.
- Draw onset and footprint length **once per schedule**, then retry footprints
  only, preserving the selected category and fixed draws through128 attempts.

The user also explicitly authorized existing regression-test navigation replays
solely for verification. Consequently 'no new policy experiments' does not mean
the existing test suite never called its historical navigation functions. The
full suite's original verification fixtures ran under that exception; new tests
are artifact-only. No reserved held-out scenario was opened or executed.

Original v0.2 documents remain unchanged. Clarifications and technical run guards
are recorded in [provenance](../results/phase1_5b0/provenance.json).

## Implemented components

| Component | Implementation and validation |
| --- | --- |
| R |16 fixed5x5 room interiors;24 lattice adjacencies; random-order Kruskal tree; .30 extra edges; one uniformly placed narrow door per selected wall. |
| B | Uniform12/16/20 leaf target; uniform eligible leaf/axis/wall/door; three-cell minimum child widths; no connectivity repair. |
| V | Uniform12/16/20 seeds without replacement; Manhattan separation/core constraints; .25 extra region edges; selected lexicographic corridors; reject unintended adjacencies. |
| M |121 coarse nodes;220 edges; random-order Kruskal tree plus .15 on100 unused edges; one-cell passages. |
| Dynamics | Five exactly equiprobable categories; specified onset/length/dwell distributions; two independent schedule streams; protected endpoints and initial/final static path checks. |
| Topology | Raster-derived2x2-room contraction, degree2 suppression, loops/multiedges, exact canonical labeling, allowed near operations, transitive lineage index and cross-partition rejection. |

Source: [generators](../src/spatial_memory/phase15_generators.py),
[topology](../src/spatial_memory/phase15_topology.py),
[audit runner](../scripts/audit_phase1_5b0.py),
[read-only verifier](../scripts/verify_phase1_5b0.py),
[new tests](../tests/test_phase1_5b0.py).

The evaluator-side `public_domain` projection contains only dimensions, start,
goal and the two public domain guarantees. It excludes seed, partition, mechanism,
free-cell raster, events and construction lineage. New modules import no policy,
simulation, evaluator episode runner or belief filter. This is a tested interface
boundary, not a Python security sandbox or a proof against malicious introspection.
No future policy integration was performed.

## Deterministic probability and stream contract

NumPy2.2.6 Philox raw uint64 words are keyed by the first128 SHA-256 bits of
length-prefixed UTF-8 fields `(phase1.5-v0.2-artifacts, decimal_seed, purpose)`;
prefix lengths/key integers are little-endian. Purposes are geometry, start-goal
and dynamics-0/dynamics-1. Uniform integers use rejection above the largest
multiple of n below2^64, eliminating modulo bias. Bernoulli probabilities use
integer ratios; permutations use Fisher–Yates. There is no shared mutable RNG
across purposes. The [NumPy stream documentation](https://numpy.org/doc/2.2/reference/random/parallel.html)
supports key-separated Philox streams; exact software/source versions and
replay hashes are nevertheless pinned, not assumed interchangeable across builds.

Tests verify exact probability arguments (.30/.25/.15 and1/5 categories), uniform
integer rejection, permutation/tree constraints and stream identity/replay. These
are algorithm/distribution checks, not empirical evidence that four observed
candidates estimate long-run acceptance rates. Golden deterministic constructions
are test fixtures, never replacements for random audit candidates.

## Tests and independent verification

**231 tests passed, zero failures/errors/skips**, in39.914 seconds of recorded
suite time;27 are new artifact-only tests and204 are the existing suite.
The14 warnings are existing Matplotlib/Pyparsing deprecations. The preliminary
new-test run's Pytest cache permission warning was avoided in final runs with
`-p no:cacheprovider`; it was not a scientific or test failure.

Coverage includes every generator's geometry, V's ambiguity witness and complete
admissible golden draw, seed/partition gates, protected endpoints, pair distances,
dynamic timing/connectivity, retry exhaustion, projection leakage, deterministic
replay, room/narrow-door contraction, pure cycles, multiedges/loops, exact versus
degree-fingerprint collisions, transitive merges and cross-partition rejection.
The dynamic fixture set constructs60 schedules on30 new fit-R seeds, covering
all five categories; these are unit-test artifacts, not60 independent manifest
worlds or navigation episodes.

The tests compare90 small random multigraphs (including loops/multiplicities)
against a separate exhaustive permutation reference and relabeled copies. The
independent verifier additionally compares **all1,099 labeled simple graphs on
one through five vertices** against its own unpruned reference implementation.
No WL/hash equality substitutes for any exact result.

The verifier independently checks every saved gzip checksum/size and parses both
archives; replays both geometry outputs, the two explicit geometry rejections,
the accepted pair and both schedules; and uses a separate level-set flood to
check distances/static connectivity. It does not retry the failed75-node
canonicalization or certify the incomplete M candidate.

Machine-readable evidence: [verification](../results/phase1_5b0/independent_verification.json),
[archive checks](../results/phase1_5b0/archive_verification.json),
[source/runtime provenance](../results/phase1_5b0/provenance.json),
[summary](../results/phase1_5b0/summary.json).
Raw JUnit XML remains outside Git at
`results/runs/phase1_5b0_test_evidence/full_suite.xml`, with its SHA-256 in verification.

## Frozen-history integrity

All previously tracked public result files were byte-hashed before generation
and matched after generation and the full regression suite. The six historical
JSON episode inventories contain exactly **2,212** records: representative6,
Phase1.1 development30/diagnostic24, Phase1.2 development288, Phase1.3 development
1,792/corridor72. Existing regression tests replay those stored expectations;
the verifier also checks their original bytes. No historical metric, source,
parameter lock, manifest or result file was edited.

The Phase1.4 parameter lock remains
`ecdd2f11e0c279bfa6c8557fcc646c4f714d2c7627deb731cbb366138a64d2f1`;
its assessment manifest remains
`6335b77dd5838b2ea312d3293c939354e0b7f454eccbc679f0c59d4fe031c822`.
The [integrity inventory](../results/phase1_5b0/historical_integrity.json) stores
per-file checksums and record counts. This is not a new replay of all13,440
Phase1.4C or1,680 Phase1.4D research traces.

## Interruption and storage record

An initial startup attempt failed in partial-artifact serialization before
start/goal assignment. Its evidence is preserved under ignored
`results/runs/phase1_5b0_failed_startup_compact` and
`results/runs/phase1_5b0_failed_startup_raw`. The serialization fix has a dedicated
regression test. The corrected audit uses one pinned source identity; its first
four candidate identities are unique. Verification replays are reported separately,
not counted as newly independent candidates.

The corrected audit took8.692 seconds and peaked at216,664 KiB RSS (211.59 MiB)
including exact-search storage, in Ubuntu WSL on an Intel Core i5-1035G1 host.
Its two bulk gzip artifacts occupy3,630 bytes
under ignored `results/raw/phase1_5b0_development`: one complete R world with two
schedules, and one M geometry without a certified topology or pair/schedules.
Every archive path/size/SHA-256 is in the
[storage manifest](../results/phase1_5b0/trace_storage_manifest.json).
Invalid B/V outputs have candidate identities/reasons and deterministic rejection
replay rather than complete accepted-world artifacts.

## Reproduction and stopping

In the repository's existing Ubuntu WSL environment:

```sh
.venv-wsl/bin/python -m pytest -q -p no:cacheprovider
.venv-wsl/bin/python scripts/verify_phase1_5b0.py
```

The audit runner is development-only, requires new designated output/archive
directories and refuses overwrite. Do not rerun it over the saved audit or
continue past its canonicalization stop without review. The verifier is read-only
with respect to research artifacts and writes only its compact verification report.
Review an exact-backend improvement, preserving the equivalence relation and
independent reference checks, before another artifact audit. No filter/controller,
policy experiment or Phase1.5C work is authorized by this negative audit.
