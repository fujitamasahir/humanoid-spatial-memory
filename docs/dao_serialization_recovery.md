# DAO formal artifact serialization recovery

The first formal invocation used prospective freeze
`11e6568a85ea837696923e3ec98ee541d3b016e4`. It executed the state loop but failed
when writing decisions.json: NumPy int64 known-cell counts are not directly
serializable by the standard JSON encoder. The process exited1 before any
usable formal rows, summary or final manifest were saved. The zero-byte
output remains in `synthetic_serialization_failure/`; its correctness/binding
inputs remain in `prepared_prefreeze_serialization/` and protocol_binding_v1.json.
No PASS status is inferred for the lost first invocation.

Repair changes only the run harness artifact boundary: recursively serialize
NumPy scalar values to their equal Python scalar values. Add a regression
that roundtrips an actual assessment/decision row. No DAO policy, geometry,
reference calculation, fixture, constant or numerical decision changes.
Original policy/fixture fingerprints must remain identical. Re-prepare the
correctness gate and commit the revised harness/binding BEFORE one replacement
formal invocation. This is a documented engineering recovery, not a parameter
iteration, navigation screen or response to an efficacy outcome. Report two
formal process invocations (one incomplete output, one replacement), never
claim the complete workflow executed without an initial failure.
