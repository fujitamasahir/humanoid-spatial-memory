# H2 Comprehensive Benchmark Protocol v1 — Amendment 2

The initial Original primary stage stopped at the first persistence-aware arm.
The shared timing adapter had asserted that its cumulative last-write
observation log must equal the controller's navigation map. Persistence-EVI
intentionally exposes a projected navigation grid while retaining the exact
last-write grid in its underlying Age controller; those representations can
legitimately differ. The assertion therefore rejected valid model state.

The adapter correction now checks the logged observations against the
controller's last-write base memory when a persistence belief is present, and
continues to leave the projected memory grid as the planner input. It changes
no observation, decision, navigation, safety behavior, metric, or replay field.
The fix is scoped to the new comprehensive run via a separately committed
source hash and binding amendment.

All 545 committed episode files from the interrupted stage remain unchanged
and are resumed by hash-verified path. The failed B+Age attempt produced no
episode checkpoint and is not counted. No high-frequency primary episode had
started when this amendment was made.
