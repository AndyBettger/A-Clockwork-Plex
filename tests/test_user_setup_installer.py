from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SETUP = ROOT / "setup.sh"
APPLIANCE_INSTALLER = ROOT / "appliance-installer.sh"
LEGACY_INSTALLER = ROOT / "install.sh"
INSTALL_GUIDE = ROOT / "docs" / "INSTALL.md"
ADVANCED_GUIDE = ROOT / "docs" / "appliance-installer.md"
README = ROOT / "README.md"


class UserSetupInstallerTests(unittest.TestCase):
    def test_setup_help_is_safe_and_describes_one_command_install(self) -> None:
        result = subprocess.run(
            ["bash", str(SETUP), "--help"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn("bash setup.sh", result.stdout)
        self.assertIn("pinned CamillaDSP artifact", result.stdout)
        self.assertIn("Plexamp claim", result.stdout)

    def test_release_installer_shell_syntax_is_valid(self) -> None:
        result = subprocess.run(
            ["bash", "-n", str(SETUP), str(APPLIANCE_INSTALLER)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_setup_delegates_to_existing_guarded_owners(self) -> None:
        text = SETUP.read_text(encoding="utf-8")
        self.assertIn("scripts/fetch-camilladsp-4.1.3.sh", text)
        self.assertIn("FETCH-CAMILLADSP-4.1.3", text)
        self.assertIn('bash "$REPO_ROOT/appliance-installer.sh"', text)
        self.assertNotIn('bash "$REPO_ROOT/install.sh"', text)
        self.assertIn("--fresh-bootstrap", text)
        self.assertIn("APPLY-A-CLOCKWORK-PLEX", text)
        self.assertIn("ACP_PLEXAMP_CLAIM_EXIT", text)
        self.assertIn('"$NODE_BIN" js/index.js', text)
        self.assertIn("claim code is entered directly into Plexamp", text)

    def test_guarded_engine_has_unambiguous_release_name(self) -> None:
        self.assertTrue(APPLIANCE_INSTALLER.is_file())
        self.assertFalse(LEGACY_INSTALLER.exists())

    def test_advanced_engine_guide_is_discoverable_and_matches_real_controls(self) -> None:
        guide = ADVANCED_GUIDE.read_text(encoding="utf-8")
        readme = README.read_text(encoding="utf-8")
        self.assertIn("docs/appliance-installer.md", readme)
        self.assertIn("use [`docs/INSTALL.md`](INSTALL.md) and run `bash setup.sh`", guide)
        self.assertIn("`appliance-installer.sh` is the lower-level guarded", guide)
        for option in (
            "--plan",
            "--apply",
            "APPLY-A-CLOCKWORK-PLEX",
            "--fresh-bootstrap",
            "--audio PROFILE",
            "--weather-observations PROVIDER",
            "--camilladsp-binary PATH",
            "--wu-station-id ID",
            "--wu-api-key-file PATH",
            "--dashboard-url URL",
            "--non-interactive",
        ):
            self.assertIn(option, guide)
        self.assertIn("Controlled hardware reboot checkpoint", guide)
        self.assertIn("Plexamp claim checkpoint", guide)
        self.assertIn("Transaction and rollback policy", guide)
        self.assertNotIn("bash install.sh", guide)

    def test_setup_does_not_accept_plex_claim_material(self) -> None:
        text = SETUP.read_text(encoding="utf-8")
        self.assertNotIn("--plex-claim", text)
        self.assertNotIn("PLEX_CLAIM_TOKEN", text)
        self.assertNotIn("PLEX_CLAIM_CODE", text)

    def test_install_guide_uses_one_command_setup_and_commissioning_contract(self) -> None:
        text = INSTALL_GUIDE.read_text(encoding="utf-8")
        self.assertIn("bash setup.sh", text)
        self.assertNotIn('CAMILLA_BINARY="$HOME/', text)
        self.assertIn("automatically launches the installed Plexamp Headless process", text)
        self.assertIn("A Clockwork Plex - Plexamp", text)
        self.assertIn("Follows system output", text)
        self.assertIn("password manager", text)
        self.assertIn("station ID and API key", text)


if __name__ == "__main__":
    unittest.main()
