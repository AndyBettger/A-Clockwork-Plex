from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SETUP = ROOT / "setup.sh"
INSTALL_GUIDE = ROOT / "docs" / "INSTALL.md"


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

    def test_setup_delegates_to_existing_guarded_owners(self) -> None:
        text = SETUP.read_text(encoding="utf-8")
        self.assertIn("scripts/fetch-camilladsp-4.1.3.sh", text)
        self.assertIn("FETCH-CAMILLADSP-4.1.3", text)
        self.assertIn('bash "$REPO_ROOT/install.sh"', text)
        self.assertIn("--fresh-bootstrap", text)
        self.assertIn("APPLY-A-CLOCKWORK-PLEX", text)
        self.assertIn("ACP_PLEXAMP_CLAIM_EXIT", text)
        self.assertIn('"$NODE_BIN" js/index.js', text)
        self.assertIn("claim code is entered directly into Plexamp", text)

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
