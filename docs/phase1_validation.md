# Phase 1 foundation validation

Executed on Windows with Python 3.12.10, 2026-11-06. macOS / Apple Silicon is
intended but unverified. No held-out episode was executed. No new navigation or
persistence algorithm, reinforcement learning, MuJoCo, or G1 integration is included.

## Commands executed

From the repository root in PowerShell:

```powershell
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pip freeze
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/run_experiment.py --config configs/development.json --output results/representative
```

The first pip attempt could not access PyPI inside the sandbox. The same install
command then succeeded with approved network access in the existing `.venv`.
`pip check` reported `No broken requirements found.` Direct dependencies:
NumPy 2.2.6, Matplotlib 3.10.3, pytest 8.3.5. The exact installed package versions
are also recorded in `results/representative/results.json`.

The first suite passed 13 tests; after adding metric attribution/contact and
image-output checks, the full suite passed **17 tests**. The latter run emitted
14 dependency deprecation warnings from Matplotlib 3.10.3 using pyparsing 3.3.3
(old parser method names). They did not prevent image generation or fail tests;
they remain a dependency maintenance issue. An initial font-cache permission
warning was resolved by routing the headless cache to a temporary directory.

Representative artifacts were regenerated after the final implementation edits.
Six PNGs were saved (initial, step 4, final for each method), plus episode CSV
and JSON with the complete config. Images were inspected for readable labels,
separation of hidden truth and memory, and executed/planned paths. Artifacts total
approximately 210 KB. Virtual environments and caches remain excluded.

## Actual development results

Three paired noise-free seeds (7, 19, 31), one corridor layout, 24-step budget:

| Metric per episode | Static | Periodic |
| --- | ---: | ---: |
| Success | false | false |
| Collision count | 23 | 5 |
| Travel distance | 1 | 19 |
| Elapsed steps | 24 | 24 |
| Observation count | 1 | 13 |
| Observation cost | 1.5 | 19.5 |
| Stale-map errors (cell-samples) | 25 | 20 |
| False persistent occupancy (cell-samples) | 17 | 3 |
| Missed persistent changes (cell-samples) | 60 | 51 |

Both success rates were **0/3**. Seeds are identical repetitions in this
noise-free scenario, not three independent environmental trials. These numbers
are an acceptance demonstration, not evidence of statistical superiority.

Static memory retains the initial pedestrian obstruction and stops at `(2, 3)`;
optimistic plans repeatedly attempt unobserved wall cells and contact does not
update its map. Periodic mapping navigates into the lower passage, discovers it
does not connect directly to the goal corridor, returns, and ends at `(8, 3)`,
one cell before `(9, 3)`. The step budget was retained rather than enlarged to
turn this into a success. Hidden changes include an addition at step 3,
relocation at step 6, and removal at step 10.

## Review and provenance

Git commands use the per-command option
`-c safe.directory=C:/Users/81704/Desktop/fujita/31_humanoid-spatial-memory/humanoid-spatial-memory`
because the sandbox account differs from the repository owner. No global Git
configuration or history rewrite is required. Review commands include
`git status --short`, `git diff --check`, and `git diff --cached` with that option.
The implementation was committed locally as
`fa12ea85d089308ddc1b09ac71552e6ff3f3161a` with message
`Implement Phase 1 spatial memory simulation and baselines`. The working tree
was clean after that commit. The requested `git push origin main` waited in Git
Credential Manager without output and was interrupted. A noninteractive retry
failed with `Cannot prompt because user interactivity has been disabled` and
`could not read Username for 'https://github.com': terminal prompts disabled`.
`gh auth status` also failed because GitHub CLI is not installed. No push is
claimed. This delivery limitation is recorded in a subsequent documentation
commit. Git history was not rewritten.

The exact bounded retry was:

```powershell
$env:GIT_TERMINAL_PROMPT='0'; $env:GCM_INTERACTIVE='Never'; git -c safe.directory=C:/Users/81704/Desktop/fujita/31_humanoid-spatial-memory/humanoid-spatial-memory -c credential.interactive=never -c http.lowSpeedLimit=1 -c http.lowSpeedTime=30 push origin main
```

Authenticate GitHub through Git Credential Manager in the user's normal
PowerShell session, then run `git push origin main` from the repository root.

The artifact's `commit_sha` identifies HEAD at execution time; because these
representative files were generated before the implementation commit,
`working_tree_dirty` is true. The SHA-256 of the actual Python source and raw
configuration disambiguates the producing implementation. A commit cannot
include an artifact that already contains its own final commit hash.

## Remaining research limitations

The testbed uses point robots, reactive-free scripted pedestrians and explicit
layouts; it cannot validate bipedal walking, human safety, or real-world transfer.
The suite is small, the baselines are sanity checks, and the sensing-cost model
does not include sensing latency. Error totals depend on episode length. See
the protocol for exact operational definitions. Freeze a broader scenario suite,
review stronger published baselines, and review the research design before
running held-out comparisons or implementing additional algorithms.
