from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / "scripts" / "test-alsa-control-alias-lab.sh"


class AlsaControlAliasLaboratorySafetyTests(unittest.TestCase):
    def test_script_has_valid_shell_syntax(self):
        result = subprocess.run(
            ["bash", "-n", str(LAB)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_default_is_prepare_only(self):
        text = LAB.read_text(encoding="utf-8")
        self.assertIn("MODE=prepare", text)
        self.assertIn('if [[ "$MODE" == prepare ]]', text)
        self.assertGreater(text.index("amixer -D acp_plexamp"), text.index('if [[ "$MODE" == prepare ]]'))

    def test_named_control_aliases_target_the_physical_card(self):
        text = LAB.read_text(encoding="utf-8")
        for name in (
            "ctl.acp_dmix",
            "ctl.acp_master",
            "ctl.acp_master_volume",
            "ctl.acp_plexamp",
            "ctl.acp_plexamp_volume",
            "ctl.acp_airplay",
            "ctl.acp_airplay_volume",
            "ctl.acp_alarm",
            "ctl.acp_alarm_volume",
        ):
            self.assertIn(name, text)
        self.assertIn('card "$ALSA_CARD"', text)

    def test_run_is_read_only_and_opens_no_pcm(self):
        text = LAB.read_text(encoding="utf-8")
        self.assertIn('amixer -D "$name" scontrols', text)
        self.assertNotIn("systemctl", text)
        self.assertNotIn("sudo ", text)
        self.assertNotIn("modprobe", text)
        self.assertNotIn("aplay -q", text)
        self.assertNotIn("speaker-test", text)
        self.assertNotIn("/etc/alsa/conf.d/99-a-clockwork-plex-shared.conf\" <<", text)

    def test_live_failure_is_diagnostic_not_a_test_failure(self):
        text = LAB.read_text(encoding="utf-8")
        self.assertIn("live-ctl-acp_plexamp", text)
        self.assertIn("INFO", text)
        self.assertIn("isolated-ctl-%s", text)


if __name__ == "__main__":
    unittest.main()
