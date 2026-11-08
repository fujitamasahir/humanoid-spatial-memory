# Humanoid Spatial Memory

**Working title:** Task-Aware Spatial Memory for Bipedal Humanoid Navigation in Dynamic Human Environments

Research project investigating how robots can distinguish **transient human-induced obstructions** from **persistent environmental changes**, and when they should re-observe an uncertain area before navigating.

> **Status:** Phase 1.4C locked development assessment complete: 13,440 episodes independently verified. The proposed policy made no additional observations and matched Static in all 840 paired conditions; superiority was not established. Ablations await separate review; no generalization, novelty or physical safety claim.

> **Phase 2 status:** The pinned Unitree G1 MJCF is integrated into a bounded,
> kinematic MuJoCo navigation smoke on an existing Phase 1.5 fit world. The G1
> now turns toward each move and receives grid observations from MuJoCo rays.
> Its first 3D-perception smoke reached the goal with zero unwanted pose
> contacts; this is one waypoint experiment, not walking or general navigation evidence. See the
> [Phase 2 validation report](docs/phase2_mujoco_validation.md).

## Research questions

- **RQ1:** Under which conditions do temporary pedestrian obstructions cause stale or incorrect long-term spatial memories?
- **RQ2:** Can task-aware verification reduce navigation failures and observation cost relative to strong memory-update baselines?
- **RQ3 (extension):** Do bipedal traversability constraints change which memories should be verified?

The project is hypothesis-driven: the questions and methods may be revised when comparisons with prior work show that a proposed improvement is already solved.

## Phases

1. **2D controlled evaluation:** Partially observable navigation, moving pedestrians, persistent changes, baseline comparisons, and reproducible measurements.
2. **3D humanoid simulation:** MuJoCo, Unitree G1 model, and pedestrian scenarios. Simplified motion must not be presented as physical walking.
3. **Bipedal locomotion:** Integrate a compatible pretrained walking policy if feasible; evaluate actual dynamic walking and falls separately.

## Research integrity

- Keep the hidden simulator ground truth separate from observations available to the agent.
- Use identical scenario seeds for fair paired comparisons between baselines.
- Define success, collision, observation cost, false map updates, and stale-map errors before reporting results.
- Report failures, uncertainty, and limitations; never fabricate results.
- Do not claim novelty, real-world transfer, or human-safe locomotion based solely on simulation.

See [the research plan](docs/research_plan.md) and [experimental protocol](docs/experimental_protocol.md).

## Getting started

Python 3.12 is required. Windows validation uses the existing Python 3.12.10
environment. macOS / Apple Silicon compatibility is intended but unverified.

Windows PowerShell, from the repository root:

```powershell
# Create only if .venv does not already exist:
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pytest -q
python scripts/run_experiment.py --config configs/development_phase1_1.json --output results/phase1_1/development
```

If PowerShell activation is restricted, run the environment executable directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/run_experiment.py --config configs/development_phase1_1.json --output results/phase1_1/development
```

macOS Terminal (not yet tested):

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest -q
python scripts/run_experiment.py --config configs/development_phase1_1.json --output results/phase1_1/development
```

The development command runs both baselines on the same scenario and seeds,
saving `episodes.csv`, `results.json` (including the full input configuration,
source hash and Git provenance), and compact PNG snapshots. Use a different
output directory for subsequent runs to preserve representative artifacts.
The reserved held-out suite remains unmodified and unexecuted; the runner blocks
held-out execution pending research review.

Diagnostic sweep (original representative files are protected):

```powershell
.\.venv\Scripts\python.exe scripts/run_experiment.py --config configs/development.json --output results/phase1_1/diagnostic --budgets 24 30 40 60 --no-figures
```

See [Phase 1.1 validation](docs/phase1_1_validation.md) for actual findings,
per-seed metrics and reproduction commands. Blocked attempts and dynamic contacts
are separate; legacy `collision_count` is deprecated and is not physical collisions.

## Phase 1.2 adaptive observation comparison

Read the [baseline review and exact definitions](docs/phase1_2_baseline_review.md)
and [validation report](docs/phase1_2_validation.md) before interpreting results.
The new schedules use cell timestamps or history-adapted entropy in the current
potential sensor footprint. They do not use planned routes or hidden obstacle
labels. All methods share the original sensor, last-write map, A* and movement
rules. Sensing costs resources but adds no simulation time.

Windows PowerShell (Python 3.12):

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/run_adaptive_experiment.py --config configs/development_phase1_2.json --output results/phase1_2/development
```

For macOS use `.venv/bin/python` (not validated). The run evaluates six development
families, three paired seeds, four methods, and unlimited/3/5/8 total observation
caps, including the initial call. It saves per-episode CSV/JSON, aggregate and
scenario summaries, observation decision traces, realized environments/provenance,
24 final snapshots and a tradeoff chart. Earlier artifacts are protected by the
new runner. Use another output directory to preserve a repeat run.

Unconstrained results: Periodic 18/18 successes at 7.06 mean observations,
Age 15/18 at 5.39, Uncertainty 18/18 at 2.78. Uncertainty also has more dynamic
contacts than Periodic (4 versus 1 across 18 episodes); reaching the goal does not
establish safer navigation. These are simplified conceptual controls, not faithful
published-method reproductions. Small related layouts and favorable sensing phases
prevent general claims. Task-aware verification, held-out evaluation, RL and
humanoid integration remain deferred for research review.

## Implementation

- `src/spatial_memory/simulation.py`: hidden geometry, pedestrian schedules, changes, movement blocking.
- `observation.py`: range-limited occupancy sensing with optional occlusion/noise.
- `memory.py`: unchanged ternary map and static/periodic baselines.
- `scheduling.py`: local cell-age and history-adapted uncertainty schedules; shared observation cap.
- `navigation.py`: shared cardinal A* using remembered occupancy only.
- `evaluation.py`: episode harness and evaluator-only truth metrics.
- `visualization.py`: hidden truth beside robot memory, with planned/executed paths.
- `scripts/`, `configs/`, `tests/`, `results/`: runner, paired scenarios, checks, outputs.

The original baselines sense at initialization and periodic refresh steps. One sensor
call costs one observation regardless of visible cells; sensing adds cost but
no simulation time. Static memory receives exactly the same initial view and
never updates, even after blocked attempts or dynamic contact. Both planners replan every step and use the
same unknown-cell rule (`optimistic` or `blocked`). A failed plan waits.
The simulator advances before each sense/plan/move cycle. Pedestrians loop
deterministic cardinal paths (repeated positions model waiting); seeds govern
sensor noise through per-time random streams. Phase 1.1 adds seeded development pedestrian paths/dwell durations and persistent
addition locations/timing. Realized scenarios and hashes are saved; layout topology
is still hand-designed.

See [metric definitions and limitations](docs/experimental_protocol.md#implemented-phase-1-semantics)
and [validation record](docs/phase1_validation.md). These are point-robot grid
experiments, not bipedal locomotion. RL, MuJoCo, G1, persistence-aware mapping,
and the proposed task-aware method are intentionally deferred for review.

## Phase 1.3 robustness and task-aware research design

Read the [diagnostic review](docs/phase1_3_diagnostic_review.md),
[fixed matrix](docs/phase1_3_experiment_plan.md),
[validation and reproduction report](docs/phase1_3_validation.md), and
[design-only task-aware specification](docs/phase1_3_task_aware_design.md).

```bash
.venv/bin/python -m pytest -q
.venv/bin/python scripts/run_robustness_experiment.py
.venv/bin/python scripts/run_corridor_diagnostic.py
```

On Windows substitute `.venv\Scripts\python.exe`. macOS / Apple Silicon is now
validated with Python 3.12.16 and the pinned requirements. This adds seven seeded
development families, 16 predefined one-factor robustness settings, 1,792 paired
baseline episodes and 72 corridor diagnostic episodes. Existing configurations,
results and baseline algorithms are preserved; no held-out evaluation was run.

Reference completion: Periodic 28/28, Age 21/28, Uncertainty 19/28. Uncertainty
uses 5.18 calls versus Periodic's 12, but has only 16/28 contact-free completions
versus 26/28. The original corridor advantage depends on change timing and priors.
Common-horizon memory errors freeze terminal memory explicitly; grid occupancy
contacts are distinct from blocked attempts and physical collisions. All 98 tests
pass, including historical regression checks. Stop for research review before
implementing task-aware sensing, MuJoCo or humanoid locomotion.

## Phase 1.4A implementation validation

The [frozen protocol](docs/phase1_4_experimental_protocol.md) now has twelve core
observation schedules and six specified ablations. Historical schedules remain
unchanged. The query gate is a conceptual control, not an ALONE reproduction.
See [validation and measured computational costs](docs/phase1_4a_validation.md).

```bash
.venv/bin/python -m pytest -q
.venv/bin/python scripts/run_phase1_4a_validation.py smoke --output results/runs/phase1_4a_smoke
.venv/bin/python scripts/benchmark_phase1_4a.py --output results/runs/phase1_4a_benchmark --smoke results/runs/phase1_4a_smoke/results.json
```

Only bounded development smoke and policy-free manifest generation are exposed.
The 35 tuning/70 assessment manifests have no policy outcomes. All 175 tests pass,
including every stored historical episode metric. Synthetic runtime estimates
exclude full-matrix storage/I/O; complete traces could require several GB.
No tuning, assessment, held-out evaluation or MuJoCo integration was run.

## Phase 1.4B frozen development tuning

All 3,780 preregistered tuning episodes are complete. The
[validation report](docs/phase1_4b_validation.md) includes every candidate table,
runtime, storage and limitations. The
[parameter lock](results/phase1_4b/parameter_lock.json) fixes one global configuration
per method; an independent SQLite verifier recomputes all scores and winners.

```bash
.venv/bin/python scripts/run_frozen_tuning.py
.venv/bin/python scripts/validate_frozen_tuning.py
```

The runner resumes completed checkpoints and accepts only the pinned tuning
manifest. Full gzip traces remain locally in `results/raw/phase1_4b_tuning/`;
Git contains every episode metric and a complete hash/path storage inventory.
The new writer lease uses POSIX `fcntl` and is validated on macOS. All 183 tests
pass. Stop for review before assessment or ablation experiments.

## Phase 1.4C locked development assessment

The [assessment report](docs/phase1_4c_validation.md) documents the pinned
70-environment, 13,440-execution matrix, checkpoint resume, independent trace
verification and layout-cluster analysis. Parameters remain fixed by the
Phase 1.4B lock; no assessment outcome is used for selection. The full suite now
passes 192 tests on Ubuntu WSL2. Native Windows cannot run the POSIX storage
layer; use WSL with a separate Linux Python environment:

```bash
python3 -m venv .venv-wsl
.venv-wsl/bin/python -m pip install -r requirements.txt
.venv-wsl/bin/python -m pytest -q -o cache_dir=/tmp/hsm-pytest-cache
.venv-wsl/bin/python scripts/run_locked_assessment.py
.venv-wsl/bin/python scripts/analyze_locked_assessment.py
```

Full gzip traces remain in `results/raw/phase1_4c_assessment/`; compact episode
metrics and the complete hash inventory are under `results/phase1_4c/`.
Preserve the raw directory and exact run environment for resume and independent
verification. Ablations, reserved held-out evaluation and humanoid integration
remain deferred for separate review.

At cap 4 without sensor noise, the proposed policy's contact-free completion was
41.43% versus route-weighted's 42.86%: a difference of -1.43 percentage points,
with a layout-cluster 95% interval of [-10.05, 8.10]. The prespecified practical
benefit is inconclusive. The locked policy requested no post-initial observations
in any of its 840 episodes and reproduced Static's trajectories and scientific
metrics throughout this matrix. See the report for all controls and limitations.

## Phase 2 MuJoCo pilot (historical proxy)

MuJoCo 3.17.0 on Python 3.12 / Apple Silicon compiled the saved 2D fit worlds into
3D floors, walls, persistent objects, pedestrian proxies and a capsule humanoid
proxy. The existing memory policies and A* planner still operate on the 2D
observation grid. The root is placed kinematically at grid waypoints; there is no
gait, actuator control, balance or physical walking. This pilot is a 3D scene and
contact-geometry replay, not evidence of 3D navigation performance or G1 behavior.

The one-episode smoke reached its goal. The paired proxy replay completed 288
episodes in 4.2 seconds using the same 36 saved worlds, two schedules, four
methods, seed 42, 80-step horizon and shared 20-observation cap (including the
initial observation). Its goal/observation metrics match the earlier 2D pilot
because the policy and planner are unchanged. Every method had 0/72 completions
without any proxy pose contact; this exposes a footprint mismatch between the
point-grid planner and the deliberately simple proxy. No parameter selection or
claim of method superiority follows from this run.

```bash
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pytest tests/test_phase2_mujoco.py -q
.venv/bin/python scripts/phase2_mujoco_navigation.py smoke
.venv/bin/python scripts/phase2_mujoco_navigation.py full
```

The CSV/JSON results, 3D screenshot, source hashes and fixed run settings are in
`results/phase2_mujoco/`. The MuJoCo OpenGL renderer was unavailable in the
headless execution context; the saved screenshot is a Matplotlib 3D rendering of
the same proxy scene. That initial limitation and its outputs are retained as
historical evidence. All simplified motion remains kinematic and must not be
described as walking.

## Actual Unitree G1 kinematic smoke

The pinned G1 MJCF and meshes under `third_party/unitree_g1/` now load directly.
The adapter initializes the `stand` keyframe and translates only
`floating_base_joint` kinematically. MuJoCo checks the actual G1 collision
geometry before each proposed move. Eight small ankle-roll spheres are
classified as intended foot-floor contacts; other floor, wall, obstacle,
pedestrian, and self contacts are unwanted. Existing fit-world walls,
pedestrians, persistent obstacle changes, memory, and A* remain in use.

The smoke used the first admitted saved fit record (`R`, fit index 0, schedule
0), periodic observations, seed 42, the existing 2D model, an 80-step cap, and
the documented 0.75 m/cell assumption with a 0.02 s MuJoCo timestep. G1 reached
the goal in 60 environment steps with 37 successful grid moves (27.75 m at that
assumed scale) and 16 observations including initialization. There were 23
ordinary grid-blocked attempts. Across 61 checked poses, the model registered
488 intended foot-floor pairs and zero unwanted pose contacts. Collision queries
also identified wall intersections on blocked targets. This is one kinematic
smoke only, not evidence of walking, balance, or general 3D navigation.

The result, portable MJCF scene, trajectory and model/source hashes are in
`results/phase2_mujoco/g1_smoke/`. Replay with the native MuJoCo Viewer on macOS:

```bash
.venv/bin/python scripts/view_phase2_g1_navigation.py \
  --result-dir results/phase2_mujoco/g1_smoke --speed 0.25
```

The offscreen renderer could not establish a CoreGraphics connection in this
headless process. The saved trajectory passed a headless replay check with zero
unwanted-contact frames. The 288-episode matrix has not been run for G1.

## G1 heading and MuJoCo 3D perception smoke

The follow-up smoke keeps the same admitted fit environment and adds heading
control and a MuJoCo ray sensor. The supplied G1 model's local +X axis is its
forward axis. Each grid move checks an in-place yaw sweep at increments no
larger than 0.05 rad, followed by a translation sweep at increments no larger
than 0.075 m. A collision blocks the maneuver and records whether turning or
translation was blocked. The stand root height and joint pose remain fixed;
this is kinematic motion, not actuated walking.

The ray origin is attached to `torso_link` and is 0.864 m above the floor in
the stand pose. The sensor casts 61 deterministic horizontal rays over 120
degrees to 6 m, sampling the ray paths every 0.075 m. Visible paths become free
cells, first hit geometries mark occupied cells, and cells outside visibility
remain unknown. A dedicated MuJoCo geom group and body exclusion keep robot
geometry out of observations; nearest-hit raycasting preserves occlusion. The
controller receives only the ternary occupancy grid. It receives no geometry
identity or evaluator truth.

The fresh result bundle is
`results/phase2_mujoco/g1_mujoco3d_heading_perception_smoke/`; its
`validation_report.json` contains the measured trajectory, sensor, collision,
memory, fit-identity, model, and source data. The updated viewer supports both
this run and the older `g1_smoke` trajectory. Start looped playback in macOS
Terminal with:

```bash
.venv/bin/mjpython scripts/view_phase2_g1_navigation.py \
  --result-dir results/phase2_mujoco/g1_mujoco3d_heading_perception_smoke --camera follow
```
