from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "install.sh"


class FullInstallerVerifierPlanTests(unittest.TestCase):
    def test_root_plan_names_matching_post_install_verifier(self) -> None:
        result = subprocess.run(
            [
                "bash",
                str(INSTALLER),
                "--audio",
                "direct",
                "--weather-observations",
                "weather-underground",
                "--project-user",
                "bedroomclock",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(
            "bash scripts/verify-appliance.sh --audio direct "
            "--weather-observations weather-underground --project-user bedroomclock",
            result.stdout,
        )
        self.assertIn("Commit gate inside that application transaction", result.stdout)
        self.assertIn("must pass before its transaction can commit", result.stdout)
        self.assertNotIn("After a future guarded installation", result.stdout)
        self.assertIn("No production file", result.stdout)


if __name__ == "__main__":
    unittest.main()
