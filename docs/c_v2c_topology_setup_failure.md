# C v2.0c protocol v1 setup failure

Protocol v1 and its source freeze were pushed at `368583d`. Its first runner
invocation stopped during import because the runner imported an unused,
undefined `TopologyEVIParameters` symbol. The exception occurred before its
correctness precheck, fixture construction, exhaustive EVI preflight, or any
candidate-arm execution. It accessed no FIT, admitted-world, or protected
Phase 1.5 data. The exact attempted command and failure are recorded in
`results/phase2_mujoco/c_v2c_topology_v1/setup_failure.json`.

No candidate result was observed. Per the versioning rule, the import defect is
corrected in a new protocol and output version (`v2`); the v1 source freeze and
failure record remain unchanged. The v2 suite keeps the same algorithm,
fixtures, seeds, definitions, and numerical gates. Any v2 policy outcome is
reported separately and cannot overwrite v1.
