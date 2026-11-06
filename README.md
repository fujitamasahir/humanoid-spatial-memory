# Humanoid Spatial Memory

**Working title:** Task-Aware Spatial Memory for Bipedal Humanoid Navigation in Dynamic Human Environments

Research project investigating how robots can distinguish **transient human-induced obstructions** from **persistent environmental changes**, and when they should re-observe an uncertain area before navigating.

> **Status:** Phase 1 foundation: reproducible 2D simulator and two sanity baselines. No novelty or improved-performance claim.

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
python scripts/run_experiment.py --config configs/development.json --output results/representative
```

If PowerShell activation is restricted, run the environment executable directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/run_experiment.py --config configs/development.json --output results/representative
```

macOS Terminal (not yet tested):

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest -q
python scripts/run_experiment.py --config configs/development.json --output results/representative
```

The development command runs both baselines on the same scenario and seeds,
saving `episodes.csv`, `results.json` (including the full input configuration,
source hash and Git provenance), and compact PNG snapshots. Use a different
output directory for subsequent runs to preserve representative artifacts.
To run the reserved evaluation configuration after research review:

```bash
python scripts/run_experiment.py --config configs/held_out.json --output results/runs/held_out
```

## Implementation

- `src/spatial_memory/simulation.py`: hidden geometry, pedestrian schedules, changes, collision checking.
- `observation.py`: range-limited occupancy sensing with optional occlusion/noise.
- `memory.py`: ternary robot map and static/periodic observation schedules.
- `navigation.py`: shared cardinal A* using remembered occupancy only.
- `evaluation.py`: episode harness and evaluator-only truth metrics.
- `visualization.py`: hidden truth beside robot memory, with planned/executed paths.
- `scripts/`, `configs/`, `tests/`, `results/`: runner, paired scenarios, checks, outputs.

Sensing happens only at initialization and periodic refresh steps. One sensor
call costs one observation regardless of visible cells; sensing adds cost but
no simulation time. Static memory receives exactly the same initial view and
never updates, even after contact. Both planners replan every step and use the
same unknown-cell rule (`optimistic` or `blocked`). A failed plan waits.
The simulator advances before each sense/plan/move cycle. Pedestrians loop
deterministic cardinal paths (repeated positions model waiting); seeds govern
sensor noise through per-time random streams. No random layout generation is
claimed: dimensions, paths, objects and layouts are explicit configuration.

See [metric definitions and limitations](docs/experimental_protocol.md#implemented-phase-1-semantics)
and [validation record](docs/phase1_validation.md). These are point-robot grid
experiments, not bipedal locomotion. RL, MuJoCo, G1, persistence-aware mapping,
and the proposed task-aware method are intentionally deferred for review.
