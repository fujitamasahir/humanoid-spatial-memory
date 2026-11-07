# Phase 1.5B-0 development manifest review

2026-11-07. **Provisional/incomplete manifest.** The artifact audit obtained
one fit cluster, not the required48/24/24 development population. Generation
stopped at an exact-canonicalization guard; neither later partition started.
This is a feasibility failure of the current exact backend under its declared
guard, not a navigation result or evidence against the proposed sensing method.

## Counts and acceptance

| Partition | Target total (R/B/V/M) | Certified provisional clusters (R/B/V/M) | Status |
| --- | --- | --- | --- |
| Fit |48 (12/12/12/12) |1 (1/0/0/0) | Stopped |
| Calibration |24 (6/6/6/6) |0 (0/0/0/0) | Not started |
| Selection |24 (6/6/6/6) |0 (0/0/0/0) | Not started |

| Mechanism | Fit attempts | Accepted clusters | Rejected geometry | Uncertified at resource stop |
| --- | ---: | ---: | ---: | ---: |
| R |1 |1 |0 |0 |
| B |1 |0 |1 connectivity |0 |
| V |1 |0 |1 seed separation |0 |
| M |1 |0 |0 |1 exact labeling |

Observed accepted-cluster fractions are R1/1, B0/1, V0/1, M0/1; aggregate1/4.
Scientific geometry rejection is2/4 and an additional1/4 is computationally
uncertified. These tiny fractions are not estimates of population acceptance
probabilities. Calibration/selection rates are undefined, not zero acceptance.
No mechanism exhausted the10,000-candidate scientific limit. The stop occurred
earlier under the fixed five-second/100,000-node exact-search resource guard.
Consequently the target shortfall is computational, not proven sampler exhaustion.

The corrected audit contains exactly four distinct candidate identities, with
seed namespaces beginning50,000,000/50,010,000/50,020,000/50,030,000. No assessment
60-million or final70-million namespace was used. Unit-test fixtures and explicit
verification replays are not additional independent manifest candidates.

## Complete and incomplete artifacts

The sole complete artifact is `fit:R:50000000`, credited to R. It has25x25
geometry, an11-node normalized quotient, eight unique near keys, and base
start/goal shortest-path distance16. Start is(10,13), goal(4,5), Manhattan14;
all pair rules hold. Its two independently keyed schedules are removal and
moving occupancy. Their endpoint protection, timing, footprint/path validity,
initial/final static connectivity and exact replay passed independent checks.
These two schedules are **one** topology cluster, not two independent layouts.

The M archive contains raw geometry and its75-node normalized adjacency matrix
only. It has no successful exact certificate, no selected pair and no schedules;
it must not be admitted for any downstream experiment. B/V rejected before a
valid geometry artifact could be admitted. Their seeds/reasons are in the
compressed inventory and were replayed as the same rejections.

Graph-size and distance distributions are therefore limited to an accepted
singleton (11 nodes, distance16) and an uncertified M geometry (75 nodes). The
[measurements](../results/phase1_5b0/canonicalization_measurements.json) retain
the larger historical/small-variant search data; do not manufacture development
quantiles or success estimates from it.

The provisional
[development manifest](../results/phase1_5b0/development_manifest.json) explicitly
sets `full_protocol_ready=false`, `provisional=true` and
`navigation_authorized=false`. It is evidence of attempted construction, not a
data partition approved for model fitting.

## Inventory, storage and verification

Compact versioned evidence:

- [Run summary](../results/phase1_5b0/summary.json): counts, rejection reasons,
  runtime, RSS, stopping cause and readiness.
- [Candidate inventory](../results/phase1_5b0/candidate_inventory.jsonl.gz): every
  corrected-run identity, outcome, timing and available artifact checksum.
- [Source/RNG provenance](../results/phase1_5b0/provenance.json): source hashes,
  selected user clarifications and technical guards.
- [Historical certificates](../results/phase1_5b0/historical_topology.json) and
  [integrity inventory](../results/phase1_5b0/historical_integrity.json).
- [Bulk storage manifest](../results/phase1_5b0/trace_storage_manifest.json),
  [archive verification](../results/phase1_5b0/archive_verification.json) and
  [independent verification](../results/phase1_5b0/independent_verification.json).

Bulk geometry/construction/schedule/near-certificate payloads remain outside Git
in `results/raw/phase1_5b0_development`; both gzip files use deterministic mtime0
and their SHA-256 values were rechecked. Compact manifests contain quotient
matrices/exact keys and references rather than bulk full-raster inventories.
The accepted raster plus fixed four-neighbor rule represents its raw labeled
cell graph; an extra large unlabeled raw-cell certificate is not claimed.

One failed startup session is preserved in ignored `results/runs` as described
in [validation](phase1_5b0_generator_validation.md). It was an implementation
logging failure before a complete first candidate, followed by a tested fix;
it is not hidden as successful generation. Corrected-run source hashes match
the committed implementations. All saved candidate artifact checksums, two
rejected-candidate replays and the accepted complete-world replay passed.

The existing regression suite ran only under the user's explicit verification
exception. All231 tests passed;2,212 historical record bytes and expected metric
regressions remain unchanged. No new research navigation/tuning/assessment/
ablation/held-out/MuJoCo matrix ran. No G/filter/controller/policy code was added.

## Historical and future independence limits

The accepted R component is disjoint under the specified exact/near/raster
relation from110 certified stored historical raster interpretations. There are
no empirical new cross-partition tests because later partitions never started;
cross-partition rejection is mathematically unit-tested only.

The raw metadata scanner flags a benchmark result with no scenario arrays.
Source inspection identifies public memory workloads rather than missing world
scenarios; [the independence report](phase1_5b0_topology_independence_audit.md)
explains the distinction and an optional public-array recovery remedy. No
unknown benchmark cell was invented as true occupancy. No claim covers reserved
old held-out worlds or unavailable historical states.

Assessment/final population sizes, cross-split collisions, acceptance probabilities,
dynamic-category proportions and transitive-merging behavior remain unverified.
There is no statistical independence claim based on seed uniqueness, and a
future successful development run alone would not certify assessment separation.

## Readiness decision

**Not ready to support Phase1.5C development.** The next review should resolve
exact-canonicalization scalability while preserving the approved equivalence
definition, and confirm historical metadata scope. Only after a complete new
artifact audit reaches all48/24/24 clusters and passes verification should these
partitions be locked for future use. No smaller manifest, skipped mechanism,
extra candidate allowance or favorable sampling change is silently substituted.
Commit this implementation and negative audit evidence, then stop for review.
