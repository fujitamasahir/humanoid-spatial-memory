# BEAT THE HUMANOID: Human vs AI

Offline, local-only visitor game for the BYU AI Day 2026 showcase. Visitors pick one of the **36 admitted Phase 1.5 mazes**, place a small number of static objects and moving pedestrian proxies, choose **Periodic**, **Age**, or **Uncertainty**, and watch the existing Phase 2 G1 navigation policy attempt the maze.

## Isolation and frozen source

This demo is developed on `demo/ai-day-2026`, separate from `phase2/mujoco-proxy-pilot`. The demo branch existed at task start. `BRANCH_BASE.json` records the research branch HEAD and merge base from that point: `b6cb1fa233fbcd30b7ea26e88b865a69db96b91e`. No merge or rebase was performed, and this task does not push to the research branch.

`data/runtime_binding.json` fingerprints the research observation controller, evaluator, G1 planner, MuJoCo perception/collision code, evaluator runner, and all Unitree G1 model assets. The app checks these hashes when it starts and refuses to run if they change. The Periodic/Age/Uncertainty implementations are used as committed; Static is not an option. The challenge runner reuses the saved Phase 2 policy configuration, the actual 61-ray memory sensor, the independent 61-ray safety sensor, forward-first planner, selected-action collision shield, and `run_episode()` evaluator.

## Maze data and integrity

`data/maze_catalog.json` contains all 36 admitted R/BP/M maze geometries, dimensions, start, goal, and row-bit wall raster. Each maze includes its source checkpoint path and SHA-256, payload SHA-256, and canonical geometry SHA-256. Experimental object-change schedules are excluded. The export script rehashed the 836 protected Phase 1.5 files before writing this asset; the frozen JSON file SHA-256 is checked by the app on startup. The app itself also verifies the 64-file G1 model binding.

The visitor editor starts without user objects or pedestrians. Static objects and initial pedestrian positions together are checked for forward-first reachability using per-geom bounding spheres derived from the committed G1 collision geometry, including swept turn and translation clearance. This is deliberately conservative. All 36 original layouts pass the check. The live collision shield then uses the actual MuJoCo model for the selected action. Blocked or rejected actions are shown separately and are never counted as actual contacts.

Pedestrians are visitor-created only. Each starts at the chosen open cell and follows a reproducible, layout-seeded cardinal random walk for the selected step horizon. Paths favor less-visited cells, avoid immediate reversals where possible, avoid static objects and start/goal, and prevent pedestrian overlaps or exchanges. Later moving pedestrians may temporarily block a route; the editor guarantees a footprint-safe route at placement time only. The original experimental schedules are never loaded into a challenge. The controllers receive ray observations and their own memory; ground-truth grids are only used by the evaluator, collision geometry, and visitor-facing map.

## Install and launch

The showcase is offline at runtime. Install the pinned demo server packages once while preparing the Mac (the project `.venv` is already used here):

```sh
.venv/bin/pip install -r demos/ai_day_2026/requirements-demo.txt
PYTHONPATH=src:scripts:demos/ai_day_2026 .venv/bin/uvicorn app:app \
  --app-dir demos/ai_day_2026 --host 127.0.0.1 --port 8765 --no-access-log
```

Open `http://127.0.0.1:8765` in Safari or Chrome. The server binds only to localhost. No Node.js, cloud service, external CDN, or internet connection is used by the running game. FastAPI/Uvicorn and their dependencies are pinned in `requirements-demo.txt`.

Stop the server with Control-C. Challenge settings and results are appended to `logs/challenges.jsonl` separately from research data. That file is ignored by Git and contains no visitor identity information.

## Controls

- Left stick or keyboard arrows: move the placement cursor.
- D-pad: select observation strategy, or difficulty when Settings is open.
- LT/RT: previous/next maze.
- A / Enter: start the challenge (or confirm settings / return from results).
- B / Backspace: remove the object or pedestrian at the cursor.
- X / Y: directly place, swap or toggle static object / pedestrian.
- Menu (three lines) / M: open difficulty settings; A confirms, B closes.
- Mouse: click to place, right-click to remove; use the on-screen maze and strategy selectors.
- There is no manual robot control.

The UI reports Xbox connection status and supports keyboard/mouse if the controller disconnects. Difficulty is enforced by the backend: Easy (80 steps, 4 objects, 2 pedestrians), Medium (120 steps, 2 objects, 1 pedestrian), Hard (200 steps, no hazards). Changing difficulty preserves the earliest placed hazards up to the new caps and removes the excess.

## Rules and screens

1. **Challenge Setup:** choose a saved maze, add hazards, choose Periodic/Age/Uncertainty, and correct any invalid placement called out by the editor.
2. **Live Simulation:** side-by-side visitor ground truth and robot spatial memory, with actual G1 pose, step count, observations, distance, safety events, actual contacts, and a separate blocked-move count. The exhibition uses optional MuJoCo 3D rendering and a lightweight 2D Canvas fallback.
3. **Results:** the AI wins only when it reaches Goal within the chosen difficulty's step limit with zero actual unwanted MuJoCo contacts. A shield-rejected action is a blocked move, **not** a contact. The results retain the final spatial memory, show the selected G1's reaction, and allow visitors to return to the same layout. On a human win, the rendered G1 kneels, lowers to its hands, and loops a trembling pose until the visitor leaves the result screen. These are presentation-only kinematic poses.

An episode is single-threaded and the API rejects overlapping challenges. Reset is available after a challenge finishes. Each run uses a reproducible seed and saves its layout, strategy, pedestrian paths, and results to the local showcase JSONL log.

## Runtime and known limitations

A loopback API smoke on the personal Mac ran four actual G1 challenges (Periodic, Age, Uncertainty, and Periodic with one visitor-placed object plus one pedestrian) in 27.1 seconds total. Full challenge wall time, including MuJoCo scene setup and live playback pacing, was 4.5–6.7 seconds. The selected maze reached 80 steps in Periodic and Uncertainty (one rejected move in Uncertainty, zero actual contacts) and reached Goal in 56 steps with Age. The mixed obstacle/pedestrian case also ran to 80 steps with zero actual contacts. This is an early machine-specific benchmark, not a performance guarantee for every visitor layout. The 80-step cap and 0.75 m/cell assumption match the saved Phase 2 configuration.

The robot is kinematically repositioned by the existing evaluator; this is not legged locomotion. The live display supports optional synchronized 3D rendering with a 2D fallback. Some object arrangements may pass the static reachability check but still be difficult for a partially observed AI. Pedestrian paths are seeded and reproducible; temporary dynamic blockages may still occur. Logs remain local; back up `logs/challenges.jsonl` separately if showcase scores need to be retained.

## Validation

```sh
PYTHONPATH=.:src:scripts:demos/ai_day_2026 .venv/bin/pytest -q demos/ai_day_2026/test_demo_engine.py
PYTHONPATH=.:src:scripts:demos/ai_day_2026 .venv/bin/python demos/ai_day_2026/smoke_api.py
```

The API smoke expects the app to be running at `127.0.0.1:8765` and performs actual, non-generative challenges on one already-admitted maze. `validation/api_smoke_report.json` records the latest verified run. It does not modify Phase 1.5 stores or Phase 2 experiment results.

### Optional defeat animation cache warm-up

Before the exhibition, run the following once from the repository root (with the app stopped). This avoids first-use generation of a new defeat spritesheet at the result screen. Existing selection portraits are preserved.

```sh
for strategy in periodic age uncertainty; do
  .venv/bin/python demos/ai_day_2026/generate_portraits.py \
    "$(.venv/bin/python -c 'import tempfile; print(tempfile.gettempdir())')/ai-day-g1-portraits-v8" \
    "$strategy" defeat
done
```

### Skip and review

Press A during the live challenge to remove presentation delays. Navigation, step cap, contact accounting, and optional 3D rendering continue to completion. B on the result screen opens a review of every evaluator step (including step zero); use D-pad left/right or the timeline, and B to go back. 3D frames are preserved when rendering succeeds, otherwise review uses the 2D ground-truth map. Only the latest challenge's review history is held in server memory, cleared on reset. The defeat animation uses palm orientation and position IK; the pose is kinematic, not a physically simulated fall.
