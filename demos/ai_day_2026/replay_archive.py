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
FINAL_COMMIT = "56ad4a4f474c6194783a02c2a949d6d61bb3ab71"
PREFIX = "results/phase2_mujoco/"
COMPREHENSIVE = PREFIX + "h2_comprehensive_benchmark_v1/"
RECOVERY = PREFIX + "h2_full_spatial_memory_replay_v1/"
HIGH_FREQ = PREFIX + "h2_high_frequency_dynamics_v1/"
FINAL = PREFIX + "h2_final_benchmark_reconciliation_v1/"
FINAL_JOURNAL = FINAL + "corrected_b_age_unseen_v1/journal.jsonl"
FINAL_METADATA = {FINAL_JOURNAL, FINAL + "final_model_summary.csv"}
FINAL_EPISODE = re.compile(re.escape(FINAL) + r"corrected_b_age_unseen_v1/episodes/(?:unseen_low_frequency|unseen_high_frequency)/[A-Za-z0-9_-]+\.json\.gz")
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
    return (path in METADATA or path in FINAL_METADATA or FINAL_EPISODE.fullmatch(path) is not None
            or EPISODE.fullmatch(path) is not None or MAP.fullmatch(path) is not None)


def archive_commit(path: str) -> str:
    return FINAL_COMMIT if path.startswith(FINAL) else RESEARCH_COMMIT


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
    return _git("cat-file", "blob", f"{archive_commit(path)}:{path}")


def preflight() -> int:
    """Verify that all metadata and 11,664 selected replay blobs exist locally."""
    data = {path: read_archive(path) for path in METADATA | FINAL_METADATA}
    manifest = json.loads(data[COMPREHENSIVE + "combined_dataset/replay_index.json"])
    recovered = list(csv.DictReader(io.StringIO(
        data[RECOVERY + "replay_index_reconciled.csv"].decode("utf-8"))))
    if len(manifest["entries"]) != 7776 or len(recovered) != 4752:
        raise RuntimeError("Unexpected research index size")
    # Historical low-frequency traces were replaced by recovered full replays.
    # Supersede the 144 mislabeled unseen B+Age records; keep corrected known
    # B+Age and every B+C record intact.
    entries = [row for row in manifest["entries"] if row["payload_type"] == "replay"]
    old_paths = [row["path"] for row in entries] + [RECOVERY + row["path"] for row in recovered]
    if len(old_paths) != 11664 or len(set(old_paths)) != 11664:
        raise RuntimeError("Unexpected historical replay count")
    replaced = {("unseen_low_frequency" if row["condition"] == "original" else "unseen_high_frequency",
                 row["world_identity"], int(row["schedule"]))
                for row in entries if row["model_id"] == "b_age"}
    replaced.update(("unseen_low_frequency", row["map_identity"], int(row["schedule"]))
                    for row in recovered if row["dataset"] == "h2_unseen" and row["model_id"] == "b_age")
    corrections = [json.loads(line)["record"] for line in data[FINAL_JOURNAL].decode().splitlines()]
    keys = {(row["condition"], row["map_identity"], row["schedule"]) for row in corrections}
    if len(corrections) != 144 or len(keys) != 144 or keys != replaced:
        raise RuntimeError("Unexpected B+Age correction coverage")
    if any(row["model_id"] != "b_age" or row["event"] != "episode_committed" or row["seed"] != 42
           or not FINAL_EPISODE.fullmatch(FINAL + row["path"])
           or not row["path"].startswith("corrected_b_age_unseen_v1/episodes/" + row["condition"] + "/")
           for row in corrections):
        raise RuntimeError("Invalid B+Age correction")
    episode_paths = ([row["path"] for row in entries if row["model_id"] != "b_age"]
                     + [RECOVERY + row["path"] for row in recovered
                        if not (row["dataset"] == "h2_unseen" and row["model_id"] == "b_age")]
                     + [FINAL + row["path"] for row in corrections])
    if len(episode_paths) != 11664 or len(set(episode_paths)) != 11664:
        raise RuntimeError("Unexpected authoritative replay count")
    if not all(allowed_path(path) for path in episode_paths):
        raise RuntimeError("An indexed path is outside the archive allowlist")
    specs = "\n".join(f"{archive_commit(path)}:{path}" for path in episode_paths) + "\n"
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
    print(f"H2 archive preflight PASS: {count:,} replay blobs and {len(METADATA | FINAL_METADATA)} metadata files available locally")
