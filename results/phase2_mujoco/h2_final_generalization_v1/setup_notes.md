# Pre-freeze setup notes (no unseen maps/outcomes accessed)

Initial pytest invocation referenced nonexistent tests/test_rdao_v2.py; no tests
ran. Original log/XML retained; corrected to existing test_rdao_v2_viewpoint.py.
163 related tests then passed; final163-test run repeated after plumbing edits.

One-case public FIT plumbing checks exposed the evaluator's plan import is local
to run_episode, so timing now uses its existing _planner injection hook. A
list/tuple representation mismatch in saved RDAO traces was resolved by applying
the existing JSON normalization before semantic comparison. These were harness
setup issues before freeze, not model changes or unknown-performance tuning.

The uncommitted binding draft is retained. Before any unseen draw, the geometric
admission design was changed from conservative full AABB turn BFS to an original
MuJoCo G1 sampled witness on the deterministic shortest point path: an AABB turn
bound can reject valid narrow-corridor G1 turns. No unknown map or navigation
outcome informed this prospective design correction. Final source binding and
protocol specify the adopted witness exactly; draft is not an evaluation gate.

15-minute report schedule uses America/Denver local time; hard stop19:30,
2026-11-15T02:30Z, with a five-minute experiment shutdown reserve.
