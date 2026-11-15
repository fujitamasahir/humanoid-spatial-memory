"""Lightweight archive path and offline Git-blob checks, independent of MuJoCo."""
import unittest
from unittest.mock import patch
import replay_archive as archive


class ArchiveTests(unittest.TestCase):
    def test_paths(self):
        for path in archive.METADATA:
            self.assertTrue(archive.allowed_path(path), path)
        samples = [
            archive.RECOVERY + "task_a/episodes/periodic4/h2-final-generalization-v1-20261114_R_910000001_s0_seed42.json.gz",
            archive.RECOVERY + "task_b_b_age_corrected_v2/episodes/b_age/phase1.5-v0.4-BPRIME-1_fit_BP_80010000_s1_seed42.json.gz",
            archive.HIGH_FREQ + "replays/primary/episode_001_periodic4.json.gz",
            archive.COMPREHENSIVE + "original_environment/episodes/original/age_event/h2-final-generalization-v1-20261114_R_910000001_s0_seed42.json.gz",
        ]
        for path in samples:
            self.assertTrue(archive.allowed_path(path), path)
        for path in ("../../etc/passwd", ".git/config", archive.RECOVERY + "task_b/episodes/../hidden.json.gz", archive.RECOVERY + "task_b/episodes/b_age//x.json.gz", archive.RECOVERY + "task_b_b_age_corrected/episodes/b_age/x.json.gz"):
            self.assertFalse(archive.allowed_path(path), path)

    def test_pinned_raw_bytes(self):
        path = next(iter(archive.METADATA))
        with patch.object(archive, "_git", return_value=b"\x1f\x8b\x00") as git:
            self.assertEqual(archive.read_archive(path), b"\x1f\x8b\x00")
            git.assert_called_once_with("cat-file", "blob", f"{archive.RESEARCH_COMMIT}:{path}")
        with patch.object(archive, "_git") as git:
            with self.assertRaises(ValueError):
                archive.read_archive("../secret")
            git.assert_not_called()


if __name__ == "__main__":
    unittest.main()
