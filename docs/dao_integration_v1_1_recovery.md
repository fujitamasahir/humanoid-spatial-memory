# v1.1 integration recovery: occupied public route start

Initial freeze82f0f2d completed36 formal navigation episodes and90 fixture scans,
then failed on the pedestrian scene's first DAO-Veto episode in diagnostic
route preparation. The public point planner permits starting at a remembered
occupied cell, while frozen DAO's optional-route validator rejects occupied
cells anywhere in the supplied prefix. Sensor projection/previous pedestrian
readings can produce this public state; it must NOT be erased using true robot
occupancy. The failure traceback and36/90 saved artifacts remain in engineering/.
The failed episode's in-memory prefix was not saved and is not fabricated.

Keep the v1 adapter, runner, policy, geometry, constants and scene definitions
unchanged. New dao_navigation_compat_v1_1.py and run_dao_integration_v1_1.py
supply an empty optional route when a computed prefix crosses remembered
occupancy (normally its start). The frozen no-route semantics then apply;
all occupancy/timestamps and non-route rules remain unchanged. Diagnostics
use the same guard and mark route unavailability. One public point A* per
Route decision is still counted. No real geometry or extra sensor query.

Regression compares the compatibility decision against frozen DAO with an
explicit missing route and retains the occupied map cell, then runs the actual
pedestrian scene for Veto and Route in tests. Commit the new compatibility
source/binding/passing tests before resuming. The recovery executes only the
12 missing navigation episodes and30 remaining fixture scans in a separate
engineering_recovery_v1_1/ directory. The36 earlier saved episodes are hash-
verified and referenced, not rerun or overwritten. The complete engineering
matrix has48 unique completed episodes, plus1 incomplete formal attempt.
Pre-freeze unit probes are counted separately. No efficacy-based tuning or
scene revision; CAA/DAO originals and the initial source freeze are preserved.
