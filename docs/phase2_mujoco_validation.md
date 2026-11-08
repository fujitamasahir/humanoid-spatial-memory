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
