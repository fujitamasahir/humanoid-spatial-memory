# C v2.0c Corrected Topology Candidate Selection Protocol — v2

**Frozen before policy outcomes:** this version is committed before the v2
formal screen. It versions the runner setup repair after v1 stopped at import;
the policy, fixtures, seeds, metric definitions, and gates remain unchanged.
Formal screen directory:
`results/phase2_mujoco/c_v2c_topology_v2/`.

The complete frozen method and gate are specified in
[`phase2_c_v2c_topology_protocol.md`](phase2_c_v2c_topology_protocol.md).
The v2 source changes remove an unused import of an undefined symbol and
version the runner, reviewer, output destination, and source fingerprint list.
V1's initialization failure remains preserved as
historical evidence in `docs/c_v2c_topology_setup_failure.md` and
`results/phase2_mujoco/c_v2c_topology_v1/setup_failure.json`. V2 does not
change or regenerate the 48 fixed fixtures, any ranking logic, comparisons,
acceptance criteria, or the intervention protocol.
