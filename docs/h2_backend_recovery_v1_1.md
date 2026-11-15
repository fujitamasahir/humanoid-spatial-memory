# H2 pre-generation backend restoration v1.1

The original frozen generator exited before its first random draw because the
historical local native-build directory no longer exists. FIT864 exact model
replays had already passed; no unseen map/performance was accessed. Original
failure log and inventory are retained in generation_setup_failure_v1/.

Restore ONLY dependency location/native build: the existing local pinned-version
pynauty2.8.8.1 / nauty2_8_8 is copied into a versioned H2 backend package, with
new native SHA256 and a separately pinned resource profile. Python wrapper
source bytes match historical wrapper hashes. The native binary differs from
the old missing build; do not assert identical binary provenance. Existing
worker/encoding/monitoring source files are unchanged and hash pinned.

Before drawing any new map, require exact canonical-key reproduction for EVERY
available archived FIT checkpoint topology matrix with a saved exact key,
including loops and multigraph structure present there (at least36). Any mismatch
stops. Record count and hashes. This is a mathematical compatibility check, not
proof of the historical build's missing binary or a preventive hard RSS limit.

The recovery wrapper, this amendment and new backend pin must be committed
before it runs. The original model/generator/source gate remains mandatory;
no original source or binding is edited. It injects only the backend constructor
with the new pin, then executes the unchanged frozen H2 generator. Original
seeds, streams, admission thresholds, map order and analysis remain fixed.
No resampling, navigation/admission optimization or policy adjustment occurs.
This is an environment/dependency repair expressly permitted by the owner's
bug-repair rule, prospectively recorded before any unknown draw.
