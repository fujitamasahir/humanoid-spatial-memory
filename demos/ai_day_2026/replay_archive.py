"""Read-only exhibition archive from the exact research commit, not the demo checkout."""
from __future__ import annotations

import csv
import io
import json
import os
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RESEARCH_COMMIT = "3b208befeb268cb2ae789add7deaaf859abcfc5a"
PREFIX = "results/phase2_mujoco/"
COMPREHENSIVE = PREFIX + "h2_comprehensive_benchmark_v1/"
RECOVERY = PREFIX + "h2_full_spatial_memory_replay_v1/"
HIGH_FREQ = PREFIX + "h2_high_frequency_dynamics_v1/"
METADATA = {
    COMPREHENSIVE + "combined_dataset/replay_index.json",
    COMPREHENSIVE + "analysis/model_summary.csv",
    COMPREHENSIVE + "analysis/failure_cases.csv",
    RECOVERY + "replay_index_reconciled.csv",
    RECOVERY + "fit72_model_summary.csv",
    RECOVERY + "fit72_b_age_correction_validation.csv",
}
EPISODE = re.compile(
    r"results/phase2_mujoco/(?:"
    r"h2_comprehensive_benchmark_v1/(?:original_environment|high_frequency_environment)/episodes/[A-Za-z0-9_/-]+"
    r"|h2_high_frequency_dynamics_v1/replays/(?:primary|original_uncertainty)/[A-Za-z0-9_-]+"
    r"|h2_final_generalization_v1/primary/[A-Za-z0-9_-]+"
    r"|h2_full_spatial_memory_replay_v1/(?:task_a|task_b|task_b_b_age_corrected_v2)/episodes/[A-Za-z0-9_./-]+"
    r")\.json\.gz"
)
MAP = re.compile(re.escape(HIGH_FREQ) + r"maps/map_\d{2}_(?:R|BP|M)\.json")


def allowed_path(path: str) -> bool:
    if not path or any(part in ("", ".", "..") for part in path.split("/")):
        return False
    return path in METADATA or EPISODE.fullmatch(path) is not None or MAP.fullmatch(path) is not None


def _git(*args: str, input: bytes | None = None, timeout: int = 60) -> bytes:
    # Don't trigger a network fetch even in a partial clone during the exhibition.
    env = dict(os.environ, GIT_NO_LAZY_FETCH="1", GIT_TERMINAL_PROMPT="0")
    result = subprocess.run(
        ["git", "-C", str(REPO), *args], input=input, capture_output=True,
        timeout=timeout, env=env, check=True,
    )
    return result.stdout


def read_archive(path: str) -> bytes:
    if not allowed_path(path):
        raise ValueError("Unknown exhibition archive path")
    return _git("cat-file", "blob", f"{RESEARCH_COMMIT}:{path}")


def preflight() -> int:
    """Verify that all metadata and 11,664 selected replay blobs exist locally."""
    data = {path: read_archive(path) for path in METADATA}
    manifest = json.loads(data[COMPREHENSIVE + "combined_dataset/replay_index.json"])
    recovered = list(csv.DictReader(io.StringIO(
        data[RECOVERY + "replay_index_reconciled.csv"].decode("utf-8"))))
    if len(manifest["entries"]) != 7776 or len(recovered) != 4752:
        raise RuntimeError("Unexpected research index size")
    recovered_paths = [RECOVERY + row["path"] for row in recovered]
    episode_paths = [row["path"] for row in manifest["entries"] if row["payload_type"] == "replay"] + recovered_paths
    if len(episode_paths) != 11664 or len(set(episode_paths)) != 11664:
        raise RuntimeError("Unexpected authoritative replay count")
    if not all(allowed_path(path) for path in episode_paths):
        raise RuntimeError("An indexed path is outside the archive allowlist")
    specs = "\n".join(f"{RESEARCH_COMMIT}:{path}" for path in episode_paths) + "\n"
    result = _git("cat-file", "--batch-check=%(objecttype) %(objectsize)", input=specs.encode(), timeout=300)
    lines = result.decode().splitlines()
    if len(lines) != len(episode_paths) or any(not line.startswith("blob ") for line in lines):
        missing = [path for path, line in zip(episode_paths, lines) if not line.startswith("blob ")]
        raise RuntimeError(f"Missing local archive blobs (sample): {missing[:5]}")
    return len(episode_paths)


if __name__ == "__main__":
    try:
        count = preflight()
    except (OSError, subprocess.SubprocessError, ValueError, RuntimeError, KeyError) as exc:
        raise SystemExit(f"H2 archive preflight FAILED: {exc}\nFetch the pinned research commit first; see README.md.") from exc
    print(f"H2 archive preflight PASS: {count:,} replay blobs and {len(METADATA)} metadata files available locally")
