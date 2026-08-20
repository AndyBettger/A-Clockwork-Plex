from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class ReleaseHygieneContractTests(unittest.TestCase):
    def test_gitignore_covers_runtime_generated_and_tooling_state(self) -> None:
        entries = {
            line.strip()
            for line in (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }
        required = {
            "config.json",
            "state.json",
            "alarm-runtime.json",
            "alarm-audio-runtime.json",
            "playback-runtime.json",
            "weather-forecast-cache.json",
            "weather-rainfall-history.json",
            "weather-rainfall-lifetime.json",
            "*.json.tmp",
            "*.log",
            "app/static/generated/",
            "__pycache__/",
            ".pytest_cache/",
            ".mypy_cache/",
            ".ruff_cache/",
            ".coverage",
            "htmlcov/",
            "build/",
            "dist/",
            "*.egg-info/",
            ".vscode/",
            ".idea/",
        }
        self.assertTrue(required <= entries, sorted(required - entries))

    def test_known_runtime_outputs_are_not_committed_source_files(self) -> None:
        runtime_outputs = (
            "config.json",
            "state.json",
            "alarm-runtime.json",
            "alarm-audio-runtime.json",
            "playback-runtime.json",
            "weather-forecast-cache.json",
            "weather-rainfall-history.json",
            "weather-rainfall-lifetime.json",
        )
        tracked = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "ls-files", "--", *runtime_outputs],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        self.assertEqual([], tracked)

    def test_obsolete_phase2_roadmap_mutators_stay_removed(self) -> None:
        obsolete = (
            ".github/workflows/complete-eq-phase2.yml",
            ".github/workflows/complete-eq-phase2-v2.yml",
            "scripts/dev/finalize_eq_phase2_roadmap.py",
        )
        present = [path for path in obsolete if (REPO_ROOT / path).exists()]
        self.assertEqual([], present)

    def test_supported_ci_workflow_remains_present(self) -> None:
        self.assertTrue((REPO_ROOT / ".github/workflows/tests.yml").is_file())


if __name__ == "__main__":
    unittest.main()
