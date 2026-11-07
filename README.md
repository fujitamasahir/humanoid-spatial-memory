# Humanoid Spatial Memory

**Working title:** Task-Aware Spatial Memory for Bipedal Humanoid Navigation in Dynamic Human Environments

Research project investigating how robots can distinguish **transient human-induced obstructions** from **persistent environmental changes**, and when they should re-observe an uncertain area before navigating.

> **Status:** Phase 1.4B development tuning complete: 3,780 frozen episodes and an independently verified parameter lock. Assessment and ablations await separate review; no generalization, novelty, statistical superiority or physical safety claim.

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
