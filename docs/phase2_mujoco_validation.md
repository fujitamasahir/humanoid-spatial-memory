# Phase 2 MuJoCo kinematic proxy validation

Date: 2026-11-08

## Status and scope

This implementation establishes a bounded MuJoCo scene adapter and performs a
saved-fit replay. It does **not** complete the requested Unitree G1 integration.
The machine had no G1 assets, and GitHub DNS resolution failed when fetching
Google DeepMind's MuJoCo Menagerie. Its upstream G1 description is documented as
a simplified MJCF model under BSD-3-Clause:
<https://github.com/google-deepmind/mujoco_menagerie/blob/main/unitree_g1/README.md>.
No upstream robot files were copied into this repository. The simulation uses
an explicit capsule humanoid proxy instead.

MuJoCo 3.17.0 was installed into the project `.venv` on macOS arm64 with Python
3.12.10. The MuJoCo release provides macOS wheels; the official release notes
are at <https://github.com/google-deepmind/mujoco/releases>. No training or GPU
was used.

## Implemented adapter

- `src/spatial_memory/mujoco_navigation.py` maps grid `(x,y)` to MuJoCo `(X,Y)`
  with Z vertical and 0.75 m per grid cell. Cell scale is an explicit uncalibrated
  modeling assumption; Phase 1.5 worlds do not encode metric dimensions.
- Each saved wall becomes a 2.5 m tall box; persistent obstacles become 0.9 m
  boxes. Event cells are predeclared and moved into/out of the scene as MuJoCo
  mocap bodies as the saved event timeline advances.
- Pedestrian traces are evaluator-side mocap capsules. A six-geom capsule/sphere
  humanoid proxy is positioned at the existing grid waypoint.
- The existing sensor, memory controller, A* planner and `World.move` remain the
  action/policy path. They receive occupancy observations and never receive the
  evaluator's `World`, obstacle classes, future pedestrian positions, or events.
- Evaluator-only callbacks synchronize saved truth to MuJoCo at each recorded
  pose. MuJoCo pose contacts and temporary blocked-target overlap queries are
  separate from 2D blocked movement attempts and grid dynamic contacts.
- The root pose is set kinematically. MuJoCo does not simulate gait, actuators,
  balance, foot placement or collision response. Pedestrians do not react to the
  robot. The contact-free proxy metric is a geometry diagnostic, not a safety or
  locomotion metric.

The finite saved pedestrian paths are extended by reversing their interior so
the simulator can remain cyclic. A unit test verifies the original first 81
samples byte-for-value and cardinal adjacency through the loop boundary.

## Validation

The read-only runner loaded 36 admitted fit records (12 each for R, BP and M),
checked their checkpoint identities/payload digests, and rehashed the complete
preservation manifest's 836 original checkpoint/receipt files before and after
the runs. No fit or environment generator was called, and all Phase 1.5 files
remained unchanged.

The smoke run completed one periodic-policy episode in approximately 12 seconds
including the screenshot. It reached the goal, traveled 37 cells (27.75 m under
the assumed scale), used 16 observations including initialization, had 23 2D
blocked attempts, and recorded 24 MuJoCo wall-proxy pose contact pairs. It had no
grid dynamic contacts. This difference is evidence that the point-grid policy
does not enforce the proxy's spatial footprint.

The fixed replay ran 36 worlds × 2 schedules × 4 methods = 288 episodes in
4.22 seconds of measured episode-loop time (preservation preflight and result
hashing are excluded; the full replay does not render video).
Results:

| Method | Goal completion | Mean observations | Blocked attempts | Grid dynamic contacts | MuJoCo wall pose contact pairs | Proxy contact-free completion |
|---|---:|---:|---:|---:|---:|---:|
| Static | 4/72 (5.6%) | 1.00 | 5,117 | 0 | 4,591 | 0/72 |
| Periodic | 57/72 (79.2%) | 12.10 | 1,137 | 0 | 2,294 | 0/72 |
| Age | 55/72 (76.4%) | 12.60 | 1,215 | 0 | 2,308 | 0/72 |
| Uncertainty | 32/72 (44.4%) | 6.82 | 3,005 | 0 | 2,844 | 0/72 |

The success and observation counts reproduce the existing 2D pilot because the
2D policy/planner remains unchanged; they must not be reported as independent 3D
navigation performance. The MuJoCo pose contacts and attempted-target overlap
pairs are separately retained in the CSV. Unprefixed map-error metrics are
cell-samples over episode frames; `final_` columns are terminal counts, following
the existing evaluator definition.

The MuJoCo offscreen renderer could not open a CoreGraphics connection in this
headless environment. The smoke result therefore contains a Matplotlib 3D scene
image, `smoke_overview.png`, and the exact MJCF scene plus kinematic trajectory.
For an interactive MuJoCo scene viewer on a Mac Terminal with a GUI session:

```bash
.venv/bin/python -m mujoco.viewer --mjcf results/phase2_mujoco/smoke/scene.xml
```

This viewer loads the static scene model, not a trajectory playback.

## Tests and reproduction

The new tests cover coordinate round-trips, persistent event toggling and
MuJoCo contact generation, first-81 pedestrian samples, same-seed repeatability,
initial observation-budget accounting, and the controller/evaluator truth
boundary. The new tests plus existing 2D evaluation/regression files passed:
**138 passed, 14 upstream Matplotlib/pyparsing deprecation warnings**.

```bash
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pytest tests/test_phase2_mujoco.py -q
.venv/bin/python scripts/phase2_mujoco_navigation.py smoke
.venv/bin/python scripts/phase2_mujoco_navigation.py full
```

The progress CLI reports completed episodes, percentage, elapsed time and ETA;
it emits a 15-minute heartbeat even during a long episode. Outputs are
non-overwriting and include CSV/JSON, SHA-256 inventories, Python/MuJoCo
provenance, scenario identities, the fixed seed/settings and the 836-file
preservation check:

- `results/phase2_mujoco/smoke/`
- `results/phase2_mujoco/full/`

## Remaining work

1. Fetch and pin the upstream G1 MJCF/meshes plus license and per-file hashes;
   instantiate the actual G1 model and rerun smoke validation.
2. Decide and justify metric scale from a real map or robot dimensions.
3. Replace point-grid movement collision checks with a robot-footprint/traversability
   model before interpreting contact-free completion.
4. Add an observation interface driven by MuJoCo sensor geometry if true 3D
   sensing is intended; current sensing remains the frozen 2D occupancy sensor.
5. Add GUI or supported offscreen rendering for trajectory playback.
6. Review contact and map-error metrics before any confirmatory comparison.

No Unitree G1, physical walking, locomotion policy, statistical superiority,
real-world transfer, or human-safety claim is made.

## Actual Unitree G1 kinematic smoke (2026-11-08)

The historical proxy implementation and its result bundles above are preserved.
This section records the subsequent integration of the user-provided, committed
Unitree G1 model (`third_party/unitree_g1/`; upstream commit
`98a70c569c4c1b6da467a20012f766ee1f8dc521`). The G1 MJCF meshes resolve from
that directory. The runner pins every model file's size and SHA-256 in
`results/phase2_mujoco/g1_smoke/provenance.json`, along with the MJCF hash,
source hashes, Python and MuJoCo versions, and original fit-world identities.

The scene initializes the G1 `stand` keyframe, then places its
`floating_base_joint` at each existing grid waypoint without integrating robot
dynamics. Every candidate move is swept in ten substeps per grid cell against
the compiled G1 collision geometries before it can be accepted. The test fixture confirms that an
obstacle-intersecting target yields real MuJoCo contact and is blocked. Of the
model's collision geoms, only the eight 5 mm ankle-roll spheres are considered
intended foot-floor contacts. Any other G1 floor contact, plus wall, persistent
obstacle, pedestrian, or self contact, counts as unwanted.

One existing fit world was used: mechanism R, stored fit index 0, schedule 0,
seed 42, periodic observation controller, existing memory and A* planner, 80
step cap, and 0.02 second MuJoCo timestep. The grid scale remains the previously
documented, uncalibrated assumption of 0.75 m/cell. No Phase 1.5 or Voronoi
environment was generated. The smoke reached its goal in 60 environment steps
with 37 successful moves (27.75 m at the assumed scale), 16 observations
including initialization, and 23 ordinary 2D blocked attempts. There were 488
intended foot-floor pairs and zero unwanted contacts across 61 recorded poses.
The G1 collision query detected wall intersections among grid-blocked targets;
these targets remained blocked. This is a single kinematic waypoint smoke and
must not be described as walking or general 3D navigation performance.

The portable replay scene, trajectory, machine-readable validation report
(`validation_report.json`), and per-file artifact inventory are saved beside the
metrics. On a
macOS GUI session, animated playback is available with:

```bash
.venv/bin/python scripts/view_phase2_g1_navigation.py \
  --result-dir results/phase2_mujoco/g1_smoke --speed 0.25
```

A headless replay of all 61 frames had zero unwanted-contact frames. The current
execution context could not initialize the offscreen renderer because it lacked
a CoreGraphics connection; this does not prevent launching the viewer from a
normal Terminal GUI session. The 288-episode G1 matrix has not been run.

G1-specific regression tests: **9 passed**. The focused G1 and Phase 1.4C
evaluation/regression set passed **41 tests**. The whole repository suite was also
started but is blocked by pre-existing Phase 1.5 tests that require a native
artifact absent from this checkout at
`results/runs/phase15_macos_build/native-build/lib.macosx-11.0-arm64-cpython-312/pynauty/__init__.py`.
No Phase 1.5 data or native binding was changed. The failed test is unrelated to
the G1 integration.

## Heading control and MuJoCo 3D perception (2026-11-08)

This follow-up preserves the previous proxy and G1 result directories. It uses
the same admitted Phase 1.5 fit record, mechanism R / stored fit index 0 /
schedule 0, with periodic observations and seed 42. The robot's local +X axis
is the forward axis; the supplied MJCF model uses the Unitree/ROS convention
with Z vertical. A world-Z yaw quaternion is written to `floating_base_joint`
while the stand root height and all non-root keyframe positions stay fixed.
Stationary steps retain the prior yaw. Each maneuver checks the rotation at
increments no greater than 0.05 radians, then checks translation at increments
no greater than 0.075 metres. The first collision rejects the complete maneuver
and records `rotation_collision` or `translation_collision`.

The separate `MujocoRayPerception` backend attaches its ray origin to a site on
`torso_link`. The ray origin is 0.864 m high in the stand pose. The recorded
configuration is 6 m maximum range, 120 degree horizontal field of view, 61
rays, and 0.075 m sampling along each ray. The sensor calls MuJoCo's `mj_ray`
interface using the environment-only geom group and excludes the robot body.
Each ray stops at its first hit. Its visible path maps to free cells; the hit
geometry's current transformed location maps to one occupied grid cell; all
other cells remain unknown. The observation contains only -1/0/1 occupancy.
Geometry identity is used for evaluator diagnostics only, not passed to memory
controllers or A*. There is no occupancy-array shortcut and no future schedule
input to the perception backend. Ray casting is deterministic for a fixed scene
and pose; no random sensor noise is applied. The single horizontal sensing plane
does not model vertical scanning, depth-camera noise, or latency. Since the
robot is excluded from the ray query, self-occlusion is not modeled. Objects
that do not intersect the ray plane or finite ray set can remain unknown.

Twenty-two G1-specific regression tests cover all four cardinal headings and
quaternions, stationary heading retention, an intermediate rotation collision,
actual obstacle collision, wall occlusion, unknown cells, heading-dependent
visibility, moving pedestrians, persistent-object appearance/removal,
determinism, truth isolation, observation budgets, and the legacy 2D path.
The focused set of G1 and Phase 1.4C evaluator tests passed **54 tests**.

The actual end-to-end 3D perception smoke is saved under
`results/phase2_mujoco/g1_mujoco3d_heading_perception_smoke/`. It reached the
goal in 72 elapsed environment steps with 69 successful moves, 51.75 m at the
unchanged 0.75 m/cell assumption, and 19 observations including initialization.
It recorded 23 heading changes, three translation-collision rejections, and
zero unwanted pose contacts. The 61-ray sensor made 1,159 raycasts: 1,138
intersected geometry (1,056 wall hits and 82 persistent-obstacle hits; zero
pedestrian hits in this particular run). Across observations it classified 441
visible cells, 291 free and 150 occupied. The run had zero stale-map errors and
five terminal missed persistent changes; it does not claim perfect mapping.
The existing occupancy scale was not adjusted. No environments were generated,
and the runner rehashed the same 836 protected Phase 1.5 files before and after.

The output includes CSV, trajectory, portable scene, validation report,
environment/configuration provenance, model hashes, and source hashes. Headless
playback validation loaded all 73 trajectory frames with zero unwanted-contact
frames. The old `results/phase2_mujoco/g1_smoke` playback also loaded all 61
frames, with zero unwanted-contact frames. The saved playback applies each
frame's yaw and loops by default. Launch it on macOS with `mjpython`:

```bash
.venv/bin/mjpython scripts/view_phase2_g1_navigation.py \
  --result-dir results/phase2_mujoco/g1_mujoco3d_heading_perception_smoke --camera follow
```

The `.gitignore` now excludes the derived display-only
`results/phase2_mujoco/g1_smoke/scene_view.xml`; any existing local copy is kept.
The full 288-episode matrix has not been run.

## Research-integrity correction and 3D comparison (2026-11-08)

This section supersedes earlier statements above where they describe the
current G1 3D sensor or current research-integrity gate. Earlier result files
and text are historical and remain unchanged.

The G1 action path no longer calls `World.move()`, which consults oracle grid
occupancy. G1 moves are accepted or rejected only by the modeled MuJoCo
collision geometry (map-boundary checks use public grid dimensions). The
evaluator also no longer writes an occupied cell into controller memory when a
G1 footprint sweep blocks movement. A blocked maneuver is retained as an
evaluation metric only; it is not counted as a sensor reading and provides no
direct memory update. Controller memory changes only through the authorized
ternary observation refresh path. The controller is not given `World`, true
occupancy, obstacle identity, or future pedestrian traces. Ground-truth maps,
prescribed trace positions, and MuJoCo contact records remain evaluator-only.

Ray-hit occupancy is now rasterized from the measured first intersection
(`origin + direction * distance`), rather than from the hit geom's center.
Visibility ends at the first-hit distance; samples behind it remain unknown.
The hit cell therefore represents the discretized visible surface and may be
adjacent to the hidden geom-center cell. Cell boundaries use deterministic
nearest-center, half-up rounding with a small floating-point tie tolerance.
This reflects the recorded 0.75 m grid discretization and avoids exposing
sub-cell object centers. Walls, persistent objects, and pedestrian capsules
are ray-tested; the G1 is excluded, so self-detection is absent by construction.
The saved sensing settings are unchanged. The viewer derives display-only XML
that makes group-5 environment geoms visible; stored experimental scenes are
not edited.

New regression coverage checks that different hidden occupancy and the same
blocked maneuver do not change memory without an authorized observation, and
independently reconstructs occupied surface cells from ray intersection
distances. It also retains occlusion, unknown-space, heading, pedestrian,
persistent-change, no-self-detection, determinism, and display-scene checks.
The focused Phase 2 MuJoCo and Phase 1.4A evaluation set passed **58 tests**
with 14 upstream Matplotlib/pyparsing deprecation warnings.

With the corrected integrity path, the required fixed-seed smoke was run against
the first admitted saved fit world (`phase1.5-v0.4-BPRIME-1:fit:R:80000000`,
schedule 0, periodic controller), with the unchanged 80-step limit, 20-call
observation cap including initialization, 0.75 m/cell assumption, MuJoCo ray
perception, and G1 collision geometry. It **failed**: the robot stayed at its
start for all 80 steps because every planned translation was rejected by a G1
wall-footprint collision. It requested 20 observations, made 1,220 raycasts
(all first hits classified as walls), changed heading zero times, traveled 0 m,
and had zero unwanted pose contacts. The trajectory retained 648 intended
foot-floor pairs. Failure reason: `deadline_repeated_blocked_attempts`. The
controller did not receive collision-as-sensor updates; this keeps memory
perception-only but exposes a limitation in the current point-grid A* plus G1
footprint-check interaction. No environment, grid scale, or policy was tuned to
force a pass.

The failure report and reproducible artifacts are in
`results/phase2_mujoco/g1_integrity_mujoco3d_seed42_final_smoke/`. Its runner
rehashed all 836 protected Phase 1.5 checkpoint/receipt files before and after.
Headless trajectory validation loaded 81 frames with zero unwanted-contact
frames. The GUI viewer remains available through the documented macOS command;
the headless environment did not visually open a native GUI window.

Because this required smoke gate failed, the 36-world × 2-schedule × 4-method
comparison was **not launched**. There are no comparison estimates or claims
from this corrected implementation. In particular, no world-clustered paired
uncertainty analysis is reported. Resolve the blocked-footprint routing issue
under the same no-oracle, perception-only memory protocol and pass a new fixed
smoke before starting the matrix. The older 288 proxy result is historical and
must not be mixed with a future corrected 3D comparison.

## Ray boundary and G1 route recovery (2026-11-08)

This newer section supersedes the preceding smoke-gate status. The integrity
smoke's zero-free-cell result came from rasterizing the measured ray surface
with ordinary nearest-center rounding. For the observed adjacent wall, the G1
sensor was at 0.864 m and the wall face was 0.37875 m from its cell center.
The raster half-cell is 0.375 m, so that face protruded 0.00375 m into the
approach cell. All 61 rays hit that nearby wall and their measured surface
points were rounded into the robot's current cell; occupied status then erased
the short, genuinely free path from sensor origin to wall.

The sensor now excludes the first-hit endpoint from free-path samples and
directionally snaps measured surfaces within 0.005 cell of a raster boundary
to the cell on the far side. This tolerance is derived from the saved MuJoCo
environment box half-width (0.505 cell) and raster half-width (0.5 cell); no
geom center is read. At this grid scale, a cell with any first-hit surface
remains conservatively occupied, while the measured approach cell remains
free. Cells behind the first hit remain unknown. The revised first observation
at the original R fit start reports free at `(5,15)` and occupied at the
adjacent wall cell `(6,15)`. Conflicting free-path and surface evidence is
reported separately in sensor statistics.

G1 routing now uses a state `(grid position, cardinal heading)`. Its public
collision-geometry bounds measured from the pinned MJCF in stand pose are
0.218955 m along local X and 0.327997 m along local Y. The planner checks
four-cardinal translations and separate in-place turns against the agent's
observed occupied cells using those orientation-dependent bounds and the
documented 0.75 m cell boxes. It does not call the MuJoCo safety shield for
unattempted alternatives. The selected action alone is submitted to the shield;
the kinematic model can translate laterally or backward while preserving its
heading, then turn when known observations and the public footprint permit.

Rejected `(position, heading, action)` transitions are held separately from
occupancy memory. Each carries a signature of nearby agent memory; it is not
retried until a new observation changes that local evidence. No obstacle cell
is added to memory due to rejection. If the memory/footprint graph has no route,
the runner records a no-route step and waits for the configured observation
schedule or a relevant observed dynamic change. All four methods use the same
routing, footprint and selected-action safety rules; only their observation
schedules differ. Collision shield feedback is not charged as an observation
and exposes only accepted/rejected action plus contact reason/counts, not
obstacle identity.

The first footprint-planner smoke version reached 45 m but did not reach the
goal in 80 steps after broad observation changes repeatedly cleared old blocked
actions. Its failed outcome is preserved in
`results/phase2_mujoco/g1_g1footprint_feedback_seed42_smoke_v2/`. Restricting
reconsideration to changed local memory evidence removed that oscillation. The
subsequent smoke reached the goal in 68 steps with 55 moves (41.25 m), 18
observations, 10 rejected actions, 3 heading changes, no unwanted contacts,
zero terminal stale-map errors and 5 missed persistent changes. That result is
in `results/phase2_mujoco/g1_g1footprint_feedback_seed42_smoke_v3/`. The fixed
80-step, 20-observation budget and 0.75 m/cell assumption were unchanged.

The focused Phase 2 MuJoCo plus Phase 1.4A evaluation set passed **64 tests**
(14 upstream Matplotlib/pyparsing deprecation warnings). Coverage includes
wall-boundary assignment and approach free-space, first-hit surfaces,
occlusion/unknown cells, G1 footprint extents, orientation-specific clearance,
blocked-action suppression and local-evidence reconsideration, no-oracle
action acceptance, viewer visibility, and matched-design/world-clustered
analysis. The 288-episode comparison is pending the final clean-commit smoke
and provenance gate.

## Full G1 comparison (2026-11-08)

The post-fix fixed-seed smoke passed on the original saved R fit world, so the
288-episode matrix was run. It contains 36 admitted world identities (12 each
R/BP/M) × 2 saved schedules × 4 methods, all with seed 42, 80 steps, and a
20-observation cap including initialization. The experiment used source commit
`9b469d7e29cb1302786244b29d3ce18acc6813a8`, finished its episode loop in
106.95 seconds, and rehashed all 836 protected Phase 1.5 files before and after.
No environments or Voronoi layouts were generated.

Overall results (72 episodes per method):

| Method | Goal | Contact-free goal | Mean observations | Mean distance (m) | Mean steps | Rejected actions | Stale map cell-steps | Missed-change cell-steps |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Static | 32/72 | 32/72 | 1.00 | 17.86 | 64.71 | 1,890 | 661 | 11,293 |
| Periodic | 67/72 | 66/72 | 11.08 | 25.13 | 42.07 | 572 | 428 | 6,086 |
| Age | 57/72 | 57/72 | 11.56 | 24.55 | 45.08 | 733 | 394 | 6,959 |
| Uncertainty | 58/72 | 58/72 | 7.19 | 23.74 | 48.08 | 887 | 262 | 7,781 |

Actual observation use varied under the common cap. Periodic had 78 unwanted
pedestrian contact pairs across its runs; this left one of its 67 goal
completions non-contact-free. The other three methods recorded zero unwanted
pose-contact pairs. Periodic had four temporary no-route steps; the other
methods had none. Failed episodes are retained and recorded as
`deadline_before_goal`.
False persistent occupancy cell-steps were Static 57, Periodic 29, Age 35 and
Uncertainty 30. Missed-change counts remain substantial and are not interpreted
as perfect mapping. Distances use the unchanged, uncalibrated 0.75 m/cell
assumption. These are kinematic navigation results, not walking performance.

Mechanism sensitivity (24 episodes per method/mechanism):

| Mechanism | Method | Goal / contact-free goal | Mean observations | Mean distance (m) |
|---|---|---:|---:|---:|
| R | Static | 12/24 / 12/24 | 1.00 | 18.88 |
| R | Periodic | 24/24 / 24/24 | 10.21 | 23.06 |
| R | Age | 24/24 / 24/24 | 12.17 | 23.06 |
| R | Uncertainty | 22/24 / 22/24 | 6.46 | 23.69 |
| BP | Static | 14/24 / 14/24 | 1.00 | 16.81 |
| BP | Periodic | 22/24 / 22/24 | 10.04 | 23.44 |
| BP | Age | 20/24 / 20/24 | 10.00 | 21.72 |
| BP | Uncertainty | 20/24 / 20/24 | 6.92 | 22.19 |
| M | Static | 6/24 / 6/24 | 1.00 | 17.88 |
| M | Periodic | 21/24 / 20/24 | 13.00 | 28.75 |
| M | Age | 13/24 / 13/24 | 12.50 | 28.75 |
| M | Uncertainty | 16/24 / 16/24 | 8.21 | 25.34 |

Paired estimates average the two within-world schedule differences, then
bootstrap the 36 saved world identities (10,000 replicates, 95% percentile
interval). Positive observation differences mean the left method used more
observations. This does not treat 288 episodes as independent:

| Contrast (left − right) | Goal completion difference (95% CI) | Observation difference (95% CI) |
|---|---:|---:|
| Age − Uncertainty | −0.014 [−0.111, 0.083] | 4.361 [3.250, 5.500] |
| Periodic − Age | 0.139 [0.028, 0.250] | −0.472 [−1.625, 0.819] |
| Periodic − Uncertainty | 0.125 [0.028, 0.236] | 3.889 [2.778, 5.139] |
| Static − Age | −0.347 [−0.500, −0.194] | −10.556 [−12.500, −8.500] |
| Static − Periodic | −0.486 [−0.639, −0.319] | −10.083 [−11.750, −8.514] |
| Static − Uncertainty | −0.361 [−0.514, −0.208] | −6.194 [−7.611, −4.861] |

The full paired analysis also reports contact-free completion, distance, steps,
blocked actions, heading changes, sensor visibility and map-error contrasts,
both overall and separately by R/BP/M. Observation cost differs across methods;
the common cap is not a claim of equal sensing cost. The results are not
directly compared with earlier 2D or proxy runs.

The outputs are under
`results/phase2_mujoco/g1_3d_perception_footprint_feedback_full_288/`:

- `episodes.csv`: original per-episode records, left byte-for-byte intact.
- `summary.json`: original run summary, retained unchanged.
- `paired_world_clustered_analysis.json`: overall and R/BP/M paired estimates.
- `episodes_action_metrics_corrected.csv` and
  `summary_action_metrics_corrected.json`: derived action-count correction.
- `action_history_audit.json`: hashes, definitions and audit totals; the
  original summary and artifact manifest are preserved alongside it.
- `provenance.json`: experiment commit, seven source hashes, Python/MuJoCo
  versions, robot asset hashes, environment identities, seed, policy and
  configuration. The starting Git status notes the already-created smoke
  result directory; the experiment source commit itself is pinned explicitly.

The raw CSV's legacy field named `g1_distinct_rejected_actions` was actually a
rejected-attempt count. The post-run audit leaves that raw CSV and the original
summary untouched, adds a corrected derived CSV/summary, and counts 4,082
attempts, 3,805 unique per-episode transitions and 277 retries across 85
episodes. Retries occurred only after a relevant local observed-memory change;
the audit retains this distinction. The original pre-audit artifact manifest
is preserved and the current manifest hashes all raw and derived outputs.

Final focused regression run: **65 passed**, with 14 upstream Matplotlib/
pyparsing deprecation warnings. Headless playback verified the final successful
smoke trajectory (69 frames) and both earlier failed smoke trajectories (81
frames each), with zero unwanted-contact frames. On macOS, animated playback
of the successful trajectory is:

```bash
.venv/bin/mjpython scripts/view_phase2_g1_navigation.py \
  --result-dir results/phase2_mujoco/g1_g1footprint_feedback_seed42_smoke_final \
  --camera overview
```

### Optional portfolio gait overlay

For a roughly 12-second, 30 FPS portfolio replay, add `--visual-gait --speed
0.18 --once`. The flag interpolates the displayed root position and shortest-arc
heading between the saved trajectory frames, then adds small alternating hip,
knee, ankle, shoulder and elbow offsets around the exact `stand` keyframe. Joint
names and hard ranges come from the loaded G1 MJCF. Forward/backward direction
reverses gait phase; lateral translation uses a regular alternating cycle; an
in-place turn fades the limbs toward stand while yaw interpolates. Animation
phase advances by traveled distance, so playback speed controls its cadence.
The default replay without the flag is unchanged.

```bash
.venv/bin/mjpython scripts/view_phase2_g1_navigation.py \
  --result-dir results/phase2_mujoco/g1_g1footprint_feedback_seed42_smoke_final \
  --camera overview --visual-gait --speed 0.18 --once
```

This is a presentation-only procedural animation. It does not change saved
positions, obstacle/pedestrian snapshots, route decisions or experiment
metrics, and it does not solve foot placement or balance. The feet can visibly
slide, lift through the floor, or intersect nearby geometry during the overlay;
it is not physically valid walking. Geometry group 5 remains visible in the
viewer. The gait regression tests cover actual MJCF joint limits, deterministic
poses, continuous root/heading interpolation, backward movement, stop settling
and default headless replay immutability.

### Separate forward-facing portfolio route

The evaluated planner may strafe or back up while retaining its heading. A
separate demonstration mode is available through
`scripts/phase2_g1_forward_portfolio.py`. It reads the already admitted BP fit
world with identity `phase1.5-v0.4-BPRIME-1:fit:BP:80010010`, schedule 0, and
uses the existing 3D ray observer and observation cap. The runner screens the
admitted fit worlds with one initial ray observation each and records that
selection screen; this uses no hidden occupancy or MuJoCo collision shield
queries. Its A* state includes
heading; every translation is forward along the current cardinal heading and
turns are separate selected actions. Route planning sees only the ternary
observed memory, public footprint dimensions and attempted-action feedback.
The single selected turn or translation is checked at the actual G1 MuJoCo
collision geometry. A rejected turn is fed back as an action rejection, after
which the memory-based planner searches for another route. It does not query
MuJoCo for unattempted alternatives or pass hidden occupancy to the planner.

The successful route uses existing fit identity
`phase1.5-v0.4-BPRIME-1:fit:BP:80010011`, reaches its goal in 13 actions (12
forward translations and one turn), with four observations and zero rejected
actions. Actual navigation recorded zero unwanted floor, pedestrian, wall,
persistent-obstacle or self contacts. A separate 30 FPS visual audit at 0.8
seconds per saved action checks 320 interpolated poses over 10.67 seconds and
records zero unwanted visual contact frames. Its 320 allowed foot-floor
contact pairs are reported only in the visual audit, not as navigation metrics.

Two attempted initial-ray-feasible environments were retained as failures: R
`80000000` had no safe route from its initial observation, and BP `80010010`
had a MuJoCo-rejected forward translation followed by no observed-map route.
The selected BP `80010011` route completed successfully. These separate outputs
are diagnostic portfolio attempts, not additions to the 288-episode comparison.

The successful output is stored separately at
`results/phase2_mujoco/g1_forward_facing_portfolio_fit_BP_80010011_schedule0/`.
It is not part of the 288-episode comparison. The viewer requires the separate
`--portfolio-forward-demo` flag for this result type; the historical
`--visual-gait` playback remains available for prior trajectories.

Record the successful roughly 10.7-second overview replay on macOS with:

```bash
.venv/bin/mjpython scripts/view_phase2_g1_navigation.py \
  --result-dir results/phase2_mujoco/g1_forward_facing_portfolio_fit_BP_80010011_schedule0 \
  --camera overview --portfolio-forward-demo --speed 0.8 --once
```

### Forward-first default Phase 2 policy

The ordinary MuJoCo Phase 2 runner now uses heading-aware forward-only A* as
its default for all observation methods. It turns through separately selected
and MuJoCo-checked actions before changing its forward travel direction.
Static-object side-steps are eligible only for a recent 3D ray hit classified
as a persistent object directly in front, with the complete lateral sweep and
the next forward cell observed free. A retreat is eligible only when two
observations provide a single consistent pedestrian track, its measured
motion predicts an imminent approach, and every cell touched by the backward
sweep is observed free. If the pedestrian motion or retreat clearance is
uncertain, the policy waits. This tracker uses measured pedestrian surface
cells only; the 61-ray horizontal sensor's limited FOV means it does not claim
full pedestrian awareness or predict hidden trajectories.

The controls remain kinematic root-pose actions with a separate actual-G1
MuJoCo collision check on each selected turn or translation. The procedural
viewer gait only changes displayed joints and is not physically actuated
locomotion. Historical smoke/full result directories remain unchanged. The new
forward-first smoke and 288-episode comparison are saved in separate result
directories and explicitly identify the changed movement policy.

#### Forward-first default results (2026-11-08)

The new single-episode `mujoco3d` smoke used the existing periodic-update,
seed-42 Phase 1.5 fit world and did **not** reach its goal. It exhausted 80
steps after 20 observations, with zero executed translations and zero unwanted
contacts; its recorded failure was `deadline_no_footprint_aware_route`. This
failure is preserved at
`results/phase2_mujoco/g1_forward_first_default_smoke/` and was not used to
change the route policy or the grid scale.

A separate 288-episode comparison completed on the same 36 admitted worlds,
two schedules, four observation methods, and seed 42, with the same 0.75 m per
cell assumption and 80-step limit. These are changed-policy results, not a
replacement for the historical 288-episode comparison:

| Observation method | Goals | Completion | Forward translations executed | Checked turns | Unwanted contacts |
|---|---:|---:|---:|---:|---:|
| Static | 6/72 | 8.33% | 196 | 123 | 0 |
| Periodic | 5/72 | 6.94% | 114 | 36 | 0 |
| Age | 6/72 | 8.33% | 124 | 39 | 0 |
| Uncertainty | 4/72 | 5.56% | 96 | 27 | 0 |
| **Total** | **21/288** | **7.29%** | **530** | **225** | **0** |

Every attempted translation action was forward (612 forward actions; no side
steps, retreats, or waits were selected in this matrix). Turns were separate
actions and were collision checked. The comparison had 74 rejected translation
attempts, zero unattempted collision queries, and zero unwanted contact pairs.
The 21 completed episodes were contact free. The low completion rate and
5,098–5,388 no-route steps per method show that forward-first behavior is now
the default, but routing success remains limited under the existing sensing,
observation budgets, footprint, and grid scale. The separate portfolio route
success is not evidence that the experimental policy completes this smoke or
comparison.

Machine-readable outputs are in
`results/phase2_mujoco/g1_forward_first_default_full_288/`, including per
episode action counts and `action_events.json` with a reason for each selected
non-forward action. Both new output artifact manifests verified without hash
mismatches. The Phase 1.5 preservation verifier also rehashed all 836 protected
checkpoint/receipt files successfully; prior experiment directories were not
overwritten.
