# Phase 1.5 B′ recovery fix and same-fit continuation provenance

This is an implementation/storage correction, not a scientific protocol change.
User authorization: fix the isolated recovery regression, verify synthetic
recovery/continuation, and preserve the same saved 313-candidate fit run.
No sampling law, RNG purpose/seed, topology equivalence, reference membership,
quota, candidate allowance or navigation/evaluation definition changes.

## Isolated correction

After recovery publishes a fully staged record, `Coordinator.restore()` must
refresh its verified rows before returning them or constructing the publication
cache. The recovered decision is applied exactly once. The next builder receives
the next identity; it never regenerates the recovered candidate. Tests cover
all five complete-publication boundaries, return values, restored sequence,
no extra complete world, and continued publication. Torn/incomplete stages,
changed/deleted records and conflicting locks still fail closed.

## Preserve the original execution

The original fit used source commit
`2dcadbef876195b43bab6d3ef0da84151c498348` and run ID
`e6dc13518f0cb32516f9827a3a2536659c583a6ecacc165a0011a396dabb8690`.
The 313 checkpoints, 313 receipts, original binding and original `run.json`
remain unchanged. Old validation failures and stop reports remain immutable.
A fix cannot be installed under that source commitment by replacing its hash.

A separate continuation binding and writer store therefore carry new source
commitments. The new binding pins a sorted original-file manifest, its original
run ID/binding and immutable source commit. `ReadOnlyPrefix` verifies original
source bytes against that Git snapshot, all original configuration/dependency/
reference commitments, the original lock, every checkpoint/receipt byte, and
all saved candidate evidence. It never opens an original writer. The approved
prefix root is read-only input; it cannot overlap a permitted writer store.

The original decisions are reconstructed as **the same fit partition**, not as
historical references or fresh samples. They retain their original order,
lineage, components, mechanism credits and candidate counters. Each continuation
record has the new immutable store/run ID; the original records keep their
original IDs. The binding links the epochs. Source and record validation are not
bypassed to accommodate the old source pin.

The expected initial state is 313 attempts, R/BP/V/M counters 24/14/263/12,
current credits 12/12/0/12. The next identity is
`phase1.5-v0.4-BPRIME-1:fit:V:80020263`, sequence 313 (candidate 314).
No record is copied into the new writer store or resampled. Full-file prefix
integrity is checked before each new decision. Missing or changed original
files, omitted prefixes, mixed-run records and order conflicts stop execution.

## Verification and execution gates

`scripts/phase15_macos_recovery.py prepare` creates new metadata only, preserving
all original bindings. The append-only production registry must be committed
before it can authorize the new binding. `verify` forbids registered stream and
world constructors, checks the reference inventory and original prefix, creates
only a separate continuation lock, reconstructs same-fit state, and reports the
next identity without drawing it. Synthetic tests also cover crashes followed
by recovery and the next decision across both epochs.

`execute` requires the exact successful verification report to be committed and
match the current binding. It reconstructs state again before any draw and uses
only the frozen next candidate order. CPU/storage accounting includes the prior
execution; the existing 30 CPU-hour/15-GB development limits are not reset. It
stops on quota completion, candidate allowance, resource failure, integrity error
or unresolved interruption. No retry or substitute candidate is introduced.
Calibration/selection and navigation are not enabled by this runner; a completed
fit still needs its independent/visual gates. Reserved assessment/final-held-out
remain inaccessible. There is no Phase 1.5/Phase 2 completion claim.

New writer root: `results/raw/phase15_bprime_fit_recovery_1/store`.
Original read-only prefix: `results/raw/phase15_macos_development/fit`.
New verification/execution reports: `results/phase15_bprime_recovery`.
