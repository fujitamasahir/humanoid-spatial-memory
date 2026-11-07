# Phase 1.4B frozen development tuning validation

Executed 2026-11-06 on macOS / Apple Silicon, Python 3.12.16, pinned project
dependencies in `/tmp/phase13-venv`. Branch `feature/phase1-4b-tuning`, created
from freshly fetched `origin/feature/phase1-4a-implementation` at
`46253fe14b1e980031f75bea7e4338d45f3a1955`.

**Development tuning only.** Exactly 3,780 prescribed episode executions completed.
No assessment/held-out episode or Phase 1.4D ablation matrix was executed, and
no assessment outcome was accessed. No policy, estimator, baseline, metric,
parameter grid, realization or selection criterion was changed in response to
outcomes. These training-set scores do not establish generalization, statistical
superiority, novelty or physical safety.

## Preflight and frozen execution

Read the [Phase 1.4 protocol](phase1_4_experimental_protocol.md) and
[Phase 1.4A validation](phase1_4a_validation.md). No experiment-changing ambiguity
or inconsistency was found. Before changing the execution adapter, all per-file
source hashes, combined source hashes and canonical configuration hashes in the
Phase 1.4A tuning manifest, smoke and benchmark artifacts matched. The immutable
input file is `results/phase1_4a/manifests/tuning.json`, SHA-256
`99ba8664625cbcadcf8450a9f96558e122c6ecbc4b71c77f7676ec29d0625a45`.
The original file and all Phase 1.4A artifacts remain unchanged.

The manifest has 35 distinct canonical environments, seven families with five
environments each, and **22 unique layout clusters**. No new seed selection or
manifest generation was performed. All candidates see the same environments,
known pose/goal, sensor and per-time noise streams. Noise is zero, radius 3,
occlusion enabled, optimistic unknown handling, deadline 40, cost 1.5 per call,
and total sensing caps 2/4/8 including initialization. Four methods × nine
candidates × 35 environments × three caps = 3,780; each candidate has 105 repeated
measurements and each method has 945. Parameter values and full model defaults
are explicitly recorded in the lock.

The only pre-existing source edit is a guard-preserving extraction of the common
instrumented episode body in `protocol_evaluation.py`. The original public smoke
entry point still rejects tuning/assessment; the new tuning adapter admits only
verified records from the pinned manifest, the four methods and frozen candidates.
No policy or movement code was edited. Policies still receive only public inputs;
world schedules, truth, visibility labels and partition metadata stay with the
evaluator. All assessment/held-out input paths are rejected before opening them
by the new runner. The approved tuning path has no assessment execution mode.

## Runner, interruption and trace integrity

`run_frozen_tuning.py` constructs a deterministic 3,780-job plan. Every job is
identified by a hash of method, candidate, full parameters, environment/layout,
family, seed and cap. A run identity freezes the plan, pinned manifest, configuration,
source hash, Python/platform and dependencies. Resume rejects a changed identity.
A single-writer lease prevents concurrent writers.

Every complete original episode payload (metrics, full decision/action/memory
frames, evaluator geometry/people, received observations and feasibility samples)
is serialized into its own gzip JSON file. Compression changes representation
only: no fields, frames or labels are dropped. Gzip headers fix filename/mtime;
wall-clock measurements inside records naturally differ on a fresh replay.
Temporary writes are flushed/fsynced before atomic publication, followed by a
directory fsync. Completed episodes are never overwritten or rerun on resume.

Recovery can adopt a complete staged checkpoint without reexecuting it. Torn
uncommitted files are moved intact to a quarantine with hash/size/reason, not
silently deleted; their episode may then be retried. Conflicting or duplicate
complete records stop execution. Inventory detects unknown IDs, filename/body
mismatches, missing jobs and metric/trace ledger conflicts. These recovery paths
are tested with synthetic data; no actual tuning checkpoint was torn or retried.
An interruption inside an uncommitted episode cannot preserve its wall-clock
timing: “exact resume” preserves committed bytes and deterministic scientific
semantics, not a nonexistent mid-step checkpoint.

Before the full run, a real integration session committed two prescribed tuning
jobs. A zero-new-episode resume verified their hashes unchanged and reexecuted
zero episodes. The final session executed the remaining 3,778, reusing those two.
Thus **2 + 0 + 3,778 = 3,780 actual tuning executions**, not 3,782 or a second matrix.
One untimed synthetic warm-up per method was performed in each executing session;
those are public-memory calls, not tuning environments. Progress logs contained
only completion counts and elapsed runtime. Scores were selected only after every
prescribed job was committed. Full traces were never accumulated across episodes
in memory; only compact metrics and hash inventories are retained between files.

## Locked global parameters and development scores

Selection version `phase1.4b-equal-family-cap-lex-v1` uses exact rational means:
within each family/cap average five environments, then equally average the 21
family/cap strata. Rank by descending contact-free completion, descending goal
completion, ascending observations, ascending elapsed steps, then the parameter
tuple in the frozen table's column order. Cost is reported but is not an added
selection criterion. Balanced strata make these means numerically equal to the
105-episode aggregate; no realized-cost or success-conditioned subset was selected.

| Method | Selected tuned parameters | Contact-free /105 | Goal /105 | Mean observations | Mean cost | Mean steps |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| fixed-rate | entropy_threshold=0.85, fixed_rate=0.05 | 50 (47.62%) | 52 (49.52%) | 3.276 | 4.914 | 28.657 |
| route-weighted | route_threshold=0.85, route_weight=1 | 46 (43.81%) | 51 (48.57%) | 4.229 | 6.343 | 28.257 |
| disruption-visible | budget_price=0, disruption_threshold=0.4 | 39 (37.14%) | 45 (42.86%) | 1.000 | 1.500 | 29.029 |
| query-gate-conceptual | reliability_threshold=0.8, visibility_fraction=0.25 | 45 (42.86%) | 53 (50.48%) | 3.010 | 4.514 | 27.600 |

The selected disruption-visible candidate made **one initialization observation
and no later granted observation in all 105 of its tuning episodes**. It therefore
has static-map behavior on this tuning sample. This is a retained negative/design
finding under the frozen rule, not a policy repair or a reason to change thresholds.
Its selected budget price is zero. Other candidates, failures and defaults remain
visible below; there is no claim that the most complicated heuristic is necessary.

All selections are global per method, not family/cap-specific. The following
comparison tables include every candidate. Candidate 4 is the frozen default for
each method; the selected row is marked “selected”. Tuples follow the protocol's
column order. Denominators count repeated executions, not independent worlds.
No confidence intervals or significance tests are computed from tuning outcomes.

### fixed-rate

Parameter tuple: `(fixed_rate, entropy_threshold)`.

| Candidate | Parameter tuple | Contact-free /105 | Goal /105 | Mean observations | Mean cost | Mean steps |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 0 | (0.01, 0.65) | 45 | 51 | 1.381 | 2.071 | 28.200 |
| 1 | (0.01, 0.75) | 45 | 51 | 1.248 | 1.871 | 28.600 |
| 2 | (0.01, 0.85) | 39 | 45 | 1.229 | 1.843 | 29.029 |
| 3 | (0.05, 0.65) | 46 | 50 | 4.067 | 6.100 | 28.210 |
| 4 default | (0.05, 0.75) | 49 | 53 | 3.781 | 5.671 | 27.752 |
| 5 selected | (0.05, 0.85) | 50 | 52 | 3.276 | 4.914 | 28.657 |
| 6 | (0.15, 0.65) | 38 | 43 | 4.610 | 6.914 | 29.467 |
| 7 | (0.15, 0.75) | 38 | 42 | 4.581 | 6.871 | 29.676 |
| 8 | (0.15, 0.85) | 43 | 49 | 4.295 | 6.443 | 28.590 |

First differing rank component between selected candidate 5 and next-ranked candidate 4: **contact-free mean**. Exact rational scores and complete rank keys for all candidates are stored in the lock.

### route-weighted

Parameter tuple: `(route_weight, route_threshold)`.

| Candidate | Parameter tuple | Contact-free /105 | Goal /105 | Mean observations | Mean cost | Mean steps |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 0 | (1, 0.65) | 41 | 47 | 4.610 | 6.914 | 28.552 |
| 1 | (1, 0.75) | 43 | 47 | 4.448 | 6.671 | 28.933 |
| 2 selected | (1, 0.85) | 46 | 51 | 4.229 | 6.343 | 28.257 |
| 3 | (3, 0.65) | 38 | 43 | 4.610 | 6.914 | 29.467 |
| 4 default | (3, 0.75) | 43 | 47 | 4.476 | 6.714 | 28.762 |
| 5 | (3, 0.85) | 45 | 49 | 4.257 | 6.386 | 28.552 |
| 6 | (9, 0.65) | 38 | 43 | 4.610 | 6.914 | 29.467 |
| 7 | (9, 0.75) | 39 | 43 | 4.476 | 6.714 | 29.705 |
| 8 | (9, 0.85) | 45 | 49 | 4.276 | 6.414 | 28.400 |

First differing rank component between selected candidate 2 and next-ranked candidate 5: **contact-free mean**. Exact rational scores and complete rank keys for all candidates are stored in the lock.

### disruption-visible

Parameter tuple: `(disruption_threshold, budget_price)`.

| Candidate | Parameter tuple | Contact-free /105 | Goal /105 | Mean observations | Mean cost | Mean steps |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 0 | (0.025, 0) | 36 | 42 | 2.029 | 3.043 | 29.714 |
| 1 | (0.025, 0.1) | 38 | 44 | 1.848 | 2.771 | 29.238 |
| 2 | (0.025, 0.4) | 39 | 45 | 1.438 | 2.157 | 29.019 |
| 3 | (0.1, 0) | 39 | 45 | 1.448 | 2.171 | 29.000 |
| 4 default | (0.1, 0.1) | 39 | 45 | 1.448 | 2.171 | 29.010 |
| 5 | (0.1, 0.4) | 39 | 45 | 1.286 | 1.929 | 29.029 |
| 6 selected | (0.4, 0) | 39 | 45 | 1.000 | 1.500 | 29.029 |
| 7 | (0.4, 0.1) | 39 | 45 | 1.000 | 1.500 | 29.029 |
| 8 | (0.4, 0.4) | 39 | 45 | 1.000 | 1.500 | 29.029 |

First differing rank component between selected candidate 6 and next-ranked candidate 7: **lexicographic parameter tuple**. Exact rational scores and complete rank keys for all candidates are stored in the lock.

### query-gate-conceptual

Parameter tuple: `(reliability_threshold, visibility_fraction)`.

| Candidate | Parameter tuple | Contact-free /105 | Goal /105 | Mean observations | Mean cost | Mean steps |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 0 selected | (0.8, 0.25) | 45 | 53 | 3.010 | 4.514 | 27.600 |
| 1 | (0.8, 0.5) | 36 | 42 | 1.524 | 2.286 | 29.714 |
| 2 | (0.8, 0.75) | 39 | 45 | 1.448 | 2.171 | 29.000 |
| 3 | (0.9, 0.25) | 42 | 50 | 3.305 | 4.957 | 28.229 |
| 4 default | (0.9, 0.5) | 36 | 42 | 1.771 | 2.657 | 29.714 |
| 5 | (0.9, 0.75) | 39 | 45 | 1.448 | 2.171 | 29.000 |
| 6 | (0.97, 0.25) | 41 | 48 | 3.581 | 5.371 | 28.590 |
| 7 | (0.97, 0.5) | 36 | 42 | 2.029 | 3.043 | 29.714 |
| 8 | (0.97, 0.75) | 39 | 45 | 1.714 | 2.571 | 29.000 |

First differing rank component between selected candidate 0 and next-ranked candidate 3: **contact-free mean**. Exact rational scores and complete rank keys for all candidates are stored in the lock.

## Lock, independent validation and reproducibility

[parameter_lock.json](../results/phase1_4b/parameter_lock.json) contains all eight
public parameter fields for every selected method, all 36 grid candidates,
exact/decimal scores and tie-breaks, source files/hash, canonical configuration
and hash, pinned tuning manifest hash, episode counts, selection version,
Python/platform/packages, run identity and hashes of the metric/score/storage
artifacts. Lock creation is exclusive and content-addressed by
[parameter_lock.sha256](../results/phase1_4b/parameter_lock.sha256); it is locally
read-only. Re-publication accepts identical bytes only and refuses changes.
This is an application/content-integrity lock, not an unbreakable filesystem or
cryptographic signature against a person deliberately rewriting repository data.
The Git commit provides the reviewed version boundary for later assessment.

`validate_frozen_tuning.py` independently loads saved metric records into SQLite,
checks all method/candidate/family/cap strata contain five environments, recomputes
integer totals and exact fractions, and selects using independent integer-total
rank keys (equal denominator 105). It does **not** call the producer's selection
function. It agrees with all four winners and all 36 candidate score records.
It verifies every full trace checksum, size, job/config identity and saved metric
agreement one episode at a time, and rejects missing/extra/duplicate trace files.
The [verification record](../results/phase1_4b/independent_verification.json) reports
3,780 episode records and 3,780 trace hashes verified, with 35 environments and
22 layout clusters. No second matrix was executed for this validation.

Lock SHA-256: `ecdd2f11e0c279bfa6c8557fcc646c4f714d2c7627deb731cbb366138a64d2f1`.

Generating source-manifest SHA-256: `b324b9ca0ec28eaba8dee5e040d5063f0c66def28229f6b28a6c2799417e75ad`.

Generating HEAD is the Phase 1.4A parent, with dirty=true, because the runner was
implemented before final commit. Every algorithm/source/configuration hash is
locked; this is not a claim that artifacts contain their own eventual commit SHA.
No lock will be modified based on later assessment outcomes. Any approved future
protocol change must produce a separately versioned lock and preserve this one.

## Runtime, storage and retained artifacts

The execution/checkpoint loops totaled **71.906 seconds**. From first committed checkpoint to final lock publication, wall time was **100.083 seconds**, including integration/resume checks and final inventory/export. Independent full validation took **9.678 seconds**. The loop includes scheduler/simulation/metrics and per-episode JSON/gzip/fsync writes, but excludes initial source verification and final inventory/compact export. These timing measurements describe this machine/run only.

All 3,780 full traces are retained locally: **44,107,109 compressed bytes** (42.06 MiB), versus **845,106,479 uncompressed JSON bytes** (805.96 MiB). Uncompressed sizes are the gzip ISIZE totals; each individual payload is under 390,192 bytes, well below the modulo limit. Filesystem block/directory usage is approximately 49 MiB. No trace was deleted, truncated, sampled or replaced by a summary.

Full trace files stay under the existing ignored directory
`results/raw/phase1_4b_tuning/` rather than adding 3,780 binary files to Git.
The compact metrics/score/lock/provenance/inventory artifacts total approximately
17 MiB and are retained in Git. No multi-gigabyte artifact is committed.

- [episodes.csv](../results/phase1_4b/episodes.csv) and
  [episodes.jsonl](../results/phase1_4b/episodes.jsonl): all 3,780 execution results,
  with method/candidate/parameters/cap/environment/layout identities and all metrics.
- [candidate_scores.csv](../results/phase1_4b/candidate_scores.csv) and
  [candidate_scores.json](../results/phase1_4b/candidate_scores.json): every candidate,
  including failures and default configurations.
- [trace_storage_manifest.json](../results/phase1_4b/trace_storage_manifest.json):
  all relative per-episode paths, compressed sizes, SHA-256 values, run/input
  identity and the absolute local storage root. Repository-relative storage root
  is recorded for transport; preserve this directory separately when cloning/moving.
- [preflight.json](../results/phase1_4b/preflight.json),
  [run_provenance.json](../results/phase1_4b/run_provenance.json),
  [runner_integration.json](../results/phase1_4b/runner_integration.json) and
  [storage_runtime.json](../results/phase1_4b/storage_runtime.json): audit records.

Local storage root:
`/Users/masahir0/Desktop/humanoid-spatial-memory/results/raw/phase1_4b_tuning`.
A Git clone alone does not include these full traces. Copy/archive the complete
raw directory alongside the compact inventory to preserve byte-identical timings
and checkpoints. A fresh simulation replay reproduces scientific decisions and
scores; timing-containing compressed file hashes will naturally differ.

Exact commands (Python 3.12 with the unchanged pinned requirements):

```bash
.venv/bin/python scripts/run_frozen_tuning.py --max-new-episodes 2
.venv/bin/python scripts/run_frozen_tuning.py --max-new-episodes 0
.venv/bin/python scripts/run_frozen_tuning.py
.venv/bin/python scripts/validate_frozen_tuning.py
.venv/bin/python -m pytest -q
```

Actual commands used `/tmp/phase13-venv/bin/python` and
`MPLCONFIGDIR=/tmp/phase13-mpl`. Windows replaces the Python executable as usual,
but **the writer lease currently uses POSIX `fcntl`**; the new runner is validated
on macOS, not Windows. A Windows locking adapter would need review before use;
no weaker concurrency mechanism is silently substituted. The existing policies
and experimental mathematics do not depend on the lease implementation.

The default runner resumes the retained run, skipping complete checkpoints. To
perform an intentional fresh reproduction without touching the published lock,
use separate artifact roots through the Python API (not executed in this phase):

```python
import sys
sys.path.insert(0, 'scripts')
from run_frozen_tuning import ROOT, load_tuning_manifest, run_matrix
run_matrix(load_tuning_manifest(ROOT),
           ROOT/'results/raw/phase1_4b_reproduction',
           ROOT/'results/runs/phase1_4b_reproduction')
```

An alternative raw directory copied from this run can be checked with
`validate_frozen_tuning.py --trace-root /path/to/phase1_4b_tuning`. The loader still
accepts only the existing pinned tuning manifest, not an arbitrary JSON substitute.

## Final checks and limitations

The complete suite passes **183 tests**, with 14 existing Matplotlib/pyparsing
deprecation warnings. All metrics across 2,212 historical Phase 1.0–1.3 records
remain unchanged. New tests cover the pinned input gate, all nine candidates per
method, exact balanced selection and tie ordering, atomic immutable artifacts,
exclusive leases, missing/duplicate/conflicting records, complete-stage adoption,
torn-file preservation and zero-reexecution resume. The real two-job integration
check precedes the remaining full execution. Existing Phase 1.4A regression and
public-input isolation tests also pass after the adapter extraction.

All old configurations, baseline/policy code, environment generators, research
protocols and Phase 1.0–1.4A results remain unchanged. No reserved outcome source
was loaded by the runner/validator. Historical regression tests and synthetic
unit fixtures are validation activity, not new assessment or ablation experiments.

These selected configurations have been optimized on the same 35 development
realizations used for the tables. Twenty-two related layout clusters and repeated
caps/candidates limit independent information; 3,780 is an execution count, not a
sample size for generalization. Visibility/confidence proxies remain uncalibrated,
last-write memory and zero sensor latency are unchanged, and the query gate is
conceptual rather than a faithful ALONE reproduction. Full traces require separate
local transport; end-to-end Windows execution remains unvalidated. No scientific
protocol ambiguity or data-integrity disagreement remains unresolved in this run.

Stop before Phase 1.4C assessment and Phase 1.4D ablations for a separate review.
