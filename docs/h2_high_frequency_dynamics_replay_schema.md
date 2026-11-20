# H2 High-Frequency Replay Schema v1

Each episode file is UTF-8 JSON compressed with gzip. Its `.json.gz` basename
is `episode_NNN_<arm>.json.gz`. Coordinates are integer `[x,y]`, x increases
east, y increases north, origin `[0,0]` is the lower-left grid cell. The
physical cell center is `((x-12)*0.75,(y-12)*0.75)` meters in world x/y. Yaw
is radians counterclockwise from Unitree G1 local +X (east). Step 0 is s0 before
the first navigation transition; steps 1..80 are after pedestrian advance and
object change, then sensing/decision/action.

Top-level keys:

- `schema_version`, `episode_key`, `arm`, `map`, `schedule`, `seed`, `grid`,
  `coordinate_convention`, `static_walls_xy`, `start_xy`, `goal_xy`,
  `initial_robot`, `initial_objects`, `initial_pedestrians`, `steps`,
  `outcome`, `metrics`, `engine_specification`.
- Each step stores `step`, `event`, `objects_before`, `objects_after`,
  `pedestrians_xy` with stable pedestrian IDs, robot position/world pose/yaw
  before and after action, executed action, planned path, observation
  requested/granted/count, full ternary `spatial_memory`, observed cells and
  values, ground-truth static-plus-object occupancy, emergency scan and
  intervention, selected-action shield rejection/contact evidence, and goal
  state.
- Ternary grids use row-major y-then-x order and values `-1` unknown, `0`
  observed free, `1` observed occupied. They are packed four 2-bit values per
  byte after mapping `-1/0/1` to `0/1/2`, least-significant value first, then
  base64 encoded. Ground-truth occupancy grids are row-major bits packed by
  `numpy.packbits(bitorder="little")`, then base64 encoded. Grid shape is in
  the top-level `grid` field; consumers can reconstruct all 625 values without
  simulator access.
- `event` contains event type, object ID, from/to cells, counts before/after,
  robot cell/yaw at generation, complete object states before/after,
  pedestrian positions, connectivity/exclusion/geometry validation, random
  stream ID, candidate rejection counts, and generation duration.
- Relocation preserves object ID; deleted IDs are never reused. `no_op` is an
  explicit recorded exception; s0 uses `initial_state` and is not counted as a
  change.

Reconstructing the replay requires applying each step's explicit `objects_after`
and recorded robot/environment states in order. The replay has no dependency on
Python, MuJoCo, hidden schedule queries, or a seed-only reconstruction.
