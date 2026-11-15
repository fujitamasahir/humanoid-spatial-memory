# H2 Comprehensive Benchmark Model Registry

Machine-readable model records, including each source commit and SHA-256, are
in `results/phase2_mujoco/h2_comprehensive_benchmark_v1/protocol/model_registry.json`
and `.csv`. Rebuild them with:

```sh
.venv/bin/python scripts/build_h2_comprehensive_registry.py
```

The source and fixed arm/mode fields in the registry identify the original
implementation to be evaluated. Runtime adapters may route calls into those
unchanged implementations; they must not alter policy logic. The common memory
sensor, emergency safety sensor, selected-action collision shield, environment,
and H2 limits are bound separately in the experiment binding.

The registry contains the 13 previously evaluated H2 arms and all 44 requested
additional names. The additional set currently has 41 arms eligible under
their own prior evidence gates. C-Route3 and C-RouteK have no valid no-benefit
fixture authorization under the shared candidate-coverage gate, and
C-Topology3-c has an invalid C-v2c gate; all three are registered as blocked.
They are not silently replaced. Their status must be reconsidered only after
the owning gate is resolved through its existing protocol.

Some names intentionally overlap implementations or behavior. For example,
the ternary C comparison must not automatically be described as a distinct
algorithm from C0 until their decision traces have been checked side by side.
The report will preserve all requested rows while identifying any verified
equivalent implementations or identical observed behavior.
