# H2 Comprehensive Benchmark Protocol v1 — Amendment 1

This amendment corrects only the runner's representation of the two already
saved schedule indices. The H2 `scenario_from_bprime` API accepts the original
zero-based indices `0` and `1`; the frozen schedule payloads and event contents
remain unchanged. The binding's mistaken `[1, 2]` labels caused an attempted
index `2` to stop the initial smoke stage after 82 valid episodes for schedule
index `1`. Those 82 files are preserved byte-for-byte and reused as index `1`
under this amendment. They are not rerun.

The comprehensive smoke and primary matrices now use schedule indices `[0, 1]`.
Map identities, two-map smoke selection, seed, policy arms, sensors, safety,
step limit, environment engine, and all scientific settings are unchanged.
The original preregistration binding is retained; an append-only binding
amendment records the correction and parent binding hash. A smoke gate requires
exactly the full eligible-arm × two-map × two-schedule × two-condition set.

This is a runner label/index correction before primary evaluation, not a
protocol or policy change. No primary episodes had started at amendment time.
