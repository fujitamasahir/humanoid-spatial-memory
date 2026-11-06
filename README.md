# Humanoid Spatial Memory

**Working title:** Task-Aware Spatial Memory for Bipedal Humanoid Navigation in Dynamic Human Environments

Research project investigating how robots can distinguish **transient human-induced obstructions** from **persistent environmental changes**, and when they should re-observe an uncertain area before navigating.

> **Status:** Research planning and Phase 1 environment setup. No experimental findings are claimed.

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

The simulation code has not been implemented yet. Use VS Code/Codex to implement **Phase 1 only** following the research plan and protocol. Add installation and execution instructions only after verified commands work.
