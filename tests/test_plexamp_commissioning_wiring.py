from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SETUP = ROOT / "setup.sh"
DEPENDENCIES = ROOT / "installer" / "repository-dependencies.txt"
RESET_CLIENT = ROOT / "app" / "static" / "js" / "settings-reset-defaults.js"
RESET_CSS = ROOT / "app" / "static" / "css" / "settings-reset-defaults.css"
SETTINGS_ADVANCED = ROOT / "app" / "static" / "js" / "settings-advanced.js"


class PlexampCommissioningWiringTests(unittest.TestCase):
    def test_setup_commissions_player_baseline_and_audio_after_guarded_install(self) -> None:
        text = SETUP.read_text(encoding="utf-8")
        self.assertIn("run_plexamp_commissioning", text)
        self.assertIn(
            'python3 "$REPO_ROOT/scripts/commission-plexamp.py" commission --home "$PROJECT_HOME"',
            text,
        )
        self.assertIn("claimed player name is recorded as this appliance's reset baseline", text)
        self.assertIn("managed audio output is verified", text)
        self.assertLess(text.index("run_guarded_installer"), text.index("run_plexamp_commissioning"))

    def test_fresh_install_dependency_closure_contains_commissioning_owner(self) -> None:
        text = DEPENDENCIES.read_text(encoding="utf-8")
        self.assertIn("app/plexamp_commissioning.py", text)
        self.assertIn("scripts/commission-plexamp.py", text)

    def test_new_commissioning_python_and_setup_shell_compile(self) -> None:
        result = subprocess.run(
            [
                "python3",
                "-m",
                "py_compile",
                "app/plexamp_commissioning.py",
                "scripts/commission-plexamp.py",
                "app/configuration_reset.py",
                "app/runner.py",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        shell = subprocess.run(
            ["bash", "-n", "setup.sh"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(shell.returncode, 0, shell.stderr)

    def test_reset_client_exposes_commissioning_without_claiming_home_reset(self) -> None:
        text = RESET_CLIENT.read_text(encoding="utf-8")
        self.assertIn("A Clockwork Plex + managed Plexamp", text)
        self.assertIn("player name will return to the name captured during appliance setup", text)
        self.assertIn("audio output will return to A Clockwork Plex - Plexamp", text)
        self.assertIn("Plexamp Home is not part of this reset", text)
        self.assertIn("plexamp_commissioning_change_count", text)
        self.assertNotIn("player identity, Headless preferences", text)
        result = subprocess.run(
            ["node", "--check", str(RESET_CLIENT)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_reset_review_layout_reserves_status_width_at_appliance_resolution(self) -> None:
        css = RESET_CSS.read_text(encoding="utf-8")
        advanced = SETTINGS_ADVANCED.read_text(encoding="utf-8")

        self.assertIn(
            "grid-template-columns: minmax(0, 1.7fr) minmax(280px, 1fr)",
            css,
        )
        self.assertIn("[data-reset-review-status]:not([hidden])", css)
        self.assertIn("grid-template-columns: 1fr", css)
        self.assertIn("white-space: normal", css)
        self.assertIn("min-width: 0", css)
        self.assertIn("20260903-reset-review-layout-v3", advanced)


if __name__ == "__main__":
    unittest.main()
