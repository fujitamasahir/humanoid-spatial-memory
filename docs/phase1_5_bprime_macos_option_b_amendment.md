# Phase 1.5 B′ prospective macOS Option B resource amendment

Identifier **phase1.5-v0.4-MACOS-RSS-B1**, adopted 2026-11-07 before any new
registered generation. Scientific population remains `phase1.5-v0.4-BPRIME-1`.
Base: `f654004930658ca1349fb16c9a1ac8c9f8dd3f15`.

The user's attached authorization explicitly selects Option B and authorizes
implementation, validation, historical certificate completion, independent
reference sealing and the frozen development workflow in order. Existing frozen
documents, old policies and all historical evidence remain unchanged. This new
amendment supersedes only the Linux/native-platform and preventive hard-memory
clauses for new macOS execution; it does not retrospectively certify earlier work.

## Normative policy

- Use the already pinned ARM64 pynauty 2.8.8.1 / nauty 2.8.8 build. Preserve C3
  encoding, ordered colors, canonical labeling, near operations, serialization
  and namespace `phase1.5-v0.3-CANON-1`, conditional on exact compatibility tests.
- The parent uses a monotonic five-second deadline starting before worker
  startup/request serialization. Native stalls, incomplete replies and late
  output are killed/reaped. Teardown latency is logged separately.
- RSS acceptance threshold is **536870912 bytes**, inclusive. This is measured
  resource acceptance, **not preventive kernel enforcement**.
- Parent sampling method: macOS libproc `proc_pid_rusage(pid,RUSAGE_INFO_V2)`
  `ri_resident_size`, bytes. Sample at startup, before accepting each reply,
  and at a nominal maximum interval of **0.010 seconds** while awaiting output.
  Log actual monotonic sample offsets, gaps and values; OS scheduling can delay
  samples. Do not claim an interval or physical-usage upper-bound guarantee.
- Worker reports independent `getrusage(RUSAGE_SELF).ru_maxrss` lifetime peak in
  Darwin bytes on every complete reply. Require integer valid positive evidence,
  matching request/profile/pin identity and threshold compliance. Parent current
  observations must not exceed worker lifetime peak, allowing only sampling
  timing ordering (final parent sample precedes reply acknowledgement).
- Parent-observed excess, worker lifetime-peak excess, missing/malformed evidence,
  sample failure, crash, timeout or source/pin conflict returns **no certificate**,
  terminates/reaps the worker and stops the audit. Use explicit resource-excess,
  resource-evidence, timeout, crash and integrity classifications. No heuristic
  fallback, silent retry, changed candidate seed or substitute world.
- Retain parent samples and worker peaks for every call, plus failure context,
  termination status and termination-time child rusage (`wait4`) where available.
  A short unobserved spike can be missed by sampling. Worker lifetime peak can
  detect an earlier spike after it ends, but cannot prevent transient excess.
  A failed worker without a complete peak report remains failure, never assumed
  below threshold. Conflicting evidence stops rather than dropping a sample.
- Reusing a serial worker retains its lifetime high-water mark. Separate workers
  have separate PID/request/sample histories. No Python signal handling inside
  native C is relied on for timeout or memory termination.
- Scientific RNG/state and candidate order are unchanged. Exact replay concerns
  saved scientific decisions and output bytes, not wall times or observed RSS.
  Committed checkpoints are adopted without reexecution. An interrupted attempt
  without a complete checkpoint stops for review; no automatic scientific retry.

## Validation and downstream gates

Before registered generation require focused synthetic normal/excess/native/
transient/crash/timeout/evidence/concurrency/recovery tests, unchanged C3 bytes,
completed verified historical keys and a sealed independently checked inventory.
Included references remain exactly 110 original +2258 admitted identities;
2276 rejected-valid identities remain nonreferences. Source raster interpretations,
ancestry and aliases must be pinned. Inventory self-hashing alone is not review.
Publish independent verifier checks and seal content only after they pass.

The user authorizes routine continuation through passed gates. R/BP/V/M laws,
Philox framing/streams, 80-million development ranges, 48/24/24 quotas and 10000
candidates/mechanism/partition remain frozen. Quota exhaustion stops. Preserve
all rejected and failed records. No parameter selection based on outcomes.

Development artifact stages proceed fit then calibration then selection; later
navigation/model work requires complete population and all other frozen numerical
and integrity gates. Assessment/final-held-out remain inaccessible until their
separate prospective conditions/authorization are satisfied. This amendment
neither declares Phase 1.5 complete nor authorizes Phase 2 automatically.
