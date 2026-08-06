from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "scripts/run-stage-c-terminal-install-from-source-root.sh"


class StageCTerminalSourceRootLauncherTests(unittest.TestCase):
    def setUp(self) -> None:
        self.content = LAUNCHER.read_text(encoding="utf-8")

    def test_launcher_parses(self) -> None:
        result = subprocess.run(
            ["bash", "-n", str(LAUNCHER)],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_launcher_changes_to_verified_source_before_operator(self) -> None:
        change_directory = self.content.index('cd "$REPO_ROOT"')
        execute_operator = self.content.index(
            "exec bash scripts/run-stage-c-terminal-install-verified.sh"
        )
        self.assertLess(change_directory, execute_operator)
        self.assertEqual(self.content.count('cd "$REPO_ROOT"'), 1)
        self.assertEqual(self.content.count("exec bash"), 1)


if __name__ == "__main__":
    unittest.main()
