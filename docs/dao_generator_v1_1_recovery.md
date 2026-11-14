# TEST generator v1.1: connectivity validation correction

Post-run structural audit of the12 TEST v1 payloads found4 disconnected free
rasters after the optional off-certificate3x3 occlusion island. The reserved
start/goal G1 certificate stayed valid, but that certificate did not establish
whole-layout free-space connectivity. This is a generator/validator defect,
not evidence about DAO efficacy. All v1 code,12 TEST payloads/logs and results
remain preserved. No production population existed or was opened.

New dao_generator_v1_1.py preserves v1 separately, rolls back an optional island
if it disconnects the free raster, records applied/rejected treatment flags,
and validates whole-raster free connectivity in addition to the original
through-event conservative G1 certificate. It also validates initial heading.
No layout parameter, sensing policy, DAO constant or statistical criterion is
optimized. TEST:v1_1 lineage labels distinguish the correction evidence; the
same explicitTEST seed101 is used for structural regression, not independence.

13 targeted tests cover4 families×3 dimensions and a hand-created disconnected
pocket. Commit code/tests before regenerating only the12 corresponding TEST
engineering payloads into a new correction directory. Production entry points
remain disabled. Unapplied occlusion treatment is reported as missing coverage,
not silently labeled an occlusion success. Corrected connected geometry still
needs complete admission, scaling/graph-edit review, approved opaque signatures,
validated environment distributions and independently enforced custody before
any production pilot. No navigation or statistical simulation rerun is needed.
