# Phase 1.5 B′ macOS memory-limit root-cause investigation

2026-11-07. Base `74935d2597bfd9cd53d6defae182001d03a7deb4`, branch
`feature/phase1-5-bprime-macos-c3`. Disposable unprivileged resource probes only.
**The hard 512-MiB whole-worker gate remains BLOCKED.** No production admission,
resource-policy change, registered candidate generation or historical replay.
The existing native backend and its pins are unchanged; its full 4,534-graph
compatibility suite was not repeated.

## Exact failure: valid arguments, kernel EINVAL

Initial RLIMIT_AS values read through both Python and libc were
`(9223372036854775807,9223372036854775807)` (Darwin unlimited). The request was
exactly `(536870912,536870912)`; soft equals hard, and neither exceeds the
inherited hard limit. Direct libc setrlimit returns -1 with errno 22 (EINVAL).
Limits stay unlimited. Thus the failure is not Python rejecting the argument
order, an inherited low hard limit, or an attempted privilege increase.

CPython 3.12.16 maps any setrlimit EINVAL to the generic ValueError text
`current limit exceeds maximum limit` after the system call. That wording is
misleading for this case; it does not establish that requested soft>hard.
[Exact CPython source](https://github.com/python/cpython/blob/v3.12.16/Modules/resource.c).

Mach task_info in fresh Python children reports roughly 420 billion mapped
virtual bytes while RSS is about 14–15 million bytes. A minimal dynamically linked
ARM64 C child, without Python, reports 419,910,352,896 virtual bytes and 1,015,808
resident bytes, and also rejects the 512-MiB request with EINVAL. This rules out
Python overhead as the essential obstacle. The probe does not identify every
mapping or attribute all mapped space to one subsystem.

Apple's XNU RLIMIT_AS path calls vm_map_set_size_limit and returns EINVAL when
existing usage exceeds the proposed limit. This agrees with the measurements;
the upstream source is explanatory evidence, not a claim to have inspected the
installed kernel binary. [Apple XNU implementation](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/kern/kern_resource.c).

## Calls and controls

Full exact per-process values, errno and before/after readings are retained in
[diagnosis.json](../results/phase1_5_bprime_macos_memory/diagnosis.json).

| Disposable probe | Requested soft/hard | Observed result |
| --- | --- | --- |
| Python API then direct libc | 536870912 / 536870912 | Python ValueError; libc -1/EINVAL; unchanged limits |
| Direct libc only | 536870912 / 536870912 | -1/EINVAL; unchanged limits |
| Soft-only reduction | 536870912 / unlimited | -1/EINVAL; unchanged limits |
| Python large-VM control | 420447535104 / 420447535104 in saved run | Success, exact readback |
| Minimal C absolute cap | 536870912 / 536870912 | -1/EINVAL; existing virtual map 419910352896 |
| Minimal C VM slack | 419977461760 / 419977461760 | Success; equals existing virtual map +67108864 |
| C 128-MiB mmap after VM-slack cap | Allocation 134217728 bytes | MAP_FAILED/ENOMEM (12); no pages committed |
| Self-task physical-footprint API | new_limit_mb=512 | Mach return 8, `(os/kern) no access`; no limit established |

The larger control uses a per-child computed baseline; ASLR/runtime maps cause
its exact numeric value to vary. Its success and the C mapping rejection show
that resource calls are not categorically blocked in this execution environment,
and demonstrate kernel VM enforcement at that larger limit. They do not establish
an absolute 512-MiB resident-memory ceiling. Reserving less *additional* VM is
not equivalent: existing reservations may acquire resident pages later.

Every modification is confined to a disposable child. Parent limits are compared
before and after and remain unchanged. No privileged or unsandboxed command was
requested. An unsandboxed baseline was not collected. Therefore the sandbox's
possible contribution cannot be ruled out completely; the below-existing-map
kernel rejection is demonstrated within this environment. Likewise, the footprint
API's no-access result does not isolate sandbox versus ordinary privilege checks.

## Allocation behavior and C3 admission

Separate children attempted the same cap before controlled 64-MiB touched Python
bytearrays, native malloc/memset, and anonymous mmap allocations. All limit requests
failed with EINVAL; all three diagnostic allocations succeeded and increased RSS.
These bounded probes demonstrate actual allocation paths, not enforcement.

The limited-C3 probe fails its cap prerequisite and explicitly refuses to execute
native C3 under unlimited memory while calling it capped. Normal C3 execution
under an absolute 512-MiB hard cap is therefore **not demonstrated**. Existing
uncapped validation-only compatibility evidence remains valid but does not pass
this resource gate. No canonicalization, search-option or namespace change is
needed to explain this failure.

## Alternatives and minimum prospective decision

`task_set_phys_footprint_limit` is present in the SDK and was tried only for the
child's own task. It returned no access. Apple's implementation requires a
footprint privilege check where supported; other builds can return failure.
No root request, entitlement change, helper service or system-wide setting was
attempted. Also, physical footprint and RSS are distinct metrics; even a future
successful footprint limit would need explicit policy review and validation.
[Apple task implementation](https://github.com/apple-oss-distributions/xnu/blob/main/osfmk/kern/task.c).

No acceptable whole-worker 512-MiB hard guarantee has been demonstrated with the
available unprivileged interfaces on this host. This is a scoped result, not
proof that no possible macOS arrangement can enforce a useful memory budget.
RLIMIT_DATA, custom nauty allocators, post-call peak checks and periodic RSS
sampling do not supply the required whole-process hard guarantee. launchd-style
rlimit settings do not make the same below-existing-VM cap usable merely by
moving its setter. No such alternative was installed or selected.

Smallest scientifically defensible prospective amendment if retaining this
ordinary macOS process model:

- Preserve the five-second parent deadline, task/algorithm semantics, all keys,
  distributions, seeds, quotas and exclusion rules.
- Explicitly replace the *preventive hard resident bound* with a *measured peak
  resource acceptance criterion*: successful workers must report/independently
  validate peak RSS≤536870912 bytes. A parent watchdog may terminate observed
  violations, with overshoot and sampling latency explicitly unbounded by this
  criterion. Collect termination-time resource evidence even for failed workers;
  do not discard violations or substitute candidate outputs.
- Freeze the precise measurement, watchdog, failure and incomplete-run rules
  before testing/adoption. A footprint metric cannot silently replace RSS.
- State plainly that this is weaker operational containment than the original
  Linux guard. If preventive whole-process enforcement is nonnegotiable, keep
  production blocked pending a separately reviewed mechanism rather than adopt
  this amendment.

This is a recommendation only; no amendment or watchdog is implemented here.

## Verification and reproduction

12 focused deterministic diagnostic tests passed in 0.91 seconds. They cover
Python/libc parity, inherited limits, exact requests, minimal-C controls, native/
Python/mmap touches, denied footprint API, unchanged parent limits, and unchanged
C3 source/native pins. The tests do not run registered worlds or the full
certificate-comparison suite. A different target-host result requires fresh
resource review rather than automatically enabling production.

Diagnostic implementation additions:
`scripts/diagnose_phase15_macos_memory.py`,
`scripts/native/phase15_macos_vm_probe.c`, and
`tests/test_phase15_macos_memory_diagnosis.py`. The native helper binary stays
ignored under `results/runs/phase15_macos_memory`; its source/build command,
compiler and SHA-256 are pinned in the report. The compiled helper is a disposable
instrument, never linked into or used as a replacement for nauty.

```sh
/usr/bin/clang -arch arm64 -O2 -Wall -Wextra -Werror \
  scripts/native/phase15_macos_vm_probe.c \
  -o results/runs/phase15_macos_memory/vm-probe
PYTHONDONTWRITEBYTECODE=1 /tmp/phase13-venv/bin/python \
  scripts/diagnose_phase15_macos_memory.py \
  --native-probe results/runs/phase15_macos_memory/vm-probe \
  --output /private/tmp/new-memory-diagnosis.json
PYTHONDONTWRITEBYTECODE=1 /tmp/phase13-venv/bin/python -m pytest \
  tests/test_phase15_macos_memory_diagnosis.py -q -p no:cacheprovider
```

Use a fresh output path; the diagnostic refuses overwrite. Frozen protocols,
Linux pins, previous reports, historical evidence, 65 incomplete near-key records
and provisional inventory are unchanged. Stop for resource-policy review; no
inventory sealing, production enabling or experiment authorization follows.
