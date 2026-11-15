# H2 Full Spatial Memory Replay Schema v1

One deterministic gzip JSON object per episode. The top level preserves the
underlying H2 replay fields and adds `dataset`, `condition`, `map_identity`,
`schedule`, `seed`, `source_binding`, and `replay_recovery`.

Every entry in `steps` is an s0 or post-transition frame and retains the source
replay's event, objects, pedestrians, ground truth, robot pose, path, memory,
observation, emergency scan, shield, contacts, and terminal data. It adds:

- `spatial_memory_before_observation_decision_packed_2bit_base64`
- `spatial_memory_before_observation_update_packed_2bit_base64`
- `spatial_memory_after_observation_update_packed_2bit_base64`
- `spatial_memory_end_of_step_packed_2bit_base64`
- `observed_grid_ternary_packed_2bit_base64` and observed cell/value pairs
- `controller_state_before_decision`, `controller_state_after_decision`,
  and `controller_state_after_observation_update`
- `selected_action`, `executed_action`, and separate shield rejection/outcome

Ternary grids are row-major y-then-x, values -1/0/1 encoded by the frozen H2
two-bit packer. An absent pre-controller s0 state is `null` with an explicit
status. The index records file path, compressed bytes, SHA-256, map and source
hashes, frame and observation counts, outcome, parity status, and replay
availability. Existing indices are never rewritten.
