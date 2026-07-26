from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "test-alsa-control-alias-migration.sh"


class AlsaControlAliasMigrationSafetyTests(unittest.TestCase):
    def test_script_has_valid_shell_syntax(self):
        result = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_default_is_prepare_only_before_privileged_actions(self):
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("MODE=prepare", text)
        self.assertLess(text.index('if [[ "$MODE" == prepare ]]'), text.index("sudo -v"))
        self.assertIn("No production file, service, mixer value or audio route has been changed.", text)

    def test_apply_requires_explicit_confirmation_and_separate_alias_file(self):
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('REQUIRED_CONFIRMATION="ACP-CONTROL-ALIASES"', text)
        self.assertIn("98-a-clockwork-plex-control-aliases.conf", text)
        self.assertIn('sudo install -o root -g root -m 0644 "$ALIAS_CANDIDATE" "$ALIAS_CONFIG"', text)
        self.assertNotIn('sudo install -o root -g root -m 0644 "$ALIAS_CANDIDATE" "$LIVE_CONFIG"', text)

    def test_aliases_only_map_named_controls_to_the_physical_card(self):
        text = SCRIPT.read_text(encoding="utf-8")
        for name in (
            "acp_dmix",
            "acp_master",
            "acp_master_volume",
            "acp_plexamp",
            "acp_plexamp_volume",
            "acp_airplay",
            "acp_airplay_volume",
            "acp_alarm",
            "acp_alarm_volume",
        ):
            self.assertIn(f"ctl.{name}", text)
        self.assertNotIn("pcm.acp_dmix", text)
        self.assertNotIn("aplay ", text)

    def test_only_plexamp_and_dashboard_are_restarted(self):
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("SERVICES=(plexamp.service a-clockwork-plex.service)", text)
        self.assertNotIn("shairport-sync.service", text)
        self.assertNotIn("camilladsp.service", text)

    def test_apply_checks_log_and_monitored_mixer_state(self):
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("Invalid CTL acp_plexamp", text)
        self.assertIn("controls-before.txt", text)
        self.assertIn("controls-after.txt", text)
        self.assertIn("Digital", text)
        self.assertIn("A Clockwork Master", text)
        self.assertIn('cmp -s "$CONTROLS_BEFORE" "$CONTROLS_AFTER"', text)

    def test_failure_and_signal_paths_restore_the_prior_alias_state(self):
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("rollback_apply", text)
        self.assertIn('trap on_exit EXIT', text)
        self.assertIn("trap 'exit 129' HUP", text)
        self.assertIn('sudo rm -f "$ALIAS_CONFIG"', text)
        self.assertIn('sudo cp -a "$BACKUP_DIR/original-alias.conf" "$ALIAS_CONFIG"', text)


if __name__ == "__main__":
    unittest.main()
