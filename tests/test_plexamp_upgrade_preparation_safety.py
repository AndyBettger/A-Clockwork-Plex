from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "prepare-plexamp-upgrade-rehearsal.sh"


class PlexampUpgradePreparationSafetyTests(unittest.TestCase):
    def test_script_has_valid_shell_syntax(self):
        result = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_script_is_read_only(self):
        text = SCRIPT.read_text(encoding="utf-8")
        forbidden = [
            "systemctl stop",
            "systemctl start",
            "systemctl restart",
            "./upgrade.sh",
            "bash upgrade.sh",
            "curl ",
            "wget ",
            "sudo ",
            "rm -f /etc",
            "install -o root",
        ]
        for token in forbidden:
            self.assertNotIn(token, text)

    def test_captures_upgrade_and_audio_device_evidence(self):
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("upgrade-sh.sha256", text)
        self.assertIn("audioDeviceUuid", text)
        self.assertIn("systemctl cat plexamp.service", text)
        self.assertIn("aplay -L", text)
        self.assertIn("98-a-clockwork-plex-control-aliases.conf", text)


if __name__ == "__main__":
    unittest.main()
