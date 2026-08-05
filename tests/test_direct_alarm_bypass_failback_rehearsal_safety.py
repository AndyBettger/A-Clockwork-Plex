from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / "scripts" / "test-direct-alarm-bypass-failback-rehearsal.sh"


class DirectAlarmBypassFailbackRehearsalSafetyTests(unittest.TestCase):
    def test_script_has_valid_shell_syntax(self):
        result = subprocess.run(
            ["bash", "-n", str(LAB)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_prepare_only_exits_before_privileged_or_physical_actions(self):
        text = LAB.read_text(encoding="utf-8")
        gate = text.index('if [[ "$MODE" == prepare ]]')
        self.assertGreater(text.index("sudo -v", gate), gate)
        self.assertGreater(text.index("stop_services", gate), gate)
        self.assertGreater(text.index('aplay -q -D acp_plexamp', gate), gate)
        self.assertIn("invokes no\nsudo command", text)
        self.assertIn("The physical DAC has not been opened", text)

    def test_activation_is_explicit_bounded_and_temporary(self):
        text = LAB.read_text(encoding="utf-8")
        self.assertIn('REQUIRED_CONFIRMATION="STAGE-C0-DIRECT-FAILBACK-REAL-DAC"', text)
        self.assertIn("Duration must be from 120 to 1200 seconds", text)
        self.assertIn("trap on_exit EXIT", text)
        self.assertIn("trap '' INT", text)
        self.assertNotIn("--keep-active", text)
        self.assertNotIn("systemctl enable", text)
        self.assertNotIn("modprobe", text)
        self.assertNotIn("CAMILLADSP_BINARY", text)
        self.assertNotIn("kill -HUP", text)
        self.assertNotIn("a-clockwork-plex-camilladsp.service", text)

    def test_music_uses_master_and_alarm_bypasses_it(self):
        text = LAB.read_text(encoding="utf-8")
        self.assertIn('pcm.acp_master_volume', text)
        self.assertIn('slave.pcm "acp_dmix"', text)
        self.assertIn('slave.pcm "acp_master"', text)
        alarm_start = text.index("pcm.acp_alarm_volume")
        alarm_end = text.index("pcm.acp_alarm {", alarm_start)
        alarm_block = text[alarm_start:alarm_end]
        self.assertIn('slave.pcm "acp_dmix"', alarm_block)
        self.assertNotIn('slave.pcm "acp_master"', alarm_block)

    def test_public_pcm_names_and_expected_services_are_retained(self):
        text = LAB.read_text(encoding="utf-8")
        for pcm in ("acp_dmix", "acp_master", "acp_plexamp", "acp_airplay", "acp_alarm"):
            self.assertIn(f"pcm.{pcm}", text)
        self.assertIn(
            "SERVICES=(plexamp.service shairport-sync.service a-clockwork-plex.service)",
            text,
        )
        self.assertNotIn("/etc/shairport-sync.conf", text)

    def test_rollback_restores_exact_config_mixer_and_service_state(self):
        text = LAB.read_text(encoding="utf-8")
        self.assertIn("ROLLBACK_NEEDED=true", text)
        self.assertIn('sudo cp -a "$SNAPSHOT_DIR/original-alsa.conf" "$ALSA_CONFIG"', text)
        self.assertIn("rollback-alsa-config", text)
        self.assertIn("rollback-mixer-state", text)
        self.assertIn("restore_mixer_levels", text)
        self.assertIn("restore_services", text)
        self.assertIn("cmp -s \"$ORIGINAL_SHA_FILE\" \"$RESTORED_SHA_FILE\"", text)

    def test_manual_gate_proves_real_alarm_independence(self):
        text = LAB.read_text(encoding="utf-8")
        self.assertIn("master-zero", text)
        self.assertIn("real scheduled alarm", text)
        self.assertIn("Music Master remains zero", text)
        self.assertIn("Snooze", text)
        self.assertIn("Dismiss", text)
        self.assertIn("master-restore", text)

    def test_prepare_output_uses_selected_duration(self):
        text = LAB.read_text(encoding="utf-8")
        self.assertIn("--duration $DURATION_SECONDS", text)
        self.assertNotIn("--duration 900 \\", text)


if __name__ == "__main__":
    unittest.main()
