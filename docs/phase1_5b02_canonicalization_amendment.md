# Phase1.5 v0.3-CANON-1: approved canonicalization and resource amendment

2026-11-07. User approval in Phase1.5B-0.2 adopts the representation proposed in
[the B-0.1 review](phase1_5b01_canonicalization_review.md), conditional on production
correctness/resource checks. This document is the formal amendment; all v0.2
documents, original literal source and historical evidence remain unchanged.

## Exact mathematical relation

Keep the raster-derived2x2 room contraction, degree-two corridor suppression,
pure-cycle/single conventions, undirected multigraph loops and multiplicities,
leaf deletion, one-nonloop-edge contraction with residual parallel edges becoming
loops, and subsequent suppression exactly as v0.2. Coordinates, seed, mechanism,
events, start/goal and corridor lengths never become graph colors. Lineage,
raster symmetries, intersecting near sets and transitive unions retain their
original semantics; reject cross-partition/historical relations. Samplers,
probabilities, streams, candidate order, quotas and scientific limits do not change.

Encode normalized graph G as a colored undirected simple graph E(G): original
vertex v has color `(0, G[v,v])`; each positive off-diagonal unordered pair
{u,v} has exactly one new vertex of color `(1,G[u,v])`, joined to u and v.
No edge node exists for a zero pair. Order color classes by their numeric pair.
An original isomorphism extends uniquely to edge vertices, preserving all colors.
A color-preserving encoded isomorphism restricts to original vertices and
preserves loops and each pair's multiplicity. Therefore G≅H iff E(G)≅E(H).

Use nauty's canonical-position-to-input `lab` array, retain original vertices in
that order, then serialize original n, diagonal, upper-triangle row-major.
This matrix is a relabeling of G; encoded canonical invariance makes it identical
on isomorphic inputs. Conversely equal matrices exhibit an isomorphism. Thus

`C2(G)=C2(H) iff G≅H iff C3(G)=C3(H)`.

C2 and C3 bytes generally differ. Equality is required within versions only.
Prefix the namespace string `phase1.5-v0.3-CANON-1` as the **first** array entry
before n and integer matrix entries. Canonical key bytes are compact JSON arrays,
UTF-8, decimal integers, separators comma/colon without whitespace or newline;
the namespace uses literal ASCII. This namespaced prefix distinguishes versions
without changing equivalence. Full arrays decide equality, not a SHA digest.
Storage JSON may be pretty-printed; checksums cover actual stored bytes.

Historical comparison keys are regenerated exclusively from the110 permitted
stored matrices into `results/phase1_5b02/historical_topology.json`. Every near
variant is regenerated under C3; never compare C2 bytes against C3 or rename old
keys. Old files remain immutable. Historical scope remains stored physical-raster
interpretations, not unstored states or reserved held-out worlds. The original
benchmark-memory metadata flag is retained and explicitly scoped as previously
reviewed public memory arrays, rather than silently counted as missing worlds.

## Backend and dependency pin

[Pinned configuration](../configs/phase15_nauty_backend.json) records
pynauty2.8.8.1, nauty2_8_8 and SHA-256 for every installed Python/native artifact
used by the isolated backend, plus its C wrapper/header. Dependency files remain
outside Git under `results/runs/phase1_5b01_dependencies`; hash mismatch fails
before import. The compiled extension hash pins actual native code. Configuration,
production parent/worker source and runtime versions are additionally frozen in
preflight/audit provenance. The wrapper uses DEFAULTOPTIONS, undirected graph,
explicit ordered partition (`defaultptn=FALSE` when colored), and
`getcanon=TRUE` through `canon_label`; no tuning of search options is exposed.
Coloring and Python iteration are explicitly ordered. Upgrading dependency,
platform build, option, encoding or serialization requires revalidation/version
review; no cross-build canonical-byte compatibility is assumed.

## Approved technical guards

The old literal backend retains **five seconds or100,000 nodes**. The nauty
backend replaces that guard with **five wall-clock seconds per call and512 MiB
peak RSS per isolated worker**. Native nodes are unavailable and recorded null;
the old node ceiling is neither claimed nor silently retained as satisfied.

Linux workers set soft and hard `RLIMIT_AS=536870912` bytes before dependency
import. This is a deliberately conservative stronger bound: resident mapped
memory cannot exceed process virtual address space. Linux refuses mappings/heap
growth beyond the hard address-space limit; a stack-growth or native allocation
failure can terminate the worker. The parent treats either error output or
process death as a failed call. This is **not** reliance on Linux's unenforced
RLIMIT_RSS, and is not merely periodic RSS sampling. The worker reports its
`ru_maxrss` high-water mark and both limits after every completed call; the parent
rejects absent/incorrect/out-of-range evidence. Address-space overhead consumes
part of the512 MiB allowance, so a workload can fail below512 MiB RSS.

The supervisor uses nonblocking input/output and an absolute five-second deadline
starting before worker startup (on the first call) and request serialization.
It can SIGKILL and reap native C execution, including partial-output stalls;
Python signal delivery inside C is not required. JSON framing, reply namespace,
request identity and returned permutation must validate. Timeout, memory error,
crash, broken pipe, malformed/oversized output or late response yield no key,
kill/reap the worker and stop the audit. There is no heuristic fallback or retry
of the failed candidate. Successful calls may reuse one serial isolated worker;
the hard limit persists and peak RSS covers its entire lifetime.

Actual WSL enforcement must pass touched-page exhaustion, native-library sleep,
partial-output timeout, crash and invalid-output tests before any audit. Source
hashes are frozen after these tests and exact-reference preflight. Candidate
generation then uses a new POSIX-locked output/archive namespace with atomic
fsync/replace writes and per-candidate durable checkpoints. Old failed audit
evidence and B/V rejected identities remain intact. Only development fit48,
calibration24 and selection24 are authorized; no navigation or held-out generation.

Sources: [Linux getrlimit documentation](https://man7.org/linux/man-pages/man2/getrlimit.2.html),
[nauty/Traces](https://pallini.di.uniroma1.it/), and
[pynauty source](https://github.com/pdobsan/pynauty). The installed wrapper source
and kernel behavior are checked locally; enforcement evidence and limitations
are reported in the production validation, not assumed from documentation alone.
