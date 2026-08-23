from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class RetiredStageCGuardTests(unittest.TestCase):
    def test_stage_c_executable_scaffolding_remains_retired(self) -> None:
        forbidden_exact = (
            "scripts/stage_c_transaction",
            "scripts/audio/play-source-test.py",
            "scripts/audio/test-tone.py",
        )
        forbidden_globs = (
            "scripts/stage_c*.py",
            "scripts/*stage-c*.sh",
            "scripts/audio/*stage-c*",
        )

        present = [
            path
            for path in forbidden_exact
            if (REPO_ROOT / path).exists()
        ]
        for pattern in forbidden_globs:
            present.extend(
                str(path.relative_to(REPO_ROOT))
                for path in REPO_ROOT.glob(pattern)
            )

        self.assertEqual([], sorted(set(present)))

    def test_positive_stage_c_test_suite_remains_retired(self) -> None:
        present = sorted(
            str(path.relative_to(REPO_ROOT))
            for path in (REPO_ROOT / "tests").glob("test_stage_c*.py")
        )
        self.assertEqual([], present)


if __name__ == "__main__":
    unittest.main()
